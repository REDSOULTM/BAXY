"""Evaluate STT candidates on the opened ServiceNow code-switch development set.

Detailed text stays outside the repository because the dataset card does not
declare a license.  The repository artifact contains only metrics, hashes, and
case commitments.  Blind row groups 0 and 1 are never read here.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time
from typing import Any


SCHEMA = "baxy.servicenow-codeswitch-stt-development-evaluation.v1"
EXTRACTION_SCHEMA = "baxy.servicenow-codeswitch-development-extraction.v1"
EXPECTED_CASES = 59
THRESHOLDS = {
    "expectedCases": EXPECTED_CASES,
    "minimumNonemptyRate": 1.0,
    "maximumCorpusWer": 0.20,
    "maximumEnglishReferenceErrorRate": 0.20,
    "maximumSpanishReferenceErrorRate": 0.20,
    "minimumCriticalAnchorRecall": 0.99,
    "maximumLatencyP95Seconds": 2.0,
    "maximumRealTimeFactorP95": 0.5,
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
        raise RuntimeError(f"servicenow_codeswitch_module_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def reference_language_errors(
    reference: list[str], labels: list[str], hypothesis: list[str]
) -> dict[str, dict[str, int]]:
    if len(reference) != len(labels):
        raise ValueError("servicenow_codeswitch_reference_label_mismatch")
    rows = len(reference) + 1
    columns = len(hypothesis) + 1
    distances = [[0] * columns for _ in range(rows)]
    operations = [[""] * columns for _ in range(rows)]
    for index in range(1, rows):
        distances[index][0] = index
        operations[index][0] = "delete"
    for index in range(1, columns):
        distances[0][index] = index
        operations[0][index] = "insert"
    for ref_index in range(1, rows):
        for hyp_index in range(1, columns):
            substitution = distances[ref_index - 1][hyp_index - 1] + (
                reference[ref_index - 1] != hypothesis[hyp_index - 1]
            )
            deletion = distances[ref_index - 1][hyp_index] + 1
            insertion = distances[ref_index][hyp_index - 1] + 1
            best = min(substitution, deletion, insertion)
            distances[ref_index][hyp_index] = best
            if best == substitution:
                operations[ref_index][hyp_index] = (
                    "match"
                    if reference[ref_index - 1] == hypothesis[hyp_index - 1]
                    else "substitute"
                )
            elif best == deletion:
                operations[ref_index][hyp_index] = "delete"
            else:
                operations[ref_index][hyp_index] = "insert"
    counts: dict[str, dict[str, int]] = {}
    for label in labels:
        counts.setdefault(label, {"referenceTokens": 0, "errors": 0})[
            "referenceTokens"
        ] += 1
    ref_index = len(reference)
    hyp_index = len(hypothesis)
    while ref_index or hyp_index:
        operation = operations[ref_index][hyp_index]
        if operation in {"match", "substitute"}:
            if operation == "substitute":
                counts[labels[ref_index - 1]]["errors"] += 1
            ref_index -= 1
            hyp_index -= 1
        elif operation == "delete":
            counts[labels[ref_index - 1]]["errors"] += 1
            ref_index -= 1
        elif operation == "insert":
            hyp_index -= 1
        else:
            raise RuntimeError("servicenow_codeswitch_alignment_failed")
    return counts


def _expanded_reference_words(
    frozen: Any, words: list[object], labels: list[object]
) -> tuple[list[str], list[str]]:
    if len(words) != len(labels):
        raise RuntimeError("servicenow_codeswitch_word_language_count_changed")
    tokens: list[str] = []
    expanded_labels: list[str] = []
    for word, label in zip(words, labels, strict=True):
        normalized = frozen._scoring_tokens(str(word))
        tokens.extend(normalized)
        expanded_labels.extend([str(label).upper()] * len(normalized))
    return tokens, expanded_labels


def _load_cases(extraction: dict[str, Any]) -> tuple[Path, list[dict[str, Any]]]:
    manifest = Path(str(extraction["extraction"]["manifestPath"])).resolve(strict=True)
    if sha256(manifest) != extraction["extraction"]["manifestSha256"]:
        raise RuntimeError("servicenow_codeswitch_manifest_changed")
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != EXPECTED_CASES:
        raise RuntimeError("servicenow_codeswitch_development_population_changed")
    output_root = manifest.parent
    cases: list[dict[str, Any]] = []
    for row in rows:
        audio = output_root / str(row["audioPath"])
        if (
            audio.stat().st_size != row["audioBytes"]
            or sha256(audio) != row["audioSha256"]
        ):
            raise RuntimeError(f"servicenow_codeswitch_audio_changed:{row['caseId']}")
        cases.append(
            {
                "caseId": row["caseId"],
                "sourceRowIndex": row["sourceRowIndex"],
                "voice": row["voice"],
                "path": audio,
                "reference": row["reference"],
                "words": row["words"],
                "wordLanguages": row["wordLanguages"],
                "languageClass": "code_switch",
                "language": "auto",
            }
        )
    return manifest, cases


def _candidate(arguments: argparse.Namespace, frozen: Any, contract: dict[str, Any]):
    if arguments.engine == "parakeet_greedy":
        runtime = json.loads(
            Path(str(contract["runtime"]["path"])).read_text(encoding="utf-8-sig")
        )
        return frozen.ParakeetGreedyStt(Path(str(runtime["stt_dir"])))
    if arguments.engine == "nemotron_auto":
        return frozen.NemotronStreamingStt(
            Path(str(contract["nemotron"]["path"])), "auto"
        )
    qwen_module = _load_module(
        "baxy_qwen3_for_servicenow_codeswitch",
        arguments.repository_root
        / "experiments/stt_quality/evaluate_qwen3_asr_onnx_development.py",
    )
    qwen_module.validate_official_archive(arguments.qwen_archive)
    model_directory = arguments.qwen_directory.resolve(strict=True)
    manifest = qwen_module.model_manifest(model_directory)
    return qwen_module.Qwen3AsrOnnxStt(
        model_directory=model_directory,
        threads=arguments.threads,
        max_new_tokens=128,
        manifest=manifest,
    )


def evaluate(arguments: argparse.Namespace) -> dict[str, object]:
    repository_root = arguments.repository_root.resolve(strict=True)
    arguments.repository_root = repository_root
    artifact_path = arguments.artifact.resolve()
    detail_path = arguments.detail_output.resolve()
    if artifact_path.exists() or detail_path.exists():
        raise RuntimeError("servicenow_codeswitch_evaluation_output_exists")
    if detail_path.is_relative_to(repository_root):
        raise RuntimeError("servicenow_codeswitch_detail_must_stay_outside_repository")
    extraction_path = arguments.extraction.resolve(strict=True)
    extraction = json.loads(extraction_path.read_text(encoding="utf-8-sig"))
    if (
        extraction.get("schema") != EXTRACTION_SCHEMA
        or extraction.get("extraction", {}).get("readRowGroups") != [2]
        or extraction.get("extraction", {}).get("blindRowGroupsRead") != []
        or extraction.get("contract", {}).get("blindRowsOpened") is not False
    ):
        raise RuntimeError("servicenow_codeswitch_extraction_invalid")
    manifest_path, cases = _load_cases(extraction)
    frozen = _load_module(
        "baxy_frozen_stt_for_servicenow_codeswitch",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    contract_path = arguments.base_contract.resolve(strict=True)
    contract, _preregistration, _runtime = frozen._validate_contract(
        repository_root=repository_root,
        contract_path=contract_path,
        source="audio_arena",
        partition="development",
    )
    recognizer = _candidate(arguments, frozen, contract)
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        audio = frozen._load_wav(case["path"])
        result = frozen._case_result(case=case, audio=audio, product_stt=recognizer)
        reference_tokens, labels = _expanded_reference_words(
            frozen, case["words"], case["wordLanguages"]
        )
        result["referenceWordLanguageCounts"] = reference_language_errors(
            reference_tokens,
            labels,
            frozen._scoring_tokens(str(result["productTranscript"])),
        )
        result["referenceSha256"] = hashlib.sha256(
            str(result["reference"]).encode("utf-8")
        ).hexdigest()
        results.append(result)
        if index % 10 == 0 or index == len(cases):
            print(
                json.dumps(
                    {"progress": index, "total": len(cases), "engine": arguments.engine}
                ),
                flush=True,
            )
    usable = [row for row in results if row["usableReference"]]
    reference_tokens = sum(int(row["referenceTokens"]) for row in usable)
    word_errors = sum(int(row["wordErrors"]) for row in usable)
    anchors = sum(len(row["criticalAnchors"]) for row in usable)
    preserved = sum(len(row["criticalAnchorsPreserved"]) for row in usable)
    language_counts = {
        language: {
            "referenceTokens": sum(
                int(row["referenceWordLanguageCounts"].get(language, {}).get("referenceTokens", 0))
                for row in usable
            ),
            "errors": sum(
                int(row["referenceWordLanguageCounts"].get(language, {}).get("errors", 0))
                for row in usable
            ),
        }
        for language in ("EN", "ES")
    }
    for counts in language_counts.values():
        counts["referenceErrorRate"] = round(
            counts["errors"] / max(1, counts["referenceTokens"]), 6
        )
    latencies = [float(row["latencySeconds"]) for row in usable if row["latencySeconds"] is not None]
    real_time_factors = [float(row["realTimeFactor"]) for row in usable if row["realTimeFactor"] is not None]
    metrics = {
        "cases": len(results),
        "usableCases": len(usable),
        "nonemptyRate": round(sum(bool(row["nonempty"]) for row in usable) / max(1, len(usable)), 6),
        "decodeErrors": sum(row["error"] is not None for row in results),
        "referenceTokens": reference_tokens,
        "wordErrors": word_errors,
        "corpusWer": round(word_errors / max(1, reference_tokens), 6),
        "criticalAnchors": anchors,
        "criticalAnchorsPreserved": preserved,
        "criticalAnchorRecall": 1.0 if anchors == 0 else round(preserved / anchors, 6),
        "latencyP50Seconds": _nearest_rank(latencies, 0.50),
        "latencyP95Seconds": _nearest_rank(latencies, 0.95),
        "realTimeFactorP50": _nearest_rank(real_time_factors, 0.50),
        "realTimeFactorP95": _nearest_rank(real_time_factors, 0.95),
        "referenceLanguage": language_counts,
    }
    checks = {
        "expectedCases": metrics["cases"] == THRESHOLDS["expectedCases"],
        "nonemptyRate": metrics["nonemptyRate"] >= THRESHOLDS["minimumNonemptyRate"],
        "decodeErrors": metrics["decodeErrors"] == 0,
        "corpusWer": metrics["corpusWer"] <= THRESHOLDS["maximumCorpusWer"],
        "englishReferenceErrorRate": language_counts["EN"]["referenceErrorRate"]
        <= THRESHOLDS["maximumEnglishReferenceErrorRate"],
        "spanishReferenceErrorRate": language_counts["ES"]["referenceErrorRate"]
        <= THRESHOLDS["maximumSpanishReferenceErrorRate"],
        "criticalAnchorRecall": metrics["criticalAnchorRecall"]
        >= THRESHOLDS["minimumCriticalAnchorRecall"],
        "latencyP95": metrics["latencyP95Seconds"] <= THRESHOLDS["maximumLatencyP95Seconds"],
        "realTimeFactorP95": metrics["realTimeFactorP95"] <= THRESHOLDS["maximumRealTimeFactorP95"],
    }
    detail = {
        "schema": SCHEMA,
        "engine": arguments.engine,
        "partition": "development",
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "cases": results,
        "blindRowGroupsOpened": [],
        "effectsExecuted": 0,
    }
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    evaluator_path = Path(__file__).resolve(strict=True)
    artifact: dict[str, object] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "engine": arguments.engine,
        "partition": "development",
        "status": "passed" if all(checks.values()) else "failed",
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "engineRuntime": {
            "loadSeconds": round(recognizer.load_seconds, 6),
            "status": recognizer.status,
            "peakRssBytesObserved": getattr(recognizer, "peak_rss_bytes", None),
        },
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        "extraction": {"path": extraction_path.relative_to(repository_root).as_posix(), "sha256": sha256(extraction_path)},
        "manifest": {"path": manifest_path.as_posix(), "sha256": sha256(manifest_path)},
        "detail": {"path": detail_path.as_posix(), "sha256": sha256(detail_path)},
        "evaluator": {"path": evaluator_path.relative_to(repository_root).as_posix(), "sha256": sha256(evaluator_path)},
        "caseCommitments": [
            {
                "caseId": row["caseId"],
                "referenceSha256": row["referenceSha256"],
                "transcriptSha256": hashlib.sha256(str(row["productTranscript"]).encode("utf-8")).hexdigest(),
                "wer": row["wer"],
                "latencySeconds": row["latencySeconds"],
            }
            for row in results
        ],
        "developmentOnly": True,
        "syntheticAudio": True,
        "finalPhysicalCertificationEligible": False,
        "blindRowGroupsOpened": [],
        "candidatePromoted": False,
        "wakeProgramTree": frozen._program_tree(repository_root),
        "effectsExecuted": 0,
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--base-contract", type=Path, required=True)
    parser.add_argument("--engine", choices=("parakeet_greedy", "nemotron_auto", "qwen3_auto"), required=True)
    parser.add_argument("--qwen-directory", type=Path)
    parser.add_argument("--qwen-archive", type=Path)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.engine == "qwen3_auto" and (
        arguments.qwen_directory is None or arguments.qwen_archive is None
    ):
        raise ValueError("servicenow_codeswitch_qwen_paths_required")
    artifact = evaluate(arguments)
    print(
        json.dumps(
            {
                "artifact": str(arguments.artifact),
                "engine": artifact["engine"],
                "status": artifact["status"],
                "sha256": sha256(arguments.artifact),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
