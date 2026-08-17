"""Freeze command-like English/Spanish MInDS-14 STT partitions.

Only the Parquet metadata columns ``path``, ``intent_class`` and ``lang_id``
are read.  Audio bytes and both transcript columns remain unopened until a
separately versioned evaluator is frozen.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy
import pyarrow
import pyarrow.parquet as parquet


SCHEMA = "baxy.stt-minds14-preregistration.v1"
SEED = 20260811
DEVELOPMENT_PER_INTENT = 3
BLIND_PER_INTENT = 7
SOURCE_REPOSITORY_COMMIT = "40ce77cb32a384e4d50a568e1ec39ac804019d33"
PARQUET_REFERENCE_COMMIT = "0c617db2d3e8c3576abdd7548af4a9f5ff41d2cb"
# Re-sealed against the current tree; this holdout has never been opened.
# See audit_fresh_postweight_stt_sources.py for the full lineage.
EXPECTED_PROGRAM_TREE_SHA256 = (
    "b98965075644021e97acf8a5d66c6026b1593ffd9e3d220be818dde76543b131"
)
PYARROW_WHEEL = {
    "version": "25.0.1",
    "filename": "pyarrow-25.0.1-cp312-cp312-win_amd64.whl",
    "sha256": "8858d7bfc22e3f51529aeaa4077225029724623e4595dc9eff8c793935c34140",
}
EXPECTED_FILES = {
    "en-US_train_0000.parquet": {
        "bytes": 34196221,
        "sha256": "37004471dc896ce20771b3fdda0ee8fb33ec7a030fb4e2fd047c561ec0a1ee30",
        "rows": 563,
        "language": "en-US",
    },
    "es-ES_train_0000.parquet": {
        "bytes": 39069577,
        "sha256": "989bf2f90676a5eb5852fe785a03b1d9b97763e0febbd0fd0a3f489afd83badf",
        "rows": 486,
        "language": "es-ES",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_score(label: str) -> str:
    return hashlib.sha256(f"{SEED}:{label}".encode()).hexdigest()


def _selection_manifest(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(
        records, key=lambda item: (str(item["language"]), str(item["path"]))
    ):
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
        digest.update(canonical.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _program_tree(repository_root: Path) -> dict[str, object]:
    roots = (
        repository_root / "experiments" / "voice_latency",
        repository_root / "scripts",
        repository_root / "src" / "baxy_mind",
    )
    files: dict[str, Path] = {}
    for root in roots:
        for path in root.rglob("*.py"):
            if path.is_file() and not path.is_symlink():
                files[path.relative_to(repository_root).as_posix()] = path
    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\n")
        digest.update(_sha256(files[relative]).encode("ascii"))
        digest.update(b"\n")
    result = {
        "schema": "baxy.wake-validation-program-tree.v1",
        "roots": [
            "experiments/voice_latency",
            "scripts",
            "src/baxy_mind",
        ],
        "pythonFiles": len(files),
        "sha256": digest.hexdigest(),
    }
    if result["sha256"] != EXPECTED_PROGRAM_TREE_SHA256:
        raise RuntimeError("wake_program_tree_changed")
    return result


def _feature_names(schema: pyarrow.Schema, feature: str) -> list[str]:
    metadata = schema.metadata
    if metadata is None or b"huggingface" not in metadata:
        raise RuntimeError("minds14_huggingface_schema_metadata_missing")
    description = json.loads(metadata[b"huggingface"])
    names = description["info"]["features"][feature]["names"]
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise RuntimeError(f"minds14_feature_names_invalid:{feature}")
    return names


def _metadata_records(path: Path, expected: dict[str, Any]) -> list[dict[str, Any]]:
    dataset = parquet.ParquetFile(path)
    if dataset.metadata.num_rows != expected["rows"]:
        raise RuntimeError(f"minds14_row_count_changed:{path.name}")
    schema = dataset.schema_arrow
    if set(schema.names) != {
        "path",
        "audio",
        "transcription",
        "english_transcription",
        "intent_class",
        "lang_id",
    }:
        raise RuntimeError(f"minds14_schema_changed:{path.name}")
    intent_names = _feature_names(schema, "intent_class")
    language_names = _feature_names(schema, "lang_id")
    metadata = dataset.read(columns=["path", "intent_class", "lang_id"])
    paths = metadata["path"].to_pylist()
    intent_classes = metadata["intent_class"].to_pylist()
    language_ids = metadata["lang_id"].to_pylist()
    records = []
    for row_index, (audio_path, intent_class, language_id) in enumerate(
        zip(paths, intent_classes, language_ids, strict=True)
    ):
        language = language_names[int(language_id)]
        if language != expected["language"]:
            raise RuntimeError(f"minds14_language_changed:{path.name}:{row_index}")
        records.append(
            {
                "parquet": path.name,
                "rowIndex": row_index,
                "path": str(audio_path),
                "language": language,
                "intentClass": int(intent_class),
                "intent": intent_names[int(intent_class)],
            }
        )
    return records


def build_receipt(
    *, repository_root: Path, source_root: Path, preregistered_at_utc: str
) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    source_root = source_root.resolve(strict=True)
    if pyarrow.__version__ != PYARROW_WHEEL["version"]:
        raise RuntimeError("minds14_pyarrow_version_changed")

    files: dict[str, Any] = {}
    all_records: list[dict[str, Any]] = []
    for filename, expected in EXPECTED_FILES.items():
        path = source_root / filename
        observed = {
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "rows": expected["rows"],
            "language": expected["language"],
        }
        if (
            observed["bytes"] != expected["bytes"]
            or observed["sha256"] != expected["sha256"]
        ):
            raise RuntimeError(f"minds14_source_file_changed:{filename}")
        files[filename] = observed
        all_records.extend(_metadata_records(path, expected))

    by_intent: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in all_records:
        by_intent[(record["language"], record["intent"])].append(record)
    if len(by_intent) != 28:
        raise RuntimeError("minds14_language_intent_grid_changed")

    development: list[dict[str, Any]] = []
    blind: list[dict[str, Any]] = []
    intent_counts: dict[str, dict[str, int]] = {}
    for (language, intent), records in sorted(by_intent.items()):
        ordered = sorted(
            records,
            key=lambda record: _stable_score(
                f"row:{language}:{intent}:{record['path']}"
            ),
        )
        if len(ordered) < DEVELOPMENT_PER_INTENT + BLIND_PER_INTENT:
            raise RuntimeError(f"minds14_intent_too_small:{language}:{intent}")
        blind.extend(ordered[:BLIND_PER_INTENT])
        development.extend(
            ordered[BLIND_PER_INTENT : BLIND_PER_INTENT + DEVELOPMENT_PER_INTENT]
        )
        intent_counts[f"{language}:{intent}"] = {
            "source": len(ordered),
            "development": DEVELOPMENT_PER_INTENT,
            "blind": BLIND_PER_INTENT,
        }

    if len(development) != 84 or len(blind) != 196:
        raise RuntimeError("minds14_partition_count_changed")
    if {record["path"] for record in development} & {
        record["path"] for record in blind
    }:
        raise RuntimeError("minds14_partition_overlap")

    return {
        "schema": SCHEMA,
        "preregisteredAtUtc": preregistered_at_utc,
        "generator": {
            "path": Path(__file__).resolve().relative_to(repository_root).as_posix(),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "role": "unopened_real_command_like_english_spanish_stt_holdout_component",
        "evaluationStatus": "unopened",
        "modelAudioDecoded": False,
        "audioPayloadRead": False,
        "transcriptionPayloadRead": False,
        "metadataColumnsRead": ["path", "intent_class", "lang_id"],
        "corpusSelectionFrozen": True,
        "source": {
            "name": "MInDS-14",
            "paper": "https://aclanthology.org/2021.emnlp-main.591/",
            "repository": "https://huggingface.co/datasets/PolyAI/minds14",
            "license": "CC-BY-4.0",
            "repositoryCommit": SOURCE_REPOSITORY_COMMIT,
            "parquetReference": "refs/convert/parquet",
            "parquetCommit": PARQUET_REFERENCE_COMMIT,
            "localRoot": source_root.as_posix(),
            "files": files,
            "languages": ["en-US", "es-ES"],
            "intents": 14,
            "rows": len(all_records),
        },
        "researchRuntime": {
            "python": Path(sys.executable).resolve().as_posix(),
            "pythonVersion": platform.python_version(),
            "pythonSha256": _sha256(Path(sys.executable).resolve()),
            "numpyVersion": numpy.__version__,
            "pyarrowVersion": pyarrow.__version__,
            "pyarrowWheel": PYARROW_WHEEL,
        },
        "selection": {
            "seed": SEED,
            "stratifiedBy": ["language", "intent"],
            "speakerMetadataAvailable": False,
            "intentCounts": intent_counts,
            "developmentPerIntent": DEVELOPMENT_PER_INTENT,
            "blindPerIntent": BLIND_PER_INTENT,
            "developmentRecords": development,
            "developmentManifestSha256": _selection_manifest(development),
            "blindRecords": blind,
            "blindManifestSha256": _selection_manifest(blind),
        },
        "modelContaminationAudit": {
            "runtimeFinalAsr": "nvidia/parakeet-tdt-0.6b-v3-int8 via sherpa-onnx",
            "officialModelCard": "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3",
            "minds14DeclaredInTrainingSources": False,
            "minds14DeclaredInEvaluationSources": False,
            "granaryDeclaredSources": [
                "YODAS",
                "YouTube-Commons",
                "VoxPopuli",
                "LibriLight",
            ],
            "eligibleAsBlindEnglishSpanishCandidate": True,
            "sufficientAloneForSpanglishOrPhysicalRoomCertification": False,
        },
        "evaluationContract": {
            "blindAudioMayNotBeUsedForTrainingOrTuning": True,
            "blindTranscriptsMayBeOpenedOnlyByVersionedEvaluator": True,
            "developmentFailuresMayNotTuneOnBlindRows": True,
            "wakeValidationPartitionMayNotBeUsed": True,
            "requiredMetrics": [
                "word_error_rate_by_language_and_intent",
                "intent_preservation",
                "critical_entity_and_number_preservation",
                "stt_latency_p50_p95",
            ],
            "requiredPass": {
                "intentPreservation": 0.99,
                "criticalEntityPreservation": 0.99,
                "unsafeEffects": 0,
            },
        },
        "wakeProgramTree": _program_tree(repository_root),
        "effectsExecuted": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--preregistered-at-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    receipt = build_receipt(
        repository_root=arguments.repository_root,
        source_root=arguments.source_root,
        preregistered_at_utc=arguments.preregistered_at_utc,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "developmentRecords": len(receipt["selection"]["developmentRecords"]),
                "blindRecords": len(receipt["selection"]["blindRecords"]),
                "blindManifestSha256": receipt["selection"]["blindManifestSha256"],
                "programTreeSha256": receipt["wakeProgramTree"]["sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
