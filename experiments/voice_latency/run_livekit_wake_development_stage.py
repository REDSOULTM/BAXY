"""Run one reproducible LiveKit development stage over an assembled corpus."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time


ASSEMBLY_SCHEMA = "baxy.voxcpm2-livekit-corpus-assembly.v1"
RUN_SCHEMA = "baxy.livekit-wake-development-run.v1"
STAGES = ("augment", "train", "export", "eval")
EXPECTED_LIVEKIT_COMMIT = "1ec7f680df30ff4ca0ebae6b5983441e94b10980"
HARD_NEGATIVE_FEATURE_SCHEMA = "baxy.mdtc-hard-negative-livekit-features.v1"
PHYSICAL_FEATURE_SCHEMA = "baxy.controlled-physical-wake-livekit-features.v1"


def configure_utf8_output() -> None:
    """Prevent third-party progress output from failing on Windows code pages."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_is_not_object:{path}")
    return value


def digest_files(paths: list[Path], root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    total_bytes = 0
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        file_hash = sha256(path)
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(file_hash))
        total_bytes += path.stat().st_size
    return {
        "file_count": len(paths),
        "total_bytes": total_bytes,
        "corpus_sha256": digest.hexdigest(),
    }


def seed_process(seed: int) -> dict[str, object]:
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("development_seed_out_of_range")
    python_hash_seed = os.environ.get("PYTHONHASHSEED")
    if python_hash_seed != str(seed):
        raise ValueError(
            f"python_hash_seed_mismatch:expected={seed}:actual={python_hash_seed}"
        )
    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    return {
        "seed": seed,
        "python_hash_seed": python_hash_seed,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
    }


def livekit_identity(expected_commit: str) -> dict[str, object]:
    import livekit.wakeword

    source = Path(livekit.wakeword.__file__).resolve()
    candidates = [source.parent, *source.parents]
    repository = next((path for path in candidates if (path / ".git").exists()), None)
    if repository is None:
        raise ValueError("livekit_repository_metadata_missing")
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if commit != expected_commit:
        raise ValueError(
            f"livekit_commit_mismatch:expected={expected_commit}:actual={commit}"
        )
    return {
        "package_version": importlib.metadata.version("livekit-wakeword"),
        "source": source.as_posix(),
        "repository": repository.as_posix(),
        "commit": commit,
    }


def validate_stage_order(stage: str, completed: set[str]) -> None:
    if stage not in STAGES:
        raise ValueError(f"unsupported_development_stage:{stage}")
    if stage in completed:
        raise ValueError(f"development_stage_already_completed:{stage}")
    required = set(STAGES[: STAGES.index(stage)])
    missing = required - completed
    if missing:
        raise ValueError(
            f"development_stage_prerequisites_missing:{','.join(sorted(missing))}"
        )


def collect_stage_artifacts(stage: str, model_dir: Path) -> dict[str, object]:
    if stage == "augment":
        augmented = [
            path
            for split in (
                "positive_train",
                "positive_test",
                "negative_train",
                "negative_test",
            )
            for path in (model_dir / split).glob("clip_*_r*.wav")
        ]
        features = sorted(model_dir.glob("*_features_*.npy"))
        if not augmented or len(features) < 4:
            raise ValueError("augment_stage_artifacts_incomplete")
        return {
            "augmented_audio": digest_files(augmented, model_dir),
            "features": {
                path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
                for path in features
            },
        }
    suffixes = {
        "train": (".pt", "_metrics.json"),
        "export": (".onnx",),
        "eval": ("_eval.json", "_det.png"),
    }[stage]
    paths = [
        path
        for path in model_dir.iterdir()
        if path.is_file() and any(path.name.endswith(suffix) for suffix in suffixes)
    ]
    if len(paths) < len(suffixes):
        raise ValueError(f"{stage}_stage_artifacts_incomplete")
    return {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(paths)
    }


def assembly_data_identity(report: dict[str, object]) -> dict[str, object]:
    """Return only the fields that define the assembled training examples."""
    return {
        "counts": report.get("counts"),
        "digests": report.get("digests"),
        "split": report.get("split"),
        "positive_manifest_sha256": report.get("positive_manifest_sha256"),
        "negative_manifest_sha256": report.get("negative_manifest_sha256"),
    }


