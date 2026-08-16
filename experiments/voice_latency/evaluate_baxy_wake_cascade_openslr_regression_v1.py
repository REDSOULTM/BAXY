"""Screen the production wake cascade on the opened 100-hour negative corpus.

The corpus is no longer blind, so this is development regression evidence and
cannot approve a wake asset.  CUDA performs a deliberately broad screen.  The
fixed CPU ONNX graphs then rescore every screened window and the product
Parakeet recognizer adjudicates only weak lexical-rescue proposals.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.wake_cascade import (  # noqa: E402
    EXPECTED_ACOUSTIC_ALIASES,
    WINDOW_SAMPLES,
    has_strict_leading_alias,
    load_wake_cascade_candidate_config,
    numpy_log_mel_spectrogram,
    upstream_logits_candidate,
)


SCHEMA = "baxy.wake-cascade-openslr-negative-regression.v1"
CHECKPOINT_SCHEMA = "baxy.wake-cascade-openslr-screen-checkpoint.v1"
EXACT_CHECKPOINT_SCHEMA = "baxy.wake-cascade-openslr-exact-checkpoint.v1"
SAMPLE_RATE = 16_000
SCREEN_MARGIN = 0.50
MINIMUM_PARITY_SAFETY_MULTIPLIER = 25.0
MAXIMUM_PARITY_DRIFT = SCREEN_MARGIN / MINIMUM_PARITY_SAFETY_MULTIPLIER


def load_component(filename: str, name: str) -> Any:
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"wake_cascade_regression_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_AUDIO = load_component(
    "audit_openslr_librispeech_retained_parakeet.py",
    "_wake_cascade_regression_audio_v1",
)
_HYPER = load_component(
    "evaluate_baxy_hyperspotter_human_development_v1.py",
    "_wake_cascade_regression_hyper_v1",
)
_LEXICAL = load_component(
    "run_lexical_wake_physical_room_gate_v1.py",
    "_wake_cascade_regression_lexical_v1",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("wake_cascade_regression_json_invalid")
    return value


def stream_audio(audio: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("wake_cascade_regression_audio_invalid")
    right = max(SAMPLE_RATE, WINDOW_SAMPLES - SAMPLE_RATE - len(values))
    return np.pad(values, (SAMPLE_RATE, right))


def window_views(audio: np.ndarray, hop_samples: int) -> list[np.ndarray]:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if hop_samples < 1 or len(values) < WINDOW_SAMPLES:
        raise ValueError("wake_cascade_regression_window_contract_invalid")
    return [
        np.ascontiguousarray(values[end - WINDOW_SAMPLES : end])
        for end in range(WINDOW_SAMPLES, len(values) + 1, hop_samples)
    ]


def broad_screen(logits: np.ndarray, config: Any | None = None) -> np.ndarray:
    values = np.asarray(logits, dtype=np.float32)
    if (
        values.ndim != 2
        or values.shape[1] != len(EXPECTED_ACOUSTIC_ALIASES)
        or not np.isfinite(values).all()
    ):
        raise ValueError("wake_cascade_regression_logits_invalid")
    ordered = np.sort(values, axis=1)
    selected = np.logical_and(
        ordered[:, -1] >= 0.5 - SCREEN_MARGIN,
        ordered[:, -2] >= 0.3 - SCREEN_MARGIN,
    )
    if (
        config is not None
        and config.rescue_alias_index is not None
        and config.rescue_alias_threshold is not None
    ):
        selected = np.logical_or(
            selected,
            values[:, config.rescue_alias_index]
            >= config.rescue_alias_threshold - SCREEN_MARGIN,
        )
    return selected


def lexical_capture(audio: np.ndarray, *, window_index: int, hop_samples: int) -> np.ndarray:
    """Approximate the product five-second pre-roll at a proposal boundary."""

    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    if window_index < 0 or hop_samples < 1:
        raise ValueError("wake_cascade_regression_lexical_window_invalid")
    raw_end = WINDOW_SAMPLES + window_index * hop_samples - SAMPLE_RATE
    start = max(0, raw_end - 5 * SAMPLE_RATE)
    return np.ascontiguousarray(
        np.concatenate((values[start:], np.zeros(SAMPLE_RATE, np.float32)))
    )


def gpu_logmel(torch: Any, audio: np.ndarray, filters: Any, window: Any) -> Any:
    tensor = torch.from_numpy(np.asarray(audio, dtype=np.float32)).cuda()
    padded = torch.nn.functional.pad(
        tensor[:, None, :], (200, 200), mode="reflect"
    )[:, 0, :]
    frames = padded.unfold(1, 400, 160)
    stft = torch.fft.rfft(frames * window, n=400, dim=2)
    magnitudes = stft.abs().square()[:, :-1, :]
    mel = magnitudes @ filters.T
    log_spec = torch.log10(torch.clamp_min(mel, 1e-10))
    log_spec = torch.maximum(
        log_spec, log_spec.amax(dim=(1, 2), keepdim=True) - 8.0
    )
    return ((log_spec + 4.0) / 4.0).float()


class GpuHyperSpotter:
    def __init__(
        self,
        *,
        checkpoint: Path,
        hyperspotter_root: Path,
        hyperspotter_site_packages: Path,
        official_checkpoint: Path,
    ) -> None:
        model, tokenizer, torch, _device, metadata = _HYPER.load_candidate(
            hyperspotter_root=hyperspotter_root,
            hyperspotter_site_packages=hyperspotter_site_packages,
            official_checkpoint_path=official_checkpoint,
            candidate_checkpoint_path=checkpoint,
            device="cuda",
        )
        aliases = list(metadata["aliases"])
        if aliases != list(EXPECTED_ACOUSTIC_ALIASES):
            raise ValueError("wake_cascade_regression_alias_mismatch")
        ids = tokenizer(aliases)["input_ids"]
        lengths = torch.tensor([len(value) for value in ids], dtype=torch.long)
        values = torch.nn.utils.rnn.pad_sequence(
            [torch.tensor(value, dtype=torch.long) for value in ids],
            padding_value=tokenizer.pad_token_id,
            batch_first=True,
        ).cuda()
        with torch.inference_mode():
            weights = model.get_text_weights(values, lengths).detach()
        self.model = model
        self.weights = weights
        self.torch = torch

    def predict(self, logmel: Any) -> np.ndarray:
        torch = self.torch
        batch = int(logmel.shape[0])
        with torch.inference_mode():
            lengths = torch.full(
                (batch,), 300, dtype=torch.long, device=logmel.device
            )
            encoded, _ = self.model.audio_encoder(logmel.transpose(1, 2), lengths)
            encoded = encoded[:, :74, :]
            mask = torch.ones((batch, 74), dtype=torch.bool, device=logmel.device)
            outputs = [
                self.model.perceiver_classifier(
                    encoded,
                    self.weights[index : index + 1].expand(
                        batch, *self.weights.shape[1:]
                    ),
                    mask=mask,
                )
                for index in range(len(EXPECTED_ACOUSTIC_ALIASES))
            ]
            return torch.cat(outputs, dim=1).float().cpu().numpy()


def _source_contract(
    *,
    cascade_manifest: Path,
    fusion_paths: tuple[Path, ...],
    checkpoint_paths: tuple[Path, ...],
) -> dict[str, str]:
    cascade = read_object(cascade_manifest)
    fusions = [read_object(path) for path in fusion_paths]
    sources = cascade.get("sources")
    fusion_hashes = [sha256(path) for path in fusion_paths]
    checkpoint_hashes = [sha256(path) for path in checkpoint_paths]
    if not isinstance(sources, dict) or len(fusions) != len(checkpoint_paths):
        raise ValueError("wake_cascade_regression_source_mismatch")
    declared_fusions = sources.get("fusionManifestSha256")
    if isinstance(declared_fusions, list):
        source_match = declared_fusions == fusion_hashes
    else:
        source_match = (
            len(fusion_hashes) == 2
            and sources.get("originalFusionManifestSha256") == fusion_hashes[0]
            and sources.get("adaptedFusionManifestSha256") == fusion_hashes[1]
        )
    checkpoint_match = all(
        isinstance(fusion.get("sources"), dict)
        and fusion["sources"].get("candidateCheckpointSha256") == checkpoint_hash
        for fusion, checkpoint_hash in zip(
            fusions, checkpoint_hashes, strict=True
        )
    )
    if not source_match or not checkpoint_match:
        raise ValueError("wake_cascade_regression_source_mismatch")
    identities = {"cascadeManifestSha256": sha256(cascade_manifest)}
    for index, (fusion_hash, checkpoint_hash) in enumerate(
        zip(fusion_hashes, checkpoint_hashes, strict=True)
    ):
        identities[f"fusionManifest{index}Sha256"] = fusion_hash
        identities[f"checkpoint{index}Sha256"] = checkpoint_hash
    return identities


def _write_checkpoint(
    path: Path,
    *,
    identities: dict[str, str],
    completed_records: int,
    windows: int,
    screened: list[dict[str, int]],
    parity_drifts: list[float],
    elapsed_seconds: float,
) -> None:
    value = {
        "schema": CHECKPOINT_SCHEMA,
        "identities": identities,
        "completedRecords": completed_records,
        "windows": windows,
        "screened": screened,
        "parityDrifts": parity_drifts,
        "elapsedSeconds": elapsed_seconds,
    }
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_checkpoint(
    path: Path, identities: dict[str, str]
) -> tuple[int, int, list[dict[str, int]], list[float], float]:
    if not path.exists():
        return 0, 0, [], [], 0.0
    value = read_object(path)
    if (
        value.get("schema") != CHECKPOINT_SCHEMA
        or value.get("identities") != identities
        or not isinstance(value.get("completedRecords"), int)
        or not isinstance(value.get("windows"), int)
        or not isinstance(value.get("screened"), list)
        or not isinstance(value.get("parityDrifts"), list)
        or not isinstance(value.get("elapsedSeconds"), (int, float))
    ):
        raise ValueError("wake_cascade_regression_checkpoint_invalid")
    return (
        int(value["completedRecords"]),
        int(value["windows"]),
        list(value["screened"]),
        [float(item) for item in value["parityDrifts"]],
        float(value["elapsedSeconds"]),
    )


def _write_exact_checkpoint(
    path: Path,
    *,
    identities: dict[str, str],
    scan_checkpoint_sha256: str,
    completed_records: int,
    exact_proposals: int,
    lexical_invocations: int,
    strong_false: list[str],
    lexical_false: list[str],
    elapsed_seconds: float,
) -> None:
    value = {
        "schema": EXACT_CHECKPOINT_SCHEMA,
        "identities": identities,
        "scanCheckpointSha256": scan_checkpoint_sha256,
        "completedRecords": completed_records,
        "exactProposals": exact_proposals,
        "lexicalInvocations": lexical_invocations,
        "strongFalseAudioSha256": strong_false,
        "lexicalFalseAudioSha256": lexical_false,
        "elapsedSeconds": elapsed_seconds,
    }
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_exact_checkpoint(
    path: Path,
    *,
    identities: dict[str, str],
    scan_checkpoint_sha256: str,
) -> tuple[int, int, int, list[str], list[str], float]:
    if not path.exists():
        return 0, 0, 0, [], [], 0.0
    value = read_object(path)
    string_lists = ("strongFalseAudioSha256", "lexicalFalseAudioSha256")
    if (
        value.get("schema") != EXACT_CHECKPOINT_SCHEMA
        or value.get("identities") != identities
        or value.get("scanCheckpointSha256") != scan_checkpoint_sha256
        or not isinstance(value.get("completedRecords"), int)
        or not isinstance(value.get("exactProposals"), int)
        or not isinstance(value.get("lexicalInvocations"), int)
        or not isinstance(value.get("elapsedSeconds"), (int, float))
        or any(
            not isinstance(value.get(name), list)
            or not all(isinstance(item, str) for item in value[name])
            for name in string_lists
        )
    ):
        raise ValueError("wake_cascade_regression_exact_checkpoint_invalid")
    return (
        int(value["completedRecords"]),
        int(value["exactProposals"]),
        int(value["lexicalInvocations"]),
        list(value["strongFalseAudioSha256"]),
        list(value["lexicalFalseAudioSha256"]),
        float(value["elapsedSeconds"]),
    )


def _exact_proposal(
    logmel: np.ndarray, sessions: tuple[Any, Any], config: Any
) -> bool:
    for session in sessions:
        logits = session.run(["logits"], {"logmel": logmel[None, :, :]})[0]
        if upstream_logits_candidate(logits[0], config):
            return True
    return False


def _batched_session_logits(
    session: Any,
    *,
    output_name: str,
    values: list[np.ndarray],
    batch_size: int,
) -> np.ndarray:
    if not values or batch_size < 1:
        raise ValueError("wake_cascade_regression_exact_batch_invalid")
    batches = []
    for start in range(0, len(values), batch_size):
        batch = np.stack(values[start : start + batch_size]).astype(
            np.float32, copy=False
        )
        batches.append(session.run([output_name], {"logmel": batch})[0])
    return np.concatenate(batches, axis=0)


def candidate_windows_by_record(
    upstream_outputs: list[np.ndarray],
    locators: list[tuple[int, int]],
    config: Any,
) -> dict[int, list[int]]:
    if not upstream_outputs or any(len(values) != len(locators) for values in upstream_outputs):
        raise ValueError("wake_cascade_regression_candidate_rows_invalid")
    selected: dict[int, list[int]] = defaultdict(list)
    for row, (record_index, window_index) in enumerate(locators):
        if any(
            upstream_logits_candidate(outputs[row], config)
            for outputs in upstream_outputs
        ):
            selected[record_index].append(window_index)
    return dict(selected)


def candidate_routes_by_record(
    upstream_outputs: list[np.ndarray],
    locators: list[tuple[int, int]],
    config: Any,
) -> dict[int, list[tuple[int, tuple[int, ...]]]]:
    if not upstream_outputs or any(
        len(values) != len(locators) for values in upstream_outputs
    ):
        raise ValueError("wake_cascade_regression_candidate_rows_invalid")
    selected: dict[int, list[tuple[int, tuple[int, ...]]]] = defaultdict(list)
    for row, (record_index, window_index) in enumerate(locators):
        upstream_candidates = tuple(
            upstream_logits_candidate(outputs[row], config)
            for outputs in upstream_outputs
        )
        route_indexes = tuple(
            route_index
            for route_index, route in enumerate(config.routes)
            if any(upstream_candidates[index] for index in route.upstream_indexes)
        )
        if route_indexes:
            selected[record_index].append((window_index, route_indexes))
    return dict(selected)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if (
        output.exists()
        or args.batch_size < 1
        or args.record_batch_size < 1
        or args.exact_batch_size < 1
        or args.exact_record_batch_size < 1
    ):
        raise ValueError("wake_cascade_regression_schedule_invalid")
    expanded_arguments = (args.expanded_fusion, args.expanded_checkpoint)
    if (expanded_arguments[0] is None) != (expanded_arguments[1] is None):
        raise ValueError("wake_cascade_regression_expanded_source_invalid")
    paths = [
        args.cascade_manifest,
        args.original_fusion,
        args.adapted_fusion,
        args.original_checkpoint,
        args.adapted_checkpoint,
        args.corpus_manifest,
        args.ffmpeg,
        args.hyperspotter_root,
        args.hyperspotter_site_packages,
        args.official_checkpoint,
        args.stt_directory,
    ]
    if expanded_arguments[0] is not None:
        paths.extend(expanded_arguments)
    resolved = [path.resolve(strict=True) for path in paths]
    (
        cascade_manifest,
        original_fusion,
        adapted_fusion,
        original_checkpoint,
        adapted_checkpoint,
        corpus_manifest,
        ffmpeg,
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint,
        stt_directory,
        *expanded_resolved,
    ) = resolved
    fusion_paths = (original_fusion, adapted_fusion)
    checkpoint_paths = (original_checkpoint, adapted_checkpoint)
    if expanded_resolved:
        expanded_fusion, expanded_checkpoint = expanded_resolved
        fusion_paths += (expanded_fusion,)
        checkpoint_paths += (expanded_checkpoint,)
    output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output.with_suffix(output.suffix + ".partial.json")
    exact_checkpoint_path = output.with_suffix(
        output.suffix + ".exact.partial.json"
    )
    config = load_wake_cascade_candidate_config(cascade_manifest)
    if (
        len(config.upstream_graph_paths) != len(checkpoint_paths)
        or len(config.verifier_graph_paths) != len(config.verifier_graph_sha256s)
    ):
        raise ValueError("wake_cascade_regression_route_assets_invalid")
    identities = _source_contract(
        cascade_manifest=cascade_manifest,
        fusion_paths=fusion_paths,
        checkpoint_paths=checkpoint_paths,
    )
    identities.update(
        {
            "evaluatorSourceSha256": sha256(Path(__file__).resolve(strict=True)),
            "corpusManifestSha256": sha256(corpus_manifest),
            "ffmpegSha256": sha256(ffmpeg),
            "officialCheckpointSha256": sha256(official_checkpoint),
            "gpuScreenMargin": format(SCREEN_MARGIN, ".17g"),
            "maximumParityDrift": format(MAXIMUM_PARITY_DRIFT, ".17g"),
            "gpuMatmulPrecision": "high",
            "screenBatchSize": str(args.batch_size),
            "screenRecordBatchSize": str(args.record_batch_size),
            "exactBatchSize": str(args.exact_batch_size),
            "exactRecordBatchSize": str(args.exact_record_batch_size),
        }
    )
    corpus = read_object(corpus_manifest)
    records = corpus.get("records")
    if (
        corpus.get("schema") != "baxy.openslr-librispeech-negative-holdout.v1"
        or corpus.get("blind_human_partition_accessed") is not False
        or not isinstance(records, list)
    ):
        raise ValueError("wake_cascade_regression_corpus_invalid")
    root = Path(str(corpus.get("corpus_root") or "")).resolve(strict=True)

    import onnxruntime as ort
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("wake_cascade_regression_cuda_unavailable")
    torch.set_float32_matmul_precision("high")
    torch.backends.cudnn.benchmark = True
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    cpu_upstream = tuple(
        ort.InferenceSession(
            str(path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        for path in config.upstream_graph_paths
    )
    cpu_verifiers = tuple(
        ort.InferenceSession(
            str(path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        for path in config.verifier_graph_paths
    )
    gpu_models = tuple(
        GpuHyperSpotter(
            checkpoint=checkpoint,
            hyperspotter_root=hyperspotter_root,
            hyperspotter_site_packages=hyperspotter_site_packages,
            official_checkpoint=official_checkpoint,
        )
        for checkpoint in checkpoint_paths
    )
    mel_filters = np.load(config.mel_filters_path, allow_pickle=False).astype(np.float32)
    gpu_filters = torch.from_numpy(mel_filters).cuda()
    gpu_window = torch.from_numpy(
        np.hanning(401)[:-1].astype(np.float32)
    ).cuda()
    (
        completed,
        windows_scored,
        screened,
        parity_drifts,
        prior_seconds,
    ) = _load_checkpoint(checkpoint_path, identities)
    scan_started = time.perf_counter()
    batch_counter = 0
    for group_start in range(completed, len(records), args.record_batch_size):
        group = records[group_start : group_start + args.record_batch_size]
        pending_audio: list[np.ndarray] = []
        pending_locator: list[tuple[int, int]] = []

        def flush() -> None:
            nonlocal windows_scored, batch_counter
            if not pending_audio:
                return
            audio_batch = np.stack(pending_audio)
            features = gpu_logmel(torch, audio_batch, gpu_filters, gpu_window)
            predictions = [model.predict(features) for model in gpu_models]
            candidate = np.logical_or.reduce(
                [broad_screen(prediction, config) for prediction in predictions]
            )
            for locator, selected in zip(pending_locator, candidate, strict=True):
                if selected:
                    screened.append(
                        {"record": locator[0], "window": locator[1]}
                    )
            if batch_counter % 100 == 0:
                exact_feature = numpy_log_mel_spectrogram(
                    audio_batch[0], mel_filters
                )
                for session, prediction in zip(
                    cpu_upstream, predictions, strict=True
                ):
                    exact = session.run(
                        ["logits"], {"logmel": exact_feature[None, :, :]}
                    )[0][0]
                    parity_drifts.append(
                        float(np.max(np.abs(exact - prediction[0])))
                    )
            windows_scored += len(pending_audio)
            batch_counter += 1
            pending_audio.clear()
            pending_locator.clear()

        for offset, record in enumerate(group):
            if not isinstance(record, dict):
                raise ValueError("wake_cascade_regression_record_invalid")
            record_index = group_start + offset
            path = (root / str(record.get("relative_path") or "")).resolve(
                strict=True
            )
            path.relative_to(root)
            if sha256(path) != record.get("sha256"):
                raise ValueError("wake_cascade_regression_audio_hash_mismatch")
            audio = _AUDIO.decode_flac(ffmpeg, path)
            if len(audio) != int(record.get("frames") or -1):
                raise ValueError("wake_cascade_regression_audio_length_mismatch")
            for window_index, window_audio in enumerate(
                window_views(stream_audio(audio), config.hop_samples)
            ):
                pending_audio.append(window_audio)
                pending_locator.append((record_index, window_index))
                if len(pending_audio) >= args.batch_size:
                    flush()
        flush()
        completed = group_start + len(group)
        elapsed = prior_seconds + time.perf_counter() - scan_started
        _write_checkpoint(
            checkpoint_path,
            identities=identities,
            completed_records=completed,
            windows=windows_scored,
            screened=screened,
            parity_drifts=parity_drifts,
            elapsed_seconds=elapsed,
        )
        print(
            f"BAXY_WAKE_CASCADE_FAR|{completed}/{len(records)}|"
            f"windows={windows_scored}|screened={len(screened)}",
            flush=True,
        )
    scan_seconds = prior_seconds + time.perf_counter() - scan_started
    maximum_drift = max(parity_drifts, default=math.inf)
    if not math.isfinite(maximum_drift) or maximum_drift > MAXIMUM_PARITY_DRIFT:
        raise ValueError("wake_cascade_regression_parity_invalid")

    by_record: dict[int, list[int]] = defaultdict(list)
    for locator in screened:
        by_record[int(locator["record"])].append(int(locator["window"]))
    scan_checkpoint_sha256 = sha256(checkpoint_path)
    items = sorted(by_record.items())
    (
        exact_completed,
        exact_proposals,
        lexical_invocations,
        strong_false,
        lexical_false,
        prior_exact_seconds,
    ) = _load_exact_checkpoint(
        exact_checkpoint_path,
        identities=identities,
        scan_checkpoint_sha256=scan_checkpoint_sha256,
    )
    if not 0 <= exact_completed <= len(items):
        raise ValueError("wake_cascade_regression_exact_checkpoint_invalid")
    recognizer = None
    rescore_started = time.perf_counter()
    while exact_completed < len(items):
        group_end = min(
            exact_completed + args.exact_record_batch_size, len(items)
        )
        group_items = items[exact_completed:group_end]
        decoded: list[tuple[int, dict[str, Any], np.ndarray, np.ndarray]] = []
        current_features: list[np.ndarray] = []
        current_locators: list[tuple[int, int]] = []
        for local_index, (record_index, indexes) in enumerate(group_items):
            record = records[record_index]
            path = (root / str(record["relative_path"])).resolve(strict=True)
            audio = _AUDIO.decode_flac(ffmpeg, path)
            streamed = stream_audio(audio)
            decoded.append((record_index, record, audio, streamed))
            for window_index in sorted(set(indexes)):
                current_start = window_index * config.hop_samples
                current_features.append(
                    numpy_log_mel_spectrogram(
                        streamed[
                            current_start : current_start + WINDOW_SAMPLES
                        ],
                        mel_filters,
                    )
                )
                current_locators.append((local_index, window_index))
        upstream_outputs = [
            _batched_session_logits(
                session,
                output_name="logits",
                values=current_features,
                batch_size=args.exact_batch_size,
            )
            for session in cpu_upstream
        ]
        selected = candidate_routes_by_record(
            upstream_outputs, current_locators, config
        )
        verifier_features: list[np.ndarray] = []
        verifier_ranges: list[tuple[int, int, int, int, tuple[int, ...]]] = []
        for local_index in sorted(selected):
            _, _, _, streamed = decoded[local_index]
            feature_cache: dict[int, np.ndarray] = {}
            for window_index, route_indexes in selected[local_index]:
                start_index = max(0, window_index - config.history_windows + 1)
                range_start = len(verifier_features)
                for offset in range(start_index, window_index + 1):
                    if offset not in feature_cache:
                        feature_cache[offset] = numpy_log_mel_spectrogram(
                            streamed[
                                offset * config.hop_samples :
                                offset * config.hop_samples + WINDOW_SAMPLES
                            ],
                            mel_filters,
                        )
                    verifier_features.append(feature_cache[offset])
                verifier_ranges.append(
                    (
                        local_index,
                        window_index,
                        range_start,
                        len(verifier_features),
                        route_indexes,
                    )
                )
        verifier_scores = tuple(
            _batched_session_logits(
                session,
                output_name="wake_logit",
                values=verifier_features,
                batch_size=args.exact_batch_size,
            )[:, 0]
            for session in cpu_verifiers
        )
        accepted_records: set[int] = set()
        for local_index, _window_index, start, end, route_indexes in verifier_ranges:
            for route_index in route_indexes:
                route = config.routes[route_index]
                score = float(
                    np.max(verifier_scores[route.verifier_index][start:end])
                )
                if score >= route.verifier_threshold:
                    accepted_records.add(local_index)
                    break
        for local_index in sorted(selected):
            _, record, audio, _ = decoded[local_index]
            exact_proposals += 1
            audio_hash = str(record["sha256"])
            if local_index in accepted_records:
                strong_false.append(audio_hash)
                continue
            if not config.lexical_rescue_enabled:
                continue
            lexical_invocations += 1
            if recognizer is None:
                recognizer, _ = _LEXICAL._recognizer(stt_directory, 5.0)
            transcript, _ = _LEXICAL._decode(
                recognizer,
                lexical_capture(
                    audio,
                    window_index=selected[local_index][0][0],
                    hop_samples=config.hop_samples,
                ),
            )
            if has_strict_leading_alias(transcript, config.lexical_aliases):
                lexical_false.append(audio_hash)
        exact_completed = group_end
        _write_exact_checkpoint(
            exact_checkpoint_path,
            identities=identities,
            scan_checkpoint_sha256=scan_checkpoint_sha256,
            completed_records=exact_completed,
            exact_proposals=exact_proposals,
            lexical_invocations=lexical_invocations,
            strong_false=strong_false,
            lexical_false=lexical_false,
            elapsed_seconds=(
                prior_exact_seconds + time.perf_counter() - rescore_started
            ),
        )
        print(
            f"BAXY_WAKE_CASCADE_EXACT|{exact_completed}/{len(items)}|"
            f"strong={len(strong_false)}|lexical={len(lexical_false)}",
            flush=True,
        )
    exact_seconds = prior_exact_seconds + time.perf_counter() - rescore_started
    false_hashes = sorted(set(strong_false + lexical_false))
    exposure_hours = float(corpus["metrics"]["audio_hours"])
    far_upper = (
        -math.log(0.05) / exposure_hours if not false_hashes else None
    )
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "previously_opened_100h_negative_development_regression",
        "sources": identities,
        "contract": {
            "gpuScreenMargin": SCREEN_MARGIN,
            "maximumObservedGpuToCpuLogitDrift": maximum_drift,
            "minimumScreenSafetyMultiplier": SCREEN_MARGIN / maximum_drift,
            "requiredScreenSafetyMultiplier": MINIMUM_PARITY_SAFETY_MULTIPLIER,
            "gpuMatmulPrecision": "high_tf32_allowed",
            "everyBroadCandidateRescoredByExactCpuOnnx": True,
            "lexicalRescueEnabled": config.lexical_rescue_enabled,
            "lexicalRescueUsesProductParakeet": config.lexical_rescue_enabled,
            "freshHoldoutClaimSupported": False,
            "promotionSupported": False,
        },
        "metrics": {
            "utterances": len(records),
            "descriptiveExposureHours": exposure_hours,
            "windowsScored": windows_scored,
            "broadScreenWindows": len(screened),
            "broadScreenRecords": len(by_record),
            "exactUpstreamProposals": exact_proposals,
            "strongFalseActivations": len(set(strong_false)),
            "lexicalInvocations": lexical_invocations,
            "lexicalFalseActivations": len(set(lexical_false)),
            "negativeFalseActivations": len(false_hashes),
            "pointFalseActivationsPerHour": len(false_hashes) / exposure_hours,
            "far95UpperConfidencePerHourIfZero": far_upper,
        },
        "runtime": {
            "cudaDevice": torch.cuda.get_device_name(0),
            "batchSize": args.batch_size,
            "recordBatchSize": args.record_batch_size,
            "exactBatchSize": args.exact_batch_size,
            "exactRecordBatchSize": args.exact_record_batch_size,
            "screenSeconds": scan_seconds,
            "exactRescoreSeconds": exact_seconds,
        },
        "falseActivationAudioSha256": false_hashes,
        "regressionPassed": not false_hashes,
        "candidateDevelopmentUse": True,
        "candidateFrozen": True,
        "negativeCorpusPreviouslyAccessed": True,
        "blindHumanAudioAccessed": False,
        "transcriptsOrFilenamesRetained": False,
        "effectsExecuted": 0,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    checkpoint_path.unlink(missing_ok=True)
    exact_checkpoint_path.unlink(missing_ok=True)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cascade-manifest", type=Path, required=True)
    parser.add_argument("--original-fusion", type=Path, required=True)
    parser.add_argument("--adapted-fusion", type=Path, required=True)
    parser.add_argument("--expanded-fusion", type=Path)
    parser.add_argument("--original-checkpoint", type=Path, required=True)
    parser.add_argument("--adapted-checkpoint", type=Path, required=True)
    parser.add_argument("--expanded-checkpoint", type=Path)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--record-batch-size", type=int, default=64)
    parser.add_argument("--exact-batch-size", type=int, default=512)
    parser.add_argument("--exact-record-batch-size", type=int, default=64)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    report = evaluate(parse_args())
    print(
        json.dumps(
            {
                "passed": report["regressionPassed"],
                "metrics": report["metrics"],
                "runtime": report["runtime"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["regressionPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
