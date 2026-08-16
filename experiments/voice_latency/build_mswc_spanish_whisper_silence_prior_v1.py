"""Build candidate text priors by aligning MSWC words against local silence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"mswc_whisper_silence_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ALIGNMENT = load_component(
    "evaluate_mswc_spanish_whisper_forced_alignment_tuning_v9.py",
    "_baxy_mswc_whisper_silence_alignment_v1",
)


def build(
    *,
    hyper_ctc_cache_path: Path,
    model_directory: Path,
    runtime_dll_directory: Path,
    av_site_packages: Path,
    output_cache_path: Path,
    output_report_path: Path,
    cpu_threads: int,
    device: str,
    compute_type: str,
    language: str,
    num_frames: int,
    candidate_batch_size: int,
) -> dict[str, object]:
    started = time.perf_counter()
    if (
        output_cache_path.exists()
        or output_report_path.exists()
        or output_cache_path.suffix.lower() != ".npz"
        or cpu_threads < 1
        or device not in {"cpu", "cuda"}
        or language != "es"
        or num_frames < 1
        or candidate_batch_size < 1
    ):
        raise ValueError("mswc_whisper_silence_schedule_invalid")
    hyper_ctc_cache_path = hyper_ctc_cache_path.resolve(strict=True)
    model_directory = model_directory.resolve(strict=True)
    runtime_dll_directory = runtime_dll_directory.resolve(strict=True)
    av_site_packages = av_site_packages.resolve(strict=True)
    output_cache_path = output_cache_path.resolve()
    output_report_path = output_report_path.resolve()
    for name in ("config.json", "model.bin", "tokenizer.json"):
        if not (model_directory / name).is_file():
            raise ValueError(f"mswc_whisper_silence_model_file_missing:{name}")
    with np.load(hyper_ctc_cache_path, allow_pickle=False) as cache:
        if cache["schema"].tolist() != [
            "baxy.mswc-hyperspotter-ctc-score-cache.v1"
        ]:
            raise ValueError("mswc_whisper_silence_source_schema_invalid")
        class_names = cache["class_names"].astype(str)
    if len(class_names) < 2 or len(set(class_names.tolist())) != len(class_names):
        raise ValueError("mswc_whisper_silence_class_names_invalid")

    dll_handle = os.add_dll_directory(str(runtime_dll_directory))
    os.environ["PATH"] = (
        str(runtime_dll_directory) + os.pathsep + os.environ.get("PATH", "")
    )
    os.environ["OMP_NUM_THREADS"] = str(cpu_threads)
    sys.path.insert(0, str(av_site_packages))
    try:
        import ctranslate2
        from faster_whisper import WhisperModel
        from faster_whisper.audio import pad_or_trim
        from faster_whisper.tokenizer import Tokenizer
    finally:
        sys.path.remove(str(av_site_packages))
    load_started = time.perf_counter()
    model = WhisperModel(
        str(model_directory),
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        local_files_only=True,
    )
    tokenizer = Tokenizer(
        model.hf_tokenizer,
        model.model.is_multilingual,
        task="transcribe",
        language=language,
    )
    load_seconds = time.perf_counter() - load_started
    silence = np.zeros(num_frames * model.feature_extractor.hop_length, dtype=np.float32)
    encoded = model.encode(pad_or_trim(model.feature_extractor(silence)))
    encoded_cpu = np.asarray(encoded.to_device(ctranslate2.Device.cpu))
    tokens = _ALIGNMENT.candidate_token_sequences(
        tokenizer=tokenizer,
        candidates=class_names.tolist(),
        token_prefix="leading_space",
        include_eot=False,
    )
    align_started = time.perf_counter()
    probabilities = _ALIGNMENT.align_candidate_probabilities(
        model=model,
        encoded_audio=encoded_cpu,
        tokenizer=tokenizer,
        token_sequences=tokens,
        num_frames=num_frames,
        candidate_batch_size=candidate_batch_size,
        ctranslate2=ctranslate2,
    )
    align_seconds = time.perf_counter() - align_started
    log_probability_sum = _ALIGNMENT.aggregate_token_probabilities(
        probabilities, length_power=0.0
    )
    output_cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_cache_path,
        schema=np.asarray(["baxy.mswc-whisper-silence-prior.v1"]),
        class_names=class_names,
        log_probability_sum=log_probability_sum.astype(np.float32),
        num_frames=np.asarray([num_frames], dtype=np.int32),
        token_prefix=np.asarray(["leading_space"]),
        include_eot=np.asarray([0], dtype=np.uint8),
        hyper_ctc_cache_sha256=np.asarray(
            [_ALIGNMENT._WHISPER._PARAKEET._AUDIO.sha256(hyper_ctc_cache_path)]
        ),
        model_tree_sha256=np.asarray(
            [_ALIGNMENT._WHISPER._WHISPER_AUDIT.sha256_tree(model_directory)]
        ),
    )
    report: dict[str, object] = {
        "schema": "baxy.mswc-whisper-silence-prior-report.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "tuning_candidate_text_prior_from_local_silence",
        "sources": {
            "hyper_ctc_cache_sha256": _ALIGNMENT._WHISPER._PARAKEET._AUDIO.sha256(
                hyper_ctc_cache_path
            ),
            "model_tree_sha256": _ALIGNMENT._WHISPER._WHISPER_AUDIT.sha256_tree(
                model_directory
            ),
            "output_cache_sha256": _ALIGNMENT._WHISPER._PARAKEET._AUDIO.sha256(
                output_cache_path
            ),
        },
        "contract": {
            "candidate_classes": len(class_names),
            "silence_samples": len(silence),
            "num_frames": num_frames,
            "token_prefix": "leading_space",
            "include_eot": False,
            "candidate_batch_size": candidate_batch_size,
        },
        "aggregates": {
            "log_probability_sum_minimum": float(log_probability_sum.min()),
            "log_probability_sum_mean": float(log_probability_sum.mean()),
            "log_probability_sum_maximum": float(log_probability_sum.max()),
        },
        "runtime": {
            "load_seconds": load_seconds,
            "align_seconds": align_seconds,
            "total_seconds": time.perf_counter() - started,
            "device": device,
            "compute_type": compute_type,
            "ctranslate2": ctranslate2.__version__,
        },
        "research_tuning_examples_scored": False,
        "research_reserved_examples_scored": False,
        "official_test_audio_accessed": False,
        "blind_human_audio_accessed": False,
        "effects_executed": 0,
    }
    output_report_path.parent.mkdir(parents=True, exist_ok=True)
    output_report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    dll_handle.close()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyper-ctc-cache", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--runtime-dll-directory", type=Path, required=True)
    parser.add_argument("--av-site-packages", type=Path, required=True)
    parser.add_argument("--output-cache", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--cpu-threads", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--compute-type", default="int8_float16")
    parser.add_argument("--language", default="es")
    parser.add_argument("--num-frames", type=int, default=100)
    parser.add_argument("--candidate-batch-size", type=int, default=41)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(
        hyper_ctc_cache_path=args.hyper_ctc_cache,
        model_directory=args.model_directory,
        runtime_dll_directory=args.runtime_dll_directory,
        av_site_packages=args.av_site_packages,
        output_cache_path=args.output_cache,
        output_report_path=args.output_report,
        cpu_threads=args.cpu_threads,
        device=args.device,
        compute_type=args.compute_type,
        language=args.language,
        num_frames=args.num_frames,
        candidate_batch_size=args.candidate_batch_size,
    )
    print(json.dumps(report["aggregates"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
