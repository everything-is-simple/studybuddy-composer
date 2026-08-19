# KaoBuddy Remote Recheck

Rechecked from the upstream repository on 2026-08-19.

- Remote: `https://github.com/jin-zi-xuan/kaobuddy-pwa.git`
- Audit checkout: `H:/kaobuddy-remote-audit`
- Remote commit: `2e12271066a17384a1888b4598805c3f4bafd60e`
- Remote tag: `v1.2.4`
- Remote branch: `main`
- Tracked file count: 84

`H:/kaobuddy` is not a Git checkout, so its copy cannot be assigned a commit identity. All requested comparison files differ byte-for-byte from the remote checkout. The observed differences are primarily CRLF/LF normalization and local-copy text state, but the local copy must not be treated as authoritative without a commit identity.

The remote checkout confirms the foundation findings:

- IndexedDB remains `kaobuddy-db`, version 2, with seven stores; API config uses browser `localStorage`.
- `backend/app/ai_client.py` performs the `httpx` OpenAI-compatible request from FastAPI; README's browser-direct wording is not the actual request chain.
- Browser file readers cover PDF, DOCX, RTF, heuristic legacy DOC, and PPTX; legacy PPT is rejected.
- `scripts/dev.mjs` and `open-kaobuddy.bat` install dependencies/bootstrap runtime as part of launch, so they were inspected but not executed under the project boundary.

The remote copy is reference-only. No remote source was copied into `H:/studybuddy`.
