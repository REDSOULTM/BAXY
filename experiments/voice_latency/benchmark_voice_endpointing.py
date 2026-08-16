"""Paired, non-microphone endpointing benchmark for BAXY voice.

This experiment synthesizes every canonical voice-gate utterance exactly once
and replays the same float32 PCM through every endpoint profile.  It never
starts microphone capture, changes the registered runtime, or overwrites a
product gate.  Results may only be written below ``artifacts/fixes``.

The two orders balance one-time cache and thermal effects.  Promotion is
deliberately stricter than the historical gate: every candidate must preserve
the baseline transcript, corrected routing text, routing decision, and 6/6
quality in both orders while reducing the quantized endpoint wait.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import test_mind_voice as canonical_gate  # noqa: E402

from baxy_mind.router import IntentRouter  # noqa: E402
from baxy_mind.voice import (  # noqa: E402
    PRE_ROLL_S,
    SAMPLE_RATE,
    SPEECH_THRESHOLD,
    TRAILING_SILENCE_S,
    VoiceEngine,
    WakePhraseMatcher,
)

WINDOW_SAMPLES = 512
BASELINE_REQUESTED_MS = round(TRAILING_SILENCE_S * 1000)
OUTPUT_ROOT = (REPO / "artifacts" / "fixes").resolve()


@dataclass(frozen=True)
class EndpointProfile:
    name: str
    requested_ms: int
    pad_asr_to_baseline: bool = False

    @property
    def endpoint_frames(self) -> int:
        return max(
            1,
            int((self.requested_ms / 1000) * SAMPLE_RATE / WINDOW_SAMPLES),
        )

    @property
    def effective_ms(self) -> int:
        return round(self.endpoint_frames * WINDOW_SAMPLES * 1000 / SAMPLE_RATE)

    @property
    def asr_pad_frames(self) -> int:
        if not self.pad_asr_to_baseline:
            return 0
        return max(0, baseline_profile().endpoint_frames - self.endpoint_frames)

    @property
    def asr_pad_ms(self) -> int:
        return round(self.asr_pad_frames * WINDOW_SAMPLES * 1000 / SAMPLE_RATE)


def baseline_profile() -> EndpointProfile:
    return EndpointProfile("baseline_700", BASELINE_REQUESTED_MS)


PROFILES = (
    baseline_profile(),
    EndpointProfile("candidate_650", 650),
    EndpointProfile("candidate_600", 600),
    EndpointProfile("candidate_500", 500),
    EndpointProfile("candidate_500_asr_pad", 500, pad_asr_to_baseline=True),
)


@dataclass(frozen=True)
class SynthesizedCase:
    index: int
    language: str
    reference: str
    expected_kind: str
    expected_operation: str
    expected_arguments: dict[str, Any] | None
    requires_wake: bool
    pcm: np.ndarray
    pcm_sha256: str


def _sha256_float32(audio: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(audio, dtype=np.float32)
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


def _git_value(*arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _safe_output_path(raw: str) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = REPO / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(OUTPUT_ROOT)
    except ValueError as error:
        raise ValueError(
            f"--output must remain below {OUTPUT_ROOT}"
        ) from error
    if resolved.suffix.casefold() != ".json":
        raise ValueError("--output must be a .json file")
    return resolved


def synthesize_cases() -> list[SynthesizedCase]:
    """Create each canonical waveform once; all profiles share the same object."""

    cases: list[SynthesizedCase] = []
    for index, (
        language,
        voice_code,
        reference,
        expected,
        requires_wake,
    ) in enumerate(canonical_gate.CASES):
        expected_kind, expected_operation, expected_arguments = expected
        pcm = np.ascontiguousarray(
            canonical_gate.synthesize(voice_code, reference),
            dtype=np.float32,
        )
        pcm.setflags(write=False)
        cases.append(
            SynthesizedCase(
                index=index,
                language=language,
                reference=reference,
                expected_kind=expected_kind,
                expected_operation=expected_operation,
                expected_arguments=expected_arguments,
                requires_wake=requires_wake,
                pcm=pcm,
                pcm_sha256=_sha256_float32(pcm),
            )
        )
    return cases


def _segment(
    vad: Any,
    audio: np.ndarray,
    profile: EndpointProfile,
    *,
    runtime_pre_roll: bool,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    """Replay one immutable waveform through the production VAD adapter."""

    vad.reset()
    window = int(vad.window_size_samples)
    if window != WINDOW_SAMPLES:
        raise RuntimeError(
            f"unexpected Silero window: {window}, expected {WINDOW_SAMPLES}"
        )
    padded = np.concatenate(
        (
            np.zeros(SAMPLE_RATE // 2, dtype=np.float32),
            audio,
            np.zeros(
                int(SAMPLE_RATE * (TRAILING_SILENCE_S + 0.4)),
                dtype=np.float32,
            ),
        )
    )
    pre_roll: deque[np.ndarray] = deque(
        maxlen=max(1, int(PRE_ROLL_S * SAMPLE_RATE / window))
    )
    utterance: list[np.ndarray] = []
    speech_started = False
    silence_frames = 0
    first_speech_frame: int | None = None
    last_speech_frame: int | None = None
    terminal_frame: int | None = None
    probability_min = 1.0
    probability_max = 0.0
    for frame_index, start in enumerate(range(0, len(padded) - window, window)):
        frame = padded[start : start + window]
        probability = vad.process(frame)
        probability_min = min(probability_min, probability)
        probability_max = max(probability_max, probability)
        if probability >= SPEECH_THRESHOLD:
            if not speech_started:
                speech_started = True
                first_speech_frame = frame_index
                if runtime_pre_roll:
                    utterance.extend(pre_roll)
                pre_roll.clear()
            last_speech_frame = frame_index
            silence_frames = 0
            utterance.append(frame)
        elif speech_started:
            silence_frames += 1
            utterance.append(frame)
            if silence_frames >= profile.endpoint_frames:
                terminal_frame = frame_index
                break
        elif runtime_pre_roll:
            pre_roll.append(frame)

    segmented = np.concatenate(utterance) if utterance else None
    return segmented, {
        "speech_started": speech_started,
        "first_speech_frame": first_speech_frame,
        "last_speech_frame": last_speech_frame,
        "terminal_frame": terminal_frame,
        "terminal_silence_frames": silence_frames,
        "probability_min": round(probability_min, 6),
        "probability_max": round(probability_max, 6),
    }


def _decode(
    engine: VoiceEngine,
    router: IntentRouter,
    wake_matcher: WakePhraseMatcher,
    case: SynthesizedCase,
    audio: np.ndarray,
) -> dict[str, Any]:
    recognizer = engine._recognizer  # noqa: SLF001 - isolated product-path gate
    if recognizer is None:
        raise RuntimeError("offline recognizer did not load")
    started = time.perf_counter()
    stream = recognizer.create_stream()
    stream.accept_waveform(SAMPLE_RATE, audio)
    recognizer.decode_stream(stream)
    transcript = (stream.result.text or "").strip()
    decode_ms = (time.perf_counter() - started) * 1000

    wake_matched, command = wake_matcher.strip(transcript)
    routed_text = (
        command if case.requires_wake and wake_matched else transcript
    )
    corrector = engine._corrector  # noqa: SLF001 - same canonical gate seam
    if transcript and corrector is not None:
        routed_text = corrector.correct(routed_text)
    decision = router.route(routed_text) if routed_text else None
    route_ok = (
        decision is not None
        and decision.kind == case.expected_kind
        and decision.operation == case.expected_operation
        and (
            case.expected_arguments is None
            or decision.arguments == case.expected_arguments
        )
    )
    return {
        "transcript": transcript,
        "routed_text": routed_text,
        "wake_prefix_cleaned": wake_matched,
        "text_match_normalized": (
            canonical_gate.normalize(transcript)
            == canonical_gate.normalize(case.reference)
        ),
        "routed_kind": decision.kind if decision else None,
        "routed_operation": decision.operation if decision else None,
        "routed_arguments": decision.arguments if decision else None,
        "route_ok": route_ok,
        "decode_ms": round(decode_ms, 3),
    }


def _semantic_signature(row: dict[str, Any]) -> str:
    fields = {
        "segmented": row["segmented"],
        "transcript": row["transcript"],
        "routed_text": row["routed_text"],
        "wake_prefix_cleaned": row["wake_prefix_cleaned"],
        "text_match_normalized": row["text_match_normalized"],
        "routed_kind": row["routed_kind"],
        "routed_operation": row["routed_operation"],
        "routed_arguments": row["routed_arguments"],
        "route_ok": row["route_ok"],
    }
    return json.dumps(fields, ensure_ascii=False, sort_keys=True)


def _summarize(
    rows: list[dict[str, Any]],
    profiles: tuple[EndpointProfile, ...],
    modes: tuple[str, ...],
) -> dict[str, Any]:
    baseline_name = baseline_profile().name
    by_key: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["profile"] == baseline_name:
            by_key[(row["segmentation_mode"], row["case_index"])].append(row)

    canonical_signatures: dict[tuple[str, int], str] = {}
    baseline_stability: list[dict[str, Any]] = []
    for mode in modes:
        for case_index in range(len(canonical_gate.CASES)):
            matching = by_key[(mode, case_index)]
            signatures = {_semantic_signature(row) for row in matching}
            stable = len(signatures) == 1 and bool(matching)
            quality = bool(matching) and all(
                row["segmented"] and row["route_ok"] for row in matching
            )
            if stable:
                canonical_signatures[(mode, case_index)] = next(iter(signatures))
            baseline_stability.append(
                {
                    "segmentation_mode": mode,
                    "case_index": case_index,
                    "observations": len(matching),
                    "stable": stable,
                    "quality_ok": quality,
                }
            )

    profile_summaries: list[dict[str, Any]] = []
    for profile in profiles:
        profile_rows = [row for row in rows if row["profile"] == profile.name]
        exact_rows = []
        for row in profile_rows:
            signature = canonical_signatures.get(
                (row["segmentation_mode"], row["case_index"])
            )
            exact_rows.append(
                signature is not None and _semantic_signature(row) == signature
            )
        baseline_is_stable = all(item["stable"] for item in baseline_stability)
        strict_quality = bool(profile_rows) and all(
            row["segmented"] and row["route_ok"] for row in profile_rows
        )
        exact_baseline = bool(exact_rows) and all(exact_rows)
        saves_endpoint = (
            profile.effective_ms < baseline_profile().effective_ms
        )
        promotable = (
            profile.name != baseline_name
            and baseline_is_stable
            and strict_quality
            and exact_baseline
            and saves_endpoint
        )
        decode_values = [float(row["decode_ms"]) for row in profile_rows]
        post_speech_values = [
            profile.effective_ms + float(row["decode_ms"])
            for row in profile_rows
        ]
        profile_summaries.append(
            {
                **asdict(profile),
                "endpoint_frames": profile.endpoint_frames,
                "effective_ms": profile.effective_ms,
                "endpoint_saved_ms": (
                    baseline_profile().effective_ms - profile.effective_ms
                ),
                "asr_pad_frames": profile.asr_pad_frames,
                "asr_pad_ms": profile.asr_pad_ms,
                "observations": len(profile_rows),
                "strict_quality_6_of_6_both_orders": strict_quality,
                "exact_baseline_semantics_both_orders": exact_baseline,
                "median_decode_ms": (
                    round(statistics.median(decode_values), 3)
                    if decode_values
                    else None
                ),
                "median_estimated_post_speech_ms": (
                    round(statistics.median(post_speech_values), 3)
                    if post_speech_values
                    else None
                ),
                "promotable_on_synthetic_gate": promotable,
                "promotion_scope": (
                    "synthetic evidence only; held-out/private microphone "
                    "evidence remains mandatory"
                ),
            }
        )
    return {
        "baseline_stability": baseline_stability,
        "profiles": profile_summaries,
        "synthetic_winners": [
            item["name"]
            for item in profile_summaries
            if item["promotable_on_synthetic_gate"]
        ],
    }


def run(
    *,
    output: Path,
    modes: tuple[str, ...],
    repeats: int,
) -> dict[str, Any]:
    synthesized_at = datetime.now(timezone.utc)
    cases = synthesize_cases()
    # Assert identity by object and digest before any model is loaded.
    if len({case.pcm_sha256 for case in cases}) != len(cases):
        raise RuntimeError("unexpected duplicate canonical waveforms")

    engine = VoiceEngine(lambda _text: None)
    load_started = time.perf_counter()
    engine.load()
    load_ms = (time.perf_counter() - load_started) * 1000
    if engine._vad is None:  # noqa: SLF001
        raise RuntimeError("Silero VAD did not load")
    router = IntentRouter()
    wake_matcher = WakePhraseMatcher()
    rows: list[dict[str, Any]] = []
    orders = (
        ("forward", PROFILES),
        ("reverse", tuple(reversed(PROFILES))),
    )
    try:
        for repeat in range(repeats):
            for order_name, ordered_profiles in orders:
                for mode in modes:
                    runtime_pre_roll = mode == "runtime_direct"
                    for case in cases:
                        for profile in ordered_profiles:
                            segmented, segmentation = _segment(
                                engine._vad,  # noqa: SLF001
                                case.pcm,
                                profile,
                                runtime_pre_roll=runtime_pre_roll,
                            )
                            asr_input = (
                                segmented
                                if segmented is not None
                                else np.asarray(case.pcm, dtype=np.float32)
                            )
                            if profile.asr_pad_frames:
                                asr_input = np.concatenate(
                                    (
                                        asr_input,
                                        np.zeros(
                                            profile.asr_pad_frames
                                            * WINDOW_SAMPLES,
                                            dtype=np.float32,
                                        ),
                                    )
                                )
                            decoded = _decode(
                                engine,
                                router,
                                wake_matcher,
                                case,
                                asr_input,
                            )
                            rows.append(
                                {
                                    "repeat": repeat,
                                    "order": order_name,
                                    "segmentation_mode": mode,
                                    "case_index": case.index,
                                    "language": case.language,
                                    "reference": case.reference,
                                    "pcm_sha256": case.pcm_sha256,
                                    "profile": profile.name,
                                    "requested_ms": profile.requested_ms,
                                    "effective_endpoint_ms": profile.effective_ms,
                                    "endpoint_saved_ms": (
                                        baseline_profile().effective_ms
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
                                        _sha256_float32(segmented)
                                        if segmented is not None
                                        else None
                                    ),
                                    "asr_input_samples": int(asr_input.size),
                                    "asr_input_sha256": _sha256_float32(asr_input),
                                    **segmentation,
                                    **decoded,
                                    "estimated_post_speech_ms": round(
                                        profile.effective_ms
                                        + float(decoded["decode_ms"]),
                                        3,
                                    ),
                                }
                            )
    finally:
        engine.shutdown()

    summary = _summarize(rows, PROFILES, modes)
    report = {
        "schema": "baxy-voice-endpointing-ab-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "synthesized_at": synthesized_at.isoformat(),
        "source": {
            "commit": _git_value("rev-parse", "HEAD"),
            "dirty": bool(_git_value("status", "--porcelain")),
            "canonical_cases": "scripts/test_mind_voice.py::CASES",
        },
        "runtime": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "silero_vad": _package_version("silero-vad"),
            "torch": _package_version("torch"),
            "sherpa_onnx": _package_version("sherpa-onnx"),
            "engine_load_ms": round(load_ms, 3),
            "stt_model": engine.status().get("sttModel"),
        },
        "contract": {
            "sample_rate": SAMPLE_RATE,
            "vad_window_samples": WINDOW_SAMPLES,
            "vad_frame_ms": WINDOW_SAMPLES * 1000 / SAMPLE_RATE,
            "speech_threshold": SPEECH_THRESHOLD,
            "production_requested_trailing_silence_ms": BASELINE_REQUESTED_MS,
            "production_effective_trailing_silence_ms": (
                baseline_profile().effective_ms
            ),
            "pcm_reuse": "each case synthesized once and replayed unchanged",
            "orders": ["forward", "reverse"],
            "modes": list(modes),
            "repeats": repeats,
            "strict_gate": (
                "segmentation + transcript + corrected text + route decision "
                "equal baseline, route quality 6/6 in both orders"
            ),
        },
        "profiles": [
            {
                **asdict(profile),
                "endpoint_frames": profile.endpoint_frames,
                "effective_ms": profile.effective_ms,
                "asr_pad_frames": profile.asr_pad_frames,
                "asr_pad_ms": profile.asr_pad_ms,
            }
            for profile in PROFILES
        ],
        "case_pcm": [
            {
                "case_index": case.index,
                "language": case.language,
                "samples": int(case.pcm.size),
                "sha256": case.pcm_sha256,
            }
            for case in cases
        ],
        "summary": summary,
        "observations": rows,
        "limitations": [
            "Synthetic Windows SAPI is paired evidence, not held-out room audio.",
            "Estimated post-speech latency adds quantized endpoint wait to decode time.",
            "The ASR-padding profile pads after segmentation/AEC; it does not delay capture.",
            "No profile is promoted by this experiment alone.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        help="JSON path below artifacts/fixes (product gates are forbidden)",
    )
    parser.add_argument(
        "--mode",
        action="append",
        choices=("gate_compat", "runtime_direct"),
        dest="modes",
        help="repeatable; default tests canonical-gate and production pre-roll",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="paired forward/reverse repetitions (default: 1)",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    if arguments.repeats < 1 or arguments.repeats > 10:
        raise ValueError("--repeats must be between 1 and 10")
    modes = tuple(arguments.modes or ("gate_compat", "runtime_direct"))
    output = _safe_output_path(arguments.output)
    report = run(output=output, modes=modes, repeats=arguments.repeats)
    compact = {
        "output": str(output.relative_to(REPO)),
        "summary": report["summary"],
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
