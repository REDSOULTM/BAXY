"""Measure HyperSpotter on opened BAXY wake corpora without touching runtime.

The program is intentionally research-only.  It validates a sealed binding,
loads the upstream Lightning checkpoints with ``weights_only=True``, reads only
the opened corpus WAV files named by their manifests, and retains no filename
or transcript text in its result.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import time
from typing import Any
import wave


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "baxy.hyperspotter-open-vocabulary-wake-pilot-development.v1"
BINDING_SCHEMA = "baxy.hyperspotter-open-vocabulary-wake-pilot-binding.v1"
PREREGISTRATION_SCHEMA = (
    "baxy.hyperspotter-open-vocabulary-wake-pilot-preregistration.v1"
)
EXPECTED_UNSAFE_GLOBALS = frozenset(
    {
        "builtins.dict",
        "collections.defaultdict",
        "omegaconf.base.ContainerMetadata",
        "omegaconf.base.Metadata",
        "omegaconf.dictconfig.DictConfig",
        "omegaconf.nodes.AnyNode",
        "typing.Any",
    }
)
RUNTIME_PACKAGES = (
    "einops",
    "lightning-utilities",
    "numpy",
    "omegaconf",
    "openai-whisper",
    "prettytable",
    "pytorch-lightning",
    "torch",
    "torchaudio",
    "torchmetrics",
    "wandb",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_tree_sha256(root: Path) -> str:
    """Hash an extracted source tree, excluding interpreter cache files."""

    files = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix.lower() not in {".pyc", ".pyo"}
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("hyperspotter_json_object_required")
    return value


def _forbid_v17(paths: Iterable[Path]) -> None:
    if any("v17" in str(path).lower() for path in paths):
        raise ValueError("hyperspotter_physical_v17_forbidden")


def _safe_corpus_path(corpus_root: Path, relative: str) -> Path:
    candidate = (corpus_root / relative).resolve()
    try:
        candidate.relative_to(corpus_root.resolve())
    except ValueError as exc:
        raise ValueError("hyperspotter_manifest_path_escape") from exc
    if candidate.suffix.lower() != ".wav" or not candidate.is_file():
        raise ValueError("hyperspotter_manifest_wav_missing")
    return candidate


def _manifest_records(
    corpus_root: Path,
    manifest: dict[str, Any],
    *,
    expected_positive: int,
    expected_negative: int,
) -> dict[str, list[dict[str, Any]]]:
    counts = manifest.get("counts")
    records = manifest.get("records")
    if (
        not isinstance(counts, dict)
        or counts.get("positive") != expected_positive
        or counts.get("negative") != expected_negative
        or not isinstance(records, list)
    ):
        raise ValueError("hyperspotter_manifest_contract_mismatch")
    grouped: dict[str, list[dict[str, Any]]] = {"positive": [], "negative": []}
    for raw in records:
        if not isinstance(raw, dict):
            raise ValueError("hyperspotter_manifest_record_invalid")
        record_id = raw.get("recordId")
        relative = raw.get("output")
        expected_hash = raw.get("outputSha256")
        if not all(
            isinstance(value, str) for value in (record_id, relative, expected_hash)
        ):
            raise ValueError("hyperspotter_manifest_record_invalid")
        label = record_id.split("/", 1)[0]
        if label not in grouped or not relative.replace("\\", "/").startswith(
            f"{label}/"
        ):
            raise ValueError("hyperspotter_manifest_label_invalid")
        path = _safe_corpus_path(corpus_root, relative)
        if _sha256(path) != expected_hash:
            raise ValueError("hyperspotter_audio_hash_mismatch")
        grouped[label].append({"path": path, "audioSha256": expected_hash})
    if (
        len(grouped["positive"]) != expected_positive
        or len(grouped["negative"]) != expected_negative
    ):
        raise ValueError("hyperspotter_manifest_record_count_mismatch")
    return grouped


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_records(
    records: list[dict[str, Any]], threshold: float
) -> dict[str, Any]:
    probabilities = [float(record["probability"]) for record in records]
    runtimes = [float(record["runtimeSeconds"]) for record in records]
    accepted = sum(probability > threshold for probability in probabilities)
    return {
        "files": len(records),
        "acceptedFiles": accepted,
        "probability": {
            "minimum": min(probabilities) if probabilities else None,
            "p50": _percentile(probabilities, 0.5),
            "p95": _percentile(probabilities, 0.95),
            "maximum": max(probabilities) if probabilities else None,
        },
        "runtimeSeconds": {
            "minimum": min(runtimes) if runtimes else None,
            "p50": _percentile(runtimes, 0.5),
            "p95": _percentile(runtimes, 0.95),
            "maximum": max(runtimes) if runtimes else None,
        },
        "records": records,
        "filenamesRetained": False,
        "transcriptTextRetained": False,
    }


def _runtime_versions() -> dict[str, str]:
    return {name: importlib.metadata.version(name) for name in RUNTIME_PACKAGES}


def whisper_encoder_dimensions(name: str) -> tuple[int, int, int, int, int]:
    dimensions = {
        "tiny": (80, 1500, 384, 6, 4),
        "base": (80, 1500, 512, 8, 6),
    }
    try:
        return dimensions[name]
    except KeyError as exc:
        raise ValueError("hyperspotter_unexpected_whisper_base") from exc


def _safe_checkpoint(path: Path) -> tuple[dict[str, Any], Any]:
    import typing

    import torch
    from omegaconf.base import ContainerMetadata, Metadata
    from omegaconf.dictconfig import DictConfig
    from omegaconf.nodes import AnyNode

    unsafe = frozenset(torch.serialization.get_unsafe_globals_in_checkpoint(path))
    if unsafe != EXPECTED_UNSAFE_GLOBALS:
        raise ValueError("hyperspotter_checkpoint_globals_mismatch")

    def safe_defaultdict(*_args: Any, **_kwargs: Any) -> dict[Any, Any]:
        return {}

    safe_globals = [
        (safe_defaultdict, "collections.defaultdict"),
        typing.Any,
        dict,
        DictConfig,
        ContainerMetadata,
        AnyNode,
        Metadata,
    ]
    with torch.serialization.safe_globals(safe_globals):
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(checkpoint, dict) or not isinstance(
        checkpoint.get("state_dict"), dict
    ):
        raise ValueError("hyperspotter_checkpoint_invalid")
    return checkpoint, checkpoint.get("hyper_parameters")


def _load_candidate(
    source_root: Path,
    checkpoint_path: Path,
    architecture: str,
    device: str,
) -> tuple[Any, Any, Any, dict[str, Any]]:
    import torch

    checkpoint, cfg = _safe_checkpoint(checkpoint_path)
    expected_model = {
        "conformer_hyper": "conformer_hyper_spotter",
        "whisper_hyper": "whisper_hyper_spotter",
    }[architecture]
    if cfg.model.name != expected_model or int(cfg.model.max_context) != 3000:
        raise ValueError("hyperspotter_checkpoint_architecture_mismatch")

    source_text = str(source_root)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    modules = importlib.import_module("src.models.modules")
    tokenizer_module = importlib.import_module("src.processing.tokenizer")

    if architecture == "whisper_hyper":
        import whisper
        from whisper.model import AudioEncoder

        original_load_model = whisper.load_model

        class EncoderOnly:
            def __init__(self, name: str) -> None:
                self.encoder = AudioEncoder(*whisper_encoder_dimensions(name))

        def local_encoder_only(name: str, *_args: Any, **_kwargs: Any) -> EncoderOnly:
            return EncoderOnly(name)

        whisper.load_model = local_encoder_only
        try:
            model = modules.models_factory(cfg.model)
        finally:
            whisper.load_model = original_load_model
    else:
        model = modules.models_factory(cfg.model)

    model_state = {
        key.removeprefix("model."): value
        for key, value in checkpoint["state_dict"].items()
        if key.startswith("model.")
    }
    if len(model_state) != len(checkpoint["state_dict"]):
        raise ValueError("hyperspotter_checkpoint_state_prefix_invalid")
    model.load_state_dict(model_state, strict=True)
    model.to(device)
    model.eval()

    tokenizer = tokenizer_module.CharTokenizer(
        str(source_root / "data" / "char_vocab.txt"),
        str(source_root / "data" / "sub_map.txt"),
    )
    keyword_ids = tokenizer(["baxy"])["input_ids"]
    lengths = torch.tensor([len(keyword_ids[0])], dtype=torch.long, device=device)
    keyword = torch.tensor(keyword_ids, dtype=torch.long, device=device)
    with torch.inference_mode():
        text_weights = model.get_text_weights(keyword, lengths)
    checkpoint_summary = {
        "stateTensorCount": len(model_state),
        "stateElementCount": sum(value.numel() for value in model_state.values()),
        "checkpointEpoch": checkpoint.get("epoch"),
        "checkpointGlobalStep": checkpoint.get("global_step"),
        "checkpointLightningVersion": checkpoint.get("pytorch-lightning_version"),
        "checkpointLoadedWeightsOnly": True,
        "unsafeGlobalsObserved": sorted(EXPECTED_UNSAFE_GLOBALS),
        "unexpectedUnsafeGlobals": [],
    }
    return model, text_weights, cfg, checkpoint_summary


def _read_pcm16_wave(path: Path) -> tuple[Any, int]:
    import numpy as np
    import torch

    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.readframes(source.getnframes())
    if channels < 1 or sample_width != 2 or sample_rate < 1:
        raise ValueError("hyperspotter_pcm16_wav_required")
    samples = np.frombuffer(frames, dtype="<i2")
    if samples.size % channels != 0:
        raise ValueError("hyperspotter_pcm16_wav_shape_invalid")
    mono = samples.reshape(-1, channels).astype(np.float32).mean(axis=1)
    waveform = torch.from_numpy(mono / 32768.0).unsqueeze(0)
    return waveform, sample_rate


def _feature_tensor(path: Path) -> tuple[Any, float]:
    import torchaudio
    import whisper

    started = time.perf_counter()
    waveform, sample_rate = _read_pcm16_wave(path)
    if sample_rate != 16_000:
        waveform = torchaudio.functional.resample(waveform, sample_rate, 16_000)
    features = whisper.log_mel_spectrogram(waveform).squeeze(0).transpose(0, 1)
    return features, time.perf_counter() - started


def _score_records(
    records: list[dict[str, Any]],
    *,
    model: Any,
    text_weights: Any,
    cfg: Any,
    device: str,
    batch_size: int,
    threshold: float,
) -> dict[str, Any]:
    import torch
    import torch.nn.functional as functional

    measured: list[dict[str, Any]] = []
    for offset in range(0, len(records), batch_size):
        batch = records[offset : offset + batch_size]
        features: list[Any] = []
        feature_seconds: list[float] = []
        for record in batch:
            feature, elapsed = _feature_tensor(record["path"])
            if feature.shape[0] > int(cfg.model.max_context) or feature.shape[1] != 80:
                raise ValueError("hyperspotter_feature_shape_invalid")
            features.append(feature)
            feature_seconds.append(elapsed)
        lengths = torch.tensor(
            [item.shape[0] for item in features], dtype=torch.long, device=device
        )
        maximum = torch.zeros((int(cfg.model.max_context), 80), dtype=features[0].dtype)
        padded = torch.nn.utils.rnn.pad_sequence(
            [maximum, *features], batch_first=True, padding_value=0.0
        )[1:].to(device)
        inference_started = time.perf_counter()
        with torch.inference_mode():
            logits = model.run_classifier(padded, text_weights, lengths)
            probabilities = functional.sigmoid(logits).reshape(-1).cpu().tolist()
        inference_per_file = (time.perf_counter() - inference_started) / len(batch)
        for index, (record, probability) in enumerate(
            zip(batch, probabilities, strict=True)
        ):
            measured.append(
                {
                    "record": offset + index,
                    "audioSha256": record["audioSha256"],
                    "probability": float(probability),
                    "accepted": float(probability) > threshold,
                    "runtimeSeconds": feature_seconds[index] + inference_per_file,
                }
            )
    return summarize_records(measured, threshold)


def _validate_binding(
    binding_path: Path,
    preregistration_path: Path,
    binding: dict[str, Any],
    preregistration: dict[str, Any],
    *,
    architecture: str,
    output: Path,
) -> dict[str, Any]:
    if binding.get("schema") != BINDING_SCHEMA:
        raise ValueError("hyperspotter_binding_invalid")
    if preregistration.get("schema") != PREREGISTRATION_SCHEMA:
        raise ValueError("hyperspotter_preregistration_invalid")
    if binding.get("programSha256") != _sha256(Path(__file__)):
        raise ValueError("hyperspotter_program_hash_mismatch")
    if binding.get("preregistrationSha256") != _sha256(preregistration_path):
        raise ValueError("hyperspotter_preregistration_hash_mismatch")
    jobs = binding.get("jobs")
    if not isinstance(jobs, dict) or not isinstance(jobs.get(architecture), dict):
        raise ValueError("hyperspotter_binding_job_missing")
    job = jobs[architecture]
    if (
        job.get("plannedOutput")
        != output.resolve().relative_to(ROOT.resolve()).as_posix()
    ):
        raise ValueError("hyperspotter_output_binding_mismatch")
    if output.exists():
        raise FileExistsError("hyperspotter_output_exists")
    contract = binding.get("contract")
    prereg_contract = preregistration.get("contract")
    if (
        not isinstance(contract, dict)
        or contract.get("keyword") != "baxy"
        or contract.get("threshold") != 0.5
        or contract.get("device") != "cpu"
        or not isinstance(contract.get("batchSize"), int)
        or contract["batchSize"] > 32
        or not isinstance(prereg_contract, dict)
        or prereg_contract.get("keyword") != "baxy"
        or prereg_contract.get("initialThreshold") != 0.5
        or prereg_contract.get("physicalV17Read") is not False
        or prereg_contract.get("retainTranscriptText") is not False
        or prereg_contract.get("modifyRuntime") is not False
        or prereg_contract.get("retrain") is not False
        or prereg_contract.get("promotionEligible") is not False
    ):
        raise ValueError("hyperspotter_contract_mismatch")
    return job


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    paths = [
        args.binding.resolve(),
        args.preregistration.resolve(),
        args.external_root.resolve(),
        args.source_root.resolve(),
        args.output.resolve(),
    ]
    _forbid_v17(paths)
    binding = _read_object(args.binding)
    preregistration = _read_object(args.preregistration)
    job = _validate_binding(
        args.binding,
        args.preregistration,
        binding,
        preregistration,
        architecture=args.architecture,
        output=args.output,
    )
    contract = binding["contract"]
    source_archive = args.external_root / "source.zip"
    checkpoint_path = args.external_root / job["checkpointFilename"]
    if (
        _sha256(source_archive) != binding.get("sourceArchiveSha256")
        or source_tree_sha256(args.source_root) != binding.get("sourceTreeSha256")
        or _sha256(checkpoint_path) != job.get("checkpointSha256")
        or _runtime_versions() != binding.get("runtimeVersions")
    ):
        raise ValueError("hyperspotter_external_identity_mismatch")

    corpora = binding.get("corpora")
    if not isinstance(corpora, list) or not corpora:
        raise ValueError("hyperspotter_corpora_missing")
    corpus_records: list[tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]] = []
    for corpus in corpora:
        if not isinstance(corpus, dict):
            raise ValueError("hyperspotter_corpus_binding_invalid")
        corpus_root = Path(corpus["root"]).resolve()
        manifest_path = corpus_root / "manifest.v1.json"
        _forbid_v17([corpus_root, manifest_path])
        if _sha256(manifest_path) != corpus.get("manifestSha256"):
            raise ValueError("hyperspotter_corpus_manifest_hash_mismatch")
        grouped = _manifest_records(
            corpus_root,
            _read_object(manifest_path),
            expected_positive=int(corpus["positiveFiles"]),
            expected_negative=int(corpus["negativeFiles"]),
        )
        corpus_records.append((corpus, grouped))

    import torch

    if contract.get("torchThreads") is not None:
        torch.set_num_threads(int(contract["torchThreads"]))
    load_started = time.perf_counter()
    model, text_weights, cfg, checkpoint_summary = _load_candidate(
        args.source_root,
        checkpoint_path,
        args.architecture,
        contract["device"],
    )
    load_seconds = time.perf_counter() - load_started
    measured_corpora: list[dict[str, Any]] = []
    run_started = time.perf_counter()
    for corpus, grouped in corpus_records:
        positive = _score_records(
            grouped["positive"],
            model=model,
            text_weights=text_weights,
            cfg=cfg,
            device=contract["device"],
            batch_size=int(contract["batchSize"]),
            threshold=float(contract["threshold"]),
        )
        negative = _score_records(
            grouped["negative"],
            model=model,
            text_weights=text_weights,
            cfg=cfg,
            device=contract["device"],
            batch_size=int(contract["batchSize"]),
            threshold=float(contract["threshold"]),
        )
        measured_corpora.append(
            {
                "label": corpus["label"],
                "manifestSha256": corpus["manifestSha256"],
                "requiredPositiveAcceptedFiles": corpus[
                    "requiredPositiveAcceptedFiles"
                ],
                "positive": positive,
                "negative": negative,
                "positiveCoveragePreserved": (
                    positive["acceptedFiles"] >= corpus["requiredPositiveAcceptedFiles"]
                ),
                "zeroNegativeFalseActivations": negative["acceptedFiles"] == 0,
            }
        )
    elapsed = time.perf_counter() - run_started
    passed = all(
        corpus["positiveCoveragePreserved"] and corpus["zeroNegativeFalseActivations"]
        for corpus in measured_corpora
    )
    result = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "architecture": args.architecture,
        "role": "research_pilot_only",
        "inputsSha256": {
            "program": _sha256(Path(__file__)),
            "binding": _sha256(args.binding),
            "preregistration": _sha256(args.preregistration),
            "sourceArchive": _sha256(source_archive),
            "sourceTree": source_tree_sha256(args.source_root),
            "checkpoint": _sha256(checkpoint_path),
        },
        "contract": {
            "keyword": "baxy",
            "threshold": contract["threshold"],
            "device": contract["device"],
            "batchSize": contract["batchSize"],
            "torchThreads": torch.get_num_threads(),
            "physicalV17Read": False,
            "retainTranscriptText": False,
            "retainFilenames": False,
            "modifyRuntime": False,
            "retrain": False,
        },
        "runtime": {
            "python": platform.python_version(),
            "packages": _runtime_versions(),
            "modelLoadSeconds": load_seconds,
            "evaluationSeconds": elapsed,
        },
        "checkpoint": checkpoint_summary,
        "corpora": measured_corpora,
        "developmentPassed": passed,
        "candidateRuntimeModified": False,
        "promotionEligible": False,
        "blindHumanPartitionAccessed": False,
        "filenamesOrTranscriptsRetained": False,
        "effectsExecuted": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--architecture",
        choices=("conformer_hyper", "whisper_hyper"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args)
    print(
        json.dumps(
            {
                "architecture": result["architecture"],
                "passed": result["developmentPassed"],
                "corpora": [
                    {
                        "label": corpus["label"],
                        "positive": corpus["positive"]["acceptedFiles"],
                        "negative": corpus["negative"]["acceptedFiles"],
                    }
                    for corpus in result["corpora"]
                ],
                "output": str(args.output),
            },
            separators=(",", ":"),
        )
    )
    return 0 if result["developmentPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
