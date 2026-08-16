"""Measure R270's ordered deterministic entry paths once, without a model."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/development/independent_clarification_cut_b_r270.jsonl"
R270_PREREGISTRATION = (
    REPO
    / "artifacts/development/independent_clarification_cut_b_r270.preregistration.json"
)
R272_RESULT = (
    REPO / "artifacts/audit/independent_clarification_cut_b_recogniser_r272.json"
)
R273_PREREGISTRATION = (
    REPO
    / "artifacts/development/independent_clarification_cut_b_r273.entry-path.preregistration.json"
)
CATALOGUE = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/audit/independent_clarification_cut_b_entry_path_r274.json"

OUTCOMES = (
    "explicit_clarification",
    "explicit_effect",
    "model_decision_candidate_after_two_effect_gates",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line
    ]


def catalogue_operations() -> tuple[str, ...]:
    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    return tuple(
        sorted(
            str(capability["name"])
            for capability in catalogue["catalogue"]["capabilities"]
        )
    )


def recogniser() -> Any:
    source = str(REPO / "src")
    import sys

    if source not in sys.path:
        sys.path.insert(0, source)
    return importlib.import_module("baxy_mind.effect_intent")


def validate_inputs() -> None:
    required = (CORPUS, R270_PREREGISTRATION, R272_RESULT, R273_PREREGISTRATION, CATALOGUE)
    if any(not path.is_file() for path in required):
        raise RuntimeError("R274 requires sealed R270/R272/R273 inputs and R219")
    r270 = json.loads(R270_PREREGISTRATION.read_text(encoding="utf-8"))
    r272 = json.loads(R272_RESULT.read_text(encoding="utf-8"))
    r273 = json.loads(R273_PREREGISTRATION.read_text(encoding="utf-8"))
    if r270["identities"]["corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R274 R270 corpus identity changed")
    if r272["identities"]["r270_corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R274 R272 source identity changed")
    if r273["source"]["r270_corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R274 preregistration names a different R270 corpus")
    if r273["source"]["r272_result_sha256"] != sha256(R272_RESULT):
        raise RuntimeError("R274 preregistration names a different R272 result")
    if r273["source"]["catalogue_sha256"] != sha256(CATALOGUE):
        raise RuntimeError("R274 preregistration names a different catalogue")
    if r273["scoring"]["runner_sha256"] != sha256(Path(__file__)):
        raise RuntimeError("R274 runner changed after preregistration")


def _summary(values: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {
        key: {"rows": value["rows"], **{outcome: value[outcome] for outcome in OUTCOMES}}
        for key, value in sorted(values.items())
    }


def build() -> dict[str, object]:
    validate_inputs()
    rows = load_rows()
    if len(rows) != 93:
        raise RuntimeError("R274 expects the sealed 93-row R270 corpus")
    available = catalogue_operations()
    if len(available) != 174 or len(set(available)) != len(available):
        raise RuntimeError("R274 requires the complete R219 operation surface")
    resolver = recogniser()
    outcomes: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = {}
    by_language: dict[str, Counter[str]] = {}
    by_operation: dict[str, Counter[str]] = {}
    explicit_clarification_operations: Counter[str] = Counter()
    explicit_effect_operations: Counter[str] = Counter()
    for row in rows:
        clarification = resolver.resolve_explicit_clarification_intent(
            str(row["text"]), available
        )
        if clarification is not None:
            outcome = "explicit_clarification"
            for operation in clarification.operations:
                explicit_clarification_operations[str(operation)] += 1
        else:
            effect = resolver.resolve_explicit_effects(
                str(row["text"]), available, (), ()
            )
            if effect is not None:
                outcome = "explicit_effect"
                for operation in effect.operations:
                    explicit_effect_operations[str(operation)] += 1
            else:
                outcome = "model_decision_candidate_after_two_effect_gates"
        outcomes[outcome] += 1
        for summary, key in (
            (by_family, str(row["family"])),
            (by_language, str(row["language"])),
            (by_operation, str(row["intended_operations"][0])),
        ):
            bucket = summary.setdefault(key, Counter())
            bucket["rows"] += 1
            bucket[outcome] += 1
    candidate_reach = outcomes["model_decision_candidate_after_two_effect_gates"] / len(rows)
    return {
        "schema": "baxy.independent-clarification-cut-b.entry-path-r274.v1",
        "authority": "single_read_only_r270_entry_path_measurement_after_r273_preregistration",
        "verdict": (
            "development_r270_can_exercise_raw_model_decision_after_two_effect_gates"
            if candidate_reach >= 0.5
            else "rejected_r270_raw_model_decision_reach_below_limit_after_two_effect_gates"
        ),
        "population": {
            "rows": len(rows),
            "request_texts_retained": False,
            "request_identifiers_retained": False,
            "intended_operation_identifiers_retained": True,
        },
        "recogniser_surface": {
            "catalogue_operations": len(available),
            "ordered_gates": [
                "resolve_explicit_clarification_intent",
                "resolve_explicit_effects",
            ],
        },
        "observed": {
            **{outcome: outcomes[outcome] for outcome in OUTCOMES},
            "model_decision_candidate_reach": candidate_reach,
            "explicit_clarification_operations": dict(
                sorted(explicit_clarification_operations.items())
            ),
            "explicit_effect_operations": dict(sorted(explicit_effect_operations.items())),
            "by_family": _summary(by_family),
            "by_language": _summary(by_language),
            "by_intended_operation": _summary(by_operation),
        },
        "interpretation": {
            "model_decision_candidate_reach_limit": 0.5,
            "population_can_exercise_raw_model_decision": candidate_reach >= 0.5,
            "model_started": False,
            "reason": "This partitions only the two ordered deterministic effect gates that precede the full decision flow. Explicit conversation and later policy exits are not credited as model-decision reach; no model, retrieval, veto, visible reply, provider, or external effect was measured.",
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
        "identities": {
            "r270_corpus_sha256": sha256(CORPUS),
            "r270_preregistration_sha256": sha256(R270_PREREGISTRATION),
            "r272_result_sha256": sha256(R272_RESULT),
            "r273_preregistration_sha256": sha256(R273_PREREGISTRATION),
            "catalogue_sha256": sha256(CATALOGUE),
            "runner_sha256": sha256(Path(__file__)),
        },
        "next_requirement": "Do not modify R270 or tune the recogniser from this result. Only if this path has sufficient reach may a full model-decision candidate be separately preregistered.",
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"R274 output exists; refusing a second measurement: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
