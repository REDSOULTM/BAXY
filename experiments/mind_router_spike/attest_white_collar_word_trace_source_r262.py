"""Reject technical Word COM traces that do not publish request labels or lifecycle coverage."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
WHITE_COLLAR_ROOT = Path(r"D:\BAXYRuntime\research\white-collar")
CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/audit/white_collar_word_trace_source_r262.json"
EXPECTED_COMMIT = "6c1c9056e800bc357eb07bfc66963c6462b927a4"
EXPECTED_ORIGIN = "https://github.com/tangemicioglu/white-collar.git"
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
    "docs/word-com-operations.md",
    "examples/slides-create.plan.json",
    "examples/word-create.plan.json",
    "examples/word-save-as.plan.json",
    "tests/fixtures/word-remove-watermark-plan.json",
    "tests/fixtures/word-replace-plan.json",
    "tests/test_word_com_real.py",
    "whitecollar/adapters/word_com.py",
    "whitecollar/models.py",
    "whitecollar/word_ops.py",
)
EXPECTED_PLAN_PATHS = (
    "examples/slides-create.plan.json",
    "examples/word-create.plan.json",
    "examples/word-save-as.plan.json",
    "tests/fixtures/word-remove-watermark-plan.json",
    "tests/fixtures/word-replace-plan.json",
)
REQUEST_FIELDS = {"instruction", "prompt", "query", "request", "utterance"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(WHITE_COLLAR_ROOT), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def tree_merkle(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(WHITE_COLLAR_ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build() -> dict[str, object]:
    semantic_paths = [WHITE_COLLAR_ROOT / relative for relative in SEMANTIC_RELATIVE_PATHS]
    if any(not path.is_file() for path in (*semantic_paths, CATALOG)):
        raise RuntimeError(
            "R262 requires the isolated white-collar source and catalogue R219"
        )
    commit = git("rev-parse", "HEAD")
    origin = git("remote", "get-url", "origin")
    if commit != EXPECTED_COMMIT or origin != EXPECTED_ORIGIN:
        raise RuntimeError(
            "R262 source identity changed; do not relabel a different white-collar revision"
        )
    license_text = (WHITE_COLLAR_ROOT / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in license_text:
        raise RuntimeError("R262 expects white-collar's MIT license")
    typed_operations = {
        str(row["name"])
        for row in json.loads(CATALOG.read_text(encoding="utf-8"))["catalogue"][
            "capabilities"
        ]
    }
    if not set(REQUIRED_OPERATIONS) <= typed_operations:
        raise RuntimeError(
            "R262 requires the six current typed Microsoft Word operations"
        )
    plan_paths = sorted(
        [*WHITE_COLLAR_ROOT.glob("examples/*.plan.json"), *WHITE_COLLAR_ROOT.glob("tests/fixtures/*plan.json")],
        key=lambda path: path.relative_to(WHITE_COLLAR_ROOT).as_posix(),
    )
    relative_plan_paths = tuple(
        path.relative_to(WHITE_COLLAR_ROOT).as_posix() for path in plan_paths
    )
    if relative_plan_paths != EXPECTED_PLAN_PATHS:
        raise RuntimeError("R262 expects exactly the five versioned white-collar plans")
    plans = [json.loads(path.read_text(encoding="utf-8")) for path in plan_paths]
    plan_top_level_keys = sorted(set().union(*(plan.keys() for plan in plans)))
    plan_request_fields = sorted(set(plan_top_level_keys) & REQUEST_FIELDS)
    if plan_top_level_keys != ["app", "operations", "policy", "schema", "target", "write"]:
        raise RuntimeError("R262 expects the bounded white-collar machine-plan schema")
    if plan_request_fields:
        raise RuntimeError("R262 expects no request-language field in published plans")
    word_ops_text = (WHITE_COLLAR_ROOT / "whitecollar/word_ops.py").read_text(
        encoding="utf-8"
    )
    word_operations = sorted(
        set(re.findall(r'"(word_(?:live_[a-z_]+|screen_capture))"', word_ops_text))
    )
    if len(word_operations) != 64:
        raise RuntimeError("R262 expects white-collar's 64-operation Word COM vocabulary")
    if any("close" in operation or "discard" in operation for operation in word_operations):
        raise RuntimeError("R262 expects no close or discard public plan operation")
    real_word_test = (WHITE_COLLAR_ROOT / "tests/test_word_com_real.py").read_text(
        encoding="utf-8"
    )
    matrix_operations = re.findall(
        r'\(\s*"(word_(?:live_[a-z_]+|screen_capture))"\s*,\s*\{',
        real_word_test,
    )
    if len(matrix_operations) != 72 or len(set(matrix_operations)) != 63:
        raise RuntimeError("R262 expects the published real-Word operation matrix")
    if any("close" in operation or "discard" in operation for operation in matrix_operations):
        raise RuntimeError("R262 expects no close or discard matrix operation")
    adapter_text = (WHITE_COLLAR_ROOT / "whitecollar/adapters/word_com.py").read_text(
        encoding="utf-8"
    )
    required_witnesses = (
        "class Win32WordComAdapter",
        '"word_live_insert_text"',
        '"word_live_save"',
        '"word_live_get_info"',
        '"saved": bool(_safe_value(doc, "Saved", False))',
        "document.Saved",
    )
    combined_trace = adapter_text + real_word_test
    if any(witness not in combined_trace for witness in required_witnesses):
        raise RuntimeError("R262 expects the public Word COM and Saved-state witnesses")
    return {
        "schema": "baxy.white-collar-word-trace-source.r262.v1",
        "authority": "external_source_identity_and_semantic_admission_audit_not_model_training",
        "verdict": "rejected_preexecution_technical_trace_without_request_or_full_lifecycle_coverage",
        "source": {
            "repository": EXPECTED_ORIGIN,
            "commit": commit,
            "license": "MIT",
            "license_sha256": sha256(WHITE_COLLAR_ROOT / "LICENSE"),
            "semantic_source_files": len(semantic_paths),
            "source_files_merkle_sha256": tree_merkle(semantic_paths),
            "published_machine_plan_files": len(plan_paths),
            "machine_plan_paths": list(relative_plan_paths),
            "machine_plan_top_level_keys": plan_top_level_keys,
            "machine_plan_request_fields": plan_request_fields,
            "machine_plan_texts_retained": False,
            "machine_plan_identifiers_retained": False,
        },
        "observed_surface": {
            "source_native_baxy_operation_labels": False,
            "word_execution_backend": "Microsoft Word COM finite semantic adapter",
            "real_word_matrix_case_rows": len(matrix_operations),
            "real_word_matrix_distinct_operations": len(set(matrix_operations)),
            "word_com_public_operation_count": len(word_operations),
            "word_com_close_operation_present": False,
            "word_com_discard_operation_present": False,
            "real_word_witnesses": {
                "append_like_insert_text": "word_live_insert_text" in word_operations,
                "save_asserts_document_saved": "document.Saved" in real_word_test,
                "create_document": "word_live_create_document" in word_operations,
                "status_reads_active_document_saved": '"saved": bool(_safe_value(doc, "Saved", False))' in adapter_text,
            },
            "internal_close_savechanges_false_is_not_a_plan_operation": True,
            "published_plan_binds_discard_to_confirmation": False,
        },
        "admission": {
            "required_baxy_operations": list(REQUIRED_OPERATIONS),
            "required_application_and_verification": "Published user requests directly tied to Microsoft Word COM traces, including active-document Saved/Dirty state and confirmation-bound discard, for all six missing typed operations",
            "admitted_baxy_operations": [],
            "reason": "white-collar provides authentic Microsoft Word COM implementation and real-Word technical tests, including an insert, save and Saved-state witness. Its five published JSON inputs are bounded machine plans with no request-language field or BAXY labels, however, and its 64-operation plan vocabulary contains neither close nor discard. Close(SaveChanges=False) appears only as internal adapter/test lifecycle management, not as a requested, confirmation-bound public operation. Mapping those plans or technical tests to BAXY user utterances would invent labels and leaves two of the six required lifecycle operations uncovered.",
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
        "next_requirement": "Do not reuse white-collar plans or technical tests to fill R207. Search only for a published source that binds human request text to native Microsoft Word COM lifecycle traces and state-sensitive verifiers, including confirmation-bound unsaved discard, for all six missing typed operations.",
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
