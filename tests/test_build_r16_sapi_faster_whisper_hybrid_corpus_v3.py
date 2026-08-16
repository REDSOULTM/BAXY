from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "build_r16_sapi_faster_whisper_hybrid_corpus_v3.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_r16_hybrid", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_expected_population_is_frozen() -> None:
    assert MODULE.EXPECTED_ROWS == 337
    assert MODULE.EXPECTED_REPLACEMENTS == 88
