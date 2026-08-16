"""Attest whether Windows Agent Arena can supply missing BAXY Word examples."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
WAA_ROOT = Path(r"D:\BAXYRuntime\research\WindowsAgentArena")
TASK_ROOT = (
    WAA_ROOT
    / "src/win-arena-container/client/evaluation_examples_windows/examples_noctxt/libreoffice_writer"
)
LICENSE = WAA_ROOT / "LICENSE"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/audit/windows_agent_arena_office_source_r258.json"
EXPECTED_COMMIT = "6d39ed88c545a0d40a7a02e39b928e278df7332b"
EXPECTED_ORIGIN = "https://github.com/microsoft/WindowsAgentArena.git"
REQUIRED_OPERATIONS = (
    "office.word.append",
    "office.word.close",
    "office.word.discard",
    "office.word.save",
    "office.word.start",
    "office.word.status",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(WAA_ROOT), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def tree_merkle(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(WAA_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build() -> dict[str, object]:
    if not LICENSE.is_file() or not TASK_ROOT.is_dir() or not CATALOG.is_file():
        raise RuntimeError("R258 requires the isolated WAA source, its MIT license and catalogue R219")
    commit = git("rev-parse", "HEAD")
    origin = git("remote", "get-url", "origin")
    if commit != EXPECTED_COMMIT or origin != EXPECTED_ORIGIN:
        raise RuntimeError("R258 source identity changed; do not relabel a different WAA revision")
    task_paths = sorted(TASK_ROOT.glob("*.json"))
    task_rows = [json.loads(path.read_text(encoding="utf-8")) for path in task_paths]
    if len(task_paths) != 19 or any(row.get("snapshot") != "libreoffice_writer" for row in task_rows):
        raise RuntimeError("R258 expects exactly the 19 public LibreOffice Writer task specifications")
    typed_operations = {
        str(row["name"])
        for row in json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"]["capabilities"]
    }
    if not set(REQUIRED_OPERATIONS) <= typed_operations:
        raise RuntimeError("R258 requires the six current typed Microsoft Word operations")
    source_files = [LICENSE, *task_paths]
    return {
        "schema": "baxy.windows-agent-arena-office-source.r258.v1",
        "authority": "external_source_identity_and_semantic_admission_audit_not_model_training",
        "verdict": "rejected_preexecution_application_and_operation_semantic_mismatch",
        "source": {
            "repository": EXPECTED_ORIGIN,
            "commit": commit,
            "license": "MIT",
            "license_sha256": sha256(LICENSE),
            "task_directory": TASK_ROOT.relative_to(WAA_ROOT).as_posix(),
            "task_files": len(task_paths),
            "source_files_merkle_sha256": tree_merkle(source_files),
            "task_instructions_decoded": True,
            "task_instruction_texts_retained": False,
        },
        "admission": {
            "required_baxy_operations": list(REQUIRED_OPERATIONS),
            "required_application_and_verification": "Microsoft Word operations verified through COM, including Saved/Dirty state and confirmation-bound discard",
            "observed_task_snapshot": "libreoffice_writer",
            "observed_baxy_operation_labels": False,
            "admitted_baxy_operations": [],
            "reason": "WAA instructions are public LibreOffice Writer tasks and carry no BAXY operation label. Mapping them to Microsoft Word COM-verified operations would be an unaudited semantic invention, so this source cannot fill R207's six missing typed operations.",
        },
        "constraints": {
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "r228_opened": False,
            "clinc_opened": False,
            "public_holdout_opened": False,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "next_requirement": "Do not derive labels from generic Writer tasks. A successor source must natively identify Microsoft Word requests that can be audited against all six typed COM-verified operations before it is used with R207.",
        "identities": {
            "catalog_sha256": sha256(CATALOG),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite source audit: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
