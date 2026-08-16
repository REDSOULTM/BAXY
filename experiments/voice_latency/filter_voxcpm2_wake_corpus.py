"""Create dense 16 kHz VoxCPM2 positive or adversarial-negative wake clips.

The filter binds the generation and phoneme-audit manifests by hash, applies
the same conservative WebRTC VAD rule used by LiveKit's Piper generator, and
rejects clips that violate the class-specific phoneme boundary or remain
outside the product's two-second input window.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import wave

import numpy as np


SAMPLE_RATE = 16_000
MAX_DURATION_SECONDS = 2.0
MIN_DURATION_SECONDS = 0.20
VAD_FRAME_SECONDS = 0.030
VAD_MIN_START_SAMPLES = 2_000


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


def remove_silence(
    audio_i16: np.ndarray,
    *,
    vad: object,
    sample_rate: int = SAMPLE_RATE,
    frame_duration: float = VAD_FRAME_SECONDS,
    min_start: int = VAD_MIN_START_SAMPLES,
) -> np.ndarray:
    """Mirror LiveKit v0.2.1's conservative Piper VAD trimming contract."""

    flattened = np.asarray(audio_i16, dtype=np.int16).flatten()
    retained = flattened[:min_start].tolist()
    step_size = round(sample_rate * frame_duration)
    for start in range(min_start, len(flattened) - step_size, step_size):
        frame = flattened[start : start + step_size]
        if vad.is_speech(frame.tobytes(), sample_rate):
            retained.extend(frame.tolist())
    result = np.asarray(retained, dtype=np.int16)
    min_speech_samples = round(sample_rate * 0.15)
    if len(result) <= min_start + min_speech_samples:
        return flattened
    return result


def inspect_pcm(audio_i16: np.ndarray) -> dict[str, object]:
    flattened = np.asarray(audio_i16, dtype=np.int16).flatten()
    if flattened.size == 0:
        raise ValueError("pcm_empty")
    float_audio = flattened.astype(np.float64) / 32768.0
    return {
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "sample_width_bytes": 2,
        "frames": int(flattened.size),
        "duration_seconds": flattened.size / SAMPLE_RATE,
        "peak": float(np.max(np.abs(float_audio))),
        "rms": float(np.sqrt(np.mean(float_audio * float_audio))),
    }


def write_wav(path: Path, audio_i16: np.ndarray) -> None:
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(SAMPLE_RATE)
        target.writeframes(np.asarray(audio_i16, dtype="<i2").tobytes())


