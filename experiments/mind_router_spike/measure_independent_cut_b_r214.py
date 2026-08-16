"""Open R213 once to price deterministic recogniser reach, not product quality."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/holdout/independent_cut_b_r213.jsonl"
PREREGISTRATION = REPO / "artifacts/holdout/independent_cut_b_r213.preregistration.json"
ALIASES = REPO / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
OUTPUT = REPO / "artifacts/audit/independent_cut_b_r213_recogniser_reach_r214.json"
sys.path.insert(0, str(REPO / "src"))

from baxy_mind import effect_intent  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _operations() -> tuple[str, ...]:
    aliases = json.loads(ALIASES.read_text(encoding="utf-8"))["aliases"]
    return tuple(
        sorted(
            {
                operation
                for alias in aliases
                for operation in [
                    alias.get("target_operation"),
                    *(alias.get("operations") or []),
                ]
                if operation
            }
        )
    )


def _rows(path: Path = CORPUS) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def measure(corpus_path: Path = CORPUS) -> dict[str, Any]:
    rows = _rows(corpus_path)
    offered = _operations()
    outcomes: list[dict[str, Any]] = []
    for row in rows:
        intent = effect_intent.resolve_explicit_effects(row["text"], offered, (), ())
        observed = list(intent.operations) if intent is not None else []
        expected = row["expected_operations"]
        outcome = (
            "expected"
            if observed == expected
            else "other"
            if observed
            else "unresolved"
        )
        outcomes.append({**row, "observed_operations": observed, "outcome": outcome})

    def counts(items: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(items)
        expected = sum(item["outcome"] == "expected" for item in items)
        return {
            "rows": total,
            "expected": expected,
            "other": sum(item["outcome"] == "other" for item in items),
            "unresolved": sum(item["outcome"] == "unresolved" for item in items),
            "reach": round(expected / total, 6),
        }

    by_language = {
        language: counts([row for row in outcomes if row["language"] == language])
        for language in sorted(Counter(row["language"] for row in outcomes))
    }
    by_family = {
        family: counts([row for row in outcomes if row["family"] == family])
        for family in sorted(Counter(row["family"] for row in outcomes))
    }
    summary = counts(outcomes)
    return {
        "schema": "baxy.independent-cut-b-r213-recogniser-reach-r214.v1",
        "authority": "opened_once_read_only_baseline_not_an_end_to_end_cut_result",
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "corpus_sha256": _sha256(corpus_path),
            "preregistration_sha256": _sha256(PREREGISTRATION),
            "aliases_sha256": _sha256(ALIASES),
            "effect_intent_sha256": _sha256(REPO / "src/baxy_mind/effect_intent.py"),
        },
        "population": {
            "rows": len(rows),
            "families": len(by_family),
            "languages": {
                language: counts["rows"] for language, counts in by_language.items()
            },
        },
        "recogniser": {
            "available_operations": len(offered),
            "overall": summary,
            "by_language": by_language,
            "by_family": by_family,
            "majority_limit": 0.5,
            "independent_of_recogniser_grammar": summary["reach"] < 0.5,
        },
        "execution": {
            "product_started": False,
            "decider_invoked": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "outcomes": outcomes,
        "next_step": "Use this frozen population only to evaluate a separately preregistered model-path candidate; do not alter R213 text or labels from this result.",
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("r214_is_one_shot_and_already_opened")
    report = measure()
    OUTPUT.write_bytes(
        (
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    )


if __name__ == "__main__":
    main()