def reuse_augmentation(
    *,
    source_run_manifest_path: Path,
    target_model_dir: Path,
    target_assembly: dict[str, object],
    seed: int,
) -> dict[str, object]:
    """Hardlink a verified augmentation stage into an identical corpus split."""
    source_run_path = source_run_manifest_path.resolve(strict=True)
    source_run = read_json(source_run_path)
    if source_run.get("schema") != RUN_SCHEMA:
        raise ValueError("reuse_augment_source_schema_invalid")
    if source_run.get("blind_human_partition_accessed") is not False:
        raise ValueError("reuse_augment_source_blind_boundary_invalid")
    if int(source_run.get("seed", -1)) != seed:
        raise ValueError("reuse_augment_seed_mismatch")
    source_stages = source_run.get("stages")
    if not isinstance(source_stages, dict) or not isinstance(
        source_stages.get("augment"), dict
    ):
        raise ValueError("reuse_augment_source_stage_missing")
    source_augment = source_stages["augment"]
    source_artifacts = source_augment.get("artifacts")
    if not isinstance(source_artifacts, dict):
        raise ValueError("reuse_augment_source_artifacts_missing")

    source_assembly_value = source_run.get("assembly_manifest")
    if not isinstance(source_assembly_value, str):
        raise ValueError("reuse_augment_source_assembly_missing")
    source_assembly_path = Path(source_assembly_value).resolve(strict=True)
    source_assembly = read_json(source_assembly_path)
    if assembly_data_identity(source_assembly) != assembly_data_identity(
        target_assembly
    ):
        raise ValueError("reuse_augment_assembly_identity_mismatch")

    source_model_dir = source_run_path.parent
    source_augmented = [
        path
        for split in (
            "positive_train",
            "positive_test",
            "negative_train",
            "negative_test",
        )
        for path in (source_model_dir / split).glob("clip_*_r*.wav")
    ]
    expected_audio = source_artifacts.get("augmented_audio")
    if not isinstance(expected_audio, dict) or digest_files(
        source_augmented, source_model_dir
    ) != expected_audio:
        raise ValueError("reuse_augment_audio_digest_mismatch")

    expected_features = source_artifacts.get("features")
    if not isinstance(expected_features, dict) or len(expected_features) < 4:
        raise ValueError("reuse_augment_feature_manifest_invalid")
    feature_paths: list[Path] = []
    for name, raw_identity in sorted(expected_features.items()):
        if not isinstance(name, str) or not isinstance(raw_identity, dict):
            raise ValueError("reuse_augment_feature_identity_invalid")
        source_feature = source_model_dir / name
        if not source_feature.is_file():
            raise ValueError(f"reuse_augment_feature_missing:{name}")
        actual = {
            "sha256": sha256(source_feature),
            "bytes": source_feature.stat().st_size,
        }
        if actual != raw_identity:
            raise ValueError(f"reuse_augment_feature_digest_mismatch:{name}")
        feature_paths.append(source_feature)

    target_model_dir = target_model_dir.resolve()
    target_paths = [
        target_model_dir / path.relative_to(source_model_dir)
        for path in source_augmented
    ] + [target_model_dir / path.name for path in feature_paths]
    existing = [path for path in target_paths if path.exists()]
    if existing:
        raise FileExistsError(f"reuse_augment_target_exists:{existing[0]}")

    created: list[Path] = []
    try:
        for source_path in [*source_augmented, *feature_paths]:
            relative = (
                source_path.relative_to(source_model_dir)
                if source_path.suffix.lower() == ".wav"
                else Path(source_path.name)
            )
            target_path = target_model_dir / relative
            target_path.parent.mkdir(parents=True, exist_ok=True)
            os.link(source_path, target_path)
            created.append(target_path)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

    return {
        "source_run_manifest": source_run_path.as_posix(),
        "source_run_manifest_sha256": sha256(source_run_path),
        "source_assembly_manifest_sha256": sha256(source_assembly_path),
        "source_config_sha256": source_run.get("config_sha256"),
        "method": "verified_hardlink_reuse",
    }


