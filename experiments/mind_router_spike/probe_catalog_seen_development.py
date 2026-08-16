"""Run the current-catalogue product probe on all seen catalogue surfaces."""

from __future__ import annotations

from pathlib import Path

import probe_current_catalog_review as probe


REPO = Path(__file__).resolve().parents[2]
probe.CORPUS = REPO / "artifacts/development/catalog_seen_development_r1.jsonl"
probe.MANIFEST = (
    REPO / "artifacts/development/catalog_seen_development_r1.manifest.json"
)
probe.OUTPUT = (
    REPO / "artifacts/development/catalog_seen_product_probe_r3_natural_surface.json"
)
probe.AUDIT = (
    REPO
    / "artifacts/development/catalog_seen_product_probe_r3_natural_surface.raw.jsonl"
)


if __name__ == "__main__":
    raise SystemExit(probe.main())
