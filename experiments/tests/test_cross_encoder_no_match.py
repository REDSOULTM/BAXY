from __future__ import annotations

from experiments.mind_router_spike.measure_functiongemma_cross_encoder_no_match import (
    acceptance_summary,
    select_zero_accept_loss_threshold,
)


def test_threshold_is_selected_only_from_development_accept_rows() -> None:
    development_rows = [
        {"verdict": "accept", "accept_margin": -0.4},
        {"verdict": "accept", "accept_margin": 0.2},
        {"verdict": "reject", "accept_margin": -0.9},
    ]

    selection = select_zero_accept_loss_threshold(development_rows)

    assert selection == {
        "threshold": -0.4,
        "development_accept_rows": 2,
        "development_accept_rows_lost": 0,
        "development_reject_rows": 1,
        "development_reject_rows_separated": 1,
    }


def test_acceptance_summary_counts_identity_losses_and_each_no_match_cause() -> None:
    rows = [
        {
            "cause": "served_identity",
            "population": "r2",
            "pair_id": "r2:a:audio.mute",
            "accept_margin": 0.5,
        },
        {
            "cause": "served_identity",
            "population": "v1",
            "pair_id": "v1:b:task.list",
            "accept_margin": -0.5,
        },
        {
            "cause": "taxi_es",
            "population": "diagnostic",
            "pair_id": "taxi_es:audio.mute",
            "accept_margin": -0.6,
        },
        {
            "cause": "taxi_en",
            "population": "diagnostic",
            "pair_id": "taxi_en:task.list",
            "accept_margin": -0.7,
        },
        {
            "cause": "known_leak_v1",
            "population": "v1",
            "pair_id": "known_leak_v1:memory.forget",
            "accept_margin": -0.8,
        },
        {
            "cause": "known_leak_v5",
            "population": "v5",
            "pair_id": "known_leak_v5:routine.read",
            "accept_margin": -0.9,
        },
    ]

    summary = acceptance_summary(rows, threshold=-0.4)

    assert summary["served_identity"]["total"] == 2
    assert summary["served_identity"]["lost"] == 1
    assert summary["served_identity"]["lost_pair_ids"] == ["v1:b:task.list"]
    assert summary["served_identity"]["by_population"] == {
        "r2": {"total": 1, "lost": 0},
        "v1": {"total": 1, "lost": 1},
    }
    assert summary["no_match_by_cause"] == {
        "known_leak_v1": {"pairs": 1, "accepted_pairs": 0, "separated": True},
        "known_leak_v5": {"pairs": 1, "accepted_pairs": 0, "separated": True},
        "taxi_en": {"pairs": 1, "accepted_pairs": 0, "separated": True},
        "taxi_es": {"pairs": 1, "accepted_pairs": 0, "separated": True},
    }
