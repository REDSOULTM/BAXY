"""Reject WindowsWorld for BAXY's multilingual Word/COM lifecycle evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
WINDOWSWORLD_ROOT = Path(r"D:\BAXYRuntime\research\WindowsWorld")
CATALOGUE = REPO / "artifacts" / "development" / "current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts" / "audit" / "windowsworld_word_source_r268.json"
EXPECTED_COMMIT = "fbccd464f94fec9e284e139f97bf96d0b192f580"
EXPECTED_ORIGIN = "https://github.com/HITsz-TMG/WindowsWorld.git"
REQUIRED_OPERATIONS = (
    "office.word.append",
    "office.word.close",
    "office.word.discard",
    "office.word.save",
    "office.word.start",
    "office.word.status",
)
SEMANTIC_RELATIVE_PATHS = (
    "LICENSE",
    "README.md",
    "benchmark.json",
    "hf_run.py",
    "desktop_env/desktop_env.py",
    "desktop_env/server/README.md",
)
NATIVE_WORD_COM_TOKENS = (
    "word.application",
    "win32com",
    "comtypes",
    "pywin32",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(WINDOWSWORLD_ROOT), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def tree_merkle(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(WINDOWSWORLD_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _catalogue_operations() -> set[str]:
    payload = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    capabilities = payload.get("catalogue", {}).get("capabilities")
    if not isinstance(capabilities, list):
        raise RuntimeError("R268 requires catalogue R219")
    return {
        row["name"]
        for row in capabilities
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }


def _word_lifecycle_counts(tasks: list[dict[str, Any]]) -> dict[str, int]:
    texts = [str(task["instruction"]) for task in tasks]
    patterns = {
        "office.word.append": re.compile(r"\bappend\b", re.IGNORECASE),
        "office.word.close": re.compile(r"\bclose\b", re.IGNORECASE),
        "office.word.discard": re.compile(
            r"\b(?:discard|don't save|do not save|without saving)\b",
            re.IGNORECASE,
        ),
        "office.word.save": re.compile(r"\bsave\b", re.IGNORECASE),
        "office.word.start": re.compile(
            r"\b(?:open|create|new)\b.{0,96}\bword\b|"
            r"\bword\b.{0,96}\b(?:open|create|new)\b",
            re.IGNORECASE,
        ),
        "office.word.status": re.compile(
            r"\b(?:saved|unsaved|dirty|active document)\b",
            re.IGNORECASE,
        ),
    }
    return {
        operation: sum(pattern.search(text) is not None for text in texts)
        for operation, pattern in patterns.items()
    }


def build() -> dict[str, object]:
    semantic_paths = [WINDOWSWORLD_ROOT / relative for relative in SEMANTIC_RELATIVE_PATHS]
    if any(not path.is_file() for path in (*semantic_paths, CATALOGUE)):
        raise RuntimeError("R268 requires the isolated WindowsWorld source and catalogue R219")
    commit = git("rev-parse", "HEAD")
    origin = git("remote", "get-url", "origin")
    if commit != EXPECTED_COMMIT or origin != EXPECTED_ORIGIN:
        raise RuntimeError("R268 source identity changed; do not relabel another revision")
    license_text = (WINDOWSWORLD_ROOT / "LICENSE").read_text(encoding="utf-8")
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        raise RuntimeError("R268 expects WindowsWorld's Apache-2.0 license")
    if not set(REQUIRED_OPERATIONS) <= _catalogue_operations():
        raise RuntimeError("R268 requires the six current typed Microsoft Word operations")

    raw_tasks = json.loads((WINDOWSWORLD_ROOT / "benchmark.json").read_text(encoding="utf-8"))
    if not isinstance(raw_tasks, list) or len(raw_tasks) != 181:
        raise RuntimeError("R268 expects the 181 published WindowsWorld tasks")
    tasks = [task for task in raw_tasks if isinstance(task, dict)]
    if len(tasks) != len(raw_tasks) or any(
        not isinstance(task.get("task_id"), str)
        or not isinstance(task.get("instruction"), str)
        or not isinstance(task.get("instruction_cn"), str)
        or not isinstance(task.get("involved_apps"), list)
        or not isinstance(task.get("evaluation_metrics"), dict)
        for task in tasks
    ):
        raise RuntimeError("R268 expects the published bilingual task shape")
    word_tasks = [task for task in tasks if "Word" in task["involved_apps"]]
    if len(word_tasks) != 40:
        raise RuntimeError("R268 expects 40 published Word-labelled task instructions")
    lifecycle_counts = _word_lifecycle_counts(word_tasks)
    if any(
        lifecycle_counts[operation] != 0
        for operation in (
            "office.word.close",
            "office.word.discard",
            "office.word.status",
        )
    ):
        raise RuntimeError("R268 expects no direct close, discard, or Word-state request")

    source_text = "\n".join(path.read_text(encoding="utf-8") for path in semantic_paths)
    if any(token in source_text.casefold() for token in NATIVE_WORD_COM_TOKENS):
        raise RuntimeError("R268 expects no native Microsoft Word COM implementation")
    word_process_checkpoint_mentions = "winword.exe" in source_text.casefold()
    libreoffice_configuration = (
        "Open LibreOffice Writer/Calc/Impress"
        in (WINDOWSWORLD_ROOT / "desktop_env/server/README.md").read_text(
            encoding="utf-8"
        )
    )
    no_op_evaluation = (
        '"func": "infeasible"' in (WINDOWSWORLD_ROOT / "desktop_env/desktop_env.py").read_text(
            encoding="utf-8"
        )
    )
    screenshot_judgement = (
        "screenshots（时间顺序）" in (WINDOWSWORLD_ROOT / "hf_run.py").read_text(
            encoding="utf-8"
        )
    )
    if not (libreoffice_configuration and no_op_evaluation and screenshot_judgement):
        raise RuntimeError("R268 expects the published non-COM screenshot judgement path")

    return {
        "schema": "baxy.windowsworld-word-source.r268.v1",
        "authority": "external_source_identity_and_semantic_admission_audit_not_model_training",
        "verdict": "rejected_preexecution_non_com_multistep_and_language_coverage_mismatch",
        "source": {
            "repository": EXPECTED_ORIGIN,
            "commit": commit,
            "license": "Apache-2.0",
            "license_sha256": sha256(WINDOWSWORLD_ROOT / "LICENSE"),
            "semantic_source_files": len(semantic_paths),
            "source_files_merkle_sha256": tree_merkle(semantic_paths),
            "published_task_rows": len(tasks),
            "published_word_task_rows": len(word_tasks),
            "published_instruction_languages": ["en", "zh"],
            "published_spanish_instruction_rows": 0,
            "published_spanglish_instruction_rows": 0,
            "instruction_texts_retained": False,
            "task_identifiers_retained": False,
        },
        "observed_surface": {
            "source_native_baxy_operation_labels": False,
            "word_task_lifecycle_keyword_rows": lifecycle_counts,
            "word_tasks_are_compound_workflows": True,
            "native_microsoft_word_com_tokens_present": False,
            "word_process_checkpoint_mentions": word_process_checkpoint_mentions,
            "published_writer_configuration": "LibreOffice Writer with Word 2007-365 (.docx) default save format",
            "evaluation_path": "LLM screenshot judgement with infeasible no-op environment metric",
            "evaluation_has_native_word_saved_dirty_verifier": False,
            "evaluation_binds_discard_to_confirmation": False,
        },
        "admission": {
            "required_baxy_operations": list(REQUIRED_OPERATIONS),
            "required_source": "Published human request text directly tied to Microsoft Word COM traces and state-sensitive lifecycle verifiers, including confirmation-bound unsaved discard, for all six current typed operations",
            "admitted_baxy_operations": [],
            "reason": "WindowsWorld publishes bilingual English/Chinese compound benchmark instructions and process checks, not BAXY operation labels or Spanish/spanglish requests. Its Word task set has no direct close, discard, or active-document Saved/Dirty request, and its public runtime configuration uses LibreOffice Writer saved as .docx. The benchmark routes evaluation through an LLM screenshot judgement while the environment metric is a no-op, so it provides neither Microsoft Word COM traces nor a native lifecycle verifier. Splitting its compound tasks into BAXY operations would invent labels and cannot repair the missing lifecycle coverage.",
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
        "next_requirement": "Do not reuse WindowsWorld tasks to fill R207 or construct a three-language recogniser-minority Cut B. Search only for published human request text tied to native Microsoft Word COM lifecycle traces and state-sensitive verifiers for all six operations, including confirmation-bound unsaved discard.",
        "identities": {
            "catalogue_sha256": sha256(CATALOGUE),
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
