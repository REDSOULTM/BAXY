"""Measure the frozen Parakeet primary on MSNER Spanish development audio.

All 504 candidate transcripts are produced before the manifest containing the
reference text is opened.  Detailed text remains outside the repository.
"""

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


SCHEMA = "baxy.msner-spanish-entity-development-evaluation.v1"
EXTRACTION_SCHEMA = "baxy.msner-spanish-entity-development-extraction.v1"
EXPECTED_CASES = 504
EXPECTED_ROW_GROUPS = [0, 1, 2, 3, 4, 5]
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)
FFMPEG_SHA256 = "227af0691433b703ffc5725e47f7d06eefc34b4a72e7870e73d30e2cda483ecf"
MODEL_FILES = {
    "encoder.int8.onnx": {
        "bytes": 652_184_281,
        "sha256": "acfc2b4456377e15d04f0243af540b7fe7c992f8d898d751cf134c3a55fd2247",
    },
    "decoder.int8.onnx": {
        "bytes": 11_845_275,
        "sha256": "179e50c43d1a9de79c8a24149a2f9bac6eb5981823f2a2ed88d655b24248db4e",
    },
    "joiner.int8.onnx": {
        "bytes": 6_355_277,
        "sha256": "3164c13fc2821009440d20fcb5fdc78bff28b4db2f8d0f0b329101719c0948b3",
    },
    "tokens.txt": {
        "bytes": 93_939,
        "sha256": "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d",
    },
}
THRESHOLDS = {
    "expectedCases": EXPECTED_CASES,
    "minimumNonemptyRate": 1.0,
    "maximumDecodeErrors": 0,
    "maximumCorpusWer": 0.20,
    "minimumEntityExactRecall": 0.99,
    "minimumEntityTokenRecall": 0.99,
    "maximumLatencyP95Seconds": 2.0,
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
        raise RuntimeError(f"msner_entity_module_import_failed:{name}")
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
            raise RuntimeError(f"msner_entity_parakeet_changed:{name}")


def _validate_extraction(
    extraction: dict[str, Any], repository_root: Path
) -> tuple[Path, list[dict[str, str]]]:
    if (
        extraction.get("schema") != EXTRACTION_SCHEMA
        or extraction.get("extraction", {}).get("role") != "development"
        or extraction.get("extraction", {}).get("readRowGroups")
        != EXPECTED_ROW_GROUPS
        or extraction.get("extraction", {}).get("blindShardsRead") != []
        or extraction.get("extraction", {}).get("rows") != EXPECTED_CASES
        or extraction.get("extraction", {}).get("audioFormats") != {"wav": 504}
        or extraction.get("contract", {}).get("validationBlindRowsOpened") is not False
        or extraction.get("contract", {}).get("finalBlindRowsOpened") is not False
        or extraction.get("effectsExecuted") != 0
    ):
        raise RuntimeError("msner_entity_extraction_invalid")
    manifest = Path(str(extraction["extraction"]["manifestPath"])).resolve(strict=True)
    if manifest.is_relative_to(repository_root):
        raise RuntimeError("msner_entity_manifest_must_stay_outside_repository")
    output_root = manifest.parent
    commitments = list(extraction["extraction"].get("rowCommitments", []))
    if len(commitments) != EXPECTED_CASES:
        raise RuntimeError("msner_entity_commitment_population_changed")
    cases: list[dict[str, str]] = []
    for index, commitment in enumerate(commitments):
        case_id = f"msner-es-development-{index:04d}"
        if commitment.get("caseId") != case_id:
            raise RuntimeError("msner_entity_case_order_changed")
        audio = output_root / "audio" / f"{case_id}.wav"
        if not audio.is_file() or sha256(audio) != commitment.get("audioSha256"):
            raise RuntimeError(f"msner_entity_audio_changed:{case_id}")
        cases.append(
            {
                "caseId": case_id,
                "audioPath": str(audio),
                "referenceSha256": str(commitment["referenceSha256"]),
            }
        )
    return manifest, cases


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
        raise RuntimeError("msner_entity_evaluation_output_exists")
    if detail_path.is_relative_to(repository_root):
        raise RuntimeError("msner_entity_detail_must_stay_outside_repository")

    extraction_path = arguments.extraction.resolve(strict=True)
    extraction = json.loads(extraction_path.read_text(encoding="utf-8-sig"))
    manifest_path, cases = _validate_extraction(extraction, repository_root)

    runtime_path = arguments.runtime_manifest.resolve(strict=True)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8-sig"))
    runtime_python = Path(str(runtime["python"])).resolve(strict=True)
    model_root = Path(str(runtime["stt_dir"])).resolve(strict=True)
    ffmpeg = arguments.ffmpeg.resolve(strict=True)
    if (
        runtime.get("schema") != "baxy-mind-runtime-v1"
        or runtime_python != Path(sys.executable).resolve(strict=True)
        or sha256(ffmpeg) != FFMPEG_SHA256
    ):
        raise RuntimeError("msner_entity_runtime_invalid")
    _validate_model(model_root)

    frozen = _load_module(
        "baxy_msner_frozen_stt",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    scoring = _load_module(
        "baxy_msner_entity_scoring",
        repository_root / "experiments/stt_quality/msner_entity_scoring.py",
    )
    wake_tree = frozen._program_tree(repository_root)
    if wake_tree.get("sha256") != EXPECTED_WAKE_TREE_SHA256:
        raise RuntimeError("msner_entity_wake_tree_changed")

    import psutil

    process = psutil.Process()
    peak_rss = process.memory_info().rss
    recognizer = frozen.ParakeetGreedyStt(model_root)
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
        latency: float | None = None
        error: str | None = None
        try:
            raw, transcript, latency = recognizer.transcribe(audio, "es")
        except Exception as exception:  # noqa: BLE001 - preserve every decode failure
            error = type(exception).__name__
        peak_rss = max(peak_rss, process.memory_info().rss)
        audio_seconds = len(audio) / frozen.SAMPLE_RATE
        candidate_rows.append(
            {
                "caseId": case["caseId"],
                "rawTranscript": raw,
                "productTranscript": transcript,
                "latencySeconds": latency,
                "realTimeFactor": (
                    None
                    if latency is None
                    else latency / max(0.001, audio_seconds)
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
        raise RuntimeError("msner_entity_manifest_changed")
    reference_rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(reference_rows) != len(candidate_rows):
        raise RuntimeError("msner_entity_reference_population_changed")

    results: list[dict[str, Any]] = []
    per_type: dict[str, dict[str, int]] = {}
    for candidate, reference_row in zip(candidate_rows, reference_rows, strict=True):
        if candidate["caseId"] != reference_row.get("caseId"):
            raise RuntimeError("msner_entity_reference_order_changed")
        reference = str(reference_row["reference"])
        if hashlib.sha256(reference.encode("utf-8")).hexdigest() != candidate[
            "referenceSha256"
        ]:
            raise RuntimeError("msner_entity_reference_changed")
        labels = list(reference_row["unifiedEntities"])
        entity_score = scoring.score_entity_preservation(
            reference=reference,
            label_ids=labels,
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
                "unifiedEntities": labels,
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
    entity_cases = [row for row in results if int(row["entities"]) > 0]
    latencies = [
        float(row["latencySeconds"])
        for row in results
        if row["latencySeconds"] is not None
    ]
    real_time_factors = [
        float(row["realTimeFactor"])
        for row in results
        if row["realTimeFactor"] is not None
    ]
    elapsed = time.perf_counter() - started
    metrics = {
        "cases": len(results),
        "entityCases": len(entity_cases),
        "entityCasesPerfect": sum(
            bool(row["allEntitiesExactlyPreserved"]) for row in entity_cases
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
        "latencyP50Seconds": _nearest_rank(latencies, 0.50),
        "latencyP95Seconds": _nearest_rank(latencies, 0.95),
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
        "latencyP95": metrics["latencyP95Seconds"]
        <= THRESHOLDS["maximumLatencyP95Seconds"],
        "realTimeFactorP95": metrics["realTimeFactorP95"]
        <= THRESHOLDS["maximumRealTimeFactorP95"],
        "peakRss": metrics["peakRssBytesObserved"]
        <= THRESHOLDS["maximumPeakRssBytes"],
        "effectsExecuted": True,
    }
    detail = {
        "schema": SCHEMA,
        "partition": "development",
        "engine": "parakeet_greedy",
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
    scoring_path = Path(scoring.__file__).resolve(strict=True)
    artifact: dict[str, object] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "engine": "parakeet_greedy",
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
        "scorer": {
            "path": scoring_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(scoring_path),
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
