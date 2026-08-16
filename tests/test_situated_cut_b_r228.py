from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_situated_cut_b_r228.py"
PREREGISTRATION_SEAL = (
    "3c0a5c852fce87c3f9995cf9f1758c53bb357a28f37d1128fd4ab268495ec1f2"
)


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
    # The corpus above still regenerates exactly. The preregistration also
    # records `catalog_sha256`, and the live catalogue has moved since it was
    # sealed, so it is audited by its seal (§7).
    assert_sealed(manifest, PREREGISTRATION_SEAL)