def append_hard_negative_features(
    *,
    manifest_path: Path,
    target_model_dir: Path,
) -> dict[str, object]:
    """Append verified, non-blind hard negatives without mutating reused files."""
    import numpy as np

    manifest_path = manifest_path.resolve(strict=True)
    manifest = read_json(manifest_path)
    if manifest.get("schema") != HARD_NEGATIVE_FEATURE_SCHEMA:
        raise ValueError("hard_negative_feature_schema_invalid")
    if manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("hard_negative_feature_blind_boundary_invalid")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("hard_negative_feature_outputs_missing")

    target_model_dir = target_model_dir.resolve(strict=True)
    bindings = (
        ("train", "negative_features_train.npy"),
        ("development", "negative_features_test.npy"),
    )
    prepared: list[tuple[Path, Path, dict[str, object]]] = []
    temporary_paths: list[Path] = []
    try:
        for split_name, target_name in bindings:
            raw = outputs.get(split_name)
            if not isinstance(raw, dict):
                raise ValueError(
                    f"hard_negative_feature_output_invalid:{split_name}"
                )
            raw_path = raw.get("path")
            raw_sha256 = raw.get("sha256")
            raw_shape = raw.get("shape")
            if (
                not isinstance(raw_path, str)
                or not isinstance(raw_sha256, str)
                or not isinstance(raw_shape, list)
            ):
                raise ValueError(
                    f"hard_negative_feature_identity_invalid:{split_name}"
                )
            extra_path = Path(raw_path).resolve(strict=True)
            if sha256(extra_path) != raw_sha256:
                raise ValueError(
                    f"hard_negative_feature_digest_mismatch:{split_name}"
                )
            target_path = (target_model_dir / target_name).resolve(strict=True)
            base = np.load(target_path, mmap_mode="r", allow_pickle=False)
            extra = np.load(extra_path, mmap_mode="r", allow_pickle=False)
            if (
                base.dtype != np.float32
                or extra.dtype != np.float32
                or base.ndim != 3
                or extra.ndim != 3
                or base.shape[1:] != (16, 96)
                or extra.shape[1:] != (16, 96)
                or list(extra.shape) != raw_shape
            ):
                raise ValueError(
                    f"hard_negative_feature_shape_invalid:{split_name}"
                )

            temporary_path = target_path.with_name(target_path.name + ".partial")
            if temporary_path.exists():
                raise FileExistsError(
                    f"hard_negative_feature_temporary_exists:{target_name}"
                )
            temporary_paths.append(temporary_path)
            combined = np.lib.format.open_memmap(
                temporary_path,
                mode="w+",
                dtype=np.float32,
                shape=(base.shape[0] + extra.shape[0], 16, 96),
            )
            for start in range(0, base.shape[0], 1024):
                end = min(start + 1024, base.shape[0])
                combined[start:end] = base[start:end]
            offset = base.shape[0]
            for start in range(0, extra.shape[0], 1024):
                end = min(start + 1024, extra.shape[0])
                combined[offset + start : offset + end] = extra[start:end]
            combined.flush()
            del combined
            prepared.append(
                (
                    temporary_path,
                    target_path,
                    {
                        "baseRecords": int(base.shape[0]),
                        "appendedRecords": int(extra.shape[0]),
                        "combinedRecords": int(base.shape[0] + extra.shape[0]),
                        "baseSha256": sha256(target_path),
                        "appendedSha256": raw_sha256,
                        "combinedSha256": sha256(temporary_path),
                    },
                )
            )
            del base
            del extra

        for temporary_path, target_path, _ in prepared:
            os.replace(temporary_path, target_path)
    except Exception:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
        raise

    return {
        "manifest": manifest_path.as_posix(),
        "manifestSha256": sha256(manifest_path),
        "method": "verified_float32_feature_concatenation",
        "splits": {
            split_name: metadata
            for (split_name, _), (_, _, metadata) in zip(bindings, prepared)
        },
    }


