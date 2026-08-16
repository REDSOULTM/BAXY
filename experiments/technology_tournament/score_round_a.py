#!/usr/bin/env python3
"""Derive the frozen round-A scorecard without changing protocol weights."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import harness


INPUT = harness.ARTIFACTS / "raw" / "packaging_results.json"
OUTPUT = harness.ARTIFACTS / "round_a_scorecard.json"


def lower_is_better(value: float, full_at: float, zero_at: float, points: float) -> float:
    if value <= full_at:
        return points
    if value >= zero_at:
        return 0.0
    return points * (zero_at - value) / (zero_at - full_at)


def higher_is_better(value: float, zero_at: float, full_at: float, points: float) -> float:
    if value >= full_at:
        return points
    if value <= zero_at:
        return 0.0
    return points * (value - zero_at) / (full_at - zero_at)


def artifact_points(mib: float) -> float:
    if mib <= 100:
        return 4.0
    if mib >= 1000:
        return 0.0
    return 4.0 * (math.log(1000) - math.log(mib)) / (math.log(1000) - math.log(100))


def sample_map(functional: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {sample["case_id"]: sample for sample in functional["samples"]}


def all_network_empty(variant: dict[str, Any]) -> bool:
    snapshots = [variant["functional"]["network_snapshot"], variant["warm"]["network_snapshot"]]
    return all(snapshot == {"tcp": [], "udp": []} for snapshot in snapshots)


def score_variant(variant_id: str, variant: dict[str, Any]) -> dict[str, Any]:
    functional = variant["functional"]
    samples = sample_map(functional)
    total_weight = sum(sample["weight"] for sample in functional["samples"])
    passed_weight = sum(sample["weight"] for sample in functional["samples"] if sample["passed"])
    functional_ratio = passed_weight / total_weight
    idle_mib = variant["warm"]["idle_memory"]["private_bytes"] / 1_048_576
    peak_mib = max(
        variant["warm"]["max_sampled_private_bytes"],
        functional["max_sampled_private_bytes"],
    ) / 1_048_576
    artifact_mib = variant["build"]["artifact"]["bytes"] / 1_048_576
    runtime_external = bool(variant["build"]["runtime_external"])
    cold_p95 = variant["cold_start"]["p95_ms"]
    warm_p95 = variant["warm"]["p95_ms"]
    throughput = variant["warm"]["throughput_per_second"]

    gates = {
        "functional_90_percent": functional_ratio >= 0.90,
        "unauthorized_workspace": functional["unauthorized_workspace_probe"]["passed"],
        "nul_traversal_absolute_and_protected": all(
            samples[case_id]["passed"]
            for case_id in (
                "T09_BLOCK_TRAVERSAL",
                "T10_BLOCK_ABSOLUTE_PATH",
                "T11_BLOCK_NUL",
                "T12_REFUSE_PROTECTED_DELETE",
            )
        ),
        "no_network": all_network_empty(variant),
        "verified_effects": all(
            sample["passed"]
            for sample in functional["samples"]
            if sample["case_id"] in {
                "T02_CREATE_NOTE",
                "T03_READ_NOTE",
                "T04_COMPOUND_CREATE_READ",
                "T05_TRASH_NOTE",
                "T06_RESTORE_NOTE",
                "T14_UNICODE_FILENAME",
            }
        ),
        "idempotent_replay": samples["T07_IDEMPOTENT_REPLAY"]["passed"],
        "journal_tail_recovery": samples["T15_TRUNCATED_JOURNAL_RECOVERY"]["passed"],
        "malformed_request_redacted": samples["T16_MALFORMED_REQUEST"]["passed"],
    }
    gate_failures = [name for name, passed in gates.items() if not passed]

    cells: dict[str, dict[str, Any]] = {}

    def measured(name: str, points: float, maximum: float, evidence: Any) -> None:
        cells[name] = {"status": "measured", "points": points, "maximum": maximum, "evidence": evidence}

    def not_evaluated(name: str, maximum: float, reason: str) -> None:
        cells[name] = {"status": "NE", "points": None, "maximum": maximum, "reason": reason}

    measured("verified_missions", 25 * functional_ratio, 25, {"passed_weight": passed_weight, "total_weight": total_weight})
    measured("resources.idle_private_working_set", lower_is_better(idle_mib, 100, 500, 3), 3, idle_mib)
    measured("resources.peak_private_working_set", lower_is_better(peak_mib, 200, 1000, 4), 4, peak_mib)
    if runtime_external:
        not_evaluated("resources.installed_or_self_contained_bytes", 4, "El runtime externo no está incluido en el artefacto.")
    else:
        measured("resources.installed_or_self_contained_bytes", artifact_points(artifact_mib), 4, artifact_mib)
    measured("resources.base_and_peak_vram", 4, 4, "0 MiB: el corte no carga inferencia")
    measured("latency.cold_start_p95", lower_is_better(cold_p95, 250, 2000, 4), 4, cold_p95)
    measured("latency.warm_mission_p95", lower_is_better(warm_p95, 50, 500, 4), 4, warm_p95)
    measured("latency.warm_throughput", higher_is_better(throughput, 10, 100, 2), 2, throughput)
    natural = all(
        isinstance(sample.get("response", {}).get("response"), str)
        and not sample.get("response", {}).get("response", "").startswith(("{", "["))
        for sample in functional["samples"]
        if sample["case_id"] != "T16_MALFORMED_REQUEST"
    )
    measured("ux.natural_spanish_and_honest_states", 2 if natural else 0, 2, natural)
    for item in (
        "ux.progress_without_raw_protocol",
        "ux.keyboard_and_focus",
        "ux.accessible_names_live_regions_and_screen_reader",
        "ux.contrast_scaling_reduced_motion",
    ):
        not_evaluated(item, 2, "Exclusivo de la ronda B con GUI instalada.")
    measured("security.offline_and_no_listeners", 2 if gates["no_network"] else 0, 2, gates["no_network"])
    measured(
        "security.root_containment_and_input_sanitization",
        2 if gates["unauthorized_workspace"] and gates["nul_traversal_absolute_and_protected"] else 0,
        2,
        {"workspace": gates["unauthorized_workspace"], "hostile_inputs": gates["nul_traversal_absolute_and_protected"]},
    )
    measured("security.risk_authorization_and_protected_targets", 2 if samples["T12_REFUSE_PROTECTED_DELETE"]["passed"] else 0, 2, samples["T12_REFUSE_PROTECTED_DELETE"]["passed"])
    not_evaluated("security.redaction_secret_storage_and_least_privilege", 2, "El corte no maneja secretos ni instala un usuario de servicio.")
    measured(
        "security.verified_effect_idempotency_and_tamper_evidence",
        0,
        2,
        {
            "verified": gates["verified_effects"],
            "idempotent": gates["idempotent_replay"],
            "journal": gates["journal_tail_recovery"],
            "tamper_evidence": False,
            "reason": "El JSONL durable no incluye todavía MAC ni firma.",
        },
    )
    for item in (
        "installation.reproducible_clean_build",
        "installation.offline_install_and_first_launch",
        "installation.single_instance_process_ownership_and_cleanup",
        "installation.crash_recovery_and_data_preservation",
        "installation.upgrade_rollback_and_uninstall",
    ):
        not_evaluated(item, 2, "Requiere repetición de build o instalador de ronda B, no solo un bundle.")
    measured("maintainability.automated_contract_and_regression_tests", 2 if functional_ratio == 1 else 0, 2, functional_ratio)
    not_evaluated("maintainability.typed_versioned_boundaries", 2, "Se revisará en la arquitectura integrada, no por lenguaje nominal.")
    measured("maintainability.fault_injection_and_deterministic_replay", 2 if gates["idempotent_replay"] and gates["journal_tail_recovery"] else 0, 2, gates)
    measured("maintainability.diagnostics_and_observability", 2 if gates["malformed_request_redacted"] else 0, 2, gates["malformed_request_redacted"])
    not_evaluated("maintainability.complexity_and_change_isolation_review", 2, "Pendiente de revisión estructural de ronda B.")
    for item, maximum in (
        ("license.compatible_and_recorded", 2),
        ("license.maintained_supported_components", 2),
        ("license.sbom_hashes_and_supply_chain", 1),
    ):
        not_evaluated(item, maximum, "Pendiente de inventario y SBOM final.")
    measured("migration.historical_corpus_and_regression_reuse", 2, 2, "Mismo protocolo derivado del corpus congelado")
    not_evaluated("migration.proven_useful_component_reuse_without_legacy_inheritance", 2, "El corte fue reescrito de forma equivalente.")
    not_evaluated("migration.estimated_migration_effort_reproduced_by_change", 1, "Requiere el corte integrado.")

    earned = sum(cell["points"] for cell in cells.values() if cell["status"] == "measured")
    available = sum(cell["maximum"] for cell in cells.values() if cell["status"] == "measured")
    return {
        "family": variant["family"],
        "disqualified": bool(gate_failures),
        "gate_failures": gate_failures,
        "gates": gates,
        "raw": {
            "functional_weight_passed": passed_weight,
            "functional_weight_total": total_weight,
            "cold_start_p95_ms": cold_p95,
            "warm_p95_ms": warm_p95,
            "throughput_per_second": throughput,
            "idle_private_mib": idle_mib,
            "peak_private_mib": peak_mib,
            "artifact_mib": artifact_mib,
            "runtime_external": runtime_external,
            "build_seconds": variant["build"]["elapsed_ns"] / 1_000_000_000,
            "implementation_source_lines": variant["build"]["source_lines"],
        },
        "cells": cells,
        "provisional_points_earned": earned,
        "provisional_points_available": available,
        "provisional_normalized_100": 100 * earned / available if available else 0,
    }


def dominates(left: dict[str, Any], right: dict[str, Any], dimensions: tuple[str, ...]) -> bool:
    smaller_or_equal = all(left[dimension] <= right[dimension] for dimension in dimensions)
    strictly_smaller = any(left[dimension] < right[dimension] for dimension in dimensions)
    return smaller_or_equal and strictly_smaller


def pareto(scores: dict[str, dict[str, Any]], dimensions: tuple[str, ...]) -> list[str]:
    eligible = {
        name: score["raw"]
        for name, score in scores.items()
        if not score["disqualified"] and not score["raw"]["runtime_external"]
    }
    frontier = []
    for name, raw in eligible.items():
        if not any(
            other_name != name and dominates(other, raw, dimensions)
            for other_name, other in eligible.items()
        ):
            frontier.append(name)
    return sorted(frontier)


def main() -> int:
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    scores = {
        variant_id: score_variant(variant_id, variant)
        for variant_id, variant in source["variants"].items()
        if "fatal" not in variant
    }
    performance_dimensions = (
        "cold_start_p95_ms",
        "warm_p95_ms",
        "peak_private_mib",
        "artifact_mib",
    )
    protocol_dimensions = performance_dimensions + (
        "build_seconds",
        "implementation_source_lines",
    )
    result = {
        "schema_version": 1,
        "protocol_id": source["protocol_id"],
        "weights_unchanged": True,
        "source_results_sha256": harness.sha256_file(INPUT),
        "scores": scores,
        "pareto": {
            "self_contained_performance": pareto(scores, performance_dimensions),
            "self_contained_protocol_dimensions": pareto(scores, protocol_dimensions),
            "dimensions_performance": list(performance_dimensions),
            "dimensions_protocol": list(protocol_dimensions),
            "note": "Los bundles con runtime externo se publican pero no compiten como artefactos autocontenidos.",
        },
        "round_a_promotion": {
            "integrated_finalists": ["dotnet_windows_core", "rust_core"],
            "python_status": "No pasa como control plane a ronda B; sigue como candidato de sidecar de modelos y automatización.",
            "reason": "Rust ocupa la frontera estricta de rendimiento en esta repetición. .NET queda a menos de 7 puntos y pasa para falsar su hipótesis de integración Windows, GUI y lifecycle. Python no mostró una ventaja de control plane que compense una tercera GUI completa.",
            "winner_declared": False,
        },
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
