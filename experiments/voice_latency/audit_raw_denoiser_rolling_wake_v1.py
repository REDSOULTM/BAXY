"""Audit a RAW rolling HyperSpotter cascade with candidate-only denoising.

The first stage runs on the unmodified RAW microphone signal.  Only its best
three-second candidate window is passed to the lexical verifier, optionally
through an official sherpa-onnx speech-enhancement model.  This mirrors the
intended streaming cascade and avoids changing the calibrated acoustic stage.
"""

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

import evaluate_raw_lexical_hyperspotter_wake_corpus_v1 as fixed_gate  # noqa: E402
import evaluate_raw_lexical_fusion_wake_corpus_v1 as lexical_gate  # noqa: E402
import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402


SCHEMA = "baxy.raw-denoiser-rolling-wake-audit.v1"
SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 48_000
SIDE_PADDING_SAMPLES = 16_000
HOP_SAMPLES = 4_000
HYPERSPOTTER_LOGIT = 0.5
MODEL_FILENAMES = (
    "gtcrn_simple.onnx",
    "dpdfnet_baseline.onnx",
    "dpdfnet2.onnx",
    "dpdfnet4.onnx",
    "dpdfnet8.onnx",
)


def rolling_windows(audio: np.ndarray) -> list[np.ndarray]:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if values.shape != (WINDOW_SAMPLES,):
        raise ValueError("rolling_audio_must_be_exactly_three_seconds")
    padded = np.pad(
        values,
        (SIDE_PADDING_SAMPLES, SIDE_PADDING_SAMPLES),
        mode="constant",
    )
    return [
        np.ascontiguousarray(padded[start : start + WINDOW_SAMPLES])
        for start in range(0, 2 * SIDE_PADDING_SAMPLES + 1, HOP_SAMPLES)
    ]


def best_rolling_candidate(
    verifier: fixed_gate.FastHyperspotter, audio: np.ndarray
) -> tuple[np.ndarray, float, int]:
    windows = rolling_windows(audio)
    logits = [verifier.score(window) for window in windows]
    best_index = int(np.argmax(np.asarray(logits, dtype=np.float32)))
    return windows[best_index], float(logits[best_index]), best_index


def _denoiser(model_path: Path) -> object:
    import sherpa_onnx

    if model_path.name == "gtcrn_simple.onnx":
        gtcrn = sherpa_onnx.OfflineSpeechDenoiserGtcrnModelConfig(
            model=str(model_path)
        )
        model = sherpa_onnx.OfflineSpeechDenoiserModelConfig(
            gtcrn=gtcrn,
            num_threads=4,
            provider="cpu",
        )
    else:
        dpdfnet = sherpa_onnx.OfflineSpeechDenoiserDpdfNetModelConfig(
            model=str(model_path)
        )
        model = sherpa_onnx.OfflineSpeechDenoiserModelConfig(
            dpdfnet=dpdfnet,
            num_threads=4,
            provider="cpu",
        )
    config = sherpa_onnx.OfflineSpeechDenoiserConfig(model=model)
    if not config.validate():
        raise ValueError(f"invalid_denoiser_config:{model_path.name}")
    return sherpa_onnx.OfflineSpeechDenoiser(config)


