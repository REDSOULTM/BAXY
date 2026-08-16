from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_mswc_spanish_forced_alignment_shortlist_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_mswc_spanish_forced_alignment_shortlist_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_top_depth_mask_unions_each_signal_top_candidate() -> None:
    mask = MODULE.top_depth_mask(
        signals=[
            np.asarray([[3.0, 2.0, 1.0], [1.0, 4.0, 2.0]]),
            np.asarray([[1.0, 2.0, 4.0], [5.0, 2.0, 1.0]]),
        ],
        depth=1,
    )
    assert mask.tolist() == [[True, False, True], [True, True, False]]


def test_global_standardize_has_unit_deviation() -> None:
    values = MODULE.global_standardize(np.asarray([[1.0, 2.0], [4.0, 8.0]]))
    assert abs(float(values.mean())) < 1e-12
    assert abs(float(values.std()) - 1.0) < 1e-12


def test_reserved_build_does_not_compute_label_recall(tmp_path: Path) -> None:
    hyper_cache = tmp_path / "hyper.npz"
    whisper_cache = tmp_path / "whisper.npz"
    output_cache = tmp_path / "shortlist.npz"
    output_report = tmp_path / "shortlist.json"
    candidate_indexes = np.asarray([[0, 1, 2], [1, 0, 2]], dtype=np.int64)
    class_names = np.asarray(["uno", "dos", "tres"])
    query_audio_sha256 = np.asarray(["a", "b"])
    query_words = np.asarray(["uno", "dos"])
    candidate_words = class_names[candidate_indexes]
    np.savez_compressed(
        hyper_cache,
        schema=np.asarray(["baxy.mswc-hyperspotter-ctc-score-cache.v1"]),
        hyper_scores=np.asarray([[3.0, 2.0, 1.0], [4.0, 1.0, 2.0]]),
        ctc_scores=np.asarray([[1.0, 2.0, 3.0], [2.0, 4.0, 1.0]]),
        candidate_indexes=candidate_indexes,
        class_names=class_names,
        query_audio_sha256=query_audio_sha256,
        query_words=query_words,
    )
    np.savez_compressed(
        whisper_cache,
        schema=np.asarray(["baxy.mswc-faster-whisper-score-cache.v1"]),
        whole_transcript_edit=np.asarray([[2.0, 1.0, 0.0], [1.0, 3.0, 2.0]]),
        whole_or_token_edit=np.asarray([[1.0, 0.0, 2.0], [3.0, 1.0, 2.0]]),
        candidate_words=candidate_words,
        query_audio_sha256=query_audio_sha256,
        query_words=query_words,
    )

    report = MODULE.build(
        hyper_ctc_cache_path=hyper_cache,
        whisper_cache_path=whisper_cache,
        output_cache_path=output_cache,
        output_report_path=output_report,
        depth=1,
        word_set="reserved",
    )

    assert report["metrics"]["true_candidate_recall"] is None
    assert report["label_metrics_computed"] is False
    assert report["research_reserved_examples_scored"] is True
