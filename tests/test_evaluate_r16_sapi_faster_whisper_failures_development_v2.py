from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_r16_sapi_faster_whisper_failures_development_v2.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_r16_faster_whisper", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_failures_rejects_wrong_population() -> None:
    with pytest.raises(ValueError, match="baxy_faster_whisper_population_invalid"):
        MODULE.select_failures(
            source_rows=[], transcript_rows=[], route_report={"rows": []}
        )
