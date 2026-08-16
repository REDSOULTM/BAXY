"""Measure candidate safety discriminators at the point the turn kind is chosen.

R122 established that the boundary which actually protects the open population
is the turn-kind classification, not the domain veto: across four sealed
veto-reach populations the 42 out-of-catalogue requests that abstained were all
``conversation`` or ``clarify``, and the 2 that leaked an effect were ``action``
and ``plan``. The veto arrives after the decision to act is already made, and it
covers only 99 of 158 operations, so both leaks walked through its gaps.

Before any guard is written, this program measures the candidate discriminators
against **everything already consumed**, including the populations where the
product is green. R117 was rejected precisely because it was derived from the
failing cases and checked only there; the discipline is to check the cost first.

This is a diagnostic over already-opened populations. It executes no operation
and it cannot promote anything: a claim needs a fresh sealed V6.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind import effect_intent  # noqa: E402
from baxy_mind.effect_intent import (  # noqa: E402
    build_application_catalog_index,
    build_game_catalog_index,
    operation_domain_is_grounded,
    resolve_explicit_effects,
    unresolved_compound_contract,
)
from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
    write_json_atomic,
)

DEFAULT_OUTPUT = REPO / "artifacts/development/turn_kind_safety_boundary_20260812.json"

# Every consumed veto-reach seal. V4 was voided and never opened, so it has no
# result file and is deliberately absent.
CONSUMED_SEALS: tuple[tuple[str, Path], ...] = (
    ("v1", REPO / "artifacts/holdout/veto_reach_v1.json"),
    ("v2", REPO / "artifacts/holdout/veto_reach_v2.json"),
    ("v3", REPO / "artifacts/holdout/veto_reach_v3.json"),
    ("v5", REPO / "artifacts/holdout/veto_reach_v5.json"),
)

PHYSICAL_MISSIONS = REPO / "artifacts/product/physical_dependent_missions_text_v1.json"
# The receipt keeps the verified steps but not the spoken surface; the sealed
# preregistration is the authority for what was actually said.
PHYSICAL_MISSIONS_PREREGISTRATION = (
    REPO
    / "artifacts/development/physical_dependent_missions_preregistration_20260811.json"
)


def _catalogue(core: Path | None) -> tuple[tuple[str, ...], Any, Any]:
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(core)
    )
    operations = tuple(
        str(capability["name"]) for capability in capabilities if capability.get("name")
    )
    applications = build_application_catalog_index(
        tuple(
            str(name)
            for name in (application_catalog or {}).get("applications", ())
            if isinstance(name, str)
        )
        if isinstance(application_catalog, dict)
        else ()
    )
    games = build_game_catalog_index(
        tuple(
            (str(entry.get("title", "")), str(entry.get("id", "")), str(entry.get("platform", "")))
            for entry in (game_catalog or {}).get("games", ())
            if isinstance(entry, dict)
        )
        if isinstance(game_catalog, dict)
        else ()
    )
    return operations, applications, games


def _deterministic(
    text: str,
    operations: tuple[str, ...],
    applications: Any,
    games: Any,
) -> dict[str, Any]:
    """Recompute what the deterministic recogniser says about a surface.

    Pure function of text and catalogue, so it is reproducible offline over the
    consumed records without re-opening any seal.
    """

    intent = resolve_explicit_effects(text, operations, applications, games)
    compound = unresolved_compound_contract(
        text,
        operations,
        applications,
        games,
        resolved_intent=intent,
    )
    return {
        "resolved": intent is not None,
        "resolved_operations": list(intent.operations) if intent is not None else [],
        "unresolved_compound": compound is not None,
        "non_action_frame": effect_intent.explicit_non_action_frame(text),
    }


def _domain_verdicts(
    text: str,
    operations: list[str],
    applications: Any,
) -> dict[str, Any]:
    verdicts = {
        operation: operation_domain_is_grounded(text, operation, applications)
        for operation in operations
    }
    return {
        "per_operation": {key: value for key, value in verdicts.items()},
        "any_refused": any(value is False for value in verdicts.values()),
        "any_uncovered": any(value is None for value in verdicts.values()),
    }


def collect(
    operations: tuple[str, ...],
    applications: Any,
    games: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for seal, path in CONSUMED_SEALS:
        if not path.is_file():
            raise FileNotFoundError(f"seal result missing: {path}")
        report = json.loads(path.read_text(encoding="utf-8"))
        for record in report["records"]:
            text = record["request_text"]
            effects = list(record.get("effect_operations") or [])
            row = {
                "population": f"veto_reach_{seal}",
                "case_id": record["case_id"],
                "role": record["role"],
                "request_text": text,
                "kind": record.get("kind"),
                "effect_operations": effects,
                "reply_text": record.get("reply_text") or "",
                "question": record.get("question") or "",
                "mute": not str(record.get("reply_text") or "").strip(),
            }
            row.update(_deterministic(text, operations, applications, games))
            row["domain"] = _domain_verdicts(text, effects, applications)
            rows.append(row)
    return rows


def collect_missions(
    operations: tuple[str, ...],
    applications: Any,
    games: Any,
) -> list[dict[str, Any]]:
    """The legitimate compound actions that any new guard must not break."""

    if not PHYSICAL_MISSIONS.is_file():
        raise FileNotFoundError(f"physical missions result missing: {PHYSICAL_MISSIONS}")
    report = json.loads(PHYSICAL_MISSIONS.read_text(encoding="utf-8"))
    surfaces = {
        entry["id"]: entry["text"]
        for entry in json.loads(
            PHYSICAL_MISSIONS_PREREGISTRATION.read_text(encoding="utf-8")
        )["missions"]
    }
    rows: list[dict[str, Any]] = []
    for mission in report["missions"]:
        text = surfaces[mission["id"]]
        row = {
            "population": "physical_dependent_missions_text",
            "case_id": mission["id"],
            "role": "legitimate_mission",
            "request_text": text,
            "kind": "plan",
            "effect_operations": list(mission.get("expectedOperations") or []),
            "reply_text": "",
            "question": "",
            "mute": True,
            "passed": bool(mission.get("passed")),
        }
        row.update(_deterministic(text, operations, applications, games))
        row["domain"] = _domain_verdicts(text, row["effect_operations"], applications)
        rows.append(row)
    return rows


def _acts(row: dict[str, Any]) -> bool:
    return row["kind"] in {"action", "plan"} or bool(row["effect_operations"])


def summarise(rows: list[dict[str, Any]], missions: list[dict[str, Any]]) -> dict[str, Any]:
    """Cost and reach of each candidate discriminator, on every population."""

    requests = [row for row in rows if row["role"] == "request"]
    legitimate = [
        row
        for row in rows
        if row["role"] in {"control", "catalogue_control"} and _acts(row)
    ] + [row for row in missions if _acts(row)]
    leaks = [row for row in requests if row["effect_operations"]]

    candidates = {
        # Ask for the action path only where the deterministic recogniser
        # resolved. R122 lists this as untested; here is its cost.
        "require_deterministic_resolution": lambda row: not row["resolved"],
        # Muteness alone. R122 predicts this breaks the green missions.
        "mute_effect": lambda row: row["mute"],
        # The conjunction the register proposes measuring.
        "mute_and_not_deterministic": lambda row: row["mute"] and not row["resolved"],
        # The same conjunction, restricted to proposals no curated rule covers.
        "mute_and_not_deterministic_and_uncovered": lambda row: (
            row["mute"] and not row["resolved"] and row["domain"]["any_uncovered"]
        ),
        "uncovered_only": lambda row: row["domain"]["any_uncovered"],
        "not_deterministic_and_uncovered": lambda row: (
            not row["resolved"] and row["domain"]["any_uncovered"]
        ),
    }

    report: dict[str, Any] = {}
    for name, predicate in candidates.items():
        stopped = [row["case_id"] for row in leaks if predicate(row)]
        broken = [
            {
                "population": row["population"],
                "case_id": row["case_id"],
                "operations": row["effect_operations"],
            }
            for row in legitimate
            if predicate(row)
        ]
        report[name] = {
            "leaks_stopped": len(stopped),
            "leaks_total": len(leaks),
            "leaks_stopped_ids": stopped,
            "legitimate_actions_broken": len(broken),
            "legitimate_actions_total": len(legitimate),
            "broken": broken,
        }
    return {
        "rows": len(rows) + len(missions),
        "out_of_catalogue_requests": len(requests),
        "leaks": [
            {
                "population": row["population"],
                "case_id": row["case_id"],
                "request_text": row["request_text"],
                "kind": row["kind"],
                "effect_operations": row["effect_operations"],
                "mute": row["mute"],
                "resolved": row["resolved"],
                "domain": row["domain"],
            }
            for row in leaks
        ],
        "legitimate_actions": len(legitimate),
        "turn_kind_separation": {
            "abstained_kinds": _histogram(
                row["kind"] for row in requests if not row["effect_operations"]
            ),
            "leaked_kinds": _histogram(row["kind"] for row in leaks),
        },
        "candidates": report,
    }


def _histogram(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    operations, applications, games = _catalogue(args.core)
    rows = collect(operations, applications, games)
    missions = collect_missions(operations, applications, games)
    summary = summarise(rows, missions)
    report = {
        "schema": "baxy.turn-kind-safety-boundary.v1",
        "authority": (
            "diagnostic over already-consumed populations; executes nothing and "
            "promotes nothing. A claim requires a fresh sealed V6."
        ),
        "catalogue_operations": len(operations),
        "summary": summary,
        "rows": rows + missions,
    }
    write_json_atomic(args.output, report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
