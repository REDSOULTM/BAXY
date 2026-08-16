"""Build and prove exact overlap-reuse graphs for LiveKit's mel frontend."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

import numpy as np


WINDOW_SAMPLES = 32_000
FRAME_SAMPLES = 512
HOP_SAMPLES = 2_560
MEL_STRIDE_SAMPLES = 160
MEL_FRAMES = 197
POST_BATCH_SIZE = 32


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def runtime_ends(sample_count: int) -> list[int]:
    padded = sample_count + WINDOW_SAMPLES * 2
    padded += (-padded) % FRAME_SAMPLES
    ends = []
    buffered = 0
    since_score = 0
    for end in range(FRAME_SAMPLES, padded + 1, FRAME_SAMPLES):
        buffered = min(WINDOW_SAMPLES, buffered + FRAME_SAMPLES)
        since_score += FRAME_SAMPLES
        if buffered >= WINDOW_SAMPLES and since_score >= HOP_SAMPLES:
            ends.append(end)
            since_score %= HOP_SAMPLES
    return ends


def _set_shape(value: object, dimensions: tuple[str | int, ...]) -> None:
    del value.type.tensor_type.shape.dim[:]
    for dimension in dimensions:
        item = value.type.tensor_type.shape.dim.add()
        if isinstance(dimension, int):
            item.dim_value = dimension
        else:
            item.dim_param = dimension


def build_graphs(source_model: Path, output_directory: Path) -> tuple[Path, Path]:
    import onnx
    from onnx import utils

    raw = output_directory / "melspectrogram-raw-overlap.onnx"
    post = output_directory / "melspectrogram-postprocess-batch.onnx"
    utils.extract_model(
        str(source_model), str(raw), ["input"], ["mel_spectrogram"]
    )
    utils.extract_model(
        str(source_model), str(post), ["mel_spectrogram"], ["output"]
    )
    model = onnx.load(str(post))
    reduce = next(
        (node for node in model.graph.node if node.name == "ReduceMax_24"),
        None,
    )
    clip = next(
        (node for node in model.graph.node if node.name == "Clip_28"), None
    )
    if (
        reduce is None
        or reduce.op_type != "ReduceMax"
        or list(reduce.input) != ["onnx::ReduceMax_31"]
        or clip is None
        or clip.op_type != "Clip"
        or list(clip.input)
        != ["onnx::ReduceMax_31", "onnx::Clip_36", "onnx::Clip_41"]
    ):
        raise ValueError("livekit_mel_source_graph_contract_changed")
    del reduce.attribute[:]
    reduce.attribute.extend(
        [
            onnx.helper.make_attribute("axes", [1, 2, 3]),
            onnx.helper.make_attribute("keepdims", 1),
        ]
    )
    clip.op_type = "Max"
    del clip.input[:]
    clip.input.extend(["onnx::ReduceMax_31", "onnx::Clip_36"])
    retained_initializers = [
        value
        for value in model.graph.initializer
        if value.name != "onnx::Clip_41"
    ]
    del model.graph.initializer[:]
    model.graph.initializer.extend(retained_initializers)
    del model.graph.value_info[:]
    _set_shape(model.graph.input[0], ("batch", 1, "frames", 32))
    _set_shape(model.graph.output[0], ("batch", 1, "frames", 32))
    onnx.checker.check_model(model)
    onnx.save(model, str(post))
    onnx.checker.check_model(str(raw))
    return raw, post


def prove_equivalence(
    source_model: Path, raw_model: Path, post_model: Path
) -> dict[str, object]:
    import onnxruntime as ort

    rng = np.random.default_rng(20_260_804)
    audio = rng.normal(0.0, 0.025, size=30 * 16_000).astype(np.float32)
    audio[: 2 * 16_000] = 0.0
    audio[10 * 16_000 : 12 * 16_000] *= np.float32(0.01)
    padded = np.concatenate(
        [
            np.zeros(WINDOW_SAMPLES, np.float32),
            audio,
            np.zeros(WINDOW_SAMPLES, np.float32),
        ]
    )
    padded = np.pad(padded, (0, (-len(padded)) % FRAME_SAMPLES))
    ends = runtime_ends(len(audio))
    windows = [padded[end - WINDOW_SAMPLES : end] for end in ends]
    source = ort.InferenceSession(
        str(source_model), providers=["CPUExecutionProvider"]
    )
    raw = ort.InferenceSession(str(raw_model), providers=["CPUExecutionProvider"])
    post = ort.InferenceSession(
        str(post_model), providers=["CPUExecutionProvider"]
    )
    started = time.perf_counter()
    expected = np.concatenate(
        [
            source.run(None, {source.get_inputs()[0].name: window[None, :]})[0]
            for window in windows
        ]
    )
    source_seconds = time.perf_counter() - started
    started = time.perf_counter()
    raw_input = raw.get_inputs()[0].name
    raw_windows = [raw.run(None, {raw_input: windows[0][None, :]})[0]]
    if len(ends) > 1:
        segment = padded[ends[1] - WINDOW_SAMPLES : ends[-1]]
        shared = raw.run(None, {raw_input: segment[None, :]})[0]
        raw_windows.extend(
            shared[
                :,
                :,
                index * (HOP_SAMPLES // MEL_STRIDE_SAMPLES) : index
                * (HOP_SAMPLES // MEL_STRIDE_SAMPLES)
                + MEL_FRAMES,
                :,
            ]
            for index in range(len(ends) - 1)
        )
    combined = np.concatenate(raw_windows)
    post_input = post.get_inputs()[0].name
    actual = np.concatenate(
        [
            post.run(
                None, {post_input: combined[start : start + POST_BATCH_SIZE]}
            )[0]
            for start in range(0, len(combined), POST_BATCH_SIZE)
        ]
    )
    overlap_seconds = time.perf_counter() - started
    if not np.array_equal(actual, expected):
        raise ValueError("livekit_mel_overlap_not_exact")
    return {
        "runtime_windows": len(ends),
        "values_compared": int(actual.size),
        "bitwise_equal": True,
        "maximum_absolute_difference": 0.0,
        "source_seconds": source_seconds,
        "overlap_seconds": overlap_seconds,
        "speedup": source_seconds / overlap_seconds,
        "first_runtime_hop_samples": ends[1] - ends[0],
        "steady_runtime_hop_samples": ends[2] - ends[1],
    }


def build(*, source_model: Path, output_directory: Path) -> dict[str, object]:
    source_model = source_model.resolve(strict=True)
    output_directory = output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"livekit_mel_overlap_output_exists:{output_directory}")
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{output_directory.name}.", dir=output_directory.parent
        )
    )
    try:
        raw, post = build_graphs(source_model, temporary)
        equivalence = prove_equivalence(source_model, raw, post)
        report: dict[str, object] = {
            "schema": "baxy.livekit-mel-overlap-models.v1",
            "measured_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": {
                "path": source_model.as_posix(),
                "sha256": sha256(source_model),
            },
            "assets": {
                "raw": raw.name,
                "raw_sha256": sha256(raw),
                "post": post.name,
                "post_sha256": sha256(post),
            },
            "contract": {
                "window_samples": WINDOW_SAMPLES,
                "audio_frame_samples": FRAME_SAMPLES,
                "stage1_hop_samples": HOP_SAMPLES,
                "mel_stride_samples": MEL_STRIDE_SAMPLES,
                "mel_frames": MEL_FRAMES,
                "post_batch_size": POST_BATCH_SIZE,
                "exact_decisions_remain_owned_by_original_runtime": True,
            },
            "equivalence": equivalence,
            "candidate_frozen": False,
            "product_runtime_asset": False,
            "blind_human_partition_accessed": False,
            "effects_executed": 0,
        }
        (temporary / "report.v1.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, output_directory)
        return report
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-model", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build(
        source_model=args.source_model,
        output_directory=args.output_directory,
    )
    print(json.dumps(report["equivalence"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
