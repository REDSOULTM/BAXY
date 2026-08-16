from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_r16_sapi_voice_transcript_corpus_v2.py"
)
SPEC = importlib.util.spec_from_file_location("build_r16_sapi_voice_transcript_v2", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def source_row() -> dict[str, object]:
    return {
        "schema": MODULE.SOURCE_SCHEMA,
        "case_id": "case-1",
        "case_type": "single_action",
        "language": "en",
        "outcome": "action",
        "text": "Please: list tabs",
        "blind_holdout": True,
        "execution_authority": False,
        "compatible_effect_operation_sets": [["browser.tabs.list"]],
    }


def test_derive_rows_binds_transcript_without_execution_authority() -> None:
    report = {
        "rows": [
            {
                "caseId": "case-1",
                "caseType": "single_action",
                "language": "en",
                "outcome": "action",
                "transcript": "Please. List tabs.",
                "vadSegmented": True,
            }
        ]
    }

    rows = MODULE.derive_rows([source_row()], report)

    assert len(rows) == 1
    assert rows[0]["schema"] == MODULE.OUTPUT_SCHEMA
    assert rows[0]["text"] == "Please. List tabs."
    assert rows[0]["blind_holdout"] is False
    assert rows[0]["execution_authority"] is False
    assert rows[0]["compatible_effect_operation_sets"] == [
        ["browser.tabs.list"]
    ]
    assert rows[0]["voice_reference_text_sha256"]


def test_derive_rows_rejects_unsegmented_or_mismatched_evidence() -> None:
    voice = {
        "caseId": "case-1",
        "caseType": "single_action",
        "language": "en",
        "outcome": "action",
        "transcript": "list tabs",
        "vadSegmented": False,
    }
    with pytest.raises(ValueError, match="voice_transcript_vad_invalid"):
        MODULE.derive_rows([source_row()], {"rows": [voice]})

    voice["vadSegmented"] = True
    voice["language"] = "es"
    with pytest.raises(ValueError, match="voice_transcript_binding_invalid"):
        MODULE.derive_rows([source_row()], {"rows": [voice]})
