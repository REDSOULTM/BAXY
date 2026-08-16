"""Evaluate a rolling same-window multi-pronunciation wake consensus gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_baxy_hyperspotter_fusion_product_candidate_v1 as hyper  # noqa: E402
import audit_raw_denoiser_rolling_wake_v1 as rolling  # noqa: E402
import evaluate_raw_lexical_hyperspotter_wake_corpus_v1 as fixed_gate  # noqa: E402
import evaluate_raw_lexical_fusion_wake_corpus_v1 as summaries  # noqa: E402
import run_multiverifier_wake_physical_room_gate_v1 as multi  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402


SCHEMA = "baxy.raw-rolling-multialias-wake-corpus-development.v2"
SAMPLE_RATE = 16_000
PRIMARY_LOGIT = 0.5
SECONDARY_LOGIT = 0.3


def same_window_consensus(
    logits: np.ndarray,
    *,
    primary_threshold: float = PRIMARY_LOGIT,
    secondary_threshold: float = SECONDARY_LOGIT,
) -> tuple[bool, int | None, float, float]:
    values = np.asarray(logits, dtype=np.float32)
    if values.ndim != 2 or values.shape[1] < 2 or not np.isfinite(values).all():
        raise ValueError("rolling_multialias_logits_invalid")
    ordered = np.sort(values, axis=1)
    primary = ordered[:, -1]
    secondary = ordered[:, -2]
    eligible = np.flatnonzero(
        (primary >= primary_threshold) & (secondary >= secondary_threshold)
    )
    if eligible.size:
        index = int(eligible[0])
        return True, index, float(primary[index]), float(secondary[index])
    closest = int(np.argmax(secondary))
    return False, None, float(primary[closest]), float(secondary[closest])


def continuous_rolling_windows(audio: np.ndarray) -> list[np.ndarray]:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.size == 0 or not np.isfinite(values).all():
        raise ValueError("continuous_rolling_audio_invalid")
    padded = np.pad(
        values,
        (rolling.SIDE_PADDING_SAMPLES, rolling.SIDE_PADDING_SAMPLES),
        mode="constant",
    )
    if padded.size < rolling.WINDOW_SAMPLES:
        padded = np.pad(padded, (0, rolling.WINDOW_SAMPLES - padded.size))
    final_start = padded.size - rolling.WINDOW_SAMPLES
    starts = list(range(0, final_start + 1, rolling.HOP_SAMPLES))
    if starts[-1] != final_start:
        starts.append(final_start)
    return [
        np.ascontiguousarray(padded[start : start + rolling.WINDOW_SAMPLES])
        for start in starts
    ]


class RollingMultiAliasSpotter(fixed_gate.FastHyperspotter):
    def score_aliases(self, audio: np.ndarray) -> np.ndarray:
        values = multi.fixed_three_second_audio(audio)
        logmel = hyper.numpy_log_mel_spectrogram(values, self._mel_filters)
        logits = self._session.run(
            ["logits"],
            {"logmel": logmel[None, :, :]},
        )[0]
        if logits.shape != (1, len(hyper.ALIASES)) or not np.isfinite(logits).all():
            raise ValueError("raw_rolling_multialias_logits_invalid")
        return np.asarray(logits[0], dtype=np.float32)

    def decide(self, audio: np.ndarray) -> tuple[bool, int | None, float, float]:
        windows = continuous_rolling_windows(audio)
        logits = np.stack([self.score_aliases(window) for window in windows])
        return same_window_consensus(logits)


def _evaluate_group(
    paths: list[Path], *, verifier: RollingMultiAliasSpotter
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    availability: list[float] = []
    for index, path in enumerate(paths):
        audio, sample_rate = room._read_pcm16(path)
        audio = room._resample(audio, sample_rate, SAMPLE_RATE)
        started = time.perf_counter()
        accepted, window_index, primary, secondary = verifier.decide(audio)
        latency = time.perf_counter() - started
        latencies.append(latency)
        if window_index is not None:
            availability.append(2.0 + window_index * rolling.HOP_SAMPLES / SAMPLE_RATE)
        records.append(
            {
                "record": index,
                "audioSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "accepted": accepted,
                "firstAcceptedWindowIndex": window_index,
                "candidateAvailableAtClipSeconds": (
                    None
                    if window_index is None
                    else 2.0 + window_index * rolling.HOP_SAMPLES / SAMPLE_RATE
                ),
                "primaryLogit": primary,
                "secondaryLogit": secondary,
            }
        )
    return {
        "files": len(paths),
        "acceptedFiles": sum(bool(record["accepted"]) for record in records),
        "decisionSeconds": summaries._summary(latencies),
        "candidateAvailableAtClipSeconds": (
            summaries._summary(availability) if availability else None
        ),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--role", choices=("development", "validation"), required=True
    )
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpus = args.corpus.resolve(strict=True)
    manifest_path = corpus / "manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("blindHumanPartitionAccessed") is not False:
        raise SystemExit("Corpus blind-boundary attestation is missing.")
    if manifest.get("physicalPath", {}).get("captureTransport") != "wasapi_raw_iaudioclient2":
        raise SystemExit("Corpus is not an attested WASAPI RAW capture.")

    verifier = RollingMultiAliasSpotter(
        args.fusion_manifest.resolve(strict=True),
        args.ctc_verifier_manifest.resolve(strict=True),
    )
    started = time.perf_counter()
    positive = _evaluate_group(
        room._wav_paths(corpus / "positive", None), verifier=verifier
    )
    negative = _evaluate_group(
        room._wav_paths(corpus / "negative", None), verifier=verifier
    )
    passed = positive["acceptedFiles"] == positive["files"] and negative["acceptedFiles"] == 0
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_known_playback_wasapi_raw_rolling_same_window_multialias",
        "role": args.role,
        "policy": {
            "aliases": list(hyper.ALIASES),
            "rollingWindowSeconds": 3.0,
            "sidePaddingSeconds": 1.0,
            "hopSeconds": rolling.HOP_SAMPLES / SAMPLE_RATE,
            "sameWindowPrimaryLogitGte": PRIMARY_LOGIT,
            "sameWindowSecondaryLogitGte": SECONDARY_LOGIT,
            "lexicalAsrRequired": False,
        },
        "models": {"hyperspotter": verifier.identities},
        "corpusManifestSha256": room._sha256(manifest_path),
        "positive": positive,
        "negative": negative,
        "elapsedWallSeconds": time.perf_counter() - started,
        "openedCorpusPassed": passed,
        "candidateFrozen": passed and args.role == "development",
        "blindHumanPartitionAccessed": False,
        "promotable": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
        "filenamesOrTranscriptsRetained": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "passed": passed,
                "positive": positive["acceptedFiles"],
                "negative": negative["acceptedFiles"],
                "latencyP50": positive["decisionSeconds"]["p50"],
                "latencyP95": positive["decisionSeconds"]["p95"],
                "candidateAvailableP95": positive[
                    "candidateAvailableAtClipSeconds"
                ]["p95"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
