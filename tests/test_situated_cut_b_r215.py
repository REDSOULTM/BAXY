from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_situated_cut_b_r215.py"


def _module():
    spec = importlib.util.spec_from_file_location("r215", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r215_freezes_situated_three_language_requests() -> None:
    module = _module()
    report = module.build()
    rows = module.build_rows()

    assert report["population"] == {
        "rows": 93,
        "families": 31,
        "languages": {"es": 31, "en": 31, "spanglish": 31},
        "recogniser_majority_limit": 0.5,
    }
    assert all(row["blind_holdout"] for row in rows)
    assert all(not row["execution_authority"] for row in rows)
    assert "effect_intent" not in SOURCE.read_text(encoding="utf-8")
    assert "catalog_operation_aliases" not in SOURCE.read_text(encoding="utf-8")
    assert "preregister_independent_cut_b_r213" not in SOURCE.read_text(
        encoding="utf-8"
    )


def test_r215_published_inputs_match_the_frozen_builder() -> None:
    module = _module()
    corpus = ROOT / "artifacts/holdout/situated_cut_b_r215.jsonl"
    preregistration = (
        ROOT / "artifacts/holdout/situated_cut_b_r215.preregistration.json"
    )
    lines = [
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in module.build_rows()
    ]

    assert corpus.read_text(encoding="utf-8").splitlines() == lines
    assert json.loads(preregistration.read_text(encoding="utf-8")) == module.build()
