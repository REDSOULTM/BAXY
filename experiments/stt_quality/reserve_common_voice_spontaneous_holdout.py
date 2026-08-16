"""Preregister and reserve a fresh Common Voice SPS holdout without decoding audio.

The public receipt never contains transcripts, prompts, speaker identifiers, or
audio filenames.  Those fields live only in a caller-selected private manifest
outside the repository.  ``preregister`` must run before the authenticated
archives are opened; ``reserve`` then verifies the frozen policy and writes both
manifests without invoking an ASR model or decoding an audio member.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import tarfile
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any


AUDIT_SCHEMA = "baxy.stt-fresh-source-audit.v1"
CONTRACT_SCHEMA = "baxy.stt-common-voice-sps-reservation-contract.v1"
PRIVATE_SCHEMA = "baxy.stt-common-voice-sps-private-holdout.v1"
RECEIPT_SCHEMA = "baxy.stt-common-voice-sps-reservation-receipt.v1"
COMMON_VOICE_SNAPSHOT = "sps-corpus-4.0-2026-06-12"
LANGUAGES = ("es", "en")
SELECTION_SEED = "baxy-common-voice-sps-v4-blind-2026-08-11"
MINIMUM_VALIDATION_VOTES = 2
ENGLISH_TARGET_CASES = 300
SPANISH_MINIMUM_CASES = 25
DISALLOWED_QUALITY_TAGS = frozenset(
    {"dataset-language-audio-mismatch", "non-allowed-script"}
)
REQUIRED_FIELDS = frozenset(
    {
        "client_id",
        "audio_id",
        "audio_file",
        "duration_ms",
        "prompt_id",
        "prompt",
        "transcription",
        "votes",
        "language",
        "split",
        "quality_tags",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(value)).casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def text_sha256(value: str) -> str:
    return hashlib.sha256(normalized_text(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"json_object_required:{path}")
    return value


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    path = path.resolve()
    if path.exists():
        raise RuntimeError(f"output_already_exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    if temporary.exists():
        raise RuntimeError(f"temporary_output_already_exists:{temporary}")
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as target:
            target.write(payload)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def relative_or_absolute(repository_root: Path, path: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return resolved.relative_to(repository_root).as_posix()
    except ValueError:
        return resolved.as_posix()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve(strict=True))
        return True
    except ValueError:
        return False


def selection_policy() -> dict[str, object]:
    return {
        "snapshot": COMMON_VOICE_SNAPSHOT,
        "languages": list(LANGUAGES),
        "validationRule": (
            "split is train/dev/test OR integer votes >= 2; transcription present"
        ),
        "minimumValidationVotes": MINIMUM_VALIDATION_VOTES,
        "pageSampleExclusion": (
            "exclude when normalized prompt OR transcription SHA-256 is blocklisted"
        ),
        "qualityExclusions": sorted(DISALLOWED_QUALITY_TAGS),
        "english": {
            "sourceSplit": "test",
            "targetCases": ENGLISH_TARGET_CASES,
            "speakerRule": "speaker has no train or dev row in the archive",
        },
        "spanish": {
            "sourceSplit": "any validated row, including unassigned",
            "minimumCases": SPANISH_MINIMUM_CASES,
            "selection": "all eligible rows",
        },
        "rank": "SHA-256(seed|locale|audio_id|audio_file), ascending",
        "seed": SELECTION_SEED,
        "audioDecoded": False,
        "modelInvoked": False,
    }


def validate_source_audit(path: Path) -> dict[str, Any]:
    audit = read_json(path.resolve(strict=True))
    if (
        audit.get("schema") != AUDIT_SCHEMA
        or audit.get("status") != "ready_pending_authenticated_common_voice_acquisition"
        or audit.get("auditContract", {}).get("audioDecoded") is not False
        or audit.get("auditContract", {}).get("referenceTranscriptsOpened") is not False
        or audit.get("decision", {}).get("selectedSource")
        != "Common Voice Spontaneous Speech 4.0"
    ):
        raise RuntimeError("common_voice_source_audit_invalid")
    sources = audit.get("sources", {}).get("commonVoiceSpontaneousSpeech4", {})
    if set(sources) != set(LANGUAGES):
        raise RuntimeError("common_voice_source_languages_invalid")
    for language in LANGUAGES:
        source = sources[language]
        if (
            source.get("snapshot") != COMMON_VOICE_SNAPSHOT
            or source.get("archiveAcquired") is not False
            or source.get("modelAudioDecoded") is not False
            or source.get("authenticatedDownloadRequired") is not True
            or source.get("pageSampleHashesMustBeExcludedFromReservation") is not True
        ):
            raise RuntimeError(f"common_voice_source_state_invalid:{language}")
    return audit


def build_contract(
    *,
    repository_root: Path,
    source_audit_path: Path,
    created_at_utc: str,
) -> dict[str, Any]:
    repository_root = repository_root.resolve(strict=True)
    source_audit_path = source_audit_path.resolve(strict=True)
    audit = validate_source_audit(source_audit_path)
    sources = audit["sources"]["commonVoiceSpontaneousSpeech4"]
    expected_archives: dict[str, object] = {}
    for language in LANGUAGES:
        source = sources[language]
        expected_archives[language] = {
            "datasetId": source["datasetId"],
            "archiveFilename": source["archiveFilename"],
            "bytes": source["contentBytes"],
            "validatedClips": source["validatedClips"],
            "pageSampleManifestSha256": source["pageSamples"]["manifestSha256"],
        }
    return {
        "schema": CONTRACT_SCHEMA,
        "createdAtUtc": created_at_utc,
        "role": "blind_holdout_reservation_before_archive_open",
        "sourceAudit": {
            "path": relative_or_absolute(repository_root, source_audit_path),
            "sha256": sha256_file(source_audit_path),
        },
        "reservationTool": {
            "path": relative_or_absolute(repository_root, Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
        },
        "expectedArchives": expected_archives,
        "selectionPolicy": selection_policy(),
        "referenceTranscriptsOpened": False,
        "audioDecoded": False,
        "modelInvoked": False,
        "caseIdsSelected": False,
        "thresholdsChanged": False,
        "effectsExecuted": 0,
    }


def validate_contract(
    *, repository_root: Path, contract_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    repository_root = repository_root.resolve(strict=True)
    contract = read_json(contract_path.resolve(strict=True))
    if (
        contract.get("schema") != CONTRACT_SCHEMA
        or contract.get("role") != "blind_holdout_reservation_before_archive_open"
        or contract.get("selectionPolicy") != selection_policy()
        or contract.get("referenceTranscriptsOpened") is not False
        or contract.get("audioDecoded") is not False
        or contract.get("modelInvoked") is not False
        or contract.get("caseIdsSelected") is not False
    ):
        raise RuntimeError("common_voice_reservation_contract_invalid")
    tool = contract.get("reservationTool", {})
    if tool.get("sha256") != sha256_file(Path(__file__)):
        raise RuntimeError("common_voice_reservation_tool_changed")
    source_entry = contract.get("sourceAudit", {})
    source_path = Path(str(source_entry.get("path", "")))
    if not source_path.is_absolute():
        source_path = repository_root / source_path
    source_path = source_path.resolve(strict=True)
    if sha256_file(source_path) != source_entry.get("sha256"):
        raise RuntimeError("common_voice_source_audit_changed")
    return contract, validate_source_audit(source_path)


def safe_tar_members(archive: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    members: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        pure = PurePosixPath(member.name)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or member.issym()
            or member.islnk()
            or member.isdev()
        ):
            raise RuntimeError(f"unsafe_common_voice_archive_member:{member.name}")
        if member.name in members:
            raise RuntimeError(f"duplicate_common_voice_archive_member:{member.name}")
        members[member.name] = member
    return members


def integer_field(row: dict[str, str], name: str) -> int:
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"common_voice_integer_field_invalid:{name}") from error


def row_is_validated(row: dict[str, str]) -> bool:
    split = row.get("split", "").strip().casefold()
    return bool(row.get("transcription", "").strip()) and (
        split in {"train", "dev", "test"}
        or integer_field(row, "votes") >= MINIMUM_VALIDATION_VOTES
    )


def row_quality_allowed(row: dict[str, str]) -> bool:
    tags = {
        value.strip().casefold()
        for value in row.get("quality_tags", "").split("|")
        if value.strip()
    }
    return not bool(tags & DISALLOWED_QUALITY_TAGS)


def page_hash_blocklist(source: dict[str, Any]) -> frozenset[str]:
    samples = source.get("pageSamples", {})
    values = [
        *samples.get("questionsNormalizedSha256", []),
        *samples.get("responsesNormalizedSha256", []),
    ]
    if len(values) != 10 or len(set(values)) != 10:
        raise RuntimeError("common_voice_page_sample_blocklist_invalid")
    return frozenset(str(value) for value in values)


def row_rank(language: str, row: dict[str, str]) -> str:
    identity = "|".join((SELECTION_SEED, language, row["audio_id"], row["audio_file"]))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def inspect_archive(
    *,
    language: str,
    archive_path: Path,
    expected: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    archive_path = archive_path.resolve(strict=True)
    if (
        archive_path.name != expected["archiveFilename"]
        or archive_path.stat().st_size != expected["bytes"]
    ):
        raise RuntimeError(f"common_voice_archive_identity_mismatch:{language}")
    archive_sha256 = sha256_file(archive_path)
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = safe_tar_members(archive)
        suffix = f"/ss-corpus-{language}.tsv"
        tsv_names = [name for name in members if name.endswith(suffix)]
        expected_root = f"{COMMON_VOICE_SNAPSHOT}-{language}"
        if len(tsv_names) != 1 or PurePosixPath(tsv_names[0]).parts[0] != expected_root:
            raise RuntimeError(f"common_voice_main_tsv_missing:{language}")
        tsv_name = tsv_names[0]
        extracted = archive.extractfile(members[tsv_name])
        if extracted is None:
            raise RuntimeError(f"common_voice_main_tsv_unreadable:{language}")
        with io.TextIOWrapper(extracted, encoding="utf-8-sig", newline="") as text:
            reader = csv.DictReader(text, delimiter="\t")
            if reader.fieldnames is None or not REQUIRED_FIELDS.issubset(
                reader.fieldnames
            ):
                raise RuntimeError(f"common_voice_main_tsv_fields_invalid:{language}")
            rows = [dict(row) for row in reader]
        if len(rows) != int(source["clips"]):
            raise RuntimeError(f"common_voice_clip_count_mismatch:{language}")
        audio_files = [row.get("audio_file", "") for row in rows]
        if any(not value for value in audio_files) or len(set(audio_files)) != len(
            rows
        ):
            raise RuntimeError(f"common_voice_audio_file_identity_invalid:{language}")
        for audio_file in audio_files:
            audio_name = f"{expected_root}/audios/{audio_file}"
            member = members.get(audio_name)
            if member is None or not member.isfile():
                raise RuntimeError(f"common_voice_audio_member_missing:{language}")

    validated = [row for row in rows if row_is_validated(row)]
    if len(validated) != int(expected["validatedClips"]):
        raise RuntimeError(f"common_voice_validated_count_mismatch:{language}")
    blocklist = page_hash_blocklist(source)
    sample_excluded = [
        row
        for row in validated
        if text_sha256(row["prompt"]) in blocklist
        or text_sha256(row["transcription"]) in blocklist
    ]
    quality_excluded = [
        row
        for row in validated
        if row not in sample_excluded and not row_quality_allowed(row)
    ]
    eligible = [
        row
        for row in validated
        if row not in sample_excluded and row not in quality_excluded
    ]
    splits_by_speaker: dict[str, set[str]] = {}
    for row in rows:
        splits_by_speaker.setdefault(row["client_id"], set()).add(
            row.get("split", "").strip().casefold()
        )
    if language == "en":
        eligible = [
            row
            for row in eligible
            if row.get("split", "").strip().casefold() == "test"
            and not (splits_by_speaker[row["client_id"]] & {"train", "dev"})
        ]
        eligible.sort(key=lambda row: row_rank(language, row))
        if len(eligible) < ENGLISH_TARGET_CASES:
            raise RuntimeError("common_voice_english_holdout_too_small")
        selected = eligible[:ENGLISH_TARGET_CASES]
    else:
        selected = sorted(eligible, key=lambda row: row_rank(language, row))
        if len(selected) < SPANISH_MINIMUM_CASES:
            raise RuntimeError("common_voice_spanish_holdout_too_small")

    private_cases: list[dict[str, object]] = []
    for row in selected:
        case_identity = f"{language}|{row['audio_id']}|{row['audio_file']}"
        case_id = hashlib.sha256(case_identity.encode("utf-8")).hexdigest()[:24]
        private_cases.append(
            {
                "caseId": case_id,
                "language": language,
                "archivePath": archive_path.as_posix(),
                "archiveSha256": archive_sha256,
                "tsvMember": tsv_name,
                "audioMember": f"{expected_root}/audios/{row['audio_file']}",
                "audioId": row["audio_id"],
                "durationMs": integer_field(row, "duration_ms"),
                "speakerId": row["client_id"],
                "promptId": row["prompt_id"],
                "promptNormalizedSha256": text_sha256(row["prompt"]),
                "referenceTranscript": row["transcription"],
                "referenceNormalizedSha256": text_sha256(row["transcription"]),
                "votes": integer_field(row, "votes"),
                "split": row.get("split", "").strip().casefold(),
                "qualityTags": sorted(
                    value.strip()
                    for value in row.get("quality_tags", "").split("|")
                    if value.strip()
                ),
            }
        )
    speakers = sorted({str(case["speakerId"]) for case in private_cases})
    public = {
        "language": language,
        "archive": {
            "datasetId": expected["datasetId"],
            "filename": archive_path.name,
            "bytes": archive_path.stat().st_size,
            "sha256": archive_sha256,
        },
        "observedRows": len(rows),
        "validatedRows": len(validated),
        "pageSampleExcludedRows": len(sample_excluded),
        "qualityExcludedRows": len(quality_excluded),
        "eligibleRowsAfterSplit": len(eligible),
        "selectedCases": len(private_cases),
        "selectedSpeakers": len(speakers),
        "speakerSetCommitmentSha256": canonical_sha256(speakers),
        "caseSetCommitmentSha256": canonical_sha256(
            sorted(str(case["caseId"]) for case in private_cases)
        ),
    }
    return {"public": public, "privateCases": private_cases}


def reserve(
    *,
    repository_root: Path,
    contract_path: Path,
    archives: dict[str, Path],
    private_manifest_path: Path,
    receipt_path: Path,
    reserved_at_utc: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    repository_root = repository_root.resolve(strict=True)
    private_manifest_path = private_manifest_path.resolve()
    receipt_path = receipt_path.resolve()
    if is_within(private_manifest_path, repository_root):
        raise RuntimeError("private_common_voice_manifest_must_be_outside_repository")
    if private_manifest_path.exists() or receipt_path.exists():
        raise RuntimeError("common_voice_reservation_output_exists")
    contract, audit = validate_contract(
        repository_root=repository_root, contract_path=contract_path
    )
    sources = audit["sources"]["commonVoiceSpontaneousSpeech4"]
    inspected: dict[str, dict[str, Any]] = {}
    all_cases: list[dict[str, object]] = []
    for language in LANGUAGES:
        result = inspect_archive(
            language=language,
            archive_path=archives[language],
            expected=contract["expectedArchives"][language],
            source=sources[language],
        )
        inspected[language] = result["public"]
        all_cases.extend(result["privateCases"])
    private_manifest: dict[str, Any] = {
        "schema": PRIVATE_SCHEMA,
        "reservedAtUtc": reserved_at_utc,
        "contractSha256": sha256_file(contract_path.resolve(strict=True)),
        "selectionPolicy": selection_policy(),
        "cases": all_cases,
        "referenceTranscriptsOpenedByReservationTool": True,
        "referenceTranscriptsExposedInPublicReceipt": False,
        "audioDecoded": False,
        "modelInvoked": False,
        "effectsExecuted": 0,
    }
    write_json_exclusive(private_manifest_path, private_manifest)
    private_sha256 = sha256_file(private_manifest_path)
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "reservedAtUtc": reserved_at_utc,
        "status": "reserved_unopened_by_model",
        "contract": {
            "path": relative_or_absolute(repository_root, contract_path),
            "sha256": sha256_file(contract_path.resolve(strict=True)),
        },
        "sources": inspected,
        "privateManifest": {
            "schema": PRIVATE_SCHEMA,
            "bytes": private_manifest_path.stat().st_size,
            "sha256": private_sha256,
            "pathPublished": False,
        },
        "selectionPolicy": selection_policy(),
        "caseIdsSelected": True,
        "speakerDisjointSelection": True,
        "pageSamplesExcluded": True,
        "referenceTranscriptsOpenedByReservationTool": True,
        "referenceTranscriptsExposedInPublicReceipt": False,
        "audioDecoded": False,
        "modelInvoked": False,
        "thresholdsChanged": False,
        "effectsExecuted": 0,
    }
    try:
        write_json_exclusive(receipt_path, receipt)
    except BaseException:
        private_manifest_path.unlink(missing_ok=True)
        raise
    return private_manifest, receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preregister = commands.add_parser("preregister")
    preregister.add_argument("--repository-root", type=Path, required=True)
    preregister.add_argument("--source-audit", type=Path, required=True)
    preregister.add_argument("--created-at-utc", required=True)
    preregister.add_argument("--output", type=Path, required=True)
    reserve_parser = commands.add_parser("reserve")
    reserve_parser.add_argument("--repository-root", type=Path, required=True)
    reserve_parser.add_argument("--contract", type=Path, required=True)
    reserve_parser.add_argument("--archive-es", type=Path, required=True)
    reserve_parser.add_argument("--archive-en", type=Path, required=True)
    reserve_parser.add_argument("--private-manifest", type=Path, required=True)
    reserve_parser.add_argument("--receipt", type=Path, required=True)
    reserve_parser.add_argument("--reserved-at-utc", required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.command == "preregister":
        result = build_contract(
            repository_root=arguments.repository_root,
            source_audit_path=arguments.source_audit,
            created_at_utc=arguments.created_at_utc,
        )
        write_json_exclusive(arguments.output, result)
        output = arguments.output
    else:
        _, result = reserve(
            repository_root=arguments.repository_root,
            contract_path=arguments.contract,
            archives={"es": arguments.archive_es, "en": arguments.archive_en},
            private_manifest_path=arguments.private_manifest,
            receipt_path=arguments.receipt,
            reserved_at_utc=arguments.reserved_at_utc,
        )
        output = arguments.receipt
    print(
        json.dumps(
            {
                "schema": result["schema"],
                "output": str(output),
                "sha256": sha256_file(output.resolve(strict=True)),
                "audioDecoded": result["audioDecoded"],
                "modelInvoked": result["modelInvoked"],
                "effectsExecuted": result["effectsExecuted"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
