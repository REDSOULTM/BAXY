"""Diagnose the historical voice clip without publishing its transcript."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from baxy_mind.corrector import catalog_correction_terms
from baxy_mind.voice import SAMPLE_RATE, VoiceEngine


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "streaming.play",
            "parameters": {
                "type": "object",
                "properties": {
                    "provider": {"type": "string", "enum": ["spotify"]}
                },
                "additionalProperties": False,
            },
        },
    }
]


def distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for row, a in enumerate(left, 1):
        current = [row]
        for column, b in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (a != b),
                )
            )
        previous = current
    return previous[-1]


def metrics(text: str) -> dict[str, object]:
    tokens = re.findall(r"[a-z0-9]+", text.casefold())
    distances = [distance(token, "spotify") for token in tokens]
    return {
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "character_count": len(text),
        "token_count": len(tokens),
        "contains_spotify": "spotify" in text.casefold(),
        "best_spotify_edit_distance": min(distances) if distances else None,
        "nearest_token_length": (
            len(tokens[distances.index(min(distances))]) if distances else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    terms = catalog_correction_terms(TOOLS)
    engine = VoiceEngine(lambda _text: None, lambda _event: None, correction_terms=terms)
    engine.start("direct")
    try:
        with wave.open(str(args.clip.resolve(strict=True)), "rb") as source:
            source_rate = source.getframerate()
            channels = source.getnchannels()
            frames = source.getnframes()
            audio = np.frombuffer(source.readframes(frames), dtype=np.int16)
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
        normalized = audio.astype(np.float32) / 32768.0
        if source_rate != SAMPLE_RATE:
            normalized = resample_poly(
                normalized, SAMPLE_RATE, source_rate
            ).astype(np.float32)
        stream = engine._recognizer.create_stream()  # noqa: SLF001
        stream.accept_waveform(SAMPLE_RATE, normalized)
        engine._recognizer.decode_stream(stream)  # noqa: SLF001
        raw = (stream.result.text or "").strip()
        corrected = (
            engine._corrector.correct(raw)  # noqa: SLF001
            if engine._corrector is not None  # noqa: SLF001
            else raw
        )
        report = {
            "schema": "baxy.audit.voice-clip-diagnostic.v1",
            "source_rate": source_rate,
            "channels": channels,
            "duration_seconds": frames / source_rate,
            "correction_terms_include_spotify": any(
                term.casefold() == "spotify" for term in terms
            ),
            "raw": metrics(raw),
            "corrected": metrics(corrected),
            "transcript_redacted": True,
        }
    finally:
        engine.shutdown()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
