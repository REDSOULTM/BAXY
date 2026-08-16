"""Replay the opened R22 Mind surface after systemic fixes, without effects."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import probe_current_catalog_review as probe  # noqa: E402
from scripts import build_catalog_surface_holdout_r22 as campaign  # noqa: E402


probe.CORPUS = campaign.OUTPUT
probe.MANIFEST = campaign.PREREGISTRATION
probe.OUTPUT = (
    REPO / "artifacts/development/catalog_surface_r22_replay_after_social_fix.v1.json"
)
probe.AUDIT = (
    REPO
    / "artifacts/development/catalog_surface_r22_replay_after_social_fix.v1.raw.jsonl"
)


def _load_mind_inputs():
    preregistration = json.loads(campaign.PREREGISTRATION.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in campaign.OUTPUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    mind_rows = [row for row in rows if row.get("owner") == "mind_sidecar"]
    manifest = {
        "blind_holdout": False,
        "catalog": preregistration["catalog"],
        "review": {
            "rows": len(mind_rows),
            "all_rows_explicitly_reviewed": True,
            "all_rows_derived_from_authenticated_catalog": False,
        },
        "output": {"sha256": probe._sha256(campaign.OUTPUT)},
    }
    return mind_rows, manifest


probe._load_inputs = _load_mind_inputs


if __name__ == "__main__":
    raise SystemExit(probe.main())
