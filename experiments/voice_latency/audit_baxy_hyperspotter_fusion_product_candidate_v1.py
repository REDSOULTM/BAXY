"""Audit the frozen BAXY HyperSpotter/CTC bundle from raw human audio.

This is a product-runtime parity gate.  It intentionally uses only NumPy,
SoundFile, and ONNX Runtime; PyTorch and the HyperSpotter source tree are not
part of the execution path.  The human-development report is aggregate-only
and never accesses the blind partition.
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
from typing import Mapping, Sequence

import numpy as np


SAMPLE_RATE = 16_000
AUDIO_SAMPLES = 48_000
LOGMEL_FRAMES = 300
LOGMEL_BINS = 80
ALIASES = ("baxy", "baxi", "basi", "bakse")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("baxy_hyper_product_json_invalid")
    return value


def adjacent_file(manifest_path: Path, name: object, suffix: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ValueError("baxy_hyper_product_asset_name_invalid")
    path = (manifest_path.parent / name).resolve(strict=True)
    if path.parent != manifest_path.parent or path.suffix.lower() != suffix:
        raise ValueError("baxy_hyper_product_asset_path_invalid")
    return path


def load_fusion_candidate(
    manifest_path: Path, ctc_manifest_path: Path
) -> dict[str, object]:
    manifest_path = manifest_path.resolve(strict=True)
    ctc_manifest_path = ctc_manifest_path.resolve(strict=True)
    manifest = read_object(manifest_path)
    ctc_manifest = read_object(ctc_manifest_path)
    policy = manifest.get("policy")
    if (
        manifest.get("schema") != "baxy-hyperspotter-fusion-v1"
        or manifest.get("backend")
        != "onnxruntime-hyperspotter-fixed-aliases-plus-phoneme-ctc"
        or manifest.get("aliases") != list(ALIASES)
        or manifest.get("sampleRate") != SAMPLE_RATE
        or manifest.get("audioSamples") != AUDIO_SAMPLES
        or manifest.get("logmelFrames") != LOGMEL_FRAMES
        or manifest.get("logmelBins") != LOGMEL_BINS
        or manifest.get("approved") is not False
        or manifest.get("developmentOnly") is not True
        or manifest.get("blindHumanAudioAccessed") is not False
        or manifest.get("effectsExecuted") != 0
        or ctc_manifest.get("schema") != "baxy-wake-verifier-v1"
        or not isinstance(policy, dict)
        or policy.get("ctc_feature") != "full_clip_margin"
    ):
        raise ValueError("baxy_hyper_product_manifest_invalid")
    try:
        center = float(policy["ctc_center"])
        scale = float(policy["ctc_scale"])
        weight = float(policy["ctc_weight"])
        threshold = float(policy["decision_threshold"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("baxy_hyper_product_policy_invalid") from error
    if (
        not all(math.isfinite(value) for value in (center, scale, weight, threshold))
        or scale <= 1e-9
    ):
        raise ValueError("baxy_hyper_product_policy_invalid")
    graph_path = adjacent_file(manifest_path, manifest.get("graph"), ".onnx")
    mel_path = adjacent_file(manifest_path, manifest.get("melFilters"), ".npy")
    if (
        sha256(graph_path) != manifest.get("graphSha256")
        or graph_path.stat().st_size != manifest.get("graphBytes")
        or sha256(mel_path) != manifest.get("melFiltersSha256")
        or sha256(ctc_manifest_path) != manifest.get("ctcVerifierManifestSha256")
    ):
        raise ValueError("baxy_hyper_product_asset_hash_mismatch")
    mel_filters = np.load(mel_path, allow_pickle=False)
    if (
        mel_filters.shape != (LOGMEL_BINS, 201)
        or manifest.get("melFiltersShape") != [LOGMEL_BINS, 201]
        or not np.isfinite(mel_filters).all()
    ):
        raise ValueError("baxy_hyper_product_mel_invalid")
    runtime_calibration = manifest.get("runtimeCalibration")
    if runtime_calibration is not None:
        if (
            not isinstance(runtime_calibration, dict)
            or runtime_calibration.get("schema")
            != "baxy.hyperspotter-fusion-runtime-calibration.v2"
            or runtime_calibration.get("selectionPartition") != "human_legacy"
            or runtime_calibration.get("expandedPartitionUsedForSelection") is not False
            or runtime_calibration.get("fixedNumericalGuard") != 0.05
        ):
            raise ValueError("baxy_hyper_product_runtime_calibration_invalid")
        report_path = adjacent_file(
            manifest_path, runtime_calibration.get("report"), ".json"
        )
        report = read_object(report_path)
        if (
            sha256(report_path) != runtime_calibration.get("reportSha256")
            or report.get("schema")
            != "baxy.hyperspotter-fusion-runtime-calibration.v2"
            or report.get("selectionPartition") != "human_legacy"
            or report.get("expandedPartitionUsedForSelection") is not False
            or report.get("blindHumanAudioAccessed") is not False
            or report.get("candidateGraphChanged") is not False
            or float(report.get("calibratedDecisionThreshold", math.nan))
            != threshold
        ):
            raise ValueError("baxy_hyper_product_runtime_calibration_invalid")
    return {
        "manifest": manifest,
        "manifest_path": manifest_path,
        "ctc_manifest_path": ctc_manifest_path,
        "graph_path": graph_path,
        "mel_path": mel_path,
        "mel_filters": np.asarray(mel_filters, dtype=np.float32),
        "policy": {
            "ctc_center": center,
            "ctc_scale": scale,
            "ctc_weight": weight,
            "decision_threshold": threshold,
        },
    }


def numpy_log_mel_spectrogram(audio: np.ndarray, mel_filters: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    filters = np.asarray(mel_filters, dtype=np.float32)
    if values.shape != (AUDIO_SAMPLES,) or filters.shape != (LOGMEL_BINS, 201):
        raise ValueError("baxy_hyper_product_logmel_shape_invalid")
    padded = np.pad(values, (200, 200), mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(padded, 400)[::160]
    window = np.hanning(401)[:-1].astype(np.float32)
    stft = np.fft.rfft(frames * window[None, :], n=400, axis=1)
    magnitudes = (np.abs(stft) ** 2).astype(np.float32).T[:, :-1]
    mel = filters @ magnitudes
    log_spec = np.log10(np.maximum(mel, np.float32(1e-10)))
    log_spec = np.maximum(log_spec, np.max(log_spec) - np.float32(8.0))
    result = ((log_spec + np.float32(4.0)) / np.float32(4.0)).T.astype(
        np.float32
    )
    if result.shape != (LOGMEL_FRAMES, LOGMEL_BINS) or not np.isfinite(result).all():
        raise ValueError("baxy_hyper_product_logmel_invalid")
    return result


def ctc_log_probability_batch(
    log_probabilities: np.ndarray,
    sequence: Sequence[int],
    *,
    blank_id: int,
) -> np.ndarray:
    values = np.asarray(log_probabilities, dtype=np.float64)
    tokens = [int(token) for token in sequence]
    if values.ndim != 3 or not tokens or values.shape[1] < 1:
        raise ValueError("baxy_hyper_product_ctc_batch_invalid")
    states = [blank_id]
    for token in tokens:
        states.extend((token, blank_id))
    state_ids = np.asarray(states, dtype=np.int64)
    previous = np.full((len(values), len(states)), -np.inf, dtype=np.float64)
    previous[:, 0] = values[:, 0, blank_id]
    previous[:, 1] = values[:, 0, tokens[0]]
    allow_skip = np.asarray(
        [
            state > 1
            and token != blank_id
            and token != states[state - 2]
            for state, token in enumerate(states)
        ],
        dtype=np.bool_,
    )
    for frame in range(1, values.shape[1]):
        total = previous.copy()
        total[:, 1:] = np.logaddexp(total[:, 1:], previous[:, :-1])
        skip_states = np.flatnonzero(allow_skip)
        if len(skip_states):
            total[:, skip_states] = np.logaddexp(
                total[:, skip_states], previous[:, skip_states - 2]
            )
        previous = total + values[:, frame, state_ids]
    return np.logaddexp(previous[:, -1], previous[:, -2])


def full_clip_ctc_margin(log_probabilities: np.ndarray, wake: object) -> float:
    values = np.asarray(log_probabilities, dtype=np.float64)
    if values.ndim != 2 or len(values) < 1:
        raise ValueError("baxy_hyper_product_ctc_probabilities_invalid")
    batch = values[None, :, :]
    target = max(
        float(ctc_log_probability_batch(batch, sequence, blank_id=wake.BLANK_ID)[0])
        for sequence in wake.TARGET_IDS
    )
    confusable = max(
        float(ctc_log_probability_batch(batch, sequence, blank_id=wake.BLANK_ID)[0])
        for sequence in wake.CONFUSABLE_IDS
    )
    margin = target - confusable
    if not math.isfinite(margin):
        raise ValueError("baxy_hyper_product_ctc_margin_invalid")
    return margin


def human_records(manifest: Mapping[str, object]) -> list[dict[str, object]]:
    if (
        manifest.get("schema") != "baxy.wav2vec2-hidden-wake-training-features.v1"
        or manifest.get("blind_human_audio_accessed") is not False
        or not isinstance(manifest.get("records"), list)
    ):
        raise ValueError("baxy_hyper_product_human_boundary_invalid")
    result = []
    for record in manifest["records"]:
        if not isinstance(record, dict) or record.get("corpus") not in {
            "human_legacy",
            "human_expanded",
        }:
            continue
        if (
            record.get("label") not in {"positive", "negative"}
            or not isinstance(record.get("relative_path"), str)
            or not isinstance(record.get("audio_sha256"), str)
        ):
            raise ValueError("baxy_hyper_product_human_record_invalid")
        result.append(record)
    counts = {
        corpus: sum(record["corpus"] == corpus for record in result)
        for corpus in ("human_legacy", "human_expanded")
    }
    if counts != {"human_legacy": 18, "human_expanded": 12}:
        raise ValueError(f"baxy_hyper_product_human_counts_invalid:{counts}")
    return result


def percentile_summary(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 1 or len(array) < 1 or not np.isfinite(array).all():
        raise ValueError("baxy_hyper_product_latency_invalid")
    return {
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "maximum": float(np.max(array)),
        "mean": float(np.mean(array)),
    }


def partition_metrics(
    labels: np.ndarray, decisions: np.ndarray, decision_margins: np.ndarray
) -> dict[str, object]:
    labels = np.asarray(labels, dtype=np.int64)
    decisions = np.asarray(decisions, dtype=np.bool_)
    margins = np.asarray(decision_margins, dtype=np.float64)
    if labels.shape != decisions.shape or labels.shape != margins.shape or not len(labels):
        raise ValueError("baxy_hyper_product_metrics_invalid")
    positive = labels == 1
    negative = ~positive
    accepted = margins[decisions]
    rejected = margins[~decisions]
    return {
        "positiveTotal": int(np.count_nonzero(positive)),
        "negativeTotal": int(np.count_nonzero(negative)),
        "positiveHits": int(np.count_nonzero(decisions & positive)),
        "falseHits": int(np.count_nonzero(decisions & negative)),
        "recall": float(np.count_nonzero(decisions & positive) / np.count_nonzero(positive)),
        "minimumPositiveDecisionMargin": float(np.min(margins[positive])),
        "maximumNegativeDecisionMargin": float(np.max(margins[negative])),
        "minimumAcceptedDecisionMargin": float(np.min(accepted)) if len(accepted) else None,
        "maximumRejectedDecisionMargin": float(np.max(rejected)) if len(rejected) else None,
    }


def resident_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.Process().memory_info().rss)
    except (ImportError, OSError):
        return None


def audit(
    *,
    fusion_manifest_path: Path,
    ctc_manifest_path: Path,
    human_source_manifest_path: Path,
    legacy_root: Path,
    expanded_root: Path,
    output_path: Path,
    threads: int,
) -> dict[str, object]:
    if output_path.exists() or threads < 1 or threads > 32:
        raise ValueError("baxy_hyper_product_schedule_invalid")
    candidate = load_fusion_candidate(fusion_manifest_path, ctc_manifest_path)
    source_path = human_source_manifest_path.resolve(strict=True)
    source = read_object(source_path)
    records = human_records(source)
    roots = {
        "human_legacy": legacy_root.resolve(strict=True),
        "human_expanded": expanded_root.resolve(strict=True),
    }

    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    from baxy_mind import wake_verifier as wake
    import onnxruntime as ort
    import soundfile as sf

    if "torch" in sys.modules:
        raise RuntimeError("baxy_hyper_product_torch_dependency_detected")

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    baseline_rss = resident_bytes()
    started = time.perf_counter()
    hyper_session = ort.InferenceSession(
        str(candidate["graph_path"]),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    hyper_load_seconds = time.perf_counter() - started
    hyper_rss = resident_bytes()
    ctc_config = wake.load_wake_verifier_candidate_config(
        candidate["ctc_manifest_path"]
    )
    started = time.perf_counter()
    ctc_session = ort.InferenceSession(
        str(ctc_config.graph_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    ctc_load_seconds = time.perf_counter() - started
    ctc_rss = resident_bytes()
    verifier = wake.OnnxWakeVerifier(ctc_config, session=ctc_session)

    zero = np.zeros(AUDIO_SAMPLES, dtype=np.float32)
    zero_mel = numpy_log_mel_spectrogram(zero, candidate["mel_filters"])
    hyper_session.run(["logits"], {"logmel": zero_mel[None, :, :]})
    ctc_session.run(["logits"], {"input_values": wake.normalize_audio(zero)})
    warm_rss = resident_bytes()

    policy = candidate["policy"]
    labels = []
    corpora = []
    hyper_scores = []
    ctc_margins = []
    combined_scores = []
    decisions = []
    decision_margins = []
    latencies: dict[str, list[float]] = {
        "audioDecodeMs": [],
        "logmelMs": [],
        "hyperOnnxMs": [],
        "ctcPreprocessMs": [],
        "ctcOnnxMs": [],
        "ctcMarginMs": [],
        "warmComputeMs": [],
        "warmEndToEndMs": [],
    }
    for index, record in enumerate(records):
        path = (
            roots[str(record["corpus"])] / str(record["relative_path"])
        ).resolve(strict=True)
        if sha256(path) != str(record["audio_sha256"]).lower():
            raise ValueError("baxy_hyper_product_audio_hash_mismatch")
        total_started = time.perf_counter()
        started = time.perf_counter()
        waveform, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
        audio = waveform.mean(axis=1, dtype=np.float32)
        decode_done = time.perf_counter()
        if sample_rate != SAMPLE_RATE or audio.shape != (AUDIO_SAMPLES,):
            raise ValueError("baxy_hyper_product_audio_contract_invalid")
        logmel = numpy_log_mel_spectrogram(audio, candidate["mel_filters"])
        logmel_done = time.perf_counter()
        hyper_logits = hyper_session.run(
            ["logits"], {"logmel": logmel[None, :, :]}
        )[0]
        hyper_done = time.perf_counter()
        if hyper_logits.shape != (1, len(ALIASES)) or not np.isfinite(hyper_logits).all():
            raise ValueError("baxy_hyper_product_hyper_logits_invalid")
        normalized = wake.normalize_audio(audio)
        normalized_done = time.perf_counter()
        ctc_logits = ctc_session.run(["logits"], {"input_values": normalized})[0]
        ctc_done = time.perf_counter()
        probabilities = wake.compress_category_logits_numpy(
            ctc_logits, verifier._category_ids
        )
        ctc_margin = full_clip_ctc_margin(
            np.log(np.maximum(probabilities, 1e-12)), wake
        )
        margin_done = time.perf_counter()
        hyper_score = float(np.max(hyper_logits))
        combined = hyper_score + float(policy["ctc_weight"]) * (
            (ctc_margin - float(policy["ctc_center"]))
            / float(policy["ctc_scale"])
        )
        decision_margin = combined - float(policy["decision_threshold"])
        labels.append(int(record["label"] == "positive"))
        corpora.append(str(record["corpus"]))
        hyper_scores.append(hyper_score)
        ctc_margins.append(ctc_margin)
        combined_scores.append(combined)
        decisions.append(decision_margin >= 0.0)
        decision_margins.append(decision_margin)
        latencies["audioDecodeMs"].append((decode_done - started) * 1000.0)
        latencies["logmelMs"].append((logmel_done - decode_done) * 1000.0)
        latencies["hyperOnnxMs"].append((hyper_done - logmel_done) * 1000.0)
        latencies["ctcPreprocessMs"].append((normalized_done - hyper_done) * 1000.0)
        latencies["ctcOnnxMs"].append((ctc_done - normalized_done) * 1000.0)
        latencies["ctcMarginMs"].append((margin_done - ctc_done) * 1000.0)
        latencies["warmComputeMs"].append((margin_done - decode_done) * 1000.0)
        latencies["warmEndToEndMs"].append((margin_done - total_started) * 1000.0)
        print(f"BAXY_HYPER_PRODUCT_AUDIT|{index + 1}/{len(records)}", flush=True)

    labels_array = np.asarray(labels, dtype=np.int64)
    corpora_array = np.asarray(corpora)
    decisions_array = np.asarray(decisions, dtype=np.bool_)
    margins_array = np.asarray(decision_margins, dtype=np.float64)
    legacy = corpora_array == "human_legacy"
    expanded = corpora_array == "human_expanded"
    all_metrics = partition_metrics(labels_array, decisions_array, margins_array)
    passed = (
        all_metrics["positiveHits"] == 18
        and all_metrics["positiveTotal"] == 18
        and all_metrics["falseHits"] == 0
        and all_metrics["negativeTotal"] == 12
    )
    report: dict[str, object] = {
        "schema": "baxy.hyperspotter-fusion-product-runtime-audit.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "raw_human_development_fixed_policy_cpu_onnxruntime",
        "sources": {
            "fusionManifestSha256": sha256(candidate["manifest_path"]),
            "ctcVerifierManifestSha256": sha256(candidate["ctc_manifest_path"]),
            "humanSourceManifestSha256": sha256(source_path),
        },
        "runtime": {
            "providers": hyper_session.get_providers(),
            "threads": threads,
            "hyperSessionLoadSeconds": hyper_load_seconds,
            "ctcSessionLoadSeconds": ctc_load_seconds,
            "residentBytes": {
                "baseline": baseline_rss,
                "afterHyperSession": hyper_rss,
                "afterCtcSession": ctc_rss,
                "afterWarmup": warm_rss,
                "afterAudit": resident_bytes(),
            },
            "torchImported": "torch" in sys.modules,
        },
        "latencyMilliseconds": {
            name: percentile_summary(values) for name, values in latencies.items()
        },
        "scoreRanges": {
            "hyperMinimum": float(np.min(hyper_scores)),
            "hyperMaximum": float(np.max(hyper_scores)),
            "ctcMarginMinimum": float(np.min(ctc_margins)),
            "ctcMarginMaximum": float(np.max(ctc_margins)),
            "combinedMinimum": float(np.min(combined_scores)),
            "combinedMaximum": float(np.max(combined_scores)),
        },
        "legacyDevelopment": partition_metrics(
            labels_array[legacy], decisions_array[legacy], margins_array[legacy]
        ),
        "expandedIndependentDevelopment": partition_metrics(
            labels_array[expanded], decisions_array[expanded], margins_array[expanded]
        ),
        "allHumanDevelopment": all_metrics,
        "rawProductParityPassed": passed,
        "humanDevelopmentAudioAccessed": True,
        "blindHumanAudioAccessed": False,
        "audioOrFilenamesRetained": False,
        "approved": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    if report["runtime"]["torchImported"] is not False:
        raise RuntimeError("baxy_hyper_product_torch_dependency_detected")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--human-source-manifest", type=Path, required=True)
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--expanded-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = audit(
        fusion_manifest_path=arguments.fusion_manifest,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        human_source_manifest_path=arguments.human_source_manifest,
        legacy_root=arguments.legacy_root,
        expanded_root=arguments.expanded_root,
        output_path=arguments.output,
        threads=arguments.threads,
    )
    print(
        json.dumps(
            {
                "passed": report["rawProductParityPassed"],
                "legacy": report["legacyDevelopment"],
                "expanded": report["expandedIndependentDevelopment"],
                "all": report["allHumanDevelopment"],
                "latency": report["latencyMilliseconds"]["warmComputeMs"],
                "residentBytes": report["runtime"]["residentBytes"],
                "torchImported": report["runtime"]["torchImported"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["rawProductParityPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
