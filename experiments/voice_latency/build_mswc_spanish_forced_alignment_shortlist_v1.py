"""Build an aligned candidate mask from cached MSWC tuning score signals."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def global_standardize(scores: np.ndarray) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    deviation = float(np.std(values))
    if values.ndim != 2 or values.size == 0 or deviation <= 0.0:
        raise ValueError("mswc_forced_alignment_shortlist_scores_invalid")
    return (values - float(np.mean(values))) / deviation


def top_depth_mask(*, signals: list[np.ndarray], depth: int) -> np.ndarray:
    if not signals or depth < 1:
        raise ValueError("mswc_forced_alignment_shortlist_schedule_invalid")
    shape = np.asarray(signals[0]).shape
    if len(shape) != 2 or depth > shape[1]:
        raise ValueError("mswc_forced_alignment_shortlist_shape_invalid")
    mask = np.zeros(shape, dtype=bool)
    rows = np.arange(shape[0])[:, None]
    for signal_raw in signals:
        signal = np.asarray(signal_raw, dtype=np.float64)
        if signal.shape != shape or not np.isfinite(signal).all():
            raise ValueError("mswc_forced_alignment_shortlist_signal_invalid")
        indexes = np.argpartition(signal, -depth, axis=1)[:, -depth:]
        mask[rows, indexes] = True
    return mask


def build(
    *,
    hyper_ctc_cache_path: Path,
    whisper_cache_path: Path,
    output_cache_path: Path,
    output_report_path: Path,
    depth: int,
    word_set: str = "tuning",
) -> dict[str, object]:
    if (
        output_cache_path.exists()
        or output_report_path.exists()
        or output_cache_path.suffix.lower() != ".npz"
        or depth < 1
        or word_set not in {"tuning", "reserved"}
    ):
        raise ValueError("mswc_forced_alignment_shortlist_output_invalid")
    hyper_ctc_cache_path = hyper_ctc_cache_path.resolve(strict=True)
    whisper_cache_path = whisper_cache_path.resolve(strict=True)
    output_cache_path = output_cache_path.resolve()
    output_report_path = output_report_path.resolve()
    with np.load(hyper_ctc_cache_path, allow_pickle=False) as hyper_ctc:
        if hyper_ctc["schema"].tolist() != [
            "baxy.mswc-hyperspotter-ctc-score-cache.v1"
        ]:
            raise ValueError("mswc_forced_alignment_shortlist_hyper_schema_invalid")
        hyper_scores = hyper_ctc["hyper_scores"].astype(np.float64)
        ctc_scores = hyper_ctc["ctc_scores"].astype(np.float64)
        candidate_indexes = hyper_ctc["candidate_indexes"].astype(np.int64)
        class_names = hyper_ctc["class_names"].astype(str)
        candidate_words = class_names[candidate_indexes]
        query_audio_sha256 = hyper_ctc["query_audio_sha256"].astype(str)
        query_words = hyper_ctc["query_words"].astype(str)
    with np.load(whisper_cache_path, allow_pickle=False) as whisper:
        if whisper["schema"].tolist() != [
            "baxy.mswc-faster-whisper-score-cache.v1"
        ]:
            raise ValueError("mswc_forced_alignment_shortlist_whisper_schema_invalid")
        if (
            not np.array_equal(query_audio_sha256, whisper["query_audio_sha256"])
            or not np.array_equal(query_words, whisper["query_words"])
            or not np.array_equal(candidate_words, whisper["candidate_words"])
        ):
            raise ValueError("mswc_forced_alignment_shortlist_alignment_invalid")
        whisper_whole = whisper["whole_transcript_edit"].astype(np.float64)
        whisper_token = whisper["whole_or_token_edit"].astype(np.float64)
    standardized_hyper = global_standardize(hyper_scores)
    standardized_ctc = global_standardize(ctc_scores)
    standardized_whisper = global_standardize(whisper_whole)
    baseline = 0.3 * standardized_hyper + 0.7 * standardized_ctc
    three_way = (
        0.3 * standardized_hyper
        + 0.5 * standardized_ctc
        + 0.2 * standardized_whisper
    )
    signals = [
        hyper_scores,
        ctc_scores,
        whisper_whole,
        whisper_token,
        baseline,
        three_way,
    ]
    mask = top_depth_mask(signals=signals, depth=depth)
    widths = mask.sum(axis=1)
    output_cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_cache_path,
        schema=np.asarray(["baxy.mswc-forced-alignment-shortlist.v1"]),
        candidate_mask=mask.astype(np.uint8),
        query_audio_sha256=query_audio_sha256,
        query_words=query_words,
        candidate_words=candidate_words,
        depth=np.asarray([depth], dtype=np.int32),
        hyper_ctc_cache_sha256=np.asarray([sha256(hyper_ctc_cache_path)]),
        whisper_cache_sha256=np.asarray([sha256(whisper_cache_path)]),
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-forced-alignment-shortlist-report.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": f"research_{word_set}_cached_signal_top_depth_union",
        "sources": {
            "hyper_ctc_cache_sha256": sha256(hyper_ctc_cache_path),
            "whisper_cache_sha256": sha256(whisper_cache_path),
            "output_cache_sha256": sha256(output_cache_path),
        },
        "contract": {
            "depth_per_signal": depth,
            "signals": [
                "hyperspotter",
                "phoneme_ctc",
                "whisper_transcript_whole",
                "whisper_transcript_token",
                "hyperspotter_ctc_baseline",
                "three_way_linear",
            ],
            "positive_candidate_forced_into_shortlist": False,
        },
        "metrics": {
            "queries": int(mask.shape[0]),
            "candidate_width": int(mask.shape[1]),
            "shortlist_width_minimum": int(widths.min()),
            "shortlist_width_mean": float(widths.mean()),
            "shortlist_width_p95": float(np.quantile(widths, 0.95)),
            "shortlist_width_maximum": int(widths.max()),
            "true_candidate_recall": (
                float(mask[:, 0].mean()) if word_set == "tuning" else None
            ),
        },
        "label_metrics_computed": word_set == "tuning",
        "research_tuning_examples_scored": word_set == "tuning",
        "research_reserved_examples_scored": word_set == "reserved",
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--whisper-cache", type=Path, required=True)
    parser.add_argument("--output-cache", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument(
        "--word-set", choices=("tuning", "reserved"), default="tuning"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(
        hyper_ctc_cache_path=args.hyper_ctc_cache,
        whisper_cache_path=args.whisper_cache,
        output_cache_path=args.output_cache,
        output_report_path=args.output_report,
        depth=args.depth,
        word_set=args.word_set,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
