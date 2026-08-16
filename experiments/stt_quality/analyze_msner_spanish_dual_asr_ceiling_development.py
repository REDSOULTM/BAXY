"""Measure the semantic ceiling of frozen Parakeet and Faster-Whisper outputs.

This is an explicitly non-promotable development oracle. It never decodes
audio and never opens either reserved MSNER shard. Its purpose is to determine
whether choosing or merging the two already-frozen hypotheses can plausibly
reach the 99% entity-preservation contract before another blind is consumed.
"""

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


SCHEMA = "baxy.msner-spanish-dual-asr-ceiling-development.v1"
EXPECTED_CASES = 504
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)
PARAKEET_ARTIFACT_SHA256 = (
    "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
)
PARAKEET_DETAIL_SHA256 = (
    "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
)
FASTER_WHISPER_ARTIFACT_SHA256 = (
    "c692bbb0cdd39552ea06b360d0631929c76a8482252dfd8b97627dfa03792aa7"
)
FASTER_WHISPER_DETAIL_SHA256 = (
    "9388ce72458893ef5107f658a68f7bf7cfd501c3904fe5c1148fb793c745aab7"
)
MINIMUM_ENTITY_EXACT_RECALL = 0.99


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"msner_dual_asr_module_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _load_source(
    artifact_path: Path,
    detail_path: Path,
    *,
    artifact_sha256: str,
    detail_sha256: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if sha256(artifact_path) != artifact_sha256 or sha256(detail_path) != detail_sha256:
        raise RuntimeError("msner_dual_asr_source_changed")
    artifact = json.loads(artifact_path.read_text(encoding="utf-8-sig"))
    detail = json.loads(detail_path.read_text(encoding="utf-8-sig"))
    rows = detail.get("cases")
    if (
        artifact.get("status") != "failed"
        or artifact.get("detail", {}).get("sha256") != detail_sha256
        or artifact.get("wakeProgramTree", {}).get("sha256")
        != EXPECTED_WAKE_TREE_SHA256
        or artifact.get("validationBlindOpened") is not False
        or artifact.get("finalBlindOpened") is not False
        or artifact.get("effectsExecuted") != 0
        or detail.get("validationBlindOpened") is not False
        or detail.get("finalBlindOpened") is not False
        or detail.get("effectsExecuted") != 0
        or not isinstance(rows, list)
        or len(rows) != EXPECTED_CASES
    ):
        raise RuntimeError("msner_dual_asr_source_invalid")
    return artifact, rows


