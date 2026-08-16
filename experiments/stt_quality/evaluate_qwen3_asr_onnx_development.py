"""Measure the official sherpa-onnx Qwen3-ASR 0.6B int8 candidate.

This evaluator is intentionally development-only.  It reuses the frozen
real-audio loaders and scoring oracles without changing the evaluator that
sealed the previous blind campaign.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time
from typing import Any
import zipfile

import numpy as np


SCHEMA = "baxy.stt-qwen3-asr-onnx-development.v1"
OFFICIAL_ASSET_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25.tar.bz2"
)
OFFICIAL_ARCHIVE_BYTES = 878_702_423
OFFICIAL_ARCHIVE_SHA256 = (
    "393f8a14e2f5fb96746aaab342997a40641001fbd5bf9592a080a8329178ee96"
)
REQUIRED_MODEL_FILES = (
    "conv_frontend.onnx",
    "encoder.int8.onnx",
    "decoder.int8.onnx",
    "tokenizer/merges.txt",
    "tokenizer/tokenizer_config.json",
    "tokenizer/vocab.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_manifest(model_directory: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for relative in REQUIRED_MODEL_FILES:
        path = model_directory / relative
        if not path.is_file():
            raise RuntimeError(f"qwen3_asr_model_file_missing:{relative}")
        result[relative] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return result


def model_tree_sha256(manifest: dict[str, dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for relative, metadata in sorted(manifest.items()):
        digest.update(
            json.dumps(
                [relative, metadata["bytes"], metadata["sha256"]],
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def validate_official_archive(path: Path) -> dict[str, object]:
    path = path.resolve(strict=True)
    size = path.stat().st_size
    digest = sha256(path)
    if size != OFFICIAL_ARCHIVE_BYTES or digest != OFFICIAL_ARCHIVE_SHA256:
        raise RuntimeError("qwen3_asr_official_archive_mismatch")
    return {
        "path": path.as_posix(),
        "bytes": size,
        "sha256": digest,
        "officialAssetUrl": OFFICIAL_ASSET_URL,
    }


def load_frozen_evaluator(repository_root: Path):
    path = repository_root / "experiments" / "stt_quality" / "evaluate_reserved_stt.py"
    specification = importlib.util.spec_from_file_location(
        "baxy_frozen_reserved_stt_evaluator", path
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("frozen_stt_evaluator_import_failed")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class Qwen3AsrOnnxStt:
    def __init__(
        self,
        *,
        model_directory: Path,
        threads: int,
        max_new_tokens: int,
        manifest: dict[str, dict[str, object]],
    ) -> None:
        import psutil
        import sherpa_onnx

        if not hasattr(sherpa_onnx.OfflineRecognizer, "from_qwen3_asr"):
            raise RuntimeError("sherpa_onnx_qwen3_asr_api_missing")
        self._process = psutil.Process()
        rss_before = self._process.memory_info().rss
        started = time.perf_counter()
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_qwen3_asr(
            conv_frontend=str(model_directory / "conv_frontend.onnx"),
            encoder=str(model_directory / "encoder.int8.onnx"),
            decoder=str(model_directory / "decoder.int8.onnx"),
            tokenizer=str(model_directory / "tokenizer"),
            num_threads=threads,
            provider="cpu",
            max_new_tokens=max_new_tokens,
            temperature=1e-6,
            top_p=0.8,
            seed=42,
        )
        self.load_seconds = time.perf_counter() - started
        rss_after = self._process.memory_info().rss
        self.peak_rss_bytes = rss_after
        warmup = self._recognizer.create_stream()
        warmup.accept_waveform(16_000, np.zeros(8_000, dtype=np.float32))
        started = time.perf_counter()
        self._recognizer.decode_stream(warmup)
        self.warmup_seconds = time.perf_counter() - started
        self.peak_rss_bytes = max(
            self.peak_rss_bytes, self._process.memory_info().rss
        )
        self.status = {
            "loaded": True,
            "model": "Qwen3-ASR-0.6B-int8-2026-03-25",
            "provider": "cpu",
            "threads": threads,
            "maxNewTokens": max_new_tokens,
            "sherpaOnnxVersion": getattr(sherpa_onnx, "__version__", None),
            "modelTreeSha256": model_tree_sha256(manifest),
            "rssBeforeLoadBytes": rss_before,
            "rssAfterLoadBytes": rss_after,
        }
        self.last_diagnostics: dict[str, float] = {}

    def transcribe(
        self, audio: np.ndarray, _language: str | None = None
    ) -> tuple[str, str, float]:
        stream = self._recognizer.create_stream()
        stream.accept_waveform(16_000, np.asarray(audio, dtype=np.float32))
        started = time.perf_counter()
        self._recognizer.decode_stream(stream)
        latency = time.perf_counter() - started
        self.peak_rss_bytes = max(
            self.peak_rss_bytes, self._process.memory_info().rss
        )
        text = str(stream.result.text or "").strip()
        self.last_diagnostics = {
            "finalizationLatencySeconds": latency,
            "maximumChunkDecodeSeconds": latency,
        }
        return text, text, latency


def evaluate(arguments: argparse.Namespace) -> dict[str, object]:
    repository_root = arguments.repository_root.resolve(strict=True)
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError("qwen3_asr_development_output_exists")
    if not 1 <= arguments.threads <= 16:
        raise ValueError("qwen3_asr_thread_count_invalid")
    if not 32 <= arguments.max_new_tokens <= 256:
        raise ValueError("qwen3_asr_max_new_tokens_invalid")

    frozen = load_frozen_evaluator(repository_root)
    contract, preregistration, _runtime = frozen._validate_contract(
        repository_root=repository_root,
        contract_path=arguments.contract.resolve(strict=True),
        source=arguments.source,
        partition="development",
    )
    official_archive = validate_official_archive(arguments.model_archive)
    model_directory = arguments.model_directory.resolve(strict=True)
    manifest = model_manifest(model_directory)
    recognizer = Qwen3AsrOnnxStt(
        model_directory=model_directory,
        threads=arguments.threads,
        max_new_tokens=arguments.max_new_tokens,
        manifest=manifest,
    )

    if arguments.source == "audio_arena":
        cases = frozen._audio_arena_cases(preregistration, "development")
    else:
        cases = frozen._minds14_cases(
            preregistration,
            "development",
            Path(str(contract["minds14Source"]["root"])),
        )
    ffmpeg = Path(str(contract["ffmpeg"]["path"]))
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, case in enumerate(cases, start=1):
        if arguments.source == "audio_arena":
            audio = frozen._load_wav(case["path"])
        else:
            with zipfile.ZipFile(case["audioZip"]) as archive:
                audio = frozen._load_wav_bytes(
                    archive.read(case["audioEntry"]),
                    str(case["audioEntry"]),
                    ffmpeg,
                )
        results.append(
            frozen._case_result(case=case, audio=audio, product_stt=recognizer)
        )
        if index % 10 == 0 or index == len(cases):
            print(
                json.dumps(
                    {
                        "progress": index,
                        "total": len(cases),
                        "source": arguments.source,
                        "engine": "qwen3_asr_onnx_cpu",
                    }
                ),
                flush=True,
            )

    intent_oracle = None
    if arguments.source == "minds14":
        intent_oracle = frozen._score_minds14_intents(
            prereg=preregistration,
            source_root=Path(str(contract["minds14Source"]["root"])),
            results=results,
        )
    aggregate = frozen._aggregate(
        source=arguments.source,
        partition="development",
        results=results,
    )
    passed = all(aggregate["checks"].values())
    report: dict[str, object] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "source": arguments.source,
        "partition": "development",
        "engine": "qwen3_asr_onnx_cpu",
        "status": "passed" if passed else "failed",
        "contract": {
            "path": arguments.contract.resolve(strict=True).as_posix(),
            "sha256": sha256(arguments.contract.resolve(strict=True)),
        },
        "frozenEvaluator": {
            "path": (repository_root / "experiments/stt_quality/evaluate_reserved_stt.py").as_posix(),
            "sha256": sha256(
                repository_root / "experiments/stt_quality/evaluate_reserved_stt.py"
            ),
        },
        "model": {
            "archive": official_archive,
            "directory": model_directory.as_posix(),
            "files": manifest,
            "treeSha256": model_tree_sha256(manifest),
        },
        "engineRuntime": {
            "loadSeconds": round(recognizer.load_seconds, 6),
            "warmupSeconds": round(recognizer.warmup_seconds, 6),
            "peakRssBytesObserved": recognizer.peak_rss_bytes,
            "status": recognizer.status,
        },
        "intentOracle": intent_oracle,
        "scoringNormalization": frozen.SCORING_NORMALIZATION,
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        "aggregate": aggregate,
        "cases": results,
        "developmentOnly": True,
        "blindHoldoutOpened": False,
        "candidatePromoted": False,
        "effectsExecuted": 0,
        "wakeProgramTree": frozen._program_tree(repository_root),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument(
        "--source", choices=("audio_arena", "minds14"), required=True
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--model-archive", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    report = evaluate(arguments)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "schema": report["schema"],
                "source": report["source"],
                "status": report["status"],
                "sha256": sha256(arguments.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
