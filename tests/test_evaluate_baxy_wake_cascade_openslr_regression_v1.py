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
        / "evaluate_baxy_wake_cascade_openslr_regression_v1.py"
    )
    spec = importlib.util.spec_from_file_location(
        "baxy_wake_cascade_openslr_regression", script
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_window_schedule_matches_product_initial_window_and_hop() -> None:
    gate = _module()
    audio = np.arange(56_000, dtype=np.float32)
    windows = gate.window_views(audio, 4_000)
    assert len(windows) == 3
    assert np.array_equal(windows[0], audio[:48_000])
    assert np.array_equal(windows[-1], audio[8_000:56_000])


def test_broad_screen_has_a_fixed_margin_around_both_thresholds() -> None:
    gate = _module()
    logits = np.asarray(
        [
            [0.001, -0.199, -1.0, -2.0],
            [-0.001, -0.199, -1.0, -2.0],
            [0.5, -0.201, -1.0, -2.0],
        ],
        dtype=np.float32,
    )
    assert gate.broad_screen(logits).tolist() == [True, False, False]


def test_broad_screen_includes_manifest_single_alias_rescue_margin() -> None:
    gate = _module()

    class Config:
        rescue_alias_index = 2
        rescue_alias_threshold = 0.3

    logits = np.asarray(
        [
            [-2.0, -2.0, -0.199, -2.0],
            [-2.0, -2.0, -0.201, -2.0],
        ],
        dtype=np.float32,
    )
    assert gate.broad_screen(logits, Config()).tolist() == [True, False]


def test_lexical_capture_keeps_only_five_seconds_before_candidate() -> None:
    gate = _module()
    audio = np.arange(160_000, dtype=np.float32)
    capture = gate.lexical_capture(audio, window_index=20, hop_samples=4_000)
    raw_end = 48_000 + 20 * 4_000 - 16_000
    start = raw_end - 5 * 16_000
    assert np.array_equal(capture[: len(audio) - start], audio[start:])
    assert np.all(capture[-16_000:] == 0.0)


def test_exact_checkpoint_round_trips_without_transcript_text(tmp_path: Path) -> None:
    gate = _module()
    path = tmp_path / "exact.json"
    identities = {"candidate": "a" * 64}
    gate._write_exact_checkpoint(
        path,
        identities=identities,
        scan_checkpoint_sha256="b" * 64,
        completed_records=10,
        exact_proposals=3,
        lexical_invocations=2,
        strong_false=["c" * 64],
        lexical_false=[],
        elapsed_seconds=12.5,
    )
    assert gate._load_exact_checkpoint(
        path,
        identities=identities,
        scan_checkpoint_sha256="b" * 64,
    ) == (10, 3, 2, ["c" * 64], [], 12.5)


def test_batched_session_logits_preserves_order_and_batch_bound() -> None:
    gate = _module()

    class Session:
        def __init__(self) -> None:
            self.batch_sizes: list[int] = []

        def run(self, outputs, inputs):
            assert outputs == ["logits"]
            values = inputs["logmel"]
            self.batch_sizes.append(len(values))
            return [values[:, :1, :1].reshape(-1, 1)]

    session = Session()
    values = [np.full((2, 2), value, dtype=np.float32) for value in range(5)]
    actual = gate._batched_session_logits(
        session,
        output_name="logits",
        values=values,
        batch_size=2,
    )
    assert actual[:, 0].tolist() == [0, 1, 2, 3, 4]
    assert session.batch_sizes == [2, 2, 1]


def test_candidate_selection_keeps_later_windows_from_the_same_record() -> None:
    gate = _module()

    class Config:
        primary_threshold = 0.5
        secondary_threshold = 0.3
        rescue_alias_index = 2
        rescue_alias_threshold = 0.3

    outputs = [
        np.asarray(
            [
                [0.4, 0.2, -1.0, -2.0],
                [0.0, 0.0, 0.31, -2.0],
                [0.6, 0.4, -1.0, -2.0],
            ],
            dtype=np.float32,
        )
    ]
    assert gate.candidate_windows_by_record(
        outputs, [(0, 3), (0, 4), (1, 2)], Config()
    ) == {0: [4], 1: [2]}


def test_routed_candidate_selection_keeps_route_isolation() -> None:
    gate = _module()

    class Route:
        def __init__(self, indexes):
            self.upstream_indexes = indexes

    class Config:
        primary_threshold = 0.5
        secondary_threshold = 0.3
        rescue_alias_index = None
        rescue_alias_threshold = None
        routes = (Route((0,)), Route((1,)))

    outputs = [
        np.asarray([[0.6, 0.4, -1.0, -2.0]], dtype=np.float32),
        np.asarray([[-2.0, -2.0, -2.0, -2.0]], dtype=np.float32),
    ]
    assert gate.candidate_routes_by_record(outputs, [(3, 7)], Config()) == {
        3: [(7, (0,))]
    }
