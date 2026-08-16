"""Regression guard for the retired phrase-driven exhaustive audit."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RETIRED_AUDIT = ROOT / "scripts" / "audit_exhaustive_runtime_cases.py"
HISTORICAL_NOTICE = ROOT / "artifacts" / "historical_exhaustive" / "README.md"


def test_phrase_driven_fast_audit_remains_retired_and_documented() -> None:
    assert not RETIRED_AUDIT.exists()

    notice = HISTORICAL_NOTICE.read_text(encoding="utf-8")
    normalized = " ".join(notice.split())
    assert "runtime_fast_gate*.json" in normalized
    assert "evidencia histórica" in normalized
    assert "scripts/run_exhaustive_runtime_model_gate.py" in normalized
    assert "sin despachar operaciones al core" in normalized


def test_no_script_imports_the_retired_audit_or_phrase_deciders() -> None:
    forbidden = (
        "audit_exhaustive_runtime_cases",
        "deterministic_bounded_plan",
        "deterministic_conversation_plan",
        "deterministic_single_step",
    )
    offenders: list[str] = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if any(name in source for name in forbidden):
            offenders.append(path.name)

    assert offenders == []
