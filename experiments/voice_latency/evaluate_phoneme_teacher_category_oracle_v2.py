"""Evaluate the lossless small-head projection of the frozen CTC teacher.

Only development data is read.  The synthetic negative set is first filtered
by the already-published stage-one cascade proposals; a verifier is never
calibrated on clips that would not invoke it in the real architecture.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_voxcpm2_gguf_pilot import configure_espeak_backend  # noqa: E402
from ctc_wake_verifier import (  # noqa: E402
    collapse_ctc_path,
    exact_sequence_spans,
    score_verifier_span,
)
from extract_mdtc_ctc_fbank_features import read_wav  # noqa: E402
from phoneme_student_vocabulary_v2 import (  # noqa: E402
    BLANK_ID,
    CATEGORY_NAMES,
    CONFUSABLE_IDS,
    TARGET_IDS,
    resolve_category_ids,
)
from train_mdtc_livekit_verifier_student import read_json, sha256  # noqa: E402


SAMPLE_RATE = 16_000
SAMPLES_PER_TEACHER_FRAME = 320
CONTEXT_FRAMES = 10


def compress_category_logits(
    torch: Any,
    logits: Any,
    category_ids: dict[str, tuple[int, ...]],
) -> Any:
    """Max-pool teacher logits so the reduced head preserves teacher argmax.

    Summing the posterior mass of hundreds of unrelated IPA tokens creates an
    artificial ``other`` winner even when the teacher's highest individual
    token is a retained BAXY phoneme.  Max-pooling logits is the exact maxout
    projection of the original classifier and avoids that distortion.
    """

    if logits.ndim != 3:
        raise ValueError("phoneme_category_oracle_logit_shape_invalid")
    values = []
    for name in CATEGORY_NAMES:
        ids = category_ids.get(name)
        if not ids:
            raise ValueError(f"phoneme_category_oracle_category_empty:{name}")
        values.append(logits[:, :, list(ids)].max(dim=-1).values)
    output = torch.softmax(torch.stack(values, dim=-1).float(), dim=-1)
    if not bool(torch.isfinite(output).all()):
        raise ValueError("phoneme_category_oracle_probability_values_invalid")
    return output / output.sum(dim=-1, keepdim=True).clamp_min(1e-12)


def _lexical_locator_tuple(locator: dict[str, object]) -> tuple[int, int, str]:
    return (
        int(locator["locator_start_frame"]),
        int(locator["locator_end_frame"]),
        "parakeet_lexical_proposal",
    )


def score_category_probabilities(
    probabilities: np.ndarray,
    *,
    lexical_locators: tuple[tuple[int, int, str], ...] = (),
    veto_spans: tuple[tuple[int, int], ...] = (),
    context_frames: int = CONTEXT_FRAMES,
) -> dict[str, object]:
    values = np.asarray(probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[1] != len(CATEGORY_NAMES)
        or values.shape[0] == 0
        or not np.isfinite(values).all()
        or np.any(values < 0.0)
    ):
        raise ValueError("phoneme_category_oracle_clip_values_invalid")
    totals = values.sum(axis=1)
    if not np.allclose(totals, 1.0, atol=2e-5):
        raise ValueError("phoneme_category_oracle_clip_probability_sum_invalid")
    if context_frames < 0:
        raise ValueError("phoneme_category_oracle_context_invalid")
    log_probabilities = np.log(np.maximum(values, 1e-12))
    predicted = np.argmax(values, axis=1)
    collapsed = collapse_ctc_path(predicted, BLANK_ID)
    greedy_spans = exact_sequence_spans(collapsed, TARGET_IDS)
    locators: list[tuple[int, int, str]] = [
        (start, end, "category_greedy_exact_target")
        for start, end, _ in greedy_spans
    ]
    locators.extend(lexical_locators)
    unique_locators = tuple(dict.fromkeys(locators))
    scored = []
    for start, end, source in unique_locators:
        veto = any(start < veto_end and veto_start < end for veto_start, veto_end in veto_spans)
        score = score_verifier_span(
            log_probabilities,
            start_frame=start,
            end_frame=end,
            target_sequences=TARGET_IDS,
            confusable_sequences=CONFUSABLE_IDS,
            blank_id=BLANK_ID,
            context_before_frames=context_frames,
            context_after_frames=context_frames,
        )
        scored.append(
            {
                "source": source,
                "locator_start_frame": start,
                "locator_end_frame": end,
                "multiword_non_target_veto": veto,
                **score,
            }
        )
    eligible = [item for item in scored if not bool(item["multiword_non_target_veto"])]
    best = max(eligible, key=lambda item: float(item["margin"])) if eligible else None
    return {
        "collapsed_category_ids": [int(item[0]) for item in collapsed],
        "collapsed_categories": [CATEGORY_NAMES[int(item[0])] for item in collapsed],
        "greedy_target_span_count": len(greedy_spans),
        "locators": scored,
        "best_verifier": best,
    }


def search_category_probabilities(
    probabilities: np.ndarray,
    *,
    span_frames: tuple[int, ...] = (36, 40, 44, 48, 52),
    hop_frames: int = 4,
) -> dict[str, object]:
    """Locate a keyword by QbT margin when the greedy path is imperfect."""

    values = np.asarray(probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[1] != len(CATEGORY_NAMES)
        or values.shape[0] == 0
        or not np.isfinite(values).all()
        or np.any(values < 0.0)
        or not span_frames
        or any(span <= 0 for span in span_frames)
        or hop_frames <= 0
    ):
        raise ValueError("phoneme_category_search_values_invalid")
    if not np.allclose(values.sum(axis=1), 1.0, atol=2e-5):
        raise ValueError("phoneme_category_search_probability_sum_invalid")
    log_probabilities = np.log(np.maximum(values, 1e-12))
    candidates = []
    for requested_span in sorted(set(span_frames)):
        span = min(requested_span, len(values))
        final_start = len(values) - span
        starts = list(range(0, final_start + 1, hop_frames))
        if not starts or starts[-1] != final_start:
            starts.append(final_start)
        for start in starts:
            scored = score_verifier_span(
                log_probabilities,
                start_frame=start,
                end_frame=start + span,
                target_sequences=TARGET_IDS,
                confusable_sequences=CONFUSABLE_IDS,
                blank_id=BLANK_ID,
                context_before_frames=0,
                context_after_frames=0,
            )
            candidates.append(
                {
                    "source": "category_qbt_span_search",
                    "requested_span_frames": requested_span,
                    "target_log_probability_per_frame": float(
                        scored["target_log_probability"]
                    )
                    / span,
                    **scored,
                }
            )
    best = max(candidates, key=lambda item: float(item["margin"]))
    return {
        "span_frames": list(sorted(set(span_frames))),
        "hop_frames": hop_frames,
        "candidate_count": len(candidates),
        "best_verifier": best,
    }


def search_anchored_category_probabilities(
    probabilities: np.ndarray,
    *,
    minimum_span_frames: int = 8,
    maximum_span_frames: int = 40,
    context_frames: int = CONTEXT_FRAMES,
) -> dict[str, object]:
    """Use target-initial and target-ending greedy anchors for a QbT span."""

    values = np.asarray(probabilities, dtype=np.float64)
    if (
        values.ndim != 2
        or values.shape[1] != len(CATEGORY_NAMES)
        or values.shape[0] == 0
        or not np.isfinite(values).all()
        or np.any(values < 0.0)
        or minimum_span_frames <= 0
        or maximum_span_frames < minimum_span_frames
        or context_frames < 0
    ):
        raise ValueError("phoneme_category_anchor_values_invalid")
    if not np.allclose(values.sum(axis=1), 1.0, atol=2e-5):
        raise ValueError("phoneme_category_anchor_probability_sum_invalid")
    log_probabilities = np.log(np.maximum(values, 1e-12))
    collapsed = collapse_ctc_path(np.argmax(values, axis=1), BLANK_ID)
    target_initials = {sequence[0] for sequence in TARGET_IDS}
    target_endings = {sequence[-1] for sequence in TARGET_IDS}
    candidates = []
    for initial_index, (initial, start, _) in enumerate(collapsed):
        if initial not in target_initials:
            continue
        for ending, _, end in collapsed[initial_index + 1 :]:
            span = end - start
            if span > maximum_span_frames:
                break
            if ending not in target_endings or span < minimum_span_frames:
                continue
            scored = score_verifier_span(
                log_probabilities,
                start_frame=start,
                end_frame=end,
                target_sequences=TARGET_IDS,
                confusable_sequences=CONFUSABLE_IDS,
                blank_id=BLANK_ID,
                context_before_frames=context_frames,
                context_after_frames=context_frames,
            )
            candidates.append(
                {
                    "source": "category_qbt_greedy_boundary_anchors",
                    "locator_start_frame": start,
                    "locator_end_frame": end,
                    **scored,
                }
            )
    best = (
        max(candidates, key=lambda item: float(item["margin"]))
        if candidates
        else None
    )
    return {
        "minimum_span_frames": minimum_span_frames,
        "maximum_span_frames": maximum_span_frames,
        "context_frames": context_frames,
        "candidate_count": len(candidates),
        "best_verifier": best,
    }


def _lexical_locators(record: dict[str, object], key: str) -> tuple[tuple[int, int, str], ...]:
    values = record.get(key)
    if not isinstance(values, list):
        return ()
    return tuple(
        _lexical_locator_tuple(value)
        for value in values
        if isinstance(value, dict)
        and value.get("source") == "parakeet_lexical_proposal"
    )


def _veto_spans(record: dict[str, object], key: str) -> tuple[tuple[int, int], ...]:
    values = record.get(key)
    if not isinstance(values, list):
        return ()
    return tuple(
        (int(value["locator_start_frame"]), int(value["locator_end_frame"]))
        for value in values
        if isinstance(value, dict) and bool(value.get("multiword_non_target_veto"))
    )


def evaluate(
    *,
    teacher_directory: Path,
    synthetic_directory: Path,
    synthetic_negative_report_path: Path,
    human_teacher_report_path: Path,
    output_path: Path,
    batch_size: int,
    device: str,
) -> dict[str, object]:
    if batch_size <= 0 or device not in {"cpu", "cuda"}:
        raise ValueError("phoneme_category_oracle_schedule_invalid")
    teacher_directory = teacher_directory.resolve(strict=True)
    synthetic_directory = synthetic_directory.resolve(strict=True)
    synthetic_negative_report_path = synthetic_negative_report_path.resolve(
        strict=True
    )
    human_teacher_report_path = human_teacher_report_path.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"phoneme_category_oracle_output_exists:{output_path}")
    negative_report = read_json(synthetic_negative_report_path)
    human_report = read_json(human_teacher_report_path)
    if negative_report.get("schema") != "baxy.livekit-negative-ctc-cascade-development.v1":
        raise ValueError("unsupported_phoneme_category_negative_report")
    if human_report.get("schema") != "baxy.ccby-wake-ctc-cascade-development.v1":
        raise ValueError("unsupported_phoneme_category_human_report")
    if (
        negative_report.get("blind_human_partition_accessed") is not False
        or human_report.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("phoneme_category_oracle_blind_boundary_invalid")
    corpus_path = Path(str(human_report.get("corpus_manifest"))).resolve(strict=True)
    if sha256(corpus_path) != human_report.get("corpus_manifest_sha256"):
        raise ValueError("phoneme_category_oracle_corpus_hash_mismatch")
    corpus_root = corpus_path.parent
    negative_values = negative_report.get("records")
    human_values = human_report.get("records")
    if not isinstance(negative_values, list) or not isinstance(human_values, list):
        raise ValueError("phoneme_category_oracle_records_missing")

    items: list[dict[str, object]] = []
    for record in negative_values:
        if not isinstance(record, dict) or not bool(record.get("stage1_proposed")):
            continue
        relative_path = f"negative_test/{record['file']}"
        path = (synthetic_directory / relative_path).resolve(strict=True)
        if sha256(path) != record.get("wav_sha256"):
            raise ValueError(f"phoneme_category_oracle_synthetic_hash_mismatch:{relative_path}")
        stage2 = record.get("stage2")
        items.append(
            {
                "partition": "synthetic_negative_development",
                "label": "negative",
                "path": path,
                "relative_path": relative_path,
                "source_record": record,
                "lexical_locators": _lexical_locators(
                    stage2 if isinstance(stage2, dict) else {}, "locators"
                ),
                "veto_spans": _veto_spans(
                    stage2 if isinstance(stage2, dict) else {}, "locators"
                ),
            }
        )
    for record in human_values:
        if not isinstance(record, dict):
            raise ValueError("phoneme_category_oracle_human_record_invalid")
        if not bool(record.get("stage1_proposed")):
            lexical_locators: tuple[tuple[int, int, str], ...] = ()
        else:
            lexical_locators = _lexical_locators(record, "verifier_locators")
        relative_path = str(record.get("output_relative_path"))
        path = (corpus_root / relative_path).resolve(strict=True)
        items.append(
            {
                "partition": "human_development",
                "label": str(record.get("label")),
                "path": path,
                "relative_path": relative_path,
                "source_id": record.get("source_id"),
                "speaker_group": record.get("speaker_group"),
                "stage1_proposed": bool(record.get("stage1_proposed")),
                "lexical_locators": lexical_locators,
                "veto_spans": _veto_spans(record, "verifier_locators"),
            }
        )
    if not items or not any(item["partition"] == "human_development" for item in items):
        raise ValueError("phoneme_category_oracle_partition_empty")

    espeak = configure_espeak_backend()
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    load_started = time.perf_counter()
    processor = Wav2Vec2Processor.from_pretrained(
        teacher_directory, local_files_only=True
    )
    model = Wav2Vec2ForCTC.from_pretrained(
        teacher_directory, local_files_only=True
    ).eval().to(device)
    category_ids = resolve_category_ids(
        processor.tokenizer.get_vocab(), int(processor.tokenizer.pad_token_id)
    )
    load_seconds = time.perf_counter() - load_started
    evaluated: list[dict[str, object]] = []
    inference_seconds = 0.0
    for start in range(0, len(items), batch_size):
        batch = items[start : start + batch_size]
        audios = [read_wav(Path(str(item["path"]))) for item in batch]
        prepared = processor(
            audios, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True
        )
        input_lengths = torch.tensor(
            [len(audio) for audio in audios], dtype=torch.long, device=device
        )
        started = time.perf_counter()
        with torch.inference_mode():
            logits = model(input_values=prepared.input_values.to(device)).logits.float()
            probabilities = compress_category_logits(
                torch, logits, category_ids
            ).cpu().numpy()
        if device == "cuda":
            torch.cuda.synchronize()
        inference_seconds += time.perf_counter() - started
        output_lengths = model._get_feat_extract_output_lengths(input_lengths).tolist()
        for item, probability, length in zip(batch, probabilities, output_lengths, strict=True):
            scored = score_category_probabilities(
                probability[: int(length)],
                lexical_locators=tuple(item["lexical_locators"]),
                veto_spans=tuple(item["veto_spans"]),
            )
            evaluated.append(
                {
                    "partition": item["partition"],
                    "label": item["label"],
                    "relative_path": item["relative_path"],
                    "source_id": item.get("source_id"),
                    "speaker_group": item.get("speaker_group"),
                    "stage1_proposed": item.get("stage1_proposed", True),
                    **scored,
                }
            )
        print(f"ORACLE|{min(start + batch_size, len(items))}/{len(items)}", flush=True)

    synthetic = [
        record
        for record in evaluated
        if record["partition"] == "synthetic_negative_development"
    ]
    negative_margins = [
        float(record["best_verifier"]["margin"])
        for record in synthetic
        if isinstance(record.get("best_verifier"), dict)
    ]
    maximum_negative_margin = max(negative_margins, default=-math.inf)
    threshold = (
        float(np.nextafter(maximum_negative_margin, math.inf))
        if negative_margins
        else 0.5
    )
    for record in evaluated:
        best = record.get("best_verifier")
        record["detected"] = bool(
            record.get("stage1_proposed")
            and isinstance(best, dict)
            and float(best["margin"]) >= threshold
        )
    human = [
        record for record in evaluated if record["partition"] == "human_development"
    ]
    positive = [record for record in human if record["label"] == "positive"]
    hard_negative = [record for record in human if record["label"] == "hard_negative"]
    false_synthetic = sum(bool(record["detected"]) for record in synthetic)
    false_human = sum(bool(record["detected"]) for record in hard_negative)
    report: dict[str, object] = {
        "schema": "baxy.phoneme-teacher-category-oracle-development.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_lossless_teacher_head_projection_before_student_training",
        "sources": {
            "teacher_directory": teacher_directory.as_posix(),
            "teacher_model_sha256": sha256(teacher_directory / "pytorch_model.bin"),
            "synthetic_directory": synthetic_directory.as_posix(),
            "synthetic_negative_report": synthetic_negative_report_path.as_posix(),
            "synthetic_negative_report_sha256": sha256(synthetic_negative_report_path),
            "human_teacher_report": human_teacher_report_path.as_posix(),
            "human_teacher_report_sha256": sha256(human_teacher_report_path),
            "human_corpus_manifest": corpus_path.as_posix(),
            "human_corpus_manifest_sha256": sha256(corpus_path),
        },
        "student_head": {
            "category_names": list(CATEGORY_NAMES),
            "category_count": len(CATEGORY_NAMES),
            "teacher_ids": category_ids,
            "target_category_sequences": [list(value) for value in TARGET_IDS],
            "confusable_category_sequences": [list(value) for value in CONFUSABLE_IDS],
            "context_frames": CONTEXT_FRAMES,
            "samples_per_frame": SAMPLES_PER_TEACHER_FRAME,
            "compression": "maximum_teacher_logit_per_category_then_softmax",
        },
        "operating_point": {
            "selection": "nextafter_maximum_scored_stage1_synthetic_negative_margin",
            "threshold": threshold,
            "maximum_negative_margin": (
                maximum_negative_margin if negative_margins else None
            ),
        },
        "metrics": {
            "synthetic_negative_stage1_proposals": len(synthetic),
            "synthetic_negative_scored_locators": len(negative_margins),
            "synthetic_negative_false_accepts": false_synthetic,
            "human_positive_accepted": sum(bool(record["detected"]) for record in positive),
            "human_positive_total": len(positive),
            "human_hard_negative_false_accepts": false_human,
            "human_hard_negative_total": len(hard_negative),
            "development_gate_passed": (
                false_synthetic == 0
                and len(positive) > 0
                and all(bool(record["detected"]) for record in positive)
                and false_human == 0
            ),
        },
        "records": evaluated,
        "runtime": {
            "device": device,
            "batch_size": batch_size,
            "model_load_seconds": load_seconds,
            "inference_seconds": inference_seconds,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "espeak": espeak,
        },
        "candidate_development_use": True,
        "candidate_frozen": False,
        "product_operating_point": False,
        "blind_human_partition_accessed": False,
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
    parser.add_argument("--teacher-dir", type=Path, required=True)
    parser.add_argument("--synthetic-dir", type=Path, required=True)
    parser.add_argument("--synthetic-negative-report", type=Path, required=True)
    parser.add_argument("--human-teacher-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        teacher_directory=args.teacher_dir,
        synthetic_directory=args.synthetic_dir,
        synthetic_negative_report_path=args.synthetic_negative_report,
        human_teacher_report_path=args.human_teacher_report,
        output_path=args.output,
        batch_size=args.batch_size,
        device=args.device,
    )
    print(json.dumps({"metrics": report["metrics"], "operating_point": report["operating_point"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
