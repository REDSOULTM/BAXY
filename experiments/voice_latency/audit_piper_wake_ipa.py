"""Audit whether synthetic positive clips actually contain the BAXY phonemes.

The wake-word trainer trusts directory labels.  This development-only gate
uses Meta's multilingual phoneme recognizer to check that a positive WAV is
close to the intended /baksi/ sequence before any candidate is trained or a
blind human partition is opened.

The expensive libraries are imported only by :func:`audit_candidate`, so the
normalisation and distance contract can be unit tested without a GPU model.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata


SAMPLE_RATE = 16_000
MODEL_ID = "facebook/wav2vec2-lv-60-espeak-cv-ft"
MODEL_REVISION = "ae45363bf3413b374fecd9dc8bc1df0e24c3b7f4"
TARGET_SEQUENCES = (
    ("b", "a", "k", "s", "i"),
    ("b", "æ", "k", "s", "i"),
    ("b", "ɑ", "k", "s", "i"),
    # Human CC-BY development evidence shows the expected Russian rendering
    # /baksʲi/.  Keep it explicit: normalize_ipa must not erase palatalization.
    ("b", "a", "k", "sʲ", "i"),
    ("b", "ɑ", "k", "sʲ", "i"),
    ("b", "ʌ", "k", "sʲ", "i"),
)
LEGACY_SINGLE_SEQUENCE = TARGET_SEQUENCES[0]
_IGNORED_IPA_CHARACTERS = frozenset("ˈˌːˑ")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_ipa(decoded: str) -> tuple[str, ...]:
    """Return comparable IPA tokens without stress, length, or tone marks.

    The recognizer emits space-delimited phonemes.  We deliberately do not
    rewrite consonants or collapse affricates: doing so would make an invalid
    positive look better.  Unicode combining marks, suprasegmentals, and tone
    digits and modifier-letter articulations are retained: accepting them
    would make this pre-training label gate optimistically permissive.
    """

    normalized: list[str] = []
    for raw_token in decoded.replace("|", " ").split():
        decomposed = unicodedata.normalize("NFD", raw_token)
        token = "".join(
            character
            for character in decomposed
            if unicodedata.category(character)[0] != "M"
            and character not in _IGNORED_IPA_CHARACTERS
        )
        token = unicodedata.normalize("NFC", token)
        if token:
            normalized.append(token)
    return tuple(normalized)


def edit_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    """Compute Levenshtein distance over phoneme tokens."""

    if len(left) > len(right):
        left, right = right, left
    previous = list(range(len(left) + 1))
    for right_index, right_token in enumerate(right, start=1):
        current = [right_index]
        for left_index, left_token in enumerate(left, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[left_index] + 1,
                    previous[left_index - 1] + (left_token != right_token),
                )
            )
        previous = current
    return previous[-1]


def target_distance(sequence: tuple[str, ...]) -> int:
    return min(edit_distance(sequence, target) for target in TARGET_SEQUENCES)


def select_dense_wavs(root: Path, count: int) -> list[Path]:
    if count <= 0:
        raise ValueError("count_must_be_positive")
    paths = [root / f"clip_{index:06d}.wav" for index in range(count)]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"dense_wav_missing:{missing[0]}")
    return paths


def trim_ctc_predictions(
    predicted_ids: object, output_lengths: list[int]
) -> list[list[int]]:
    """Remove batch padding before CTC decoding.

    ``batch_decode`` otherwise sees predictions produced for the longest WAV's
    padded tail, which makes a result depend on the other clips in its batch.
    The tensor-like input is intentionally duck typed to keep unit tests light.
    """

    if len(predicted_ids) != len(output_lengths):
        raise ValueError("ctc_batch_length_mismatch")
    trimmed: list[list[int]] = []
    for row, length in zip(predicted_ids, output_lengths, strict=True):
        if length <= 0 or length > len(row):
            raise ValueError(f"ctc_output_length_invalid:{length}:{len(row)}")
        values = row[:length]
        if hasattr(values, "detach"):
            values = values.detach().cpu().tolist()
        else:
            values = list(values)
        trimmed.append([int(value) for value in values])
    return trimmed


def wav_set_digest(paths: list[Path]) -> str:
    """Bind a result to ordered names and complete WAV contents."""

    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _validate_sha256(value: str, field: str) -> str:
    normalized = value.casefold()
    if re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
        raise ValueError(f"invalid_sha256:{field}")
    return normalized


def audit_candidate(
    *,
    name: str,
    root: Path,
    count: int,
    configuration_sha256: str,
    processor: object,
    model: object,
    device: str,
    batch_size: int,
) -> dict[str, object]:
    import librosa
    import torch

    paths = select_dense_wavs(root, count)
    decoded_all: list[str] = []
    for start in range(0, len(paths), batch_size):
        batch_paths = paths[start : start + batch_size]
        audios = []
        for path in batch_paths:
            audio, sample_rate = librosa.load(path, sr=None, mono=True)
            if sample_rate != SAMPLE_RATE:
                raise ValueError(f"wav_sample_rate_mismatch:{path}:{sample_rate}")
            audios.append(audio)
        inputs = processor(
            audios,
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
            padding=True,
        )
        input_lengths = torch.tensor(
            [len(audio) for audio in audios], dtype=torch.long, device=device
        )
        model_inputs = {"input_values": inputs.input_values.to(device)}
        if getattr(inputs, "attention_mask", None) is not None:
            model_inputs["attention_mask"] = inputs.attention_mask.to(device)
        with torch.inference_mode():
            logits = model(**model_inputs).logits
        predicted_ids = torch.argmax(logits, dim=-1)
        output_lengths = model._get_feat_extract_output_lengths(input_lengths)
        decoded_all.extend(
            processor.batch_decode(
                trim_ctc_predictions(predicted_ids, output_lengths.tolist())
            )
        )

    normalized = [normalize_ipa(value) for value in decoded_all]
    distances = [target_distance(value) for value in normalized]
    counts = Counter(distances)
    legacy_distances = [
        edit_distance(value, LEGACY_SINGLE_SEQUENCE) for value in normalized
    ]
    legacy_counts = Counter(legacy_distances)
    sequence_counts = Counter(" ".join(value) for value in normalized)
    exact = counts[0]
    within_one = exact + counts[1]
    examples = []
    for path, raw, sequence, distance in zip(
        paths, decoded_all, normalized, distances, strict=True
    ):
        if len(examples) >= 16:
            break
        if distance == 0 or len(examples) < 8:
            examples.append(
                {
                    "file": path.name,
                    "decoded_ipa": raw,
                    "normalized_tokens": list(sequence),
                    "target_edit_distance": distance,
                }
            )
    return {
        "name": name,
        "source_directory": root.as_posix(),
        "configuration_sha256": _validate_sha256(
            configuration_sha256, f"{name}.configuration_sha256"
        ),
        "clip_count": len(paths),
        "ordered_wav_set_sha256": wav_set_digest(paths),
        "exact_target_count": exact,
        "exact_target_rate": exact / len(paths),
        "edit_distance_lte_1_count": within_one,
        "edit_distance_lte_1_rate": within_one / len(paths),
        "edit_distance_counts": {
            str(distance): counts[distance] for distance in sorted(counts)
        },
        "legacy_single_sequence_comparison": {
            "sequence": list(LEGACY_SINGLE_SEQUENCE),
            "purpose": "reproduce_the_initial_ad_hoc_pilot;_not_used_for_rejection",
            "exact_target_count": legacy_counts[0],
            "exact_target_rate": legacy_counts[0] / len(paths),
            "edit_distance_lte_1_count": legacy_counts[0] + legacy_counts[1],
            "edit_distance_lte_1_rate": (
                legacy_counts[0] + legacy_counts[1]
            )
            / len(paths),
            "edit_distance_counts": {
                str(distance): legacy_counts[distance]
                for distance in sorted(legacy_counts)
            },
        },
        "accepted_sequence_counts": {
            " ".join(target): sequence_counts[" ".join(target)]
            for target in TARGET_SEQUENCES
        },
        "most_common_normalized_sequences": [
            {"sequence": sequence, "count": sequence_count}
            for sequence, sequence_count in sequence_counts.most_common(20)
        ],
        "examples": examples,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--interpolated-dir", type=Path, required=True)
    parser.add_argument("--interpolated-config-sha256", required=True)
    parser.add_argument("--discrete-dir", type=Path, required=True)
    parser.add_argument("--discrete-config-sha256", required=True)
    parser.add_argument("--count", type=int, default=1048)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise ValueError("batch_size_must_be_positive")

    import phonemizer
    import safetensors
    import tokenizers
    import torch
    import transformers
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

    if args.device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("cuda_requested_but_unavailable")

    model_dir = args.model_dir.resolve()
    model_weights = model_dir / "pytorch_model.bin"
    if not model_weights.is_file():
        raise FileNotFoundError(f"phoneme_model_weights_missing:{model_weights}")
    espeak_library_raw = os.environ.get("PHONEMIZER_ESPEAK_LIBRARY")
    espeak_data_raw = os.environ.get("PHONEMIZER_ESPEAK_DATA_PATH")
    if not espeak_library_raw or not espeak_data_raw:
        raise RuntimeError("phonemizer_espeak_environment_missing")
    espeak_library = Path(espeak_library_raw).resolve()
    espeak_data = Path(espeak_data_raw).resolve()
    if not espeak_library.is_file() or not espeak_data.is_dir():
        raise FileNotFoundError("phonemizer_espeak_artifact_missing")

    processor = Wav2Vec2Processor.from_pretrained(model_dir, local_files_only=True)
    model = Wav2Vec2ForCTC.from_pretrained(
        model_dir, local_files_only=True
    ).eval().to(device)
    candidates = [
        audit_candidate(
            name="interpolated_slerp",
            root=args.interpolated_dir.resolve(),
            count=args.count,
            configuration_sha256=args.interpolated_config_sha256,
            processor=processor,
            model=model,
            device=device,
            batch_size=args.batch_size,
        ),
        audit_candidate(
            name="discrete_speaker_endpoint",
            root=args.discrete_dir.resolve(),
            count=args.count,
            configuration_sha256=args.discrete_config_sha256,
            processor=processor,
            model=model,
            device=device,
            batch_size=args.batch_size,
        ),
    ]
    report = {
        "schema": "baxy.piper-wake-ipa-pilot.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_only_synthetic_positive_label_audit",
        "target_display_name": "Baxy",
        "target_generator_text": "baxi",
        "accepted_normalized_target_sequences": [
            list(target) for target in TARGET_SEQUENCES
        ],
        "normalization": {
            "unit": "space_delimited_ipa_token",
            "removed": "Unicode combining marks, stress, and length only",
            "consonant_substitutions_allowed": False,
            "affricates_split": False,
            "ctc_batch_padding_logits_decoded": False,
        },
        "phoneme_recognizer": {
            "model_id": MODEL_ID,
            "revision": MODEL_REVISION,
            "local_model_directory": model_dir.as_posix(),
            "pytorch_model_sha256": sha256(model_weights),
            "sample_rate": SAMPLE_RATE,
        },
        "runtime": {
            "device": device,
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "transformers": transformers.__version__,
            "tokenizers": tokenizers.__version__,
            "safetensors": safetensors.__version__,
            "phonemizer": phonemizer.__version__,
            "espeak_library": espeak_library.as_posix(),
            "espeak_library_sha256": sha256(espeak_library),
            "espeak_data_directory": espeak_data.as_posix(),
        },
        "common_prefix_clip_count": args.count,
        "candidates": candidates,
        "decision": {
            "interpolated_slerp": "rejected_positive_label_noise",
            "discrete_speaker_endpoint": "rejected_no_material_ipa_improvement",
            "candidate_training_started": False,
        },
        "blind_human_partition_accessed": False,
        "effects_executed": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