def denoise_candidate(denoiser: object | None, audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if denoiser is None:
        return values
    result = denoiser(values, SAMPLE_RATE)
    if result.sample_rate != SAMPLE_RATE:
        raise ValueError("denoiser_sample_rate_changed")
    enhanced = np.asarray(result.samples, dtype=np.float32).reshape(-1)
    if enhanced.size < WINDOW_SAMPLES:
        enhanced = np.pad(enhanced, (0, WINDOW_SAMPLES - enhanced.size))
    elif enhanced.size > WINDOW_SAMPLES:
        enhanced = enhanced[:WINDOW_SAMPLES]
    if not np.isfinite(enhanced).all():
        raise ValueError("denoiser_returned_non_finite_audio")
    return np.ascontiguousarray(enhanced)


def _evaluate_group(
    paths: list[Path],
    *,
    recognizer: object,
    hotwords: str,
    verifier: fixed_gate.FastHyperspotter,
    denoisers: dict[str, object | None],
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    variant_latencies: dict[str, list[float]] = {name: [] for name in denoisers}
    for index, path in enumerate(paths):
        audio, sample_rate = room._read_pcm16(path)
        audio = room._resample(audio, sample_rate, SAMPLE_RATE)
        if audio.size != WINDOW_SAMPLES:
            audio = lexical_gate.multi.fixed_three_second_audio(audio)
        stage1_started = time.perf_counter()
        candidate, logit, window_index = best_rolling_candidate(verifier, audio)
        stage1_seconds = time.perf_counter() - stage1_started
        variants: dict[str, object] = {}
        for name, denoiser in denoisers.items():
            started = time.perf_counter()
            if logit >= HYPERSPOTTER_LOGIT:
                verified_audio = denoise_candidate(denoiser, candidate)
                transcript, _ = lexical._decode(
                    recognizer,
                    verified_audio,
                    hotwords=hotwords,
                )
                evidence = lexical_gate.contextual_lexical_evidence(transcript)
                transcript_sha256 = hashlib.sha256(
                    transcript.encode("utf-8")
                ).hexdigest()
            else:
                evidence = False
                transcript_sha256 = None
            latency = stage1_seconds + (time.perf_counter() - started)
            variant_latencies[name].append(latency)
            variants[name] = {
                "accepted": bool(logit >= HYPERSPOTTER_LOGIT and evidence),
                "lexicalEvidence": evidence,
                "transcriptSha256": transcript_sha256,
                "decisionSeconds": latency,
            }
        records.append(
            {
                "record": index,
                "audioSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "rollingHyperspotterMaximumLogit": logit,
                "rollingWindowIndex": window_index,
                "variants": variants,
            }
        )
    return {
        "files": len(paths),
        "stage1AcceptedFiles": sum(
            record["rollingHyperspotterMaximumLogit"] >= HYPERSPOTTER_LOGIT
            for record in records
        ),
        "variants": {
            name: {
                "acceptedFiles": sum(
                    bool(record["variants"][name]["accepted"])
                    for record in records
                ),
                "decisionSeconds": lexical_gate._summary(variant_latencies[name]),
            }
            for name in denoisers
        },
        "records": records,
        "transcriptTextRetained": False,
    }


def _validate_corpus(corpus: Path) -> tuple[Path, dict[str, object]]:
    manifest_path = corpus / "manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("blindHumanPartitionAccessed") is not False:
        raise ValueError("corpus_blind_boundary_attestation_missing")
    if manifest.get("physicalPath", {}).get("captureTransport") != "wasapi_raw_iaudioclient2":
        raise ValueError("corpus_is_not_attested_wasapi_raw")
    return manifest_path, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--models-directory", type=Path, required=True)
    parser.add_argument("--corpus", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpora = [path.resolve(strict=True) for path in args.corpus]
    model_directory = args.models_directory.resolve(strict=True)
    model_paths = [
        (model_directory / filename).resolve(strict=True)
        for filename in MODEL_FILENAMES
    ]
    denoisers: dict[str, object | None] = {"raw": None}
    denoisers.update({path.stem: _denoiser(path) for path in model_paths})

    recognizer, hotwords = lexical._recognizer(
        args.stt_directory.resolve(strict=True), 5.0
    )
    verifier = fixed_gate.FastHyperspotter(
        args.fusion_manifest.resolve(strict=True),
        args.ctc_verifier_manifest.resolve(strict=True),
    )
    started = time.perf_counter()
    corpus_reports: list[dict[str, object]] = []
    for corpus in corpora:
        manifest_path, _ = _validate_corpus(corpus)
        corpus_reports.append(
            {
                "corpusManifestSha256": room._sha256(manifest_path),
                "positive": _evaluate_group(
                    room._wav_paths(corpus / "positive", None),
                    recognizer=recognizer,
                    hotwords=hotwords,
                    verifier=verifier,
                    denoisers=denoisers,
                ),
                "negative": _evaluate_group(
                    room._wav_paths(corpus / "negative", None),
                    recognizer=recognizer,
                    hotwords=hotwords,
                    verifier=verifier,
                    denoisers=denoisers,
                ),
            }
        )

    variant_summary: dict[str, object] = {}
    for name in denoisers:
        positive_files = sum(int(c["positive"]["files"]) for c in corpus_reports)
        negative_files = sum(int(c["negative"]["files"]) for c in corpus_reports)
        positive_accepted = sum(
            int(c["positive"]["variants"][name]["acceptedFiles"])
            for c in corpus_reports
        )
        negative_accepted = sum(
            int(c["negative"]["variants"][name]["acceptedFiles"])
            for c in corpus_reports
        )
        variant_summary[name] = {
            "positiveAccepted": positive_accepted,
            "positiveFiles": positive_files,
            "negativeAccepted": negative_accepted,
            "negativeFiles": negative_files,
            "openedAuditPassed": (
                positive_accepted == positive_files and negative_accepted == 0
            ),
        }

    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_known_playback_wasapi_raw_rolling_candidate_denoiser_audit",
        "policy": {
            "rollingWindowSeconds": 3.0,
            "sidePaddingSeconds": 1.0,
            "hopSeconds": HOP_SAMPLES / SAMPLE_RATE,
            "hyperspotterMaximumLogitGte": HYPERSPOTTER_LOGIT,
            "candidateOnlyContextualLexicalEvidenceRequired": True,
            "contextualHotwordScore": 5.0,
        },
        "models": {
            "speechEnhancement": {
                path.stem: {
                    "sha256": room._sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in model_paths
            },
            "hyperspotter": verifier.identities,
        },
        "corpora": corpus_reports,
        "variantSummary": variant_summary,
        "elapsedWallSeconds": time.perf_counter() - started,
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
    print(json.dumps(variant_summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
