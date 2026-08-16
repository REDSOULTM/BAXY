"""Measure Nemotron streaming on the opened MSNER Spanish development shard."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from typing import Any


SCHEMA = "baxy.msner-spanish-nemotron-development-evaluation.v1"
EXPECTED_CASES = 504
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)
FFMPEG_SHA256 = "227af0691433b703ffc5725e47f7d06eefc34b4a72e7870e73d30e2cda483ecf"
MODEL_FILES = {
    "encoder.int8.onnx": {
        "bytes": 657_601_403,
        "sha256": "012e9321373af99021415e0b0eb3ec827b4be3153be6f30d9b448fe65e896e68",
    },
    "decoder.int8.onnx": {
        "bytes": 14_978_075,
        "sha256": "19f9c98fc6d0a2c33a65a43b36fdb2e914c26c0aa9764be3aebc502a1e982fb0",
    },
    "joiner.int8.onnx": {
        "bytes": 9_504_438,
        "sha256": "4101c7c679a0bc30483794b27a059e34e79232aa2068d78d51231a22c8b0d7ce",
    },
    "tokens.txt": {
        "bytes": 131_440,
        "sha256": "729cc103155bafa785f9cd45746cd41cabe97eab7182fc04d594129587958f8a",
    },
}
THRESHOLDS = {
    "expectedCases": EXPECTED_CASES,
    "minimumNonemptyRate": 1.0,
    "maximumDecodeErrors": 0,
    "maximumCorpusWer": 0.20,
    "minimumEntityExactRecall": 0.99,
    "minimumEntityTokenRecall": 0.99,
    "maximumFinalizationLatencyP95Seconds": 1.5,
    "maximumRealTimeFactorP95": 0.5,
    "maximumPeakRssBytes": 4_294_967_296,
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
        raise RuntimeError(f"msner_nemotron_module_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _validate_model(root: Path) -> None:
    for name, expected in MODEL_FILES.items():
        path = root / name
        if (
            not path.is_file()
            or path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise RuntimeError(f"msner_nemotron_model_changed:{name}")


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


def evaluate(arguments: argparse.Namespace) -> dict[str, object]:
    repository_root = arguments.repository_root.resolve(strict=True)
    artifact_path = arguments.artifact.resolve()
    detail_path = arguments.detail_output.resolve()
    if artifact_path.exists() or detail_path.exists():
        raise RuntimeError("msner_nemotron_evaluation_output_exists")
    if detail_path.is_relative_to(repository_root):
        raise RuntimeError("msner_nemotron_detail_must_stay_outside_repository")

    baseline = _load_module(
        "baxy_msner_nemotron_baseline_contract",
        repository_root
        / "experiments/stt_quality/evaluate_msner_spanish_entity_development.py",
    )
    extraction_path = arguments.extraction.resolve(strict=True)
    extraction = json.loads(extraction_path.read_text(encoding="utf-8-sig"))
    manifest_path, cases = baseline._validate_extraction(extraction, repository_root)
    if len(cases) != EXPECTED_CASES:
        raise RuntimeError("msner_nemotron_population_changed")

    runtime_path = arguments.runtime_manifest.resolve(strict=True)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8-sig"))
    runtime_python = Path(str(runtime["python"])).resolve(strict=True)
    model_root = arguments.model_directory.resolve(strict=True)
    ffmpeg = arguments.ffmpeg.resolve(strict=True)
    if (
        runtime.get("schema") != "baxy-mind-runtime-v1"
        or runtime_python != Path(sys.executable).resolve(strict=True)
        or sha256(ffmpeg) != FFMPEG_SHA256
    ):
        raise RuntimeError("msner_nemotron_runtime_invalid")
    _validate_model(model_root)

    frozen = _load_module(
        "baxy_msner_nemotron_frozen_stt",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    scoring = _load_module(
        "baxy_msner_nemotron_entity_scoring",
        repository_root / "experiments/stt_quality/msner_entity_scoring.py",
    )
    wake_tree = frozen._program_tree(repository_root)
    if wake_tree.get("sha256") != EXPECTED_WAKE_TREE_SHA256:
        raise RuntimeError("msner_nemotron_wake_tree_changed")

    import psutil

    process = psutil.Process()
    peak_rss = process.memory_info().rss
    recognizer = frozen.NemotronStreamingStt(model_root, "auto")
    peak_rss = max(peak_rss, process.memory_info().rss)
    started = time.perf_counter()
    candidate_rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        audio_path = Path(case["audioPath"])
        audio = frozen._load_wav_bytes(
            audio_path.read_bytes(), str(audio_path), ffmpeg
        )
        raw = ""
        transcript = ""
        total_cpu_seconds: float | None = None
        diagnostics: dict[str, float] = {}
        error: str | None = None
        try:
            raw, transcript, total_cpu_seconds = recognizer.transcribe(audio, "auto")
            diagnostics = dict(recognizer.last_diagnostics)
        except Exception as exception:  # noqa: BLE001 - preserve every decode failure
            error = type(exception).__name__
        peak_rss = max(peak_rss, process.memory_info().rss)
        audio_seconds = len(audio) / frozen.SAMPLE_RATE
        candidate_rows.append(
            {
                "caseId": case["caseId"],
                "rawTranscript": raw,
                "productTranscript": transcript,
                "totalCpuSeconds": total_cpu_seconds,
                "finalizationLatencySeconds": diagnostics.get(
                    "finalizationLatencySeconds"
                ),
                "maximumChunkDecodeSeconds": diagnostics.get(
                    "maximumChunkDecodeSeconds"
                ),
                "realTimeFactor": (
                    None
                    if total_cpu_seconds is None
                    else total_cpu_seconds / max(0.001, audio_seconds)
                ),
                "audioSeconds": audio_seconds,
                "error": error,
                "referenceSha256": case["referenceSha256"],
            }
        )
        if index % 25 == 0 or index == len(cases):
            print(json.dumps({"progress": index, "total": len(cases)}), flush=True)

    # All candidate outputs are now immutable. Oracle/reference access begins here.
    if sha256(manifest_path) != extraction["extraction"]["manifestSha256"]:
        raise RuntimeError("msner_nemotron_manifest_changed")
    reference_rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(reference_rows) != len(candidate_rows):
        raise RuntimeError("msner_nemotron_reference_population_changed")

    results: list[dict[str, Any]] = []
    per_type: dict[str, dict[str, int]] = {}
    for candidate, reference_row in zip(candidate_rows, reference_rows, strict=True):
        if candidate["caseId"] != reference_row.get("caseId"):
            raise RuntimeError("msner_nemotron_reference_order_changed")
        reference = str(reference_row["reference"])
        if hashlib.sha256(reference.encode("utf-8")).hexdigest() != candidate[
            "referenceSha256"
        ]:
            raise RuntimeError("msner_nemotron_reference_changed")
        entity_score = scoring.score_entity_preservation(
            reference=reference,
            label_ids=list(reference_row["unifiedEntities"]),
            hypothesis=str(candidate["productTranscript"]),
            normalize_tokens=frozen._scoring_tokens,
        )
        reference_tokens = frozen._scoring_tokens(reference)
        hypothesis_tokens = frozen._scoring_tokens(str(candidate["productTranscript"]))
        word_errors = frozen._edit_distance(reference_tokens, hypothesis_tokens)
        _merge_per_type(per_type, entity_score["perType"])
        results.append(
            {
                **candidate,
                "reference": reference,
                "unifiedEntities": list(reference_row["unifiedEntities"]),
                "referenceTokens": len(reference_tokens),
                "wordErrors": word_errors,
                "wer": round(word_errors / max(1, len(reference_tokens)), 6),
                **entity_score,
            }
        )

    reference_tokens = sum(int(row["referenceTokens"]) for row in results)
    word_errors = sum(int(row["wordErrors"]) for row in results)
    entities = sum(int(row["entities"]) for row in results)
    entities_preserved = sum(int(row["entitiesExactlyPreserved"]) for row in results)
    entity_tokens = sum(int(row["entityTokens"]) for row in results)
    entity_tokens_preserved = sum(int(row["entityTokensPreserved"]) for row in results)
    finalization_latencies = [
        float(row["finalizationLatencySeconds"])
        for row in results
        if row["finalizationLatencySeconds"] is not None
    ]
    chunk_latencies = [
        float(row["maximumChunkDecodeSeconds"])
        for row in results
        if row["maximumChunkDecodeSeconds"] is not None
    ]
    real_time_factors = [
        float(row["realTimeFactor"])
        for row in results
        if row["realTimeFactor"] is not None
    ]
    elapsed = time.perf_counter() - started
    metrics = {
        "cases": len(results),
        "entityCases": sum(int(row["entities"]) > 0 for row in results),
        "entityCasesPerfect": sum(
            int(row["entities"]) > 0 and bool(row["allEntitiesExactlyPreserved"])
            for row in results
        ),
        "nonemptyRate": round(
            sum(bool(frozen._scoring_tokens(str(row["productTranscript"]))) for row in results)
            / max(1, len(results)),
            6,
        ),
        "decodeErrors": sum(row["error"] is not None for row in results),
        "referenceTokens": reference_tokens,
        "wordErrors": word_errors,
        "corpusWer": round(word_errors / max(1, reference_tokens), 6),
        "entities": entities,
        "entitiesExactlyPreserved": entities_preserved,
        "entityExactRecall": round(entities_preserved / max(1, entities), 6),
        "entityTokens": entity_tokens,
        "entityTokensPreserved": entity_tokens_preserved,
        "entityTokenRecall": round(
            entity_tokens_preserved / max(1, entity_tokens), 6
        ),
        "finalizationLatencyP50Seconds": _nearest_rank(
            finalization_latencies, 0.50
        ),
        "finalizationLatencyP95Seconds": _nearest_rank(
            finalization_latencies, 0.95
        ),
        "maximumChunkDecodeP95Seconds": _nearest_rank(chunk_latencies, 0.95),
        "realTimeFactorP50": _nearest_rank(real_time_factors, 0.50),
        "realTimeFactorP95": _nearest_rank(real_time_factors, 0.95),
        "peakRssBytesObserved": peak_rss,
        "elapsedSeconds": elapsed,
        "rowsPerSecond": len(results) / max(0.001, elapsed),
        "perType": dict(sorted(per_type.items())),
    }
    checks = {
        "expectedCases": metrics["cases"] == THRESHOLDS["expectedCases"],
        "nonemptyRate": metrics["nonemptyRate"] >= THRESHOLDS["minimumNonemptyRate"],
        "decodeErrors": metrics["decodeErrors"] <= THRESHOLDS["maximumDecodeErrors"],
        "corpusWer": metrics["corpusWer"] <= THRESHOLDS["maximumCorpusWer"],
        "entityExactRecall": metrics["entityExactRecall"]
        >= THRESHOLDS["minimumEntityExactRecall"],
        "entityTokenRecall": metrics["entityTokenRecall"]
        >= THRESHOLDS["minimumEntityTokenRecall"],
        "finalizationLatencyP95": metrics["finalizationLatencyP95Seconds"]
        <= THRESHOLDS["maximumFinalizationLatencyP95Seconds"],
        "realTimeFactorP95": metrics["realTimeFactorP95"]
        <= THRESHOLDS["maximumRealTimeFactorP95"],
        "peakRss": metrics["peakRssBytesObserved"]
        <= THRESHOLDS["maximumPeakRssBytes"],
        "effectsExecuted": True,
    }
    detail = {
        "schema": SCHEMA,
        "partition": "development",
        "engine": "nemotron_auto",
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "cases": results,
        "validationBlindOpened": False,
        "finalBlindOpened": False,
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
        "partition": "development",
        "engine": "nemotron_auto",
        "status": "passed" if all(checks.values()) else "failed",
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "modelRuntime": {
            "path": model_root.as_posix(),
            "files": MODEL_FILES,
            "loadSeconds": recognizer.load_seconds,
            "status": recognizer.status,
        },
        "runtime": {
            "manifest": runtime_path.as_posix(),
            "manifestSha256": sha256(runtime_path),
            "python": runtime_python.as_posix(),
            "pythonSha256": sha256(runtime_python),
        },
        "extraction": {
            "path": extraction_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(extraction_path),
        },
        "manifest": {"path": manifest_path.as_posix(), "sha256": sha256(manifest_path)},
        "detail": {"path": detail_path.as_posix(), "sha256": sha256(detail_path)},
        "evaluator": {
            "path": evaluator_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(evaluator_path),
        },
        "caseCommitments": [
            {
                "caseId": row["caseId"],
                "referenceSha256": row["referenceSha256"],
                "transcriptSha256": hashlib.sha256(
                    str(row["productTranscript"]).encode("utf-8")
                ).hexdigest(),
                "wer": row["wer"],
                "entities": row["entities"],
                "entitiesExactlyPreserved": row["entitiesExactlyPreserved"],
            }
            for row in results
        ],
        "developmentRowsOpened": True,
        "validationBlindOpened": False,
        "finalBlindOpened": False,
        "candidatePromoted": False,
        "wakeProgramTree": wake_tree,
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
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
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
