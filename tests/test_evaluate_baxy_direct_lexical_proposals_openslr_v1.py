from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_direct_lexical_proposals_openslr_v1.py"
)
SPEC = importlib.util.spec_from_file_location("direct_lexical_openslr", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_confirmation_stops_on_first_bounded_match(monkeypatch) -> None:
    transcripts = iter(("Maxi viene en camino", "Vaxi open the calculator"))
    monkeypatch.setattr(
        MODULE.lexical,
        "_decode",
        lambda *_args, **_kwargs: (next(transcripts), 0.01),
    )
    config = SimpleNamespace(
        direct_lexical_retry_speed_factors=(0.85, 1.14),
        lexical_aliases=frozenset(("baxy", "baxi", "boxy")),
    )

    result = MODULE.confirm_audio(
        object(),
        np.ones(16_000, dtype=np.float32),
        contextual_hotwords="tokens",
        config=config,
    )

    assert result["accepted"] is True
    assert result["method"] == "bounded_phonetic_alias"
    assert len(result["attemptTranscriptSha256"]) == 2


def test_confirmation_rejects_all_non_wake_views(monkeypatch) -> None:
    transcripts = iter(("Maxi viene", "La caja esta vacia", "normal speech"))
    monkeypatch.setattr(
        MODULE.lexical,
        "_decode",
        lambda *_args, **_kwargs: (next(transcripts), 0.01),
    )
    config = SimpleNamespace(
        direct_lexical_retry_speed_factors=(0.85, 1.14),
        lexical_aliases=frozenset(("baxy", "baxi", "boxy")),
    )

    result = MODULE.confirm_audio(
        object(),
        np.ones(16_000, dtype=np.float32),
        contextual_hotwords="tokens",
        config=config,
    )

    assert result["accepted"] is False
    assert result["method"] is None
    assert len(result["attemptTranscriptSha256"]) == 3
