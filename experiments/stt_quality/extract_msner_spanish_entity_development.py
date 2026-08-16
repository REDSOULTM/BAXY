"""Extract only the preregistered MSNER Spanish development shard."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA = "baxy.msner-spanish-entity-development-extraction.v1"
PREREG_SCHEMA = "baxy.msner-spanish-entity-stt-preregistration.v1"
SOURCE_NAME = "es-00000-of-00003-a42389ca171fa00e.parquet"
SOURCE_BYTES = 339_378_246
SOURCE_SHA256 = "155e24b0719f52ef688e14a675b9b834b55a4e414b94c02946ab711316654d81"
ROW_GROUPS = [0, 1, 2, 3, 4, 5]
ROWS_PER_GROUP = [100, 100, 100, 100, 100, 4]
EXPECTED_ROWS = 504
PYARROW_TREE = {
    "files": 760,
    "bytes": 86_422_337,
    "sha256": "653012f1ce8d89dc343776c7e852a7e3efdef874eb0300fe0a96bbd53701b976",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def semantic_tree_commitment(root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    files = 0
    total_bytes = 0
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        if (
            "__pycache__" in path.parts
            or path.suffix.casefold() == ".pyc"
            or relative.endswith(("/RECORD", "/REQUESTED", "/INSTALLER"))
        ):
            continue
        size = path.stat().st_size
        digest.update(f"{relative}\t{size}\t{sha256(path)}\n".encode("utf-8"))
        files += 1
        total_bytes += size
    return {"files": files, "bytes": total_bytes, "sha256": digest.hexdigest()}


def _created_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("msner_development_extraction_created_at_invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("msner_development_extraction_timezone_required")


def _audio_suffix(payload: bytes) -> str:
    if payload.startswith(b"RIFF") and payload[8:12] == b"WAVE":
        return ".wav"
    if payload.startswith(b"fLaC"):
        return ".flac"
    if payload.startswith(b"OggS"):
        return ".ogg"
    if payload.startswith(b"ID3") or (
        len(payload) >= 2 and payload[0] == 0xFF and payload[1] & 0xE0 == 0xE0
    ):
        return ".mp3"
    raise RuntimeError("msner_development_audio_format_unknown")


def extract(arguments: argparse.Namespace) -> dict[str, Any]:
    _created_at(arguments.created_at_utc)
    repository_root = arguments.repository_root.resolve(strict=True)
    source = arguments.source.resolve(strict=True)
    prereg_path = arguments.preregistration.resolve(strict=True)
    pyarrow_root = arguments.pyarrow_root.resolve(strict=True)
    output_root = arguments.output_root.resolve()
    artifact_path = arguments.artifact.resolve()
    if output_root.exists() or artifact_path.exists():
        raise RuntimeError("msner_development_extraction_output_exists")
    if (
        source.name != SOURCE_NAME
        or source.stat().st_size != SOURCE_BYTES
        or sha256(source) != SOURCE_SHA256
    ):
        raise RuntimeError("msner_development_source_changed")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8-sig"))
    development = prereg.get("partition", {}).get("shards", {}).get("development", {})
    if (
        prereg.get("schema") != PREREG_SCHEMA
        or development.get("path") != f"data/{SOURCE_NAME}"
        or development.get("bytes") != SOURCE_BYTES
        or development.get("lfsSha256") != SOURCE_SHA256
        or development.get("rowValuesRead") is not False
        or prereg.get("contract", {}).get("rowValuesRead") is not False
        or prereg.get("contract", {}).get("effectsExecuted") != 0
    ):
        raise RuntimeError("msner_development_preregistration_invalid")
    if semantic_tree_commitment(pyarrow_root) != PYARROW_TREE:
        raise RuntimeError("msner_development_pyarrow_changed")
    sys.path.insert(0, str(pyarrow_root))
    import pyarrow
    import pyarrow.parquet as parquet

    if (
        pyarrow.__version__ != "25.0.0"
        or not Path(pyarrow.__file__).resolve(strict=True).is_relative_to(pyarrow_root)
    ):
        raise RuntimeError("msner_development_pyarrow_runtime_invalid")
    parquet_file = parquet.ParquetFile(source)
    rows: list[dict[str, Any]] = []
    for row_group, expected in zip(ROW_GROUPS, ROWS_PER_GROUP, strict=True):
        table = parquet_file.read_row_group(row_group)
        if table.num_rows != expected:
            raise RuntimeError("msner_development_row_group_population_changed")
        rows.extend(table.to_pylist())
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError("msner_development_population_changed")

    output_root.mkdir(parents=True)
    audio_root = output_root / "audio"
    audio_root.mkdir()
    manifest_path = output_root / "manifest.jsonl"
    manifest_lines: list[str] = []
    row_commitments: list[dict[str, Any]] = []
    formats: dict[str, int] = {}
    total_audio_bytes = 0
    for index, row in enumerate(rows):
        audio = row.get("audio")
        if not isinstance(audio, dict) or not isinstance(audio.get("bytes"), bytes):
            raise RuntimeError(f"msner_development_audio_missing:{index}")
        payload = audio["bytes"]
        suffix = _audio_suffix(payload)
        case_id = f"msner-es-development-{index:04d}"
        relative_audio = Path("audio") / f"{case_id}{suffix}"
        audio_path = output_root / relative_audio
        audio_path.write_bytes(payload)
        reference = str(row.get("sentence") or "").strip()
        unified_entities = row.get("unified_entities")
        raw_entities = row.get("raw_entities")
        if not reference:
            raise RuntimeError(f"msner_development_reference_empty:{index}")
        if not isinstance(unified_entities, list) or not isinstance(raw_entities, list):
            raise RuntimeError(f"msner_development_entity_labels_missing:{index}")
        record = {
            "caseId": case_id,
            "sourceRowIndex": index,
            "audioId": row.get("audio_id"),
            "audioPath": relative_audio.as_posix(),
            "audioBytes": len(payload),
            "audioSha256": sha256(audio_path),
            "reference": reference,
            "unifiedEntities": unified_entities,
            "rawEntities": raw_entities,
        }
        manifest_lines.append(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        )
        row_commitments.append(
            {
                "caseId": case_id,
                "audioSha256": record["audioSha256"],
                "referenceSha256": hashlib.sha256(
                    reference.encode("utf-8")
                ).hexdigest(),
                "unifiedEntitiesSha256": hashlib.sha256(
                    json.dumps(unified_entities, separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
            }
        )
        format_name = suffix.removeprefix(".")
        formats[format_name] = formats.get(format_name, 0) + 1
        total_audio_bytes += len(payload)
    manifest_path.write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8", newline="\n"
    )

    generator = Path(__file__).resolve(strict=True)
    artifact: dict[str, Any] = {
        "schema": SCHEMA,
        "createdAtUtc": arguments.created_at_utc,
        "source": {
            "path": source.as_posix(),
            "bytes": SOURCE_BYTES,
            "sha256": SOURCE_SHA256,
        },
        "preregistration": {
            "path": prereg_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(prereg_path),
        },
        "extractionRuntime": {
            "pyarrowVersion": pyarrow.__version__,
            "pyarrowRoot": pyarrow_root.as_posix(),
            "semanticTree": semantic_tree_commitment(pyarrow_root),
        },
        "extraction": {
            "role": "development",
            "readRowGroups": ROW_GROUPS,
            "blindShardsRead": [],
            "rows": len(rows),
            "outputRoot": output_root.as_posix(),
            "manifestPath": manifest_path.as_posix(),
            "manifestSha256": sha256(manifest_path),
            "audioFiles": len(rows),
            "audioBytes": total_audio_bytes,
            "audioFormats": formats,
            "rowCommitments": row_commitments,
        },
        "contract": {
            "developmentRowsOpened": True,
            "validationBlindRowsOpened": False,
            "finalBlindRowsOpened": False,
            "candidatePromoted": False,
            "effectsExecuted": 0,
        },
        "generator": {
            "path": generator.relative_to(repository_root).as_posix(),
            "sha256": sha256(generator),
        },
        "effectsExecuted": 0,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--pyarrow-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--created-at-utc", required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    artifact = extract(arguments)
    print(
        json.dumps(
            {
                "artifact": str(arguments.artifact),
                "rows": artifact["extraction"]["rows"],
                "sha256": sha256(arguments.artifact),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
