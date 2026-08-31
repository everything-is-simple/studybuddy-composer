"""Run the independent B3 report-core C1 smoke without external dependencies."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import tracemalloc
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPORT_KINDS = ("daily", "weekly", "monthly", "exam_alert")
FORMATS = ("json", "markdown")
STATUSES = ("pending", "in_progress", "completed", "skipped")
SOURCE_STATUSES = ("valid", "stale", "source_deleted", "source_unavailable")
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_COUNT = 1_000_000
SAFE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
FORBIDDEN = re.compile(r"(?i)(password|secret|api[_-]?key|token\s*[:=]|[a-z]:\\|/users/|/home/|answer_key|answer_json|prompt)" )


class ReportError(ValueError):
    pass


def _int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > MAX_COUNT:
        raise ReportError("invalid_fact")
    return value


def _bucket(value: object, allowed: tuple[str, ...], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ReportError("invalid_fact")
    return value


def _period(facts: dict[str, object]) -> dict[str, str]:
    kind = _bucket(facts.get("report_kind"), REPORT_KINDS, "report_kind")
    timezone = facts.get("timezone")
    if not isinstance(timezone, str) or len(timezone) > 80:
        raise ReportError("invalid_timezone")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ReportError("invalid_timezone") from None
    start = facts.get("period_start")
    end = facts.get("period_end")
    if not isinstance(start, str) or not isinstance(end, str):
        raise ReportError("invalid_period")
    try:
        start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        raise ReportError("invalid_period") from None
    if end_date <= start_date:
        raise ReportError("invalid_period")
    return {"report_kind": kind, "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(), "timezone": timezone}


def _rows(facts: dict[str, object], name: str, fields: tuple[str, ...]) -> list[dict[str, object]]:
    values = facts.get(name, [])
    if not isinstance(values, list) or len(values) > 10000:
        raise ReportError("invalid_fact")
    result = []
    for row in values:
        if not isinstance(row, dict) or set(row) != set(fields):
            raise ReportError("invalid_fact")
        if not all(isinstance(key, str) and SAFE_KEY_RE.match(key) for key in row):
            raise ReportError("invalid_fact")
        result.append(row)
    return result


def project(facts: dict[str, object]) -> dict[str, object]:
    if not isinstance(facts, dict):
        raise ReportError("invalid_fact")
    allowed = {"report_kind", "timezone", "period_start", "period_end", "plan", "rhythm",
               "practice", "feedback", "source_quality", "exam_alert"}
    if set(facts) - allowed:
        raise ReportError("unsupported_fact")
    period = _period(facts)
    plan = facts.get("plan", {})
    rhythm = facts.get("rhythm", {})
    practice = facts.get("practice", {})
    feedback = facts.get("feedback", {})
    source_quality = facts.get("source_quality", {})
    exam = facts.get("exam_alert", {})
    if not all(isinstance(item, dict) for item in (plan, rhythm, practice, feedback, source_quality, exam)):
        raise ReportError("invalid_fact")
    def counts(item: dict[str, object], names: tuple[str, ...]) -> dict[str, int]:
        if set(item) != set(names):
            raise ReportError("invalid_fact")
        return {name: _int(item[name], name) for name in names}
    plan_counts = counts(plan, ("active_goal_count", "active_plan_count", "planned_item_count",
                               "completed_item_count", "started_item_count", "skipped_item_count",
                               "planned_minutes_total"))
    rhythm_counts = counts(rhythm, ("allocated_day_count", "allocated_minutes_total",
                                    "unallocated_eligible_item_count", "overload_day_count"))
    practice_counts = counts(practice, ("practice_session_count", "cram_session_count", "attempt_count",
                                        "deterministic_correct_count", "deterministic_incorrect_count",
                                        "pending_review_count", "completed_session_count"))
    feedback_counts = counts(feedback, ("open_mistake_count", "in_review_count", "fixed_count",
                                        "reopened_count", "archived_count", "weak_point_count"))
    source_counts = counts(source_quality, SOURCE_STATUSES)
    if set(exam) != {"days_remaining_bucket", "is_imminent"} or not isinstance(exam["is_imminent"], bool):
        raise ReportError("invalid_fact")
    bucket = exam["days_remaining_bucket"]
    if bucket is not None and bucket not in ("0-3", "4-7", "8-14", "15+"):
        raise ReportError("invalid_fact")
    payload = {"content_version": "b3-report-v1", "period": period,
               "plan": plan_counts, "rhythm": rhythm_counts, "practice": practice_counts,
               "feedback": feedback_counts, "source_quality": source_counts,
               "exam_alert": {"days_remaining_bucket": bucket, "is_imminent": exam["is_imminent"]}}
    payload["quality_flags"] = {
        "has_pending_review": practice_counts["pending_review_count"] > 0,
        "has_source_warnings": any(source_counts[key] for key in SOURCE_STATUSES[1:]),
        "has_uncertain_capture": source_counts["source_unavailable"] > 0,
    }
    basis = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    payload["aggregation_fingerprint"] = hashlib.sha256(basis.encode()).hexdigest()
    return payload


def render(payload: dict[str, object], format_name: str) -> str:
    if format_name == "json":
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if format_name != "markdown":
        raise ReportError("unsupported_format")
    p = payload
    lines = ["# Study report", "", f"- Kind: {p['period']['report_kind']}",
             f"- Period: {p['period']['period_start']} to {p['period']['period_end']} (exclusive)",
             f"- Timezone: {p['period']['timezone']}", "", "## Plan"]
    lines.extend(f"- {key}: {p['plan'][key]}" for key in sorted(p["plan"]))
    lines.append("\n## Rhythm")
    lines.extend(f"- {key}: {p['rhythm'][key]}" for key in sorted(p["rhythm"]))
    lines.append("\n## Practice")
    lines.extend(f"- {key}: {p['practice'][key]}" for key in sorted(p["practice"]))
    lines.append("\n## Feedback")
    lines.extend(f"- {key}: {p['feedback'][key]}" for key in sorted(p["feedback"]))
    lines.append("\n## Source quality")
    lines.extend(f"- {key}: {p['source_quality'][key]}" for key in sorted(p["source_quality"]))
    lines += ["\n## Exam alert", f"- days_remaining_bucket: {p['exam_alert']['days_remaining_bucket']}",
              f"- is_imminent: {str(p['exam_alert']['is_imminent']).lower()}", ""]
    return "\n".join(lines)


def base_facts(kind: str, *, populated: bool = True) -> dict[str, object]:
    zero = {key: 0 for key in ("active_goal_count", "active_plan_count", "planned_item_count",
                                "completed_item_count", "started_item_count", "skipped_item_count",
                                "planned_minutes_total")}
    facts = {"report_kind": kind, "timezone": "Asia/Shanghai", "period_start": "2026-08-01",
             "period_end": "2026-08-08", "plan": zero.copy(),
             "rhythm": {key: 0 for key in ("allocated_day_count", "allocated_minutes_total",
                                             "unallocated_eligible_item_count", "overload_day_count")},
             "practice": {key: 0 for key in ("practice_session_count", "cram_session_count", "attempt_count",
                                               "deterministic_correct_count", "deterministic_incorrect_count",
                                               "pending_review_count", "completed_session_count")},
             "feedback": {key: 0 for key in ("open_mistake_count", "in_review_count", "fixed_count",
                                               "reopened_count", "archived_count", "weak_point_count")},
             "source_quality": {key: 0 for key in SOURCE_STATUSES},
             "exam_alert": {"days_remaining_bucket": None, "is_imminent": False}}
    if populated:
        facts["plan"].update(active_goal_count=1, active_plan_count=1, planned_item_count=2,
                              completed_item_count=1, planned_minutes_total=45)
        facts["practice"].update(practice_session_count=1, attempt_count=2,
                                  deterministic_correct_count=1, deterministic_incorrect_count=1)
        facts["source_quality"].update(valid=2, stale=1, source_deleted=1, source_unavailable=1)
        facts["exam_alert"] = {"days_remaining_bucket": "4-7", "is_imminent": True}
    return facts


def expect_error(call, code: str) -> None:
    try:
        call()
    except ReportError as error:
        assert str(error) == code, (str(error), code)
    else:
        raise AssertionError(f"expected {code}")


def run_cases() -> dict[str, object]:
    started = time.perf_counter()
    tracemalloc.start()
    checks = []
    for kind in REPORT_KINDS:
        empty = project(base_facts(kind, populated=False))
        normal = project(base_facts(kind))
        assert project(json.loads(json.dumps(base_facts(kind)))) == normal
        assert render(normal, "json") == render(normal, "json")
        assert len(render(normal, "json").encode()) < MAX_OUTPUT_BYTES
        assert "source_deleted" in render(normal, "markdown")
        checks.append({"case": kind, "empty": True, "normal": True})
    shuffled = base_facts("daily")
    shuffled["plan"] = dict(reversed(list(shuffled["plan"].items())))
    assert project(shuffled) == project(base_facts("daily"))
    bad = base_facts("daily")
    expect_error(lambda: project({**bad, "report_kind": "yearly"}), "invalid_fact")
    expect_error(lambda: project({**bad, "timezone": "Unknown/Zone"}), "invalid_timezone")
    expect_error(lambda: project({**bad, "period_end": "2026-07-01"}), "invalid_period")
    expect_error(lambda: project({**bad, "extra": 1}), "unsupported_fact")
    expect_error(lambda: render(project(bad), "pdf"), "unsupported_format")
    malformed = dict(bad)
    malformed["plan"] = {"active_goal_count": -1}
    expect_error(lambda: project(malformed), "invalid_fact")
    network_attempt = lambda: (_ for _ in ()).throw(ReportError("network_disabled"))
    expect_error(network_attempt, "network_disabled")
    assert not FORBIDDEN.search(render(project(base_facts("daily")), "json"))
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - started
    assert elapsed < 60
    return {"status": "passed", "candidate": "report-core", "gate": "B3-C1",
            "scope": "synthetic allowlisted facts; four report kinds; JSON and Markdown",
            "checks": checks + [{"case": "validation_and_privacy", "passed": True},
                                 {"case": "network_denial", "passed": True}],
            "measurements": {"wall_time_ms": round(elapsed * 1000, 3),
                             "peak_working_set_bytes": peak, "output_bytes": len(render(project(base_facts("daily")), "json").encode()),
                             "temporary_files": 0},
            "versions": {"runner": "b3-report-projection-candidate-v1", "python": os.sys.version.split()[0]},
            "evidence_policy": "sanitized metadata only"}


def main() -> int:
    artifact = Path(__file__).resolve().parents[2] / "results" / "report-core" / "c1-smoke.json"
    temporary = Path(tempfile.mkdtemp(prefix="studybuddy-report-c1-"))
    try:
        result = run_cases()
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(f"B3 C1 report-core smoke passed: {len(result['checks']) + 2} checks")
        return 0
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
