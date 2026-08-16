"""Redacted endpoint replay of BAXY's existing private historical voice clip.

The clip is never copied and no transcript, routed text, path, or operation is
written to the report.  Only hashes, presence flags, endpoint timings, and
baseline-equivalence booleans leave the process.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
import wave

import numpy as np

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

import benchmark_voice_endpointing as endpoint_ab  # noqa: E402

from baxy_mind.router import IntentRouter  # noqa: E402
from baxy_mind.voice import VoiceEngine, WakePhraseMatcher  # noqa: E402


def _load_pcm16(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        sample_rate = source.getframerate()
        channels = source.getnchannels()
        width = source.getsampwidth()
        raw = source.readframes(source.getnframes())
    if width != 2:
        raise RuntimeError("private replay requires PCM16 WAV")
    audio = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
    pcm = audio.astype(np.float32) / 32768.0
    if sample_rate != endpoint_ab.SAMPLE_RATE:
        target = round(len(pcm) * endpoint_ab.SAMPLE_RATE / sample_rate)
        pcm = np.interp(
            np.linspace(0, len(pcm) - 1, target),
            np.arange(len(pcm)),
            pcm,
        ).astype(np.float32)
    return np.ascontiguousarray(pcm, dtype=np.float32)


def _secret_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _redacted_semantics(decoded: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_text": bool(decoded["transcript"]),
        "has_routed_text": bool(decoded["routed_text"]),
        "wake_prefix_cleaned": decoded["wake_prefix_cleaned"],
        "transcript_sha256": _secret_hash(decoded["transcript"]),
        "routed_text_sha256": _secret_hash(decoded["routed_text"]),
        "decision_sha256": _secret_hash(
            {
                "kind": decoded["routed_kind"],
                "operation": decoded["routed_operation"],
                "arguments": decoded["routed_arguments"],
            }
        ),
        "has_decision": decoded["routed_kind"] is not None,
    }


def run(clip: Path, output: Path) -> dict[str, Any]:
    pcm = _load_pcm16(clip)
    clip_file_sha256 = hashlib.sha256(clip.read_bytes()).hexdigest()
    pcm_sha256 = endpoint_ab._sha256_float32(pcm)  # noqa: SLF001
    private_case = endpoint_ab.SynthesizedCase(
        index=0,
        language="redacted",
        reference="",
        expected_kind="",
        expected_operation="",
        expected_arguments=None,
        requires_wake=False,
        pcm=pcm,
        pcm_sha256=pcm_sha256,
    )
    engine = VoiceEngine(lambda _text: None)
    engine.load()
    if engine._vad is None:  # noqa: SLF001
        raise RuntimeError("Silero VAD did not load")
    router = IntentRouter()
    wake_matcher = WakePhraseMatcher()
    observations: list[dict[str, Any]] = []
    try:
        for order_name, profiles in (
            ("forward", endpoint_ab.PROFILES),
            ("reverse", tuple(reversed(endpoint_ab.PROFILES))),
        ):
            for mode in ("gate_compat", "runtime_direct"):
                for profile in profiles:
                    segmented, segmentation = endpoint_ab._segment(  # noqa: SLF001
                        engine._vad,  # noqa: SLF001
                        pcm,
                        profile,
                        runtime_pre_roll=mode == "runtime_direct",
                    )
                    asr_input = segmented if segmented is not None else pcm
                    if profile.asr_pad_frames:
                        asr_input = np.concatenate(
                            (
                                asr_input,
                                np.zeros(
                                    profile.asr_pad_frames
                                    * endpoint_ab.WINDOW_SAMPLES,
                                    dtype=np.float32,
                                ),
                            )
                        )
                    decoded = endpoint_ab._decode(  # noqa: SLF001
                        engine,
                        router,
                        wake_matcher,
                        private_case,
                        asr_input,
                    )
                    semantics = _redacted_semantics(decoded)
                    observations.append(
                        {
                            "order": order_name,
                            "segmentation_mode": mode,
                            "profile": profile.name,
                            "effective_endpoint_ms": profile.effective_ms,
                            "endpoint_saved_ms": (
                                endpoint_ab.baseline_profile().effective_ms
                                - profile.effective_ms
                            ),
                            "asr_pad_ms": profile.asr_pad_ms,
                            "segmented": segmented is not None,
                            "segment_samples": (
                                int(segmented.size)
                                if segmented is not None
                                else None
                            ),
                            "segment_sha256": (
                                endpoint_ab._sha256_float32(segmented)  # noqa: SLF001
                                if segmented is not None
                                else None
                            ),
                            "asr_input_samples": int(asr_input.size),
                            "asr_input_sha256": (
                                endpoint_ab._sha256_float32(asr_input)  # noqa: SLF001
                            ),
                            "decode_ms": decoded["decode_ms"],
                            "semantic_sha256": _secret_hash(semantics),
                            **semantics,
                            **segmentation,
                        }
                    )
    finally:
        engine.shutdown()

    baseline_name = endpoint_ab.baseline_profile().name
    baseline_by_mode: dict[str, list[dict[str, Any]]] = {}
    for mode in ("gate_compat", "runtime_direct"):
        baseline_by_mode[mode] = [
            row
            for row in observations
            if row["segmentation_mode"] == mode
            and row["profile"] == baseline_name
        ]

    summaries = []
    for profile in endpoint_ab.PROFILES:
        matching = [
            row for row in observations if row["profile"] == profile.name
        ]
        semantic_matches = []
        input_matches = []
        for row in matching:
            baselines = baseline_by_mode[row["segmentation_mode"]]
            semantic_matches.append(
                bool(baselines)
                and all(
                    row["semantic_sha256"] == base["semantic_sha256"]
                    for base in baselines
                )
            )
            input_matches.append(
                bool(baselines)
                and all(
                    row["asr_input_sha256"] == base["asr_input_sha256"]
                    for base in baselines
                )
            )
        summaries.append(
            {
                "profile": profile.name,
                "effective_endpoint_ms": profile.effective_ms,
                "endpoint_saved_ms": (
                    endpoint_ab.baseline_profile().effective_ms
                    - profile.effective_ms
                ),
                "asr_pad_ms": profile.asr_pad_ms,
                "observations": len(matching),
                "segmented_both_orders_modes": bool(matching)
                and all(row["segmented"] for row in matching),
                "exact_redacted_semantics_vs_baseline": (
                    bool(semantic_matches) and all(semantic_matches)
                ),
                "byte_exact_asr_input_vs_baseline": (
                    bool(input_matches) and all(input_matches)
                ),
                "baseline_and_candidate_have_decision": bool(matching)
                and all(row["has_decision"] for row in matching),
            }
        )

    report = {
        "schema": "baxy-private-voice-endpointing-ab-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "clip_path_recorded": False,
            "transcript_recorded": False,
            "routed_text_recorded": False,
            "operation_recorded": False,
            "audio_copied": False,
        },
        "clip": {
            "file_sha256": clip_file_sha256,
            "pcm_sha256": pcm_sha256,
            "samples_at_16khz": int(pcm.size),
        },
        "summary": summaries,
        "observations": observations,
        "limitations": [
            "One historical private clip is not a held-out multi-speaker corpus.",
            "No expected transcript or route is disclosed or asserted.",
            "No configuration is promoted by this replay.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    clip = Path(arguments.clip).resolve()
    if not clip.is_file():
        raise FileNotFoundError("private voice clip is unavailable")
    output = endpoint_ab._safe_output_path(arguments.output)  # noqa: SLF001
    report = run(clip, output)
    print(
        json.dumps(
            {
                "output": str(output.relative_to(endpoint_ab.REPO)),
                "privacy": report["privacy"],
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
