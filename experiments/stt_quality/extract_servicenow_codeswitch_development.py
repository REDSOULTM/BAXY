"""Extract only the preregistered ServiceNow code-switch development row group."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "baxy.servicenow-codeswitch-development-extraction.v1"
PREREG_SCHEMA = "baxy.servicenow-codeswitch-stt-preregistration.v1"
SOURCE_BYTES = 134_596_508
SOURCE_SHA256 = "808e373099ae16c80f2bf5434fbb70afd06487ffd3a9c2f88495638dc7e035d8"
DEVELOPMENT_ROW_GROUP = 2
EXPECTED_DEVELOPMENT_ROWS = 59


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audio_suffix(payload: bytes) -> str:
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
    raise RuntimeError("servicenow_codeswitch_audio_format_unknown")


def _created_at(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("servicenow_extraction_created_at_invalid") from error
    if parsed.tzinfo is None:
        raise ValueError("servicenow_extraction_created_at_timezone_required")


def extract(
    *,
    repository_root: Path,
    source_parquet: Path,
    preregistration_path: Path,
    output_root: Path,
    artifact_path: Path,
    created_at_utc: str,
) -> dict[str, object]:
    import pyarrow.parquet as parquet

    _created_at(created_at_utc)
    repository_root = repository_root.resolve(strict=True)
    source_parquet = source_parquet.resolve(strict=True)
    preregistration_path = preregistration_path.resolve(strict=True)
    output_root = output_root.resolve()
    artifact_path = artifact_path.resolve()
    if output_root.exists() or artifact_path.exists():
        raise RuntimeError("servicenow_development_extraction_output_exists")
    if (
        source_parquet.stat().st_size != SOURCE_BYTES
        or sha256(source_parquet) != SOURCE_SHA256
    ):
        raise RuntimeError("servicenow_codeswitch_source_changed")
    preregistration = json.loads(
        preregistration_path.read_text(encoding="utf-8-sig")
    )
    if (
        preregistration.get("schema") != PREREG_SCHEMA
        or preregistration.get("selection", {})
        .get("development", {})
        .get("rowGroups")
        != [DEVELOPMENT_ROW_GROUP]
        or preregistration.get("selection", {}).get("blind", {}).get("rowGroups")
        != [0, 1]
        or preregistration.get("partitionContract", {}).get("blindRowsOpened")
        is not False
    ):
        raise RuntimeError("servicenow_codeswitch_preregistration_invalid")

    parquet_file = parquet.ParquetFile(source_parquet)
    table = parquet_file.read_row_group(DEVELOPMENT_ROW_GROUP)
    if table.num_rows != EXPECTED_DEVELOPMENT_ROWS:
        raise RuntimeError("servicenow_codeswitch_development_rows_changed")
    rows: list[dict[str, Any]] = table.to_pylist()
    output_root.mkdir(parents=True)
    audio_root = output_root / "audio"
    audio_root.mkdir()
    manifest_path = output_root / "manifest.jsonl"
    manifest_lines: list[str] = []
    commitments: list[dict[str, object]] = []
    formats: dict[str, int] = {}
    total_audio_bytes = 0
    for offset, row in enumerate(rows):
        row_index = 200 + offset
        audio = row.get("audio")
        if not isinstance(audio, dict) or not isinstance(audio.get("bytes"), bytes):
            raise RuntimeError(f"servicenow_codeswitch_audio_missing:{row_index}")
        payload = audio["bytes"]
        suffix = audio_suffix(payload)
        relative_audio = Path("audio") / f"servicenow-en-es-{row_index:04d}{suffix}"
        audio_path = output_root / relative_audio
        audio_path.write_bytes(payload)
        audio_hash = sha256(audio_path)
        reference = str(row.get("utterance") or "").strip()
        if not reference:
            raise RuntimeError(f"servicenow_codeswitch_reference_empty:{row_index}")
        record = {
            "caseId": f"servicenow-en-es-{row_index:04d}",
            "sourceRowIndex": row_index,
            "sourceId": row.get("ID"),
            "voice": row.get("voice"),
            "audioPath": relative_audio.as_posix(),
            "audioBytes": len(payload),
            "audioSha256": audio_hash,
            "reference": reference,
            "words": row.get("words"),
            "wordLanguages": row.get("word_languages"),
            "questions": row.get("questions"),
            "expectedAnswers": row.get("expected_answers"),
        }
        manifest_lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        reference_hash = hashlib.sha256(reference.encode("utf-8")).hexdigest()
        commitments.append(
            {
                "caseId": record["caseId"],
                "sourceRowIndex": row_index,
                "audioSha256": audio_hash,
                "referenceSha256": reference_hash,
            }
        )
        formats[suffix.removeprefix(".")] = formats.get(suffix.removeprefix("."), 0) + 1
        total_audio_bytes += len(payload)
    manifest_path.write_text(
        "\n".join(manifest_lines) + "\n", encoding="utf-8", newline="\n"
    )
    generator = Path(__file__).resolve(strict=True)
    artifact: dict[str, object] = {
        "schema": SCHEMA,
        "createdAtUtc": created_at_utc,
        "source": {
            "path": source_parquet.as_posix(),
            "bytes": SOURCE_BYTES,
            "sha256": SOURCE_SHA256,
        },
        "preregistration": {
            "path": preregistration_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(preregistration_path),
        },
        "extraction": {
            "readRowGroups": [DEVELOPMENT_ROW_GROUP],
            "blindRowGroupsRead": [],
            "rows": len(rows),
            "firstSourceRowIndex": 200,
            "lastSourceRowIndexInclusive": 258,
            "outputRoot": output_root.as_posix(),
            "manifestPath": manifest_path.as_posix(),
            "manifestSha256": sha256(manifest_path),
            "audioFiles": len(rows),
            "audioBytes": total_audio_bytes,
            "audioFormats": formats,
            "rowCommitments": commitments,
        },
        "contract": {
            "developmentOnly": True,
            "syntheticAudio": True,
            "finalPhysicalCertificationEligible": False,
            "blindRowsOpened": False,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-parquet", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--created-at-utc", required=True)
    arguments = parser.parse_args()
    artifact = extract(
        repository_root=arguments.repository_root,
        source_parquet=arguments.source_parquet,
        preregistration_path=arguments.preregistration,
        output_root=arguments.output_root,
        artifact_path=arguments.artifact,
        created_at_utc=arguments.created_at_utc,
    )
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
