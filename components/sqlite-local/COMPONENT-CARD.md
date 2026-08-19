# Component Card: sqlite-local

- Source: Python standard-library `sqlite3`; prior evidence reviewed at `H:/ai-studybuddy-composer/windows-native/01-sqlite`.
- License: Python standard library / SQLite public domain.
- Version: Python 3.14.7, SQLite 3.50.4 on Windows 11 10.0.22631.
- Owner boundary: Composer-only feasibility test. Formal schema and adapter must be implemented in `H:/studybuddy` after integration.
- Independent smoke command: `python H:/studybuddy-composer/components/sqlite-local/smoke.py`
- Real input: a real temporary SQLite database under `H:/studybuddy-test/artifacts/sqlite-local`.
- Output contract: `latest.json` plus preserved database, backup, and restored database in a per-run directory.
- Verified behavior: creates project/material/knowledge-module tables; inserts records; closes and reopens; reads joins; runs `PRAGMA integrity_check`; enables WAL; verifies readers during an uncommitted write; verifies second writer receives `database is locked`; uses SQLite backup API and validates restored content/integrity.
- Failure boundaries: network shares, disk-full, abrupt process termination recovery, antivirus interference, schema migration, encryption, and sustained multi-process load are not tested.
- Windows prerequisites: Python with stdlib SQLite only; no package installation.
- Resource measurement: 29.472 ms in the recorded run; tiny synthetic database.
- Privacy/logging restrictions: synthetic Chinese data only; no user data or credentials.
- Prior evidence assessment: the old `better-sqlite3` card covered WAL/CRUD/rollback/backup in one process, but omitted the requested three-table schema, explicit reopen read, integrity check, and lock evidence. It was not accepted without this re-test.
- Smoke result: `smoke_passed`
- Integration result: `not started`
- Evidence path: `H:/studybuddy-test/artifacts/sqlite-local/latest.json`
