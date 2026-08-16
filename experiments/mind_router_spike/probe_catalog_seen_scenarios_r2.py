"""Probe dependency-complete seen catalogue aliases without dispatching effects."""

from __future__ import annotations

from pathlib import Path

import probe_current_catalog_review as probe


REPO = Path(__file__).resolve().parents[2]
probe.CORPUS = (
    REPO
    / "artifacts/development/catalog_seen_scenarios_r2_dependency_complete.jsonl"
)
probe.MANIFEST = (
    REPO
    / "artifacts/development/catalog_seen_scenarios_r2_dependency_complete.manifest.json"
)
probe.OUTPUT = (
    REPO / "artifacts/development/catalog_seen_scenarios_probe_r8_authenticated_game.json"
)
probe.AUDIT = (
    REPO
    / "artifacts/development/catalog_seen_scenarios_probe_r8_authenticated_game.raw.jsonl"
)


_base_load_inputs = probe._load_inputs


def _load_mind_owned_inputs():
    rows, manifest = _base_load_inputs()
    return [row for row in rows if row.get("owner") == "mind_sidecar"], manifest


probe._load_inputs = _load_mind_owned_inputs


if __name__ == "__main__":
    raise SystemExit(probe.main())
