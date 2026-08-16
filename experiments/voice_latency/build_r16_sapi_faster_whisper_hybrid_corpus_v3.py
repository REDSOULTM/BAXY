"""Build an opened dual-ASR replay corpus for Parakeet router failures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


EXPECTED_ROWS = 337
EXPECTED_REPLACEMENTS = 88


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(
    *, transcript_corpus_path: Path, faster_report_path: Path, output_path: Path
) -> dict[str, object]:
    transcript_corpus_path = transcript_corpus_path.resolve(strict=True)
    faster_report_path = faster_report_path.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists():
        raise ValueError("baxy_r16_hybrid_output_exists")
    rows = [
        json.loads(line)
        for line in transcript_corpus_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    faster = json.loads(faster_report_path.read_text(encoding="utf-8-sig"))
    records = faster.get("records") if isinstance(faster, dict) else None
    if (
        len(rows) != EXPECTED_ROWS
        or faster.get("schema")
        != "baxy.r16-sapi-faster-whisper-failures-development.v2"
        or faster.get("metrics", {}).get("cases") != EXPECTED_REPLACEMENTS
        or faster.get("effectsExecuted") != 0
        or not isinstance(records, list)
        or len(records) != EXPECTED_REPLACEMENTS
    ):
        raise ValueError("baxy_r16_hybrid_evidence_invalid")
    by_id = {str(record.get("caseId")): record for record in records}
    if len(by_id) != EXPECTED_REPLACEMENTS:
        raise ValueError("baxy_r16_hybrid_ids_invalid")
    derived = []
    replaced = 0
    for row in rows:
        item = dict(row)
        record = by_id.get(str(row.get("case_id")))
        if record is not None:
            transcript = record.get("fasterWhisperTranscript")
            if not isinstance(transcript, str) or not transcript.strip():
                raise ValueError("baxy_r16_hybrid_transcript_invalid")
            item["text"] = transcript.strip()
            item["schema"] = "baxy.r16-sapi-dual-asr-development.v3"
            item["transcript_authority"] = "faster_whisper_large_v3_fallback"
            replaced += 1
        else:
            item["schema"] = "baxy.r16-sapi-dual-asr-development.v3"
            item["transcript_authority"] = "parakeet_primary"
        derived.append(item)
    if replaced != EXPECTED_REPLACEMENTS:
        raise ValueError("baxy_r16_hybrid_replacement_count_invalid")
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
        "schema": "baxy.r16-sapi-dual-asr-development.v3",
        "rows": len(derived),
        "replacements": replaced,
        "transcriptCorpusSha256": sha256(transcript_corpus_path),
        "fasterReportSha256": sha256(faster_report_path),
        "outputSha256": sha256(output_path),
        "developmentOnly": True,
        "effectsExecuted": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript-corpus", type=Path, required=True)
    parser.add_argument("--faster-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    print(
        json.dumps(
            build(
                transcript_corpus_path=arguments.transcript_corpus,
                faster_report_path=arguments.faster_report,
                output_path=arguments.output,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
