from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_qbyt_contextual_development_v9.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_qbyt_contextual", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_qbyt_policy_requires_same_acoustic_view() -> None:
    result = MODULE.qbyt_same_view_policy(
        established=False,
        fixed=True,
        full_hot=False,
        observation={
            "acousticByView": {40000: True, 64000: False},
            "acceptedByView": {40000: False, 64000: True},
        },
        base_signals={"sameViewDualDecode": False},
    )
    assert result == {
        "sameViewQbyT": False,
        "sameViewQbyTOrDualDecode": False,
    }


def test_qbyt_policy_accepts_same_view_consensus() -> None:
    result = MODULE.qbyt_same_view_policy(
        established=False,
        fixed=True,
        full_hot=False,
        observation={
            "acousticByView": {40000: True},
            "acceptedByView": {40000: True},
        },
        base_signals={"sameViewDualDecode": False},
    )
    assert result == {"sameViewQbyT": True, "sameViewQbyTOrDualDecode": True}


def test_qbyt_policy_can_fall_back_to_same_view_dual_decode() -> None:
    result = MODULE.qbyt_same_view_policy(
        established=False,
        fixed=True,
        full_hot=False,
        observation={"acousticByView": {40000: True}, "acceptedByView": {40000: False}},
        base_signals={"sameViewDualDecode": True},
    )
    assert result["sameViewQbyTOrDualDecode"] is True
