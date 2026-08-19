from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

ARTIFACT_DIR = Path(os.environ.get("STUDYBUDDY_SQLITE_ARTIFACT_DIR", "H:/studybuddy-test/artifacts/sqlite-local"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
run_dir = Path(tempfile.mkdtemp(prefix="sqlite-local-", dir=ARTIFACT_DIR))
db_path = run_dir / "studybuddy-smoke.sqlite3"
backup_path = run_dir / "backup.sqlite3"
restored_path = run_dir / "restored.sqlite3"
started = time.perf_counter()
checks: dict[str, object] = {}

schema = """
PRAGMA foreign_keys = ON;
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE materials (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  extracted_text TEXT NOT NULL DEFAULT ''
);
CREATE TABLE knowledge_modules (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  evidence TEXT NOT NULL DEFAULT ''
);
"""

conn = sqlite3.connect(db_path, timeout=1)
try:
    conn.executescript(schema)
    journal_mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    conn.execute("INSERT INTO projects VALUES (?, ?, ?)", ("p1", "合成项目", "2026-01-01T00:00:00Z"))
    conn.execute("INSERT INTO materials VALUES (?, ?, ?, ?)", ("m1", "p1", "合成资料", "进程是资源分配的基本单位。"))
    conn.execute("INSERT INTO knowledge_modules VALUES (?, ?, ?, ?)", ("k1", "p1", "进程", "合成资料中的定义"))
    conn.commit()
    checks["journal_mode"] = journal_mode
finally:
    conn.close()

reopened = sqlite3.connect(db_path, timeout=1)
try:
    row = reopened.execute(
        "SELECT p.name, m.title, k.title FROM projects p JOIN materials m ON m.project_id=p.id JOIN knowledge_modules k ON k.project_id=p.id WHERE p.id=?",
        ("p1",),
    ).fetchone()
    checks["reopen_read"] = list(row) if row else None
    checks["integrity_check"] = reopened.execute("PRAGMA integrity_check").fetchone()[0]

    lock_owner = sqlite3.connect(db_path, timeout=0)
    lock_contender = sqlite3.connect(db_path, timeout=0)
    try:
        lock_owner.execute("BEGIN IMMEDIATE")
        lock_owner.execute("UPDATE projects SET name=? WHERE id='p1'", ("锁测试中",))
        checks["wal_reader_during_write"] = lock_contender.execute("SELECT name FROM projects WHERE id='p1'").fetchone()[0]
        try:
            lock_contender.execute("UPDATE projects SET name=? WHERE id='p1'", ("竞争写入",))
            checks["second_writer"] = "unexpected-success"
        except sqlite3.OperationalError as exc:
            checks["second_writer"] = str(exc)
        lock_owner.rollback()
    finally:
        lock_contender.close()
        lock_owner.close()

    backup_conn = sqlite3.connect(backup_path)
    try:
        reopened.backup(backup_conn)
    finally:
        backup_conn.close()
finally:
    reopened.close()

shutil.copy2(backup_path, restored_path)
restored = sqlite3.connect(restored_path)
try:
    checks["restored_project"] = restored.execute("SELECT name FROM projects WHERE id='p1'").fetchone()[0]
    checks["restored_integrity_check"] = restored.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    restored.close()

checks["db_files_after_close"] = sorted(path.name for path in run_dir.iterdir())
checks["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
passed = (
    checks["journal_mode"] == "wal"
    and checks["reopen_read"] == ["合成项目", "合成资料", "进程"]
    and checks["integrity_check"] == "ok"
    and "locked" in str(checks["second_writer"]).lower()
    and checks["restored_project"] == "合成项目"
    and checks["restored_integrity_check"] == "ok"
)
result = {
    "component": "sqlite-local",
    "status": "passed" if passed else "failed",
    "runtime": {"python": platform.python_version(), "sqlite": sqlite3.sqlite_version, "platform": platform.platform()},
    "run_dir": str(run_dir),
    "checks": checks,
    "limitations": [
        "Windows 本机单进程双连接锁争用已测；尚未测试网络盘、杀进程恢复、磁盘满和多进程高并发。",
        "这是 Composer 独立能力测试，不代表 StudyBuddy 已完成数据库 schema 或迁移。",
    ],
}
(run_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
(ARTIFACT_DIR / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if passed else 1)
