"""Reject OfficeBench when its file-oriented Word surface cannot label BAXY operations."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
OFFICEBENCH_ROOT = Path(r"D:\BAXYRuntime\research\OfficeBench")
TASK_ROOT = OFFICEBENCH_ROOT / "tasks"
WORD_APP_ROOT = OFFICEBENCH_ROOT / "apps" / "word_app"
LICENSE = OFFICEBENCH_ROOT / "LICENSE"
EVALUATOR = OFFICEBENCH_ROOT / "utils" / "evaluate.py"
DOCKERFILE = OFFICEBENCH_ROOT / "docker" / "Dockerfile"
REQUIREMENTS = OFFICEBENCH_ROOT / "docker" / "requirements.txt"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/audit/officebench_word_source_r259.json"
EXPECTED_COMMIT = "b978b808667c32b52ce19a67ce1def1de9ae02b7"
EXPECTED_ORIGIN = "https://github.com/zlwang-cs/OfficeBench.git"
REQUIRED_OPERATIONS = (
    "office.word.append",
    "office.word.close",
    "office.word.discard",
    "office.word.save",
    "office.word.start",
    "office.word.status",
)
EXPECTED_WORD_ACTION_MODULES = (
    "word_convert_to_pdf.py",
    "word_create_new_file.py",
    "word_read_file.py",
    "word_write_to_file.py",
)
KEYWORD_PATTERNS = {
    "office.word.append": re.compile(
        r"(?i)(?:add|append|insert).*(?:end|document|docx|word)|"
        r"(?:end|document|docx|word).*?(?:add|append|insert)"
    ),
    "office.word.close": re.compile(r"(?i)close"),
    "office.word.discard": re.compile(
        r"(?i)discard|don't save|do not save|without saving"
    ),
    "office.word.save": re.compile(r"(?i)save"),
    "office.word.start": re.compile(
        r"(?i)(?:create|new).*(?:word|docx|document)|"
        r"(?:word|docx|document).*?(?:create|new)"
    ),
    "office.word.status": re.compile(r"(?i)saved|unsaved|dirty|status|active document"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(OFFICEBENCH_ROOT), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def tree_merkle(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(OFFICEBENCH_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def evaluation_functions(value: Any) -> set[str]:
    if isinstance(value, dict):
        names = {str(value["function"])} if "function" in value else set()
        for nested in value.values():
            names.update(evaluation_functions(nested))
        return names
    if isinstance(value, list):
        return set().union(*(evaluation_functions(item) for item in value))
    return set()


def build() -> dict[str, object]:
    required_paths = (
        LICENSE,
        TASK_ROOT,
        WORD_APP_ROOT,
        EVALUATOR,
        DOCKERFILE,
        REQUIREMENTS,
        CATALOG,
    )
    if any(not path.exists() for path in required_paths):
        raise RuntimeError(
            "R259 requires the isolated OfficeBench source and catalogue R219"
        )
    commit = git("rev-parse", "HEAD")
    origin = git("remote", "get-url", "origin")
    if commit != EXPECTED_COMMIT or origin != EXPECTED_ORIGIN:
        raise RuntimeError(
            "R259 source identity changed; do not relabel a different OfficeBench revision"
        )
    if not LICENSE.read_text(encoding="utf-8").lstrip().startswith("Apache License"):
        raise RuntimeError("R259 expects OfficeBench's Apache-2.0 license")
    task_paths = sorted(TASK_ROOT.glob("*-*/subtasks/*.json"))
    task_rows = [json.loads(path.read_text(encoding="utf-8")) for path in task_paths]
    word_modules = tuple(path.name for path in sorted(WORD_APP_ROOT.glob("word_*.py")))
    if len(task_paths) != 300 or word_modules != EXPECTED_WORD_ACTION_MODULES:
        raise RuntimeError(
            "R259 expects OfficeBench's 300 task specs and four file-oriented Word actions"
        )
    typed_operations = {
        str(row["name"])
        for row in json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"][
            "capabilities"
        ]
    }
    if not set(REQUIRED_OPERATIONS) <= typed_operations:
        raise RuntimeError(
            "R259 requires the six current typed Microsoft Word operations"
        )
    task_texts = [str(row.get("task", "")) for row in task_rows]
    doc_related = [
        text for text in task_texts if re.search(r"(?i)word|docx|document", text)
    ]
    keyword_candidates = {
        operation: sum(bool(pattern.search(text)) for text in doc_related)
        for operation, pattern in KEYWORD_PATTERNS.items()
    }
    source_files = [
        LICENSE,
        EVALUATOR,
        DOCKERFILE,
        REQUIREMENTS,
        *(WORD_APP_ROOT / name for name in word_modules),
        *task_paths,
    ]
    evaluation_names = sorted(
        set().union(*(evaluation_functions(row.get("evaluation")) for row in task_rows))
    )
    source_text = "\n".join(
        (OFFICEBENCH_ROOT / "apps" / "word_app" / name).read_text(encoding="utf-8")
        for name in word_modules
    )
    return {
        "schema": "baxy.officebench-word-source.r259.v1",
        "authority": "external_source_identity_and_semantic_admission_audit_not_model_training",
        "verdict": "rejected_preexecution_file_backend_and_state_verification_mismatch",
        "source": {
            "repository": EXPECTED_ORIGIN,
            "commit": commit,
            "license": "Apache-2.0",
            "license_sha256": sha256(LICENSE),
            "task_directory": TASK_ROOT.relative_to(OFFICEBENCH_ROOT).as_posix(),
            "task_files": len(task_paths),
            "document_related_task_files": len(doc_related),
            "semantic_source_files": len(source_files),
            "source_files_merkle_sha256": tree_merkle(source_files),
            "task_instructions_decoded": True,
            "task_instruction_texts_retained": False,
            "task_instruction_identifiers_retained": False,
        },
        "observed_surface": {
            "application_label": "OfficeBench word_app",
            "word_action_modules": list(word_modules),
            "document_backend": "python-docx Document file manipulation",
            "linux_container_installs_libreoffice": "apt-get install -y libreoffice"
            in DOCKERFILE.read_text(encoding="utf-8"),
            "microsoft_word_com_identifiers_present": "win32com" in source_text.lower(),
            "evaluation_functions": evaluation_names,
            "evaluation_observes_active_document_state": False,
            "evaluation_observes_saved_dirty_state": False,
            "evaluation_binds_discard_to_confirmation": False,
        },
        "admission": {
            "required_baxy_operations": list(REQUIRED_OPERATIONS),
            "required_application_and_verification": "Microsoft Word operations verified through COM, including an active document, Saved/Dirty state and confirmation-bound discard",
            "source_native_baxy_operation_labels": False,
            "instruction_keyword_candidates_not_labels": keyword_candidates,
            "admitted_baxy_operations": [],
            "reason": "OfficeBench has file-oriented python-docx actions and file-content evaluators, not an interactive Microsoft Word COM surface. Its task wording cannot establish BAXY's active-document, Saved/Dirty or confirmation semantics; mapping even its append-like instructions would invent labels.",
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
        "next_requirement": "Do not derive labels from OfficeBench file tasks. A successor source must natively identify Microsoft Word COM requests and verifiers for all six missing typed operations before it is used with R207.",
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
