"""Publish aggregate causes from the rejected MSNER Parakeet development run."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any


SCHEMA = "baxy.msner-spanish-parakeet-failure-analysis.v1"
SOURCE_SCHEMA = "baxy.msner-spanish-entity-development-evaluation.v1"
SOURCE_ARTIFACT_SHA256 = (
    "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
)
SOURCE_DETAIL_SHA256 = (
    "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
)
NUMERIC_TYPES = {
    "cardinal_number",
    "date",
    "money",
    "ordinal_number",
    "percent",
    "quantity",
    "time",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _surface_key(surface: str) -> str:
    folded = unicodedata.normalize("NFKD", surface.casefold())
    plain = "".join(character for character in folded if not unicodedata.combining(character))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def analyze(
    *, artifact_path: Path, detail_path: Path, output_path: Path
) -> dict[str, Any]:
    artifact_path = artifact_path.resolve(strict=True)
    detail_path = detail_path.resolve(strict=True)
    output_path = output_path.resolve()
    if output_path.exists():
        raise RuntimeError("msner_parakeet_failure_analysis_output_exists")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8-sig"))
    detail = json.loads(detail_path.read_text(encoding="utf-8-sig"))
    if (
        sha256(artifact_path) != SOURCE_ARTIFACT_SHA256
        or sha256(detail_path) != SOURCE_DETAIL_SHA256
        or artifact.get("schema") != SOURCE_SCHEMA
        or detail.get("schema") != SOURCE_SCHEMA
        or artifact.get("status") != "failed"
        or artifact.get("validationBlindOpened") is not False
        or artifact.get("finalBlindOpened") is not False
        or artifact.get("effectsExecuted") != 0
        or detail.get("effectsExecuted") != 0
        or artifact.get("detail", {}).get("sha256") != SOURCE_DETAIL_SHA256
    ):
        raise RuntimeError("msner_parakeet_failure_analysis_source_invalid")

    occurrences: list[tuple[str, str, bool]] = []
    for case in detail.get("cases", []):
        for entity in case.get("entityCommitments", []):
            occurrences.append(
                (
                    str(entity["type"]),
                    _surface_key(str(entity["surface"])),
                    bool(entity["exactlyPreserved"]),
                )
            )
    surface_frequency = Counter(surface for _type, surface, _preserved in occurrences)
    misses = [row for row in occurrences if not row[2]]
    misses_by_type = Counter(entity_type for entity_type, _surface, _preserved in misses)
    empty_cases = [
        {
            "caseId": str(case["caseId"]),
            "audioSeconds": float(case["audioSeconds"]),
            "referenceTokens": int(case["referenceTokens"]),
            "entities": int(case["entities"]),
        }
        for case in detail.get("cases", [])
        if not str(case.get("productTranscript") or "").strip()
    ]
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "analyzedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "baseline_rejected",
        "source": {
            "artifact": {
                "path": artifact_path.as_posix(),
                "sha256": SOURCE_ARTIFACT_SHA256,
            },
            "detail": {
                "path": detail_path.as_posix(),
                "sha256": SOURCE_DETAIL_SHA256,
                "storedOutsideRepository": True,
            },
        },
        "passed": {
            "corpusWer": artifact["metrics"]["corpusWer"],
            "latencyP95Seconds": artifact["metrics"]["latencyP95Seconds"],
            "realTimeFactorP95": artifact["metrics"]["realTimeFactorP95"],
            "peakRssBytesObserved": artifact["metrics"]["peakRssBytesObserved"],
            "decodeErrors": artifact["metrics"]["decodeErrors"],
        },
        "failed": {
            "nonemptyRate": artifact["metrics"]["nonemptyRate"],
            "entityExactRecall": artifact["metrics"]["entityExactRecall"],
            "entityTokenRecall": artifact["metrics"]["entityTokenRecall"],
        },
        "mechanism": {
            "emptyCases": empty_cases,
            "entities": len(occurrences),
            "missedEntities": len(misses),
            "missedEntityTokens": int(artifact["metrics"]["entityTokens"])
            - int(artifact["metrics"]["entityTokensPreserved"]),
            "missedNumericEntities": sum(
                entity_type in NUMERIC_TYPES
                for entity_type, _surface, _preserved in misses
            ),
            "missedNamedEntities": sum(
                entity_type not in NUMERIC_TYPES
                for entity_type, _surface, _preserved in misses
            ),
            "missesWithSurfaceSeenInAnotherDevelopmentCase": sum(
                surface_frequency[surface] > 1
                for _entity_type, surface, _preserved in misses
            ),
            "missesWithUniqueDevelopmentSurface": sum(
                surface_frequency[surface] == 1
                for _entity_type, surface, _preserved in misses
            ),
            "missesByType": dict(sorted(misses_by_type.items())),
        },
        "decision": {
            "candidatePromoted": False,
            "validationBlindMayOpen": False,
            "finalBlindMayOpen": False,
            "plainGreedyPrimaryRetainedAsLatencyBaseline": True,
            "nextArchitecture": [
                "short-utterance recovery measured with an independent streaming recognizer",
                "numeric semantic canonicalization measured separately from literal surface recall",
                "selective contextual entity recovery from a reference-independent authenticated inventory",
                "clarification when independent hypotheses disagree on a critical entity",
            ],
            "sameDevelopmentRowsMayTune": True,
            "blindRowsMayTune": False,
        },
        "contract": {
            "rawTextStoredInRepository": False,
            "developmentRowsOpened": True,
            "validationBlindRowsOpened": False,
            "finalBlindRowsOpened": False,
            "effectsExecuted": 0,
        },
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--detail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    result = analyze(
        artifact_path=arguments.artifact,
        detail_path=arguments.detail,
        output_path=arguments.output,
    )
    print(
        json.dumps(
            {
                "output": str(arguments.output),
                "status": result["status"],
                "sha256": sha256(arguments.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
