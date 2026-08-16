"""Exercise opened R16 commands through SAPI, VAD, Parakeet, and semantics.

This is a development-scale post-wake gate, not human-microphone evidence.
Only the plain, Mind-owned R16 surfaces are used.  A case is scored only when
the deterministic product effect boundary resolves its original text to the
published R16 contract; LLM-only originals are counted but kept outside the
STT score so router coverage cannot be confused with transcription quality.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import time
import unicodedata
import wave

import numpy as np


SAMPLE_RATE = 16_000
TRAILING_SILENCE_SECONDS = 0.7
PRE_ROLL_SECONDS = 0.256
SPEECH_THRESHOLD = 0.5
EXPECTED_CORPUS_ROWS = 700
EXPECTED_PLAIN_MIND_ROWS = 344
EXPECTED_BASELINE_ELIGIBLE_ROWS = 337
EXPECTED_BASELINE_ELIGIBLE_COMPOSITIONS = 100
TARGET_ACCURACY = 0.99
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_words(value: str) -> tuple[str, ...]:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    plain = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return tuple(_WORD_RE.findall(plain))


def edit_distance(left: tuple[str, ...], right: tuple[str, ...]) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def one_sided_lower_if_zero_failures(count: int, alpha: float = 0.05) -> float:
    if count < 1 or not 0.0 < alpha < 1.0:
        raise ValueError("baxy_sapi_voice_confidence_contract_invalid")
    return math.pow(alpha, 1.0 / count)


def accepted_effect_sets(row: dict[str, object]) -> set[tuple[str, ...]]:
    raw = row.get("compatible_effect_operation_sets")
    if not isinstance(raw, list):
        raise ValueError("baxy_sapi_voice_effect_sets_invalid")
    values = set()
    for item in raw:
        if not isinstance(item, list) or not all(isinstance(value, str) for value in item):
            raise ValueError("baxy_sapi_voice_effect_set_invalid")
        values.add(tuple(item))
    return values


def read_rows(path: Path) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if (
        len(rows) != EXPECTED_CORPUS_ROWS
        or any(not isinstance(row, dict) for row in rows)
        or any(row.get("schema") != "baxy.generalization-product-holdout.v16" for row in rows)
        or any(row.get("execution_authority") is not False for row in rows)
    ):
        raise ValueError("baxy_sapi_voice_corpus_invalid")
    selected = [
        row
        for row in rows
        if row.get("surface") == "plain" and row.get("owner") == "mind_sidecar"
    ]
    if (
        len(selected) != EXPECTED_PLAIN_MIND_ROWS
        or len({str(row.get("case_id")) for row in selected}) != len(selected)
    ):
        raise ValueError("baxy_sapi_voice_population_invalid")
    return selected


class SapiSynthesizer:
    """Reuse one local COM voice while producing isolated PCM clips."""

    def __init__(self) -> None:
        import pythoncom
        import win32com.client

        self._pythoncom = pythoncom
        self._client = win32com.client
        pythoncom.CoInitialize()
        self._voice = win32com.client.Dispatch("SAPI.SpVoice")
        self._tokens = tuple(self._voice.GetVoices())
        self.voice_names: dict[str, str] = {}

    def close(self) -> None:
        self._voice = None
        self._tokens = ()
        self._pythoncom.CoUninitialize()

    def _token(self, language_code: str):
        token = next(
            candidate
            for candidate in self._tokens
            if str(candidate.GetAttribute("Language")).upper() == language_code
        )
        self.voice_names.setdefault(language_code, str(token.GetDescription()))
        return token

    def synthesize(self, language_code: str, text: str, *, rate: int) -> np.ndarray:
        temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        path = Path(temporary.name)
        temporary.close()
        try:
            self._voice.Voice = self._token(language_code)
            self._voice.Rate = rate
            stream = self._client.Dispatch("SAPI.SpFileStream")
            stream.Open(str(path), 3, False)
            self._voice.AudioOutputStream = stream
            self._voice.Speak(text)
            stream.Close()
            with wave.open(str(path), "rb") as source:
                source_rate = source.getframerate()
                channels = source.getnchannels()
                if source.getsampwidth() != 2:
                    raise RuntimeError("baxy_sapi_voice_pcm_width_invalid")
                audio = np.frombuffer(
                    source.readframes(source.getnframes()), dtype=np.int16
                )
            if channels > 1:
                audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
            values = audio.astype(np.float32) / 32768.0
        finally:
            path.unlink(missing_ok=True)
        if source_rate != SAMPLE_RATE:
            target = int(round(len(values) * SAMPLE_RATE / source_rate))
            values = np.interp(
                np.linspace(0, len(values) - 1, target),
                np.arange(len(values)),
                values,
            ).astype(np.float32)
        return values


def segment_with_product_vad(
    vad: object,
    audio: np.ndarray,
    *,
    trailing_silence_seconds: float = TRAILING_SILENCE_SECONDS,
    retained_trailing_silence_seconds: float | None = None,
) -> np.ndarray | None:
    if not math.isfinite(trailing_silence_seconds) or trailing_silence_seconds <= 0:
        raise ValueError("baxy_sapi_voice_trailing_silence_invalid")
    retained_seconds = (
        trailing_silence_seconds
        if retained_trailing_silence_seconds is None
        else retained_trailing_silence_seconds
    )
    if (
        not math.isfinite(retained_seconds)
        or retained_seconds <= 0
        or retained_seconds > trailing_silence_seconds
    ):
        raise ValueError("baxy_sapi_voice_retained_silence_invalid")
    vad.reset()
    window = int(vad.window_size_samples)
    leading = np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
    trailing = np.zeros(
        int(SAMPLE_RATE * (trailing_silence_seconds + 0.4)), dtype=np.float32
    )
    padded = np.concatenate((leading, np.asarray(audio, np.float32), trailing))
    pre_roll_frames = max(1, round(PRE_ROLL_SECONDS * SAMPLE_RATE / window))
    history: deque[np.ndarray] = deque(maxlen=pre_roll_frames)
    utterance: list[np.ndarray] = []
    speech_started = False
    silence = 0
    silence_frames = max(
        1,
        round(trailing_silence_seconds * SAMPLE_RATE / window),
    )
    retained_silence_frames = max(1, round(retained_seconds * SAMPLE_RATE / window))
    for start in range(0, len(padded) - window + 1, window):
        frame = padded[start : start + window]
        probability = float(vad.process(frame))
        if not speech_started:
            if probability >= SPEECH_THRESHOLD:
                speech_started = True
                utterance.extend(history)
                utterance.append(frame)
            else:
                history.append(frame)
            continue
        utterance.append(frame)
        if probability >= SPEECH_THRESHOLD:
            silence = 0
        else:
            silence += 1
            if silence >= silence_frames:
                discarded = max(0, silence - retained_silence_frames)
                if discarded:
                    del utterance[-discarded:]
                return np.concatenate(utterance)
    return np.concatenate(utterance) if utterance else None


def empty_checkpoint(identities: dict[str, str]) -> dict[str, object]:
    return {
        "schema": "baxy.r16-sapi-voice-semantics-checkpoint.v1",
        "identities": identities,
        "completedRecords": 0,
        "results": [],
        "synthesisSeconds": 0.0,
        "decodeSeconds": 0.0,
        "audioSeconds": 0.0,
    }


def write_checkpoint(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def evaluate(
    *,
    corpus_path: Path,
    stt_directory: Path,
    output_path: Path,
    trailing_silence_seconds: float = TRAILING_SILENCE_SECONDS,
    retained_trailing_silence_seconds: float | None = None,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("baxy_sapi_voice_output_exists")
    corpus_path = corpus_path.resolve(strict=True)
    stt_directory = stt_directory.resolve(strict=True)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = read_rows(corpus_path)
    stt_files = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt")
    for name in stt_files:
        (stt_directory / name).resolve(strict=True)
    identities = {
        "corpusSha256": sha256(corpus_path),
        "trailingSilenceSeconds": str(trailing_silence_seconds),
        "retainedTrailingSilenceSeconds": str(
            trailing_silence_seconds
            if retained_trailing_silence_seconds is None
            else retained_trailing_silence_seconds
        ),
        **{f"stt:{name}": sha256(stt_directory / name) for name in stt_files},
    }

    from baxy_mind.effect_intent import resolve_explicit_effects
    from baxy_mind.voice import SileroVad
    import sherpa_onnx

    available_operations = frozenset(
        operation
        for row in rows
        for accepted in accepted_effect_sets(row)
        for operation in accepted
    )
    baseline_eligible: list[dict[str, object]] = []
    baseline_ineligible: list[str] = []
    for row in rows:
        intent = resolve_explicit_effects(str(row["text"]), available_operations)
        operations = tuple(intent.operations) if intent is not None else ()
        if operations in accepted_effect_sets(row):
            baseline_eligible.append(row)
        else:
            baseline_ineligible.append(str(row["case_id"]))
    if (
        len(baseline_eligible) != EXPECTED_BASELINE_ELIGIBLE_ROWS
        or sum(row.get("case_type") == "composition" for row in baseline_eligible)
        != EXPECTED_BASELINE_ELIGIBLE_COMPOSITIONS
    ):
        raise ValueError("baxy_sapi_voice_baseline_coverage_drift")

    checkpoint_path = output_path.with_suffix(output_path.suffix + ".partial.json")
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            checkpoint.get("schema")
            != "baxy.r16-sapi-voice-semantics-checkpoint.v1"
            or checkpoint.get("identities") != identities
            or not isinstance(checkpoint.get("completedRecords"), int)
            or not isinstance(checkpoint.get("results"), list)
            or checkpoint["completedRecords"] != len(checkpoint["results"])
        ):
            raise ValueError("baxy_sapi_voice_checkpoint_invalid")
    else:
        checkpoint = empty_checkpoint(identities)

    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(stt_directory / "encoder.int8.onnx"),
        decoder=str(stt_directory / "decoder.int8.onnx"),
        joiner=str(stt_directory / "joiner.int8.onnx"),
        tokens=str(stt_directory / "tokens.txt"),
        num_threads=6,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
        hotwords_score=5.0,
    )
    warmup = recognizer.create_stream()
    warmup.accept_waveform(SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, np.float32))
    recognizer.decode_stream(warmup)
    vad = SileroVad()
    synthesizer = SapiSynthesizer()
    try:
        start_at = int(checkpoint["completedRecords"])
        for index, row in enumerate(baseline_eligible[start_at:], start=start_at):
            synthesis_started = time.perf_counter()
            language = str(row["language"])
            audio = synthesizer.synthesize(
                "409" if language == "en" else "80A",
                str(row["text"]),
                rate=(-1, 0, 1)[index % 3],
            )
            checkpoint["synthesisSeconds"] = float(
                checkpoint["synthesisSeconds"]
            ) + (time.perf_counter() - synthesis_started)
            segmented = segment_with_product_vad(
                vad,
                audio,
                trailing_silence_seconds=trailing_silence_seconds,
                retained_trailing_silence_seconds=(
                    retained_trailing_silence_seconds
                ),
            )
            decode_started = time.perf_counter()
            transcript = ""
            if segmented is not None:
                stream = recognizer.create_stream()
                stream.accept_waveform(SAMPLE_RATE, segmented)
                recognizer.decode_stream(stream)
                transcript = str(stream.result.text or "").strip()
            checkpoint["decodeSeconds"] = float(checkpoint["decodeSeconds"]) + (
                time.perf_counter() - decode_started
            )
            checkpoint["audioSeconds"] = float(checkpoint["audioSeconds"]) + (
                len(audio) / SAMPLE_RATE
            )
            intent = (
                resolve_explicit_effects(transcript, available_operations)
                if transcript
                else None
            )
            actual = tuple(intent.operations) if intent is not None else ()
            reference_words = normalized_words(str(row["text"]))
            hypothesis_words = normalized_words(transcript)
            semantic_correct = bool(transcript) and actual in accepted_effect_sets(row)
            checkpoint["results"].append(
                {
                    "caseId": row["case_id"],
                    "caseType": row["case_type"],
                    "language": language,
                    "outcome": row["outcome"],
                    "rate": (-1, 0, 1)[index % 3],
                    "vadSegmented": segmented is not None,
                    "referenceWordCount": len(reference_words),
                    "wordEdits": edit_distance(reference_words, hypothesis_words),
                    "transcript": transcript,
                    "actualOperations": list(actual),
                    "semanticCorrect": semantic_correct,
                    "unsafeEffect": row["outcome"] != "action" and bool(actual),
                }
            )
            checkpoint["completedRecords"] = index + 1
            write_checkpoint(checkpoint_path, checkpoint)
            print(
                f"BAXY_R16_SAPI_VOICE|{checkpoint['completedRecords']}/{len(baseline_eligible)}",
                flush=True,
            )
    finally:
        synthesizer.close()

    results = checkpoint["results"]
    correct = sum(bool(row["semanticCorrect"]) for row in results)
    compositions = [row for row in results if row["caseType"] == "composition"]
    by_type: dict[str, dict[str, object]] = {}
    for name in sorted({str(row["caseType"]) for row in results}):
        group = [row for row in results if row["caseType"] == name]
        by_type[name] = {
            "cases": len(group),
            "correct": sum(bool(row["semanticCorrect"]) for row in group),
            "accuracy": sum(bool(row["semanticCorrect"]) for row in group) / len(group),
        }
    total_words = sum(int(row["referenceWordCount"]) for row in results)
    total_edits = sum(int(row["wordEdits"]) for row in results)
    confidence_lower = (
        one_sided_lower_if_zero_failures(len(results))
        if correct == len(results)
        else None
    )
    checks = {
        "allBaselineEligibleRowsCompleted": len(results)
        == EXPECTED_BASELINE_ELIGIBLE_ROWS,
        "allSemanticRoutesCorrect": correct == len(results),
        "allCompositionsCorrect": sum(
            bool(row["semanticCorrect"]) for row in compositions
        )
        == EXPECTED_BASELINE_ELIGIBLE_COMPOSITIONS,
        "allVadSegmented": all(bool(row["vadSegmented"]) for row in results),
        "allTranscriptsNonEmpty": all(bool(str(row["transcript"]).strip()) for row in results),
        "zeroUnsafeEffects": not any(bool(row["unsafeEffect"]) for row in results),
        "oneSided95LowerSupports99Percent": confidence_lower is not None
        and confidence_lower >= TARGET_ACCURACY,
    }
    report: dict[str, object] = {
        "schema": "baxy.r16-sapi-voice-semantics-development.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_r16_local_sapi_post_wake_vad_parakeet_semantic_route",
        "sources": identities,
        "contract": {
            "openedCorpus": True,
            "plainMindRows": EXPECTED_PLAIN_MIND_ROWS,
            "baselineEligibleRows": EXPECTED_BASELINE_ELIGIBLE_ROWS,
            "baselineIneligibleLlmOnlyRows": len(baseline_ineligible),
            "baselineIneligibleCaseIds": baseline_ineligible,
            "rateCycle": [-1, 0, 1],
            "executionAuthority": False,
            "targetAccuracy": TARGET_ACCURACY,
            "trailingSilenceSeconds": trailing_silence_seconds,
            "retainedTrailingSilenceSeconds": (
                trailing_silence_seconds
                if retained_trailing_silence_seconds is None
                else retained_trailing_silence_seconds
            ),
        },
        "metrics": {
            "cases": len(results),
            "semanticCorrect": correct,
            "semanticAccuracy": correct / len(results),
            "compositionCases": len(compositions),
            "compositionCorrect": sum(
                bool(row["semanticCorrect"]) for row in compositions
            ),
            "wordErrorRate": total_edits / total_words,
            "unsafeEffects": sum(bool(row["unsafeEffect"]) for row in results),
            "oneSided95BinomialLowerIfZeroFailures": confidence_lower,
            "byCaseType": by_type,
            "audioSeconds": checkpoint["audioSeconds"],
            "synthesisSeconds": checkpoint["synthesisSeconds"],
            "decodeSeconds": checkpoint["decodeSeconds"],
            "audioRealtimeFactor": float(checkpoint["decodeSeconds"])
            / float(checkpoint["audioSeconds"]),
        },
        "gate": {"passed": all(checks.values()), "checks": checks},
        "runtime": {
            "stt": "parakeet-tdt-0.6b-v3-int8",
            "vad": "silero-vad-onnx-cpu",
            "sapiVoices": synthesizer.voice_names,
        },
        "rows": results,
        "humanMicrophoneClaimSupported": False,
        "blindHoldoutClaimSupported": False,
        "effectsExecuted": 0,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--trailing-silence-seconds",
        type=float,
        default=TRAILING_SILENCE_SECONDS,
    )
    parser.add_argument("--retained-trailing-silence-seconds", type=float)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        corpus_path=arguments.corpus,
        stt_directory=arguments.stt_directory,
        output_path=arguments.output,
        trailing_silence_seconds=arguments.trailing_silence_seconds,
        retained_trailing_silence_seconds=(
            arguments.retained_trailing_silence_seconds
        ),
    )
    print(json.dumps({"passed": report["gate"]["passed"], "metrics": report["metrics"]}, sort_keys=True))
    return 0 if report["gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
