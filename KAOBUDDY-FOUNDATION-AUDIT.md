# KaoBuddy Foundation Audit

Audit date: 2026-08-19. This phase performed inventory and isolated smoke tests only. No StudyBuddy business code or reference installer was executed.

## 1. Persistence

KaoBuddy does **not** use SQLite for product data.

- IndexedDB name: `kaobuddy-db`.
- Declared version: `2`.
- Object stores: `projects`, `materials`, `notes`, `tasks`, `mistakes`, `weak_points`, `mock_attempts`.
- Indexes: `materials.project_id`; `notes.project_id`; `tasks.project_id`, `tasks.date`; and `project_id` on mistakes/weak points/mock attempts.
- Migration mechanism: version-gated `MIGRATIONS` in `src/storage.ts`. Only migration version 1 exists although `DB_VERSION=2`; version 2 is an example comment, so opening v2 performs no schema change beyond v1.
- Export: `exportAll()` returns JSON v2 for all object stores. API config and invite state are deliberately omitted.
- Import: despite README saying merge, `importAll()` clears every store first and then inserts imported rows. This is destructive replacement, not merge. There is no transaction spanning all stores, so partial failure can leave partial data.
- API config: plaintext JSON in `localStorage['kaobuddy-api-config']`, including API key, provider, base URL, model, temperature, and max tokens.
- Invite state: `localStorage['kaobuddy-invite-state']` includes invite code and counters.
- Delete behavior: deleting a project scans and deletes child records by `project_id`, then deletes the project. Deleting one material does not cascade tasks/notes that may reference it.
- Browser clearing risk: clearing site data/profile, private mode, quota eviction, browser reset, or changing origin/port can remove or isolate all product data and credentials. No automatic filesystem backup exists.
- StudyBuddy suitability: unsuitable as the authoritative store. IndexedDB may remain a cache, but StudyBuddy's required local durable store should be SQLite plus retained local files and explicit backup/restore.

Independent SQLite feasibility passed. See `components/sqlite-local/COMPONENT-CARD.md` and `H:/studybuddy-test/artifacts/sqlite-local/latest.json`.

## 2. AI Request Chain

Actual BYOK chain is browser UI -> same-origin FastAPI -> `httpx` -> `${base_url}/chat/completions`. README statements that BYOK goes directly from browser to provider are inaccurate; `src/api.ts` posts `api_config`, including API key, to FastAPI, and `backend/app/ai_client.py` performs the provider request.

- Test endpoint: `POST /api/ai/test` performs a real provider call.
- Custom providers: arbitrary HTTP(S) base URL, provider name, model, temperature, and max tokens are accepted.
- Non-stream: validates `choices[0].message.content`, trims text, rejects empty content, and optionally returns usage internally.
- Stream: parses `data: ` SSE lines and yields `choices[0].delta.content`; malformed events are logged/skipped.
- Errors: upstream 401/403/429/5xx become `AiClientError` text, then FastAPI HTTP 502. Frontend displays detail but has no status-specific retry/auth/rate-limit state.
- Timeout: 60-300 seconds non-stream, 120-420 seconds stream, scaled by max tokens.
- Nonstandard JSON object: explicit compatible-format error. Invalid JSON: raw `JSONDecodeError`, not the intended error type.
- SSE disconnect: missing `[DONE]` is not detected; partial output can be accepted as success.
- Logging: no request body/full successful output logging. Provider/model/prompt chars/max tokens/timing are logged. Truncated upstream error body may reach logs and UI.
- Tokens/cost: BYOK usage is discarded. Invite mode records usage and estimated CNY based on configured prices.
- DeepSeek hard-coding: `deepseek-v4*` may receive `thinking: {type:'disabled'}`; image recognition is blocked when provider/base URL/model contains DeepSeek markers.
- Real provider status: **not verified**. Offline protocol smoke is not provider availability evidence.

## 3. Local Launch

Inspected launch modes:

1. `npm run dev` executes `scripts/dev.mjs`; it creates `.venv`, runs `pip install -e .[test]` every launch, runs `npm install` if Vite is absent, starts FastAPI on 8000, then Vite on 5173.
2. `open-kaobuddy.bat` similarly creates a venv, installs Python dependencies, conditionally installs npm dependencies, builds frontend, opens 8000, and starts uvicorn.
3. `open-kaobuddy.command` does the same for macOS and may remove/recreate a broken `.venv`.
4. Portable package is described as launching FastAPI at 8000, but its installer/launcher was not read or executed under the task boundary.

Isolated source launch evidence:

- KaoBuddy FastAPI itself started successfully on `127.0.0.1:18731`; `/health` returned `{"ok":true}`.
- `/` returned HTTP 200, but its HTML references `/assets/index-DlXvwnmZ.js` and `/assets/index-DvlQ1ZUm.css`; no `backend/static/assets` or `dist/assets` directory exists in the current source tree.
- Therefore the current checkout is **not a usable frontend launch without building/installing dependencies**. HTTP 200 is not counted as UI success.
- One-click/source scripts were not executed because they install dependencies. No browser user path was claimed.

Evidence: `H:/studybuddy-test/artifacts/kaobuddy-launch/latest.json` and `uvicorn.log`.

## 4. File Capability

The complete per-format matrix is in `components/kaobuddy-file-foundation/FORMAT-MATRIX.md`. Parser-level evidence is in `H:/studybuddy-test/artifacts/kaobuddy-foundation/latest.json`.

Main decisions:

- Carry forward concepts, output contracts, and failure messages; do not copy source.
- Reimplement text/PDF/DOCX/PPTX behind FastAPI and preserve original files, hashes, structured page/slide spans, parser version, warnings, and extracted body.
- Replace RTF regex and legacy DOC heuristics. Keep legacy PPT explicitly unsupported until a controlled converter is independently tested.
- Treat image OCR and video URL import as separate network/security components, not core file parsing.

## 5. Status Gate

- `sqlite-local`: `smoke_passed`; eligible for Integration only after manifest review.
- `kaobuddy-file-foundation`: parser/dependency smoke passed with material findings; not eligible as a single component. Split backend parser candidates and retest their APIs.
- `openai-compatible-provider`: offline protocol smoke passed; real provider remains unverified. Integration may test local protocol composition, but no external availability claim.
- `kaobuddy-launch`: backend-only pass; frontend/source launch failed readiness due to missing bundle. Not eligible for reuse as a launch shell.
