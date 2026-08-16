"""Build label-free temporal CTC candidate features for cached MSWC queries."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


FEATURE_NAMES = (
    "forward_score_per_frame",
    "phoneme_length",
    "character_length",
    "adjacent_repeat_fraction",
    "greedy_edit_similarity",
    "greedy_length_ratio",
    "greedy_token_coverage",
    "independent_token_peak_mean",
    "independent_token_peak_minimum",
    "independent_token_peak_maximum",
    "independent_token_peak_deviation",
    "independent_peak_margin_mean",
    "independent_peak_margin_minimum",
    "independent_peak_order_fraction",
    "independent_peak_regression_fraction",
    "independent_peak_span_fraction",
    "independent_unique_peak_fraction",
    "monotonic_token_score_per_token",
    "monotonic_token_score_per_frame",
    "monotonic_order_penalty_per_token",
    "candidate_token_mass_mean",
    "candidate_token_mass_maximum",
    "candidate_token_mass_over_blank_mean",
    "query_blank_log_probability_mean",
    "query_frame_entropy_mean",
    "query_frames_scaled",
)


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_ctc_temporal_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SEQUENCE = load_component(
    "evaluate_mswc_spanish_qbye_sequence_tuning_v3.py",
    "_baxy_mswc_ctc_temporal_sequence_v13",
)
_HASH = load_component(
    "evaluate_mswc_spanish_qbye_ssl_baseline_v1.py",
    "_baxy_mswc_ctc_temporal_hash_v13",
)


def edit_distance(left: list[int], right: list[int]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + int(left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def collapse_greedy(values: np.ndarray, blank_id: int) -> list[int]:
    result = []
    previous = None
    for raw in np.asarray(values, dtype=np.int64).tolist():
        if raw != previous and raw != blank_id:
            result.append(int(raw))
        previous = raw
    return result


def monotonic_token_score(log_probabilities: np.ndarray, sequence: list[int]) -> float:
    values = np.asarray(log_probabilities, dtype=np.float64)
    if values.ndim != 2 or not sequence or len(sequence) > len(values):
        return -1e4
    previous = values[:, int(sequence[0])].copy()
    for token in sequence[1:]:
        prefix = np.maximum.accumulate(previous)
        current = np.full_like(previous, -np.inf)
        current[1:] = values[1:, int(token)] + prefix[:-1]
        previous = current
    return float(np.max(previous))


def temporal_candidate_features(
    *,
    log_probabilities: np.ndarray,
    sequence: list[int],
    candidate_characters: int,
    forward_score_per_frame: float,
    blank_id: int,
) -> np.ndarray:
    values = np.asarray(log_probabilities, dtype=np.float64)
    tokens = [int(token) for token in sequence]
    if (
        values.ndim != 2
        or not len(values)
        or not tokens
        or any(token < 0 or token >= values.shape[1] for token in tokens)
        or not 0 <= blank_id < values.shape[1]
    ):
        raise ValueError("mswc_ctc_temporal_candidate_invalid")
    frames = len(values)
    greedy = collapse_greedy(np.argmax(values, axis=1), blank_id)
    distance = edit_distance(greedy, tokens)
    edit_similarity = 1.0 - distance / max(len(greedy), len(tokens), 1)
    token_matrix = values[:, tokens]
    peak_frames = np.argmax(token_matrix, axis=0)
    peak_values = token_matrix[peak_frames, np.arange(len(tokens))]
    frame_maximum = np.max(values, axis=1)
    peak_margins = peak_values - frame_maximum[peak_frames]
    adjacent_order = (
        np.diff(peak_frames) >= 0 if len(peak_frames) > 1 else np.asarray([True])
    )
    regressions = (
        np.maximum(0, -np.diff(peak_frames))
        if len(peak_frames) > 1
        else np.asarray([0])
    )
    independent_sum = float(np.sum(peak_values))
    monotonic_sum = monotonic_token_score(values, tokens)
    candidate_mass = np.max(token_matrix, axis=1)
    probabilities = np.exp(values)
    entropy = -np.sum(probabilities * values, axis=1)
    token_set = set(tokens)
    greedy_coverage = len(token_set.intersection(greedy)) / max(len(token_set), 1)
    repeats = sum(left == right for left, right in zip(tokens, tokens[1:]))
    span = (
        (int(np.max(peak_frames)) - int(np.min(peak_frames)) + 1) / frames
        if len(peak_frames)
        else 0.0
    )
    features = np.asarray(
        [
            forward_score_per_frame,
            len(tokens) / 16.0,
            candidate_characters / 16.0,
            repeats / max(len(tokens) - 1, 1),
            edit_similarity,
            len(greedy) / max(len(tokens), 1),
            greedy_coverage,
            float(np.mean(peak_values)),
            float(np.min(peak_values)),
            float(np.max(peak_values)),
            float(np.std(peak_values)),
            float(np.mean(peak_margins)),
            float(np.min(peak_margins)),
            float(np.mean(adjacent_order)),
            float(np.sum(regressions)) / max(frames * (len(tokens) - 1), 1),
            span,
            len(set(peak_frames.tolist())) / len(tokens),
            monotonic_sum / len(tokens),
            monotonic_sum / frames,
            (independent_sum - monotonic_sum) / len(tokens),
            float(np.mean(candidate_mass)),
            float(np.max(candidate_mass)),
            float(np.mean(candidate_mass - values[:, blank_id])),
            float(np.mean(values[:, blank_id])),
            float(np.mean(entropy)),
            frames / 100.0,
        ],
        dtype=np.float32,
    )
    if features.shape != (len(FEATURE_NAMES),) or not np.isfinite(features).all():
        raise ValueError("mswc_ctc_temporal_features_invalid")
    return features


def build(
    *,
    ctc_feature_manifest_path: Path,
    hyper_ctc_cache_path: Path,
    tokenizer_directory: Path,
    phonemizer_site_packages: Path,
    output_cache_path: Path,
    output_report_path: Path,
    word_set: str,
) -> dict[str, object]:
    if (
        output_cache_path.exists()
        or output_report_path.exists()
        or output_cache_path.suffix.lower() != ".npz"
        or word_set not in {"tuning", "reserved"}
    ):
        raise ValueError("mswc_ctc_temporal_schedule_invalid")
    ctc_feature_manifest_path = ctc_feature_manifest_path.resolve(strict=True)
    hyper_ctc_cache_path = hyper_ctc_cache_path.resolve(strict=True)
    tokenizer_directory = tokenizer_directory.resolve(strict=True)
    phonemizer_site_packages = phonemizer_site_packages.resolve(strict=True)
    output_cache_path = output_cache_path.resolve()
    output_report_path = output_report_path.resolve()
    manifest = _SEQUENCE.read_object(ctc_feature_manifest_path)
    records_raw = manifest.get("records")
    files = manifest.get("files")
    sources = manifest.get("sources")
    contract = manifest.get("contract")
    if (
        manifest.get("schema") != "baxy.mswc-spanish-qbye-sequence-features.v3"
        or manifest.get("official_test_audio_accessed") is not False
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(records_raw, list)
        or not isinstance(files, dict)
        or not isinstance(sources, dict)
        or not isinstance(contract, dict)
    ):
        raise ValueError("mswc_ctc_temporal_boundary_invalid")
    records = []
    index_by_hash: dict[str, int] = {}
    for index, raw in enumerate(records_raw):
        if not isinstance(raw, dict):
            raise ValueError("mswc_ctc_temporal_record_invalid")
        records.append(raw)
        audio_hash = str(raw["audio_sha256"])
        if audio_hash in index_by_hash:
            raise ValueError("mswc_ctc_temporal_audio_duplicate")
        index_by_hash[audio_hash] = index
    with np.load(hyper_ctc_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-hyperspotter-ctc-score-cache.v1"
        ]:
            raise ValueError("mswc_ctc_temporal_cache_schema_invalid")
        query_hashes = cache["query_audio_sha256"].astype(str)
        query_words = cache["query_words"].astype(str)
        candidate_indexes = cache["candidate_indexes"].astype(np.int64)
        class_names = cache["class_names"].astype(str)
        candidate_words = class_names[candidate_indexes]
        ctc_scores = cache["ctc_scores"].astype(np.float64)
    query_indexes = []
    for audio_hash, word in zip(query_hashes, query_words, strict=True):
        index = index_by_hash.get(audio_hash)
        if index is None:
            raise ValueError("mswc_ctc_temporal_audio_missing")
        record = records[index]
        if (
            record.get("partition") != "open_keyword_query"
            or str(record.get("class_name")) != word
        ):
            raise ValueError("mswc_ctc_temporal_audio_alignment_invalid")
        query_indexes.append(index)
    expected_queries = 2400 if word_set == "tuning" else 1200
    expected_classes = 400 if word_set == "tuning" else 200
    if (
        len(query_indexes) != expected_queries
        or len(class_names) != expected_classes
        or candidate_indexes.shape != (expected_queries, 41)
        or not np.array_equal(candidate_words[:, 0], query_words)
    ):
        raise ValueError("mswc_ctc_temporal_partition_invalid")
    offset_path = ctc_feature_manifest_path.parent / str(files["offsets"])
    descriptor = files.get("ctc_log_probabilities")
    if (
        not isinstance(descriptor, dict)
        or _HASH.sha256(offset_path) != files.get("offsets_sha256")
    ):
        raise ValueError("mswc_ctc_temporal_offset_invalid")
    probability_path = ctc_feature_manifest_path.parent / str(descriptor["path"])
    if _HASH.sha256(probability_path) != descriptor.get("sha256"):
        raise ValueError("mswc_ctc_temporal_probability_hash_invalid")
    offsets = np.load(offset_path)
    log_probabilities = np.load(probability_path, mmap_mode="r")
    if len(offsets) != len(records) + 1 or int(offsets[-1]) != len(log_probabilities):
        raise ValueError("mswc_ctc_temporal_probability_shape_invalid")
    if _HASH.sha256(tokenizer_directory / "vocab.json") != sources.get(
        "model_vocabulary_sha256"
    ):
        raise ValueError("mswc_ctc_temporal_vocabulary_invalid")
    if str(phonemizer_site_packages) not in sys.path:
        sys.path.append(str(phonemizer_site_packages))
    from audit_voxcpm2_gguf_pilot import configure_espeak_backend

    if configure_espeak_backend() is None:
        raise ValueError("mswc_ctc_temporal_espeak_unavailable")
    from transformers import Wav2Vec2PhonemeCTCTokenizer

    tokenizer = Wav2Vec2PhonemeCTCTokenizer.from_pretrained(
        str(tokenizer_directory),
        local_files_only=True,
        phonemizer_lang="es",
    )
    sequences = [
        [int(token) for token in values]
        for values in tokenizer(class_names.tolist())["input_ids"]
    ]
    blank_id = int(contract["ctc_blank_id"])
    feature_rows = np.empty(
        (expected_queries, 41, len(FEATURE_NAMES)), dtype=np.float32
    )
    for row, record_index in enumerate(query_indexes):
        start = int(offsets[record_index])
        end = int(offsets[record_index + 1])
        query_values = np.asarray(log_probabilities[start:end], dtype=np.float32)
        for column, class_index in enumerate(candidate_indexes[row]):
            sequence = sequences[int(class_index)]
            forward_score = ctc_scores[row, column] - 0.05 * len(sequence)
            feature_rows[row, column] = temporal_candidate_features(
                log_probabilities=query_values,
                sequence=sequence,
                candidate_characters=len(candidate_words[row, column]),
                forward_score_per_frame=float(forward_score),
                blank_id=blank_id,
            )
        if (row + 1) % 200 == 0 or row + 1 == expected_queries:
            print(f"CTC_TEMPORAL_FEATURES|{row + 1}/{expected_queries}", flush=True)
    output_cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_cache_path,
        schema=np.asarray(["baxy.mswc-ctc-temporal-features.v1"]),
        features=feature_rows,
        feature_names=np.asarray(FEATURE_NAMES),
        query_audio_sha256=query_hashes,
        query_words=query_words,
        candidate_words=candidate_words,
        source_hyper_ctc_cache_sha256=np.asarray([_HASH.sha256(hyper_ctc_cache_path)]),
        source_ctc_feature_manifest_sha256=np.asarray(
            [_HASH.sha256(ctc_feature_manifest_path)]
        ),
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-ctc-temporal-feature-build.v13",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": f"{word_set}_label_free_temporal_ctc_candidate_features",
        "sources": {
            "ctc_feature_manifest_sha256": _HASH.sha256(ctc_feature_manifest_path),
            "hyper_ctc_cache_sha256": _HASH.sha256(hyper_ctc_cache_path),
            "tokenizer_vocabulary_sha256": _HASH.sha256(
                tokenizer_directory / "vocab.json"
            ),
            "output_cache_sha256": _HASH.sha256(output_cache_path),
        },
        "contract": {
            "word_set": word_set,
            "queries": expected_queries,
            "word_classes": expected_classes,
            "candidates_per_query": 41,
            "feature_names": list(FEATURE_NAMES),
            "label_metrics_computed": False,
        },
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
    parser.add_argument("--ctc-feature-manifest", type=Path, required=True)
    parser.add_argument("--hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--tokenizer-directory", type=Path, required=True)
    parser.add_argument("--phonemizer-site-packages", type=Path, required=True)
    parser.add_argument("--output-cache", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--word-set", choices=("tuning", "reserved"), required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(
        ctc_feature_manifest_path=args.ctc_feature_manifest,
        hyper_ctc_cache_path=args.hyper_ctc_cache,
        tokenizer_directory=args.tokenizer_directory,
        phonemizer_site_packages=args.phonemizer_site_packages,
        output_cache_path=args.output_cache,
        output_report_path=args.output_report,
        word_set=args.word_set,
    )
    print(json.dumps(report["contract"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
