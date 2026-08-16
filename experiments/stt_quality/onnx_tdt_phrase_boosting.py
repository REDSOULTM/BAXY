"""Greedy ONNX TDT decoding with catalog phrase boosting.

This development module reuses BAXY's existing Parakeet ONNX exports.  It does
not download, duplicate, or retrain model weights.  The boosting graph mirrors
NeMo's non-uniform Aho-Corasick scoring and is intentionally independent from
the product runtime until a fresh blind gate justifies promotion.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
from pathlib import Path
import sys
import time
from typing import Any, Iterable
import unicodedata

import numpy as np


SAMPLE_RATE = 16_000
WORD_BOUNDARY = "\u2581"


def load_token_table(tokens_path: Path) -> tuple[dict[int, str], dict[str, int]]:
    """Load the exact UTF-8 token table shipped with the ONNX model."""

    id_to_piece: dict[int, str] = {}
    piece_to_id: dict[str, int] = {}
    for line in tokens_path.read_text(encoding="utf-8").splitlines():
        try:
            piece, raw_id = line.rsplit(" ", 1)
            token_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if piece in piece_to_id or token_id in id_to_piece:
            raise ValueError("onnx_tdt_duplicate_token")
        id_to_piece[token_id] = piece
        piece_to_id[piece] = token_id
    if not id_to_piece or sorted(id_to_piece) != list(range(len(id_to_piece))):
        raise ValueError("onnx_tdt_token_ids_not_dense")
    return id_to_piece, piece_to_id


def _index_pieces(piece_to_id: dict[str, int]) -> dict[str, tuple[str, ...]]:
    by_initial: dict[str, list[str]] = {}
    for piece in piece_to_id:
        if not piece or piece.startswith("<") or any(char.isspace() for char in piece):
            continue
        by_initial.setdefault(piece[0], []).append(piece)
    return {
        initial: tuple(sorted(pieces, key=lambda value: (-len(value), value)))
        for initial, pieces in by_initial.items()
    }


def _phrase_value(surface: str) -> str:
    normalized = unicodedata.normalize("NFKC", surface).strip()
    words = normalized.split()
    return WORD_BOUNDARY + WORD_BOUNDARY.join(words) if words else ""


def encode_phrase(
    surface: str,
    piece_to_id: dict[str, int],
) -> tuple[int, ...] | None:
    """Find a deterministic minimum-piece exact BPE path for a phrase."""

    if not isinstance(surface, str):
        raise TypeError("onnx_tdt_phrase_must_be_text")
    value = _phrase_value(surface)
    if not value:
        return None
    pieces_by_initial = _index_pieces(piece_to_id)
    best: list[tuple[str, ...] | None] = [None] * (len(value) + 1)
    best[0] = ()
    for index in range(len(value)):
        prefix = best[index]
        if prefix is None:
            continue
        for piece in pieces_by_initial.get(value[index], ()):
            if not value.startswith(piece, index):
                continue
            end = index + len(piece)
            candidate = (*prefix, piece)
            current = best[end]
            if current is None or (len(candidate), candidate) < (len(current), current):
                best[end] = candidate
    encoded = best[-1]
    return None if encoded is None else tuple(piece_to_id[piece] for piece in encoded)


def phrase_variants(surface: str) -> tuple[str, ...]:
    """Return conservative case/accent variants for a case-sensitive model."""

    exact = unicodedata.normalize("NFKC", surface).strip()
    casefolded = exact.casefold()
    accent_folded = "".join(
        char
        for char in unicodedata.normalize("NFKD", casefolded)
        if not unicodedata.combining(char)
    )
    values: list[str] = []
    for value in (exact, casefolded, accent_folded):
        if value and value not in values:
            values.append(value)
    return tuple(values)


def encode_phrases(
    surfaces: Iterable[str],
    piece_to_id: dict[str, int],
    *,
    include_variants: bool = True,
) -> tuple[tuple[int, ...], ...]:
    """Encode unique phrases, dropping only phrases absent from the vocabulary."""

    encoded: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()
    for surface in surfaces:
        candidates = phrase_variants(surface) if include_variants else (surface,)
        for candidate in candidates:
            token_ids = encode_phrase(candidate, piece_to_id)
            if token_ids and token_ids not in seen:
                seen.add(token_ids)
                encoded.append(token_ids)
    return tuple(encoded)


@dataclass
class _Node:
    children: dict[int, int] = field(default_factory=dict)
    fail: int = 0
    node_score: float = 0.0
    is_end: bool = False


@dataclass(frozen=True)
class BoostingGraph:
    """Dense full-vocabulary score and transition tables for one phrase set."""

    scores: np.ndarray
    next_states: np.ndarray
    phrase_count: int

    @property
    def states(self) -> int:
        return int(self.scores.shape[0])

    @property
    def vocabulary_size(self) -> int:
        return int(self.scores.shape[1])

    def advance(self, state: int, token_id: int) -> tuple[float, int]:
        return float(self.scores[state, token_id]), int(
            self.next_states[state, token_id]
        )


def build_boosting_graph(
    phrases: Iterable[tuple[int, ...]],
    vocabulary_size: int,
    *,
    context_score: float = 1.0,
    depth_scaling: float = 2.0,
) -> BoostingGraph:
    """Build NeMo-compatible non-uniform phrase-boosting transitions."""

    if vocabulary_size < 1:
        raise ValueError("onnx_tdt_boosting_vocabulary_invalid")
    if context_score < 0 or depth_scaling < 1:
        raise ValueError("onnx_tdt_boosting_score_invalid")
    unique_phrases = tuple(dict.fromkeys(tuple(phrase) for phrase in phrases))
    nodes = [_Node()]
    for phrase in unique_phrases:
        if not phrase or any(token < 0 or token >= vocabulary_size for token in phrase):
            raise ValueError("onnx_tdt_boosting_phrase_invalid")
        state = 0
        for depth, token in enumerate(phrase):
            child = nodes[state].children.get(token)
            token_score = (
                context_score
                if depth == 0
                else context_score * depth_scaling + math.log(depth + 1)
            )
            if child is None:
                child = len(nodes)
                nodes[state].children[token] = child
                nodes.append(
                    _Node(node_score=nodes[state].node_score + token_score)
                )
            state = child
        nodes[state].is_end = True

    queue: deque[int] = deque()
    for child in nodes[0].children.values():
        nodes[child].fail = 0
        queue.append(child)
    breadth_first = [0]
    while queue:
        state = queue.popleft()
        breadth_first.append(state)
        for token, child in nodes[state].children.items():
            fail = nodes[state].fail
            while fail and token not in nodes[fail].children:
                fail = nodes[fail].fail
            nodes[child].fail = nodes[fail].children.get(token, 0)
            queue.append(child)

    scores = np.zeros((len(nodes), vocabulary_size), dtype=np.float32)
    next_states = np.zeros((len(nodes), vocabulary_size), dtype=np.int32)
    for token, child in nodes[0].children.items():
        scores[0, token] = nodes[child].node_score
        next_states[0, token] = child
    for state in breadth_first[1:]:
        node = nodes[state]
        fail = node.fail
        backoff = 0.0 if node.is_end else nodes[fail].node_score - node.node_score
        scores[state] = scores[fail] + backoff
        next_states[state] = next_states[fail]
        for token, child in node.children.items():
            scores[state, token] = nodes[child].node_score - node.node_score
            next_states[state, token] = child
    return BoostingGraph(scores, next_states, len(unique_phrases))


def choose_boosted_token(
    token_logits: np.ndarray,
    *,
    blank_id: int,
    state_scores: np.ndarray | None,
    alpha: float,
) -> int:
    """Preserve blank/nonblank category, as NeMo greedy fusion does."""

    unboosted = int(np.argmax(token_logits))
    if unboosted == blank_id or state_scores is None or alpha == 0:
        return unboosted
    nonblank = np.asarray(token_logits[:blank_id], dtype=np.float32)
    return int(np.argmax(nonblank + np.float32(alpha) * state_scores))


def _import_runtime(dependency_root: Path | None) -> tuple[Any, Any]:
    if dependency_root is not None:
        dependency = str(dependency_root.resolve(strict=True))
        if dependency not in sys.path:
            sys.path.insert(0, dependency)
    import kaldi_native_fbank as knf  # type: ignore[import-not-found]
    import onnxruntime as ort

    return knf, ort


class OnnxTdtPhraseBoostingDecoder:
    """CPU ONNX decoder over the exact Parakeet assets used by BAXY."""

    def __init__(
        self,
        model_directory: Path,
        *,
        dependency_root: Path | None = None,
        num_threads: int = 4,
    ) -> None:
        if num_threads < 1:
            raise ValueError("onnx_tdt_threads_invalid")
        self.model_directory = model_directory.resolve(strict=True)
        self.id_to_piece, self.piece_to_id = load_token_table(
            self.model_directory / "tokens.txt"
        )
        self.blank_id = len(self.id_to_piece) - 1
        if self.id_to_piece[self.blank_id] != "<blk>":
            raise ValueError("onnx_tdt_blank_token_invalid")
        self._knf, ort = _import_runtime(dependency_root)
        options = ort.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = num_threads
        self.encoder = ort.InferenceSession(
            str(self.model_directory / "encoder.int8.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.decoder = ort.InferenceSession(
            str(self.model_directory / "decoder.int8.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.joiner = ort.InferenceSession(
            str(self.model_directory / "joiner.int8.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        metadata = self.encoder.get_modelmeta().custom_metadata_map
        self.normalize_type = metadata.get("normalize_type", "")
        self.pred_rnn_layers = int(metadata["pred_rnn_layers"])
        self.pred_hidden = int(metadata["pred_hidden"])

    def compile_graph(
        self,
        phrases: Iterable[str],
        *,
        include_variants: bool = True,
        context_score: float = 1.0,
        depth_scaling: float = 2.0,
    ) -> BoostingGraph:
        token_phrases = encode_phrases(
            phrases,
            self.piece_to_id,
            include_variants=include_variants,
        )
        return build_boosting_graph(
            token_phrases,
            self.blank_id,
            context_score=context_score,
            depth_scaling=depth_scaling,
        )

    def _features(self, audio: np.ndarray) -> np.ndarray:
        options = self._knf.FbankOptions()
        options.frame_opts.dither = 0
        options.frame_opts.remove_dc_offset = False
        options.frame_opts.window_type = "hann"
        options.mel_opts.low_freq = 0
        options.mel_opts.num_bins = 128
        options.mel_opts.is_librosa = True
        fbank = self._knf.OnlineFbank(options)
        fbank.accept_waveform(SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
        features = np.stack(
            [np.asarray(fbank.get_frame(index)) for index in range(fbank.num_frames_ready)]
        ).astype(np.float32, copy=False)
        if self.normalize_type:
            if self.normalize_type != "per_feature":
                raise ValueError("onnx_tdt_normalization_unsupported")
            mean = features.mean(axis=0, keepdims=True)
            # PyTorch's default std uses Bessel's correction (ddof=1).
            stddev = features.std(axis=0, ddof=1, keepdims=True) + np.float32(1e-5)
            features = (features - mean) / stddev
        return features.astype(np.float32, copy=False)

    def _run_decoder(
        self, token: int, state0: np.ndarray, state1: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        outputs = self.decoder.run(
            None,
            {
                self.decoder.get_inputs()[0].name: np.asarray([[token]], dtype=np.int32),
                self.decoder.get_inputs()[1].name: np.asarray([1], dtype=np.int32),
                self.decoder.get_inputs()[2].name: state0,
                self.decoder.get_inputs()[3].name: state1,
            },
        )
        return outputs[0], outputs[2], outputs[3]

    def encode_audio(
        self,
        audio: np.ndarray,
        *,
        leading_silence_seconds: float = 0.2,
        trailing_silence_seconds: float = 0.2,
    ) -> tuple[np.ndarray, float]:
        """Compute acoustic encoder output once for multiple boost candidates."""

        leading = np.zeros(round(SAMPLE_RATE * leading_silence_seconds), np.float32)
        trailing = np.zeros(round(SAMPLE_RATE * trailing_silence_seconds), np.float32)
        padded = np.concatenate(
            [leading, np.asarray(audio, dtype=np.float32).reshape(-1), trailing]
        )
        started = time.perf_counter()
        features = self._features(padded)
        encoder_input = features.T[np.newaxis, :, :]
        encoder_out = self.encoder.run(
            None,
            {
                self.encoder.get_inputs()[0].name: encoder_input,
                self.encoder.get_inputs()[1].name: np.asarray(
                    [encoder_input.shape[-1]], dtype=np.int64
                ),
            },
        )[0]
        return encoder_out, time.perf_counter() - started

    def decode_encoded(
        self,
        encoder_out: np.ndarray,
        *,
        graph: BoostingGraph | None = None,
        alpha: float = 0.0,
    ) -> dict[str, Any]:
        """Decode cached acoustic output with one immutable boosting candidate."""

        if alpha < 0:
            raise ValueError("onnx_tdt_boosting_alpha_invalid")
        if graph is not None and graph.vocabulary_size != self.blank_id:
            raise ValueError("onnx_tdt_boosting_graph_vocabulary_mismatch")
        started = time.perf_counter()
        state0 = np.zeros(
            (self.pred_rnn_layers, 1, self.pred_hidden), dtype=np.float32
        )
        state1 = np.zeros_like(state0)
        decoder_out, state0_next, state1_next = self._run_decoder(
            self.blank_id, state0, state1
        )
        emitted: list[int] = []
        graph_state = 0
        frame = 0
        while frame < encoder_out.shape[2]:
            logits = self.joiner.run(
                None,
                {
                    self.joiner.get_inputs()[0].name: encoder_out[:, :, frame : frame + 1],
                    self.joiner.get_inputs()[1].name: decoder_out,
                },
            )[0].reshape(-1)
            token_logits = logits[: self.blank_id + 1]
            duration_logits = logits[self.blank_id + 1 :]
            state_scores = None if graph is None else graph.scores[graph_state]
            token = choose_boosted_token(
                token_logits,
                blank_id=self.blank_id,
                state_scores=state_scores,
                alpha=alpha,
            )
            skip = max(1, int(np.argmax(duration_logits)))
            if token != self.blank_id:
                emitted.append(token)
                if graph is not None:
                    graph_state = int(graph.next_states[graph_state, token])
                state0, state1 = state0_next, state1_next
                decoder_out, state0_next, state1_next = self._run_decoder(
                    token, state0, state1
                )
            frame += skip
        text = "".join(self.id_to_piece[token] for token in emitted)
        text = text.replace(WORD_BOUNDARY, " ").strip()
        return {
            "text": text,
            "tokenIds": emitted,
            "latencySeconds": time.perf_counter() - started,
            "encoderFrames": int(encoder_out.shape[2]),
            "boostingPhrases": 0 if graph is None else graph.phrase_count,
            "boostingAlpha": alpha,
        }

    def transcribe(
        self,
        audio: np.ndarray,
        *,
        graph: BoostingGraph | None = None,
        alpha: float = 0.0,
        leading_silence_seconds: float = 0.2,
        trailing_silence_seconds: float = 0.2,
    ) -> dict[str, Any]:
        encoder_out, encoding_seconds = self.encode_audio(
            audio,
            leading_silence_seconds=leading_silence_seconds,
            trailing_silence_seconds=trailing_silence_seconds,
        )
        result = self.decode_encoded(encoder_out, graph=graph, alpha=alpha)
        result["encodingSeconds"] = encoding_seconds
        result["decodingSeconds"] = result["latencySeconds"]
        result["latencySeconds"] += encoding_seconds
        return result


def load_wav(path: Path) -> np.ndarray:
    """Load a mono 16 kHz PCM or IEEE-float development WAV."""

    from scipy.io import wavfile

    sample_rate, values = wavfile.read(path)
    if sample_rate != SAMPLE_RATE:
        raise ValueError("onnx_tdt_wav_sample_rate_unsupported")
    if values.ndim == 2:
        values = values[:, 0]
    if np.issubdtype(values.dtype, np.floating):
        return np.asarray(values, dtype=np.float32)
    if values.dtype == np.uint8:
        return (values.astype(np.float32) - np.float32(128.0)) / np.float32(128.0)
    if np.issubdtype(values.dtype, np.signedinteger):
        scale = np.float32(max(abs(np.iinfo(values.dtype).min), np.iinfo(values.dtype).max))
        return values.astype(np.float32) / scale
    raise ValueError("onnx_tdt_wav_format_unsupported")
