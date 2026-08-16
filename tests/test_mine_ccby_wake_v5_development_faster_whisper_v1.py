from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "mine_ccby_wake_v5_development_faster_whisper_v1.py"
)
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location(
    "mine_ccby_wake_v5_development_faster_whisper_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_select_sources_rejects_consumed_blind_source() -> None:
    spec = {
        "schema": "baxy.ccby-wake-v5-development-sources.v1",
        "scope": "development_only",
        "excluded_consumed_blind_source_ids": list(
            MODULE.CONSUMED_BLIND_SOURCE_IDS
        ),
        "sources": [{"inventory": "round1", "id": "ix-oaNUxFSA"}],
    }
    inventory = {
        "sources": [
            {
                "id": "ix-oaNUxFSA",
                "license": MODULE.ALLOWED_LICENSE,
            }
        ]
    }
    with pytest.raises(ValueError, match="source_boundary_invalid"):
        MODULE.select_sources(spec, {"round1": inventory})


def test_select_sources_requires_ccby_license() -> None:
    spec = {
        "schema": "baxy.ccby-wake-v5-development-sources.v1",
        "scope": "development_only",
        "excluded_consumed_blind_source_ids": list(
            MODULE.CONSUMED_BLIND_SOURCE_IDS
        ),
        "sources": [{"inventory": "round1", "id": "fresh"}],
    }
    inventory = {"sources": [{"id": "fresh", "license": "unknown"}]}
    with pytest.raises(ValueError, match="license_invalid"):
        MODULE.select_sources(spec, {"round1": inventory})


def test_is_lexical_candidate_accepts_product_aliases_only() -> None:
    assert MODULE.is_lexical_candidate("Baxi Ferrol")
    assert MODULE.is_lexical_candidate("Baxiroca")
    assert not MODULE.is_lexical_candidate("Tarang Bakshi")
