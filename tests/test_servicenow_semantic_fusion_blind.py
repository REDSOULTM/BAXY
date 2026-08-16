from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR_PATH = (
    ROOT / "experiments/stt_quality/extract_servicenow_codeswitch_blind.py"
)
EVALUATOR_PATH = (
    ROOT / "experiments/stt_quality/evaluate_servicenow_semantic_fusion_blind.py"
)
PREREGISTER_PATH = (
    ROOT / "experiments/stt_quality/preregister_servicenow_semantic_fusion_blind.py"
)


def _load(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


extractor = _load("test_servicenow_blind_extractor", EXTRACTOR_PATH)
evaluator = _load("test_servicenow_blind_evaluator", EVALUATOR_PATH)
preregister = _load("test_servicenow_blind_preregister", PREREGISTER_PATH)


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("send it to 24 Main Street 94105", True),
        ("send it to 24 Main Street", False),
        ("use postal code 94105", False),
        ("send it to 24 Main Street 123", False),
        ("send it to 24 Main Street 1234567", False),
        ("send it to 24 Main Street ABCDE", False),
    ],
)
def test_secondary_selector_requires_address_suffix_and_four_to_six_digits(
    transcript: str, expected: bool
) -> None:
    assert evaluator.needs_secondary_hypothesis(transcript) is expected


def test_extraction_tree_commitment_ignores_target_specific_files(
    tmp_path: Path,
) -> None:
    package = tmp_path / "pyarrow"
    package.mkdir()
    (package / "__init__.py").write_text("__version__ = '25.0.0'\n", encoding="utf-8")
    baseline = extractor.semantic_tree_commitment(tmp_path)

    cache = package / "__pycache__"
    cache.mkdir()
    (cache / "module.cpython-312.pyc").write_bytes(b"machine-specific")
    metadata = tmp_path / "pyarrow-25.0.0.dist-info"
    metadata.mkdir()
    for name in ("RECORD", "REQUESTED", "INSTALLER"):
        (metadata / name).write_text("target-specific\n", encoding="utf-8")

    assert extractor.semantic_tree_commitment(tmp_path) == baseline


@pytest.mark.parametrize(
    ("payload", "suffix"),
    [
        (b"RIFF\x00\x00\x00\x00WAVE", ".wav"),
        (b"fLaCpayload", ".flac"),
        (b"OggSpayload", ".ogg"),
        (b"ID3payload", ".mp3"),
        (bytes((0xFF, 0xE3, 0x00)), ".mp3"),
    ],
)
def test_audio_suffix_is_derived_from_payload(payload: bytes, suffix: str) -> None:
    assert extractor._audio_suffix(payload) == suffix


def test_audio_suffix_rejects_unknown_payload() -> None:
    with pytest.raises(RuntimeError, match="servicenow_blind_audio_format_unknown"):
        extractor._audio_suffix(b"unknown")


def test_blind_population_and_threshold_contract_is_fixed() -> None:
    assert extractor.BLIND_ROW_GROUPS == [0, 1]
    assert extractor.EXPECTED_ROWS_PER_GROUP == [100, 100]
    assert extractor.EXPECTED_BLIND_ROWS == 200
    assert preregister.SOURCE_BYTES == 134_596_508
    assert preregister.SOURCE_SHA256 == (
        "808e373099ae16c80f2bf5434fbb70afd06487ffd3a9c2f88495638dc7e035d8"
    )
    assert preregister.THRESHOLDS == {
        "expectedCases": 200,
        "minimumNonemptyRate": 1.0,
        "maximumCorpusWer": 0.20,
        "maximumEnglishReferenceErrorRate": 0.20,
        "maximumSpanishReferenceErrorRate": 0.20,
        "minimumCriticalAnchorRecall": 0.99,
        "minimumClarificationUtilityRate": 1.0,
        "maximumInitialSignalLatencyP95Seconds": 2.0,
        "maximumSemanticFinalizationLatencyP95Seconds": 2.0,
        "maximumSemanticRealTimeFactorP95": 0.5,
        "maximumPeakRssBytes": 4_294_967_296,
    }


def test_extractor_does_not_read_answer_or_question_columns() -> None:
    source = EXTRACTOR_PATH.read_text(encoding="utf-8")
    assert "questions" not in source
    assert "expectedAnswers" not in source
    assert 'row.get("utterance")' in source
    assert 'row.get("words")' in source
    assert 'row.get("word_languages")' in source


def test_reference_is_accessed_only_after_candidate_output() -> None:
    source = EVALUATOR_PATH.read_text(encoding="utf-8")
    candidate_output = source.index("semantic = fusion.canonicalize_transcript")
    reference_access = source.index('reference = str(case["reference"])')
    assert candidate_output < reference_access
