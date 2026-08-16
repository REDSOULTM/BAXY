from __future__ import annotations

import ast
import importlib.util
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_independent_clarification_cut_b_r270.py"
CORPUS = ROOT / "artifacts/development/independent_clarification_cut_b_r270.jsonl"
PREREGISTRATION = (
    ROOT / "artifacts/development/independent_clarification_cut_b_r270.preregistration.json"
)


def _module():
    spec = importlib.util.spec_from_file_location("r270", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r270_seals_three_language_clarification_coverage() -> None:
    candidate = _module()
    report = candidate.build()
    rows = candidate.build_rows()

    assert report["population"] == {
        "rows": 93,
        "semantic_cases": 31,
        "families": 31,
        "languages": {"es": 31, "en": 31, "spanglish": 31},
        "expected_turn_kind": "clarify",
        "expected_effect_operations": 0,
    }
    assert Counter(row["language"] for row in rows) == {
        "es": 31,
        "en": 31,
        "spanglish": 31,
    }
    assert {row["family"] for row in rows} == {
        operation.split(".", 1)[0]
        for operation in candidate.current_catalogue_operations()
    }
    assert all(row["expected_turn_kind"] == "clarify" for row in rows)
    assert all(row["expected_effect_operations"] == [] for row in rows)
    assert all(row["missing_facts"] for row in rows)
    assert all(row["blind_holdout"] for row in rows)
    assert all(not row["execution_authority"] for row in rows)


def test_r270_generator_is_independent_before_measurement() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    build_rows = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_rows"
    )
    names = {node.id for node in ast.walk(build_rows) if isinstance(node, ast.Name)}

    for forbidden in (
        "effect_intent",
        "catalog_operation_aliases",
        "preregister_fresh_independent_cut_b_r264",
        "resolve_runtime",
        "LlmRuntime",
    ):
        assert forbidden not in source
    assert "_normalised_texts" in names
    assert _module().build()["independence"] == {
        "generator_imports_recogniser": False,
        "generator_imports_alias_catalogue": False,
        "generator_imports_prior_cut_b_builder": False,
        "generator_uses_r196_or_r264_language": False,
        "generator_uses_current_catalogue_descriptions": False,
        "manual_contract_missing_fact_specification": True,
    }


def test_r270_published_corpus_and_preregistration_match_the_sealed_builder() -> None:
    candidate = _module()

    assert CORPUS.read_bytes() == candidate.corpus_bytes(candidate.build_rows())
    assert json.loads(PREREGISTRATION.read_text(encoding="utf-8")) == candidate.build()
