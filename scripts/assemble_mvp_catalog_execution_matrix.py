from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = "baxy.mvp-catalog-execution-matrix.v1"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_rows(
    rows: list[dict[str, Any]], key: str, source: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        operation = row.get(key)
        if not isinstance(operation, str) or not operation:
            raise ValueError(f"Missing operation in {source}")
        if operation in result:
            raise ValueError(f"Duplicate operation {operation} in {source}")
        result[operation] = row
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def source_record(path: Path, schema: object) -> dict[str, str]:
    return {
        "path": str(path),
        "schema": str(schema),
        "sha256": sha256(path),
    }


def assemble(
    *,
    routing_path: Path,
    core_path: Path,
    external_path: Path,
    stateful_path: Path,
    transient_path: Path,
    memory_path: Path,
    expected_operations: int,
) -> dict[str, Any]:
    routing = load_json(routing_path)
    core = load_json(core_path)
    external = load_json(external_path)
    stateful = load_json(stateful_path)
    transient = load_json(transient_path)
    memory = load_json(memory_path)

    require(routing.get("routing_gate_passed") is True, "Routing gate is not green")
    for label, evidence in (
        ("core", core),
        ("external", external),
        ("stateful", stateful),
        ("transient", transient),
        ("memory", memory),
    ):
        require(evidence.get("gatePassed") is True, f"{label} gate is not green")

    routing_rows = unique_rows(routing["rows"], "operation", "routing")
    core_rows = unique_rows(core["rows"], "operation", "core")
    external_rows = unique_rows(external["rows"], "operation", "external")
    stateful_rows = unique_rows(stateful["rows"], "Operation", "stateful")
    transient_rows = unique_rows(transient["rows"], "Operation", "transient")
    memory_rows = unique_rows(memory["rows"], "Operation", "memory")

    catalog = set(routing_rows)
    require(
        len(catalog) == expected_operations,
        f"Expected {expected_operations} catalog operations, got {len(catalog)}",
    )
    require(set(core_rows) == catalog, "Core contract set differs from routing catalog")
    require(
        all(row.get("routing_passed") is True for row in routing_rows.values()),
        "At least one routing row failed",
    )
    require(
        all(
            row.get("contract", {}).get("passed") is True
            and row.get("contract", {}).get("effectMayHaveOccurred") is False
            for row in core_rows.values()
        ),
        "At least one Core contract boundary failed",
    )

    readonly_rows = {
        operation: row
        for operation, row in core_rows.items()
        if row.get("readOnlyProvider") is not None
    }
    require(
        all(
            row["readOnlyProvider"].get("passed") is True
            and row["readOnlyProvider"].get("effectMayHaveOccurred") is False
            and (
                (
                    row["readOnlyProvider"].get("status") == "completed"
                    and row["readOnlyProvider"].get("verified") is True
                    and row["readOnlyProvider"].get("errorCode") is None
                )
                or (
                    row["readOnlyProvider"].get("status") == "failed"
                    and row["readOnlyProvider"].get("verified") is False
                    and isinstance(row["readOnlyProvider"].get("errorCode"), str)
                )
            )
            for row in readonly_rows.values()
        ),
        "At least one real read-only provider row failed",
    )
    readonly_success_rows = {
        operation: row
        for operation, row in readonly_rows.items()
        if row["readOnlyProvider"].get("status") == "completed"
        and row["readOnlyProvider"].get("verified") is True
    }
    require(
        all(
            row.get("exactOperationForwarded") is True
            and row.get("verifiedReceiptAccepted") is True
            and row.get("unverifiedReceiptRejected") is True
            and row.get("actualEffectsExecuted") == 0
            for row in external_rows.values()
        ),
        "At least one external provider contract row failed",
    )
    require(
        all(
            row.get("Verified") is True
            and row.get("EffectMayHaveOccurred") is False
            and row.get("ActualUserEffectsExecuted") == 0
            for row in stateful_rows.values()
        ),
        "At least one local stateful row failed",
    )
    require(
        all(
            row.get("Verified") is True
            and row.get("EffectMayHaveOccurred") is False
            and row.get("ActualUserEffectsExecuted") == 0
            for row in transient_rows.values()
        ),
        "At least one local transient row failed",
    )
    require(
        all(
            row.get("Verified") is True
            and row.get("PrivateResultOpened") is True
            and row.get("SecretInPublicOutcome") is False
            and row.get("ActualUserEffectsExecuted") == 0
            for row in memory_rows.values()
        ),
        "At least one private memory row failed",
    )

    sources = {
        "routing": source_record(routing_path, routing.get("schema")),
        "core": source_record(core_path, core.get("schema")),
        "external": source_record(external_path, external.get("schema")),
        "stateful": source_record(stateful_path, stateful.get("schema")),
        "transient": source_record(transient_path, transient.get("schema")),
        "memory": source_record(memory_path, memory.get("schema")),
    }

    output_rows: list[dict[str, Any]] = []
    for operation in sorted(catalog):
        route = routing_rows[operation]
        contract = core_rows[operation]
        if operation in memory_rows:
            evidence = memory_rows[operation]
            source = "memory"
            kind = evidence["EvidenceKind"]
            provider = "LocalMemoryStore + WindowsProtectedPayload"
            verifier = evidence["Verifier"]
        elif operation in stateful_rows:
            evidence = stateful_rows[operation]
            source = "stateful"
            kind = "real_isolated_stateful_provider"
            provider = "current-tree local stateful provider"
            verifier = evidence["Verifier"]
        elif operation in transient_rows:
            evidence = transient_rows[operation]
            source = "transient"
            kind = evidence["EvidenceKind"]
            provider = (
                "WindowsNetworkIpProvider"
                if kind == "real_read_only_provider"
                else "current-tree handler + safe verified provider double"
            )
            verifier = evidence["Verifier"]
        elif operation in readonly_success_rows:
            evidence = readonly_success_rows[operation]["readOnlyProvider"]
            source = "core"
            kind = "real_read_only_provider"
            provider = "current-tree Core real read-only provider"
            verifier = "verified_terminal_from_real_provider"
        elif operation in external_rows:
            evidence = external_rows[operation]
            source = "external"
            kind = "safe_external_contract_simulation"
            provider = evidence["provider"]
            verifier = "verified_receipt_acceptance_and_unverified_rejection"
        else:
            raise ValueError(f"No provider evidence for {operation}")

        simulation = "simulation" in kind
        output_rows.append(
            {
                "operation": operation,
                "family": route["family"],
                "risk": contract["risk"],
                "caseId": route["case_id"],
                "example": {
                    "language": route["language"],
                    "text": route["text"],
                },
                "routing": {
                    "owner": route["routing_owner"],
                    "passed": True,
                    "seconds": route["routing_seconds"],
                },
                "contractBoundaryPassed": True,
                "provider": provider,
                "verifier": verifier,
                "executionEvidenceKind": kind,
                "executionEvidenceSource": source,
                "executionEvidenceSourceSha256": sources[source]["sha256"],
                "providerExecutionPassed": True,
                "independentlyVerified": True,
                "physicalExternalEffectExecuted": False,
                "actualUserEffectsExecuted": 0,
                "status": (
                    "approved_safe_contract_simulation"
                    if simulation
                    else "approved_real_isolated_or_read_only"
                ),
            }
        )

    strength_counts = Counter(row["executionEvidenceKind"] for row in output_rows)
    gaps = [row["operation"] for row in output_rows if not row["providerExecutionPassed"]]
    simulations = sum(
        1 for row in output_rows if "simulation" in row["executionEvidenceKind"]
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(UTC).isoformat(),
        "scope": "all_catalog_operations_routed_and_bound_to_provider_verifier_evidence",
        "status": "approved_current_tree_safe_execution_matrix",
        "actualUserEffectsExecuted": 0,
        "sources": sources,
        "metrics": {
            "catalogOperations": len(output_rows),
            "routingPassed": sum(row["routing"]["passed"] for row in output_rows),
            "contractBoundariesPassed": len(output_rows),
            "providerExecutionEvidencePassed": sum(
                row["providerExecutionPassed"] for row in output_rows
            ),
            "independentlyVerified": sum(
                row["independentlyVerified"] for row in output_rows
            ),
            "realOrIsolatedEvidence": len(output_rows) - simulations,
            "safeContractSimulations": simulations,
            "physicalExternalEffectsExecuted": 0,
            "actualUserEffectsExecuted": 0,
            "gaps": len(gaps),
            "failed": 0,
            "strengthCounts": dict(sorted(strength_counts.items())),
        },
        "policy": {
            "externalEffects": (
                "safe contract simulations; no user effects were produced"
            ),
            "simulationIsExplicit": True,
            "simulationIsNeverReportedAsPhysicalExecution": True,
            "successRequiresIndependentVerification": True,
        },
        "gaps": gaps,
        "rows": output_rows,
        "gatePassed": (
            len(output_rows) == expected_operations
            and not gaps
            and all(row["independentlyVerified"] for row in output_rows)
            and all(row["actualUserEffectsExecuted"] == 0 for row in output_rows)
        ),
    }
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--routing", type=Path, required=True)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--external", type=Path, required=True)
    parser.add_argument("--stateful", type=Path, required=True)
    parser.add_argument("--transient", type=Path, required=True)
    parser.add_argument("--memory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-operations", type=int, default=169)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite evidence: {args.output}")
    report = assemble(
        routing_path=args.routing.resolve(),
        core_path=args.core.resolve(),
        external_path=args.external.resolve(),
        stateful_path=args.stateful.resolve(),
        transient_path=args.transient.resolve(),
        memory_path=args.memory.resolve(),
        expected_operations=args.expected_operations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "operations": report["metrics"]["catalogOperations"],
                "gaps": report["metrics"]["gaps"],
                "gatePassed": report["gatePassed"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["gatePassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
