"""Audit an SSL-recall plus explicit CTC-confusable-veto wake ensemble."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
from baxy_mind.wake_verifier import (  # noqa: E402
    CATEGORY_NAMES,
    CONFUSABLE_IDS,
    TARGET_IDS,
    _collapse_path,
    compress_category_logits_numpy,
    load_wake_verifier_candidate_config,
    normalize_audio,
    resolve_category_ids,
)
from evaluate_wake_verifier_negative_holdout_v1 import decode_flac, sha256  # noqa: E402


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"wake_ensemble_json_invalid:{path}")
    return value


def contains_sequence(
    collapsed: tuple[tuple[int, int, int], ...],
    sequences: tuple[tuple[int, ...], ...],
) -> bool:
    tokens = tuple(item[0] for item in collapsed)
    return any(
        tokens[start : start + len(sequence)] == sequence
        for sequence in sequences
        for start in range(len(tokens) - len(sequence) + 1)
    )


def ensemble_accept(
    *, ssl_accepted: bool, explicit_confusable: bool, ctc_positive: bool
) -> tuple[bool, str]:
    if ctc_positive:
        return True, "ctc_positive_authority"
    if explicit_confusable:
        return False, "ctc_explicit_confusable_veto"
    if ssl_accepted:
        return True, "ssl_product_scan"
    return False, "no_positive_evidence"


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    positives = [record for record in records if record["label"] == "positive"]
    negatives = [record for record in records if record["label"] != "positive"]
    accepted = sum(bool(record["ensemble_accepted"]) for record in positives)
    false = sum(bool(record["ensemble_accepted"]) for record in negatives)
    return {
        "positive_accepted": accepted,
        "positive_total": len(positives),
        "negative_false_accepts": false,
        "negative_total": len(negatives),
        "development_gate_passed": accepted == len(positives) and false == 0,
    }


def audit(
    *,
    legacy_manifest_path: Path,
    expanded_manifest_path: Path,
    hidden_sweep_path: Path,
    legacy_ctc_path: Path,
    expanded_ctc_path: Path,
    verifier_manifest_path: Path,
    ffmpeg_path: Path,
    output_path: Path,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("wake_ensemble_output_exists")
    paths = [
        legacy_manifest_path,
        expanded_manifest_path,
        hidden_sweep_path,
        legacy_ctc_path,
        expanded_ctc_path,
        verifier_manifest_path,
        ffmpeg_path,
    ]
    (
        legacy_manifest_path,
        expanded_manifest_path,
        hidden_sweep_path,
        legacy_ctc_path,
        expanded_ctc_path,
        verifier_manifest_path,
        ffmpeg_path,
    ) = [path.resolve(strict=True) for path in paths]
    output_path = output_path.resolve()
    legacy = read_object(legacy_manifest_path)
    expanded = read_object(expanded_manifest_path)
    hidden = read_object(hidden_sweep_path)
    legacy_ctc = read_object(legacy_ctc_path)
    expanded_ctc = read_object(expanded_ctc_path)
    if (
        legacy.get("schema") != "baxy.ccby-wake-holdout-corpus.v1"
        or expanded.get("schema") != "baxy.ccby-wake-v5-development-corpus.v1"
        or hidden.get("schema") != "baxy.wav2vec2-hidden-wake-expanded-layer-sweep.v1"
        or legacy_ctc.get("schema") != "baxy.wake-verifier-product-capture-development.v1"
        or expanded_ctc.get("schema") != "baxy.wake-verifier-expanded-development.v1"
        or hidden.get("blind_human_audio_accessed") is not False
        or legacy_ctc.get("blind_human_partition_accessed") is not False
        or expanded_ctc.get("blind_human_audio_accessed") is not False
    ):
        raise ValueError("wake_ensemble_boundary_invalid")
    source_records = [
        ({**record, "corpus": "legacy"}, legacy_manifest_path.parent)
        for record in legacy.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ] + [
        ({**record, "corpus": "expanded"}, expanded_manifest_path.parent)
        for record in expanded.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    if len(source_records) != 30:
        raise ValueError("wake_ensemble_record_count_invalid")
    hidden_winner = hidden.get("winner")
    if not isinstance(hidden_winner, dict) or not isinstance(hidden_winner.get("records"), list):
        raise ValueError("wake_ensemble_hidden_winner_invalid")
    hidden_by_path = {
        str(record["relative_path"]): record for record in hidden_winner["records"]
    }
    ctc_by_path = {
        str(record["relative_path"]): record
        for source in (legacy_ctc, expanded_ctc)
        for record in source.get("records", [])
        if isinstance(record, dict)
    }
    expected_paths = {str(record["output_relative_path"]) for record, _ in source_records}
    if set(hidden_by_path) != expected_paths or set(ctc_by_path) != expected_paths:
        raise ValueError("wake_ensemble_record_alignment_invalid")

    config = load_wake_verifier_candidate_config(verifier_manifest_path)
    vocabulary = read_object(config.vocabulary_path)
    if not all(isinstance(key, str) and isinstance(value, int) for key, value in vocabulary.items()):
        raise ValueError("wake_ensemble_vocabulary_invalid")
    category_ids = resolve_category_ids(vocabulary, 0)
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(
        str(config.graph_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for source, root in source_records:
        relative = str(source["output_relative_path"])
        path = root / relative
        wav = source.get("wav")
        if not isinstance(wav, dict) or sha256(path) != wav.get("sha256"):
            raise ValueError(f"wake_ensemble_audio_hash_mismatch:{path}")
        audio = decode_flac(ffmpeg_path, path)
        if len(audio) != config.maximum_samples:
            raise ValueError(f"wake_ensemble_audio_length_invalid:{path}:{len(audio)}")
        logits = session.run(
            ["logits"], {"input_values": normalize_audio(audio)}
        )[0]
        probabilities = compress_category_logits_numpy(logits, category_ids)
        collapsed = _collapse_path(np.argmax(probabilities, axis=1))
        explicit_confusable = contains_sequence(collapsed, CONFUSABLE_IDS)
        explicit_target = contains_sequence(collapsed, TARGET_IDS)
        hidden_record = hidden_by_path[relative]
        ctc_record = ctc_by_path[relative]
        accepted, method = ensemble_accept(
            ssl_accepted=bool(hidden_record["accepted"]),
            explicit_confusable=explicit_confusable,
            ctc_positive=bool(ctc_record["detected"]),
        )
        records.append(
            {
                "corpus": source["corpus"],
                "relative_path": relative,
                "speaker_group": source.get("speaker_group"),
                "label": source["label"],
                "ssl_calibrated_margin": hidden_record["calibrated_margin"],
                "ssl_accepted": hidden_record["accepted"],
                "ctc_product_detected": ctc_record["detected"],
                "ctc_product_method": ctc_record["method"],
                "ctc_product_margin": ctc_record.get("margin"),
                "ctc_greedy_exact_target": explicit_target,
                "ctc_greedy_exact_confusable": explicit_confusable,
                "ctc_collapsed_categories": [CATEGORY_NAMES[item[0]] for item in collapsed],
                "ensemble_method": method,
                "ensemble_accepted": accepted,
            }
        )
    metrics = summarize(records)
    report: dict[str, object] = {
        "schema": "baxy.wake-ssl-ctc-ensemble-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_hypothesis_after_component_failure_analysis",
        "sources": {
            "legacy_manifest_sha256": sha256(legacy_manifest_path),
            "expanded_manifest_sha256": sha256(expanded_manifest_path),
            "hidden_sweep_sha256": sha256(hidden_sweep_path),
            "legacy_ctc_sha256": sha256(legacy_ctc_path),
            "expanded_ctc_sha256": sha256(expanded_ctc_path),
            "verifier_manifest_sha256": sha256(verifier_manifest_path),
            "verifier_graph_sha256": sha256(config.graph_path),
            "verifier_graph_data_sha256": sha256(config.graph_data_path),
            "ffmpeg_sha256": sha256(ffmpeg_path),
        },
        "rule": {
            "positive_authority": "frozen_product_ctc_acceptance",
            "confusable_veto": "exact_greedy_span_in_general_phoneme_category_sequence",
            "fallback_authority": "speaker_held_out_ssl_product_scan_margin_at_or_above_zero",
            "precedence": [
                "ctc_positive_authority",
                "ctc_explicit_confusable_veto",
                "ssl_product_scan",
                "reject",
            ],
            "hardcoded_speaker_or_filename_rules": False,
        },
        "hidden_winner": {
            key: hidden_winner[key]
            for key in (
                "layer",
                "window_offset_seconds",
                "window_duration_seconds",
                "pooling",
                "metrics",
            )
        },
        "metrics": metrics,
        "records": records,
        "runtime_seconds": time.perf_counter() - started,
        "development_only": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-manifest", type=Path, required=True)
    parser.add_argument("--expanded-manifest", type=Path, required=True)
    parser.add_argument("--hidden-sweep", type=Path, required=True)
    parser.add_argument("--legacy-ctc", type=Path, required=True)
    parser.add_argument("--expanded-ctc", type=Path, required=True)
    parser.add_argument("--verifier-manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        legacy_manifest_path=arguments.legacy_manifest,
        expanded_manifest_path=arguments.expanded_manifest,
        hidden_sweep_path=arguments.hidden_sweep,
        legacy_ctc_path=arguments.legacy_ctc,
        expanded_ctc_path=arguments.expanded_ctc,
        verifier_manifest_path=arguments.verifier_manifest,
        ffmpeg_path=arguments.ffmpeg,
        output_path=arguments.output,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
