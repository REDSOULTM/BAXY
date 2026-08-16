"""Measure target-only ONNX TDT phrase boosting on opened MSNER development.

This is an explicit reference-assisted oracle diagnostic.  It may select a
safe algorithm and alpha for later catalog-derived evaluation, but its numbers
must never be presented as blind evidence or promoted directly to product.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys
import time
from typing import Any


SCHEMA = "baxy.msner-spanish-onnx-phrase-boosting-development.v1"
DETAIL_SCHEMA = f"{SCHEMA}.detail"
ALPHAS = (0.0, 0.5, 1.0, 2.0, 4.0, 10.0)
SELECTED_ALPHA = 2.0
EXPECTED_CASES = 15
EXPECTED_TARGETS = 18
BASELINE_DETAIL_SHA256 = (
    "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
)
ORACLE_DETAIL_SHA256 = (
    "2838d74689636ac8cb60938bf56133f97198378f6be897d5e133cc54ab97252d"
)
MANIFEST_SHA256 = (
    "78a299aa0e9603e9b72830ce646805db70e60e99a1a78cb2a86975b451745ad9"
)
THRESHOLDS = {
    "minimumTargetRecoveryRate": 0.50,
    "maximumPreviouslyCorrectEntityDamages": 0,
    "maximumSemanticWerDelta": 0.0,
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
        raise RuntimeError(f"onnx_phrase_boosting_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for index, reference_token in enumerate(reference, start=1):
        current = [index]
        for offset, hypothesis_token in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[offset] + 1,
                    previous[offset - 1] + (reference_token != hypothesis_token),
                )
            )
        previous = current
    return previous[-1]


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _summarize(rows: list[dict[str, Any]], alpha: float) -> dict[str, Any]:
    selected = [row for row in rows if float(row["alpha"]) == alpha]
    latencies = [float(row["latencySeconds"]) for row in selected]
    targets = sum(int(row["targets"]) for row in selected)
    recovered = sum(int(row["targetsRecovered"]) for row in selected)
    damages = sum(len(row["previouslyCorrectEntityDamages"]) for row in selected)
    word_errors = sum(int(row["semanticWordErrors"]) for row in selected)
    reference_words = sum(int(row["semanticReferenceTokens"]) for row in selected)
    return {
        "alpha": alpha,
        "cases": len(selected),
        "targets": targets,
        "targetsRecovered": recovered,
        "targetRecoveryRate": recovered / targets,
        "previouslyCorrectEntityDamages": damages,
        "nonTargetEntityRecoveries": sum(
            len(row["nonTargetEntityRecoveries"]) for row in selected
        ),
        "changedCases": sum(bool(row["changedFromUnboosted"]) for row in selected),
        "semanticWordErrors": word_errors,
        "semanticReferenceTokens": reference_words,
        "semanticWer": word_errors / reference_words,
        "latencyP50Seconds": statistics.median(latencies),
        "latencyP95Seconds": _nearest_rank(latencies, 0.95),
    }


def run(arguments: argparse.Namespace) -> int:
    repository_root = arguments.repository_root.resolve(strict=True)
    artifact_path = arguments.output.resolve()
    detail_path = arguments.detail_output.resolve()
    if artifact_path.exists() or detail_path.exists():
        raise FileExistsError("onnx_phrase_boosting_output_exists")
    if detail_path.is_relative_to(repository_root):
        raise RuntimeError("onnx_phrase_boosting_detail_must_stay_external")

    baseline_path = arguments.baseline_detail.resolve(strict=True)
    oracle_path = arguments.oracle_detail.resolve(strict=True)
    manifest_path = arguments.manifest.resolve(strict=True)
    if sha256(baseline_path) != BASELINE_DETAIL_SHA256:
        raise RuntimeError("onnx_phrase_boosting_baseline_changed")
    if sha256(oracle_path) != ORACLE_DETAIL_SHA256:
        raise RuntimeError("onnx_phrase_boosting_oracle_changed")
    if sha256(manifest_path) != MANIFEST_SHA256:
        raise RuntimeError("onnx_phrase_boosting_manifest_changed")

    boosting_path = repository_root / "experiments/stt_quality/onnx_tdt_phrase_boosting.py"
    scorer_path = repository_root / "experiments/stt_quality/msner_entity_scoring.py"
    numeric_path = repository_root / "experiments/stt_quality/spanish_numeric_semantics.py"
    boosting = _load_module("baxy_onnx_tdt_boosting_eval", boosting_path)
    scorer = _load_module("baxy_msner_scorer_boosting_eval", scorer_path)
    numeric = _load_module("baxy_msner_numeric_boosting_eval", numeric_path)

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    baseline_by_id = {row["caseId"]: row for row in baseline["cases"]}
    manifest_by_id = {
        row["caseId"]: row
        for row in (
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    specs = oracle["cases"]
    if len(specs) != EXPECTED_CASES or sum(
        len(row["targets"]) for row in specs
    ) != EXPECTED_TARGETS:
        raise RuntimeError("onnx_phrase_boosting_population_changed")

    started = time.perf_counter()
    decoder = boosting.OnnxTdtPhraseBoostingDecoder(
        arguments.model.resolve(strict=True),
        dependency_root=arguments.dependency_root.resolve(strict=True),
        num_threads=arguments.num_threads,
    )
    detail_rows: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        case_id = str(spec["caseId"])
        baseline_row = baseline_by_id[case_id]
        manifest_row = manifest_by_id[case_id]
        audio_path = manifest_path.parent / manifest_row["audioPath"]
        audio = boosting.load_wav(audio_path)
        graph = decoder.compile_graph(spec["targetTerms"])
        encoder_out, encoding_seconds = decoder.encode_audio(audio)
        outputs = {
            alpha: decoder.decode_encoded(encoder_out, graph=graph, alpha=alpha)
            for alpha in ALPHAS
        }
        scores = {
            alpha: scorer.score_entity_preservation(
                reference=baseline_row["reference"],
                label_ids=baseline_row["unifiedEntities"],
                hypothesis=outputs[alpha]["text"],
                normalize_tokens=numeric.semantic_tokens,
            )
            for alpha in ALPHAS
        }
        unboosted_commitments = scores[0.0]["entityCommitments"]
        target_indices = {int(target["entityIndex"]) for target in spec["targets"]}
        reference_tokens = numeric.semantic_tokens(baseline_row["reference"])
        for alpha in ALPHAS:
            output = outputs[alpha]
            commitments = scores[alpha]["entityCommitments"]
            detail_rows.append(
                {
                    "caseId": case_id,
                    "alpha": alpha,
                    "targetTerms": spec["targetTerms"],
                    "targets": len(target_indices),
                    "encodedPhraseVariants": graph.phrase_count,
                    "transcript": output["text"],
                    "changedFromUnboosted": output["text"] != outputs[0.0]["text"],
                    "targetsRecovered": sum(
                        commitments[target]["exactlyPreserved"] is True
                        for target in target_indices
                    ),
                    "previouslyCorrectEntityDamages": [
                        entity_index
                        for entity_index, (before, after) in enumerate(
                            zip(unboosted_commitments, commitments, strict=True)
                        )
                        if before["exactlyPreserved"] is True
                        and after["exactlyPreserved"] is False
                    ],
                    "nonTargetEntityRecoveries": [
                        entity_index
                        for entity_index, (before, after) in enumerate(
                            zip(unboosted_commitments, commitments, strict=True)
                        )
                        if entity_index not in target_indices
                        and before["exactlyPreserved"] is False
                        and after["exactlyPreserved"] is True
                    ],
                    "semanticWordErrors": _edit_distance(
                        reference_tokens, numeric.semantic_tokens(output["text"])
                    ),
                    "semanticReferenceTokens": len(reference_tokens),
                    "latencySeconds": encoding_seconds + output["latencySeconds"],
                    "encodingSeconds": encoding_seconds,
                    "decodingSeconds": output["latencySeconds"],
                    "score": scores[alpha],
                }
            )
        print(json.dumps({"progress": index, "total": len(specs)}), flush=True)

    matrix = [_summarize(detail_rows, alpha) for alpha in ALPHAS]
    unboosted = next(row for row in matrix if row["alpha"] == 0.0)
    selected = next(row for row in matrix if row["alpha"] == SELECTED_ALPHA)
    selected["semanticWerDelta"] = selected["semanticWer"] - unboosted["semanticWer"]
    checks = {
        "targetRecoveryRate": selected["targetRecoveryRate"]
        >= THRESHOLDS["minimumTargetRecoveryRate"],
        "previouslyCorrectEntityDamages": selected[
            "previouslyCorrectEntityDamages"
        ]
        <= THRESHOLDS["maximumPreviouslyCorrectEntityDamages"],
        "semanticWerDelta": selected["semanticWerDelta"]
        <= THRESHOLDS["maximumSemanticWerDelta"],
    }
    status = "passed_development_oracle" if all(checks.values()) else "rejected"
    measured_at = datetime.now(timezone.utc).isoformat()
    detail = {
        "schema": DETAIL_SCHEMA,
        "measuredAtUtc": measured_at,
        "partition": "opened_development",
        "diagnosticKind": "reference_assisted_target_only_oracle",
        "candidatePromotable": False,
        "matrix": matrix,
        "cases": detail_rows,
        "validationBlindOpened": False,
        "finalBlindOpened": False,
        "effectsExecuted": 0,
    }
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    artifact = {
        "schema": SCHEMA,
        "measuredAtUtc": measured_at,
        "partition": "opened_development",
        "status": status,
        "diagnosticKind": "reference_assisted_target_only_oracle",
        "candidatePromotable": False,
        "configuration": {
            "alphas": ALPHAS,
            "selectedAlpha": SELECTED_ALPHA,
            "contextScore": 1.0,
            "depthScaling": 2.0,
            "caseAndAccentVariants": True,
            "silenceSeconds": {"leading": 0.2, "trailing": 0.2},
        },
        "matrix": matrix,
        "selected": selected,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "decision": (
            "retain_for_catalog_derived_fresh_evaluation"
            if status == "passed_development_oracle"
            else "reject"
        ),
        "source": {
            "baselineDetail": {
                "path": baseline_path.as_posix(),
                "sha256": BASELINE_DETAIL_SHA256,
            },
            "oracleDetail": {
                "path": oracle_path.as_posix(),
                "sha256": ORACLE_DETAIL_SHA256,
            },
            "manifest": {
                "path": manifest_path.as_posix(),
                "sha256": MANIFEST_SHA256,
            },
            "detail": {"path": detail_path.as_posix(), "sha256": sha256(detail_path)},
        },
        "implementation": {
            "path": boosting_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(boosting_path),
        },
        "elapsedSeconds": time.perf_counter() - started,
        "developmentRowsOpened": True,
        "validationBlindOpened": False,
        "finalBlindOpened": False,
        "effectsExecuted": 0,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": status, "selected": selected}), flush=True)
    return 0 if status == "passed_development_oracle" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--dependency-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline-detail", type=Path, required=True)
    parser.add_argument("--oracle-detail", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--num-threads", type=int, default=6)
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
