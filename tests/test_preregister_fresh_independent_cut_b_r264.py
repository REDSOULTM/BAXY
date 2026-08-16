from __future__ import annotations

import ast
import importlib.util
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/preregister_fresh_independent_cut_b_r264.py"


def module():
    spec = importlib.util.spec_from_file_location("r264", SOURCE)
    assert spec and spec.loader
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    return candidate


def test_r264_seals_current_family_and_word_lifecycle_coverage() -> None:
    candidate = module()
    report = candidate.build()
    rows = candidate.build_rows()

    assert report["population"] == {
        "rows": 114,
        "semantic_cases": 38,
        "families": 31,
        "languages": {"es": 38, "en": 38, "spanglish": 38},
        "office_cases": 8,
        "confirmation_bound_cases": 3,
    }
    assert Counter(row["language"] for row in rows) == {
        "es": 38,
        "en": 38,
        "spanglish": 38,
    }
    assert {row["family"] for row in rows} == {
        operation.split(".", 1)[0]
        for operation in candidate.current_catalogue_operations()
    }
    assert all(row["blind_holdout"] for row in rows)
    assert all(not row["execution_authority"] for row in rows)
    assert {
        row["expected_operations"][0]
        for row in rows
        if row["family"] == "office"
    } == {
        "office.document.create",
        "office.document.read",
        "office.word.append",
        "office.word.close",
        "office.word.discard",
        "office.word.save",
        "office.word.start",
        "office.word.status",
    }


def test_r264_generator_is_structurally_independent_before_measurement() -> None:
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
    assert "preregister_independent_cut_b_r213" not in source
    assert "r196_normalised_texts" in names
    candidate = module()
    assert candidate.build()["independence"] == {
        "generator_imports_recogniser": False,
        "generator_imports_alias_catalogue": False,
        "generator_imports_prior_cut_b_builder": False,
        "generator_uses_r196_language": False,
        "generator_uses_current_catalogue_descriptions": False,
        "manual_semantic_specification": True,
    }