def ipa_rejection_reason(
    audited: dict[str, object],
    class_label: str,
    positive_ipa_policy: str = "exact_target",
) -> str | None:
    if class_label == "positive":
        if positive_ipa_policy == "exact_target":
            return (
                "ipa_not_exact"
                if int(audited["target_edit_distance"]) != 0
                else None
            )
        if positive_ipa_policy == "exact_target_subsequence":
            if "exact_target_subsequence" not in audited:
                raise ValueError("positive_audit_missing_exact_target_subsequence")
            return (
                None
                if bool(audited["exact_target_subsequence"])
                else "ipa_target_subsequence_missing"
            )
        raise ValueError(f"unsupported_positive_ipa_policy:{positive_ipa_policy}")
    if class_label == "adversarial_negative":
        if "exact_target_subsequence" not in audited:
            raise ValueError("negative_audit_missing_exact_target_subsequence")
        return (
            "exact_target_subsequence_collision"
            if bool(audited["exact_target_subsequence"])
            else None
        )
    raise ValueError(f"unsupported_generation_class_label:{class_label}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation-manifest", type=Path, required=True)
    parser.add_argument("--ipa-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--vad-aggressiveness", type=int, choices=range(4), default=0)
    parser.add_argument(
        "--positive-ipa-policy",
        choices=("exact_target", "exact_target_subsequence"),
        default="exact_target",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generation_path = args.generation_manifest.resolve()
    audit_path = args.ipa_audit.resolve()
    generation = read_json(generation_path)
    audit = read_json(audit_path)
    if generation.get("schema") != "baxy.voxcpm2-gguf-wake-pilot-corpus.v1":
        raise ValueError("unsupported_generation_manifest_schema")
    if audit.get("schema") != "baxy.voxcpm2-gguf-wake-ipa-pilot.v1":
        raise ValueError("unsupported_ipa_audit_schema")
    if str(audit.get("source_manifest_sha256", "")) != sha256(generation_path):
        raise ValueError("generation_and_ipa_audit_hash_mismatch")
    if generation.get("blind_human_partition_accessed") is not False:
        raise ValueError("generation_blind_boundary_invalid")
    if audit.get("blind_human_partition_accessed") is not False:
        raise ValueError("audit_blind_boundary_invalid")
    generation_settings = generation.get("generation")
    if not isinstance(generation_settings, dict):
        raise ValueError("generation_settings_missing")
    class_label = str(generation_settings.get("class_label", "positive"))
    if class_label not in {"positive", "adversarial_negative"}:
        raise ValueError(f"unsupported_generation_class_label:{class_label}")
    audit_class_label = str(audit.get("class_label", class_label))
    if audit_class_label != class_label:
        raise ValueError("generation_and_ipa_audit_class_label_mismatch")
    positive_ipa_policy = args.positive_ipa_policy
    if class_label != "positive" and positive_ipa_policy != "exact_target":
        raise ValueError("positive_ipa_policy_only_valid_for_positive_class")
    audit_positive_policy = str(audit.get("positive_ipa_policy", "exact_target"))
    if class_label == "positive" and audit_positive_policy != positive_ipa_policy:
        raise ValueError("filter_and_audit_positive_ipa_policy_mismatch")

    generation_records = generation.get("records")
    audit_records = audit.get("records")
    if not isinstance(generation_records, list) or not isinstance(audit_records, list):
        raise ValueError("records_missing")
    generated_by_index = {
        int(record["index"]): record
        for record in generation_records
        if isinstance(record, dict)
    }
    audited_by_index = {
        int(record["index"]): record
        for record in audit_records
        if isinstance(record, dict)
    }
    if generated_by_index.keys() != audited_by_index.keys():
        raise ValueError("generation_and_ipa_record_index_mismatch")

    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"filtered_output_directory_not_empty:{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    import librosa
    import webrtcvad

    vad = webrtcvad.Vad(args.vad_aggressiveness)
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    generation_root = generation_path.parent
    for source_index in sorted(generated_by_index):
        generated = generated_by_index[source_index]
        audited = audited_by_index[source_index]
        source_path = generation_root / str(generated["output_file"])
        expected_hash = str(generated.get("wav", {}).get("sha256", ""))
        actual_hash = sha256(source_path)
        if actual_hash != expected_hash or actual_hash != str(
            audited.get("source_wav_sha256", "")
        ):
            raise ValueError(f"source_wav_hash_mismatch:{source_path}")
        rejection_reason = ipa_rejection_reason(
            audited, class_label, positive_ipa_policy
        )
        if rejection_reason is not None:
            rejected.append(
                {
                    "source_index": source_index,
                    "reason": rejection_reason,
                    "phrase_id": generated.get("phrase_id", "target"),
                    "phrase_text": generated.get("phrase_text", generated.get("text")),
                    "target_edit_distance": int(audited["target_edit_distance"]),
                    "exact_target_subsequence": audited.get(
                        "exact_target_subsequence"
                    ),
                    "decoded_ipa": audited["decoded_ipa"],
                }
            )
            continue

        float_audio, _ = librosa.load(source_path, sr=SAMPLE_RATE, mono=True)
        peak = float(np.max(np.abs(float_audio))) if float_audio.size else 0.0
        if peak <= 0.0:
            rejected.append(
                {"source_index": source_index, "reason": "source_audio_silent"}
            )
            continue
        clipped = np.clip(float_audio, -1.0, 1.0)
        audio_i16 = np.rint(clipped * 32767.0).astype(np.int16)
        trimmed = remove_silence(audio_i16, vad=vad)
        wav = inspect_pcm(trimmed)
        duration = float(wav["duration_seconds"])
        if not MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS:
            rejected.append(
                {
                    "source_index": source_index,
                    "reason": "vad_duration_out_of_range",
                    "duration_seconds": duration,
                    "decoded_ipa": audited["decoded_ipa"],
                }
            )
            continue

        output_index = len(accepted)
        output_path = output_dir / f"clip_{output_index:06d}.wav"
        temporary = output_path.with_suffix(".wav.partial")
        write_wav(temporary, trimmed)
        os.replace(temporary, output_path)
        wav["sha256"] = sha256(output_path)
        accepted.append(
            {
                "output_index": output_index,
                "output_file": output_path.name,
                "source_index": source_index,
                "source_file": source_path.name,
                "source_sha256": actual_hash,
                "persona_id": generated["persona_id"],
                "persona": generated["persona"],
                "seed": generated["seed"],
                "phrase_id": generated.get("phrase_id", "target"),
                "phrase_text": generated.get("phrase_text", generated.get("text")),
                "class_label": class_label,
                "decoded_ipa": audited["decoded_ipa"],
                "normalized_tokens": audited["normalized_tokens"],
                "wav": wav,
            }
        )

    manifest = {
        "schema": "baxy.voxcpm2-ipa-filtered-wake-corpus.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "generation_manifest": generation_path.as_posix(),
        "generation_manifest_sha256": sha256(generation_path),
        "ipa_audit": audit_path.as_posix(),
        "ipa_audit_sha256": sha256(audit_path),
        "class_label": class_label,
        "filter": {
            "positive_ipa_policy": (
                positive_ipa_policy if class_label == "positive" else None
            ),
            "phoneme_selection_rule": (
                (
                    "target_edit_distance_equals_zero"
                    if positive_ipa_policy == "exact_target"
                    else "exact_target_subsequence_is_true"
                )
                if class_label == "positive"
                else "exact_target_subsequence_is_false"
            ),
            "required_target_edit_distance": (
                0
                if class_label == "positive"
                and positive_ipa_policy == "exact_target"
                else None
            ),
            "required_exact_target_subsequence": (
                True
                if class_label == "positive"
                and positive_ipa_policy == "exact_target_subsequence"
                else None
            ),
            "forbidden_exact_target_subsequence": (
                class_label == "adversarial_negative"
            ),
            "sample_rate": SAMPLE_RATE,
            "vad": "webrtcvad",
            "vad_aggressiveness": args.vad_aggressiveness,
            "vad_frame_seconds": VAD_FRAME_SECONDS,
            "vad_min_start_samples": VAD_MIN_START_SAMPLES,
            "min_duration_seconds": MIN_DURATION_SECONDS,
            "max_duration_seconds": MAX_DURATION_SECONDS,
        },
        "counts": {
            "generated": len(generated_by_index),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "ipa_rejected": sum(
                record["reason"]
                in {"ipa_not_exact", "ipa_target_subsequence_missing"}
                for record in rejected
            ),
            "target_subsequence_collision_rejected": sum(
                record["reason"] == "exact_target_subsequence_collision"
                for record in rejected
            ),
            "phoneme_rejected": sum(
                record["reason"]
                in {
                    "ipa_not_exact",
                    "ipa_target_subsequence_missing",
                    "exact_target_subsequence_collision",
                }
                for record in rejected
            ),
            "temporal_or_signal_rejected": sum(
                record["reason"]
                not in {
                    "ipa_not_exact",
                    "ipa_target_subsequence_missing",
                    "exact_target_subsequence_collision",
                }
                for record in rejected
            ),
        },
        "records": accepted,
        "rejections": rejected,
        "blind_human_partition_accessed": False,
        "candidate_model_training_started": False,
        "effects_executed": 0,
    }
    manifest_path = output_dir / "manifest.v1.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = {
        "manifest": manifest_path.as_posix(),
        "class_label": class_label,
        "counts": manifest["counts"],
        "blind_human_partition_accessed": False,
    }
    sys.stdout.buffer.write(
        (json.dumps(summary, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
