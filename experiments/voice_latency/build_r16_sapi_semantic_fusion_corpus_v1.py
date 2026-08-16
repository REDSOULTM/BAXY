"""Build a label-free Parakeet/Faster-Whisper semantic fusion corpus."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.asr_fusion import select_transcript  # noqa: E402


EXPECTED_ROWS = 337
CORPUS_SCHEMA = "baxy.r16-sapi-semantic-asr-fusion-development.v1"
REPORT_SCHEMA = "baxy.r16-sapi-semantic-asr-fusion-build-development.v1"


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
        raise ValueError("baxy_asr_fusion_jsonl_invalid")
    return rows


def build(
    *,
    parakeet_path: Path,
    whisper_path: Path,
    output_path: Path,
    report_path: Path,
) -> dict[str, object]:
    for candidate in (output_path, report_path):
        if candidate.exists():
            raise ValueError(f"baxy_asr_fusion_output_exists:{candidate}")
    parakeet_path = parakeet_path.resolve(strict=True)
    whisper_path = whisper_path.resolve(strict=True)
    output_path = output_path.resolve()
    report_path = report_path.resolve()
    parakeet_rows = read_jsonl(parakeet_path)
    whisper_rows = read_jsonl(whisper_path)
    if (
        len(parakeet_rows) != EXPECTED_ROWS
        or len(whisper_rows) != EXPECTED_ROWS
        or any(row.get("execution_authority") is not False for row in parakeet_rows)
        or any(row.get("execution_authority") is not False for row in whisper_rows)
    ):
        raise ValueError("baxy_asr_fusion_population_invalid")
    available_operations = frozenset(
        operation
        for row in parakeet_rows
        for accepted in row.get("compatible_effect_operation_sets", [])
        for operation in accepted
        if isinstance(operation, str)
    )
    if not available_operations:
        raise ValueError("baxy_asr_fusion_catalog_invalid")
    derived: list[dict[str, object]] = []
    decisions: list[dict[str, str]] = []
    counts: Counter[tuple[str, str]] = Counter()
    for parakeet, whisper in zip(parakeet_rows, whisper_rows, strict=True):
        case_id = str(parakeet.get("case_id"))
        if (
            case_id != str(whisper.get("case_id"))
            or parakeet.get("voice_reference_text_sha256")
            != whisper.get("voice_reference_text_sha256")
        ):
            raise ValueError(f"baxy_asr_fusion_binding_invalid:{case_id}")
        selection = select_transcript(
            str(parakeet.get("text") or ""),
            str(whisper.get("text") or ""),
            available_operations,
        )
        if selection.requires_clarification:
            raise ValueError(
                f"baxy_asr_fusion_conflict:{case_id}:{selection.reason}"
            )
        row = dict(parakeet)
        row.update(
            {
                "schema": CORPUS_SCHEMA,
                "text": selection.text,
                "transcript_authority": selection.source,
                "transcript_selection_reason": selection.reason,
            }
        )
        derived.append(row)
        decisions.append(
            {
                "caseId": case_id,
                "source": selection.source,
                "reason": selection.reason,
            }
        )
        counts[(selection.source, selection.reason)] += 1
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in derived
        ),
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, output_path)
    report = {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_r16_label_free_semantic_asr_fusion_build",
        "sources": {
            "parakeetCorpusSha256": sha256(parakeet_path),
            "whisperCorpusSha256": sha256(whisper_path),
        },
        "rows": len(derived),
        "selectionCounts": [
            {"source": source, "reason": reason, "cases": cases}
            for (source, reason), cases in sorted(counts.items())
        ],
        "decisions": decisions,
        "outputSha256": sha256(output_path),
        "usesExpectedLabelsForSelection": False,
        "effectsExecuted": 0,
        "developmentOnly": True,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parakeet", type=Path, required=True)
    parser.add_argument("--whisper", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = build(
        parakeet_path=arguments.parakeet,
        whisper_path=arguments.whisper,
        output_path=arguments.output,
        report_path=arguments.report,
    )
    print(json.dumps({"rows": report["rows"], "outputSha256": report["outputSha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
