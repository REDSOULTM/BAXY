"""Reject PC-Eval's instruction-only Word subset for BAXY lifecycle evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
PC_EVAL_ROOT = Path(r"D:\BAXYRuntime\research\PC-Eval")
CATALOGUE = REPO / "artifacts" / "development" / "current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts" / "audit" / "pc_eval_word_source_r269.json"
EXPECTED_COMMIT = "39317b7d903e5bbdf72c16069a9bbded67b31b21"
EXPECTED_ORIGIN = "https://huggingface.co/datasets/StarBottle/PC-Eval"
REQUIRED_OPERATIONS = (
    "office.word.append",
    "office.word.close",
    "office.word.discard",
    "office.word.save",
    "office.word.start",
    "office.word.status",
)
SEMANTIC_RELATIVE_PATHS = (
    "README.md",
    "PC-Eval.json",
    "memo.txt",
    "movie_rate.xlsx",
    "test_doc1.docx",
    "test_doc2.docx",
    "test_doc3.docx",
    "travel_plan.txt",
    "travel_plan2.txt",
)
EXECUTABLE_OR_VERIFIER_SUFFIXES = {".cs", ".js", ".ps1", ".py", ".ts"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(PC_EVAL_ROOT), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def tree_merkle(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(PC_EVAL_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _catalogue_operations() -> set[str]:
    payload = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    capabilities = payload.get("catalogue", {}).get("capabilities")
    if not isinstance(capabilities, list):
        raise RuntimeError("R269 requires catalogue R219")
    return {
        row["name"]
        for row in capabilities
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }


def _instruction_rows(path: Path) -> tuple[list[str], bool]:
    source = path.read_text(encoding="utf-8")
    try:
        decoded = json.loads(source)
    except json.JSONDecodeError:
        decoded = None
    is_json_array = isinstance(decoded, list)
    rows: list[str] = []
    for line_number, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip().removesuffix(",")
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"R269 instruction line {line_number} is not a string")
        rows.append(value)
    return rows, is_json_array


def _word_lifecycle_counts(texts: list[str]) -> dict[str, int]:
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
    semantic_paths = [PC_EVAL_ROOT / relative for relative in SEMANTIC_RELATIVE_PATHS]
    if any(not path.is_file() for path in (*semantic_paths, CATALOGUE)):
        raise RuntimeError("R269 requires the isolated PC-Eval source and catalogue R219")
    commit = git("rev-parse", "HEAD")
    origin = git("remote", "get-url", "origin")
    if commit != EXPECTED_COMMIT or origin != EXPECTED_ORIGIN:
        raise RuntimeError("R269 source identity changed; do not relabel another revision")
    if "license: apache-2.0" not in (PC_EVAL_ROOT / "README.md").read_text(
        encoding="utf-8"
    ).casefold():
        raise RuntimeError("R269 expects PC-Eval's Apache-2.0 dataset card")
    if not set(REQUIRED_OPERATIONS) <= _catalogue_operations():
        raise RuntimeError("R269 requires the six current typed Microsoft Word operations")

    instructions, is_json_array = _instruction_rows(PC_EVAL_ROOT / "PC-Eval.json")
    normalized = {" ".join(text.split()).casefold() for text in instructions}
    word_instructions = [
        text for text in instructions if re.search(r"\bword\b", text, re.IGNORECASE)
    ]
    lifecycle_counts = _word_lifecycle_counts(word_instructions)
    if (
        len(instructions) != 27
        or len(normalized) != 26
        or len(word_instructions) != 7
        or is_json_array
        or any(
            lifecycle_counts[operation] != 0
            for operation in (
                "office.word.append",
                "office.word.close",
                "office.word.discard",
                "office.word.status",
            )
        )
    ):
        raise RuntimeError("R269 expects PC-Eval's bounded instruction-only Word subset")
    executable_or_verifier_paths = sorted(
        path.relative_to(PC_EVAL_ROOT).as_posix()
        for path in PC_EVAL_ROOT.rglob("*")
        if path.is_file() and path.suffix.casefold() in EXECUTABLE_OR_VERIFIER_SUFFIXES
    )
    if executable_or_verifier_paths:
        raise RuntimeError("R269 expects no published execution or verifier source files")

    return {
        "schema": "baxy.pc-eval-word-source.r269.v1",
        "authority": "external_source_identity_and_semantic_admission_audit_not_model_training",
        "verdict": "rejected_preexecution_instruction_only_no_com_or_lifecycle_verifier",
        "source": {
            "repository": EXPECTED_ORIGIN,
            "commit": commit,
            "license": "Apache-2.0",
            "dataset_card_sha256": sha256(PC_EVAL_ROOT / "README.md"),
            "semantic_source_files": len(semantic_paths),
            "source_files_merkle_sha256": tree_merkle(semantic_paths),
            "published_instruction_rows": len(instructions),
            "distinct_normalized_instruction_rows": len(normalized),
            "instruction_stream_is_json_array": is_json_array,
            "published_word_instruction_rows": len(word_instructions),
            "published_instruction_language": "en",
            "published_spanish_instruction_rows": 0,
            "published_spanglish_instruction_rows": 0,
            "instruction_texts_retained": False,
        },
        "observed_surface": {
            "source_native_baxy_operation_labels": False,
            "word_lifecycle_keyword_rows": lifecycle_counts,
            "published_execution_or_verifier_source_files": executable_or_verifier_paths,
            "published_microsoft_word_com_trace": False,
            "published_saved_dirty_verifier": False,
            "published_confirmation_bound_discard_verifier": False,
        },
        "admission": {
            "required_baxy_operations": list(REQUIRED_OPERATIONS),
            "required_source": "Published human request text directly tied to Microsoft Word COM traces and state-sensitive lifecycle verifiers, including confirmation-bound unsaved discard, for all six current typed operations",
            "admitted_baxy_operations": [],
            "reason": "PC-Eval publishes English instruction strings and static input documents but no execution or verifier source, no BAXY operation labels, no Microsoft Word COM trace and no Spanish or spanglish request surface. Its seven Word instructions contain save/start wording only; append, close, discard and Saved/Dirty status are absent. Treating a compound instruction or static document as a typed lifecycle example would invent the missing mapping and cannot establish confirmation-bound discard or a native state verifier.",
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
        "next_requirement": "Do not use PC-Eval to fill R207 or create the new three-language Cut B. Search only for published human request text tied to native Microsoft Word COM lifecycle traces and state-sensitive verifiers for all six operations, including confirmation-bound unsaved discard.",
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
