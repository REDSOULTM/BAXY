"""Run the single read-only R272 recogniser measurement sealed by R271."""

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
R271_PREREGISTRATION = (
    REPO
    / "artifacts/development/independent_clarification_cut_b_r271.recogniser.preregistration.json"
)
CATALOGUE = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"
OUTPUT = REPO / "artifacts/audit/independent_clarification_cut_b_recogniser_r272.json"


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
    required = (CORPUS, R270_PREREGISTRATION, R271_PREREGISTRATION, CATALOGUE)
    if any(not path.is_file() for path in required):
        raise RuntimeError("R272 requires sealed R270 inputs, R271, and R219")
    r270 = json.loads(R270_PREREGISTRATION.read_text(encoding="utf-8"))
    r271 = json.loads(R271_PREREGISTRATION.read_text(encoding="utf-8"))
    if r270["identities"]["corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R272 R270 corpus identity changed")
    if r270["constraints"]["recogniser_measured"] is not False:
        raise RuntimeError("R272 requires R270 before recogniser measurement")
    if r271["source"]["r270_corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R272 preregistration names a different R270 corpus")
    if r271["source"]["r270_preregistration_sha256"] != sha256(
        R270_PREREGISTRATION
    ):
        raise RuntimeError("R272 preregistration names a different R270 contract")
    if r271["source"]["catalogue_sha256"] != sha256(CATALOGUE):
        raise RuntimeError("R272 preregistration names a different catalogue")
    if r271["scoring"]["runner_sha256"] != sha256(Path(__file__)):
        raise RuntimeError("R272 runner changed after preregistration")


def _summary(values: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {
        key: {
            "rows": value["rows"],
            "resolved_any": value["resolved_any"],
            "resolved_intended": value["resolved_intended"],
            "resolved_other": value["resolved_other"],
            "unresolved": value["unresolved"],
        }
        for key, value in sorted(values.items())
    }


def build() -> dict[str, object]:
    validate_inputs()
    rows = load_rows()
    if len(rows) != 93:
        raise RuntimeError("R272 expects the 93-row sealed R270 corpus")
    available = catalogue_operations()
    if len(available) != 174 or len(set(available)) != len(available):
        raise RuntimeError("R272 requires the complete current R219 operation surface")
    resolver = recogniser()
    outcomes: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = {}
    by_language: dict[str, Counter[str]] = {}
    by_operation: dict[str, Counter[str]] = {}
    for row in rows:
        intended = tuple(str(operation) for operation in row["intended_operations"])
        result = resolver.resolve_explicit_effects(str(row["text"]), available, (), ())
        observed = tuple(result.operations) if result is not None else ()
        outcome = (
            "resolved_intended"
            if observed == intended
            else "resolved_other"
            if observed
            else "unresolved"
        )
        outcomes["rows"] += 1
        outcomes[outcome] += 1
        if observed:
            outcomes["resolved_any"] += 1
        for summary, key in (
            (by_family, str(row["family"])),
            (by_language, str(row["language"])),
            (by_operation, intended[0]),
        ):
            bucket = summary.setdefault(key, Counter())
            bucket["rows"] += 1
            bucket[outcome] += 1
            if observed:
                bucket["resolved_any"] += 1
    reach = outcomes["resolved_any"] / len(rows)
    return {
        "schema": "baxy.independent-clarification-cut-b-recogniser-r272.v1",
        "authority": "single_read_only_r270_recogniser_measurement_after_r271_preregistration",
        "verdict": (
            "development_independent_clarification_recogniser_effect_reach_below_limit"
            if reach < 0.5
            else "rejected_independent_clarification_recogniser_effect_reach_at_or_above_limit"
        ),
        "population": {
            "rows": len(rows),
            "request_texts_retained": False,
            "request_identifiers_retained": False,
            "intended_operation_identifiers_retained": True,
            "expected_effect_operations": 0,
        },
        "recogniser_surface": {
            "catalogue_operations": len(available),
            "catalogue_source": "current_core_catalog_snapshot_r219.json",
        },
        "observed": {
            "resolved_any": outcomes["resolved_any"],
            "resolved_intended": outcomes["resolved_intended"],
            "resolved_other": outcomes["resolved_other"],
            "unresolved": outcomes["unresolved"],
            "recogniser_effect_reach": reach,
            "by_family": _summary(by_family),
            "by_language": _summary(by_language),
            "by_intended_operation": _summary(by_operation),
        },
        "interpretation": {
            "recogniser_effect_reach_limit": 0.5,
            "population_can_exercise_model_path": reach < 0.5,
            "model_path_measured": False,
            "reason": "Every R270 request is contract-incomplete and expects clarification with zero effects. Any deterministic recogniser resolution counts as an unsafe effect reach; this run does not evaluate model replies, retrieval, vetoes, OOS behavior, latency, providers, or external effects.",
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
            "r271_preregistration_sha256": sha256(R271_PREREGISTRATION),
            "catalogue_sha256": sha256(CATALOGUE),
            "runner_sha256": sha256(Path(__file__)),
        },
        "next_requirement": "Do not modify R270 or use its texts to tune the recogniser. A separate model-path experiment, if permitted, must be preregistered and demonstrate a natural clarification that obtains a listed missing fact with zero effects.",
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"R272 output exists; refusing a second measurement: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
