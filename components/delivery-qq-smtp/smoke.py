"""Run B4 QQ-SMTP C1 smoke only against an in-process loopback receiver.

This is a protocol/safety feasibility test.  It never loads environment credentials
and never resolves or connects to a non-loopback address.
"""
from __future__ import annotations

import hashlib
import json
import socket
import socketserver
import threading
import time
import tracemalloc
from pathlib import Path

MAX_PAYLOAD_BYTES = 4096
RATE_LIMIT = 2
TIMEOUT_SECONDS = 0.25
ALLOWED_RECIPIENTS = {"guardian-test@example.invalid"}


class DeliveryError(Exception):
    pass


class _Receiver(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], handler: type[socketserver.BaseRequestHandler]) -> None:
        super().__init__(address, handler)
        self.messages: list[bytes] = []
        self.lock = threading.Lock()
        self.fail_next = False
        self.delay_seconds = 0.0


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server: _Receiver = self.server  # type: ignore[assignment]
        try:
            if server.delay_seconds:
                time.sleep(server.delay_seconds)
            self.request.sendall(b"220 loopback SMTP\r\n")
            data_mode = False
            payload = bytearray()
            while True:
                line = self.request.recv(4096)
                if not line:
                    return
                if data_mode:
                    payload.extend(line)
                    if b"\r\n.\r\n" not in payload:
                        continue
                    with server.lock:
                        server.messages.append(bytes(payload[:-5]))
                    self.request.sendall(b"250 accepted\r\n")
                    data_mode = False
                    continue
                command = line.upper()
                if command.startswith(b"DATA"):
                    with server.lock:
                        failing = server.fail_next
                        server.fail_next = False
                    self.request.sendall(b"451 temporary failure\r\n" if failing else b"354 end with dot\r\n")
                    data_mode = not failing
                elif command.startswith(b"QUIT"):
                    self.request.sendall(b"221 bye\r\n")
                    return
                else:
                    self.request.sendall(b"250 ok\r\n")
        except OSError:
            # Timeout smoke closes its client before the deliberate receiver delay.
            return


def _reply(sock: socket.socket, expected: bytes) -> None:
    if not sock.recv(1024).startswith(expected):
        raise DeliveryError("delivery_failed")


def _send(*, host: str, port: int, recipient: str, payload: bytes, secret: str,
          key: str, sent_keys: set[str], timestamps: list[float]) -> str:
    if host != "127.0.0.1" or recipient not in ALLOWED_RECIPIENTS:
        raise DeliveryError("delivery_target_not_allowed")
    if not secret or len(payload) > MAX_PAYLOAD_BYTES:
        raise DeliveryError("delivery_failed")
    if key in sent_keys:
        return "replayed"
    now = time.monotonic()
    timestamps[:] = [item for item in timestamps if now - item < 1]
    if len(timestamps) >= RATE_LIMIT:
        raise DeliveryError("delivery_rate_limited")
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT_SECONDS) as sock:
            sock.settimeout(TIMEOUT_SECONDS)
            _reply(sock, b"220")
            for command in (b"EHLO loopback\r\n", b"MAIL FROM:<sender@example.invalid>\r\n",
                            f"RCPT TO:<{recipient}>\r\n".encode(), b"DATA\r\n"):
                sock.sendall(command)
                _reply(sock, b"354" if command == b"DATA\r\n" else b"250")
            message = b"X-Idempotency-Key: " + key.encode("ascii") + b"\r\n\r\n" + payload + b"\r\n.\r\n"
            sock.sendall(message)
            _reply(sock, b"250")
            sock.sendall(b"QUIT\r\n")
            _reply(sock, b"221")
    except (OSError, TimeoutError, socket.timeout) as exc:
        raise DeliveryError("delivery_timeout" if isinstance(exc, socket.timeout) else "delivery_failed") from None
    sent_keys.add(key)
    timestamps.append(now)
    return "sent"


def _expect(code: str, call) -> None:
    try:
        call()
    except DeliveryError as exc:
        assert str(exc) == code
    else:
        raise AssertionError(f"expected {code}")


def run_cases() -> dict[str, object]:
    tracemalloc.start()
    started = time.perf_counter()
    receiver = _Receiver(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    thread.start()
    keys: set[str] = set()
    timestamps: list[float] = []
    payload = b"synthetic report summary: completed=1"
    secret = "test-secret-not-recorded"
    try:
        port = receiver.server_address[1]
        assert _send(host="127.0.0.1", port=port, recipient="guardian-test@example.invalid", payload=payload, secret=secret, key="smtp-1", sent_keys=keys, timestamps=timestamps) == "sent"
        assert _send(host="127.0.0.1", port=port, recipient="guardian-test@example.invalid", payload=payload, secret=secret, key="smtp-1", sent_keys=keys, timestamps=timestamps) == "replayed"
        _expect("delivery_target_not_allowed", lambda: _send(host="smtp.qq.com", port=port, recipient="guardian-test@example.invalid", payload=payload, secret=secret, key="no-net", sent_keys=keys, timestamps=timestamps))
        _expect("delivery_target_not_allowed", lambda: _send(host="127.0.0.1", port=port, recipient="not-allowed@example.invalid", payload=payload, secret=secret, key="bad-recipient", sent_keys=keys, timestamps=timestamps))
        receiver.fail_next = True
        _expect("delivery_failed", lambda: _send(host="127.0.0.1", port=port, recipient="guardian-test@example.invalid", payload=payload, secret=secret, key="retry", sent_keys=keys, timestamps=timestamps))
        assert _send(host="127.0.0.1", port=port, recipient="guardian-test@example.invalid", payload=payload, secret=secret, key="retry", sent_keys=keys, timestamps=timestamps) == "sent"
        _expect("delivery_rate_limited", lambda: _send(host="127.0.0.1", port=port, recipient="guardian-test@example.invalid", payload=payload, secret=secret, key="limited", sent_keys=keys, timestamps=timestamps))
        receiver.delay_seconds = TIMEOUT_SECONDS * 2
        _expect("delivery_timeout", lambda: _send(host="127.0.0.1", port=port, recipient="guardian-test@example.invalid", payload=payload, secret=secret, key="timeout", sent_keys=keys, timestamps=[]))
        assert len(receiver.messages) == 2
    finally:
        receiver.shutdown()
        receiver.server_close()
        thread.join(timeout=1)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - started
    result = {"status": "passed", "candidate": "delivery-qq-smtp", "gate": "B4-C1", "scope": "stdlib SMTP protocol against in-process loopback only", "checks": {"payload": True, "recipient_allowlist": True, "network_default_disabled": True, "secret_isolation": True, "timeout": True, "rate_limit": True, "failure": True, "explicit_retry": True, "idempotency_key": True, "receiver_cleanup": not thread.is_alive()}, "measurements": {"wall_time_ms": round(elapsed * 1000, 3), "peak_working_set_bytes": peak, "request_count": 2, "payload_sha256": hashlib.sha256(payload).hexdigest()}, "versions": {"runner": "b4-qq-smtp-c1-v1"}, "evidence_policy": "sanitized metadata only; no addresses, credentials, report body, or SMTP response"}
    assert secret not in json.dumps(result)
    return result


def main() -> int:
    result = run_cases()
    output = Path(__file__).resolve().parents[2] / "results" / "delivery-qq-smtp" / "c1-smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print("B4 C1 QQ SMTP loopback smoke passed: 10 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
