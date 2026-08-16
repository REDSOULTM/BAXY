from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_r16_sapi_qwen3_asr_failures_development_v1.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_r16_qwen3_asr", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_failures_rejects_wrong_population() -> None:
    with pytest.raises(ValueError, match="baxy_qwen3_asr_population_invalid"):
        MODULE.select_failures(
            source_rows=[], transcript_rows=[], route_report={"rows": []}
        )


def test_expected_failure_population_is_frozen() -> None:
    assert MODULE.EXPECTED_FAILURES == 60
