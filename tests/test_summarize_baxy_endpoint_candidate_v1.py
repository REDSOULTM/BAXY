from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "experiments" / "voice_latency" / "summarize_baxy_endpoint_candidate_v1.py"
)
SPEC = importlib.util.spec_from_file_location("summarize_endpoint_candidate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_verdict_contract_excludes_ambiguous_basi_alias() -> None:
    assert MODULE.EXPECTED_ENDPOINT_ALIASES == [
        "backsy",
        "bakse",
        "baxi",
        "baxy",
        "boxy",
    ]
    assert "basi" not in MODULE.EXPECTED_ENDPOINT_ALIASES


def test_verdict_requires_every_input_to_be_explicit() -> None:
    parser = MODULE._parser()
    required = {
        action.dest for action in parser._actions if getattr(action, "required", False)
    }
    assert required == {
        "candidate_manifest",
        "baseline_manifest",
        "human_runtime_report",
        "confusable_runtime_report",
        "suffix_runtime_report",
        "human_fusion_report",
        "confusable_source_corpus",
        "confusable_physical_corpus",
        "suffix_source_corpus",
        "suffix_physical_corpus",
        "output",
    }
