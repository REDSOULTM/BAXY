"""Freeze disjoint MSNER Spanish entity partitions before reading row values."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA = "baxy.msner-spanish-entity-stt-preregistration.v1"
DATASET = "qmeeus/MSNER"
COMMIT = "304333fb5eba28fcc72a4ad543cb779a33dbc767"
LAST_MODIFIED_UTC = "2024-03-28T14:45:40Z"
EXPECTED_SPANISH_ROWS = 1_512
SHARDS = {
    "development": {
        "path": "data/es-00000-of-00003-a42389ca171fa00e.parquet",
        "bytes": 339_378_246,
        "lfsSha256": "155e24b0719f52ef688e14a675b9b834b55a4e414b94c02946ab711316654d81",
    },
    "validationBlind": {
        "path": "data/es-00001-of-00003-c36065ba224609ab.parquet",
        "bytes": 324_010_870,
        "lfsSha256": "9051491a6c6420bc989954308cff4fb4bff2e4dd14e19d01e31a935fbf2e5e5a",
    },
    "finalBlind": {
        "path": "data/es-00002-of-00003-c61be09c1b996f0a.parquet",
        "bytes": 324_064_119,
        "lfsSha256": "8e34fac51592bc989cb8bf67c22f41dfaf04e6d4574396f48f3ab4acbbc5fc73",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _created_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("msner_spanish_preregistration_created_at_invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("msner_spanish_preregistration_timezone_required")


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"msner_spanish_preregistration_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def preregister(arguments: argparse.Namespace) -> dict[str, Any]:
    _created_at(arguments.created_at_utc)
    repository_root = arguments.repository_root.resolve(strict=True)
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError("msner_spanish_preregistration_output_exists")
    frozen = _load(
        "baxy_msner_preregistration_program_tree",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    wake_tree = frozen._program_tree(repository_root)
    if (
        wake_tree.get("sha256")
        != "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
    ):
        raise RuntimeError("msner_spanish_preregistration_wake_tree_changed")

    resolved_shards = {
        role: {
            **commitment,
            "url": (
                f"https://huggingface.co/datasets/{DATASET}/resolve/{COMMIT}/"
                f"{commitment['path']}"
            ),
            "rowValuesRead": False,
            "audioDecoded": False,
        }
        for role, commitment in SHARDS.items()
    }
    generator = Path(__file__).resolve(strict=True)
    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "createdAtUtc": arguments.created_at_utc,
        "source": {
            "dataset": DATASET,
            "commit": COMMIT,
            "lastModifiedUtc": LAST_MODIFIED_UTC,
            "language": "es",
            "expectedRowsAcrossShards": EXPECTED_SPANISH_ROWS,
            "format": "parquet",
            "origin": "MSNER human-annotated VoxPopuli Spanish test audio",
        },
        "partition": {
            "development": "development",
            "validationBlind": "validationBlind",
            "finalBlind": "finalBlind",
            "shards": resolved_shards,
            "noShardMayChangeRole": True,
        },
        "oracle": {
            "referenceColumn": "sentence",
            "entityColumns": ["unified_entities", "raw_entities"],
            "metrics": [
                "corpus_wer",
                "named_entity_exact_recall",
                "named_entity_token_recall",
                "latency_p50_p95",
                "unbiased_word_error_rate",
            ],
            "referencesMayBeReadOnlyAfterCandidateOutput": True,
        },
        "provenance": {
            "paper": "https://aclanthology.org/2024.isa-1.2/",
            "paperLicense": "CC BY-NC 4.0",
            "datasetCardLicenseDeclared": False,
            "usage": "external_research_evaluation_only",
            "redistributeOrShipDataset": False,
        },
        "contract": {
            "remoteMetadataInspected": True,
            "rowValuesRead": False,
            "referencesOpened": False,
            "audioDecoded": False,
            "developmentMayTune": True,
            "validationBlindMayTune": False,
            "finalBlindMayTune": False,
            "candidatePromoted": False,
            "effectsExecuted": 0,
        },
        "wakeProgramTree": wake_tree,
        "generator": {
            "path": generator.relative_to(repository_root).as_posix(),
            "sha256": sha256(generator),
        },
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-at-utc", required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    artifact = preregister(arguments)
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "schema": artifact["schema"],
                "sha256": sha256(arguments.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
