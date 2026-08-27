# Component Card: openai-compatible-provider

- Source: project-owned, independent Composer reimplementation of the documented OpenAI-compatible non-streaming HTTP contract. KaoBuddy was used only as historical protocol reference; this component imports no KaoBuddy source.
- License: project-owned test implementation; Python standard library only.
- Version: `1.0.0`.
- Owner boundary: offline loopback protocol/error behavior only. It is not a StudyBuddy runtime dependency and does not establish external Provider availability.
- Independent smoke command: `C:\miniconda\py310\python.exe H:\studybuddy-composer\components\openai-compatible-provider\smoke.py`.
- Real input: requests to a real local `127.0.0.1` HTTP server with a synthetic message and fixed `TEST_ONLY_API_KEY` sentinel.
- Output contract: sanitized JSON at `H:/studybuddy-test/artifacts/openai-compatible-provider/latest.json`; it records stable codes and booleans only, not requests, responses, keys, source text, paths, or raw exceptions.
- Request contract: `${base_url}/chat/completions`; Bearer auth; fixed model/messages/temperature/max_tokens; `stream: false`.
- Verified behavior: successful cited response, HTTP 401/403/429/500 mapping, timeout, malformed JSON/schema, empty content, response byte limit, and request header/body shape.
- Failure boundaries: SSE/streaming, retry policy, real Provider account/model/gateway availability, cost/usage, public network, real source material, browser storage and UI are out of scope.
- Windows prerequisites: Python 3.10 standard library; no package installation or external service.
- Privacy/logging restrictions: loopback-only; only the fixed sentinel key is accepted; artifact excludes full request/response data and credentials.
- Smoke result: `smoke_passed` only after the independent loopback command passes; real Provider remains `not_verified`.
- Integration result: `not started`.
- Evidence path: `H:/studybuddy-test/artifacts/openai-compatible-provider/latest.json`.
