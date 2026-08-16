"""Bind the completed R16 SAPI transcripts to their opened expected contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


VOICE_SCHEMA = "baxy.r16-sapi-voice-semantics-development.v1"
SOURCE_SCHEMA = "baxy.generalization-product-holdout.v16"
OUTPUT_SCHEMA = "baxy.r16-sapi-voice-transcript-development.v2"
EXPECTED_SOURCE_ROWS = 700
EXPECTED_VOICE_ROWS = 337


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("baxy_r16_voice_transcript_source_invalid")
    return rows


def derive_rows(
    source_rows: list[dict[str, object]],
    voice_report: dict[str, object],
) -> list[dict[str, object]]:
    by_id = {str(row.get("case_id")): row for row in source_rows}
    if len(by_id) != len(source_rows):
        raise ValueError("baxy_r16_voice_transcript_source_ids_invalid")
    voice_rows = voice_report.get("rows")
    if not isinstance(voice_rows, list):
        raise ValueError("baxy_r16_voice_transcript_rows_invalid")
    derived: list[dict[str, object]] = []
    for voice in voice_rows:
        if not isinstance(voice, dict):
            raise ValueError("baxy_r16_voice_transcript_row_invalid")
        case_id = str(voice.get("caseId"))
        source = by_id.get(case_id)
        if source is None or any(
            voice.get(voice_name) != source.get(source_name)
            for voice_name, source_name in (
                ("caseType", "case_type"),
                ("language", "language"),
                ("outcome", "outcome"),
            )
        ):
            raise ValueError(f"baxy_r16_voice_transcript_binding_invalid:{case_id}")
        transcript = voice.get("transcript")
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError(f"baxy_r16_voice_transcript_empty:{case_id}")
        if voice.get("vadSegmented") is not True:
            raise ValueError(f"baxy_r16_voice_transcript_vad_invalid:{case_id}")
        row = dict(source)
        row.update(
            {
                "schema": OUTPUT_SCHEMA,
                "text": transcript.strip(),
                "blind_holdout": False,
                "execution_authority": False,
                "voice_reference_text_sha256": hashlib.sha256(
                    str(source.get("text", "")).encode("utf-8")
                ).hexdigest(),
            }
        )
        derived.append(row)
    if len({str(row["case_id"]) for row in derived}) != len(derived):
        raise ValueError("baxy_r16_voice_transcript_duplicate_ids")
    return derived


def build(*, corpus_path: Path, voice_report_path: Path, output_path: Path) -> dict[str, object]:
    corpus_path = corpus_path.resolve(strict=True)
    voice_report_path = voice_report_path.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"baxy_r16_voice_transcript_output_exists:{output_path}")
    source_rows = read_jsonl(corpus_path)
    voice_report = json.loads(voice_report_path.read_text(encoding="utf-8-sig"))
    if (
        len(source_rows) != EXPECTED_SOURCE_ROWS
        or any(row.get("schema") != SOURCE_SCHEMA for row in source_rows)
        or not isinstance(voice_report, dict)
        or voice_report.get("schema") != VOICE_SCHEMA
        or voice_report.get("effectsExecuted") != 0
        or voice_report.get("sources", {}).get("corpusSha256") != sha256(corpus_path)
    ):
        raise ValueError("baxy_r16_voice_transcript_evidence_invalid")
    derived = derive_rows(source_rows, voice_report)
    if len(derived) != EXPECTED_VOICE_ROWS:
        raise ValueError("baxy_r16_voice_transcript_population_invalid")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".partial")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in derived
        ),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output_path)
    return {
        "schema": OUTPUT_SCHEMA,
        "rows": len(derived),
        "sourceCorpusSha256": sha256(corpus_path),
        "voiceReportSha256": sha256(voice_report_path),
        "outputSha256": sha256(output_path),
        "blindHoldoutClaimSupported": False,
        "effectsExecuted": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--voice-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    print(
        json.dumps(
            build(
                corpus_path=arguments.corpus,
                voice_report_path=arguments.voice_report,
                output_path=arguments.output,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
