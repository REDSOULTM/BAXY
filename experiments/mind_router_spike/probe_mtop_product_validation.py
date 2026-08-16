"""Measure the real product on hash-bound MTOP development validation.

This runner never opens MTOP test and never dispatches an operation.  It sends
only ``catalog.configure`` and ``turn.decide`` to the production mind sidecar.
MTOP contract projections describe complete planner skeletons; for this turn
boundary, technical predecessors are removed so the oracle names only the
terminal user-requested effect.  The planner remains responsible for adding
authenticated predecessors after the turn decision.
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
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
for path in (REPO, SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
from baxy_mind.planner import required_predecessors  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    RamSampler,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    tree_ram_mib,
    write_json_atomic,
)


DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "mtop_product_validation_development.json"
)
SEED = "baxy-mtop-product-validation-v1"


def _percentile(values: Iterable[float], probability: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = round((len(ordered) - 1) * probability)
    return round(ordered[index], 6)


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def terminal_user_operations(operations: Iterable[str]) -> tuple[str, ...]:
    """Remove technical producers already implied by another selected leaf."""

    ordered = tuple(dict.fromkeys(operations))
    technical = {
        predecessor
        for operation in ordered
        for predecessor in required_predecessors(operation)
        if predecessor in ordered
    }
    return tuple(operation for operation in ordered if operation not in technical)


def expected_turn(row: dict[str, Any]) -> dict[str, Any]:
    projection = row["projection"]
    disposition = str(projection["disposition"])
    operations = terminal_user_operations(projection["candidate_operations"])
    if disposition == "candidate":
        kinds = ["action", "plan"] if len(operations) == 1 else ["plan"]
        effects = operations
    elif disposition == "candidate_missing_information":
        kinds = ["clarify"]
        effects = ()
    else:
        kinds = ["conversation"]
        operations = ()
        effects = ()
    return {
        "kinds": kinds,
        "intent_operations": list(operations),
        "effect_operations": list(effects),
    }


def _row_signature(row: dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    projection = row["projection"]
    return (
        str(projection["disposition"]),
        str(projection["reason"]),
        terminal_user_operations(projection["candidate_operations"]),
    )


def select_validation_rows(
    rows: Iterable[dict[str, Any]],
    *,
    groups_per_stratum: int,
) -> list[dict[str, Any]]:
    """Select whole parallel-language mission groups, balanced by contract."""

    if groups_per_stratum < 1:
        raise ValueError("groups_per_stratum must be positive")
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        if (
            row["split"] == "validation"
            and row["projection"]["reason"]
            not in mtop.QUARANTINED_PROJECTION_REASONS
        ):
            groups[str(row["mission_id"])].append(row)
    strata: dict[tuple[str, str, tuple[str, ...]], list[str]] = (
        collections.defaultdict(list)
    )
    for mission_id, group in groups.items():
        signatures = {_row_signature(row) for row in group}
        if len(signatures) != 1:
            # A few upstream parallel translations differ in slot completeness.
            # They cannot be split without leaking one language variant across
            # the mission boundary, so quarantine the complete group.
            continue
        strata[next(iter(signatures))].append(mission_id)

    selected_ids: set[str] = set()
    for signature, mission_ids in sorted(strata.items()):
        ranked = sorted(
            mission_ids,
            key=lambda mission_id: (
                hashlib.sha256(
                    (
                        SEED
                        + "\0"
                        + repr(signature)
                        + "\0"
                        + mission_id
                    ).encode("utf-8")
                ).digest(),
                mission_id,
            ),
        )
        selected_ids.update(ranked[:groups_per_stratum])
    return sorted(
        (
            dict(row)
            for mission_id in selected_ids
            for row in groups[mission_id]
        ),
        key=lambda row: (str(row["mission_id"]), str(row["locale"])),
    )


def assess(expected: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    observed_intent = list(reply.get("intentOperations") or [])
    observed_effect = list(reply.get("effectOperations") or [])
    observed_kind = reply.get("kind")
    intent_exact = observed_intent == expected["intent_operations"]
    effect_exact = observed_effect == expected["effect_operations"]
    kind_exact = observed_kind in expected["kinds"]
    contract_ok = reply.get("type") == "turn.result"
    return {
        "exact": contract_ok and intent_exact and effect_exact and kind_exact,
        "contract_ok": contract_ok,
        "intent_exact": intent_exact,
        "effect_exact": effect_exact,
        "kind_exact": kind_exact,
        "observed_kind": observed_kind,
        "observed_intent_operations": observed_intent,
        "observed_effect_operations": observed_effect,
    }


def _summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(samples)
    latencies = [float(sample["seconds"]) for sample in samples]
    exact = sum(bool(sample["assessment"]["exact"]) for sample in samples)
    intent = sum(
        bool(sample["assessment"]["intent_exact"]) for sample in samples
    )
    effect = sum(
        bool(sample["assessment"]["effect_exact"]) for sample in samples
    )
    kind = sum(bool(sample["assessment"]["kind_exact"]) for sample in samples)
    return {
        "cases": total,
        "exact": exact,
        "exact_accuracy": round(exact / total, 6),
        "intent_exact": intent,
        "intent_exact_accuracy": round(intent / total, 6),
        "effect_exact": effect,
        "effect_exact_accuracy": round(effect / total, 6),
        "kind_exact": kind,
        "kind_exact_accuracy": round(kind / total, 6),
        "latency_seconds": {
            "mean": round(statistics.fmean(latencies), 6),
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "maximum": round(max(latencies), 6),
        },
    }


def run(
    *,
    output: Path,
    groups_per_stratum: int,
    mind_module: str = "baxy_mind",
    audit: Path | None = None,
) -> dict[str, Any]:
    rows, manifest, identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    selected = select_validation_rows(
        rows,
        groups_per_stratum=groups_per_stratum,
    )
    if not selected:
        raise ValueError("the MTOP validation sample is empty")

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    catalog_names = {str(capability.get("name") or "") for capability in capabilities}
    expected_operations = {
        operation
        for row in selected
        for operation in expected_turn(row)["intent_operations"]
    }
    missing = sorted(expected_operations - catalog_names)
    if missing:
        raise ValueError(f"MTOP references absent catalog operations: {missing}")

    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    if audit is not None:
        if audit.exists():
            raise RuntimeError(f"refusing to append to existing audit: {audit}")
        environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(audit.resolve())
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", mind_module],
        environment=environment,
        cwd=REPO,
    )
    measured: list[dict[str, Any]] = []
    process_memory_mib: dict[str, float | None] = {}
    ram_sampler = RamSampler(client.pid)
    ram_sampler.start()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("mind sidecar did not publish hello")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "mtop-product-validation-catalog",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready" or ready.get("count") != len(
            capabilities
        ):
            raise RuntimeError("mind sidecar rejected the authenticated catalog")
        client.request(
            {
                "type": "turn.decide",
                "id": "mtop-product-validation-warmup",
                "text": "hola, responde brevemente",
                "history": [],
            },
            limits["turn.decide"],
        )
        process_memory_mib["after_warmup"] = tree_ram_mib(client.pid)
        for index, row in enumerate(selected):
            expected = expected_turn(row)
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": f"mtop-validation-{index}",
                    "text": row["text"],
                    "history": [],
                },
                limits["turn.decide"],
            )
            measured.append(
                {
                    "source_id": row["source_id"],
                    "mission_id": row["mission_id"],
                    "locale": row["locale"],
                    "text": row["text"],
                    "semantic": row["semantic"],
                    "projection": row["projection"],
                    "expected": expected,
                    "seconds": round(time.perf_counter() - started, 6),
                    "assessment": assess(expected, reply),
                }
            )
    finally:
        process_memory_mib["before_shutdown"] = tree_ram_mib(client.pid)
        ram_sampler.stop()
        process_memory_mib["peak"] = ram_sampler.peak_mib
        client.close(
            graceful_message={
                "type": "shutdown",
                "id": "mtop-product-validation-shutdown",
            },
            timeout=limits["shutdown"],
        )

    mtop._assert_input_identity_stable(identity)
    summary = _summary(measured)
    by_locale = {
        locale: _summary([row for row in measured if row["locale"] == locale])
        for locale in sorted({str(row["locale"]) for row in measured})
    }
    by_disposition = {
        disposition: _summary(
            [
                row
                for row in measured
                if row["projection"]["disposition"] == disposition
            ]
        )
        for disposition in sorted(
            {str(row["projection"]["disposition"]) for row in measured}
        )
    }
    report = {
        "schema": "baxy.mtop-product-validation-development.v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "scope": "development_validation_only_mtop_test_remains_sealed",
        "side_effect_free": True,
        "source": {
            "corpus_sha256": identity.corpus.sha256,
            "manifest_sha256": identity.manifest.sha256,
            "map_sha256": manifest["source"]["map_sha256"],
            "groups_per_stratum": groups_per_stratum,
            "selected_rows": len(selected),
            "selected_missions": len({row["mission_id"] for row in selected}),
            "selected_identity_sha256": _canonical_sha256(
                [row["source_id"] for row in selected]
            ),
            "test_content_read": False,
            "mind_module": mind_module,
            "turn_audit_enabled": audit is not None,
        },
        "runtime": public_runtime_identity(runtime),
        "process_tree_rss_mib": {
            key: round(value, 3) if value is not None else None
            for key, value in process_memory_mib.items()
        },
        "summary": summary,
        "by_locale": by_locale,
        "by_disposition": by_disposition,
        "failures": [row for row in measured if not row["assessment"]["exact"]],
        "samples": measured,
        "status": "passed" if summary["exact_accuracy"] >= 0.99 else "failed",
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--groups-per-stratum", type=int, default=8)
    parser.add_argument("--mind-module", default="baxy_mind")
    parser.add_argument("--audit", type=Path)
    args = parser.parse_args()
    report = run(
        output=args.output,
        groups_per_stratum=args.groups_per_stratum,
        mind_module=args.mind_module,
        audit=args.audit,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                **report["summary"],
                "failures": len(report["failures"]),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
