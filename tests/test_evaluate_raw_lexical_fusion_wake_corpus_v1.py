from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "evaluate_raw_lexical_fusion_wake_corpus_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_raw_lexical_fusion", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_contextual_lexical_evidence_accepts_spaced_fused_and_cyrillic_aliases() -> None:
    gate = _module()

    assert gate.contextual_lexical_evidence("hola baxy roca")
    assert gate.contextual_lexical_evidence("el grupo Basiroca")
    assert gate.contextual_lexical_evidence("торговой марки боксы")
    assert not gate.contextual_lexical_evidence("programming")


def test_lexical_fusion_requires_both_verifiers() -> None:
    gate = _module()

    assert gate.lexical_fusion_decision(
        lexical_evidence=True,
        fusion_margin=-4.2,
    )[0]
    assert not gate.lexical_fusion_decision(
        lexical_evidence=True,
        fusion_margin=-4.6,
    )[0]
    assert not gate.lexical_fusion_decision(
        lexical_evidence=False,
        fusion_margin=1.0,
    )[0]
