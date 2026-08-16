"""Narrow R257's scope when its R207 development source predates the current catalogue."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
R196 = REPO / "artifacts/development/r196_full_provenance_classifier_training.jsonl"
LEGACY_CATALOG = REPO / "artifacts/development/catalog_vocabulary_snapshot.json"
CURRENT_CATALOG = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
R207 = REPO / "artifacts/development/r207_cross_encoder_pairs.jsonl"
BUILDER = REPO / "experiments/mind_router_spike/build_r207_cross_encoder_pairs.py"
OUTPUT = REPO / "artifacts/audit/r207_catalog_provenance_drift_r263.json"
REQUIRED_WORD_OPERATIONS = (
    "office.word.append",
    "office.word.close",
    "office.word.discard",
    "office.word.save",
    "office.word.start",
    "office.word.status",
)
EXPECTED_QWEN_GENERATED_ROWS = 4179


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def names_from_catalog(path: Path, key_path: tuple[str, ...]) -> set[str]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    for key in key_path:
        value = value[key]  # type: ignore[index]
    return {str(row["name"]) for row in value}  # type: ignore[union-attr]


def build() -> dict[str, object]:
    required_paths = (R196, LEGACY_CATALOG, CURRENT_CATALOG, R207, BUILDER)
    if any(not path.is_file() for path in required_paths):
        raise RuntimeError("R263 requires the immutable R196/R207 provenance inputs")
    r196_rows = jsonl(R196)
    r207_rows = jsonl(R207)
    legacy_operations = names_from_catalog(LEGACY_CATALOG, ("capabilities",))
    current_operations = names_from_catalog(
        CURRENT_CATALOG, ("catalogue", "capabilities")
    )
    r196_labels = {str(row["label"]) for row in r196_rows}
    r207_positive_labels = {
        str(row["operation"]) for row in r207_rows if row["target"] == 1
    }
    source_counts = Counter(str(row["source"]) for row in r196_rows)
    generated_rows = source_counts["qwen-generator+gemma-reviewer"]
    current_missing_from_r196 = tuple(
        sorted(current_operations - r196_labels)
    )
    legacy_missing_from_current = tuple(sorted(legacy_operations - current_operations))
    if len(r196_rows) != 4740 or len(r207_rows) != 23700:
        raise RuntimeError("R263 expects the sealed R196 and R207 row counts")
    if len(legacy_operations) != 169 or len(current_operations) != 174:
        raise RuntimeError("R263 expects the two catalogue snapshot sizes")
    if r196_labels != r207_positive_labels:
        raise RuntimeError("R263 expects R207 positives to preserve every R196 label")
    if r196_labels != legacy_operations | {"__no_action__"}:
        raise RuntimeError("R263 expects R196 to use the prior catalogue plus abstention")
    if current_missing_from_r196 != REQUIRED_WORD_OPERATIONS:
        raise RuntimeError("R263 expects exactly the six current Word operations to be absent")
    if legacy_missing_from_current != ("notification.cancel.at",):
        raise RuntimeError("R263 expects the single retired legacy operation")
    if generated_rows != EXPECTED_QWEN_GENERATED_ROWS:
        raise RuntimeError("R263 expects the sealed generated-source count")
    if any(bool(row["human_semantic_audit"]) for row in r196_rows):
        raise RuntimeError("R263 expects no R196 row to claim human semantic review")
    if any(bool(row["human_semantic_audit"]) for row in r207_rows):
        raise RuntimeError("R263 expects no R207 pair to claim human semantic review")
    if any(operation in r207_positive_labels for operation in REQUIRED_WORD_OPERATIONS):
        raise RuntimeError("R263 expects no positive R207 pair for the six Word operations")
    builder = BUILDER.read_text(encoding="utf-8")
    if "SOURCE=REPO/'artifacts/development/r196_full_provenance_classifier_training.jsonl'" not in builder:
        raise RuntimeError("R263 expects R207's recorded R196 input")
    return {
        "schema": "baxy.r207-catalog-provenance-drift.r263.v1",
        "authority": "development_source_provenance_scope_audit_not_model_training",
        "verdict": "development_evidence_scope_narrowed_stale_catalog_and_unreviewed_r207_provenance",
        "source": {
            "r196_training_rows": len(r196_rows),
            "r207_pair_rows": len(r207_rows),
            "r207_positive_pairs": sum(row["target"] == 1 for row in r207_rows),
            "r196_unique_labels": len(r196_labels),
            "prior_catalogue_operations": len(legacy_operations),
            "current_catalogue_operations": len(current_operations),
            "qwen_generated_r196_rows": generated_rows,
            "other_r196_rows": len(r196_rows) - generated_rows,
            "r196_human_semantic_audit_rows": 0,
            "r207_human_semantic_audit_pairs": 0,
            "query_texts_retained": False,
            "query_identifiers_retained": False,
            "source_files_merkle_sha256": hashlib.sha256(
                "".join(
                    f"{path.relative_to(REPO).as_posix()}\0{sha256(path)}\n"
                    for path in required_paths
                ).encode("utf-8")
            ).hexdigest(),
        },
        "catalogue_delta": {
            "current_operations_missing_from_r196_and_r207_positives": list(
                current_missing_from_r196
            ),
            "legacy_operations_absent_from_current": list(legacy_missing_from_current),
            "r196_uses_prior_catalogue_plus_explicit_abstention": True,
        },
        "interpretation": {
            "r257_numerical_result_changed": False,
            "r257_full_current_catalogue_coverage_claim_supported": False,
            "r207_provenance_is_human_semantically_reviewed": False,
            "native_microsoft_word_com_requests_present_for_missing_operations": False,
            "admitted_baxy_operations": [],
            "reason": "R207 deterministically preserves R196 labels built against a 169-operation snapshot plus __no_action__. The current catalogue has six Microsoft Word lifecycle operations absent from both that snapshot and every R196/R207 positive; it also retires notification.cancel.at. In addition, every R196 and R207 row records human_semantic_audit false, and 4,179 of 4,740 R196 rows identify qwen-generator+gemma-reviewer as their source. R257's measured retrieval values remain factual for its query-disjoint R207 population, but cannot become a coverage or semantic-admission claim for the current 174-operation catalogue.",
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
        "next_requirement": "Do not backfill the six Word labels from current catalogue descriptions, R196-style generated text, or technical plans. A successor must establish independently published human requests tied to native Microsoft Word COM lifecycle verification for all six operations before any new all-catalogue retrieval measurement.",
        "identities": {
            "r196_sha256": sha256(R196),
            "legacy_catalogue_sha256": sha256(LEGACY_CATALOG),
            "current_catalogue_sha256": sha256(CURRENT_CATALOG),
            "r207_sha256": sha256(R207),
            "program_sha256": sha256(Path(__file__)),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite provenance audit: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
