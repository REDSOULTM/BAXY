from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_r211_inventories_catalog_without_authorizing_a_gate() -> None:
    spec = importlib.util.spec_from_file_location("r211", ROOT / "experiments/mind_router_spike/audit_catalog_structural_signal_r211.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.build()
    assert report["counts"]["operations"] == 169
    assert report["counts"]["families"] == 31
    assert report["counts"]["operations_without_required_fields"] > 0
    assert report["conclusion"]["runtime_change_authorized"] is False
    assert report["conclusion"]["lexical_gate_authorized"] is False
