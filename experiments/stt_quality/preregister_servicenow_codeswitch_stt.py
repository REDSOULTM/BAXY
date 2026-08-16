"""Reserve physically disjoint ServiceNow English-Spanish code-switch rows.

Only Parquet footer metadata is inspected.  Row groups 0 and 1 remain blind;
row group 2 is the only partition allowed for development.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path


SCHEMA = "baxy.servicenow-codeswitch-stt-preregistration.v1"
SOURCE_DATASET = "ServiceNow-AI/asr_codeswitched"
SOURCE_COMMIT = "82bf4b49499bcaa6f4cf6a67bebfab3ee2affcbb"
SOURCE_PARQUET_BYTES = 134_596_508
SOURCE_PARQUET_SHA256 = (
    "808e373099ae16c80f2bf5434fbb70afd06487ffd3a9c2f88495638dc7e035d8"
)
EXPECTED_ROWS = 259
EXPECTED_ROW_GROUP_ROWS = (100, 100, 59)
EXPECTED_SCHEMA = (
    "ID",
    "es_utterance",
    "en_utterance",
    "utterance",
    "voice",
    "audio",
    "words",
    "word_languages",
    "questions",
    "expected_answers",
    "welodata_utter_id",
)
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def program_tree(repository_root: Path) -> dict[str, object]:
    roots = (
        repository_root / "experiments/voice_latency",
        repository_root / "scripts",
        repository_root / "src/baxy_mind",
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
        digest.update(sha256(files[relative]).encode("ascii"))
        digest.update(b"\n")
    result = {
        "schema": "baxy.wake-validation-program-tree.v1",
        "roots": ["experiments/voice_latency", "scripts", "src/baxy_mind"],
        "pythonFiles": len(files),
        "sha256": digest.hexdigest(),
    }
    if result["sha256"] != EXPECTED_WAKE_TREE_SHA256:
        raise RuntimeError("wake_program_tree_changed")
    return result


def inspect_footer(path: Path) -> dict[str, object]:
    import pyarrow.parquet as parquet

    source = parquet.ParquetFile(path)
    metadata = source.metadata
    return {
        "rows": metadata.num_rows,
        "rowGroups": metadata.num_row_groups,
        "rowGroupRows": [
            metadata.row_group(index).num_rows
            for index in range(metadata.num_row_groups)
        ],
        "columns": metadata.num_columns,
        "schemaNames": source.schema_arrow.names,
        "createdBy": metadata.created_by,
    }


def validate_footer(footer: dict[str, object]) -> dict[str, object]:
    if (
        footer.get("rows") != EXPECTED_ROWS
        or footer.get("rowGroups") != len(EXPECTED_ROW_GROUP_ROWS)
        or tuple(footer.get("rowGroupRows", [])) != EXPECTED_ROW_GROUP_ROWS
        or tuple(footer.get("schemaNames", [])) != EXPECTED_SCHEMA
    ):
        raise RuntimeError("servicenow_codeswitch_parquet_footer_changed")
    return {
        "development": {
            "rowGroups": [2],
            "firstRowIndex": 200,
            "lastRowIndexInclusive": 258,
            "rows": 59,
        },
        "blind": {
            "rowGroups": [0, 1],
            "firstRowIndex": 0,
            "lastRowIndexInclusive": 199,
            "rows": 200,
        },
    }


def build_preregistration(
    *,
    repository_root: Path,
    source_parquet: Path,
    created_at_utc: str,
) -> dict[str, object]:
    repository_root = repository_root.resolve(strict=True)
    source_parquet = source_parquet.resolve(strict=True)
    try:
        parsed = datetime.fromisoformat(created_at_utc.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("servicenow_codeswitch_created_at_invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("servicenow_codeswitch_created_at_timezone_required")
    size = source_parquet.stat().st_size
    digest = sha256(source_parquet)
    if size != SOURCE_PARQUET_BYTES or digest != SOURCE_PARQUET_SHA256:
        raise RuntimeError("servicenow_codeswitch_source_changed")
    footer = inspect_footer(source_parquet)
    selection = validate_footer(footer)
    generator = Path(__file__).resolve(strict=True)
    return {
        "schema": SCHEMA,
        "createdAtUtc": created_at_utc,
        "source": {
            "dataset": SOURCE_DATASET,
            "commit": SOURCE_COMMIT,
            "config": "en_es",
            "split": "test",
            "path": source_parquet.as_posix(),
            "bytes": size,
            "sha256": digest,
            "huggingFaceLfsSha256": SOURCE_PARQUET_SHA256,
            "lastContentCommitAtUtc": "2026-06-09T05:21:55Z",
            "lastRepositoryUpdateAtUtc": "2026-07-21T21:37:30Z",
        },
        "footer": footer,
        "selection": selection,
        "partitionContract": {
            "developmentMayReadOnlyRowGroups": [2],
            "blindMayReadOnlyRowGroups": [0, 1],
            "blindRequiresNewFrozenEvaluatorAndCandidateContract": True,
            "blindRowsOpened": False,
            "developmentRowsOpened": False,
        },
        "provenance": {
            "audio": "ElevenLabs Multilingual V2 synthetic speech",
            "text": "GPT-5 generated code-switch from parallel enterprise utterances",
            "review": "AI/NLP linguist native in the matrix language",
            "synthetic": True,
            "naturalHumanSpeech": False,
            "licenseDeclaredInDatasetCard": False,
        },
        "eligibility": {
            "supplementalCodeSwitchEvaluation": True,
            "finalPhysicalCertification": False,
            "reason": "synthetic_audio_and_no_declared_dataset_license",
        },
        "preopenContract": {
            "parquetFooterInspected": True,
            "rowValuesRead": False,
            "referenceTranscriptsOpened": False,
            "audioDecoded": False,
            "candidatePromoted": False,
            "effectsExecuted": 0,
        },
        "generator": {
            "path": generator.relative_to(repository_root).as_posix(),
            "sha256": sha256(generator),
        },
        "wakeProgramTree": program_tree(repository_root),
        "effectsExecuted": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-parquet", type=Path, required=True)
    parser.add_argument("--created-at-utc", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError("servicenow_codeswitch_preregistration_output_exists")
    preregistration = build_preregistration(
        repository_root=arguments.repository_root,
        source_parquet=arguments.source_parquet,
        created_at_utc=arguments.created_at_utc,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(preregistration, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "schema": preregistration["schema"],
                "sha256": sha256(output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
