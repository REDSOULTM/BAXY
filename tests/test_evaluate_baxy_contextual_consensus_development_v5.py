from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_contextual_consensus_development_v5.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_contextual_consensus_development_v5", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_consensus_policy_signals_keep_scopes_distinct() -> None:
    signals = MODULE.consensus_policy_signals(
        full_plain=False,
        full_hot=True,
        acoustic_by_view={40_000: True, 64_000: False},
        plain_by_view={40_000: False, 64_000: True},
        hot_by_view={40_000: True, 64_000: True},
    )
    assert signals == {
        "currentFullHot": True,
        "fullDualDecode": False,
        "sameViewHot": True,
        "fullAndSameViewHot": True,
        "sameViewDualDecode": False,
        "twoViewHotConsensus": True,
    }


def test_same_view_dual_decode_requires_all_evidence_on_one_view() -> None:
    signals = MODULE.consensus_policy_signals(
        full_plain=True,
        full_hot=True,
        acoustic_by_view={40_000: True, 64_000: False},
        plain_by_view={40_000: True, 64_000: False},
        hot_by_view={40_000: True, 64_000: False},
    )
    assert signals["sameViewDualDecode"] is True
    assert signals["twoViewHotConsensus"] is False


def test_empty_views_reject_every_view_consensus() -> None:
    signals = MODULE.consensus_policy_signals(
        full_plain=False,
        full_hot=False,
        acoustic_by_view={},
        plain_by_view={},
        hot_by_view={},
    )
    assert not any(signals.values())
