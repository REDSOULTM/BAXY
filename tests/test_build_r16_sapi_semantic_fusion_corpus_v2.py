from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "voice_latency"
sys.path.insert(0, str(SCRIPT))

import build_r16_sapi_semantic_fusion_corpus_v2 as builder  # noqa: E402


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_build_uses_authenticated_catalog_not_evaluation_labels(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(builder, "EXPECTED_ROWS", 2)
    common = {
        "execution_authority": False,
        "voice_reference_text_sha256": "a" * 64,
        "compatible_effect_operation_sets": [["message.send"]],
    }
    parakeet = [
        {**common, "case_id": "one", "text": "show the text ready to paste"},
        {**common, "case_id": "two", "text": "send a message"},
    ]
    whisper = [
        {**common, "case_id": "one", "text": "keywords ready to paste"},
        {**common, "case_id": "two", "text": "ordinary conversation"},
    ]
    parakeet_path = tmp_path / "parakeet.jsonl"
    whisper_path = tmp_path / "whisper.jsonl"
    output_path = tmp_path / "output.jsonl"
    report_path = tmp_path / "report.json"
    _write(parakeet_path, parakeet)
    _write(whisper_path, whisper)

    report = builder.build(
        parakeet_path=parakeet_path,
        whisper_path=whisper_path,
        output_path=output_path,
        report_path=report_path,
        available_operations=frozenset({"clipboard.read.text"}),
        application_names=(),
        game_catalog=(),
        catalog_identities={"operations": 1},
    )

    rows = builder.read_jsonl(output_path)
    assert rows[0]["transcript_authority"] == "parakeet"
    assert rows[1]["transcript_authority"] == "whisper"
    assert rows[1]["transcript_selection_reason"] == "quality_default"
    assert report["usesExpectedLabelsForSelection"] is False
    assert report["catalogSource"] == "live_core_hello"


def test_build_rejects_mismatched_audio_binding(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(builder, "EXPECTED_ROWS", 1)
    parakeet_path = tmp_path / "parakeet.jsonl"
    whisper_path = tmp_path / "whisper.jsonl"
    row = {
        "case_id": "one",
        "text": "hello",
        "execution_authority": False,
        "voice_reference_text_sha256": "a" * 64,
    }
    _write(parakeet_path, [row])
    _write(
        whisper_path,
        [{**row, "voice_reference_text_sha256": "b" * 64}],
    )

    try:
        builder.build(
            parakeet_path=parakeet_path,
            whisper_path=whisper_path,
            output_path=tmp_path / "output.jsonl",
            report_path=tmp_path / "report.json",
            available_operations=frozenset({"wifi.status"}),
            application_names=(),
            game_catalog=(),
            catalog_identities={"operations": 1},
        )
    except ValueError as error:
        assert str(error) == "baxy_asr_fusion_binding_invalid:one"
    else:
        raise AssertionError("mismatched binding was accepted")
