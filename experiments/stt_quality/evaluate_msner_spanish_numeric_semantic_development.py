"""Rescore frozen MSNER Parakeet outputs with Spanish numeric semantics."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


SCHEMA = "baxy.msner-spanish-numeric-semantic-development.v1"
SOURCE_ARTIFACT_SHA256 = (
    "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
)
SOURCE_DETAIL_SHA256 = (
    "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
)
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
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
THRESHOLDS = {
    "expectedCases": 504,
    "minimumNonemptyRate": 1.0,
    "maximumSemanticCorpusWer": 0.20,
    "minimumSemanticEntityExactRecall": 0.99,
    "minimumSemanticEntityTokenRecall": 0.99,
    "minimumNumericEntityExactRecall": 0.99,
    "minimumNamedEntityExactRecall": 0.99,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"msner_numeric_semantic_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _merge_per_type(
    target: dict[str, dict[str, int]], source: dict[str, dict[str, int]]
) -> None:
    for entity_type, source_counts in source.items():
        counts = target.setdefault(
            entity_type,
            {
                "entities": 0,
                "entitiesExactlyPreserved": 0,
                "entityTokens": 0,
                "entityTokensPreserved": 0,
            },
        )
        for key, value in source_counts.items():
            counts[key] += int(value)


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    repository_root = arguments.repository_root.resolve(strict=True)
    source_artifact_path = arguments.source_artifact.resolve(strict=True)
    source_detail_path = arguments.source_detail.resolve(strict=True)
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError("msner_numeric_semantic_output_exists")
    source_artifact = json.loads(
        source_artifact_path.read_text(encoding="utf-8-sig")
    )
    source_detail = json.loads(source_detail_path.read_text(encoding="utf-8-sig"))
    if (
        sha256(source_artifact_path) != SOURCE_ARTIFACT_SHA256
        or sha256(source_detail_path) != SOURCE_DETAIL_SHA256
        or source_artifact.get("status") != "failed"
        or source_artifact.get("detail", {}).get("sha256")
        != SOURCE_DETAIL_SHA256
        or source_artifact.get("wakeProgramTree", {}).get("sha256")
        != EXPECTED_WAKE_TREE_SHA256
        or source_artifact.get("validationBlindOpened") is not False
        or source_artifact.get("finalBlindOpened") is not False
        or source_artifact.get("effectsExecuted") != 0
        or source_detail.get("effectsExecuted") != 0
        or len(source_detail.get("cases", [])) != THRESHOLDS["expectedCases"]
    ):
        raise RuntimeError("msner_numeric_semantic_source_invalid")

    scorer = _load_module(
        "baxy_msner_numeric_entity_scorer",
        repository_root / "experiments/stt_quality/msner_entity_scoring.py",
    )
    numeric = _load_module(
        "baxy_msner_spanish_numeric_semantics",
        repository_root / "experiments/stt_quality/spanish_numeric_semantics.py",
    )
    frozen = _load_module(
        "baxy_msner_numeric_frozen_stt",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    per_type: dict[str, dict[str, int]] = {}
    case_commitments: list[dict[str, object]] = []
    reference_tokens = 0
    word_errors = 0
    entities = 0
    entities_preserved = 0
    entity_tokens = 0
    entity_tokens_preserved = 0
    for case in source_detail["cases"]:
        reference = str(case["reference"])
        hypothesis = str(case["productTranscript"])
        score = scorer.score_entity_preservation(
            reference=reference,
            label_ids=list(case["unifiedEntities"]),
            hypothesis=hypothesis,
            normalize_tokens=numeric.semantic_tokens,
        )
        normalized_reference = numeric.semantic_tokens(reference)
        normalized_hypothesis = numeric.semantic_tokens(hypothesis)
        errors = frozen._edit_distance(normalized_reference, normalized_hypothesis)
        reference_tokens += len(normalized_reference)
        word_errors += errors
        entities += int(score["entities"])
        entities_preserved += int(score["entitiesExactlyPreserved"])
        entity_tokens += int(score["entityTokens"])
        entity_tokens_preserved += int(score["entityTokensPreserved"])
        _merge_per_type(per_type, score["perType"])
        case_commitments.append(
            {
                "caseId": str(case["caseId"]),
                "referenceSha256": str(case["referenceSha256"]),
                "transcriptSha256": hashlib.sha256(
                    hypothesis.encode("utf-8")
                ).hexdigest(),
                "semanticWordErrors": errors,
                "semanticReferenceTokens": len(normalized_reference),
                "semanticEntities": score["entities"],
                "semanticEntitiesExactlyPreserved": score[
                    "entitiesExactlyPreserved"
                ],
            }
        )

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"entities": 0, "entitiesExactlyPreserved": 0}
    )
    for entity_type, counts in per_type.items():
        bucket = "numeric" if entity_type in NUMERIC_TYPES else "named"
        buckets[bucket]["entities"] += counts["entities"]
        buckets[bucket]["entitiesExactlyPreserved"] += counts[
            "entitiesExactlyPreserved"
        ]
        counts["entityExactRecall"] = round(
            counts["entitiesExactlyPreserved"] / max(1, counts["entities"]), 6
        )
        counts["entityTokenRecall"] = round(
            counts["entityTokensPreserved"] / max(1, counts["entityTokens"]), 6
        )
    for counts in buckets.values():
        counts["entityExactRecall"] = round(
            counts["entitiesExactlyPreserved"] / max(1, counts["entities"]), 6
        )

    metrics = {
        "cases": len(source_detail["cases"]),
        "nonemptyRate": source_artifact["metrics"]["nonemptyRate"],
        "semanticReferenceTokens": reference_tokens,
        "semanticWordErrors": word_errors,
        "semanticCorpusWer": round(word_errors / max(1, reference_tokens), 6),
        "entities": entities,
        "semanticEntitiesExactlyPreserved": entities_preserved,
        "semanticEntityExactRecall": round(
            entities_preserved / max(1, entities), 6
        ),
        "entityTokens": entity_tokens,
        "semanticEntityTokensPreserved": entity_tokens_preserved,
        "semanticEntityTokenRecall": round(
            entity_tokens_preserved / max(1, entity_tokens), 6
        ),
        "numeric": buckets["numeric"],
        "named": buckets["named"],
        "perType": dict(sorted(per_type.items())),
        "sourceLiteral": {
            "corpusWer": source_artifact["metrics"]["corpusWer"],
            "entityExactRecall": source_artifact["metrics"]["entityExactRecall"],
            "entityTokenRecall": source_artifact["metrics"]["entityTokenRecall"],
        },
    }
    checks = {
        "expectedCases": metrics["cases"] == THRESHOLDS["expectedCases"],
        "nonemptyRate": metrics["nonemptyRate"] >= THRESHOLDS["minimumNonemptyRate"],
        "semanticCorpusWer": metrics["semanticCorpusWer"]
        <= THRESHOLDS["maximumSemanticCorpusWer"],
        "semanticEntityExactRecall": metrics["semanticEntityExactRecall"]
        >= THRESHOLDS["minimumSemanticEntityExactRecall"],
        "semanticEntityTokenRecall": metrics["semanticEntityTokenRecall"]
        >= THRESHOLDS["minimumSemanticEntityTokenRecall"],
        "numericEntityExactRecall": metrics["numeric"]["entityExactRecall"]
        >= THRESHOLDS["minimumNumericEntityExactRecall"],
        "namedEntityExactRecall": metrics["named"]["entityExactRecall"]
        >= THRESHOLDS["minimumNamedEntityExactRecall"],
        "effectsExecuted": True,
    }
    evaluator_path = Path(__file__).resolve(strict=True)
    numeric_path = Path(numeric.__file__).resolve(strict=True)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "status": "passed" if all(checks.values()) else "failed",
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "decision": {
            "candidatePromoted": False,
            "numericNormalizerRetainedForDevelopmentCascade": True,
            "validationBlindMayOpen": False,
            "finalBlindMayOpen": False,
            "remainingPrimaryFailure": "named_entity_preservation",
        },
        "source": {
            "artifactSha256": SOURCE_ARTIFACT_SHA256,
            "detailSha256": SOURCE_DETAIL_SHA256,
        },
        "evaluator": {
            "path": evaluator_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(evaluator_path),
        },
        "numericNormalizer": {
            "path": numeric_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(numeric_path),
        },
        "caseCommitments": case_commitments,
        "developmentRowsOpened": True,
        "validationBlindOpened": False,
        "finalBlindOpened": False,
        "wakeProgramTree": source_artifact["wakeProgramTree"],
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
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-artifact", type=Path, required=True)
    parser.add_argument("--source-detail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    result = evaluate(arguments)
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
