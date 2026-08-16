"""Open and extract only preregistered ServiceNow blind row groups 0 and 1."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA = "baxy.servicenow-codeswitch-blind-extraction.v1"
SOURCE_PREREG_SCHEMA = "baxy.servicenow-codeswitch-stt-preregistration.v1"
CANDIDATE_PREREG_SCHEMA = "baxy.servicenow-semantic-fusion-blind-preregistration.v1"
SOURCE_BYTES = 134_596_508
SOURCE_SHA256 = "808e373099ae16c80f2bf5434fbb70afd06487ffd3a9c2f88495638dc7e035d8"
BLIND_ROW_GROUPS = [0, 1]
EXPECTED_ROWS_PER_GROUP = [100, 100]
EXPECTED_BLIND_ROWS = 200


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
        file_hash = sha256(path)
        digest.update(f"{relative}\t{size}\t{file_hash}\n".encode("utf-8"))
        files += 1
        total_bytes += size
    return {"files": files, "bytes": total_bytes, "sha256": digest.hexdigest()}


def _created_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("servicenow_blind_extraction_created_at_invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("servicenow_blind_extraction_created_at_timezone_required")


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
    raise RuntimeError("servicenow_blind_audio_format_unknown")


def extract(arguments: argparse.Namespace) -> dict[str, object]:
    _created_at(arguments.created_at_utc)
    repository_root = arguments.repository_root.resolve(strict=True)
    source_parquet = arguments.source_parquet.resolve(strict=True)
    source_prereg_path = arguments.source_preregistration.resolve(strict=True)
    candidate_prereg_path = arguments.candidate_preregistration.resolve(strict=True)
    pyarrow_root = arguments.pyarrow_root.resolve(strict=True)
    output_root = arguments.output_root.resolve()
    artifact_path = arguments.artifact.resolve()
    if output_root.exists() or artifact_path.exists():
        raise RuntimeError("servicenow_blind_extraction_output_exists")
    if (
        source_parquet.stat().st_size != SOURCE_BYTES
        or sha256(source_parquet) != SOURCE_SHA256
    ):
        raise RuntimeError("servicenow_blind_source_changed")
    source_prereg = json.loads(source_prereg_path.read_text(encoding="utf-8-sig"))
    candidate_prereg = json.loads(
        candidate_prereg_path.read_text(encoding="utf-8-sig")
    )
    if (
        source_prereg.get("schema") != SOURCE_PREREG_SCHEMA
        or source_prereg.get("selection", {}).get("blind", {}).get("rowGroups")
        != BLIND_ROW_GROUPS
        or source_prereg.get("partitionContract", {}).get("blindRowsOpened") is not False
    ):
        raise RuntimeError("servicenow_blind_source_preregistration_invalid")
    if (
        candidate_prereg.get("schema") != CANDIDATE_PREREG_SCHEMA
        or candidate_prereg.get("partition", {}).get("rowGroups") != BLIND_ROW_GROUPS
        or candidate_prereg.get("partition", {}).get("rows") != EXPECTED_BLIND_ROWS
        or candidate_prereg.get("contract", {}).get("blindRowsOpened") is not False
        or candidate_prereg.get("contract", {}).get("candidateFrozen") is not True
        or candidate_prereg.get("contract", {}).get("effectsExecuted") != 0
    ):
        raise RuntimeError("servicenow_blind_candidate_preregistration_invalid")
    if semantic_tree_commitment(pyarrow_root) != candidate_prereg.get(
        "extractionRuntime", {}
    ).get("semanticTree"):
        raise RuntimeError("servicenow_blind_pyarrow_changed")
    sys.path.insert(0, str(pyarrow_root))
    import pyarrow
    import pyarrow.parquet as parquet

    if (
        pyarrow.__version__ != "25.0.0"
        or not Path(pyarrow.__file__).resolve(strict=True).is_relative_to(pyarrow_root)
    ):
        raise RuntimeError("servicenow_blind_pyarrow_runtime_invalid")

    parquet_file = parquet.ParquetFile(source_parquet)
    rows: list[dict[str, Any]] = []
    for row_group, expected_rows in zip(
        BLIND_ROW_GROUPS, EXPECTED_ROWS_PER_GROUP, strict=True
    ):
        table = parquet_file.read_row_group(row_group)
        if table.num_rows != expected_rows:
            raise RuntimeError("servicenow_blind_row_group_population_changed")
        rows.extend(table.to_pylist())
    if len(rows) != EXPECTED_BLIND_ROWS:
        raise RuntimeError("servicenow_blind_population_changed")

    output_root.mkdir(parents=True)
    audio_root = output_root / "audio"
    audio_root.mkdir()
    manifest_path = output_root / "manifest.jsonl"
    manifest_lines: list[str] = []
    commitments: list[dict[str, object]] = []
    formats: dict[str, int] = {}
    total_audio_bytes = 0
    for row_index, row in enumerate(rows):
        audio = row.get("audio")
        if not isinstance(audio, dict) or not isinstance(audio.get("bytes"), bytes):
            raise RuntimeError(f"servicenow_blind_audio_missing:{row_index}")
        payload = audio["bytes"]
        suffix = _audio_suffix(payload)
        case_id = f"servicenow-en-es-{row_index:04d}"
        relative_audio = Path("audio") / f"{case_id}{suffix}"
        audio_path = output_root / relative_audio
        audio_path.write_bytes(payload)
        audio_hash = sha256(audio_path)
        reference = str(row.get("utterance") or "").strip()
        words = row.get("words")
        languages = row.get("word_languages")
        if not reference:
            raise RuntimeError(f"servicenow_blind_reference_empty:{row_index}")
        if not isinstance(words, list) or not isinstance(languages, list):
            raise RuntimeError(f"servicenow_blind_word_metadata_missing:{row_index}")
        record = {
            "caseId": case_id,
            "sourceRowIndex": row_index,
            "sourceId": row.get("ID"),
            "voice": row.get("voice"),
            "audioPath": relative_audio.as_posix(),
            "audioBytes": len(payload),
            "audioSha256": audio_hash,
            "reference": reference,
            "words": words,
            "wordLanguages": languages,
        }
        manifest_lines.append(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        )
        commitments.append(
            {
                "caseId": case_id,
                "sourceRowIndex": row_index,
                "audioSha256": audio_hash,
                "referenceSha256": hashlib.sha256(
                    reference.encode("utf-8")
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
    artifact: dict[str, object] = {
        "schema": SCHEMA,
        "createdAtUtc": arguments.created_at_utc,
        "source": {
            "path": source_parquet.as_posix(),
            "bytes": SOURCE_BYTES,
            "sha256": SOURCE_SHA256,
        },
        "sourcePreregistration": {
            "path": source_prereg_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(source_prereg_path),
        },
        "candidatePreregistration": {
            "path": candidate_prereg_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(candidate_prereg_path),
        },
        "extractionRuntime": {
            "pyarrowVersion": pyarrow.__version__,
            "pyarrowRoot": pyarrow_root.as_posix(),
            "semanticTree": semantic_tree_commitment(pyarrow_root),
        },
        "extraction": {
            "readRowGroups": BLIND_ROW_GROUPS,
            "developmentRowGroupsRead": [],
            "rows": len(rows),
            "firstSourceRowIndex": 0,
            "lastSourceRowIndexInclusive": 199,
            "outputRoot": output_root.as_posix(),
            "manifestPath": manifest_path.as_posix(),
            "manifestSha256": sha256(manifest_path),
            "audioFiles": len(rows),
            "audioBytes": total_audio_bytes,
            "audioFormats": formats,
            "rowCommitments": commitments,
        },
        "contract": {
            "blindRowsOpened": True,
            "syntheticAudio": True,
            "finalPhysicalCertificationEligible": False,
            "candidateFrozen": True,
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
    parser.add_argument("--source-parquet", type=Path, required=True)
    parser.add_argument("--source-preregistration", type=Path, required=True)
    parser.add_argument("--candidate-preregistration", type=Path, required=True)
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
