from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_situated_cut_b_r228.py"


def _module():
    spec = importlib.util.spec_from_file_location("r228", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r228_freezes_manual_three_language_population() -> None:
    module = _module()
    report = module.build()
    assert report["population"]["rows"] == 93
    assert "effect_intent" not in SOURCE.read_text(encoding="utf-8")
    assert "catalog_operation_aliases" not in SOURCE.read_text(encoding="utf-8")
    assert "preregister_situated_cut_b_r215" not in SOURCE.read_text(encoding="utf-8")


def test_r228_published_inputs_match_builder() -> None:
    module = _module()
    corpus = ROOT / "artifacts/holdout/situated_cut_b_r228.jsonl"
    manifest = ROOT / "artifacts/holdout/situated_cut_b_r228.preregistration.json"
    assert corpus.read_text(encoding="utf-8").splitlines() == [
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in module.build_rows()
    ]
    assert json.loads(manifest.read_text(encoding="utf-8")) == module.build()
