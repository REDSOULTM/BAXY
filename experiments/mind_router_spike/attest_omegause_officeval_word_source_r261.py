"""Reject final-artifact OfficeVal tasks as labels for active Word lifecycle operations."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
OMEGA_ROOT = Path(r"D:\BAXYRuntime\research\OmegaUse-OfficeVal")
README = OMEGA_ROOT / "README.md"
TASKS = OMEGA_ROOT / "tasks_and_rubrics_en.json"
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/audit/omegause_officeval_word_source_r261.json"
EXPECTED_COMMIT = "cd6ba6d8fb83b3fb551e24eebc20e1fb0bd154a5"
EXPECTED_ORIGIN = (
    "https://huggingface.co/datasets/baidu-frontier-research/OmegaUse-OfficeVal"
)
REQUIRED_OPERATIONS = (
    "office.word.append",
    "office.word.close",
    "office.word.discard",
    "office.word.save",
    "office.word.start",
    "office.word.status",
)
EXPECTED_TOP_LEVEL_KEYS = (
    "domain",
    "human_labor_time",
    "id",
    "instruction",
    "operation_intent",
    "origin_files",
    "price_source",
    "rubrics",
    "task_price_proxy",
)
KEYWORD_PATTERNS = {
    "office.word.append": re.compile(
        r"(?i)(?:append|add).*(?:end|existing|document|docx|word)|"
        r"(?:end|existing|document|docx|word).*?(?:append|add)"
    ),
    "office.word.close": re.compile(r"(?i)\bclose\b"),
    "office.word.discard": re.compile(
        r"(?i)discard|don't save|do not save|without saving"
    ),
    "office.word.save": re.compile(r"(?i)\bsave\b"),
    "office.word.start": re.compile(
        r"(?i)(?:open|create|new).*(?:word|document|docx)|"
        r"(?:word|document|docx).*?(?:open|create|new)"
    ),
    "office.word.status": re.compile(
        r"(?i)active document|saved|unsaved|dirty|document status"
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(OMEGA_ROOT), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def tree_merkle(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(OMEGA_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build() -> dict[str, object]:
    if not README.is_file() or not TASKS.is_file() or not CATALOG.is_file():
        raise RuntimeError(
            "R261 requires the isolated OmegaUse-OfficeVal source and catalogue R219"
        )
    commit = git("rev-parse", "HEAD")
    origin = git("remote", "get-url", "origin")
    if commit != EXPECTED_COMMIT or origin != EXPECTED_ORIGIN:
        raise RuntimeError(
            "R261 source identity changed; do not relabel a different OmegaUse revision"
        )
    readme = README.read_text(encoding="utf-8")
    if (
        "license: apache-2.0" not in readme
        or "Evaluation focuses on the quality and correctness" not in readme
        or "specific execution trajectory." not in readme
    ):
        raise RuntimeError(
            "R261 expects OmegaUse's Apache license and final-artifact evaluation contract"
        )
    rows = json.loads(TASKS.read_text(encoding="utf-8"))
    top_level_keys = tuple(sorted(set().union(*(row.keys() for row in rows))))
    if len(rows) != 100 or top_level_keys != EXPECTED_TOP_LEVEL_KEYS:
        raise RuntimeError(
            "R261 expects exactly 100 merged English OmegaUse task records"
        )
    if any(not isinstance(row["rubrics"], dict) for row in rows):
        raise RuntimeError(
            "R261 expects final-artifact rubric dictionaries, not execution traces"
        )
    typed_operations = {
        str(row["name"])
        for row in json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"][
            "capabilities"
        ]
    }
    if not set(REQUIRED_OPERATIONS) <= typed_operations:
        raise RuntimeError(
            "R261 requires the six current typed Microsoft Word operations"
        )
    instructions = [str(row["instruction"]) for row in rows]
    word_related = [
        text for text in instructions if re.search(r"(?i)word|docx|document", text)
    ]
    keyword_candidates = {
        operation: sum(bool(pattern.search(text)) for text in word_related)
        for operation, pattern in KEYWORD_PATTERNS.items()
    }
    operation_intents = sorted({str(row["operation_intent"]) for row in rows})
    return {
        "schema": "baxy.omegause-officeval-word-source.r261.v1",
        "authority": "external_source_identity_and_semantic_admission_audit_not_model_training",
        "verdict": "rejected_preexecution_final_artifact_only_lifecycle_mismatch",
        "source": {
            "repository": EXPECTED_ORIGIN,
            "commit": commit,
            "license": "Apache-2.0",
            "source_files_merkle_sha256": tree_merkle([README, TASKS]),
            "merged_english_task_rows": len(rows),
            "word_related_instruction_rows": len(word_related),
            "operation_intents": operation_intents,
            "task_instruction_texts_retained": False,
            "task_instruction_identifiers_retained": False,
        },
        "observed_surface": {
            "source_native_baxy_operation_labels": False,
            "source_requires_microsoft_word_application": False,
            "evaluation_target": "final delivered artifact, not execution trajectory",
            "evaluation_allows_gui_scripts_or_apis": True,
            "evaluation_observes_active_document_state": False,
            "evaluation_observes_saved_dirty_state": False,
            "evaluation_binds_discard_to_confirmation": False,
        },
        "admission": {
            "required_baxy_operations": list(REQUIRED_OPERATIONS),
            "required_application_and_verification": "Microsoft Word operations verified through COM, including an active document, Saved/Dirty state and confirmation-bound discard",
            "instruction_keyword_candidates_not_labels": keyword_candidates,
            "admitted_baxy_operations": [],
            "reason": "OmegaUse publishes authentic long-horizon requests and final-artifact rubrics, but deliberately does not constrain or observe the execution trajectory. It has no native BAXY labels and no close, discard, save or active-state requests in its Word-related instructions. Final deliverable quality cannot establish BAXY's active Microsoft Word lifecycle semantics.",
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
        "next_requirement": "Do not use OmegaUse final-artifact tasks to fill R207. A successor must publish native Microsoft Word COM lifecycle requests and state-sensitive verifiers for all six missing typed operations.",
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
