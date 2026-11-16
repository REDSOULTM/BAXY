"""What a GGUF's header says about the memory its model takes on the graphics card: the App's GgufShape and ModelMemory
(src/Baxy.App/GgufShape.cs, ModelMemory.cs), read the same way here for the mind's own server (llm_server.card_mib).

MOD5 (MOD2 §1, point 2: «la memoria se calcula con las cifras del 4B»): the server's line over the cells was measured
with the factory's model alone; another GGUF in the mind's engine was said to fit when it did not, or the other way
round. Its header says what changes: the weights the card keeps, which layers keep a KV cache and how wide, the window of
those that slide, the recurrent state of a hybrid, and its own context. Source: the GGUF specification (docs/gguf.md in
ggml's repository: magic, version, counts, the key-value pairs, then each tensor's name, shape, type and offset), and
llama.cpp's own sizes as ModelMemory cites them (llama-kv-cache.cpp, llama-kv-cache-iswa.cpp, llama-hparams.cpp).
"""
from __future__ import annotations

import math
import os
import struct
from dataclasses import dataclass
from typing import BinaryIO

MIB = 1 << 20
# llama.cpp's micro-batch (-ub, 512 by default): the activations the compute buffer holds at once (ModelMemory.MicroBatch).
MICRO_BATCH = 512
# A header past this is not read (GgufShape.MostHeaderBytes).
MOST_HEADER_BYTES = 64 << 20


@dataclass(frozen=True)
class GgufShape:
    """The App's GgufShape, with the file's size and whether the output matrix is the token embedding (tied)."""
    architecture: str
    layers: int
    context_length: int
    embedding: int
    feed_forward: int
    full_cell_values: int
    sliding_cell_values: int
    sliding_window: int
    layer_cell_values: int
    recurrent_values: int
    token_embedding_bytes: int | None
    input_bytes: int
    file_bytes: int
    tied: bool
    has_tools: bool


# ggml's block sizes (ggml.c, type_traits: bytes per block, values per block), as GgufShape.TensorBytes has them.
_BLOCKS = {0: (4, 1), 1: (2, 1), 30: (2, 1), 2: (18, 32), 3: (20, 32), 6: (22, 32), 7: (24, 32), 8: (34, 32),
           20: (18, 32), 10: (84, 256), 11: (110, 256), 12: (144, 256), 13: (176, 256), 14: (210, 256), 23: (136, 256)}
# The tables llama.cpp reads rows of at the input (LLM_TENSOR_LAYER_INPUT, GGML_OP_GET_ROWS in llama-arch.cpp): kept in the
# PC's RAM, never on the card (the output's copy of a tied token embedding aside).
_INPUT_TENSORS = ("token_embd.weight", "per_layer_token_embd.weight", "token_types.weight", "position_embd.weight")
_SCALARS = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


