from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "run_multiverifier_wake_physical_room_gate_v1.py"
    )
    spec = importlib.util.spec_from_file_location("baxy_multiverifier", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_strong_phonetic_fusion_accepts_without_secondary_scores() -> None:
    gate = _module()

    accepted, reason = gate.multiverifier_decision(
        fusion_margin=-2.9,
        livekit_score=0.01,
        qbyt_margin=-0.05,
        livekit_peak_index=4,
    )

    assert accepted
    assert reason == "strong_phonetic_fusion"


def test_weak_consensus_requires_utterance_prefix_evidence() -> None:
    gate = _module()
    common = {"fusion_margin": -4.0, "livekit_score": 0.08, "qbyt_margin": -0.01}

    early = gate.multiverifier_decision(**common, livekit_peak_index=1)
    late = gate.multiverifier_decision(**common, livekit_peak_index=2)

    assert early == (True, "early_acoustic_phonetic_consensus")
    assert late == (False, "insufficient_consensus")


def test_fixed_three_second_audio_has_exact_contract() -> None:
    gate = _module()

    short = gate.fixed_three_second_audio(np.ones(12_000, dtype=np.float32))
    long = gate.fixed_three_second_audio(np.ones(60_000, dtype=np.float32))

    assert short.shape == (48_000,)
    assert long.shape == (48_000,)
    assert np.all(short[12_000:] == 0.0)