def analyze(arguments: argparse.Namespace) -> dict[str, Any]:
    repository_root = arguments.repository_root.resolve(strict=True)
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError("msner_dual_asr_output_exists")
    parakeet_artifact_path = arguments.parakeet_artifact.resolve(strict=True)
    parakeet_detail_path = arguments.parakeet_detail.resolve(strict=True)
    faster_artifact_path = arguments.faster_whisper_artifact.resolve(strict=True)
    faster_detail_path = arguments.faster_whisper_detail.resolve(strict=True)
    parakeet_artifact, parakeet_rows = _load_source(
        parakeet_artifact_path,
        parakeet_detail_path,
        artifact_sha256=PARAKEET_ARTIFACT_SHA256,
        detail_sha256=PARAKEET_DETAIL_SHA256,
    )
    faster_artifact, faster_rows = _load_source(
        faster_artifact_path,
        faster_detail_path,
        artifact_sha256=FASTER_WHISPER_ARTIFACT_SHA256,
        detail_sha256=FASTER_WHISPER_DETAIL_SHA256,
    )

    scorer = _load_module(
        "baxy_msner_dual_asr_entity_scorer",
        repository_root / "experiments/stt_quality/msner_entity_scoring.py",
    )
    numeric = _load_module(
        "baxy_msner_dual_asr_numeric_semantics",
        repository_root / "experiments/stt_quality/spanish_numeric_semantics.py",
    )
    frozen = _load_module(
        "baxy_msner_dual_asr_frozen_scoring",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    totals: defaultdict[str, int] = defaultdict(int)
    per_type: dict[str, dict[str, int]] = {}
    case_commitments: list[dict[str, object]] = []
    for parakeet, faster in zip(parakeet_rows, faster_rows, strict=True):
        if (
            parakeet.get("caseId") != faster.get("caseId")
            or parakeet.get("referenceSha256") != faster.get("referenceSha256")
            or parakeet.get("reference") != faster.get("reference")
            or parakeet.get("unifiedEntities") != faster.get("unifiedEntities")
        ):
            raise RuntimeError("msner_dual_asr_case_binding_changed")
        reference = str(parakeet["reference"])
        labels = list(parakeet["unifiedEntities"])
        parakeet_score = scorer.score_entity_preservation(
            reference=reference,
            label_ids=labels,
            hypothesis=str(parakeet["productTranscript"]),
            normalize_tokens=numeric.semantic_tokens,
        )
        faster_score = scorer.score_entity_preservation(
            reference=reference,
            label_ids=labels,
            hypothesis=str(faster["productTranscript"]),
            normalize_tokens=numeric.semantic_tokens,
        )
        reference_tokens = numeric.semantic_tokens(reference)
        parakeet_errors = frozen._edit_distance(
            reference_tokens,
            numeric.semantic_tokens(str(parakeet["productTranscript"])),
        )
        faster_errors = frozen._edit_distance(
            reference_tokens,
            numeric.semantic_tokens(str(faster["productTranscript"])),
        )
        parakeet_rank = (
            int(parakeet_score["entitiesExactlyPreserved"]),
            int(parakeet_score["entityTokensPreserved"]),
            -parakeet_errors,
        )
        faster_rank = (
            int(faster_score["entitiesExactlyPreserved"]),
            int(faster_score["entityTokensPreserved"]),
            -faster_errors,
        )
        selected_name, selected_score, selected_errors = (
            ("fasterWhisper", faster_score, faster_errors)
            if faster_rank > parakeet_rank
            else ("parakeet", parakeet_score, parakeet_errors)
        )
        totals["cases"] += 1
        totals["referenceTokens"] += len(reference_tokens)
        totals["entities"] += int(parakeet_score["entities"])
        totals["entityTokens"] += int(parakeet_score["entityTokens"])
        for name, score, errors in (
            ("parakeet", parakeet_score, parakeet_errors),
            ("fasterWhisper", faster_score, faster_errors),
        ):
            totals[f"{name}Errors"] += errors
            totals[f"{name}Entities"] += int(score["entitiesExactlyPreserved"])
            totals[f"{name}EntityTokens"] += int(score["entityTokensPreserved"])
        totals["selectorErrors"] += selected_errors
        totals["selectorEntities"] += int(selected_score["entitiesExactlyPreserved"])
        totals["selectorEntityTokens"] += int(selected_score["entityTokensPreserved"])
        totals[f"selector{selected_name}Cases"] += 1

        union_preserved = 0
        for parakeet_entity, faster_entity in zip(
            parakeet_score["entityCommitments"],
            faster_score["entityCommitments"],
            strict=True,
        ):
            if (
                parakeet_entity["type"] != faster_entity["type"]
                or parakeet_entity["surface"] != faster_entity["surface"]
            ):
                raise RuntimeError("msner_dual_asr_entity_binding_changed")
            entity_type = str(parakeet_entity["type"])
            parakeet_exact = bool(parakeet_entity["exactlyPreserved"])
            faster_exact = bool(faster_entity["exactlyPreserved"])
            union_exact = parakeet_exact or faster_exact
            counts = per_type.setdefault(
                entity_type,
                {
                    "entities": 0,
                    "parakeetExactlyPreserved": 0,
                    "fasterWhisperExactlyPreserved": 0,
                    "unionExactlyPreserved": 0,
                },
            )
            counts["entities"] += 1
            counts["parakeetExactlyPreserved"] += int(parakeet_exact)
            counts["fasterWhisperExactlyPreserved"] += int(faster_exact)
            counts["unionExactlyPreserved"] += int(union_exact)
            totals["unionEntities"] += int(union_exact)
            totals["parakeetOnly"] += int(parakeet_exact and not faster_exact)
            totals["fasterWhisperOnly"] += int(faster_exact and not parakeet_exact)
            totals["neither"] += int(not parakeet_exact and not faster_exact)
            union_preserved += int(union_exact)
        case_commitments.append(
            {
                "caseId": str(parakeet["caseId"]),
                "referenceSha256": str(parakeet["referenceSha256"]),
                "parakeetSemanticEntities": int(
                    parakeet_score["entitiesExactlyPreserved"]
                ),
                "fasterWhisperSemanticEntities": int(
                    faster_score["entitiesExactlyPreserved"]
                ),
                "unionSemanticEntities": union_preserved,
                "oracleSelectedSource": selected_name,
            }
        )

    entities = max(1, totals["entities"])
    entity_tokens = max(1, totals["entityTokens"])
    reference_tokens = max(1, totals["referenceTokens"])
    for counts in per_type.values():
        denominator = max(1, counts["entities"])
        counts["parakeetExactRecall"] = round(
            counts["parakeetExactlyPreserved"] / denominator, 6
        )
        counts["fasterWhisperExactRecall"] = round(
            counts["fasterWhisperExactlyPreserved"] / denominator, 6
        )
        counts["unionExactRecall"] = round(
            counts["unionExactlyPreserved"] / denominator, 6
        )
        counts["neither"] = counts["entities"] - counts["unionExactlyPreserved"]
    metrics = {
        "cases": totals["cases"],
        "entities": totals["entities"],
        "entityTokens": totals["entityTokens"],
        "parakeetSemantic": {
            "corpusWer": round(totals["parakeetErrors"] / reference_tokens, 6),
            "entityExactRecall": round(totals["parakeetEntities"] / entities, 6),
            "entityTokenRecall": round(
                totals["parakeetEntityTokens"] / entity_tokens, 6
            ),
        },
        "fasterWhisperSemantic": {
            "corpusWer": round(
                totals["fasterWhisperErrors"] / reference_tokens, 6
            ),
            "entityExactRecall": round(
                totals["fasterWhisperEntities"] / entities, 6
            ),
            "entityTokenRecall": round(
                totals["fasterWhisperEntityTokens"] / entity_tokens, 6
            ),
        },
        "caseSelectorOracle": {
            "corpusWer": round(totals["selectorErrors"] / reference_tokens, 6),
            "entityExactRecall": round(totals["selectorEntities"] / entities, 6),
            "entityTokenRecall": round(
                totals["selectorEntityTokens"] / entity_tokens, 6
            ),
            "parakeetCases": totals["selectorparakeetCases"],
            "fasterWhisperCases": totals["selectorfasterWhisperCases"],
        },
        "entityUnionOracle": {
            "entitiesExactlyPreserved": totals["unionEntities"],
            "entityExactRecall": round(totals["unionEntities"] / entities, 6),
            "parakeetOnly": totals["parakeetOnly"],
            "fasterWhisperOnly": totals["fasterWhisperOnly"],
            "neither": totals["neither"],
        },
        "perType": dict(sorted(per_type.items())),
    }
    union_passed = (
        metrics["entityUnionOracle"]["entityExactRecall"]
        >= MINIMUM_ENTITY_EXACT_RECALL
    )
    analyzer_path = Path(__file__).resolve(strict=True)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "status": "diagnostic_complete",
        "metrics": metrics,
        "thresholds": {
            "minimumEntityExactRecall": MINIMUM_ENTITY_EXACT_RECALL,
        },
        "decision": {
            "dualAsrAloneSufficient": union_passed,
            "candidatePromoted": False,
            "validationBlindMayOpen": False,
            "finalBlindMayOpen": False,
            "requiredNextArchitecture": (
                "none"
                if union_passed
                else "catalog_derived_acoustic_phrase_boosting_or_constrained_decoding"
            ),
        },
        "sources": {
            "parakeet": {
                "artifactSha256": PARAKEET_ARTIFACT_SHA256,
                "detailSha256": PARAKEET_DETAIL_SHA256,
            },
            "fasterWhisper": {
                "artifactSha256": FASTER_WHISPER_ARTIFACT_SHA256,
                "detailSha256": FASTER_WHISPER_DETAIL_SHA256,
            },
        },
        "analyzer": {
            "path": analyzer_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(analyzer_path),
        },
        "scoringDependencies": {
            path.relative_to(repository_root).as_posix(): sha256(path)
            for path in (
                repository_root / "experiments/stt_quality/msner_entity_scoring.py",
                repository_root / "experiments/stt_quality/spanish_numeric_semantics.py",
                repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
            )
        },
        "caseCommitments": case_commitments,
        "oracleUsesDevelopmentReferences": True,
        "candidatePromotable": False,
        "developmentRowsOpened": True,
        "validationBlindOpened": False,
        "finalBlindOpened": False,
        "wakeProgramTree": parakeet_artifact["wakeProgramTree"],
        "fasterWakeProgramTreeMatches": (
            faster_artifact["wakeProgramTree"] == parakeet_artifact["wakeProgramTree"]
        ),
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
    parser.add_argument("--parakeet-artifact", type=Path, required=True)
    parser.add_argument("--parakeet-detail", type=Path, required=True)
    parser.add_argument("--faster-whisper-artifact", type=Path, required=True)
    parser.add_argument("--faster-whisper-detail", type=Path, required=True)
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
