import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "components" / "asr-whisper-cpp" / "smoke.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("asr_c1_smoke", SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def passed_checks(module):
    return [
        {"id": check_id, "status": "passed", "name": "test", "metrics": {}}
        for check_id in module.CHECK_IDS
    ]


def test_promotion_requires_all_fourteen_checks_to_pass():
    module = load_smoke_module()
    checks = passed_checks(module)
    assert module.promotion_status(checks) == "smoke_passed"

    checks[-1]["status"] = "failed"
    assert module.promotion_status(checks) == "c1_partial"


def test_c1_check_ids_are_explicit_and_complete():
    module = load_smoke_module()
    assert module.CHECK_IDS == tuple(f"C1-ASR-{number:02d}" for number in range(1, 15))


def test_promotion_rejects_missing_or_unknown_checks():
    module = load_smoke_module()
    checks = passed_checks(module)
    assert module.promotion_status(checks[:-1]) == "c1_partial"

    checks.append({"id": "C1-ASR-99", "status": "passed", "name": "unknown", "metrics": {}})
    assert module.promotion_status(checks) == "c1_partial"
