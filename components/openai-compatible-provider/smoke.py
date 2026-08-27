from __future__ import annotations

import json
import os
import platform
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ARTIFACT_DIR = Path(os.environ.get("STUDYBUDDY_PROVIDER_ARTIFACT_DIR", "H:/studybuddy-test/artifacts/openai-compatible-provider"))
TEST_API_KEY = "TEST_ONLY_API_KEY"
MAX_RESPONSE_BYTES = 1024


class ProtocolError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Completion:
    content: str
    citation_keys: tuple[str, ...]


def _citation_keys(content: str) -> tuple[str, ...]:
    import re
    return tuple(dict.fromkeys(re.findall(r"\[(ctx-[A-Za-z0-9_-]{1,70})\]", content)))


def complete(base_url: str, *, model: str, messages: list[dict[str, str]], api_key: str, timeout: float = 0.2) -> Completion:
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0, "max_tokens": 128, "stream": False}).encode("utf-8")
    request = Request(f"{base_url.rstrip('/')}/chat/completions", data=payload,
                      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ProtocolError("response_too_large")
    except ProtocolError:
        raise
    except HTTPError as error:
        raise ProtocolError({401: "auth_failed", 403: "forbidden", 429: "rate_limited"}.get(error.code, "unavailable" if error.code >= 500 else "protocol_error")) from None
    except TimeoutError:
        raise ProtocolError("timeout") from None
    except URLError as error:
        raise ProtocolError("timeout" if getattr(error, "reason", None).__class__.__name__ == "timeout" else "connection_failed") from None
    except OSError:
        raise ProtocolError("connection_failed") from None
    try:
        value = json.loads(raw.decode("utf-8"))
        content = value["choices"][0]["message"]["content"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError):
        raise ProtocolError("malformed_response") from None
    if not isinstance(content, str) or not content.strip():
        raise ProtocolError("empty_response")
    return Completion(content=content, citation_keys=_citation_keys(content))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:
        mode = self.path.strip("/").split("/")[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "bad_request"})
            return
        self.server.captured.append({"mode": mode, "authorization": self.headers.get("Authorization", ""), "body": body})
        if mode == "timeout":
            time.sleep(0.5)
            return
        if mode in {"401", "403", "429", "500"}:
            self._json(int(mode), {"error": {"code": "synthetic"}})
        elif mode == "malformed":
            self._raw(200, b"not-json")
        elif mode == "empty":
            self._json(200, {"choices": [{"message": {"content": "  "}}]})
        elif mode == "oversized":
            self._json(200, {"choices": [{"message": {"content": "x" * (MAX_RESPONSE_BYTES + 100)}}]})
        else:
            self._json(200, {"id": "synthetic-1", "choices": [{"message": {"content": "Offline answer [ctx-synthetic-1]"}}]})

    def _raw(self, status: int, payload: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, value: object) -> None:
        self._raw(status, json.dumps(value, ensure_ascii=False).encode("utf-8"))


def attempt(base_url: str, mode: str) -> str:
    try:
        result = complete(f"{base_url}/{mode}", model="offline-model", api_key=TEST_API_KEY,
                          messages=[{"role": "user", "content": "synthetic protocol input"}])
        if mode == "success":
            return "success" if result.citation_keys == ("ctx-synthetic-1",) else "unexpected_citations"
        return "unexpected_success"
    except ProtocolError as error:
        return error.code


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.captured = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    started = time.perf_counter()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        expected = {"success": "success", "401": "auth_failed", "403": "forbidden", "429": "rate_limited", "500": "unavailable", "timeout": "timeout", "malformed": "malformed_response", "empty": "empty_response", "oversized": "response_too_large"}
        checks = {mode: attempt(base_url, mode) for mode in expected}
        captured = server.captured
        request_contract = {
            "endpoint": "chat/completions",
            "all_bearer_auth": all(item["authorization"] == f"Bearer {TEST_API_KEY}" for item in captured),
            "all_model_values": all(item["body"].get("model") == "offline-model" for item in captured),
            "all_non_streaming": all(item["body"].get("stream") is False for item in captured),
            "all_synthetic_messages": all(item["body"].get("messages") == [{"role": "user", "content": "synthetic protocol input"}] for item in captured),
        }
        passed = checks == expected and all(request_contract.values())
        payload = {
            "component": "openai-compatible-provider",
            "component_version": "1.0.0",
            "status": "smoke_passed" if passed else "failed",
            "scope": "independent local loopback OpenAI-compatible non-streaming protocol smoke; no external provider called",
            "runtime": {"python": platform.python_version()},
            "network": {"required": False, "called": False, "loopback_only": True},
            "checks": checks,
            "request_contract": request_contract,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "limitations": ["does not prove real provider, account, model, cost, SSE streaming, or public-network availability", "does not store request bodies, response bodies, or credentials in the artifact"],
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "latest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"component": payload["component"], "status": payload["status"], "checks": len(payload["checks"])}, ensure_ascii=False))
    raise SystemExit(0 if payload["status"] == "smoke_passed" else 1)


if __name__ == "__main__":
    main()
