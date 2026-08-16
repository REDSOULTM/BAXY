from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "audit_ccby_wake_development_parakeet.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audit_ccby_wake_development_parakeet", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_development_records_never_returns_blind_entries() -> None:
    records = MODULE.development_records(
        {
            "schema": "baxy.ccby-wake-holdout-corpus.v1",
            "records": [
                {"partition": "development", "label": "positive"},
                {"partition": "blind", "label": "positive"},
            ],
        }
    )

    assert records == [{"partition": "development", "label": "positive"}]


def test_development_records_rejects_unknown_label() -> None:
    with pytest.raises(ValueError, match="ccby_development_label_invalid"):
        MODULE.development_records(
            {
                "schema": "baxy.ccby-wake-holdout-corpus.v1",
                "records": [
                    {"partition": "development", "label": "unknown"},
                ],
            }
        )

