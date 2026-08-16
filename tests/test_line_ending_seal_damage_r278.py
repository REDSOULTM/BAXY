"""R278: the line-ending seal audit is read-only and its rule cannot invert."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/audit_line_ending_seal_damage_r278.py"


def _module():
    spec = importlib.util.spec_from_file_location("r278", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r278_reports_a_repaired_tree_with_no_restorable_files_left() -> None:
    result = _module().classify(ROOT)

    # The sweep already ran, so nothing may still be broken by the checkout.
    assert result["restorableCount"] == 0
    assert result["restorable"] == []
    assert result["publishedConstants"] > 0


def test_r278_never_proposes_normalising_a_file_sealed_as_crlf() -> None:
    module = _module()
    result = module.classify(ROOT)
    constants = module.published_constants(ROOT)

    # Every pinned file's on-disk bytes must remain the published identity.
    for relative in result["sealedAsCrlf"]:
        data = (ROOT / relative).read_bytes()
        assert hashlib.sha256(data).hexdigest() in constants
        assert relative not in result["restorable"]


def test_r278_audit_does_not_write_the_files_it_classifies() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    classify = source[source.index("def classify(") : source.index("def main(")]
    assert "write_bytes" not in classify
    assert "write_text" not in classify
    assert "open(" not in classify
