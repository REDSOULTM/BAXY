from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/audit_recogniser_alias_catalogue_drift_r267.py"
ARTIFACT = ROOT / "artifacts/audit/recogniser_alias_catalogue_drift_r267.json"
ALIASES = ROOT / "src/baxy_mind/data/catalog_operation_aliases.v1.json"
CATALOGUE = ROOT / "artifacts/development/current_core_catalog_snapshot_r219.json"


def _module():
    spec = importlib.util.spec_from_file_location("alias_drift_r267", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r267_audit_regenerates_its_published_receipt() -> None:
    module = _module()
    assert module.audit() == json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_r267_binds_aliases_to_current_catalogue_without_word_expansion() -> None:
    result = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert result["verdict"] == (
        "passed_current_catalogue_binding_without_manual_word_grammar_expansion"
    )
    assert result["catalogue_binding"] == {
        "catalogue_operations": 174,
        "catalogue_operation_names_sha256": (
            "23784c0d5e223c368be9e7665067378ad369aa5e934d9c27de5bd5a8dac518ae"
        ),
        "alias_rows": 157,
        "alias_target_operations": 157,
        "all_alias_operations_are_current": True,
        "retired_alias_target_operations": [],
    }
    assert result["unaliased_current_operations"] == {
        "total": 17,
        "intentional_private_memory_operations": [
            "memory.correct",
            "memory.disable",
            "memory.enable",
            "memory.export",
            "memory.forget",
            "memory.list",
            "memory.recall",
            "memory.save",
            "memory.sensitive.save",
            "memory.session.clear",
            "memory.status",
        ],
        "word_lifecycle_operations_without_aliases": [
            "office.word.append",
            "office.word.close",
            "office.word.discard",
            "office.word.save",
            "office.word.start",
            "office.word.status",
        ],
        "manual_word_aliases_added": False,
        "requires_published_human_word_com_lifecycle_source": True,
    }


def test_r267_receipt_hashes_the_program_and_inputs() -> None:
    result = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert result["identities"] == {
        "program_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "alias_asset_sha256": hashlib.sha256(ALIASES.read_bytes()).hexdigest(),
        "r219_catalogue_snapshot_sha256": hashlib.sha256(CATALOGUE.read_bytes()).hexdigest(),
    }


def test_r267_source_cannot_start_the_model_or_dispatch_an_effect() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    for forbidden in (
        "resolve_explicit_effects",
        "LlmRuntime",
        "resolve_runtime",
        "subprocess",
        "discover_core",
    ):
        assert forbidden not in source
