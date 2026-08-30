"""Validate the metadata-only B0 candidate catalog and component cards."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "manifests" / "b0-catalog.json"
ALLOWED_STATUSES = {"researching", "smoke_passed", "integration_passed", "rejected"}
REQUIRED_FIELDS = {
    "id", "capability", "kind", "source", "version", "source_revision", "license_status", "artifact_sha256",
    "status", "smoke_command", "fixture", "network_default", "timeout_seconds",
    "output_limit_bytes", "cleanup", "privacy", "windows_prerequisites",
    "resource_measurement", "evidence_path", "formal_system_allowed",
}
CARD_MARKERS = (
    "# Component Card:",
    "- Gate: B0 candidate intake",
    "- Independent smoke command:",
    "- Fixture:",
    "- Output contract:",
    "- Failure boundaries:",
    "- Windows prerequisites:",
    "- Resource measurement:",
    "- Network policy:",
    "- Cleanup:",
    "- Privacy/logging restrictions:",
    "- Smoke result:",
    "- Integration result:",
    "- Evidence path:",
    "- Formal system allowed: `false`",
)


def fail(message: str) -> None:
    raise SystemExit(f"B0 catalog validation failed: {message}")


def main() -> int:
    if not CATALOG.is_file():
        fail(f"missing {CATALOG}")
    try:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON: {exc}")

    if data.get("schema_version") != 1 or data.get("gate") != "B0":
        fail("catalog schema or gate is not B0/v1")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("components/**/*.onnx", "components/**/*.gguf", "components/**/*.safetensors", "components/**/artifacts/"):
        if pattern not in gitignore:
            fail(f".gitignore missing B0 artifact rule: {pattern}")

    if data.get("status") != "governance_scaffolded_smoke_pending":
        fail("catalog must remain smoke-pending until candidate evidence exists")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        fail("candidates must be a non-empty list")

    ids: set[str] = set()
    capabilities: set[str] = set()
    for candidate in candidates:
        missing = REQUIRED_FIELDS.difference(candidate)
        if missing:
            fail(f"{candidate.get('id', '<unknown>')} missing fields: {sorted(missing)}")
        candidate_id = candidate["id"]
        if candidate_id in ids:
            fail(f"duplicate candidate id: {candidate_id}")
        ids.add(candidate_id)
        capabilities.add(candidate["capability"])
        if candidate["status"] not in ALLOWED_STATUSES:
            fail(f"{candidate_id} has invalid status {candidate['status']!r}")
        if candidate["capability"] not in {"asr", "ocr", "report", "delivery"}:
            fail(f"{candidate_id} has an out-of-scope capability")
        if candidate["network_default"] != "disabled":
            fail(f"{candidate_id} must default to network disabled")
        if candidate["formal_system_allowed"] is not False:
            fail(f"{candidate_id} is incorrectly authorized for Formal")
        if candidate["status"] == "researching":
            if candidate["evidence_path"] is not None:
                fail(f"{candidate_id} has evidence while still researching")
            if candidate["artifact_sha256"] is not None:
                fail(f"{candidate_id} records selected-artifact hash before smoke")
        elif not candidate["evidence_path"]:
            fail(f"{candidate_id} needs evidence_path before promotion")

        card_path = ROOT / "components" / candidate_id / "COMPONENT-CARD.md"
        if not card_path.is_file():
            fail(f"missing card for {candidate_id}: {card_path}")
        card = card_path.read_text(encoding="utf-8")
        for marker in CARD_MARKERS:
            if marker not in card:
                fail(f"{candidate_id} card missing marker: {marker}")
        if re.search(r"(?i)(sk-[a-z0-9]{20,}|api[_-]?key\s*[:=]|secret\s*[:=]|password\s*[:=])", card):
            fail(f"{candidate_id} card contains a credential-like token")

    required_capabilities = {"asr", "ocr", "report", "delivery"}
    if capabilities != required_capabilities:
        fail(f"capability coverage is {sorted(capabilities)}, expected {sorted(required_capabilities)}")

    selected = {candidate["id"] for candidate in candidates if "C0 selected" in candidate["notes"]}
    if selected != {"asr-whisper-cpp", "ocr-paddleocr", "ocr-rapidocr"}:
        fail(f"unexpected C0 media selections: {sorted(selected)}")
    asr = next(candidate for candidate in candidates if candidate["id"] == "asr-whisper-cpp")
    if not asr["local_reference"].startswith("H:/Whisper canonical runtime"):
        fail("asr-whisper-cpp must retain H:/Whisper as its canonical runtime")
    status_counts = {status: sum(candidate["status"] == status for candidate in candidates) for status in ALLOWED_STATUSES}
    summary = ", ".join(
        f"{status_counts[status]} {status}"
        for status in ("smoke_passed", "integration_passed", "researching")
    )
    print(f"B0 catalog validation passed: {summary} candidates across 4 capabilities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
