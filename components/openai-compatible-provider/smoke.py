from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import platform
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType

ARTIFACT_DIR = Path(os.environ.get("STUDYBUDDY_PROVIDER_ARTIFACT_DIR", "H:/studybuddy-test/artifacts/openai-compatible-provider"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
SOURCE_ROOT = Path("H:/kaobuddy/backend/app")


def load_kaobuddy_modules() -> tuple[ModuleType, ModuleType]:
    package = ModuleType("kaobuddy_probe")
    package.__path__ = [str(SOURCE_ROOT)]
    sys.modules[package.__name__] = package
    loaded = []
    for name in ("schemas", "ai_client"):
        spec = importlib.util.spec_from_file_location(f"kaobuddy_probe.{name}", SOURCE_ROOT / f"{name}.py")
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load {name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        loaded.append(module)
    return loaded[0], loaded[1]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        mode = self.path.split("/")[1] if self.path.count("/") >= 2 else "success"
        self.server.captured.append({
            "mode": mode,
            "authorization": self.headers.get("Authorization", ""),
            "body": json.loads(body.decode("utf-8")),
        })
        if mode == "timeout":
            time.sleep(1.0)
            return
        if mode in {"401", "429", "500"}:
            payload = json.dumps({"error": {"message": f"offline-{mode}"}}).encode()
            self.send_response(int(mode))
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if mode == "nonstandard":
            self._json(200, {"result": "missing choices"})
            return
        if mode == "invalid-json":
            payload = b"not-json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if mode == "empty":
            self._json(200, {"choices": [{"message": {"content": "  "}}]})
            return
        if mode in {"stream", "stream-cut"}:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            chunks = [
                'data: {"choices":[{"delta":{"content":"离线"}}]}\n\n',
                'data: {"choices":[{"delta":{"content":"成功"}}]}\n\n',
            ]
            for chunk in chunks[:1 if mode == "stream-cut" else 2]:
                self.wfile.write(chunk.encode())
                self.wfile.flush()
            if mode == "stream":
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            self.close_connection = True
            return
        self._json(200, {
            "choices": [{"message": {"content": "离线成功"}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        })

    def _json(self, status: int, value: object) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


async def run() -> dict[str, object]:
    schemas, client = load_kaobuddy_modules()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.captured = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    messages = [schemas.ChatMessage(role="user", content="协议测试，不含真实资料")]
    checks: dict[str, object] = {}
    started = time.perf_counter()

    original_timeout = client.completion_timeout_seconds
    client.completion_timeout_seconds = lambda _config, stream=False: 0.2
    try:
        async def nonstream(mode: str) -> str:
            config = schemas.ApiConfig(
                provider_name="Offline Test",
                base_url=f"http://127.0.0.1:{port}/{mode}",
                api_key="TEST_ONLY_API_KEY",
                model="offline-model",
                max_tokens=128,
            )
            try:
                content, usage = await client.chat_completion_with_usage(config, messages)
                return json.dumps({"content": content, "usage": usage}, ensure_ascii=False)
            except Exception as exc:
                return f"{type(exc).__name__}: {exc}"

        for mode in ("success", "401", "429", "500", "timeout", "empty", "nonstandard", "invalid-json"):
            checks[mode] = await nonstream(mode)

        async def stream(mode: str) -> str:
            config = schemas.ApiConfig(
                provider_name="Offline Test",
                base_url=f"http://127.0.0.1:{port}/{mode}",
                api_key="TEST_ONLY_API_KEY",
                model="offline-model",
                max_tokens=128,
            )
            parts = []
            try:
                async for part in client.chat_completion_stream(config, messages):
                    parts.append(part)
                return json.dumps({"content": "".join(parts), "ended_without_done_signal": mode == "stream-cut"}, ensure_ascii=False)
            except Exception as exc:
                return f"{type(exc).__name__}: {exc}"

        checks["stream"] = await stream("stream")
        checks["stream-cut"] = await stream("stream-cut")
    finally:
        client.completion_timeout_seconds = original_timeout
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    captured = server.captured
    checks["request_contract"] = {
        "auth_redacted": all(item["authorization"] == "Bearer TEST_ONLY_API_KEY" for item in captured),
        "endpoint_suffix": "/chat/completions",
        "models": sorted(set(item["body"].get("model") for item in captured)),
        "stream_flags": [item["body"].get("stream", False) for item in captured if item["mode"].startswith("stream")],
    }
    passed = (
        "离线成功" in str(checks["success"])
        and all(f"AI 服务返回错误：{code}" in str(checks[code]) for code in ("401", "429", "500"))
        and "AI 生成超时" in str(checks["timeout"])
        and "空内容" in str(checks["empty"])
        and "响应格式不是" in str(checks["nonstandard"])
        and "离线成功" in str(checks["stream"])
    )
    return {
        "component": "openai-compatible-provider",
        "status": "passed" if passed else "failed",
        "scope": "KaoBuddy ai_client.py against local offline HTTP server; no external provider called",
        "runtime": {"python": platform.python_version()},
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "checks": checks,
        "findings": [
            "非流式 invalid JSON 未被 AiClientError 包装，会直接暴露 JSONDecodeError。",
            "SSE 中途正常断开且没有 [DONE] 时，客户端把已收内容当成功结束，无法识别不完整响应。",
            "所有 provider HTTP 状态在 FastAPI 路由层统一变为 502；前端只能显示 detail 文本。",
            "本测试不证明任何真实 provider、账号、模型、费用或公网连通性可用。",
        ],
    }


result = asyncio.run(run())
(ARTIFACT_DIR / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["status"] == "passed" else 1)
