"""Measure the product sidecar on the reviewed current-catalogue corpus.

This is a development diagnostic, not a blind release oracle.  It sends only
``turn.decide`` and joins the public result with opt-in raw policy telemetry so
failures are attributed to retrieval, decision, or the first authority veto.
No plan is sent to Core and no provider can execute an effect.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from baxy_mind.planner import required_predecessors  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


CORPUS = REPO / "artifacts/development/current_catalog_review_development.v1.jsonl"
MANIFEST = REPO / "artifacts/development/current_catalog_review_development.v1.manifest.json"
OUTPUT = REPO / "artifacts/fixes/current_catalog_review_product_probe_r1.json"
AUDIT = REPO / "artifacts/fixes/current_catalog_review_product_probe_r1.raw.jsonl"
EXPECTED_STAGE_NAMES = (
    "validated_raw",
    "explicit_contract",
    "information_question",
    "domain_grounding",
    "compound_conservation",
    "action_relevance",
    "action_grounding",
    "conversation_presentation",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot take a percentile of an empty population")
    rank = max(0, min(len(ordered) - 1, int(percentile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def _terminal_operations(operations: Iterable[str]) -> tuple[str, ...]:
    ordered = tuple(dict.fromkeys(str(operation) for operation in operations))
    technical = {
        predecessor
        for operation in ordered
        for predecessor in required_predecessors(operation)
        if predecessor in ordered
    }
    return tuple(operation for operation in ordered if operation not in technical)


def _operation_sets(row: dict[str, Any], field: str) -> tuple[tuple[str, ...], ...]:
    return tuple(
        _terminal_operations(str(value) for value in item)
        for item in row[field]
    )


def _matches(operations: Iterable[str], accepted: tuple[tuple[str, ...], ...]) -> bool:
    return _terminal_operations(operations) in accepted


def _is_subset_offered(
    accepted: tuple[tuple[str, ...], ...],
    offered: Iterable[str],
) -> bool:
    offered_set = set(offered)
    return any(set(operation_set) <= offered_set for operation_set in accepted)


def _raw_operations(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, dict):
        return ()
    for field in ("intent_operations", "effect_operations"):
        value = raw.get(field)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return _terminal_operations(value)
    operation = raw.get("operation")
    return (str(operation),) if isinstance(operation, str) and operation else ()


def _no_effect_raw(raw: object) -> bool:
    return (
        isinstance(raw, dict)
        and raw.get("mode") == "conversation"
        and not _raw_operations(raw)
    )


def _first_veto(
    audit: dict[str, Any],
    accepted_effects: tuple[tuple[str, ...], ...],
) -> str | None:
    previous_matches = _matches(_raw_operations(audit.get("raw_decision")), accepted_effects)
    for stage in audit.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        current_matches = _matches(stage.get("effect_operations") or [], accepted_effects)
        if previous_matches and not current_matches:
            return str(stage.get("name"))
        previous_matches = current_matches
    return None


def _load_inputs() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected_rows = manifest.get("review", {}).get("rows")
    reviewed = manifest.get("review", {})
    if (
        manifest.get("blind_holdout") is not False
        or not isinstance(expected_rows, int)
        or expected_rows < 1
        or (
            reviewed.get("all_rows_explicitly_reviewed") is not True
            and reviewed.get("all_rows_derived_from_authenticated_catalog")
            is not True
        )
    ):
        raise RuntimeError("current-catalogue development manifest is invalid")
    if manifest.get("output", {}).get("sha256") != _sha256(CORPUS):
        raise RuntimeError("current-catalogue development corpus identity changed")
    rows = [
        json.loads(line)
        for line in CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != expected_rows or len({row.get("case_id") for row in rows}) != len(rows):
        raise RuntimeError("current-catalogue development corpus shape changed")
    return rows, manifest


def _read_audit(path: Path, expected_ids: set[str]) -> dict[str, dict[str, Any]]:
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        request_id = str(record.get("request_id", ""))
        if request_id in expected_ids:
            grouped[request_id].append(record)
    if set(grouped) != expected_ids:
        raise RuntimeError(
            f"raw turn audit is incomplete: expected={len(expected_ids)} actual={len(grouped)}"
        )
    selected: dict[str, dict[str, Any]] = {}
    for request_id, attempts in grouped.items():
        terminal_records = [
            record
            for record in attempts
            if record.get("phase") in {"final", "recovery"}
            or (record.get("phase") is None and "final" in record)
        ]
        if not terminal_records:
            raise RuntimeError(f"raw turn audit has no terminal record for {request_id}")
        record = dict(terminal_records[-1])
        raw_attempts = [
            attempt for attempt in attempts if attempt.get("phase") == "raw_attempt"
        ]
        if raw_attempts:
            record["candidate_operations"] = raw_attempts[-1].get(
                "candidate_operations", []
            )
            record["raw_decision"] = raw_attempts[-1].get("raw_decision")
        record["attempt_records"] = attempts
        record["raw_attempts"] = len(raw_attempts)
        stages = tuple(
            str(stage.get("name"))
            for stage in record.get("stages") or []
            if isinstance(stage, dict)
        )
        if stages not in {
            EXPECTED_STAGE_NAMES,
            ("explicit_clarification",),
            ("total_recovery",),
        }:
            raise RuntimeError(f"raw turn audit stages are incomplete for {request_id}: {stages}")
        selected[request_id] = record
    return selected


def run(args: argparse.Namespace) -> dict[str, Any]:
    cases, corpus_manifest = _load_inputs()
    if args.audit.exists():
        raise RuntimeError(f"refusing to overwrite raw audit: {args.audit}")
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = {str(item["name"]) for item in capabilities}
    reviewed_names = {
        operation
        for row in cases
        for field in (
            "compatible_terminal_operation_sets",
            "compatible_effect_operation_sets",
        )
        for operation_set in row[field]
        for operation in operation_set
    }
    if not reviewed_names <= catalog_names or len(capabilities) != corpus_manifest["catalog"]["operations"]:
        raise RuntimeError("compiled catalogue no longer covers the reviewed oracle")
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(args.audit.resolve())
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    public_rows: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-current-review",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("sidecar rejected the authenticated catalogue")
        client.request(
            {
                "type": "turn.decide",
                "id": "warm-current-review",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in cases:
            request_id = f"current-review-{case['case_id']}"
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": request_id,
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": case["language"] if case["language"] in {"es", "en"} else "es",
                },
                limits["turn.decide"],
            )
            public_rows.append(
                {
                    "request_id": request_id,
                    "reply": reply,
                    "seconds": round(time.perf_counter() - started, 6),
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-current-review"},
            timeout=limits["shutdown"],
        )

    expected_ids = {str(row["request_id"]) for row in public_rows}
    audits = _read_audit(args.audit, expected_ids)
    evaluated: list[dict[str, Any]] = []
    for case, public in zip(cases, public_rows, strict=True):
        reply = public["reply"]
        audit = audits[public["request_id"]]
        accepted_intents = _operation_sets(case, "compatible_terminal_operation_sets")
        accepted_effects = _operation_sets(case, "compatible_effect_operation_sets")
        final_intents = _terminal_operations(reply.get("intentOperations") or [])
        final_effects = _terminal_operations(reply.get("effectOperations") or [])
        deterministic_bypass = tuple(
            str(stage.get("name")) for stage in audit.get("stages") or []
        ) == ("explicit_clarification",)
        total_recovery = tuple(
            str(stage.get("name")) for stage in audit.get("stages") or []
        ) == ("total_recovery",)
        if case["outcome"] in {"action", "clarify"}:
            retrieval_correct = deterministic_bypass or _is_subset_offered(
                accepted_intents, audit.get("candidate_operations") or []
            )
            raw_decision_correct = deterministic_bypass or _matches(
                _raw_operations(audit.get("raw_decision")), accepted_intents
            )
            intent_correct = _matches(final_intents, accepted_intents)
        else:
            retrieval_correct = True
            raw_decision_correct = _no_effect_raw(audit.get("raw_decision"))
            intent_correct = not final_intents
        if case["outcome"] == "action":
            effect_correct = _matches(final_effects, accepted_effects)
            kind_correct = reply.get("kind") in {"action", "plan"}
        elif case["outcome"] == "clarify":
            effect_correct = not final_effects
            kind_correct = reply.get("kind") == "clarify"
        else:
            effect_correct = not final_effects
            kind_correct = reply.get("kind") in {"conversation", "clarify"}
        unsafe_effect = bool(final_effects) and not effect_correct
        first_veto = (
            _first_veto(audit, accepted_effects)
            if case["outcome"] == "action" and accepted_effects
            else None
        )
        failure_cause = (
            "none"
            if intent_correct and effect_correct and kind_correct
            else "recovery"
            if total_recovery
            else "retrieval"
            if not retrieval_correct
            else "decision"
            if not raw_decision_correct or not intent_correct
            else f"veto:{first_veto or 'unattributed'}"
            if not effect_correct
            else "presentation"
        )
        visible_text = str(reply.get("reply") or reply.get("question") or "").strip()
        evaluated.append(
            {
                **case,
                "seconds": public["seconds"],
                "candidate_operations": audit.get("candidate_operations") or [],
                "raw_decision": audit.get("raw_decision"),
                "raw_attempts": audit.get("raw_attempts", 0),
                "turn_recovery": reply.get("turn_recovery"),
                "failure_code": reply.get("failure_code"),
                "policy_stages": audit.get("stages"),
                "final_kind": reply.get("kind"),
                "final_intent_operations": list(final_intents),
                "final_effect_operations": list(final_effects),
                "visible_text": visible_text,
                "retrieval_correct": retrieval_correct,
                "raw_decision_correct": raw_decision_correct,
                "intent_correct": intent_correct,
                "effect_correct": effect_correct,
                "kind_correct": kind_correct,
                "unsafe_effect": unsafe_effect,
                "first_veto": first_veto,
                "failure_cause": failure_cause,
                "exact_turn_correct": intent_correct and effect_correct and kind_correct,
            }
        )

    latencies = [float(row["seconds"]) for row in evaluated]
    causes = collections.Counter(str(row["failure_cause"]) for row in evaluated)
    outcomes = collections.defaultdict(list)
    for row in evaluated:
        outcomes[str(row["outcome"])].append(row)

    def accuracy(rows: list[dict[str, Any]], field: str) -> float:
        return sum(bool(row[field]) for row in rows) / len(rows) if rows else 0.0

    manifest_after = file_sha256(args.runtime_manifest)
    report = {
        "schema": "baxy.current-catalog-development-product-probe.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_review_not_blind",
        "authority": "turn.decide_only_no_plan_sent_to_core_or_provider",
        "effects_executed": 0,
        "runtime": public_runtime_identity(runtime),
        "runtime_manifest_changed": manifest_before != manifest_after,
        "source": {
            "corpus": str(CORPUS.relative_to(REPO)),
            "corpus_sha256": _sha256(CORPUS),
            "manifest": str(MANIFEST.relative_to(REPO)),
            "raw_audit": str(args.audit.resolve()),
            "raw_audit_sha256": _sha256(args.audit),
            "cases": len(cases),
            "blind_holdout": False,
        },
        "metrics": {
            "exact_turn_accuracy": accuracy(evaluated, "exact_turn_correct"),
            "retrieval_accuracy": accuracy(evaluated, "retrieval_correct"),
            "raw_decision_accuracy": accuracy(evaluated, "raw_decision_correct"),
            "intent_accuracy": accuracy(evaluated, "intent_correct"),
            "effect_accuracy": accuracy(evaluated, "effect_correct"),
            "kind_accuracy": accuracy(evaluated, "kind_correct"),
            "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in evaluated),
            "total_recoveries": sum(
                row["turn_recovery"] is not None for row in evaluated
            ),
            "failure_causes": dict(sorted(causes.items())),
            "turn_decide_seconds_p50": statistics.median(latencies),
            "turn_decide_seconds_p95": _percentile(latencies, 0.95),
            "by_outcome": {
                outcome: {
                    "cases": len(rows),
                    "exact_turn_accuracy": accuracy(rows, "exact_turn_correct"),
                    "unsafe_effects": sum(bool(row["unsafe_effect"]) for row in rows),
                }
                for outcome, rows in sorted(outcomes.items())
            },
        },
        "rows": evaluated,
    }
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--audit", type=Path, default=AUDIT)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
