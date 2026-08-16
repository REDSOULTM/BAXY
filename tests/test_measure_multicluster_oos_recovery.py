from __future__ import annotations

import importlib
import json
from pathlib import Path

import numpy as np


def _candidate_module():
    return importlib.import_module(
        "experiments.mind_router_spike.measure_multicluster_oos_recovery"
    )


def test_multicluster_boundary_keeps_distinct_modes_and_rejects_open_space() -> None:
    candidate = _candidate_module()
    embeddings = np.asarray(
        [
            [1.00, 0.00, 0.01],
            [0.99, 0.02, 0.00],
            [0.00, 1.00, 0.01],
            [0.02, 0.99, 0.00],
            [-1.00, 0.00, 0.01],
            [-0.99, 0.02, 0.00],
            [0.00, -1.00, 0.01],
            [0.02, -0.99, 0.00],
        ],
        dtype=np.float32,
    )
    labels = ("alpha", "alpha", "alpha", "alpha", "beta", "beta", "beta", "beta")

    boundaries = candidate.fit_multicluster_boundaries(
        embeddings,
        labels,
        clusters_per_label=2,
        radius_scale=1.0,
        random_state=17,
    )
    scores = candidate.score_multicluster_boundaries(
        boundaries,
        np.asarray(
            [
                [1.00, 0.01, 0.00],
                [-1.00, 0.01, 0.00],
                [0.00, 0.00, 1.00],
            ],
            dtype=np.float32,
        ),
    )

    assert [score.accepted for score in scores] == [True, True, False]
    assert [score.label for score in scores[:2]] == ["alpha", "beta"]
    assert scores[2].normalized_distance > 1.0


def test_multicluster_boundary_is_deterministic_for_a_fixed_seed() -> None:
    candidate = _candidate_module()
    embeddings = np.asarray(
        [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.0, 1.0],
            [0.1, 0.9],
            [-1.0, 0.0],
            [-0.9, -0.1],
            [0.0, -1.0],
            [-0.1, -0.9],
        ],
        dtype=np.float32,
    )
    labels = ("alpha", "alpha", "alpha", "alpha", "beta", "beta", "beta", "beta")

    first = candidate.fit_multicluster_boundaries(
        embeddings,
        labels,
        clusters_per_label=2,
        radius_scale=1.0,
        random_state=23,
    )
    second = candidate.fit_multicluster_boundaries(
        embeddings,
        labels,
        clusters_per_label=2,
        radius_scale=1.0,
        random_state=23,
    )

    assert first.labels == second.labels
    np.testing.assert_array_equal(first.centroids, second.centroids)
    np.testing.assert_array_equal(first.variances, second.variances)
    np.testing.assert_array_equal(first.radii, second.radii)


def test_oracle_pricing_names_every_served_loss_and_outside_gain() -> None:
    candidate = _candidate_module()
    rows = (
        candidate.OracleRetrievalRow(
            population="cut-a",
            row_id="served-kept",
            expected_operations=("system.time",),
            baseline_candidates=("system.time", "system.status"),
            outside_catalogue=False,
        ),
        candidate.OracleRetrievalRow(
            population="cut-b",
            row_id="served-lost",
            expected_operations=("note.read",),
            baseline_candidates=("note.read",),
            outside_catalogue=False,
        ),
        candidate.OracleRetrievalRow(
            population="open",
            row_id="outside-rejected",
            expected_operations=(),
            baseline_candidates=("task.create",),
            outside_catalogue=True,
        ),
        candidate.OracleRetrievalRow(
            population="open",
            row_id="outside-accepted",
            expected_operations=(),
            baseline_candidates=("web.search", "task.list"),
            outside_catalogue=True,
        ),
    )

    report = candidate.price_gate_against_oracles(
        rows,
        accepted=(True, False, False, True),
    )

    assert report["expected_operation_recall"] == {
        "baseline": "2/2",
        "candidate": "1/2",
    }
    assert report["served_rows_lost"] == ["cut-b:served-lost"]
    assert report["outside_zero_candidates"] == {
        "baseline": "0/2",
        "candidate": "1/2",
    }
    assert report["outside_rows_newly_zero"] == ["open:outside-rejected"]
    assert report["refuting_populations"] == {
        "served_loss": ["cut-a", "cut-b"],
        "outside_non_empty": ["open"],
    }


def test_public_validation_loader_treats_only_supported_families_as_inside(
    tmp_path: Path,
) -> None:
    candidate = _candidate_module()
    source = tmp_path / "public.jsonl"
    rows = [
        {"text": "read the clock", "families": ["system"], "source_id": "inside"},
        {"text": "water the roses", "families": [], "source_id": "outside-empty"},
        {
            "text": "operate the spaceship",
            "families": ["spaceship"],
            "source_id": "outside-unknown",
        },
    ]
    source.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    loaded = candidate.load_public_validation_rows(source, {"system"})

    assert [row.inside_catalogue for row in loaded] == [True, False, False]
    assert [row.source_id for row in loaded] == [
        "inside",
        "outside-empty",
        "outside-unknown",
    ]


def test_duplicate_training_rows_do_not_create_empty_cluster_boundaries() -> None:
    candidate = _candidate_module()
    embeddings = np.asarray(
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
        ],
        dtype=np.float32,
    )

    boundaries = candidate.fit_multicluster_boundaries(
        embeddings,
        ("alpha", "alpha", "alpha", "alpha"),
        clusters_per_label=2,
        radius_scale=1.0,
        random_state=29,
    )

    assert boundaries.labels == ("alpha",)
    assert np.isfinite(boundaries.centroids).all()
    assert np.isfinite(boundaries.variances).all()
    assert np.isfinite(boundaries.radii).all()