class _Reader:
    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream
        self._read = 0

    def bytes(self, count: int) -> bytes:
        if count < 0 or self._read + count > MOST_HEADER_BYTES:
            raise ValueError("the GGUF header is larger than expected")
        data = self._stream.read(count)
        if len(data) != count:
            raise EOFError("the GGUF header ends early")
        self._read += count
        return data

    def skip(self, count: int) -> None:
        self.bytes(count) if count <= 4096 else self._skip_long(count)

    def _skip_long(self, count: int) -> None:
        if self._read + count > MOST_HEADER_BYTES:
            raise ValueError("the GGUF header is larger than expected")
        self._stream.seek(count, os.SEEK_CUR)
        self._read += count

    def u32(self) -> int:
        return struct.unpack("<I", self.bytes(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self.bytes(8))[0]

    def text(self) -> str:
        return self.bytes(self.u64()).decode("utf-8", errors="replace")

    def value(self, kind: int, keep_text: bool) -> object:
        """A number, a list of numbers, or a text (only when ``keep_text``: the chat template); None for what is not used."""
        if kind == 8:
            length = self.u64()
            if keep_text:
                return self.bytes(length).decode("utf-8", errors="replace")
            self.skip(length)
            return None
        if kind == 9:
            inner, count = self.u32(), self.u64()
            if inner == 8:
                for _ in range(count):
                    self.skip(self.u64())
                return None
            fmt = _SCALARS.get(inner)
            if fmt is None:
                raise ValueError(f"unknown GGUF value type {inner}")
            size = struct.calcsize(fmt)
            if count > 4096:
                self.skip(size * count)
                return None
            return [struct.unpack(fmt, self.bytes(size))[0] for _ in range(count)]
        fmt = _SCALARS.get(kind)
        if fmt is None:
            raise ValueError(f"unknown GGUF value type {kind}")
        return struct.unpack(fmt, self.bytes(struct.calcsize(fmt)))[0]


def read(path: str) -> GgufShape | None:
    """The shape a GGUF file's header gives; None when it is not one this reads (or cannot be read)."""
    try:
        with open(path, "rb") as file:
            return _read(file, os.fstat(file.fileno()).st_size)
    except (OSError, ValueError, EOFError, OverflowError, struct.error):
        return None


def _read(stream: BinaryIO, file_bytes: int) -> GgufShape | None:
    reader = _Reader(stream)
    if reader.bytes(4) != b"GGUF" or reader.u32() not in (2, 3):
        return None
    tensor_count, key_count = reader.u64(), reader.u64()
    keys: dict[str, object] = {}
    for _ in range(key_count):
        key = reader.text()
        value = reader.value(reader.u32(), keep_text=key in ("general.architecture", "tokenizer.chat_template"))
        if value is not None:
            keys[key] = value
    architecture = keys.get("general.architecture")
    if not isinstance(architecture, str):
        return None
    embedding_bytes: int | None = None
    input_bytes = 0
    tied = True
    for _ in range(tensor_count):
        name = reader.text()
        elements = 1
        for _ in range(reader.u32()):
            elements *= reader.u64()
        kind = reader.u32()
        reader.u64()
        if name in _INPUT_TENSORS and kind in _BLOCKS:
            size, values = _BLOCKS[kind]
            input_bytes += elements // values * size
            embedding_bytes = elements // values * size if name == "token_embd.weight" else embedding_bytes
        elif name == "output.weight":
            tied = False
    template = keys.get("tokenizer.chat_template")
    return _shape(keys, architecture, embedding_bytes, input_bytes, file_bytes, tied,
                  isinstance(template, str) and "tools" in template)


def _shape(keys: dict[str, object], architecture: str, embedding_bytes: int | None, input_bytes: int, file_bytes: int,
           tied: bool,
           has_tools: bool) -> GgufShape | None:
    def numbers(name: str) -> list[int] | None:
        value = keys.get(f"{architecture}.{name}")
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return [int(value)]
        if isinstance(value, list) and all(isinstance(item, (int, float)) for item in value):
            return [int(item) for item in value]
        return None

    def number(name: str, otherwise: int) -> int:
        values = numbers(name)
        return values[0] if values else otherwise

    layers = number("block_count", 0)
    heads = numbers("attention.head_count")
    kv_heads = numbers("attention.head_count_kv") or heads
    if layers <= 0 or not heads or not kv_heads:
        return None
    embedding = number("embedding_length", 0)
    head_width = embedding // heads[0] if heads[0] > 0 else 0
    key_width = number("attention.key_length", head_width)
    value_width = number("attention.value_length", head_width)
    # A sliding layer's own widths where the GGUF gives them (Gemma 3n and 4: «key_length_swa», llama-hparams.h n_embd_head_k_swa).
    sliding_width = number("attention.key_length_swa", key_width) + number("attention.value_length_swa", value_width)
    interval = number("full_attention_interval", 0)
    window = number("attention.sliding_window", 0)
    pattern = keys.get(f"{architecture}.attention.sliding_window_pattern")
    has_state = f"{architecture}.ssm.state_size" in keys
    # The last «shared_kv_layers» layers read the cache of earlier ones and keep none of their own (llama-hparams.h,
    # n_layer_kv_from_start; llama-model.cpp, Gemma 3n and 4).
    keeping = layers - max(number("attention.shared_kv_layers", 0), 0)
    full = slides = recurrent = 0
    full_values = sliding_values = widest = 0
    for layer in range(layers):
        each = kv_heads[layer] if len(kv_heads) == layers else kv_heads[0]
        values = each * (key_width + value_width)
        attends = (layer + 1) % interval == 0 if interval > 0 else values > 0
        if not attends:
            recurrent += 1
            continue
        slide = window > 0 and _slides(architecture, pattern if isinstance(pattern, list) else None, layer)
        values = each * sliding_width if slide else values
        widest = max(widest, values)
        if layer >= keeping:
            continue
        if slide:
            slides += 1
            sliding_values += values
        else:
            full += 1
            full_values += values
    if has_state and recurrent == 0:
        recurrent = layers
    kernel, state, inner = number("ssm.conv_kernel", 0), number("ssm.state_size", 0), number("ssm.inner_size", 0)
    groups = number("ssm.group_count", 0)
    state_values = (max(kernel - 1, 0) * (inner + 2 * groups * state) + state * inner) if has_state else 0
    feed = numbers("feed_forward_length")
    feed_forward = max(max(feed) if feed else 0,
                       number("expert_feed_forward_length", 0) * max(number("expert_used_count", 1), 1))
    return GgufShape(architecture, layers, number("context_length", 0), embedding, feed_forward, full_values,
                     sliding_values, window, widest, recurrent * state_values, embedding_bytes, input_bytes, file_bytes,
                     tied,
                     has_tools)


def _slides(architecture: str, pattern: list | None, layer: int) -> bool:
    """GgufShape.Slides: the GGUF's own pattern (true for a sliding layer), or llama.cpp's set in code."""
    if pattern:
        return bool(pattern[layer % len(pattern)])
    if architecture in ("gemma2", "gpt-oss"):
        return layer % 2 == 0
    if architecture == "gemma3":
        return (layer + 1) % 6 != 0
    return False


# The bytes a cache of this type keeps per value (ModelMemory.CacheBytesPerValue).
_CACHE_BYTES = {"f16": 2.0, "bf16": 2.0, "q8_0": 34 / 32, "q5_1": 24 / 32, "q5_0": 22 / 32, "q4_1": 20 / 32,
                "q4_0": 18 / 32}


def gpu_bytes(shape: GgufShape, context: int, kv: str = "q8_0", output_in_ram: bool = True) -> int:
    """ModelMemory.GpuBytes without the CUDA runtime's fixed part and with no projector: what llama.cpp keeps on the card
    for this model at ``context`` cells. The weights: the file, less the token embedding where the card does not keep
    it (the output kept in RAM, or an output matrix of its own: the input's copy is always in RAM). The KV cache of
    each layer that keeps one, rounded up to 256 cells (a sliding layer, its window and a batch). The recurrent state, in
    f32, for one slot. The compute buffer: the batch's activations and, per cell, an f16 copy of the widest layer's K
    and V and the f16 mask."""
    cells = (max(context, 1) + 255) // 256 * 256
    keeps_embedding = shape.tied and not output_in_ram
    weights = shape.file_bytes - shape.input_bytes + ((shape.token_embedding_bytes or 0) if keeps_embedding else 0)
    sliding = min(cells, (shape.sliding_window + MICRO_BATCH + 255) // 256 * 256)
    cache = (shape.full_cell_values * cells + shape.sliding_cell_values * sliding) * _CACHE_BYTES.get(kv, 4.0)
    state = shape.recurrent_values * 4
    compute = 4 * MICRO_BATCH * (3 * shape.feed_forward + 6 * shape.embedding) + cells * (
        2 * shape.layer_cell_values + 2 * MICRO_BATCH)
    return weights + math.ceil(cache) + state + compute