def append_physical_features(
    *, manifest_path: Path, target_model_dir: Path
) -> dict[str, object]:
    """Append hash-bound physical-room features to all four class splits."""

    import numpy as np

    manifest_path = manifest_path.resolve(strict=True)
    manifest = read_json(manifest_path)
    if manifest.get("schema") != PHYSICAL_FEATURE_SCHEMA:
        raise ValueError("physical_feature_schema_invalid")
    if manifest.get("blind_human_partition_accessed") is not False:
        raise ValueError("physical_feature_blind_boundary_invalid")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("physical_feature_outputs_missing")
    bindings = (
        ("positive_train", "positive_features_train.npy"),
        ("positive_development", "positive_features_test.npy"),
        ("negative_train", "negative_features_train.npy"),
        ("negative_development", "negative_features_test.npy"),
    )
    target_model_dir = target_model_dir.resolve(strict=True)
    prepared: list[tuple[Path, Path, str, dict[str, object]]] = []
    temporary_paths: list[Path] = []
    try:
        for split_name, target_name in bindings:
            raw = outputs.get(split_name)
            if not isinstance(raw, dict):
                raise ValueError(f"physical_feature_output_invalid:{split_name}")
            raw_path = raw.get("path")
            raw_sha256 = raw.get("sha256")
            raw_shape = raw.get("shape")
            if (
                not isinstance(raw_path, str)
                or not isinstance(raw_sha256, str)
                or not isinstance(raw_shape, list)
            ):
                raise ValueError(f"physical_feature_identity_invalid:{split_name}")
            extra_path = Path(raw_path).resolve(strict=True)
            if sha256(extra_path) != raw_sha256:
                raise ValueError(f"physical_feature_digest_mismatch:{split_name}")
            target_path = (target_model_dir / target_name).resolve(strict=True)
            base = np.load(target_path, mmap_mode="r", allow_pickle=False)
            extra = np.load(extra_path, mmap_mode="r", allow_pickle=False)
            if (
                base.dtype != np.float32
                or extra.dtype != np.float32
                or base.ndim != 3
                or extra.ndim != 3
                or base.shape[1:] != (16, 96)
                or extra.shape[1:] != (16, 96)
                or list(extra.shape) != raw_shape
            ):
                raise ValueError(f"physical_feature_shape_invalid:{split_name}")
            temporary_path = target_path.with_name(target_path.name + ".partial")
            if temporary_path.exists():
                raise FileExistsError(
                    f"physical_feature_temporary_exists:{target_name}"
                )
            temporary_paths.append(temporary_path)
            combined = np.lib.format.open_memmap(
                temporary_path,
                mode="w+",
                dtype=np.float32,
                shape=(base.shape[0] + extra.shape[0], 16, 96),
            )
            combined[: base.shape[0]] = base
            combined[base.shape[0] :] = extra
            combined.flush()
            del combined
            prepared.append(
                (
                    temporary_path,
                    target_path,
                    split_name,
                    {
                        "baseRecords": int(base.shape[0]),
                        "appendedRecords": int(extra.shape[0]),
                        "combinedRecords": int(base.shape[0] + extra.shape[0]),
                        "baseSha256": sha256(target_path),
                        "appendedSha256": raw_sha256,
                        "combinedSha256": sha256(temporary_path),
                    },
                )
            )
            del base
            del extra
        for temporary_path, target_path, _, _ in prepared:
            os.replace(temporary_path, target_path)
    except Exception:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
        raise
    return {
        "manifest": manifest_path.as_posix(),
        "manifestSha256": sha256(manifest_path),
        "method": "verified_labeled_float32_feature_concatenation",
        "splits": {split_name: metadata for _, _, split_name, metadata in prepared},
    }


