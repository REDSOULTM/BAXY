from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "evaluate_raw_lexical_hyperspotter_wake_corpus_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_raw_lexical_hyper", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_lexical_hyperspotter_requires_both_verifiers() -> None:
    gate = _module()

    assert gate.lexical_hyperspotter_decision(
        lexical_evidence=True,
        hyperspotter_logit=0.8,
    )[0]
    assert not gate.lexical_hyperspotter_decision(
        lexical_evidence=True,
        hyperspotter_logit=0.4,
    )[0]
    assert not gate.lexical_hyperspotter_decision(
        lexical_evidence=False,
        hyperspotter_logit=5.0,
    )[0]
