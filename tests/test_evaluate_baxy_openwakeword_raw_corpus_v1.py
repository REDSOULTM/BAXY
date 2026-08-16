from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_openwakeword_raw_corpus_v1.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_openwakeword_raw_corpus_v1", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def manifest() -> dict[str, object]:
    return {
        "schema": MODULE._EXTRACTOR.PHYSICAL_SCHEMA,
        "blindHumanPartitionAccessed": False,
        "developmentOnly": True,
        "physicalPath": {"captureTransport": "wasapi_raw_iaudioclient2"},
        "counts": {"positive": 1, "negative": 1},
        "records": [
            {
                "recordId": "positive/1",
                "output": "p.wav",
                "outputSha256": "a",
                "sourceSha256": "b",
            },
            {
                "recordId": "negative/1",
                "output": "n.wav",
                "outputSha256": "c",
                "sourceSha256": "d",
            },
        ],
    }


def test_controlled_records_normalize_labels() -> None:
    records = MODULE.controlled_records(manifest())
    assert [record["label"] for record in records] == [
        "positive",
        "adversarial_negative",
    ]


def test_controlled_records_reject_count_drift() -> None:
    value = manifest()
    value["counts"] = {"positive": 2, "negative": 0}
    with pytest.raises(ValueError, match="counts_invalid"):
        MODULE.controlled_records(value)


def test_classifier_argument_requires_name_and_path() -> None:
    name, path = MODULE.parse_classifier("lstm=model.onnx")
    assert name == "lstm"
    assert path == Path("model.onnx")
    with pytest.raises(Exception):
        MODULE.parse_classifier("model.onnx")
