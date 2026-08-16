"""Evaluate a LiveKit/Parakeet proposal plus phoneme-CTC verifier cascade.

Only the human CC-BY development partition is accepted.  The script cannot
score the blind partition and cannot create a product freeze.  Its purpose is
to decide whether the architecture deserves a raw-negative campaign.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
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
    lexical_word_spans,
    multiword_non_target_overlap,
    score_verifier_span,
)


SAMPLE_RATE = 16_000
LIVEKIT_WINDOW_SECONDS = 2.0
LIVEKIT_STEP_SECONDS = 0.25


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


def validate_inputs(
    corpus: dict[str, object],
    parakeet: dict[str, object],
    *,
    corpus_manifest_sha256: str,
) -> list[dict[str, object]]:
    if corpus.get("schema") != "baxy.ccby-wake-holdout-corpus.v1":
        raise ValueError("unsupported_ccby_corpus_schema")
    if parakeet.get("schema") != "baxy.ccby-wake-parakeet-development-audit.v1":
        raise ValueError("unsupported_parakeet_audit_schema")
    if parakeet.get("partition") != "development":
        raise ValueError("cascade_requires_development_partition")
    if parakeet.get("blind_human_partition_accessed") is not False:
        raise ValueError("cascade_blind_boundary_is_not_clean")
    if str(parakeet.get("corpus_manifest_sha256", "")) != corpus_manifest_sha256:
        raise ValueError("cascade_corpus_manifest_hash_mismatch")
    raw_records = corpus.get("records")
    if not isinstance(raw_records, list):
        raise ValueError("ccby_corpus_records_missing")
    records = [
        record
        for record in raw_records
        if isinstance(record, dict) and record.get("partition") == "development"
    ]
    parakeet_records = parakeet.get("records")
    if not isinstance(parakeet_records, list):
        raise ValueError("parakeet_audit_records_missing")
    expected_paths = {str(record["output_relative_path"]) for record in records}
    actual_paths = {
        str(record.get("output_relative_path"))
        for record in parakeet_records
        if isinstance(record, dict)
    }
    if actual_paths != expected_paths:
        raise ValueError("parakeet_audit_record_set_mismatch")
    return records


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        contract = (
            source.getnchannels(),
            source.getsampwidth(),
            source.getframerate(),
        )
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError(f"wav_contract_mismatch:{path}:{contract}")
        payload = source.readframes(source.getnframes())
    return np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0


def first_livekit_proposal(
    model: object,
    audio: np.ndarray,
    threshold: float,
) -> dict[str, float | int] | None:
    if not 0.0 < threshold < 1.0:
        raise ValueError("livekit_proposal_threshold_invalid")
    window_samples = round(LIVEKIT_WINDOW_SECONDS * SAMPLE_RATE)
    step_samples = round(LIVEKIT_STEP_SECONDS * SAMPLE_RATE)
    padded = np.concatenate(
        [
            np.zeros(window_samples, np.float32),
            np.asarray(audio, dtype=np.float32),
            np.zeros(window_samples, np.float32),
        ]
    )
    windows = 0
    for end in range(window_samples, len(padded) + 1, step_samples):
        scores = model.predict(padded[end - window_samples : end])
        if len(scores) != 1:
            raise ValueError("livekit_expected_one_classifier")
        score = float(next(iter(scores.values())))
        windows += 1
        if score >= threshold:
            return {
                "score": score,
                "window_end_seconds": (end - window_samples) / SAMPLE_RATE,
                "windows_scored": windows,
            }
    return None


def summarize(records: list[dict[str, object]]) -> dict[str, object]:
    if not records:
        raise ValueError("cascade_records_empty")
    positive = [record for record in records if record["label"] == "positive"]
    negative = [
        record for record in records if record["label"] == "hard_negative"
    ]
    if not positive or not negative:
        raise ValueError("cascade_requires_both_labels")
    stage1_positive = sum(bool(record["stage1_proposed"]) for record in positive)
    final_positive = sum(bool(record["detected"]) for record in positive)
    final_false_positive = sum(bool(record["detected"]) for record in negative)
    return {
        "positive_clips": len(positive),
        "hard_negative_clips": len(negative),
        "stage1_positive_proposals": stage1_positive,
        "stage1_recall": stage1_positive / len(positive),
        "true_positive": final_positive,
        "false_negative": len(positive) - final_positive,
        "recall": final_positive / len(positive),
        "false_positive": final_false_positive,
        "true_negative": len(negative) - final_false_positive,
        "hard_negative_rejection": 1.0 - final_false_positive / len(negative),
        "development_gate_passed": (
            stage1_positive == len(positive)
            and final_positive == len(positive)
            and final_false_positive == 0
        ),
    }


def evaluate(
    *,
    corpus_manifest_path: Path,
    parakeet_audit_path: Path,
    livekit_model_path: Path,
    livekit_proposal_threshold: float,
    lexical_corroboration_threshold: float,
    phoneme_model_directory: Path,
    verifier_margin: float,
    context_before_seconds: float,
    context_after_seconds: float,
    device: str,
    output_path: Path,
) -> dict[str, object]:
    if device not in {"cpu", "cuda"}:
        raise ValueError("ctc_device_invalid")
    if not 0.0 < lexical_corroboration_threshold <= livekit_proposal_threshold:
        raise ValueError("lexical_corroboration_threshold_invalid")
    if not math.isfinite(verifier_margin):
        raise ValueError("ctc_verifier_margin_invalid")
    if context_before_seconds < 0.0 or context_after_seconds < 0.0:
        raise ValueError("ctc_verifier_context_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    parakeet_audit_path = parakeet_audit_path.resolve(strict=True)
    livekit_model_path = livekit_model_path.resolve(strict=True)
    phoneme_model_directory = phoneme_model_directory.resolve(strict=True)
    corpus_hash = sha256(corpus_manifest_path)
    corpus = read_json(corpus_manifest_path)
    parakeet = read_json(parakeet_audit_path)
    records = validate_inputs(
        corpus, parakeet, corpus_manifest_sha256=corpus_hash
    )
    parakeet_by_path = {
        str(record["output_relative_path"]): record
        for record in parakeet["records"]
        if isinstance(record, dict)
    }
    corpus_root = corpus_manifest_path.parent
    audios: list[np.ndarray] = []
    for record in records:
        relative_path = str(record["output_relative_path"])
        path = corpus_root / relative_path
        expected_hash = str(record.get("wav", {}).get("sha256", ""))
        if sha256(path) != expected_hash:
            raise ValueError(f"ccby_wav_hash_mismatch:{relative_path}")
        audios.append(read_wav(path))

    from livekit.wakeword import WakeWordModel

    livekit = WakeWordModel(models=[livekit_model_path])
    livekit_proposals = [
        first_livekit_proposal(livekit, audio, livekit_proposal_threshold)
        for audio in audios
    ]
    lexical_corroborations = [
        first_livekit_proposal(livekit, audio, lexical_corroboration_threshold)
        if parakeet_by_path[str(record["output_relative_path"])].get(
            "lexical_proposals"
        )
        else None
        for record, audio in zip(records, audios, strict=True)
    ]

    # Transformers' phoneme tokenizer initializes eSpeak even though this
    # runner only decodes acoustic logits.  Reuse the pinned wheel backend.
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
    prepared = processor(
        audios,
        sampling_rate=SAMPLE_RATE,
        return_tensors="pt",
        padding=True,
    )
    input_lengths = torch.tensor(
        [len(audio) for audio in audios], dtype=torch.long, device=device
    )
    inference_started = time.perf_counter()
    with torch.inference_mode():
        logits = phoneme_model(
            input_values=prepared.input_values.to(device)
        ).logits.float().cpu()
    inference_seconds = time.perf_counter() - inference_started
    output_lengths = phoneme_model._get_feat_extract_output_lengths(
        input_lengths
    ).cpu().tolist()
    log_probabilities = torch.log_softmax(logits, dim=-1).numpy()
    predicted = torch.argmax(logits, dim=-1).numpy()
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

    evaluated: list[dict[str, object]] = []
    for index, record in enumerate(records):
        relative_path = str(record["output_relative_path"])
        parakeet_record = parakeet_by_path[relative_path]
        lexical = parakeet_record.get("lexical_proposals")
        if not isinstance(lexical, list):
            raise ValueError(f"parakeet_lexical_proposals_invalid:{relative_path}")
        livekit_proposal = livekit_proposals[index]
        lexical_corroboration = lexical_corroborations[index]
        lexical_words = lexical_word_spans(
            [str(value) for value in parakeet_record.get("tokens", [])],
            [float(value) for value in parakeet_record.get("timestamps", [])],
        )
        stage1_proposed = (
            livekit_proposal is not None
            or (bool(lexical) and lexical_corroboration is not None)
        )
        length = int(output_lengths[index])
        clip_log_probs = log_probabilities[index, :length]
        collapsed = collapse_ctc_path(predicted[index, :length], blank_id)
        greedy_spans = exact_sequence_spans(collapsed, target_ids)
        locators: list[dict[str, object]] = [
            {
                "source": "ctc_greedy_exact_target",
                "locator_start_frame": start,
                "locator_end_frame": end,
                "greedy_sequence": list(sequence),
            }
            for start, end, sequence in greedy_spans
        ]
        for proposal in lexical:
            if not isinstance(proposal, dict):
                raise ValueError(f"parakeet_lexical_proposal_invalid:{relative_path}")
            if not is_exact_lexical_target_proposal(str(proposal["surface"])):
                continue
            start = math.floor(
                float(proposal["start_seconds"]) * SAMPLE_RATE / samples_per_frame
            )
            end = math.ceil(
                float(proposal["end_seconds"]) * SAMPLE_RATE / samples_per_frame
            )
            locators.append(
                {
                    "source": "parakeet_lexical_proposal",
                    "surface": proposal["surface"],
                    "locator_start_frame": start,
                    "locator_end_frame": end,
                }
            )

        scored_locators: list[dict[str, object]] = []
        if stage1_proposed:
            for locator in locators:
                scored = score_verifier_span(
                    clip_log_probs,
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
                lexical_veto = multiword_non_target_overlap(
                    lexical_words,
                    start_seconds=locator_start_seconds,
                    end_seconds=locator_end_seconds,
                )
                scored_locators.append(
                    {
                        **locator,
                        **scored,
                        "locator_start_seconds": locator_start_seconds,
                        "locator_end_seconds": locator_end_seconds,
                        "multiword_non_target_veto": lexical_veto,
                    }
                )
        eligible_locators = [
            locator
            for locator in scored_locators
            if not bool(locator["multiword_non_target_veto"])
        ]
        best = (
            max(eligible_locators, key=lambda value: float(value["margin"]))
            if eligible_locators
            else None
        )
        detected = bool(
            stage1_proposed
            and best is not None
            and float(best["margin"]) >= verifier_margin
        )
        evaluated.append(
            {
                "source_id": record["source_id"],
                "speaker_group": record["speaker_group"],
                "label": record["label"],
                "output_relative_path": relative_path,
                "livekit_proposal": livekit_proposal,
                "lexical_acoustic_corroboration": lexical_corroboration,
                "parakeet_transcript": parakeet_record.get("transcript", ""),
                "parakeet_lexical_proposals": lexical,
                "parakeet_lexical_words": list(lexical_words),
                "stage1_proposed": stage1_proposed,
                "ctc_greedy_target_span_count": len(greedy_spans),
                "verifier_locators": scored_locators,
                "best_verifier": best,
                "detected": detected,
                "correct": detected if record["label"] == "positive" else not detected,
            }
        )

    metrics = summarize(evaluated)
    weights = phoneme_model_directory / "pytorch_model.bin"
    report: dict[str, object] = {
        "schema": "baxy.ccby-wake-ctc-cascade-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "architecture": (
            "LiveKit_or_Parakeet_permissive_proposal_then_exact_CTC_target_vs_confusables"
        ),
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": corpus_hash,
        "preregistration_sha256": corpus.get("preregistration_sha256"),
        "parakeet_audit": parakeet_audit_path.as_posix(),
        "parakeet_audit_sha256": sha256(parakeet_audit_path),
        "livekit": {
            "model": livekit_model_path.as_posix(),
            "model_sha256": sha256(livekit_model_path),
            "proposal_threshold": livekit_proposal_threshold,
            "lexical_corroboration_threshold": lexical_corroboration_threshold,
            "product_operating_point": False,
            "window_seconds": LIVEKIT_WINDOW_SECONDS,
            "step_seconds": LIVEKIT_STEP_SECONDS,
        },
        "ctc_verifier": {
            "model_directory": phoneme_model_directory.as_posix(),
            "weights_sha256": sha256(weights),
            "target_sequences": [list(sequence) for sequence in TARGET_SEQUENCES],
            "confusable_sequences": [
                list(sequence) for sequence in CONFUSABLE_SEQUENCES
            ],
            "margin_threshold": verifier_margin,
            "context_before_seconds": context_before_seconds,
            "context_after_seconds": context_after_seconds,
            "device": device,
            "model_load_seconds": round(model_load_seconds, 6),
            "batch_inference_seconds": round(inference_seconds, 6),
            "samples_per_output_frame": samples_per_frame,
        },
        "runtime": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "espeak": espeak,
        },
        "metrics": metrics,
        "records": evaluated,
        "blind_human_partition_accessed": False,
        "candidate_frozen": False,
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
    parser.add_argument("--corpus-manifest", type=Path, required=True)
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
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        corpus_manifest_path=args.corpus_manifest,
        parakeet_audit_path=args.parakeet_audit,
        livekit_model_path=args.livekit_model,
        livekit_proposal_threshold=args.livekit_proposal_threshold,
        lexical_corroboration_threshold=args.lexical_corroboration_threshold,
        phoneme_model_directory=args.phoneme_model_dir,
        verifier_margin=args.verifier_margin,
        context_before_seconds=args.context_before_seconds,
        context_after_seconds=args.context_after_seconds,
        device=args.device,
        output_path=args.output,
    )
    sys.stdout.buffer.write(
        (
            json.dumps(
                {"output": args.output.resolve().as_posix(), "metrics": report["metrics"]},
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
