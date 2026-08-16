"""Open R215 once to test whether situated language escapes recogniser grammar."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "artifacts/holdout/situated_cut_b_r215.jsonl"
PREREGISTRATION = REPO / "artifacts/holdout/situated_cut_b_r215.preregistration.json"
ALIASES = REPO / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
OUTPUT = REPO / "artifacts/audit/situated_cut_b_r215_recogniser_reach_r216.json"
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


def _counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    expected = sum(row["outcome"] == "expected" for row in rows)
    return {
        "rows": total,
        "expected": expected,
        "other": sum(row["outcome"] == "other" for row in rows),
        "unresolved": sum(row["outcome"] == "unresolved" for row in rows),
        "reach": round(expected / total, 6),
    }


def measure(corpus_path: Path = CORPUS) -> dict[str, Any]:
    offered = _operations()
    outcomes = []
    for row in _rows(corpus_path):
        intent = effect_intent.resolve_explicit_effects(row["text"], offered, (), ())
        observed = list(intent.operations) if intent is not None else []
        outcome = (
            "expected"
            if observed == row["expected_operations"]
            else "other"
            if observed
            else "unresolved"
        )
        outcomes.append({**row, "observed_operations": observed, "outcome": outcome})
    by_language = {
        language: _counts([row for row in outcomes if row["language"] == language])
        for language in sorted(Counter(row["language"] for row in outcomes))
    }
    by_family = {
        family: _counts([row for row in outcomes if row["family"] == family])
        for family in sorted(Counter(row["family"] for row in outcomes))
    }
    overall = _counts(outcomes)
    return {
        "schema": "baxy.situated-cut-b-r215-recogniser-reach-r216.v1",
        "authority": "opened_once_read_only_baseline_not_an_end_to_end_cut_result",
        "identities": {
            "program_sha256": _sha256(Path(__file__)),
            "corpus_sha256": _sha256(corpus_path),
            "preregistration_sha256": _sha256(PREREGISTRATION),
            "aliases_sha256": _sha256(ALIASES),
            "effect_intent_sha256": _sha256(REPO / "src/baxy_mind/effect_intent.py"),
        },
        "population": {
            "rows": len(outcomes),
            "families": len(by_family),
            "languages": {key: value["rows"] for key, value in by_language.items()},
        },
        "recogniser": {
            "available_operations": len(offered),
            "overall": overall,
            "by_language": by_language,
            "by_family": by_family,
            "majority_limit": 0.5,
            "independent_of_recogniser_grammar": overall["reach"] < 0.5,
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
        "next_step": "If recogniser reach is below one half, use the unchanged R215 population to preregister a model-path candidate; otherwise reject this source without editing it.",
    }


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError("r216_is_one_shot_and_already_opened")
    OUTPUT.write_bytes(
        (
            json.dumps(measure(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
    )


if __name__ == "__main__":
    main()
