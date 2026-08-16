"""Evaluate causal two-second stage-two windows after a LiveKit proposal."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluate_phoneme_teacher_category_oracle_v2 import (  # noqa: E402
    compress_category_logits,
    search_anchored_category_probabilities,
    search_category_probabilities,
    score_category_probabilities,
)
from extract_mdtc_ctc_fbank_features import read_wav  # noqa: E402
from phoneme_student_vocabulary_v2 import resolve_category_ids  # noqa: E402
from train_mdtc_livekit_verifier_student import read_json, sha256  # noqa: E402


SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 32_000


def proposal_window(
    audio: np.ndarray,
    *,
    proposal_end_seconds: float,
    postroll_seconds: float,
    window_samples: int = WINDOW_SAMPLES,
) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if (
        not np.isfinite(values).all()
        or not np.isfinite(proposal_end_seconds)
        or not np.isfinite(postroll_seconds)
        or proposal_end_seconds < 0.0
        or postroll_seconds < 0.0
        or window_samples <= 0
    ):
        raise ValueError("stage2_window_inputs_invalid")
    padded = np.concatenate(
        [
            np.zeros(window_samples, dtype=np.float32),
            values,
            np.zeros(window_samples * 2, dtype=np.float32),
        ]
    )
    start = round((proposal_end_seconds + postroll_seconds) * SAMPLE_RATE)
    end = start + window_samples
    if end > len(padded):
        raise ValueError("stage2_window_postroll_out_of_range")
    return np.ascontiguousarray(padded[start:end])


def stage1_proposal(record: dict[str, object]) -> tuple[dict[str, object] | None, str | None]:
    broad = record.get("lexical_acoustic_corroboration")
    if isinstance(broad, dict):
        return broad, "livekit_broad_threshold"
    primary = record.get("livekit_proposal")
    if isinstance(primary, dict):
        return primary, "livekit_primary_threshold"
    return None, None


def summarize(clips: list[dict[str, object]]) -> dict[str, object]:
    positive = [clip for clip in clips if clip["label"] == "positive"]
    negative = [clip for clip in clips if clip["label"] == "hard_negative"]
    accepted = sum(bool(clip["detected"]) for clip in positive)
    false_accepts = sum(bool(clip["detected"]) for clip in negative)
    return {
        "positive_accepted": accepted,
        "positive_total": len(positive),
        "hard_negative_false_accepts": false_accepts,
        "hard_negative_total": len(negative),
        "gate_passed": accepted == len(positive) and false_accepts == 0,
        "clips": clips,
    }


def run(
    *,
    teacher_directory: Path,
    corpus_manifest_path: Path,
    teacher_report_path: Path,
    output_path: Path,
    postroll_values: tuple[float, ...],
    batch_size: int,
    device: str,
    window_samples: int = WINDOW_SAMPLES,
    locator_mode: str = "exact",
    window_source: str = "proposal",
) -> dict[str, object]:
    teacher_directory = teacher_directory.resolve(strict=True)
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    teacher_report_path = teacher_report_path.resolve(strict=True)
    output_path = output_path.resolve()
    if (
        output_path.exists()
        or batch_size <= 0
        or device not in {"cpu", "cuda"}
        or not postroll_values
        or any(not np.isfinite(value) or value < 0.0 for value in postroll_values)
        or window_samples not in {WINDOW_SAMPLES, 48_000, 64_000}
        or locator_mode not in {"exact", "scan", "anchor"}
        or window_source not in {"proposal", "full_clip"}
    ):
        raise ValueError("stage2_window_schedule_invalid")
    corpus_manifest = read_json(corpus_manifest_path)
    teacher_report = read_json(teacher_report_path)
    if (
        corpus_manifest.get("blind_partition_was_not_scored") is not True
        or teacher_report.get("blind_human_partition_accessed") is not False
    ):
        raise ValueError("stage2_window_blind_boundary_invalid")
    records = [
        record
        for record in corpus_manifest.get("records", [])
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    source_records = {
        str(record.get("output_relative_path")): record
        for record in teacher_report.get("records", [])
        if isinstance(record, dict)
    }
    if len(records) != 18 or set(source_records) != {
        str(record["output_relative_path"]) for record in records
    }:
        raise ValueError("stage2_window_development_records_invalid")

    import torch
    import transformers
    from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("stage2_window_cuda_required")
    extractor = Wav2Vec2FeatureExtractor.from_pretrained(
        teacher_directory, local_files_only=True
    )
    model = Wav2Vec2ForCTC.from_pretrained(
        teacher_directory, local_files_only=True
    ).eval().to(device)
    vocabulary = read_json(teacher_directory / "vocab.json")
    model_config = read_json(teacher_directory / "config.json")
    category_ids = resolve_category_ids(vocabulary, int(model_config["pad_token_id"]))
    corpus_directory = corpus_manifest_path.parent
    audios = {
        str(record["output_relative_path"]): read_wav(
            corpus_directory / str(record["output_relative_path"])
        )
        for record in records
    }

    started = time.perf_counter()
    results: dict[str, object] = {}
    for postroll in postroll_values:
        windows = []
        proposals = []
        for record in records:
            relative_path = str(record["output_relative_path"])
            proposal, proposal_source = stage1_proposal(source_records[relative_path])
            proposals.append((proposal, proposal_source))
            proposal_end = float(proposal["window_end_seconds"]) if proposal else 0.0
            if window_source == "full_clip":
                if len(audios[relative_path]) != window_samples:
                    raise ValueError(f"stage2_full_clip_length_invalid:{relative_path}")
                windows.append(np.ascontiguousarray(audios[relative_path]))
            else:
                windows.append(
                    proposal_window(
                        audios[relative_path],
                        proposal_end_seconds=proposal_end,
                        postroll_seconds=postroll,
                        window_samples=window_samples,
                    )
                )
        clips = []
        for start in range(0, len(windows), batch_size):
            prepared = extractor(
                windows[start : start + batch_size],
                sampling_rate=SAMPLE_RATE,
                return_tensors="pt",
                padding=True,
            )
            with torch.inference_mode():
                logits = model(
                    input_values=prepared.input_values.to(device)
                ).logits
                categories = compress_category_logits(
                    torch, logits, category_ids
                ).cpu().numpy()
            for offset, probabilities in enumerate(categories):
                record = records[start + offset]
                relative_path = str(record["output_relative_path"])
                if locator_mode == "exact":
                    scored = score_category_probabilities(probabilities)
                elif locator_mode == "anchor":
                    scored = search_anchored_category_probabilities(probabilities)
                else:
                    scored = search_category_probabilities(probabilities)
                best = scored.get("best_verifier")
                margin = float(best["margin"]) if isinstance(best, dict) else None
                proposal, proposal_source = proposals[start + offset]
                clips.append(
                    {
                        "relative_path": relative_path,
                        "label": record["label"],
                        "stage1_proposed": proposal is not None,
                        "proposal_source": proposal_source,
                        "proposal_end_seconds": (
                            proposal["window_end_seconds"] if proposal else None
                        ),
                        "margin": margin,
                        "detected": (
                            proposal is not None and margin is not None and margin >= 0.5
                        ),
                    }
                )
        results[f"{postroll:.3f}"] = summarize(clips)

    report = {
        "schema": "baxy.phoneme-teacher-stage2-windows.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "teacher_directory": teacher_directory.as_posix(),
            "teacher_model_sha256": sha256(teacher_directory / "pytorch_model.bin"),
            "corpus_manifest": corpus_manifest_path.as_posix(),
            "corpus_manifest_sha256": sha256(corpus_manifest_path),
            "teacher_report": teacher_report_path.as_posix(),
            "teacher_report_sha256": sha256(teacher_report_path),
        },
        "contract": {
            "sample_rate": SAMPLE_RATE,
            "window_samples": window_samples,
            "decision_margin_gte": 0.5,
            "window_source": window_source,
            "locator": (
                "category_greedy_exact_target_only"
                if locator_mode == "exact"
                else (
                    "category_qbt_greedy_boundary_anchors"
                    if locator_mode == "anchor"
                    else "category_qbt_span_search"
                )
            ),
        },
        "runtime": {
            "device": device,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "evaluation_seconds": time.perf_counter() - started,
        },
        "postroll_seconds": results,
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


def parse_postrolls(value: str) -> tuple[float, ...]:
    try:
        values = tuple(float(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as error:
        raise argparse.ArgumentTypeError("postrolls must be comma-separated numbers") from error
    if not values or any(not np.isfinite(item) or item < 0.0 for item in values):
        raise argparse.ArgumentTypeError("postrolls must be finite and non-negative")
    return values


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--teacher-dir", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--teacher-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--postrolls", type=parse_postrolls, default=parse_postrolls("0,.25,.5,.75,1,1.25")
    )
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--window-seconds", type=int, choices=(2, 3, 4), default=2)
    parser.add_argument(
        "--locator", choices=("exact", "anchor", "scan"), default="exact"
    )
    parser.add_argument(
        "--window-source", choices=("proposal", "full_clip"), default="proposal"
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = run(
        teacher_directory=arguments.teacher_dir,
        corpus_manifest_path=arguments.corpus_manifest,
        teacher_report_path=arguments.teacher_report,
        output_path=arguments.output,
        postroll_values=arguments.postrolls,
        batch_size=arguments.batch_size,
        device=arguments.device,
        window_samples=arguments.window_seconds * SAMPLE_RATE,
        locator_mode=arguments.locator,
        window_source=arguments.window_source,
    )
    print(
        json.dumps(
            {
                key: {
                    "positive": value["positive_accepted"],
                    "false_accepts": value["hard_negative_false_accepts"],
                    "gate": value["gate_passed"],
                }
                for key, value in report["postroll_seconds"].items()
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
