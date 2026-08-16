"""Localize known opened Baxy positives with token-timestamp Parakeet.

This teacher is only allowed on explicitly opened development positives. It
stores source hashes and target spans, never filenames or transcript text.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
import wave

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.voice import _compile_contextual_hotwords  # noqa: E402


SCHEMA = "baxy.opened-human-wake-parakeet-localization.v1"
SAMPLE_RATE = 16_000
ALIASES = frozenset({"baxy", "baxi", "baksi", "basi"})
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def fold_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        character for character in normalized if not unicodedata.combining(character)
    ).lower()
    return _NON_ALNUM.sub("", ascii_value)


def locate_alias_spans(
    tokens: list[str],
    timestamps: list[float],
    durations: list[float],
    aliases: frozenset[str] = ALIASES,
) -> list[tuple[float, float, str]]:
    if not (len(tokens) == len(timestamps) == len(durations)):
        raise ValueError("opened_wake_localizer_token_timing_mismatch")
    spans: list[tuple[float, float, str]] = []
    for start in range(len(tokens)):
        if not fold_token(tokens[start]):
            continue
        combined = ""
        for end in range(start, min(len(tokens), start + 8)):
            combined += tokens[end]
            folded = fold_token(combined)
            if folded in aliases and fold_token(tokens[end]):
                span_start = float(timestamps[start])
                span_end = float(timestamps[end]) + float(durations[end])
                if 0.0 <= span_start < span_end:
                    spans.append((span_start, span_end, folded))
            if len(folded) > max(map(len, aliases)):
                break
    return spans


def recognizer(stt_directory: Path) -> tuple[object, str]:
    import sherpa_onnx

    required = {
        "encoder": stt_directory / "encoder.int8.onnx",
        "decoder": stt_directory / "decoder.int8.onnx",
        "joiner": stt_directory / "joiner.int8.onnx",
        "tokens": stt_directory / "tokens.txt",
    }
    if any(not path.is_file() for path in required.values()):
        raise ValueError("opened_wake_localizer_stt_bundle_incomplete")
    instance = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(required["encoder"]),
        decoder=str(required["decoder"]),
        joiner=str(required["joiner"]),
        tokens=str(required["tokens"]),
        num_threads=4,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
        hotwords_score=5.0,
    )
    hotwords = _compile_contextual_hotwords(required["tokens"], tuple(sorted(ALIASES)))
    if not hotwords:
        raise ValueError("opened_wake_localizer_hotword_encoding_failed")
    return instance, hotwords


def decode(instance: object, audio: np.ndarray, hotwords: str | None) -> object:
    stream = (
        instance.create_stream(hotwords=hotwords)
        if hotwords is not None
        else instance.create_stream()
    )
    stream.accept_waveform(SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
    instance.decode_stream(stream)
    return stream.result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--maximum-source-seconds", type=float, default=20.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.maximum_source_seconds <= 0:
        raise SystemExit("--maximum-source-seconds must be positive.")
    source_root = args.source_dir.resolve(strict=True)
    output_path = args.output.resolve()
    if output_path.exists():
        raise SystemExit("Output already exists.")
    paths: list[Path] = []
    for path in sorted(source_root.rglob("*.wav")):
        with wave.open(str(path), "rb") as source:
            contract = (
                source.getnchannels(),
                source.getsampwidth(),
                source.getframerate(),
            )
            duration = source.getnframes() / source.getframerate()
        if contract != (1, 2, SAMPLE_RATE):
            raise ValueError("opened_wake_localizer_wav_contract_invalid")
        if duration <= args.maximum_source_seconds:
            paths.append(path)
    if not paths:
        raise ValueError("opened_wake_localizer_sources_empty")
    instance, hotwords = recognizer(args.stt_directory.resolve(strict=True))
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for index, path in enumerate(paths):
        audio, rate = room._read_pcm16(path)
        if rate != SAMPLE_RATE:
            raise ValueError("opened_wake_localizer_sample_rate_invalid")
        arms: list[dict[str, object]] = []
        selected: tuple[float, float, str] | None = None
        selected_arm: str | None = None
        for arm, context in (("baseline", None), ("contextual", hotwords)):
            result = decode(instance, audio, context)
            spans = locate_alias_spans(
                list(result.tokens),
                [float(value) for value in result.timestamps],
                [float(value) for value in result.durations],
            )
            arms.append(
                {
                    "arm": arm,
                    "transcriptSha256": hashlib.sha256(
                        str(result.text).encode("utf-8")
                    ).hexdigest(),
                    "aliasSpanCount": len(spans),
                }
            )
            if selected is None and spans:
                selected = min(spans, key=lambda value: (value[1] - value[0], value[0]))
                selected_arm = arm
        records.append(
            {
                "sourceSha256": room._sha256(path),
                "sourceSeconds": audio.size / SAMPLE_RATE,
                "targetSpanSeconds": (
                    {"start": selected[0], "end": selected[1], "alias": selected[2]}
                    if selected is not None
                    else None
                ),
                "selectedArm": selected_arm,
                "arms": arms,
            }
        )
        print(f"localized:{index + 1}/{len(paths)}", flush=True)
    localized = sum(record["targetSpanSeconds"] is not None for record in records)
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_known_positive_localization_teacher",
        "sourceCorpusSha256": room._corpus_sha256(paths, source_root),
        "sourceCount": len(paths),
        "localizedCount": localized,
        "records": records,
        "elapsedSeconds": time.perf_counter() - started,
        "filenamesOrTranscriptsRetained": False,
        "blindHumanPartitionAccessed": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"sources": len(paths), "localized": localized}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
