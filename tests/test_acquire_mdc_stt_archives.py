from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "stt_quality" / "acquire_mdc_stt_archives.py"
SPEC = importlib.util.spec_from_file_location("baxy_mdc_acquisition", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
acquire_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = acquire_module
SPEC.loader.exec_module(acquire_module)


class Response(io.BytesIO):
    def __init__(
        self,
        payload: bytes,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(payload)
        self.status = status
        self.headers = headers or {}

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def getcode(self) -> int:
        return self.status


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _source_contracts(repository: Path) -> tuple[Path, Path, Path]:
    common_voice = repository / "common-voice.json"
    bangor_source = repository / "bangor-source.json"
    bangor_preregistration = repository / "bangor-preregistration.json"
    _write_json(
        common_voice,
        {
            "schema": acquire_module.COMMON_VOICE_CONTRACT_SCHEMA,
            "referenceTranscriptsOpened": False,
            "audioDecoded": False,
            "caseIdsSelected": False,
            "expectedArchives": {
                "es": {
                    "datasetId": "datasetes",
                    "archiveFilename": "spanish.tar.gz",
                    "bytes": 10,
                },
                "en": {
                    "datasetId": "dataseten",
                    "archiveFilename": "english.tar.gz",
                    "bytes": 20,
                },
            },
        },
    )
    _write_json(
        bangor_source,
        {
            "schema": acquire_module.BANGOR_SOURCE_SCHEMA,
            "evaluationStatus": "unopened",
            "modelAudioDecoded": False,
        },
    )
    _write_json(
        bangor_preregistration,
        {
            "schema": acquire_module.BANGOR_PREREGISTRATION_SCHEMA,
            "evaluationStatus": "unopened",
            "modelAudioDecoded": False,
        },
    )
    return common_voice, bangor_source, bangor_preregistration


def test_plan_binds_unopened_contracts_without_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(acquire_module, "REPO", repository)
    common_voice, bangor_source, bangor_preregistration = _source_contracts(repository)
    output_root = tmp_path / "private-archives"
    plan = acquire_module.build_plan(
        common_voice_contract_path=common_voice,
        bangor_source_path=bangor_source,
        bangor_preregistration_path=bangor_preregistration,
        output_root=output_root,
        created_at_utc="2026-08-11T00:00:00Z",
    )

    serialized = json.dumps(plan)
    assert plan["schema"] == acquire_module.PLAN_SCHEMA
    assert plan["outputRoot"] == output_root.as_posix()
    assert len(plan["datasets"]) == 3
    assert "MDC_API_KEY" in serialized
    assert "Bearer" not in serialized
    assert plan["archiveOpened"] is False
    assert plan["audioDecoded"] is False


def test_acquisition_resumes_exact_range_and_never_persists_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    monkeypatch.setattr(acquire_module, "REPO", repository)
    monkeypatch.setattr(
        acquire_module,
        "BANGOR_DATASET",
        {
            "label": "bangor_miami_es_en",
            "datasetId": "datasetmiami",
            "archiveFilename": "miami.tar.gz",
            "bytes": 30,
            "datasetPage": ("https://mozilladatacollective.com/datasets/datasetmiami"),
        },
    )
    common_voice, bangor_source, bangor_preregistration = _source_contracts(repository)
    output_root = tmp_path / "private-archives"
    plan = acquire_module.build_plan(
        common_voice_contract_path=common_voice,
        bangor_source_path=bangor_source,
        bangor_preregistration_path=bangor_preregistration,
        output_root=output_root,
        created_at_utc="2026-08-11T00:00:00Z",
    )
    plan_path = repository / "plan.json"
    _write_json(plan_path, plan)
    output_root.mkdir()
    first = acquire_module.DatasetSpec.from_object(plan["datasets"][0])
    payloads = {
        item["datasetId"]: bytes([index + 1]) * int(item["bytes"])
        for index, item in enumerate(plan["datasets"])
    }
    partial = output_root / f".{first.archive_filename}.partial"
    partial.write_bytes(payloads[first.dataset_id][:4])
    token = "private-mdc-token"
    requests: list[object] = []

    def urlopen(request, timeout):
        requests.append(request)
        url = request.full_url
        if url.startswith(acquire_module.API_BASE):
            dataset_id = url.split("/datasets/", 1)[1].split("/", 1)[0]
            assert request.get_header("Authorization") == f"Bearer {token}"
            spec = next(
                item for item in plan["datasets"] if item["datasetId"] == dataset_id
            )
            if request.get_method() == "GET":
                value = {"id": dataset_id, "sizeBytes": str(spec["bytes"])}
            else:
                digest = hashlib.sha256(payloads[dataset_id]).hexdigest()
                value = {
                    "filename": spec["archiveFilename"],
                    "sizeBytes": str(spec["bytes"]),
                    "checksum": f"sha256:{digest}",
                    "downloadUrl": f"https://storage.invalid/{dataset_id}",
                }
            return Response(json.dumps(value).encode())
        dataset_id = url.rsplit("/", 1)[1]
        assert request.get_header("Authorization") is None
        range_header = request.get_header("Range")
        start = (
            int(range_header.removeprefix("bytes=").removesuffix("-"))
            if range_header
            else 0
        )
        body = payloads[dataset_id][start:]
        headers = (
            {
                "Content-Range": f"bytes {start}-{len(payloads[dataset_id]) - 1}/{len(payloads[dataset_id])}"
            }
            if start
            else {}
        )
        return Response(body, status=206 if start else 200, headers=headers)

    receipt_path = repository / "receipt.json"
    receipt = acquire_module.acquire(
        plan_path=plan_path,
        receipt_path=receipt_path,
        token=token,
        acquired_at_utc="2026-08-11T00:01:00Z",
        urlopen=urlopen,
    )

    assert len(receipt["datasets"]) == 3
    assert receipt["datasets"][0]["resumed"] is True
    assert all(
        (output_root / item["archiveFilename"]).read_bytes()
        == payloads[item["datasetId"]]
        for item in plan["datasets"]
    )
    assert token not in receipt_path.read_text(encoding="utf-8")
    assert receipt["archivesOpened"] is False
    assert receipt["audioDecoded"] is False
    assert len(requests) == 9


def test_resume_refuses_a_storage_response_that_ignores_range(
    tmp_path: Path,
) -> None:
    spec = acquire_module.DatasetSpec.from_object(
        {
            "label": "test",
            "datasetId": "datasetone",
            "archiveFilename": "archive.tar.gz",
            "bytes": 10,
            "datasetPage": ("https://mozilladatacollective.com/datasets/datasetone"),
        }
    )
    output_root = tmp_path / "archives"
    output_root.mkdir()
    partial = output_root / ".archive.tar.gz.partial"
    partial.write_bytes(b"1234")

    def ignores_range(_request, *, timeout):
        assert timeout == 120
        return Response(b"1234567890", status=200)

    with pytest.raises(RuntimeError, match="mdc_range_resume_not_honored:test"):
        acquire_module.download_archive(
            spec,
            output_root=output_root,
            download_url="https://storage.invalid/archive",
            expected_sha256=hashlib.sha256(b"1234567890").hexdigest(),
            urlopen=ignores_range,
        )

    assert partial.read_bytes() == b"1234"
    assert not (output_root / "archive.tar.gz").exists()


def test_download_session_rejects_untrusted_url_and_wrong_identity() -> None:
    spec = acquire_module.DatasetSpec.from_object(
        {
            "label": "test",
            "datasetId": "datasetone",
            "archiveFilename": "archive.tar.gz",
            "bytes": 10,
            "datasetPage": ("https://mozilladatacollective.com/datasets/datasetone"),
        }
    )
    with pytest.raises(RuntimeError, match="mdc_download_url_invalid:test"):
        acquire_module.validate_download_session(
            spec,
            {
                "filename": "archive.tar.gz",
                "sizeBytes": 10,
                "checksum": "sha256:" + "a" * 64,
                "downloadUrl": "http://storage.invalid/archive",
            },
        )
    with pytest.raises(RuntimeError, match="mdc_dataset_details_mismatch:test"):
        acquire_module.validate_dataset_details(
            spec,
            {"id": "another", "sizeBytes": 10},
        )


def test_missing_key_fails_before_plan_or_network(tmp_path: Path) -> None:
    called = False

    def urlopen(_request, _timeout):
        nonlocal called
        called = True
        raise AssertionError("network must not be called")

    with pytest.raises(RuntimeError, match="mdc_api_key_missing:MDC_API_KEY"):
        acquire_module.acquire(
            plan_path=tmp_path / "missing.json",
            receipt_path=tmp_path / "receipt.json",
            token="",
            acquired_at_utc="2026-08-11T00:00:00Z",
            urlopen=urlopen,
        )
    assert called is False


def test_path_check_accepts_an_output_root_not_created_yet(tmp_path: Path) -> None:
    output_root = tmp_path / "not-created" / "archives"
    public_receipt = tmp_path / "repository" / "receipt.json"

    assert not output_root.exists()
    assert acquire_module.is_within(public_receipt, output_root) is False
