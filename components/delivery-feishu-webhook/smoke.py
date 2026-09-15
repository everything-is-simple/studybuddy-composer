"""Run B4 Feishu-webhook C1 smoke only against an in-process HTTP receiver.

No environment configuration is read.  The sender refuses all non-loopback URLs.
"""
from __future__ import annotations

import hashlib
import http.server
import json
import threading
import time
import tracemalloc
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_PAYLOAD_BYTES = 4096
RATE_LIMIT = 2
TIMEOUT_SECONDS = 0.25


class DeliveryError(Exception):
    pass


class _Receiver(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address) -> None:  # type: ignore[no-untyped-def]
        # The timeout case closes its loopback socket while the receiver sleeps.
        return

    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, _Handler)
        self.requests: list[tuple[str, bytes]] = []
        self.lock = threading.Lock()
        self.fail_next = False
        self.delay_seconds = 0.0


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        server: _Receiver = self.server  # type: ignore[assignment]
        try:
            if server.delay_seconds:
                time.sleep(server.delay_seconds)
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            with server.lock:
                server.requests.append((self.headers.get("Idempotency-Key", ""), body))
                failing = server.fail_next
                server.fail_next = False
            self.send_response(503 if failing else 200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"code":1}' if failing else b'{"code":0}')
        except (BrokenPipeError, ConnectionResetError):
            # Timeout smoke deliberately closes the local client before response.
            return


def _send(*, url: str, payload: dict[str, object], secret: str, key: str,
          sent_keys: set[str], timestamps: list[float]) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path != "/hook":
        raise DeliveryError("delivery_target_not_allowed")
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()
    if not secret or len(raw) > MAX_PAYLOAD_BYTES:
        raise DeliveryError("delivery_failed")
    if key in sent_keys:
        return "replayed"
    now = time.monotonic()
    timestamps[:] = [item for item in timestamps if now - item < 1]
    if len(timestamps) >= RATE_LIMIT:
        raise DeliveryError("delivery_rate_limited")
    request = Request(url, data=raw, method="POST", headers={"Content-Type": "application/json", "Idempotency-Key": key})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # nosec B310: loopback-only URL validated above
            if response.status != 200 or response.read() != b'{"code":0}':
                raise DeliveryError("delivery_failed")
    except HTTPError:
        raise DeliveryError("delivery_failed") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise DeliveryError("delivery_timeout" if isinstance(exc, TimeoutError) else "delivery_failed") from None
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
    receiver = _Receiver(("127.0.0.1", 0))
    thread = threading.Thread(target=receiver.serve_forever, daemon=True)
    thread.start()
    payload = {"msg_type": "text", "content": {"text": "synthetic report summary"}}
    secret = "test-webhook-secret-not-recorded"
    keys: set[str] = set()
    timestamps: list[float] = []
    try:
        url = f"http://127.0.0.1:{receiver.server_address[1]}/hook"
        assert _send(url=url, payload=payload, secret=secret, key="feishu-1", sent_keys=keys, timestamps=timestamps) == "sent"
        assert _send(url=url, payload=payload, secret=secret, key="feishu-1", sent_keys=keys, timestamps=timestamps) == "replayed"
        _expect("delivery_target_not_allowed", lambda: _send(url="https://open.feishu.cn/open-apis/bot/v2/hook/example", payload=payload, secret=secret, key="no-net", sent_keys=keys, timestamps=timestamps))
        _expect("delivery_target_not_allowed", lambda: _send(url=f"http://127.0.0.1:{receiver.server_address[1]}/wrong", payload=payload, secret=secret, key="wrong-path", sent_keys=keys, timestamps=timestamps))
        receiver.fail_next = True
        _expect("delivery_failed", lambda: _send(url=url, payload=payload, secret=secret, key="retry", sent_keys=keys, timestamps=timestamps))
        assert _send(url=url, payload=payload, secret=secret, key="retry", sent_keys=keys, timestamps=timestamps) == "sent"
        _expect("delivery_rate_limited", lambda: _send(url=url, payload=payload, secret=secret, key="limited", sent_keys=keys, timestamps=timestamps))
        receiver.delay_seconds = TIMEOUT_SECONDS * 2
        _expect("delivery_timeout", lambda: _send(url=url, payload=payload, secret=secret, key="timeout", sent_keys=keys, timestamps=[]))
        assert len(receiver.requests) == 3
    finally:
        receiver.shutdown()
        receiver.server_close()
        thread.join(timeout=1)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - started
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode()
    result = {"status": "passed", "candidate": "delivery-feishu-webhook", "gate": "B4-C1", "scope": "stdlib HTTP protocol against in-process loopback only", "checks": {"payload": True, "url_allowlist": True, "network_default_disabled": True, "secret_isolation": True, "timeout": True, "rate_limit": True, "failure": True, "explicit_retry": True, "idempotency_key": True, "receiver_cleanup": not thread.is_alive()}, "measurements": {"wall_time_ms": round(elapsed * 1000, 3), "peak_working_set_bytes": peak, "request_count": 3, "payload_sha256": hashlib.sha256(raw).hexdigest()}, "versions": {"runner": "b4-feishu-webhook-c1-v1"}, "evidence_policy": "sanitized metadata only; no URL, credentials, report body, or raw response"}
    assert secret not in json.dumps(result)
    return result


def main() -> int:
    result = run_cases()
    output = Path(__file__).resolve().parents[2] / "results" / "delivery-feishu-webhook" / "c1-smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print("B4 C1 Feishu webhook loopback smoke passed: 10 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
