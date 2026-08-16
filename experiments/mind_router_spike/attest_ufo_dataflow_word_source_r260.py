"""Reject UFO Dataflow as a source when it ships a harness, not Word requests."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
UFO_ROOT = Path(r"D:\BAXYRuntime\research\UFO")
DATAFLOW_ROOT = UFO_ROOT / "dataflow"
LICENSE = UFO_ROOT / "LICENSE"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/audit/ufo_dataflow_word_source_r260.json"
EXPECTED_COMMIT = "96983c73ed09e884a5f1d7ff8936c953b234b684"
EXPECTED_ORIGIN = "https://github.com/microsoft/UFO.git"
REQUIRED_OPERATIONS = (
    "office.word.append",
    "office.word.close",
    "office.word.discard",
    "office.word.save",
    "office.word.start",
    "office.word.status",
)
SEMANTIC_PATHS = (
    ".gitignore",
    "README.md",
    "config/config.yaml.template",
    "config/config_dev.yaml",
    "data_flow_controller.py",
    "dataflow.py",
    "execution/workflow/execute_flow.py",
    "schema/execution_schema.json",
    "schema/instantiation_schema.json",
    "templates/word/description.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(UFO_ROOT), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def tree_merkle(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(UFO_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def versioned_paths(prefix: str) -> list[str]:
    paths = git("ls-tree", "-r", "--name-only", "HEAD", "dataflow").splitlines()
    return [path for path in paths if path.startswith(prefix)]


def build() -> dict[str, object]:
    semantic_files = [DATAFLOW_ROOT / relative_path for relative_path in SEMANTIC_PATHS]
    required_paths = (
        *semantic_files,
        LICENSE,
        CATALOG,
        DATAFLOW_ROOT / "templates" / "word",
    )
    if any(not path.exists() for path in required_paths):
        raise RuntimeError(
            "R260 requires the isolated UFO Dataflow source and catalogue R219"
        )
    commit = git("rev-parse", "HEAD")
    origin = git("remote", "get-url", "origin")
    if commit != EXPECTED_COMMIT or origin != EXPECTED_ORIGIN:
        raise RuntimeError(
            "R260 source identity changed; do not relabel a different UFO revision"
        )
    if "MIT License" not in LICENSE.read_text(encoding="utf-8"):
        raise RuntimeError("R260 expects UFO's MIT license")
    typed_operations = {
        str(row["name"])
        for row in json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"][
            "capabilities"
        ]
    }
    if not set(REQUIRED_OPERATIONS) <= typed_operations:
        raise RuntimeError(
            "R260 requires the six current typed Microsoft Word operations"
        )
    task_paths = versioned_paths("dataflow/tasks/")
    result_paths = versioned_paths("dataflow/results/")
    if task_paths or result_paths:
        raise RuntimeError(
            "R260 expects UFO Dataflow to ship no versioned task or result rows"
        )
    ignored_paths = (DATAFLOW_ROOT / ".gitignore").read_text(encoding="utf-8")
    execution_flow = (DATAFLOW_ROOT / "execution/workflow/execute_flow.py").read_text(
        encoding="utf-8"
    )
    task_schema = json.loads(
        (DATAFLOW_ROOT / "schema/instantiation_schema.json").read_text(encoding="utf-8")
    )
    original_fields = sorted(task_schema["properties"]["original"]["properties"])
    if "tasks/" not in ignored_paths or "results/" not in ignored_paths:
        raise RuntimeError(
            "R260 expects Dataflow task and result directories to be ignored"
        )
    if (
        "win_com_receiver.save()" not in execution_flow
        or "win_com_receiver.client.Quit()" not in execution_flow
    ):
        raise RuntimeError("R260 expects Dataflow's save-and-quit completion path")
    word_templates = sorted((DATAFLOW_ROOT / "templates" / "word").glob("*.docx"))
    return {
        "schema": "baxy.ufo-dataflow-word-source.r260.v1",
        "authority": "external_source_identity_and_semantic_admission_audit_not_model_training",
        "verdict": "rejected_preexecution_unversioned_input_and_forced_save_quit_semantics",
        "source": {
            "repository": EXPECTED_ORIGIN,
            "commit": commit,
            "license": "MIT",
            "license_sha256": sha256(LICENSE),
            "dataflow_directory": "dataflow",
            "semantic_source_files": len(semantic_files),
            "source_files_merkle_sha256": tree_merkle(semantic_files),
            "versioned_task_rows": len(task_paths),
            "versioned_result_rows": len(result_paths),
            "word_template_files": len(word_templates),
            "task_instruction_texts_retained": False,
            "task_instruction_identifiers_retained": False,
        },
        "observed_surface": {
            "word_execution_backend": "Windows WinCOMReceiverBasic",
            "task_input_contract": {
                "versioned_task_files": False,
                "ignored_task_directory": "dataflow/tasks/",
                "ignored_result_directory": "dataflow/results/",
                "caller_supplied_fields": original_fields,
                "source_native_baxy_operation_labels": False,
            },
            "cloud_generation_template_present": "https://api.openai.com/v1/chat/completions"
            in (DATAFLOW_ROOT / "config/config.yaml.template").read_text(
                encoding="utf-8"
            ),
            "completion_path_forces_save_then_quit": True,
            "completion_path_observes_saved_dirty_state": False,
            "completion_path_binds_discard_to_confirmation": False,
        },
        "admission": {
            "required_baxy_operations": list(REQUIRED_OPERATIONS),
            "required_application_and_verification": "Microsoft Word operations verified through COM, including an active document, Saved/Dirty state and confirmation-bound discard",
            "admitted_baxy_operations": [],
            "reason": "UFO Dataflow supplies a Windows/WinCOM harness but no versioned task corpus: task and result directories are ignored and callers must provide generic task strings. Generating those rows would invent a corpus. Its completion path then forces save and Quit without Saved/Dirty or confirmation evidence, so it cannot represent BAXY's discard or status semantics either.",
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
        "next_requirement": "Do not use UFO Dataflow to generate or relabel R207 examples. A successor must publish native Microsoft Word COM requests and state-sensitive verifiers for all six missing typed operations.",
        "identities": {
            "catalog_sha256": sha256(CATALOG),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite source audit: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
