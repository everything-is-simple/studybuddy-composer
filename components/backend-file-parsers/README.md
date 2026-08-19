# Backend File Parsers

Independent server-side parser trial. Run from this directory after installing `requirements-smoke.txt`:

```powershell
.venv\Scripts\python.exe smoke.py
.venv\Scripts\python.exe -m pytest tests
```

The parser never owns original-file storage. It emits sanitized smoke evidence only.
