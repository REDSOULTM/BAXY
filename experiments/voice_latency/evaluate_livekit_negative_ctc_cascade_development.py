"""Evaluate the CTC cascade on LiveKit's augmented negative development set.

This diagnostic reuses a split seen during candidate development.  It can
expose mechanisms and regressions, but it cannot certify a false-activation
rate.  A later frozen raw-audio holdout with at least 30 hours owns that claim.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import wave

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctc_wake_verifier import (  # noqa: E402
    CONFUSABLE_SEQUENCES,
    TARGET_SEQUENCES,
    collapse_ctc_path,
    encode_sequences,
    exact_sequence_spans,
    is_exact_lexical_target_proposal,
    multiword_non_target_overlap,
    score_verifier_span,
)


SAMPLE_RATE = 16_000
_AUGMENTED_NAME = re.compile(r"^clip_\d{6}_r\d+\.wav$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def augmented_wavs(directory: Path) -> list[Path]:
    paths = sorted(
        path
        for path in directory.glob("*.wav")
        if path.is_file() and _AUGMENTED_NAME.fullmatch(path.name)
    )
    if not paths:
        raise ValueError("livekit_negative_augmented_wavs_empty")
    return paths


def read_wav(path: Path) -> tuple[np.ndarray, float]:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError(f"wav_contract_mismatch:{path}:{contract}")
        frames = source.getnframes()
        payload = source.readframes(frames)
    return (
        np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0,
        frames / SAMPLE_RATE,
    )


def validate_parakeet_audit(
    audit: dict[str, object],
    *,
    feature_sha256: str,
    paths: list[Path],
) -> dict[str, dict[str, object]]:
    if audit.get("schema") != "baxy.livekit-negative-parakeet-development.v1":
        raise ValueError("unsupported_negative_parakeet_audit_schema")
    if audit.get("blind_human_partition_accessed") is not False:
        raise ValueError("negative_cascade_blind_boundary_is_not_clean")
    if audit.get("independent_holdout") is not False:
        raise ValueError("negative_development_scope_mismatch")
    if audit.get("feature_sha256") != feature_sha256:
        raise ValueError("negative_cascade_feature_hash_mismatch")
    records = audit.get("records")
    if not isinstance(records, list):
        raise ValueError("negative_parakeet_records_missing")
    by_name = {
        str(record.get("file")): record
        for record in records
        if isinstance(record, dict)
    }
    if set(by_name) != {path.name for path in paths}:
        raise ValueError("negative_parakeet_record_set_mismatch")
    return by_name


def predict_scores(model_path: Path, features: np.ndarray) -> tuple[np.ndarray, str]:
    import onnxruntime as ort

    session = ort.InferenceSession(
        str(model_path), providers=["CPUExecutionProvider"]
    )
    input_name = session.get_inputs()[0].name
    chunks = []
    for start in range(0, len(features), 512):
        chunks.append(
            np.asarray(
                session.run(None, {input_name: features[start : start + 512]})[0]
            ).reshape(-1)
        )
    return np.concatenate(chunks).astype(np.float64), ort.__version__


def evaluate(
    *,
    wav_directory: Path,
    feature_path: Path,
    parakeet_audit_path: Path,
    livekit_model_path: Path,
    livekit_proposal_threshold: float,
    lexical_corroboration_threshold: float,
    phoneme_model_directory: Path,
    verifier_margin: float,
    context_before_seconds: float,
    context_after_seconds: float,
    device: str,
    batch_size: int,
    output_path: Path,
) -> dict[str, object]:
    if not 0.0 < livekit_proposal_threshold < 1.0:
        raise ValueError("livekit_proposal_threshold_invalid")
    if not 0.0 < lexical_corroboration_threshold <= livekit_proposal_threshold:
        raise ValueError("lexical_corroboration_threshold_invalid")
    if not math.isfinite(verifier_margin):
        raise ValueError("ctc_verifier_margin_invalid")
    if context_before_seconds < 0.0 or context_after_seconds < 0.0:
        raise ValueError("ctc_verifier_context_invalid")
    if device not in {"cpu", "cuda"} or batch_size <= 0:
        raise ValueError("ctc_runtime_configuration_invalid")
    wav_directory = wav_directory.resolve(strict=True)
    feature_path = feature_path.resolve(strict=True)
    parakeet_audit_path = parakeet_audit_path.resolve(strict=True)
    livekit_model_path = livekit_model_path.resolve(strict=True)
    phoneme_model_directory = phoneme_model_directory.resolve(strict=True)
    paths = augmented_wavs(wav_directory)
    features = np.load(feature_path)
    if features.ndim != 3 or features.shape[1:] != (16, 96):
        raise ValueError(f"negative_feature_shape_invalid:{features.shape}")
    if len(features) != len(paths):
        raise ValueError("negative_feature_wav_count_mismatch")
    feature_hash = sha256(feature_path)
    parakeet = read_json(parakeet_audit_path)
    parakeet_by_name = validate_parakeet_audit(
        parakeet, feature_sha256=feature_hash, paths=paths
    )
    livekit_scores, onnxruntime_version = predict_scores(
        livekit_model_path, features
    )
    stage1_indices = [
        index
        for index, path in enumerate(paths)
        if livekit_scores[index] >= livekit_proposal_threshold
        or (
            livekit_scores[index] >= lexical_corroboration_threshold
            and bool(parakeet_by_name[path.name].get("lexical_proposals"))
        )
    ]

    from audit_voxcpm2_gguf_pilot import configure_espeak_backend

    espeak = configure_espeak_backend()
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")
    load_started = time.perf_counter()
    processor = Wav2Vec2Processor.from_pretrained(
        phoneme_model_directory, local_files_only=True
    )
    phoneme_model = Wav2Vec2ForCTC.from_pretrained(
        phoneme_model_directory, local_files_only=True
    ).eval().to(device)
    model_load_seconds = time.perf_counter() - load_started
    vocab = processor.tokenizer.get_vocab()
    target_ids = encode_sequences(vocab, TARGET_SEQUENCES)
    confusable_ids = encode_sequences(vocab, CONFUSABLE_SEQUENCES)
    blank_id = int(processor.tokenizer.pad_token_id)
    samples_per_frame = int(phoneme_model.config.inputs_to_logits_ratio)
    context_before_frames = round(
        context_before_seconds * SAMPLE_RATE / samples_per_frame
    )
    context_after_frames = round(
        context_after_seconds * SAMPLE_RATE / samples_per_frame
    )
    stage2_by_index: dict[int, dict[str, object]] = {}
    inference_seconds = 0.0
    for batch_start in range(0, len(stage1_indices), batch_size):
        indices = stage1_indices[batch_start : batch_start + batch_size]
        audios = []
        for index in indices:
            audio, _ = read_wav(paths[index])
            audios.append(audio)
        prepared = processor(
            audios,
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
            padding=True,
        )
        input_lengths = torch.tensor(
            [len(audio) for audio in audios], dtype=torch.long, device=device
        )
        started = time.perf_counter()
        with torch.inference_mode():
            logits = phoneme_model(
                input_values=prepared.input_values.to(device)
            ).logits.float().cpu()
        inference_seconds += time.perf_counter() - started
        output_lengths = phoneme_model._get_feat_extract_output_lengths(
            input_lengths
        ).cpu().tolist()
        log_probabilities = torch.log_softmax(logits, dim=-1).numpy()
        predictions = torch.argmax(logits, dim=-1).numpy()
        for local_index, global_index in enumerate(indices):
            length = int(output_lengths[local_index])
            log_probs = log_probabilities[local_index, :length]
            collapsed = collapse_ctc_path(
                predictions[local_index, :length], blank_id
            )
            greedy_spans = exact_sequence_spans(collapsed, target_ids)
            parakeet_record = parakeet_by_name[paths[global_index].name]
            words = parakeet_record.get("lexical_words")
            proposals = parakeet_record.get("lexical_proposals")
            if not isinstance(words, list) or not isinstance(proposals, list):
                raise ValueError("negative_parakeet_lexical_evidence_invalid")
            locators: list[dict[str, object]] = [
                {
                    "source": "ctc_greedy_exact_target",
                    "locator_start_frame": start,
                    "locator_end_frame": end,
                    "greedy_sequence": list(sequence),
                }
                for start, end, sequence in greedy_spans
            ]
            for proposal in proposals:
                if not isinstance(proposal, dict):
                    raise ValueError("negative_lexical_proposal_invalid")
                if not is_exact_lexical_target_proposal(str(proposal["surface"])):
                    continue
                locators.append(
                    {
                        "source": "parakeet_lexical_proposal",
                        "surface": proposal["surface"],
                        "locator_start_frame": math.floor(
                            float(proposal["start_seconds"])
                            * SAMPLE_RATE
                            / samples_per_frame
                        ),
                        "locator_end_frame": math.ceil(
                            float(proposal["end_seconds"])
                            * SAMPLE_RATE
                            / samples_per_frame
                        ),
                    }
                )
            scored = []
            for locator in locators:
                value = score_verifier_span(
                    log_probs,
                    start_frame=int(locator["locator_start_frame"]),
                    end_frame=int(locator["locator_end_frame"]),
                    target_sequences=target_ids,
                    confusable_sequences=confusable_ids,
                    blank_id=blank_id,
                    context_before_frames=context_before_frames,
                    context_after_frames=context_after_frames,
                )
                locator_start_seconds = (
                    int(locator["locator_start_frame"])
                    * samples_per_frame
                    / SAMPLE_RATE
                )
                locator_end_seconds = (
                    int(locator["locator_end_frame"])
                    * samples_per_frame
                    / SAMPLE_RATE
                )
                veto = multiword_non_target_overlap(
                    words,
                    start_seconds=locator_start_seconds,
                    end_seconds=locator_end_seconds,
                )
                scored.append(
                    {
                        **locator,
                        **value,
                        "locator_start_seconds": locator_start_seconds,
                        "locator_end_seconds": locator_end_seconds,
                        "multiword_non_target_veto": veto,
                    }
                )
            eligible = [
                value
                for value in scored
                if not bool(value["multiword_non_target_veto"])
            ]
            best = (
                max(eligible, key=lambda value: float(value["margin"]))
                if eligible
                else None
            )
            stage2_by_index[global_index] = {
                "ctc_greedy_target_span_count": len(greedy_spans),
                "locators": scored,
                "best_verifier": best,
                "detected": bool(
                    best is not None
                    and float(best["margin"]) >= verifier_margin
                ),
            }

    records: list[dict[str, object]] = []
    total_audio_seconds = 0.0
    for index, path in enumerate(paths):
        _, duration = read_wav(path)
        total_audio_seconds += duration
        parakeet_record = parakeet_by_name[path.name]
        stage2 = stage2_by_index.get(index)
        records.append(
            {
                "file": path.name,
                "wav_sha256": parakeet_record["wav_sha256"],
                "duration_seconds": duration,
                "livekit_score": float(livekit_scores[index]),
                "livekit_proposed": bool(
                    livekit_scores[index] >= livekit_proposal_threshold
                ),
                "parakeet_transcript": parakeet_record.get("transcript", ""),
                "parakeet_lexical_proposals": parakeet_record.get(
                    "lexical_proposals", []
                ),
                "stage1_proposed": stage2 is not None,
                "stage2": stage2,
                "detected": bool(stage2 and stage2["detected"]),
            }
        )
    false_activations = sum(bool(record["detected"]) for record in records)
    exposure_hours = total_audio_seconds / 3600.0
    point_fpph = false_activations / exposure_hours
    zero_event_upper_95 = (
        -math.log(0.05) / exposure_hours if false_activations == 0 else None
    )
    weights = phoneme_model_directory / "pytorch_model.bin"
    report: dict[str, object] = {
        "schema": "baxy.livekit-negative-ctc-cascade-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "candidate_development_negative_split",
        "independent_holdout": False,
        "far_claim_supported": False,
        "reason_far_claim_not_supported": (
            "split_reused_during_candidate_development_and_exposure_below_30_hours"
        ),
        "wav_directory": wav_directory.as_posix(),
        "feature_file": feature_path.as_posix(),
        "feature_sha256": feature_hash,
        "parakeet_audit": parakeet_audit_path.as_posix(),
        "parakeet_audit_sha256": sha256(parakeet_audit_path),
        "livekit": {
            "model": livekit_model_path.as_posix(),
            "model_sha256": sha256(livekit_model_path),
            "proposal_threshold": livekit_proposal_threshold,
            "lexical_corroboration_threshold": lexical_corroboration_threshold,
            "product_operating_point": False,
        },
        "ctc_verifier": {
            "model_directory": phoneme_model_directory.as_posix(),
            "weights_sha256": sha256(weights),
            "margin_threshold": verifier_margin,
            "context_before_seconds": context_before_seconds,
            "context_after_seconds": context_after_seconds,
            "device": device,
            "batch_size": batch_size,
            "model_load_seconds": round(model_load_seconds, 6),
            "inference_seconds": round(inference_seconds, 6),
        },
        "metrics": {
            "clips": len(records),
            "audio_seconds": round(total_audio_seconds, 6),
            "exposure_hours": exposure_hours,
            "livekit_proposals": sum(
                bool(record["livekit_proposed"]) for record in records
            ),
            "parakeet_lexical_proposals": sum(
                bool(record["parakeet_lexical_proposals"]) for record in records
            ),
            "stage1_union_proposals": len(stage1_indices),
            "false_activations": false_activations,
            "point_false_activations_per_hour": point_fpph,
            "zero_event_upper_95_fpph": zero_event_upper_95,
        },
        "runtime": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "onnxruntime": onnxruntime_version,
            "espeak": espeak,
        },
        "records": records,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav-dir", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--parakeet-audit", type=Path, required=True)
    parser.add_argument("--livekit-model", type=Path, required=True)
    parser.add_argument("--livekit-proposal-threshold", type=float, default=0.05)
    parser.add_argument(
        "--lexical-corroboration-threshold", type=float, default=0.02
    )
    parser.add_argument("--phoneme-model-dir", type=Path, required=True)
    parser.add_argument("--verifier-margin", type=float, default=0.0)
    parser.add_argument("--context-before-seconds", type=float, default=0.2)
    parser.add_argument("--context-after-seconds", type=float, default=0.2)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        wav_directory=args.wav_dir,
        feature_path=args.features,
        parakeet_audit_path=args.parakeet_audit,
        livekit_model_path=args.livekit_model,
        livekit_proposal_threshold=args.livekit_proposal_threshold,
        lexical_corroboration_threshold=args.lexical_corroboration_threshold,
        phoneme_model_directory=args.phoneme_model_dir,
        verifier_margin=args.verifier_margin,
        context_before_seconds=args.context_before_seconds,
        context_after_seconds=args.context_after_seconds,
        device=args.device,
        batch_size=args.batch_size,
        output_path=args.output,
    )
    print(json.dumps({"output": args.output.resolve().as_posix(), "metrics": report["metrics"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
