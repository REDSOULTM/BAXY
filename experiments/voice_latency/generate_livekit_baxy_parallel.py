"""Benchmark concurrent LiveKit wake-word positive and negative generation.

The upstream generator processes all four speech splits serially.  On the
6 GiB validation GPU that leaves substantial compute idle while VITS prepares
each batch.  This research-only driver runs one positive and one adversarial
negative worker, each with a deliberately smaller batch.  Sustained runs on
that GPU showed that the two independent CUDA allocator caches can eventually
consume unsafe headroom even when short smokes look healthy.  Use the upstream
single-process generator for full campaigns unless the target GPU has enough
measured long-run margin.  This driver preserves the upstream naming/resume
contract so its valid clips remain consumable after a switch back to upstream.

On Windows the eSpeak NG bridge used by the repository must be on ``PATH``.
The script never modifies the installed BAXY runtime.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

from livekit.wakeword.config import WakeWordConfig, load_config
from livekit.wakeword.data.generate import (
    _count_original_clips,
    _generate_background_clips,
    generate_adversarial_phrases,
    get_tts_backend,
)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _resolved_config(
    config_path: Path,
    *,
    model_name: str | None,
    n_samples: int | None,
    n_samples_val: int | None,
    n_background_samples: int | None,
    n_background_samples_val: int | None,
    batch_size: int,
) -> WakeWordConfig:
    config = load_config(config_path)
    updates: dict[str, object] = {"tts_batch_size": batch_size}
    if model_name is not None:
        updates["model_name"] = model_name
    if n_samples is not None:
        updates["n_samples"] = n_samples
    if n_samples_val is not None:
        updates["n_samples_val"] = n_samples_val
    if n_background_samples is not None:
        updates["n_background_samples"] = n_background_samples
    if n_background_samples_val is not None:
        updates["n_background_samples_val"] = n_background_samples_val
    return config.model_copy(update=updates)


def _synthesize_split(
    config: WakeWordConfig,
    *,
    split_name: str,
    phrases: list[str],
    target_count: int,
) -> None:
    split_dir = config.model_output_dir / split_name
    existing = _count_original_clips(split_dir)
    if existing >= target_count:
        return
    tts = get_tts_backend(config)
    tts.validate_artifacts()
    tts.synthesize_clips(
        phrases=phrases,
        output_dir=split_dir,
        n_samples=target_count,
        start_index=existing,
        batch_size=config.tts_batch_size,
    )


def _speech_worker(
    config_path_text: str,
    model_name: str | None,
    n_samples: int | None,
    n_samples_val: int | None,
    n_background_samples: int | None,
    n_background_samples_val: int | None,
    batch_size: int,
    role: str,
) -> None:
    config = _resolved_config(
        Path(config_path_text),
        model_name=model_name,
        n_samples=n_samples,
        n_samples_val=n_samples_val,
        n_background_samples=n_background_samples,
        n_background_samples_val=n_background_samples_val,
        batch_size=batch_size,
    )
    if role == "positive":
        phrases = list(config.target_phrases)
        names = ("positive_train", "positive_test")
    elif role == "negative":
        phrases = generate_adversarial_phrases(list(config.target_phrases))
        phrases.extend(config.custom_negative_phrases)
        if not phrases:
            phrases = ["hello", "okay", "hey", "stop", "go", "yes", "no"]
        names = ("negative_train", "negative_test")
    else:
        raise ValueError(f"unknown worker role: {role}")

    _synthesize_split(
        config,
        split_name=names[0],
        phrases=phrases,
        target_count=config.n_samples,
    )
    _synthesize_split(
        config,
        split_name=names[1],
        phrases=phrases,
        target_count=config.n_samples_val,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--model-name")
    parser.add_argument("--n-samples", type=_positive_int)
    parser.add_argument("--n-samples-val", type=_positive_int)
    parser.add_argument("--n-background-samples", type=_nonnegative_int)
    parser.add_argument("--n-background-samples-val", type=_nonnegative_int)
    # Sustained runs cache more memory than short smokes: two x 32 reached
    # ~5.50 GiB, two x 24 reached ~5.18 GiB, two x 20 reached ~5.27 GiB, and
    # even two x 16 eventually reached ~5.64 GiB on the 6 GiB validation GPU.
    # The conservative default is useful for bounded benchmarks only; it is
    # not evidence that a full two-worker campaign is safe on a 6 GiB device.
    parser.add_argument("--batch-size", type=_positive_int, default=8)
    return parser


def main() -> int:
    args = _parser().parse_args()
    config_path = args.config.resolve()
    config = _resolved_config(
        config_path,
        model_name=args.model_name,
        n_samples=args.n_samples,
        n_samples_val=args.n_samples_val,
        n_background_samples=args.n_background_samples,
        n_background_samples_val=args.n_background_samples_val,
        batch_size=args.batch_size,
    )
    config.model_output_dir.mkdir(parents=True, exist_ok=True)

    worker_args = (
        str(config_path),
        args.model_name,
        args.n_samples,
        args.n_samples_val,
        args.n_background_samples,
        args.n_background_samples_val,
        args.batch_size,
    )
    context = mp.get_context("spawn")
    started = time.perf_counter()
    workers = [
        context.Process(target=_speech_worker, args=(*worker_args, role), name=role)
        for role in ("positive", "negative")
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    failed = {worker.name: worker.exitcode for worker in workers if worker.exitcode != 0}
    if failed:
        raise RuntimeError(f"speech generation workers failed: {failed}")

    if config.n_background_samples:
        _generate_background_clips(config, "background_train", config.n_background_samples)
    if config.n_background_samples_val:
        _generate_background_clips(config, "background_test", config.n_background_samples_val)

    wav_files = list(config.model_output_dir.rglob("*.wav"))
    report = {
        "schema": "baxy-livekit-parallel-generation-v1",
        "model_name": config.model_name,
        "workers": 2,
        "batch_size_per_worker": config.tts_batch_size,
        "elapsed_s": round(time.perf_counter() - started, 3),
        "wav_files": len(wav_files),
        "wav_bytes": sum(path.stat().st_size for path in wav_files),
        "output_dir": str(config.model_output_dir.resolve()),
    }
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
