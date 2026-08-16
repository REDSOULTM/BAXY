from __future__ import annotations

import csv
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "experiments" / "stt_quality" / "reserve_common_voice_spontaneous_holdout.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_common_voice_reserve", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
reserve_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reserve_module)


def _row(
    *,
    speaker: str,
    audio_id: int,
    split: str,
    transcript: str,
    votes: int = 2,
    quality_tags: str = "",
) -> dict[str, str]:
    return {
        "client_id": speaker,
        "audio_id": str(audio_id),
        "audio_file": f"clip-{audio_id}.mp3",
        "duration_ms": "2500",
        "prompt_id": f"prompt-{audio_id}",
        "prompt": f"Question {audio_id}?",
        "transcription": transcript,
        "votes": str(votes),
        "age": "",
        "gender": "",
        "accents": "",
        "variant": "",
        "language": "test-language",
        "prompt_upvotes": "2",
        "prompt_reports": "0",
        "is_edited": "0",
        "split": split,
        "char_per_sec": "6.0",
        "quality_tags": quality_tags,
    }


def _archive(path: Path, language: str, rows: list[dict[str, str]]) -> None:
    root = f"{reserve_module.COMMON_VOICE_SNAPSHOT}-{language}"
    fieldnames = list(rows[0])
    payload = io.StringIO(newline="")
    writer = csv.DictWriter(payload, delimiter="\t", fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    tsv = payload.getvalue().encode("utf-8")
    with tarfile.open(path, "w:gz") as archive:
        tsv_info = tarfile.TarInfo(f"{root}/ss-corpus-{language}.tsv")
        tsv_info.size = len(tsv)
        archive.addfile(tsv_info, io.BytesIO(tsv))
        for row in rows:
            audio = f"fake audio {row['audio_id']}".encode()
            audio_info = tarfile.TarInfo(f"{root}/audios/{row['audio_file']}")
            audio_info.size = len(audio)
            archive.addfile(audio_info, io.BytesIO(audio))


def _audit(
    path: Path,
    archives: dict[str, Path],
    rows: dict[str, list[dict[str, str]]],
    blocked_text: str,
) -> None:
    block_hash = reserve_module.text_sha256(blocked_text)
    filler_hashes = [f"{index:064x}" for index in range(1, 10)]
    sources = {}
    for language in reserve_module.LANGUAGES:
        validated = sum(reserve_module.row_is_validated(row) for row in rows[language])
        sources[language] = {
            "datasetId": f"dataset-{language}",
            "archiveFilename": archives[language].name,
            "contentBytes": archives[language].stat().st_size,
            "clips": len(rows[language]),
            "validatedClips": validated,
            "snapshot": reserve_module.COMMON_VOICE_SNAPSHOT,
            "archiveAcquired": False,
            "modelAudioDecoded": False,
            "authenticatedDownloadRequired": True,
            "pageSampleHashesMustBeExcludedFromReservation": True,
            "pageSamples": {
                "questionsNormalizedSha256": [block_hash, *filler_hashes[:4]],
                "responsesNormalizedSha256": filler_hashes[4:9],
                "manifestSha256": f"{20 if language == 'es' else 21:064x}",
            },
        }
    value = {
        "schema": reserve_module.AUDIT_SCHEMA,
        "status": "ready_pending_authenticated_common_voice_acquisition",
        "auditContract": {
            "audioDecoded": False,
            "referenceTranscriptsOpened": False,
        },
        "decision": {"selectedSource": "Common Voice Spontaneous Speech 4.0"},
        "sources": {"commonVoiceSpontaneousSpeech4": sources},
    }
    path.write_text(json.dumps(value), encoding="utf-8")


def test_reservation_is_private_deterministic_and_speaker_disjoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(reserve_module, "ENGLISH_TARGET_CASES", 2)
    monkeypatch.setattr(reserve_module, "SPANISH_MINIMUM_CASES", 1)
    repository = tmp_path / "repository"
    repository.mkdir()
    archives = {
        "es": tmp_path / "spanish.tar.gz",
        "en": tmp_path / "english.tar.gz",
    }
    rows = {
        "es": [
            _row(
                speaker="es-a",
                audio_id=1,
                split="unassigned",
                transcript="Visible datasheet sample",
            ),
            _row(
                speaker="es-b",
                audio_id=2,
                split="unassigned",
                transcript="Respuesta espontánea privada",
            ),
            _row(
                speaker="es-c",
                audio_id=3,
                split="unassigned",
                transcript="pending",
                votes=1,
            ),
        ],
        "en": [
            _row(speaker="en-train", audio_id=10, split="train", transcript="train"),
            _row(speaker="en-a", audio_id=11, split="test", transcript="first blind"),
            _row(speaker="en-b", audio_id=12, split="test", transcript="second blind"),
            _row(speaker="en-c", audio_id=13, split="test", transcript="third blind"),
            _row(speaker="overlap", audio_id=14, split="train", transcript="train two"),
            _row(
                speaker="overlap", audio_id=15, split="test", transcript="not disjoint"
            ),
        ],
    }
    for language in reserve_module.LANGUAGES:
        _archive(archives[language], language, rows[language])
    audit_path = repository / "source-audit.json"
    _audit(audit_path, archives, rows, "Visible datasheet sample")
    contract_path = repository / "contract.json"
    contract = reserve_module.build_contract(
        repository_root=repository,
        source_audit_path=audit_path,
        created_at_utc="2026-08-11T00:00:00Z",
    )
    reserve_module.write_json_exclusive(contract_path, contract)
    private_path = tmp_path / "private" / "holdout.json"
    receipt_path = repository / "receipt.json"
    private, receipt = reserve_module.reserve(
        repository_root=repository,
        contract_path=contract_path,
        archives=archives,
        private_manifest_path=private_path,
        receipt_path=receipt_path,
        reserved_at_utc="2026-08-11T00:01:00Z",
    )

    assert len(private["cases"]) == 3
    assert {case["speakerId"] for case in private["cases"]}.isdisjoint(
        {"en-train", "overlap"}
    )
    serialized_receipt = json.dumps(receipt, ensure_ascii=False)
    for private_text in (
        "Respuesta espontánea privada",
        "first blind",
        "second blind",
        "third blind",
        "es-b",
        "en-a",
        "clip-2.mp3",
    ):
        assert private_text not in serialized_receipt
    assert receipt["sources"]["es"]["pageSampleExcludedRows"] == 1
    assert receipt["sources"]["en"]["selectedCases"] == 2
    assert receipt["privateManifest"]["sha256"] == reserve_module.sha256_file(
        private_path
    )
    assert receipt["audioDecoded"] is False
    assert receipt["modelInvoked"] is False


def test_reservation_rejects_private_manifest_inside_repository(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    with pytest.raises(
        RuntimeError, match="private_common_voice_manifest_must_be_outside_repository"
    ):
        reserve_module.reserve(
            repository_root=repository,
            contract_path=repository / "missing-contract.json",
            archives={"es": tmp_path / "es", "en": tmp_path / "en"},
            private_manifest_path=repository / "private.json",
            receipt_path=repository / "receipt.json",
            reserved_at_utc="2026-08-11T00:00:00Z",
        )


def test_archive_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        payload = b"bad"
        info = tarfile.TarInfo("../escape")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with tarfile.open(archive_path, "r:gz") as archive:
        with pytest.raises(RuntimeError, match="unsafe_common_voice_archive_member"):
            reserve_module.safe_tar_members(archive)


def test_normalization_matches_audit_contract() -> None:
    assert reserve_module.normalized_text("  ¿Árbol &amp; NIÑO?  ") == "árbol niño"
    assert reserve_module.text_sha256("Uno—dos") == reserve_module.text_sha256(
        "uno dos"
    )


def test_checked_in_preopen_contract_pins_current_unopened_tool() -> None:
    contract_path = (
        ROOT
        / "artifacts"
        / "research"
        / "common_voice_sps_v4_reservation_preopen_contract_v1.json"
    )
    contract, audit = reserve_module.validate_contract(
        repository_root=ROOT,
        contract_path=contract_path,
    )

    assert reserve_module.sha256_file(contract_path) == (
        "2b6a30a7beb29fe89c453ef6ddc8fc0afe5f344fc42404684a4b00e039a3e6bb"
    )
    assert contract["expectedArchives"]["es"]["bytes"] == 28_931_716
    assert contract["expectedArchives"]["en"]["bytes"] == 522_005_930
    assert contract["referenceTranscriptsOpened"] is False
    assert contract["audioDecoded"] is False
    assert contract["modelInvoked"] is False
    assert contract["caseIdsSelected"] is False
    assert audit["auditContract"]["audioDecoded"] is False
