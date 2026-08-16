"""Screen every opened OpenSLR window with a direct compact wake verifier.

This development regression measures the VAD-bounded architecture where the
compact log-Mel verifier is allowed to propose a lexical confirmation even
when HyperSpotter did not propose first.  CUDA is only a broad screen.  Every
record within a fixed margin of the product threshold is recomputed with the
exported ONNX graph and the exact NumPy product log-Mel implementation.

The opened corpus is public LibriSpeech data.  No transcript or filename is
retained in the report, and a direct acoustic proposal is not represented as
a wake activation: lexical confirmation remains mandatory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


SCHEMA = "baxy.direct-logmel-openslr-negative-regression.v1"
CORPUS_SCHEMA = "baxy.openslr-librispeech-negative-holdout.v1"
CASCADE_SCHEMA = "baxy-wake-cascade-v2"
SAMPLE_RATE = 16_000
WINDOW_SAMPLES = 48_000
FRAMES = 300
MEL_BINS = 80

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("direct_logmel_openslr_json_invalid")
    return value


def load_component(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("direct_logmel_openslr_component_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stream_audio(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not values.size or not np.isfinite(values).all():
        raise ValueError("direct_logmel_openslr_audio_invalid")
    left = SAMPLE_RATE
    right = max(SAMPLE_RATE, WINDOW_SAMPLES - left - len(values))
    return np.pad(values, (left, right))


def window_views(audio: np.ndarray, hop_samples: int) -> list[np.ndarray]:
    if not 1 <= hop_samples <= WINDOW_SAMPLES:
        raise ValueError("direct_logmel_openslr_hop_invalid")
    maximum = max(0, len(audio) - WINDOW_SAMPLES)
    return [
        np.ascontiguousarray(audio[start : start + WINDOW_SAMPLES])
        for start in range(0, maximum + 1, hop_samples)
    ]


def gpu_logmel(torch: Any, audio: np.ndarray, filters: Any, window: Any) -> Any:
    values = torch.from_numpy(audio).cuda(non_blocking=True)
    spectrum = torch.stft(
        values,
        n_fft=400,
        hop_length=160,
        win_length=400,
        window=window,
        center=True,
        return_complex=True,
    )
    magnitudes = spectrum[..., :-1].abs().square()
    mel_spec = filters @ magnitudes
    log_spec = torch.clamp(mel_spec, min=1e-10).log10()
    log_spec = torch.maximum(
        log_spec, log_spec.amax(dim=(1, 2), keepdim=True) - 8.0
    )
    result = ((log_spec + 4.0) / 4.0).transpose(1, 2).float()
    if result.shape[1:] != (FRAMES, MEL_BINS):
        raise ValueError("direct_logmel_openslr_logmel_shape_invalid")
    return result


def candidate_assets(
    cascade_path: Path, checkpoint_path: Path, verifier_index: int
) -> dict[str, Any]:
    cascade = read_object(cascade_path)
    verifiers = cascade.get("logmelVerifiers")
    if (
        cascade.get("schema") != CASCADE_SCHEMA
        or not isinstance(verifiers, list)
        or not 0 <= verifier_index < len(verifiers)
    ):
        raise ValueError("direct_logmel_openslr_cascade_invalid")
    verifier = verifiers[verifier_index]
    if not isinstance(verifier, dict):
        raise ValueError("direct_logmel_openslr_verifier_invalid")
    onnx_path = (cascade_path.parent / str(verifier.get("graph") or "")).resolve(
        strict=True
    )
    mel_path = (cascade_path.parent / str(cascade.get("melFilters") or "")).resolve(
        strict=True
    )
    if (
        sha256(onnx_path) != verifier.get("graphSha256")
        or sha256(mel_path) != cascade.get("melFiltersSha256")
    ):
        raise ValueError("direct_logmel_openslr_asset_hash_mismatch")
    checkpoint = read_checkpoint(checkpoint_path)
    if checkpoint.get("onnx_sha256") not in {None, sha256(onnx_path)}:
        raise ValueError("direct_logmel_openslr_checkpoint_onnx_mismatch")
    return {
        "cascade": cascade,
        "verifier": verifier,
        "onnx_path": onnx_path,
        "mel_path": mel_path,
        "checkpoint": checkpoint,
    }


def read_checkpoint(path: Path) -> dict[str, Any]:
    import torch

    value = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(value, dict) or not isinstance(value.get("model_state_dict"), dict):
        raise ValueError("direct_logmel_openslr_checkpoint_invalid")
    return value


def exact_record_score(
    *,
    audio: np.ndarray,
    hop_samples: int,
    mel_filters: np.ndarray,
    session: Any,
    product: Any,
    batch_size: int,
) -> float:
    windows = window_views(stream_audio(audio), hop_samples)
    maximum = float("-inf")
    for start in range(0, len(windows), batch_size):
        features = np.stack(
            [
                product.numpy_log_mel_spectrogram(window, mel_filters)
                for window in windows[start : start + batch_size]
            ]
        ).astype(np.float32)
        scores = np.asarray(
            session.run(["wake_logit"], {"logmel": features})[0],
            dtype=np.float32,
        ).reshape(-1)
        if scores.size != len(features) or not np.isfinite(scores).all():
            raise ValueError("direct_logmel_openslr_exact_score_invalid")
        maximum = max(maximum, float(np.max(scores)))
    return maximum


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    import onnxruntime as ort
    import soundfile as sf
    import torch

    if (
        args.batch_size < 1
        or args.group_size < 1
        or args.progress_records < 1
        or not np.isfinite(args.screen_margin)
        or args.screen_margin < 0.0
        or not torch.cuda.is_available()
    ):
        raise ValueError("direct_logmel_openslr_schedule_invalid")
    output = args.output.resolve()
    partial = output.with_name(output.name + ".partial.json")
    if output.exists():
        raise FileExistsError("direct_logmel_openslr_output_exists")
    corpus_path = args.corpus_manifest.resolve(strict=True)
    cascade_path = args.cascade_manifest.resolve(strict=True)
    checkpoint_path = args.verifier_checkpoint.resolve(strict=True)
    corpus = read_object(corpus_path)
    records = corpus.get("records")
    if corpus.get("schema") != CORPUS_SCHEMA or not isinstance(records, list):
        raise ValueError("direct_logmel_openslr_corpus_invalid")
    root = (corpus_path.parent / str(corpus.get("corpus_root") or "")).resolve(
        strict=True
    )
    assets = candidate_assets(cascade_path, checkpoint_path, args.verifier_index)
    cascade = assets["cascade"]
    threshold = float(assets["verifier"].get("scoreGte"))
    hop_samples = int(cascade.get("hopSamples") or 0)
    if not np.isfinite(threshold) or not 1 <= hop_samples <= WINDOW_SAMPLES:
        raise ValueError("direct_logmel_openslr_policy_invalid")
    screen_threshold = threshold - args.screen_margin
    identities = {
        "corpusManifestSha256": sha256(corpus_path),
        "cascadeManifestSha256": sha256(cascade_path),
        "verifierCheckpointSha256": sha256(checkpoint_path),
        "onnxVerifierSha256": sha256(assets["onnx_path"]),
        "melFiltersSha256": sha256(assets["mel_path"]),
        "evaluatorSourceSha256": sha256(Path(__file__).resolve()),
    }

    trainer = load_component(
        Path(__file__).with_name("train_baxy_logmel_closed_set_verifier_v1.py"),
        "_baxy_direct_logmel_openslr_trainer_v1",
    )
    from baxy_mind import wake_cascade as product
    checkpoint = assets["checkpoint"]
    model = trainer.build_model(
        channels=int(checkpoint["channels"]),
        blocks=int(checkpoint["blocks"]),
        dropout=float(checkpoint["dropout"]),
    )
    model.load_state_dict(checkpoint["model_state_dict"], strict=True)
    model.eval().cuda()
    torch.set_float32_matmul_precision("high")
    filters_cpu = np.load(assets["mel_path"], allow_pickle=False).astype(np.float32)
    if filters_cpu.shape != (MEL_BINS, 201):
        raise ValueError("direct_logmel_openslr_mel_invalid")
    filters_gpu = torch.from_numpy(filters_cpu).cuda()
    hann = torch.hann_window(400, device="cuda")

    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    exact_session = ort.InferenceSession(
        str(assets["onnx_path"]),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )

    start_index = 0
    windows_scored = 0
    screen_records: list[dict[str, Any]] = []
    maximum_screen_score = float("-inf")
    if partial.exists():
        progress = read_object(partial)
        if progress.get("schema") != SCHEMA + ".partial" or progress.get(
            "sources"
        ) != identities:
            raise ValueError("direct_logmel_openslr_partial_invalid")
        start_index = int(progress.get("nextRecord") or 0)
        windows_scored = int(progress.get("windowsScored") or 0)
        screen_records = list(progress.get("screenRecords") or [])
        maximum_screen_score = float(progress.get("maximumScreenScore"))

    started = time.perf_counter()
    last_report = start_index
    for group_start in range(start_index, len(records), args.group_size):
        group = records[group_start : group_start + args.group_size]
        decoded: list[np.ndarray] = []
        grouped_windows: list[list[np.ndarray]] = []
        for record in group:
            if not isinstance(record, dict):
                raise ValueError("direct_logmel_openslr_record_invalid")
            path = (root / str(record.get("relative_path") or "")).resolve(strict=True)
            if sha256(path) != record.get("sha256"):
                raise ValueError("direct_logmel_openslr_audio_hash_mismatch")
            audio, rate = sf.read(str(path), dtype="float32", always_2d=False)
            values = np.asarray(audio, dtype=np.float32).reshape(-1)
            if (
                int(rate) != SAMPLE_RATE
                or values.size != int(record.get("frames") or -1)
                or not np.isfinite(values).all()
            ):
                raise ValueError("direct_logmel_openslr_audio_contract_invalid")
            decoded.append(values)
            grouped_windows.append(window_views(stream_audio(values), hop_samples))

        maxima = [float("-inf")] * len(group)
        locators = [
            (record_index, window)
            for record_index, windows in enumerate(grouped_windows)
            for window in windows
        ]
        for start in range(0, len(locators), args.batch_size):
            batch = locators[start : start + args.batch_size]
            audio_batch = np.stack([window for _, window in batch]).astype(np.float32)
            with torch.inference_mode():
                logmel = gpu_logmel(torch, audio_batch, filters_gpu, hann)
                scores = model(logmel)[:, 0].float().cpu().numpy()
            if scores.size != len(batch) or not np.isfinite(scores).all():
                raise ValueError("direct_logmel_openslr_screen_score_invalid")
            for (record_index, _), score in zip(batch, scores):
                maxima[record_index] = max(maxima[record_index], float(score))
        windows_scored += len(locators)
        for record, maximum in zip(group, maxima):
            maximum_screen_score = max(maximum_screen_score, maximum)
            if maximum >= screen_threshold:
                screen_records.append(
                    {
                        "audioSha256": str(record["sha256"]),
                        "screenScore": maximum,
                    }
                )

        next_record = group_start + len(group)
        progress = {
            "schema": SCHEMA + ".partial",
            "sources": identities,
            "nextRecord": next_record,
            "windowsScored": windows_scored,
            "maximumScreenScore": maximum_screen_score,
            "screenRecords": screen_records,
        }
        partial.parent.mkdir(parents=True, exist_ok=True)
        temporary = partial.with_name(partial.name + ".tmp")
        temporary.write_text(
            json.dumps(progress, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(partial)
        if next_record - last_report >= args.progress_records or next_record == len(
            records
        ):
            elapsed = time.perf_counter() - started
            rate = (next_record - start_index) / elapsed if elapsed else 0.0
            remaining = (len(records) - next_record) / rate if rate else None
            print(
                "BAXY_DIRECT_LOGMEL_OPENSLR|"
                f"{next_record}/{len(records)}|windows={windows_scored}|"
                f"screen={len(screen_records)}|rate={rate:.2f}/s|"
                f"eta={remaining:.1f}",
                flush=True,
            )
            last_report = next_record

    records_by_hash = {
        str(record["sha256"]): record for record in records if isinstance(record, dict)
    }
    exact_records: list[dict[str, Any]] = []
    for index, screen in enumerate(screen_records):
        record = records_by_hash.get(str(screen["audioSha256"]))
        if record is None:
            raise ValueError("direct_logmel_openslr_screen_record_missing")
        path = (root / str(record.get("relative_path") or "")).resolve(strict=True)
        audio, rate = sf.read(str(path), dtype="float32", always_2d=False)
        if int(rate) != SAMPLE_RATE:
            raise ValueError("direct_logmel_openslr_exact_rate_invalid")
        exact = exact_record_score(
            audio=np.asarray(audio, dtype=np.float32),
            hop_samples=hop_samples,
            mel_filters=filters_cpu,
            session=exact_session,
            product=product,
            batch_size=max(1, min(args.batch_size, 128)),
        )
        exact_records.append(
            {
                "audioSha256": str(screen["audioSha256"]),
                "screenScore": float(screen["screenScore"]),
                "exactScore": exact,
                "directProposal": exact >= threshold,
            }
        )
        print(
            f"BAXY_DIRECT_LOGMEL_EXACT|{index + 1}/{len(screen_records)}",
            flush=True,
        )

    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "previously_opened_openslr100h_all_windows_direct_verifier_regression",
        "sources": identities,
        "contract": {
            "utteranceCount": len(records),
            "hopSamples": hop_samples,
            "verifierIndex": args.verifier_index,
            "verifierScoreGte": threshold,
            "cudaScreenMargin": args.screen_margin,
            "lexicalConfirmationRequired": True,
        },
        "metrics": {
            "utterances": len(records),
            "descriptiveExposureHours": corpus.get("metrics", {}).get(
                "audio_hours"
            ),
            "windowsScored": windows_scored,
            "screenRecords": len(screen_records),
            "directAcousticProposals": sum(
                bool(record["directProposal"]) for record in exact_records
            ),
            "maximumScreenScore": maximum_screen_score,
            "maximumExactScore": max(
                (float(record["exactScore"]) for record in exact_records),
                default=None,
            ),
        },
        "exactRecords": exact_records,
        "runtimeSeconds": time.perf_counter() - started,
        "directProposalIsWakeAuthority": False,
        "lexicalGuardMeasured": False,
        "candidateFrozen": False,
        "promotable": False,
        "negativeCorpusPreviouslyAccessed": True,
        "blindHumanAudioAccessed": False,
        "transcriptsOrFilenamesRetained": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.unlink()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--verifier-checkpoint", type=Path, required=True)
    parser.add_argument("--verifier-index", type=int, default=1)
    parser.add_argument("--screen-margin", type=float, default=0.5)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--group-size", type=int, default=32)
    parser.add_argument("--progress-records", type=int, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    report = evaluate(parse_args())
    print(json.dumps(report["metrics"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
