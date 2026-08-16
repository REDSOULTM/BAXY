"""Prepare and acquire BAXY's sealed Mozilla Data Collective STT sources.

The acquisition plan is public and contains no credentials or private corpus
content.  Downloading requires a caller-provided ``MDC_API_KEY`` after the
person has accepted each dataset's terms in the MDC web interface.  Archives
are downloaded without opening or decoding them and interrupted transfers are
resumed only when the storage endpoint honors the requested byte range.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, BinaryIO, Callable
import urllib.error
import urllib.parse
import urllib.request


REPO = Path(__file__).resolve().parents[2]
API_BASE = "https://dev.mozilladatacollective.com/api"
PLAN_SCHEMA = "baxy.mdc-stt-acquisition-plan.v1"
RECEIPT_SCHEMA = "baxy.mdc-stt-acquisition-receipt.v1"
COMMON_VOICE_CONTRACT_SCHEMA = "baxy.stt-common-voice-sps-reservation-contract.v1"
BANGOR_SOURCE_SCHEMA = "baxy.stt-holdout-source-acquisition.v1"
BANGOR_PREREGISTRATION_SCHEMA = "baxy.stt-natural-codeswitch-preregistration.v1"
TOKEN_ENVIRONMENT = "MDC_API_KEY"
MAXIMUM_API_RESPONSE_BYTES = 1024 * 1024
COPY_BLOCK_BYTES = 4 * 1024 * 1024
DATASET_ID = re.compile(r"^[a-z0-9]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")

BANGOR_DATASET = {
    "label": "bangor_miami_es_en",
    "datasetId": "cmmfulo4r018bnz07py4q9t09",
    "archiveFilename": "bangor-miami-spanish-english-corpus-36d9f971.tar.gz",
    "bytes": 1_199_355_238,
    "datasetPage": (
        "https://mozilladatacollective.com/datasets/cmmfulo4r018bnz07py4q9t09"
    ),
}


UrlOpen = Callable[..., Any]


@dataclass(frozen=True)
class DatasetSpec:
    label: str
    dataset_id: str
    archive_filename: str
    bytes: int
    dataset_page: str

    @classmethod
    def from_object(cls, value: object) -> DatasetSpec:
        if not isinstance(value, dict):
            raise RuntimeError("mdc_dataset_spec_object_required")
        label = str(value.get("label", ""))
        dataset_id = str(value.get("datasetId", ""))
        archive_filename = str(value.get("archiveFilename", ""))
        dataset_page = str(value.get("datasetPage", ""))
        try:
            bytes_count = int(value.get("bytes", 0))
        except (TypeError, ValueError) as error:
            raise RuntimeError("mdc_dataset_bytes_invalid") from error
        if not label or not DATASET_ID.fullmatch(dataset_id):
            raise RuntimeError("mdc_dataset_identity_invalid")
        if (
            Path(archive_filename).name != archive_filename
            or not archive_filename.endswith(".tar.gz")
            or bytes_count <= 0
        ):
            raise RuntimeError(f"mdc_dataset_archive_invalid:{label}")
        page = urllib.parse.urlparse(dataset_page)
        if (
            page.scheme != "https"
            or page.hostname != "mozilladatacollective.com"
            or not page.path.endswith(f"/datasets/{dataset_id}")
        ):
            raise RuntimeError(f"mdc_dataset_page_invalid:{label}")
        return cls(label, dataset_id, archive_filename, bytes_count, dataset_page)

    def as_object(self) -> dict[str, object]:
        return {
            "label": self.label,
            "datasetId": self.dataset_id,
            "archiveFilename": self.archive_filename,
            "bytes": self.bytes,
            "datasetPage": self.dataset_page,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(COPY_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"json_object_required:{path}")
    return value


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    resolved = path.resolve()
    if resolved.exists():
        raise RuntimeError(f"output_already_exists:{resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_name(f".{resolved.name}.tmp")
    if temporary.exists():
        raise RuntimeError(f"temporary_output_already_exists:{temporary}")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as target:
            target.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, resolved)
    finally:
        if temporary.exists():
            temporary.unlink()


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _relative(path: Path) -> str:
    return path.resolve(strict=True).relative_to(REPO).as_posix()


def _binding(path: Path) -> dict[str, str]:
    resolved = path.resolve(strict=True)
    return {"path": _relative(resolved), "sha256": sha256_file(resolved)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_plan(
    *,
    common_voice_contract_path: Path,
    bangor_source_path: Path,
    bangor_preregistration_path: Path,
    output_root: Path,
    created_at_utc: str,
) -> dict[str, Any]:
    contract_path = common_voice_contract_path.resolve(strict=True)
    source_path = bangor_source_path.resolve(strict=True)
    preregistration_path = bangor_preregistration_path.resolve(strict=True)
    contract = read_object(contract_path)
    source = read_object(source_path)
    preregistration = read_object(preregistration_path)
    if (
        contract.get("schema") != COMMON_VOICE_CONTRACT_SCHEMA
        or contract.get("referenceTranscriptsOpened") is not False
        or contract.get("audioDecoded") is not False
        or contract.get("caseIdsSelected") is not False
    ):
        raise RuntimeError("common_voice_acquisition_contract_invalid")
    if (
        source.get("schema") != BANGOR_SOURCE_SCHEMA
        or source.get("evaluationStatus") != "unopened"
        or source.get("modelAudioDecoded") is not False
        or preregistration.get("schema") != BANGOR_PREREGISTRATION_SCHEMA
        or preregistration.get("evaluationStatus") != "unopened"
        or preregistration.get("modelAudioDecoded") is not False
    ):
        raise RuntimeError("bangor_acquisition_contract_invalid")

    resolved_output = output_root.resolve()
    if is_within(resolved_output, REPO):
        raise RuntimeError("mdc_archive_output_must_be_outside_repository")
    expected_archives = contract.get("expectedArchives")
    if not isinstance(expected_archives, dict) or set(expected_archives) != {
        "es",
        "en",
    }:
        raise RuntimeError("common_voice_expected_archives_invalid")
    datasets: list[dict[str, object]] = []
    for language in ("es", "en"):
        expected = expected_archives[language]
        if not isinstance(expected, dict):
            raise RuntimeError(f"common_voice_archive_invalid:{language}")
        dataset_id = str(expected.get("datasetId", ""))
        datasets.append(
            DatasetSpec.from_object(
                {
                    "label": f"common_voice_sps4_{language}",
                    "datasetId": dataset_id,
                    "archiveFilename": expected.get("archiveFilename"),
                    "bytes": expected.get("bytes"),
                    "datasetPage": (
                        "https://mozilladatacollective.com/datasets/" + dataset_id
                    ),
                }
            ).as_object()
        )
    datasets.append(DatasetSpec.from_object(BANGOR_DATASET).as_object())
    if len({item["datasetId"] for item in datasets}) != len(datasets):
        raise RuntimeError("mdc_dataset_ids_not_unique")
    if len({item["archiveFilename"] for item in datasets}) != len(datasets):
        raise RuntimeError("mdc_archive_names_not_unique")
    return {
        "schema": PLAN_SCHEMA,
        "createdAtUtc": created_at_utc,
        "role": "authenticated_download_without_archive_open",
        "api": {
            "baseUrl": API_BASE,
            "authenticationEnvironment": TOKEN_ENVIRONMENT,
            "termsAgreement": "required_out_of_band_through_mdc_web_interface",
            "downloadProtocol": "POST /datasets/:datasetId/download",
            "presignedUrlRangeResume": True,
        },
        "bindings": {
            "commonVoiceContract": _binding(contract_path),
            "bangorSourceAudit": _binding(source_path),
            "bangorPreregistration": _binding(preregistration_path),
        },
        "outputRoot": resolved_output.as_posix(),
        "datasets": datasets,
        "archiveOpened": False,
        "audioDecoded": False,
        "referenceTranscriptsOpened": False,
        "modelInvoked": False,
        "credentialsPersisted": False,
        "baxyOperationsExecuted": 0,
    }


def validate_plan(plan_path: Path) -> tuple[dict[str, Any], list[DatasetSpec], Path]:
    resolved_plan = plan_path.resolve(strict=True)
    plan = read_object(resolved_plan)
    if (
        plan.get("schema") != PLAN_SCHEMA
        or plan.get("role") != "authenticated_download_without_archive_open"
        or plan.get("api", {}).get("baseUrl") != API_BASE
        or plan.get("archiveOpened") is not False
        or plan.get("audioDecoded") is not False
        or plan.get("referenceTranscriptsOpened") is not False
        or plan.get("modelInvoked") is not False
        or plan.get("credentialsPersisted") is not False
    ):
        raise RuntimeError("mdc_acquisition_plan_invalid")
    bindings = plan.get("bindings")
    if not isinstance(bindings, dict) or len(bindings) != 3:
        raise RuntimeError("mdc_acquisition_bindings_invalid")
    for binding in bindings.values():
        if not isinstance(binding, dict):
            raise RuntimeError("mdc_acquisition_binding_invalid")
        path = (REPO / str(binding.get("path", ""))).resolve(strict=True)
        if not is_within(path, REPO) or sha256_file(path) != binding.get("sha256"):
            raise RuntimeError("mdc_acquisition_binding_hash_mismatch")
    raw_datasets = plan.get("datasets")
    if not isinstance(raw_datasets, list) or len(raw_datasets) != 3:
        raise RuntimeError("mdc_acquisition_dataset_count_invalid")
    specs = [DatasetSpec.from_object(value) for value in raw_datasets]
    if len({spec.dataset_id for spec in specs}) != len(specs):
        raise RuntimeError("mdc_dataset_ids_not_unique")
    output_root = Path(str(plan.get("outputRoot", ""))).resolve()
    if is_within(output_root, REPO):
        raise RuntimeError("mdc_archive_output_must_be_outside_repository")
    return plan, specs, output_root


def _read_api_json(
    request: urllib.request.Request,
    *,
    phase: str,
    urlopen: UrlOpen,
) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=60) as response:
            payload = response.read(MAXIMUM_API_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"mdc_api_http_{error.code}:{phase}") from error
    except (OSError, urllib.error.URLError) as error:
        raise RuntimeError(f"mdc_api_unavailable:{phase}") from error
    if len(payload) > MAXIMUM_API_RESPONSE_BYTES:
        raise RuntimeError(f"mdc_api_response_too_large:{phase}")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"mdc_api_response_invalid:{phase}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"mdc_api_response_invalid:{phase}")
    return value


def _api_request(
    path: str,
    *,
    token: str,
    method: str,
    phase: str,
    urlopen: UrlOpen,
) -> dict[str, Any]:
    request = urllib.request.Request(
        API_BASE + path,
        data=b"" if method == "POST" else None,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "BAXY-MDC-acquisition/1",
        },
    )
    return _read_api_json(request, phase=phase, urlopen=urlopen)


def _integer(value: object, *, error_code: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(error_code) from error


def validate_dataset_details(spec: DatasetSpec, details: dict[str, Any]) -> None:
    if (
        details.get("id") != spec.dataset_id
        or _integer(details.get("sizeBytes"), error_code="mdc_details_size_invalid")
        != spec.bytes
    ):
        raise RuntimeError(f"mdc_dataset_details_mismatch:{spec.label}")


def validate_download_session(
    spec: DatasetSpec, session: dict[str, Any]
) -> tuple[str, str]:
    if (
        session.get("filename") != spec.archive_filename
        or _integer(session.get("sizeBytes"), error_code="mdc_session_size_invalid")
        != spec.bytes
    ):
        raise RuntimeError(f"mdc_download_session_mismatch:{spec.label}")
    checksum = str(session.get("checksum", "")).lower()
    if checksum.startswith("sha256:"):
        checksum = checksum.removeprefix("sha256:")
    if not SHA256.fullmatch(checksum):
        raise RuntimeError(f"mdc_download_checksum_invalid:{spec.label}")
    url = str(session.get("downloadUrl", ""))
    parsed = urllib.parse.urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise RuntimeError(f"mdc_download_url_invalid:{spec.label}")
    return url, checksum


def _response_status(response: Any) -> int:
    value = getattr(response, "status", None)
    if value is None:
        value = response.getcode()
    return int(value)


def _content_range(response: Any) -> str:
    headers = getattr(response, "headers", {})
    return str(headers.get("Content-Range", ""))


def _copy_response(response: BinaryIO, target: BinaryIO) -> None:
    shutil.copyfileobj(response, target, length=COPY_BLOCK_BYTES)


def download_archive(
    spec: DatasetSpec,
    *,
    output_root: Path,
    download_url: str,
    expected_sha256: str,
    urlopen: UrlOpen,
) -> dict[str, object]:
    final = output_root / spec.archive_filename
    partial = output_root / f".{spec.archive_filename}.partial"
    if final.exists():
        if partial.exists():
            raise RuntimeError(f"mdc_final_and_partial_both_exist:{spec.label}")
        if final.stat().st_size != spec.bytes or sha256_file(final) != expected_sha256:
            raise RuntimeError(f"mdc_existing_archive_mismatch:{spec.label}")
        return {
            "label": spec.label,
            "datasetId": spec.dataset_id,
            "archiveFilename": spec.archive_filename,
            "bytes": spec.bytes,
            "sha256": expected_sha256,
            "resumed": False,
            "alreadyComplete": True,
        }
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > spec.bytes:
        raise RuntimeError(f"mdc_partial_archive_oversized:{spec.label}")
    resumed = offset > 0
    if offset < spec.bytes:
        headers = {"User-Agent": "BAXY-MDC-acquisition/1"}
        if resumed:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(download_url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=120) as response:
                status = _response_status(response)
                if resumed and (
                    status != 206
                    or not _content_range(response).startswith(f"bytes {offset}-")
                ):
                    raise RuntimeError(f"mdc_range_resume_not_honored:{spec.label}")
                if not resumed and status not in {200, 206}:
                    raise RuntimeError(f"mdc_storage_http_{status}:{spec.label}")
                mode = "ab" if resumed else "xb"
                with partial.open(mode) as target:
                    _copy_response(response, target)
                    target.flush()
                    os.fsync(target.fileno())
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"mdc_storage_http_{error.code}:{spec.label}") from error
        except (OSError, urllib.error.URLError) as error:
            raise RuntimeError(f"mdc_storage_unavailable:{spec.label}") from error
    if partial.stat().st_size != spec.bytes:
        raise RuntimeError(f"mdc_archive_size_mismatch:{spec.label}")
    actual_sha256 = sha256_file(partial)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(f"mdc_archive_hash_mismatch:{spec.label}")
    os.replace(partial, final)
    return {
        "label": spec.label,
        "datasetId": spec.dataset_id,
        "archiveFilename": spec.archive_filename,
        "bytes": spec.bytes,
        "sha256": actual_sha256,
        "resumed": resumed,
        "alreadyComplete": False,
    }


def acquire(
    *,
    plan_path: Path,
    receipt_path: Path,
    token: str,
    acquired_at_utc: str,
    urlopen: UrlOpen = urllib.request.urlopen,
) -> dict[str, Any]:
    if not token.strip():
        raise RuntimeError(f"mdc_api_key_missing:{TOKEN_ENVIRONMENT}")
    plan, specs, output_root = validate_plan(plan_path)
    if is_within(receipt_path.resolve(), output_root):
        raise RuntimeError("mdc_public_receipt_must_not_share_archive_root")
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for spec in specs:
        escaped_id = urllib.parse.quote(spec.dataset_id, safe="")
        details = _api_request(
            f"/datasets/{escaped_id}",
            token=token,
            method="GET",
            phase=f"details:{spec.label}",
            urlopen=urlopen,
        )
        validate_dataset_details(spec, details)
        session = _api_request(
            f"/datasets/{escaped_id}/download",
            token=token,
            method="POST",
            phase=f"download_session:{spec.label}",
            urlopen=urlopen,
        )
        download_url, expected_sha256 = validate_download_session(spec, session)
        results.append(
            download_archive(
                spec,
                output_root=output_root,
                download_url=download_url,
                expected_sha256=expected_sha256,
                urlopen=urlopen,
            )
        )
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "acquiredAtUtc": acquired_at_utc,
        "plan": {
            "path": _relative(plan_path.resolve(strict=True)),
            "sha256": sha256_file(plan_path.resolve(strict=True)),
        },
        "outputRoot": output_root.as_posix(),
        "datasets": results,
        "archivesOpened": False,
        "audioDecoded": False,
        "referenceTranscriptsOpened": False,
        "modelInvoked": False,
        "credentialsPersisted": False,
        "baxyOperationsExecuted": 0,
    }
    serialized = json.dumps(receipt, ensure_ascii=False)
    if token in serialized:
        raise RuntimeError("mdc_api_key_leaked_into_receipt")
    write_json_exclusive(receipt_path, receipt)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--common-voice-contract", type=Path, required=True)
    prepare.add_argument("--bangor-source", type=Path, required=True)
    prepare.add_argument("--bangor-preregistration", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--created-at-utc", default="")
    download = subparsers.add_parser("download")
    download.add_argument("--plan", type=Path, required=True)
    download.add_argument("--receipt", type=Path, required=True)
    download.add_argument("--token-environment", default=TOKEN_ENVIRONMENT)
    download.add_argument("--acquired-at-utc", default="")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.command == "prepare":
            plan = build_plan(
                common_voice_contract_path=args.common_voice_contract,
                bangor_source_path=args.bangor_source,
                bangor_preregistration_path=args.bangor_preregistration,
                output_root=args.output_root,
                created_at_utc=args.created_at_utc or _utc_now(),
            )
            write_json_exclusive(args.output, plan)
            print(json.dumps(plan, ensure_ascii=False))
            return 0
        token = os.environ.get(args.token_environment, "")
        receipt = acquire(
            plan_path=args.plan,
            receipt_path=args.receipt,
            token=token,
            acquired_at_utc=args.acquired_at_utc or _utc_now(),
        )
        print(json.dumps(receipt, ensure_ascii=False))
        return 0
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
