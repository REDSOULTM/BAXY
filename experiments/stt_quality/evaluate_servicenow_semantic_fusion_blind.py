"""Evaluate the frozen semantic STT candidate on 200 ServiceNow blind rows."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import time
from typing import Any


SCHEMA = "baxy.servicenow-semantic-fusion-blind-evaluation.v1"
PREREG_SCHEMA = "baxy.servicenow-semantic-fusion-blind-preregistration.v1"
EXTRACTION_SCHEMA = "baxy.servicenow-codeswitch-blind-extraction.v1"
EXPECTED_CASES = 200
MODEL_FILES = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt")
_ADDRESS_SUFFIX = re.compile(
    r"(?i)\b(?:avenue|bypass|boulevard|circle|court|drive|highway|lane|"
    r"parkway|place|road|street|trail|view|way)\b"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"semantic_fusion_blind_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def semantic_tree_commitment(root: Path) -> dict[str, object]:
    """Hash importable content, excluding target-path-specific pip launchers."""

    digest = hashlib.sha256()
    files = 0
    total_bytes = 0
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        if (
            "__pycache__" in path.parts
            or path.suffix.casefold() == ".pyc"
            or relative.startswith("bin/")
            or relative.endswith(("/RECORD", "/REQUESTED", "/INSTALLER"))
        ):
            continue
        size = path.stat().st_size
        file_hash = sha256(path)
        digest.update(f"{relative}\t{size}\t{file_hash}\n".encode("utf-8"))
        files += 1
        total_bytes += size
    return {
        "files": files,
        "bytes": total_bytes,
        "sha256": digest.hexdigest(),
    }


def needs_secondary_hypothesis(transcript: str) -> bool:
    return bool(_ADDRESS_SUFFIX.search(transcript) and re.search(r"\b\d{4,6}\b", transcript))


def _validate_files(root: Path, commitments: dict[str, Any], label: str) -> None:
    for name in MODEL_FILES:
        path = root / name
        expected = commitments.get(name)
        if (
            not isinstance(expected, dict)
            or not path.is_file()
            or path.stat().st_size != expected.get("bytes")
            or sha256(path) != expected.get("sha256")
        ):
            raise RuntimeError(f"semantic_fusion_blind_{label}_changed:{name}")


def _load_cases(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = Path(str(extraction["extraction"]["manifestPath"])).resolve(strict=True)
    if sha256(manifest) != extraction["extraction"]["manifestSha256"]:
        raise RuntimeError("semantic_fusion_blind_manifest_changed")
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) != EXPECTED_CASES:
        raise RuntimeError("semantic_fusion_blind_population_changed")
    output_root = manifest.parent
    for index, row in enumerate(rows):
        if row.get("caseId") != f"servicenow-en-es-{index:04d}":
            raise RuntimeError("semantic_fusion_blind_case_order_changed")
        audio = output_root / str(row["audioPath"])
        if (
            not audio.is_file()
            or audio.stat().st_size != row["audioBytes"]
            or sha256(audio) != row["audioSha256"]
        ):
            raise RuntimeError(f"semantic_fusion_blind_audio_changed:{row['caseId']}")
        row["resolvedAudioPath"] = audio
    return rows


def evaluate(arguments: argparse.Namespace) -> dict[str, object]:
    repository_root = arguments.repository_root.resolve(strict=True)
    prereg_path = arguments.preregistration.resolve(strict=True)
    extraction_path = arguments.extraction.resolve(strict=True)
    runtime_path = arguments.runtime_manifest.resolve(strict=True)
    wordfreq_root = arguments.wordfreq_root.resolve(strict=True)
    detail_path = arguments.detail_output.resolve()
    artifact_path = arguments.artifact.resolve()
    if detail_path.exists() or artifact_path.exists():
        raise RuntimeError("semantic_fusion_blind_output_exists")
    if detail_path.is_relative_to(repository_root):
        raise RuntimeError("semantic_fusion_blind_detail_must_stay_outside_repository")

    prereg = json.loads(prereg_path.read_text(encoding="utf-8-sig"))
    extraction = json.loads(extraction_path.read_text(encoding="utf-8-sig"))
    if (
        prereg.get("schema") != PREREG_SCHEMA
        or prereg.get("partition", {}).get("rows") != EXPECTED_CASES
        or prereg.get("partition", {}).get("rowGroups") != [0, 1]
        or prereg.get("contract", {}).get("candidateFrozen") is not True
        or prereg.get("contract", {}).get("blindRowsOpened") is not False
        or prereg.get("contract", {}).get("effectsExecuted") != 0
    ):
        raise RuntimeError("semantic_fusion_blind_preregistration_invalid")
    evaluator_path = Path(__file__).resolve(strict=True)
    if prereg.get("candidate", {}).get("blindEvaluator", {}).get("sha256") != sha256(
        evaluator_path
    ):
        raise RuntimeError("semantic_fusion_blind_evaluator_changed")
    if (
        extraction.get("schema") != EXTRACTION_SCHEMA
        or extraction.get("candidatePreregistration", {}).get("sha256")
        != sha256(prereg_path)
        or extraction.get("extraction", {}).get("readRowGroups") != [0, 1]
        or extraction.get("extraction", {}).get("developmentRowGroupsRead") != []
        or extraction.get("extraction", {}).get("rows") != EXPECTED_CASES
        or extraction.get("contract", {}).get("blindRowsOpened") is not True
        or extraction.get("effectsExecuted") != 0
    ):
        raise RuntimeError("semantic_fusion_blind_extraction_invalid")
    cases = _load_cases(extraction)

    runtime = json.loads(runtime_path.read_text(encoding="utf-8-sig"))
    python_path = Path(str(runtime["python"])).resolve(strict=True)
    if (
        runtime.get("schema") != "baxy-mind-runtime-v1"
        or sha256(runtime_path) != prereg["runtime"]["manifestSha256"]
        or python_path != Path(sys.executable).resolve(strict=True)
        or sha256(python_path) != prereg["runtime"]["pythonSha256"]
    ):
        raise RuntimeError("semantic_fusion_blind_runtime_changed")
    parakeet_root = Path(str(prereg["models"]["parakeet"]["path"])).resolve(strict=True)
    nemotron_root = Path(str(prereg["models"]["nemotron"]["path"])).resolve(strict=True)
    _validate_files(parakeet_root, prereg["models"]["parakeet"]["files"], "parakeet")
    _validate_files(nemotron_root, prereg["models"]["nemotron"]["files"], "nemotron")
    if semantic_tree_commitment(wordfreq_root) != prereg["lexicon"]["semanticTree"]:
        raise RuntimeError("semantic_fusion_blind_lexicon_changed")

    scorer_path = repository_root / "experiments/stt_quality/evaluate_reserved_stt.py"
    source_evaluator_path = (
        repository_root
        / "experiments/stt_quality/evaluate_servicenow_codeswitch_development.py"
    )
    development_evaluator_path = (
        repository_root
        / "experiments/stt_quality/evaluate_servicenow_semantic_fusion_development.py"
    )
    fusion_path = repository_root / "experiments/stt_quality/semantic_stt_fusion_v4.py"
    frozen_paths = {
        "scorer": scorer_path,
        "sourceEvaluator": source_evaluator_path,
        "developmentEvaluator": development_evaluator_path,
        "fusion": fusion_path,
    }
    for key, path in frozen_paths.items():
        if prereg["candidate"][key]["sha256"] != sha256(path):
            raise RuntimeError(f"semantic_fusion_blind_candidate_changed:{key}")
    sys.path.insert(0, str(wordfreq_root))
    frozen = _load_module("baxy_blind_frozen_stt", scorer_path)
    source_evaluator = _load_module(
        "baxy_blind_servicenow_source_evaluator", source_evaluator_path
    )
    development_evaluator = _load_module(
        "baxy_blind_semantic_development_evaluator", development_evaluator_path
    )
    fusion = _load_module("baxy_blind_semantic_fusion_v4", fusion_path)
    lexicon = development_evaluator.WordfreqBilingualLexicon()

    import psutil

    process = psutil.Process()
    peak_rss = process.memory_info().rss
    primary = frozen.ParakeetGreedyStt(parakeet_root)
    peak_rss = max(peak_rss, process.memory_info().rss)
    secondary = frozen.NemotronStreamingStt(nemotron_root, "auto")
    peak_rss = max(peak_rss, process.memory_info().rss)
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        audio = frozen._load_wav(Path(case["resolvedAudioPath"]))
        primary_raw = ""
        primary_text = ""
        primary_latency: float | None = None
        primary_diagnostics: dict[str, float] = {}
        secondary_text: str | None = None
        secondary_total_latency: float | None = None
        secondary_diagnostics: dict[str, float] = {}
        error: str | None = None
        try:
            primary_raw, primary_text, primary_latency = primary.transcribe(audio, "auto")
            primary_diagnostics = dict(primary.last_diagnostics)
            use_secondary = needs_secondary_hypothesis(primary_text)
            alternatives: tuple[str, ...] = ()
            if use_secondary:
                _secondary_raw, secondary_text, secondary_total_latency = secondary.transcribe(
                    audio, "auto"
                )
                secondary_diagnostics = dict(secondary.last_diagnostics)
                alternatives = (secondary_text,)
            semantic = fusion.canonicalize_transcript(
                primary_text,
                alternatives=alternatives,
                lexicon=lexicon,
            )
        except Exception as exception:  # noqa: BLE001 - preserve every blind failure
            error = type(exception).__name__
            use_secondary = False
            semantic = fusion.SemanticTranscript("", (), ())
        peak_rss = max(peak_rss, process.memory_info().rss)

        # The candidate has already produced its output. Reference access starts here.
        reference = str(case["reference"])
        reference_tokens = frozen._scoring_tokens(reference)
        semantic_tokens = frozen._scoring_tokens(semantic.text)
        primary_tokens = frozen._scoring_tokens(primary_text)
        word_errors = frozen._edit_distance(reference_tokens, semantic_tokens)
        anchors = frozen._critical_anchors(reference)
        primary_preserved = [
            anchor for anchor in anchors if frozen._anchor_present(anchor, primary_text)
        ]
        semantic_preserved = [
            anchor for anchor in anchors if frozen._anchor_present(anchor, semantic.text)
        ]
        expanded_reference, labels = source_evaluator._expanded_reference_words(
            frozen,
            list(case["words"]),
            list(case["wordLanguages"]),
        )
        language_counts = source_evaluator.reference_language_errors(
            expanded_reference, labels, semantic_tokens
        )
        audio_seconds = len(audio) / frozen.SAMPLE_RATE
        initial_latency = float(primary_latency or 0.0)
        secondary_endpoint = float(
            secondary_diagnostics.get("finalizationLatencySeconds", 0.0)
        )
        semantic_latency = max(initial_latency, secondary_endpoint)
        clarification_useful = (
            not semantic.requires_clarification
            or len(semantic_preserved) > len(primary_preserved)
        )
        results.append(
            {
                "caseId": case["caseId"],
                "reference": reference,
                "primaryRawTranscript": primary_raw,
                "primaryTranscript": primary_text,
                "secondaryTranscript": secondary_text,
                "semanticTranscript": semantic.text,
                "transformations": list(semantic.transformations),
                "ambiguities": [
                    {
                        "surface": ambiguity.surface,
                        "alternatives": list(ambiguity.alternatives),
                        "reason": ambiguity.reason,
                    }
                    for ambiguity in semantic.ambiguities
                ],
                "requiresClarification": semantic.requires_clarification,
                "clarificationUseful": clarification_useful,
                "secondaryTriggered": use_secondary,
                "nonempty": bool(semantic_tokens),
                "error": error,
                "referenceTokens": len(reference_tokens),
                "wordErrors": word_errors,
                "wer": round(word_errors / max(1, len(reference_tokens)), 6),
                "criticalAnchors": anchors,
                "primaryCriticalAnchorsPreserved": primary_preserved,
                "criticalAnchorsPreserved": semantic_preserved,
                "referenceWordLanguageCounts": language_counts,
                "audioSeconds": audio_seconds,
                "initialSignalLatencySeconds": initial_latency,
                "semanticFinalizationLatencySeconds": semantic_latency,
                "semanticRealTimeFactor": semantic_latency / max(0.001, audio_seconds),
                "primaryDiagnostics": primary_diagnostics,
                "secondaryTotalCpuSeconds": secondary_total_latency,
                "secondaryDiagnostics": secondary_diagnostics,
                "referenceSha256": hashlib.sha256(reference.encode("utf-8")).hexdigest(),
            }
        )
        if index % 25 == 0 or index == len(cases):
            print(json.dumps({"progress": index, "total": len(cases)}), flush=True)

    reference_tokens = sum(int(row["referenceTokens"]) for row in results)
    word_errors = sum(int(row["wordErrors"]) for row in results)
    anchors = sum(len(row["criticalAnchors"]) for row in results)
    preserved = sum(len(row["criticalAnchorsPreserved"]) for row in results)
    language_counts = {
        language: {
            "referenceTokens": sum(
                int(row["referenceWordLanguageCounts"].get(language, {}).get("referenceTokens", 0))
                for row in results
            ),
            "errors": sum(
                int(row["referenceWordLanguageCounts"].get(language, {}).get("errors", 0))
                for row in results
            ),
        }
        for language in ("EN", "ES")
    }
    for counts in language_counts.values():
        counts["referenceErrorRate"] = round(
            counts["errors"] / max(1, counts["referenceTokens"]), 6
        )
    clarification_cases = [row for row in results if row["requiresClarification"]]
    useful_clarifications = sum(row["clarificationUseful"] for row in clarification_cases)
    initial_latencies = [float(row["initialSignalLatencySeconds"]) for row in results]
    semantic_latencies = [float(row["semanticFinalizationLatencySeconds"]) for row in results]
    semantic_rtfs = [float(row["semanticRealTimeFactor"]) for row in results]
    elapsed = time.perf_counter() - started
    metrics = {
        "cases": len(results),
        "nonemptyRate": round(sum(bool(row["nonempty"]) for row in results) / len(results), 6),
        "decodeErrors": sum(row["error"] is not None for row in results),
        "referenceTokens": reference_tokens,
        "wordErrors": word_errors,
        "corpusWer": round(word_errors / max(1, reference_tokens), 6),
        "criticalAnchors": anchors,
        "criticalAnchorsPreserved": preserved,
        "criticalAnchorRecall": round(preserved / max(1, anchors), 6),
        "ambiguities": sum(len(row["ambiguities"]) for row in results),
        "casesRequiringClarification": len(clarification_cases),
        "usefulClarificationCases": useful_clarifications,
        "clarificationUtilityRate": (
            1.0 if not clarification_cases else round(useful_clarifications / len(clarification_cases), 6)
        ),
        "secondaryTriggeredCases": sum(bool(row["secondaryTriggered"]) for row in results),
        "initialSignalLatencyP50Seconds": _nearest_rank(initial_latencies, 0.50),
        "initialSignalLatencyP95Seconds": _nearest_rank(initial_latencies, 0.95),
        "semanticFinalizationLatencyP50Seconds": _nearest_rank(semantic_latencies, 0.50),
        "semanticFinalizationLatencyP95Seconds": _nearest_rank(semantic_latencies, 0.95),
        "semanticRealTimeFactorP50": _nearest_rank(semantic_rtfs, 0.50),
        "semanticRealTimeFactorP95": _nearest_rank(semantic_rtfs, 0.95),
        "peakRssBytesObserved": peak_rss,
        "referenceLanguage": language_counts,
        "elapsedSeconds": elapsed,
        "rowsPerSecond": len(results) / max(0.001, elapsed),
    }
    thresholds = prereg["thresholds"]
    checks = {
        "expectedCases": metrics["cases"] == thresholds["expectedCases"],
        "nonemptyRate": metrics["nonemptyRate"] >= thresholds["minimumNonemptyRate"],
        "decodeErrors": metrics["decodeErrors"] == 0,
        "corpusWer": metrics["corpusWer"] <= thresholds["maximumCorpusWer"],
        "englishReferenceErrorRate": language_counts["EN"]["referenceErrorRate"]
        <= thresholds["maximumEnglishReferenceErrorRate"],
        "spanishReferenceErrorRate": language_counts["ES"]["referenceErrorRate"]
        <= thresholds["maximumSpanishReferenceErrorRate"],
        "criticalAnchorRecall": metrics["criticalAnchorRecall"]
        >= thresholds["minimumCriticalAnchorRecall"],
        "clarificationUtility": metrics["clarificationUtilityRate"]
        >= thresholds["minimumClarificationUtilityRate"],
        "initialSignalLatencyP95": metrics["initialSignalLatencyP95Seconds"]
        <= thresholds["maximumInitialSignalLatencyP95Seconds"],
        "semanticFinalizationLatencyP95": metrics["semanticFinalizationLatencyP95Seconds"]
        <= thresholds["maximumSemanticFinalizationLatencyP95Seconds"],
        "semanticRealTimeFactorP95": metrics["semanticRealTimeFactorP95"]
        <= thresholds["maximumSemanticRealTimeFactorP95"],
        "peakRss": metrics["peakRssBytesObserved"] <= thresholds["maximumPeakRssBytes"],
        "effectsExecuted": True,
    }
    detail = {
        "schema": SCHEMA,
        "partition": "blind",
        "metrics": metrics,
        "checks": checks,
        "thresholds": thresholds,
        "cases": results,
        "blindRowGroupsOpened": [0, 1],
        "effectsExecuted": 0,
    }
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    artifact: dict[str, object] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "partition": "blind",
        "status": "passed" if all(checks.values()) else "failed",
        "metrics": metrics,
        "checks": checks,
        "thresholds": thresholds,
        "modelRuntime": {
            "primary": {"loadSeconds": primary.load_seconds, "status": primary.status},
            "secondary": {"loadSeconds": secondary.load_seconds, "status": secondary.status},
        },
        "preregistration": {
            "path": prereg_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(prereg_path),
        },
        "extraction": {
            "path": extraction_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(extraction_path),
        },
        "detail": {"path": detail_path.as_posix(), "sha256": sha256(detail_path)},
        "evaluator": {
            "path": evaluator_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(evaluator_path),
        },
        "caseCommitments": [
            {
                "caseId": row["caseId"],
                "referenceSha256": row["referenceSha256"],
                "semanticTranscriptSha256": hashlib.sha256(
                    str(row["semanticTranscript"]).encode("utf-8")
                ).hexdigest(),
                "wer": row["wer"],
                "ambiguities": len(row["ambiguities"]),
                "requiresClarification": row["requiresClarification"],
                "clarificationUseful": row["clarificationUseful"],
            }
            for row in results
        ],
        "syntheticAudio": True,
        "supplementalOnly": True,
        "finalPhysicalCertificationEligible": False,
        "candidatePromoted": False,
        "blindRowGroupsOpened": [0, 1],
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
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--wordfreq-root", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    artifact = evaluate(arguments)
    print(
        json.dumps(
            {
                "artifact": str(arguments.artifact),
                "status": artifact["status"],
                "sha256": sha256(arguments.artifact),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
