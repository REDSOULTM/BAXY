"""Evaluate the frozen wake cascade on raw LibriSpeech development audio.

This corpus is independent of the synthetic training material, but it is an
architecture-development set and is too short to certify the product FAR.
The human blind wake partition is never read by this runner.
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

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from audit_openslr_librispeech_retained_parakeet import decode_flac  # noqa: E402
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


def join_evidence(
    corpus: dict[str, object],
    scan: dict[str, object],
    parakeet: dict[str, object],
    *,
    corpus_sha256: str,
    scan_sha256: str,
    livekit_proposal_threshold: float,
    lexical_corroboration_threshold: float,
) -> list[dict[str, object]]:
    """Validate every identity boundary and attach retained ASR evidence."""
    if corpus.get("schema") != "baxy.openslr-librispeech-negative-development.v1":
        raise ValueError("unsupported_openslr_corpus_schema")
    if scan.get("schema") != "baxy.openslr-librispeech-livekit-development-scan.v1":
        raise ValueError("unsupported_openslr_livekit_scan_schema")
    if parakeet.get("schema") != "baxy.openslr-librispeech-parakeet-development.v1":
        raise ValueError("unsupported_openslr_parakeet_schema")
    if scan.get("corpus_manifest_sha256") != corpus_sha256:
        raise ValueError("openslr_cascade_scan_corpus_hash_mismatch")
    if parakeet.get("corpus_manifest_sha256") != corpus_sha256:
        raise ValueError("openslr_cascade_parakeet_corpus_hash_mismatch")
    if parakeet.get("livekit_scan_sha256") != scan_sha256:
        raise ValueError("openslr_cascade_parakeet_scan_hash_mismatch")
    if any(
        value.get("blind_human_partition_accessed") is not False
        for value in (scan, parakeet)
    ):
        raise ValueError("openslr_cascade_blind_boundary_is_not_clean")
    if not math.isclose(
        float(scan["proposal_threshold"]),
        livekit_proposal_threshold,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("openslr_cascade_proposal_threshold_mismatch")
    if not math.isclose(
        float(scan["retention_threshold"]),
        lexical_corroboration_threshold,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise ValueError("openslr_cascade_retention_threshold_mismatch")

    corpus_records = corpus.get("records")
    scan_records = scan.get("records")
    parakeet_records = parakeet.get("records")
    if not all(isinstance(value, list) for value in (corpus_records, scan_records, parakeet_records)):
        raise ValueError("openslr_cascade_records_missing")
    assert isinstance(corpus_records, list)
    assert isinstance(scan_records, list)
    assert isinstance(parakeet_records, list)
    if len(corpus_records) != len(scan_records):
        raise ValueError("openslr_cascade_scan_record_count_mismatch")
    parakeet_by_id = {
        str(record.get("utterance_id")): record
        for record in parakeet_records
        if isinstance(record, dict)
    }
    retained_ids = {
        str(record.get("utterance_id"))
        for record in scan_records
        if isinstance(record, dict)
        and float(record["max_score"]) >= lexical_corroboration_threshold
    }
    if (
        len(parakeet_by_id) != len(parakeet_records)
        or set(parakeet_by_id) != retained_ids
    ):
        raise ValueError("openslr_cascade_parakeet_record_set_mismatch")

    joined: list[dict[str, object]] = []
    for corpus_record, scan_record in zip(corpus_records, scan_records, strict=True):
        if not isinstance(corpus_record, dict) or not isinstance(scan_record, dict):
            raise ValueError("openslr_cascade_record_invalid")
        identity = (
            corpus_record.get("utterance_id"),
            corpus_record.get("relative_path"),
            corpus_record.get("sha256"),
        )
        scan_identity = (
            scan_record.get("utterance_id"),
            scan_record.get("relative_path"),
            scan_record.get("wav_sha256"),
        )
        if identity != scan_identity:
            raise ValueError("openslr_cascade_scan_identity_mismatch")
        score = float(scan_record["max_score"])
        expected_strong = score >= livekit_proposal_threshold
        if bool(scan_record.get("proposal")) != expected_strong:
            raise ValueError("openslr_cascade_scan_proposal_mismatch")
        asr = parakeet_by_id.get(str(identity[0]))
        if asr is not None and (
            asr.get("relative_path") != identity[1]
            or asr.get("wav_sha256") != identity[2]
        ):
            raise ValueError("openslr_cascade_parakeet_identity_mismatch")
        lexical = bool(asr and asr.get("lexical_proposals"))
        joined.append(
            {
                "corpus": corpus_record,
                "scan": scan_record,
                "parakeet": asr,
                "strong_proposal": expected_strong,
                "lexical_corroboration": lexical and score >= lexical_corroboration_threshold,
                "stage1_proposed": expected_strong or lexical,
            }
        )
    return joined


def evaluate(
    *,
    corpus_manifest_path: Path,
    livekit_scan_path: Path,
    parakeet_audit_path: Path,
    ffmpeg_path: Path,
    phoneme_model_directory: Path,
    livekit_proposal_threshold: float,
    lexical_corroboration_threshold: float,
    verifier_margin: float,
    context_before_seconds: float,
    context_after_seconds: float,
    device: str,
    batch_size: int,
    output_path: Path,
) -> dict[str, object]:
    if not 0.0 < lexical_corroboration_threshold <= livekit_proposal_threshold < 1.0:
        raise ValueError("openslr_cascade_livekit_thresholds_invalid")
    if not math.isfinite(verifier_margin):
        raise ValueError("openslr_cascade_verifier_margin_invalid")
    if context_before_seconds < 0.0 or context_after_seconds < 0.0:
        raise ValueError("openslr_cascade_context_invalid")
    if device not in {"cpu", "cuda"} or batch_size <= 0:
        raise ValueError("openslr_cascade_runtime_configuration_invalid")
    corpus_manifest_path = corpus_manifest_path.resolve(strict=True)
    livekit_scan_path = livekit_scan_path.resolve(strict=True)
    parakeet_audit_path = parakeet_audit_path.resolve(strict=True)
    ffmpeg_path = ffmpeg_path.resolve(strict=True)
    phoneme_model_directory = phoneme_model_directory.resolve(strict=True)
    corpus_hash = sha256(corpus_manifest_path)
    scan_hash = sha256(livekit_scan_path)
    corpus = read_json(corpus_manifest_path)
    scan = read_json(livekit_scan_path)
    parakeet = read_json(parakeet_audit_path)
    joined = join_evidence(
        corpus,
        scan,
        parakeet,
        corpus_sha256=corpus_hash,
        scan_sha256=scan_hash,
        livekit_proposal_threshold=livekit_proposal_threshold,
        lexical_corroboration_threshold=lexical_corroboration_threshold,
    )
    corpus_root = Path(str(corpus["corpus_root"])).resolve(strict=True)
    stage1_indices = [
        index for index, record in enumerate(joined) if bool(record["stage1_proposed"])
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
    model = Wav2Vec2ForCTC.from_pretrained(
        phoneme_model_directory, local_files_only=True
    ).eval().to(device)
    model_load_seconds = time.perf_counter() - load_started
    vocab = processor.tokenizer.get_vocab()
    target_ids = encode_sequences(vocab, TARGET_SEQUENCES)
    confusable_ids = encode_sequences(vocab, CONFUSABLE_SEQUENCES)
    blank_id = int(processor.tokenizer.pad_token_id)
    samples_per_frame = int(model.config.inputs_to_logits_ratio)
    before_frames = round(context_before_seconds * SAMPLE_RATE / samples_per_frame)
    after_frames = round(context_after_seconds * SAMPLE_RATE / samples_per_frame)
    stage2_by_index: dict[int, dict[str, object]] = {}
    inference_seconds = 0.0
    decoded_audio_seconds = 0.0
    for batch_start in range(0, len(stage1_indices), batch_size):
        indices = stage1_indices[batch_start : batch_start + batch_size]
        audios: list[np.ndarray] = []
        for index in indices:
            source = joined[index]["corpus"]
            assert isinstance(source, dict)
            path = corpus_root / str(source["relative_path"])
            if sha256(path) != source.get("sha256"):
                raise ValueError(f"openslr_cascade_audio_hash_mismatch:{path}")
            audio = decode_flac(ffmpeg_path, path)
            audios.append(audio)
            decoded_audio_seconds += len(audio) / SAMPLE_RATE
        prepared = processor(
            audios, sampling_rate=SAMPLE_RATE, return_tensors="pt", padding=True
        )
        input_lengths = torch.tensor(
            [len(audio) for audio in audios], dtype=torch.long, device=device
        )
        started = time.perf_counter()
        with torch.inference_mode():
            logits = model(input_values=prepared.input_values.to(device)).logits.float().cpu()
        inference_seconds += time.perf_counter() - started
        output_lengths = model._get_feat_extract_output_lengths(input_lengths).cpu().tolist()
        log_probabilities = torch.log_softmax(logits, dim=-1).numpy()
        predictions = torch.argmax(logits, dim=-1).numpy()
        for local_index, global_index in enumerate(indices):
            length = int(output_lengths[local_index])
            log_probs = log_probabilities[local_index, :length]
            collapsed = collapse_ctc_path(predictions[local_index, :length], blank_id)
            greedy_spans = exact_sequence_spans(collapsed, target_ids)
            asr = joined[global_index]["parakeet"]
            if not isinstance(asr, dict):
                raise ValueError("openslr_cascade_stage1_parakeet_evidence_missing")
            words = asr.get("lexical_words")
            lexical_proposals = asr.get("lexical_proposals")
            if not isinstance(words, list) or not isinstance(lexical_proposals, list):
                raise ValueError("openslr_cascade_lexical_evidence_invalid")
            locators: list[dict[str, object]] = [
                {
                    "source": "ctc_greedy_exact_target",
                    "locator_start_frame": start,
                    "locator_end_frame": end,
                    "greedy_sequence": list(sequence),
                }
                for start, end, sequence in greedy_spans
            ]
            for proposal in lexical_proposals:
                if not isinstance(proposal, dict):
                    raise ValueError("openslr_cascade_lexical_proposal_invalid")
                if not is_exact_lexical_target_proposal(str(proposal["surface"])):
                    continue
                locators.append(
                    {
                        "source": "parakeet_lexical_proposal",
                        "surface": proposal["surface"],
                        "locator_start_frame": math.floor(
                            float(proposal["start_seconds"]) * SAMPLE_RATE / samples_per_frame
                        ),
                        "locator_end_frame": math.ceil(
                            float(proposal["end_seconds"]) * SAMPLE_RATE / samples_per_frame
                        ),
                    }
                )
            scored: list[dict[str, object]] = []
            for locator in locators:
                value = score_verifier_span(
                    log_probs,
                    start_frame=int(locator["locator_start_frame"]),
                    end_frame=int(locator["locator_end_frame"]),
                    target_sequences=target_ids,
                    confusable_sequences=confusable_ids,
                    blank_id=blank_id,
                    context_before_frames=before_frames,
                    context_after_frames=after_frames,
                )
                locator_start = int(locator["locator_start_frame"]) * samples_per_frame / SAMPLE_RATE
                locator_end = int(locator["locator_end_frame"]) * samples_per_frame / SAMPLE_RATE
                scored.append(
                    {
                        **locator,
                        **value,
                        "locator_start_seconds": locator_start,
                        "locator_end_seconds": locator_end,
                        "multiword_non_target_veto": multiword_non_target_overlap(
                            words, start_seconds=locator_start, end_seconds=locator_end
                        ),
                    }
                )
            eligible = [value for value in scored if not value["multiword_non_target_veto"]]
            best = max(eligible, key=lambda value: float(value["margin"])) if eligible else None
            stage2_by_index[global_index] = {
                "ctc_greedy_target_span_count": len(greedy_spans),
                "locators": scored,
                "best_verifier": best,
                "detected": bool(best and float(best["margin"]) >= verifier_margin),
            }
        print(f"PROGRESS|{min(batch_start + len(indices), len(stage1_indices))}/{len(stage1_indices)}", flush=True)

    records: list[dict[str, object]] = []
    for index, evidence in enumerate(joined):
        source = evidence["corpus"]
        scan_record = evidence["scan"]
        asr = evidence["parakeet"]
        assert isinstance(source, dict) and isinstance(scan_record, dict)
        stage2 = stage2_by_index.get(index)
        records.append(
            {
                "utterance_id": source["utterance_id"],
                "relative_path": source["relative_path"],
                "duration_seconds": source["duration_seconds"],
                "reference_transcript": source["transcript"],
                "livekit_max_score": scan_record["max_score"],
                "strong_proposal": evidence["strong_proposal"],
                "parakeet_transcript": asr.get("transcript", "") if isinstance(asr, dict) else "",
                "parakeet_lexical_proposals": asr.get("lexical_proposals", []) if isinstance(asr, dict) else [],
                "stage1_proposed": evidence["stage1_proposed"],
                "stage2": stage2,
                "detected": bool(stage2 and stage2["detected"]),
            }
        )
    exposure_seconds = sum(float(record["duration_seconds"]) for record in records)
    exposure_hours = exposure_seconds / 3600.0
    false_activations = sum(bool(record["detected"]) for record in records)
    weights = phoneme_model_directory / "pytorch_model.bin"
    report: dict[str, object] = {
        "schema": "baxy.openslr-librispeech-ctc-cascade-development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "independent_raw_negative_architecture_development",
        "independent_from_synthetic_training": True,
        "frozen_product_holdout": False,
        "product_far_claim_supported": False,
        "reason_product_far_claim_not_supported": "architecture_development_and_exposure_below_30_hours",
        "corpus_manifest": corpus_manifest_path.as_posix(),
        "corpus_manifest_sha256": corpus_hash,
        "livekit_scan": livekit_scan_path.as_posix(),
        "livekit_scan_sha256": scan_hash,
        "parakeet_audit": parakeet_audit_path.as_posix(),
        "parakeet_audit_sha256": sha256(parakeet_audit_path),
        "thresholds": {
            "livekit_strong_proposal": livekit_proposal_threshold,
            "livekit_lexical_corroboration": lexical_corroboration_threshold,
            "ctc_margin": verifier_margin,
            "context_before_seconds": context_before_seconds,
            "context_after_seconds": context_after_seconds,
        },
        "ctc_teacher": {
            "directory": phoneme_model_directory.as_posix(),
            "weights_sha256": sha256(weights),
            "device": device,
            "batch_size": batch_size,
            "model_load_seconds": round(model_load_seconds, 6),
            "inference_seconds": round(inference_seconds, 6),
            "decoded_stage1_audio_seconds": decoded_audio_seconds,
            "samples_per_output_frame": samples_per_frame,
        },
        "decoder": {"path": ffmpeg_path.as_posix(), "sha256": sha256(ffmpeg_path)},
        "metrics": {
            "utterances": len(records),
            "exposure_seconds": exposure_seconds,
            "exposure_hours": exposure_hours,
            "strong_livekit_proposals": sum(bool(record["strong_proposal"]) for record in records),
            "lexical_proposals": sum(bool(record["parakeet_lexical_proposals"]) for record in records),
            "stage1_union_proposals": len(stage1_indices),
            "false_activations": false_activations,
            "point_false_activations_per_hour": false_activations / exposure_hours,
            "zero_event_upper_95_fpph": -math.log(0.05) / exposure_hours if false_activations == 0 else None,
        },
        "runtime": {"torch": torch.__version__, "transformers": transformers.__version__, "espeak": espeak},
        "records": records,
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--livekit-scan", type=Path, required=True)
    parser.add_argument("--parakeet-audit", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--phoneme-model-dir", type=Path, required=True)
    parser.add_argument("--livekit-proposal-threshold", type=float, default=0.05)
    parser.add_argument("--lexical-corroboration-threshold", type=float, default=0.02)
    parser.add_argument("--verifier-margin", type=float, default=0.5)
    parser.add_argument("--context-before-seconds", type=float, default=0.2)
    parser.add_argument("--context-after-seconds", type=float, default=0.2)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate(
        corpus_manifest_path=args.corpus_manifest,
        livekit_scan_path=args.livekit_scan,
        parakeet_audit_path=args.parakeet_audit,
        ffmpeg_path=args.ffmpeg,
        phoneme_model_directory=args.phoneme_model_dir,
        livekit_proposal_threshold=args.livekit_proposal_threshold,
        lexical_corroboration_threshold=args.lexical_corroboration_threshold,
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