def run_stage(
    *,
    config_path: Path,
    assembly_path: Path,
    stage: str,
    seed: int,
    expected_livekit_commit: str,
    reuse_augment_from: Path | None = None,
    append_hard_negative_manifest: Path | None = None,
    append_physical_feature_manifest: Path | None = None,
) -> dict[str, object]:
    from livekit.wakeword.config import load_config

    config_path = config_path.resolve(strict=True)
    assembly_path = assembly_path.resolve(strict=True)
    config = load_config(config_path)
    model_dir = config.model_output_dir.resolve()
    if assembly_path.parent != model_dir:
        raise ValueError("assembly_manifest_outside_configured_model_directory")
    assembly = read_json(assembly_path)
    if assembly.get("schema") != ASSEMBLY_SCHEMA:
        raise ValueError("unsupported_assembly_manifest_schema")
    if assembly.get("blind_human_partition_accessed") is not False:
        raise ValueError("assembly_blind_boundary_invalid")

    run_manifest_path = model_dir / "development_run_manifest.v1.json"
    if run_manifest_path.exists():
        report = read_json(run_manifest_path)
        if report.get("schema") != RUN_SCHEMA:
            raise ValueError("unsupported_development_run_manifest_schema")
        if report.get("config_sha256") != sha256(config_path):
            raise ValueError("development_config_changed_between_stages")
        if report.get("assembly_manifest_sha256") != sha256(assembly_path):
            raise ValueError("development_assembly_changed_between_stages")
    else:
        report = {
            "schema": RUN_SCHEMA,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "config": config_path.as_posix(),
            "config_sha256": sha256(config_path),
            "assembly_manifest": assembly_path.as_posix(),
            "assembly_manifest_sha256": sha256(assembly_path),
            "livekit": livekit_identity(expected_livekit_commit),
            "seed": seed,
            "stages": {},
            "blind_human_partition_accessed": False,
            "candidate_frozen": False,
            "effects_executed": 0,
        }
    if int(report.get("seed", -1)) != seed:
        raise ValueError("development_seed_changed_between_stages")
    stages = report.get("stages")
    if not isinstance(stages, dict):
        raise ValueError("development_stage_records_missing")
    validate_stage_order(stage, set(str(name) for name in stages))
    if reuse_augment_from is not None and stage != "augment":
        raise ValueError("reuse_augment_only_valid_for_augment_stage")
    if append_hard_negative_manifest is not None and stage != "augment":
        raise ValueError("hard_negative_append_only_valid_for_augment_stage")
    if append_physical_feature_manifest is not None and stage != "augment":
        raise ValueError("physical_feature_append_only_valid_for_augment_stage")

    reproducibility = seed_process(seed)
    started = time.perf_counter()
    reuse: dict[str, object] | None = None
    hard_negative_extension: dict[str, object] | None = None
    physical_feature_extension: dict[str, object] | None = None
    if stage == "augment":
        if reuse_augment_from is not None:
            reuse = reuse_augmentation(
                source_run_manifest_path=reuse_augment_from,
                target_model_dir=model_dir,
                target_assembly=assembly,
                seed=seed,
            )
        else:
            from livekit.wakeword.data.augment import run_augment
            from livekit.wakeword.data.features import run_extraction

            run_augment(config)
            run_extraction(config)
        if append_hard_negative_manifest is not None:
            hard_negative_extension = append_hard_negative_features(
                manifest_path=append_hard_negative_manifest,
                target_model_dir=model_dir,
            )
        if append_physical_feature_manifest is not None:
            physical_feature_extension = append_physical_features(
                manifest_path=append_physical_feature_manifest,
                target_model_dir=model_dir,
            )
    elif stage == "train":
        from livekit.wakeword.training.trainer import run_train

        run_train(config)
    elif stage == "export":
        from livekit.wakeword.export.onnx import run_export

        run_export(config, quantize=False)
    else:
        from livekit.wakeword.eval.evaluate import run_eval

        run_eval(config, model_dir / f"{config.model_name}.onnx")
    elapsed = time.perf_counter() - started
    stage_record: dict[str, object] = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "reproducibility": reproducibility,
        "artifacts": collect_stage_artifacts(stage, model_dir),
    }
    if reuse is not None:
        stage_record["reuse"] = reuse
    if hard_negative_extension is not None:
        stage_record["hard_negative_extension"] = hard_negative_extension
    if physical_feature_extension is not None:
        stage_record["physical_feature_extension"] = physical_feature_extension
    stages[stage] = stage_record
    temporary = run_manifest_path.with_suffix(".json.partial")
    temporary.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(temporary, run_manifest_path)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--assembly-manifest", type=Path, required=True)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--seed", type=int, default=20260803)
    parser.add_argument("--expected-livekit-commit", default=EXPECTED_LIVEKIT_COMMIT)
    parser.add_argument("--reuse-augment-from", type=Path)
    parser.add_argument("--append-hard-negative-manifest", type=Path)
    parser.add_argument("--append-physical-feature-manifest", type=Path)
    return parser.parse_args()


def main() -> int:
    configure_utf8_output()
    args = parse_args()
    report = run_stage(
        config_path=args.config,
        assembly_path=args.assembly_manifest,
        stage=args.stage,
        seed=args.seed,
        expected_livekit_commit=args.expected_livekit_commit,
        reuse_augment_from=args.reuse_augment_from,
        append_hard_negative_manifest=args.append_hard_negative_manifest,
        append_physical_feature_manifest=args.append_physical_feature_manifest,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
