from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_independent_cut_b_r213.py"


def _module():
    spec = importlib.util.spec_from_file_location("r213", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r213_freezes_a_three_language_independent_cut_b() -> None:
    module = _module()
    report = module.build()
    rows = module.build_rows()

    assert report["population"] == {
        "rows": 93,
        "families": 31,
        "languages": {"es": 31, "en": 31, "spanglish": 31},
        "recogniser_majority_limit": 0.5,
    }
    assert len({row["text"] for row in rows}) == 93
    assert all(row["blind_holdout"] for row in rows)
    assert all(not row["execution_authority"] for row in rows)
    assert report["constraints"] == {
        "generator_imports_recogniser": False,
        "generator_imports_alias_catalogue": False,
        "prior_cut_b_builder_imported": False,
        "recogniser_measured": False,
        "model_started": False,
        "providers_enabled": False,
        "effects_executed": 0,
        "opened_v9": False,
        "voice_stt_wake_exercised": False,
    }


def test_r213_generation_has_no_recogniser_or_alias_dependency() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    build_rows = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_rows"
    )
    names = {node.id for node in ast.walk(build_rows) if isinstance(node, ast.Name)}

    assert "effect_intent" not in source
    assert "catalog_operation_aliases" not in source
    assert "build_independent_cut_b_oracle_r146" not in source
    assert "_prior_normalised_texts" in names


def test_r213_published_inputs_match_the_frozen_builder() -> None:
    module = _module()
    corpus = ROOT / "artifacts/holdout/independent_cut_b_r213.jsonl"
    preregistration = (
        ROOT / "artifacts/holdout/independent_cut_b_r213.preregistration.json"
    )
    expected_lines = [
        json.dumps(row, ensure_ascii=False, sort_keys=True)
        for row in module.build_rows()
    ]

    assert corpus.read_text(encoding="utf-8").splitlines() == expected_lines
    assert json.loads(preregistration.read_text(encoding="utf-8")) == module.build()
