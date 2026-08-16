"""Probe Mind-owned natural seen scenarios without dispatching operations."""

from __future__ import annotations

from pathlib import Path

import probe_current_catalog_review as probe


REPO = Path(__file__).resolve().parents[2]
probe.CORPUS = REPO / "artifacts/development/catalog_seen_scenarios_r1.jsonl"
probe.MANIFEST = (
    REPO / "artifacts/development/catalog_seen_scenarios_r1.manifest.json"
)
probe.OUTPUT = (
    REPO
    / "artifacts/development/catalog_seen_scenarios_probe_r5_operation_ranker5.json"
)
probe.AUDIT = (
    REPO
    / "artifacts/development/catalog_seen_scenarios_probe_r5_operation_ranker5.raw.jsonl"
)

_ProductJsonLineProcess = probe.JsonLineProcess


class _ExperimentJsonLineProcess(_ProductJsonLineProcess):
    def __init__(self, command, *, environment, cwd):
        experiment_command = [*command]
        experiment_command[-1] = (
            "experiments.mind_router_spike.operation_ranker_candidate_mind_entrypoint"
        )
        super().__init__(experiment_command, environment=environment, cwd=cwd)


probe.JsonLineProcess = _ExperimentJsonLineProcess

_base_load_inputs = probe._load_inputs


def _load_mind_owned_inputs():
    rows, manifest = _base_load_inputs()
    return [row for row in rows if row.get("owner") == "mind_sidecar"], manifest


probe._load_inputs = _load_mind_owned_inputs


if __name__ == "__main__":
    raise SystemExit(probe.main())
