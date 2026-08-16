from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind.turn_evidence import (  # noqa: E402
    CorpusEvidenceReport,
    TurnEvidenceIndex,
    TurnEvidenceRecord,
)
from baxy_mind.turn_probe import (  # noqa: E402
    ConversationKnnThresholds,
    OneSidedTurnEvidencePolicy,
    TurnModeLinearProbe,
)


def _probe(threshold: float = 0.90) -> TurnModeLinearProbe:
    return TurnModeLinearProbe(
        classes=("action", "conversation"),
        coefficients=((-4.0, 0.0), (4.0, 0.0)),
        intercepts=(0.0, 0.0),
        temperature=1.0,
        conversation_threshold=threshold,
        implementation="fixture",
        training_rows=20,
        training_split_fingerprint="a" * 64,
    )


def _policy(probe: TurnModeLinearProbe) -> OneSidedTurnEvidencePolicy:
    return OneSidedTurnEvidencePolicy(
        runtime_source_sha256="b" * 64,
        encoder_identity="fixture",
        probe=probe,
        neighbors=2,
        conversation_knn=ConversationKnnThresholds(
            minimum_top1_score=-1.0,
            minimum_score_margin=0.0,
            minimum_conversation_agreement=0.0,
            maximum_mode_entropy=1.0,
            minimum_conversation_fraction=0.0,
        ),
        validation_fingerprint="c" * 64,
        validation_rows=10,
        final_seal_source_ids_sha256="d" * 64,
        historical_index_rows=7,
    )


def test_probe_json_round_trip_and_weight_hash_rejects_tamper() -> None:
    probe = _probe()
    payload = probe.to_dict()

    assert TurnModeLinearProbe.from_dict(payload) == probe
    payload["coefficients"][0][0] = 123.0
    with pytest.raises(ValueError, match="hash"):
        TurnModeLinearProbe.from_dict(payload)


def test_policy_json_is_one_sided_and_records_historical_role() -> None:
    policy = _policy(_probe())
    payload = policy.to_dict()

    loaded = OneSidedTurnEvidencePolicy.from_dict(
        json.loads(json.dumps(payload))
    )

    assert loaded == policy
    assert payload["authority"] == "conversation_signal_or_abstain_only"
    assert payload["historical_usage"] == {
        "rows": 7,
        "probe_training_rows": 0,
        "reason": "weak_or_noisy_labels",
        "role": "index_and_conversation_retrieval_only",
        "text_sent_to_llm": False,
    }


def test_runtime_policy_can_emit_only_conversation_cards_or_abstain() -> None:
    records = [
        TurnEvidenceRecord("", "action", ("app",), "a", "a"),
        TurnEvidenceRecord("", "conversation", (), "c1", "c1"),
        TurnEvidenceRecord("", "conversation", (), "c2", "c2"),
    ]
    report = CorpusEvidenceReport("b" * 64, 3, 3, 0, 0, 0, 0)
    index = TurnEvidenceIndex(
        records,
        np.asarray([[-1.0, 0.0], [1.0, 0.0], [0.9, 0.1]], dtype=np.float32),
        report,
        encoder_identity="fixture",
    )
    policy = _policy(_probe())

    conversation = index.retrieve(
        "explica",
        lambda _texts: np.asarray([[1.0, 0.0]], dtype=np.float32),
        ["app.open"],
        policy=policy,
    )
    action = index.retrieve(
        "abre",
        lambda _texts: np.asarray([[-1.0, 0.0]], dtype=np.float32),
        ["app.open"],
        policy=policy,
    )

    assert conversation
    assert {card["mode"] for card in conversation} == {"conversation"}
    assert all(card["families"] == [] for card in conversation)
    assert all(card["candidate_family_match"] is False for card in conversation)
    assert action == []


def test_one_sided_retrieve_still_uses_historical_records_outside_train_view() -> None:
    records = [
        TurnEvidenceRecord(
            "",
            "conversation",
            (),
            "historical-conversation",
            "historical",
        ),
        TurnEvidenceRecord(
            "",
            "action",
            ("app",),
            "public-train-action",
            "train",
            "train",
        ),
    ]
    report = CorpusEvidenceReport("b" * 64, 2, 2, 0, 0, 0, 0)
    index = TurnEvidenceIndex(
        records,
        np.asarray([[1.0, 0.0], [0.8, 0.2]], dtype=np.float32),
        report,
        encoder_identity="fixture",
    )
    encoder = lambda _texts: np.asarray([[1.0, 0.0]], dtype=np.float32)

    evidence = index.retrieve(
        "explica",
        encoder,
        ["app.open"],
        policy=_policy(_probe()),
    )

    assert index.candidate_families("explica", encoder) == ("app",)
    assert len(evidence) == 1
    assert evidence[0]["mode"] == "conversation"
    assert evidence[0]["families"] == []
    assert evidence[0]["score"] == 1.0
    assert evidence[0]["candidate_family_match"] is False
