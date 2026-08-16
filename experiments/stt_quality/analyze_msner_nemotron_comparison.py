"""Compare MSNER Parakeet and Nemotron development results without raw text."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "baxy.msner-nemotron-comparison-analysis.v1"
PARAKEET_ARTIFACT_SHA256 = (
    "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
)
PARAKEET_DETAIL_SHA256 = (
    "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
)
NEMOTRON_ARTIFACT_SHA256 = (
    "cf00d336bceb0c87be08746a99f1369faf5f2c709d30a6573fd5e24998a3de85"
)
NEMOTRON_DETAIL_SHA256 = (
    "d2fec9837d2bef3f8abb0941e866510a160b00352ea5e5e94c64358c8fa3eddc"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_source(
    artifact_path: Path,
    detail_path: Path,
    artifact_hash: str,
    detail_hash: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact_path = artifact_path.resolve(strict=True)
    detail_path = detail_path.resolve(strict=True)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8-sig"))
    detail = json.loads(detail_path.read_text(encoding="utf-8-sig"))
    if (
        sha256(artifact_path) != artifact_hash
        or sha256(detail_path) != detail_hash
        or artifact.get("status") != "failed"
        or artifact.get("detail", {}).get("sha256") != detail_hash
        or artifact.get("validationBlindOpened") is not False
        or artifact.get("finalBlindOpened") is not False
        or artifact.get("effectsExecuted") != 0
        or detail.get("effectsExecuted") != 0
        or len(detail.get("cases", [])) != 504
    ):
        raise RuntimeError("msner_nemotron_comparison_source_invalid")
    return artifact, detail


def analyze(arguments: argparse.Namespace) -> dict[str, Any]:
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError("msner_nemotron_comparison_output_exists")
    parakeet_artifact, parakeet_detail = _read_source(
        arguments.parakeet_artifact,
        arguments.parakeet_detail,
        PARAKEET_ARTIFACT_SHA256,
        PARAKEET_DETAIL_SHA256,
    )
    nemotron_artifact, nemotron_detail = _read_source(
        arguments.nemotron_artifact,
        arguments.nemotron_detail,
        NEMOTRON_ARTIFACT_SHA256,
        NEMOTRON_DETAIL_SHA256,
    )

    relationship = {
        "bothPreserved": 0,
        "nemotronRescued": 0,
        "nemotronDamaged": 0,
        "neitherPreserved": 0,
    }
    case_wer = {"parakeetBetter": 0, "nemotronBetter": 0, "tie": 0}
    parakeet_empty: list[dict[str, object]] = []
    nemotron_empty_cases = 0
    oracle_word_errors = 0
    reference_tokens = 0
    oracle_case_entities = 0
    for parakeet, nemotron in zip(
        parakeet_detail["cases"], nemotron_detail["cases"], strict=True
    ):
        if parakeet["caseId"] != nemotron["caseId"]:
            raise RuntimeError("msner_nemotron_comparison_case_order_changed")
        parakeet_errors = int(parakeet["wordErrors"])
        nemotron_errors = int(nemotron["wordErrors"])
        reference_tokens += int(parakeet["referenceTokens"])
        oracle_word_errors += min(parakeet_errors, nemotron_errors)
        if parakeet_errors < nemotron_errors:
            case_wer["parakeetBetter"] += 1
        elif nemotron_errors < parakeet_errors:
            case_wer["nemotronBetter"] += 1
        else:
            case_wer["tie"] += 1
        oracle_case_entities += max(
            int(parakeet["entitiesExactlyPreserved"]),
            int(nemotron["entitiesExactlyPreserved"]),
        )
        if not str(parakeet.get("productTranscript") or "").strip():
            parakeet_empty.append(
                {
                    "caseId": str(parakeet["caseId"]),
                    "nemotronNonempty": bool(
                        str(nemotron.get("productTranscript") or "").strip()
                    ),
                    "nemotronWer": float(nemotron["wer"]),
                }
            )
        nemotron_empty_cases += not str(
            nemotron.get("productTranscript") or ""
        ).strip()
        for first, second in zip(
            parakeet["entityCommitments"],
            nemotron["entityCommitments"],
            strict=True,
        ):
            if (
                first["type"] != second["type"]
                or first["surface"] != second["surface"]
            ):
                raise RuntimeError("msner_nemotron_comparison_entity_order_changed")
            parakeet_preserved = bool(first["exactlyPreserved"])
            nemotron_preserved = bool(second["exactlyPreserved"])
            if parakeet_preserved and nemotron_preserved:
                relationship["bothPreserved"] += 1
            elif not parakeet_preserved and nemotron_preserved:
                relationship["nemotronRescued"] += 1
            elif parakeet_preserved and not nemotron_preserved:
                relationship["nemotronDamaged"] += 1
            else:
                relationship["neitherPreserved"] += 1

    entities = int(parakeet_artifact["metrics"]["entities"])
    union_entities = (
        relationship["bothPreserved"]
        + relationship["nemotronRescued"]
        + relationship["nemotronDamaged"]
    )
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "analyzedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "nemotron_rejected",
        "baseline": {
            "engine": "parakeet_greedy",
            "corpusWer": parakeet_artifact["metrics"]["corpusWer"],
            "entityExactRecall": parakeet_artifact["metrics"]["entityExactRecall"],
            "nonemptyRate": parakeet_artifact["metrics"]["nonemptyRate"],
            "realTimeFactorP95": parakeet_artifact["metrics"]["realTimeFactorP95"],
        },
        "candidate": {
            "engine": "nemotron_auto",
            "corpusWer": nemotron_artifact["metrics"]["corpusWer"],
            "entityExactRecall": nemotron_artifact["metrics"]["entityExactRecall"],
            "nonemptyRate": nemotron_artifact["metrics"]["nonemptyRate"],
            "realTimeFactorP95": nemotron_artifact["metrics"]["realTimeFactorP95"],
        },
        "comparison": {
            "entityRelationship": relationship,
            "caseWerRelationship": case_wer,
            "entityUnionOracleRecall": round(union_entities / max(1, entities), 6),
            "caseChoiceOracleWer": round(
                oracle_word_errors / max(1, reference_tokens), 6
            ),
            "caseChoiceOracleEntityRecall": round(
                oracle_case_entities / max(1, entities), 6
            ),
            "parakeetEmptyCases": parakeet_empty,
            "nemotronEmptyCases": nemotron_empty_cases,
        },
        "decision": {
            "candidatePromoted": False,
            "nemotronAllowedAsGeneralSecondary": False,
            "nemotronAllowedAsEmptyFallback": False,
            "validationBlindMayOpen": False,
            "finalBlindMayOpen": False,
            "reason": (
                "The candidate rescues too few entities, damages many baseline "
                "successes, worsens WER, and leaves three of four baseline empty "
                "utterances empty. Even oracle fusion remains far below the gate."
            ),
            "nextArchitecture": (
                "reference-independent selective contextual recovery on top of "
                "the Parakeet primary"
            ),
        },
        "sources": {
            "parakeet": {
                "artifactSha256": PARAKEET_ARTIFACT_SHA256,
                "detailSha256": PARAKEET_DETAIL_SHA256,
            },
            "nemotron": {
                "artifactSha256": NEMOTRON_ARTIFACT_SHA256,
                "detailSha256": NEMOTRON_DETAIL_SHA256,
            },
        },
        "contract": {
            "developmentRowsOpened": True,
            "validationBlindRowsOpened": False,
            "finalBlindRowsOpened": False,
            "rawTextStoredInRepository": False,
            "effectsExecuted": 0,
        },
        "effectsExecuted": 0,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parakeet-artifact", type=Path, required=True)
    parser.add_argument("--parakeet-detail", type=Path, required=True)
    parser.add_argument("--nemotron-artifact", type=Path, required=True)
    parser.add_argument("--nemotron-detail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    result = analyze(arguments)
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
