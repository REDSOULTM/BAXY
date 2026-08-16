"""Run exactly one read-only recogniser-reach measurement for sealed R264."""

from __future__ import annotations

import hashlib
import importlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/development/fresh_independent_cut_b_r264.jsonl"
R264_PREREGISTRATION = (
    REPO / "artifacts/development/fresh_independent_cut_b_r264.preregistration.json"
)
MEASUREMENT_PREREGISTRATION = (
    REPO
    / "artifacts/development/fresh_independent_cut_b_r265.recogniser.preregistration.json"
)
ALIASES = REPO / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
OUTPUT = REPO / "artifacts/audit/fresh_independent_cut_b_recogniser_r265.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line
    ]


def alias_operations() -> tuple[str, ...]:
    aliases = json.loads(ALIASES.read_text(encoding="utf-8"))
    return tuple(
        sorted(
            {
                operation
                for row in aliases["aliases"]
                for operation in [
                    row.get("target_operation"),
                    *(row.get("operations") or []),
                ]
                if operation
            }
        )
    )


def recogniser() -> Any:
    source = str(REPO / "src")
    import sys

    if source not in sys.path:
        sys.path.insert(0, source)
    return importlib.import_module("baxy_mind.effect_intent")


def validate_inputs() -> dict[str, object]:
    if any(
        not path.is_file()
        for path in (CORPUS, R264_PREREGISTRATION, MEASUREMENT_PREREGISTRATION, ALIASES)
    ):
        raise RuntimeError("R265 requires the sealed R264 inputs, preregistration, and aliases")
    r264 = json.loads(R264_PREREGISTRATION.read_text(encoding="utf-8"))
    r265 = json.loads(MEASUREMENT_PREREGISTRATION.read_text(encoding="utf-8"))
    if r264["identities"]["corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R265 R264 corpus identity changed")
    if r264["constraints"]["recogniser_measured"] is not False:
        raise RuntimeError("R265 requires R264 before recogniser measurement")
    if r265["identities"]["runner_sha256"] != sha256(Path(__file__)):
        raise RuntimeError("R265 runner changed after preregistration")
    if r265["identities"]["r264_corpus_sha256"] != sha256(CORPUS):
        raise RuntimeError("R265 preregistration names a different R264 corpus")
    return r265


def build() -> dict[str, object]:
    validate_inputs()
    rows = load_rows()
    if len(rows) != 114:
        raise RuntimeError("R265 expects 114 sealed R264 rows")
    available = alias_operations()
    available_set = set(available)
    resolver = recogniser()
    by_family: dict[str, Counter[str]] = {}
    by_language: dict[str, Counter[str]] = {}
    by_operation: dict[str, Counter[str]] = {}
    outcomes: Counter[str] = Counter()
    expected_missing_from_aliases: Counter[str] = Counter()
    for row in rows:
        expected = tuple(str(operation) for operation in row["expected_operations"])
        result = resolver.resolve_explicit_effects(row["text"], available, (), ())
        observed = tuple(result.operations) if result is not None else ()
        outcome = (
            "resolved_expected"
            if observed == expected
            else "resolved_other"
            if observed
            else "unresolved"
        )
        outcomes[outcome] += 1
        groups = (
            (by_family, str(row["family"])),
            (by_language, str(row["language"])),
        )
        for summary, key in groups:
            bucket = summary.setdefault(key, Counter())
            bucket["rows"] += 1
            bucket[outcome] += 1
        for operation in expected:
            bucket = by_operation.setdefault(operation, Counter())
            bucket["rows"] += 1
            bucket[outcome] += 1
            if operation not in available_set:
                expected_missing_from_aliases[operation] += 1

    def summary(values: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
        return {
            key: {
                "rows": value["rows"],
                "resolved_expected": value["resolved_expected"],
                "resolved_other": value["resolved_other"],
                "unresolved": value["unresolved"],
            }
            for key, value in sorted(values.items())
        }

    resolved_expected = outcomes["resolved_expected"]
    reach = resolved_expected / len(rows)
    return {
        "schema": "baxy.fresh-independent-cut-b-recogniser-r265.v1",
        "authority": "single_read_only_recogniser_measurement_after_r264_preregistration",
        "verdict": (
            "development_independent_cut_b_recogniser_reach_below_majority"
            if reach < 0.5
            else "rejected_independent_cut_b_recogniser_reach_majority_or_higher"
        ),
        "population": {
            "rows": len(rows),
            "request_texts_retained": False,
            "request_identifiers_retained": False,
            "expected_operation_identifiers_retained": True,
            "confirmation_bound_rows": sum(
                bool(row["confirmation_required"]) for row in rows
            ),
        },
        "recogniser_surface": {
            "alias_catalogue_operations": len(available),
            "expected_operations_missing_from_alias_catalogue": sorted(
                expected_missing_from_aliases
            ),
            "expected_rows_with_no_alias_for_at_least_one_operation": sum(
                1
                for row in rows
                if any(
                    operation not in available_set
                    for operation in row["expected_operations"]
                )
            ),
        },
        "observed": {
            "resolved_expected": resolved_expected,
            "resolved_other": outcomes["resolved_other"],
            "unresolved": outcomes["unresolved"],
            "recogniser_reach": reach,
            "by_family": summary(by_family),
            "by_language": summary(by_language),
            "by_expected_operation": summary(by_operation),
        },
        "interpretation": {
            "recogniser_majority_limit": 0.5,
            "population_can_exercise_model_path": reach < 0.5,
            "model_path_measured": False,
            "reason": "This result prices only the explicit recogniser boundary on a fresh manually specified population. It does not evaluate retrieval, model decision, vetoes, visible text, OOS behavior, latency, providers, or external effects.",
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
            "r264_corpus_sha256": sha256(CORPUS),
            "r264_preregistration_sha256": sha256(R264_PREREGISTRATION),
            "r265_preregistration_sha256": sha256(MEASUREMENT_PREREGISTRATION),
            "aliases_sha256": sha256(ALIASES),
            "runner_sha256": sha256(Path(__file__)),
        },
        "next_requirement": "Do not alter R264 or use this population to tune the recogniser. A later model-path experiment must be preregistered separately and report retrieval, raw decision, veto, visible-text, OOS, latency, and zero-effect evidence.",
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"R265 output exists; refusing a second recogniser measurement: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
