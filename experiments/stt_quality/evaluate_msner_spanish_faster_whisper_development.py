"""Measure Faster-Whisper large-v3-turbo on opened MSNER Spanish development.

All candidate transcripts are frozen before this evaluator opens the reference
manifest. Detailed text stays outside the repository. This is development
evidence only and cannot open either reserved MSNER blind shard.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any


SCHEMA = "baxy.msner-spanish-faster-whisper-development-evaluation.v1"
EXPECTED_CASES = 504
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)
MODEL_FILES = {
    "config.json": {
        "bytes": 2_263,
        "sha256": "b0253ea6c0d3bea6b1e19e91a02acfd3b53f4467362efcb5a3e6b16c9b3a9b7e",
    },
    "model.bin": {
        "bytes": 1_617_884_929,
        "sha256": "e76620f83d5f5b69efd3d87e3dc180c1bd21df9fbebacfd4335e5e1efcc018da",
    },
    "preprocessor_config.json": {
        "bytes": 340,
        "sha256": "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711",
    },
    "tokenizer.json": {
        "bytes": 2_710_337,
        "sha256": "297b13372ac43916285644fb9687add3cc62ee2a1adb60da3dc25cc94c1871fd",
    },
    "vocabulary.json": {
        "bytes": 1_068_114,
        "sha256": "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1",
    },
}
PACKAGE_VERSIONS = {
    "faster-whisper": "1.2.1",
    "ctranslate2": "4.8.1",
    "av": "18.0.0",
    "numpy": "2.5.1",
}
REQUIRED_RUNTIME_DLLS = {
    "cublas64_12.dll",
    "cublasLt64_12.dll",
    "cudart64_12.dll",
    "cudnn64_9.dll",
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
        raise RuntimeError(f"msner_faster_whisper_module_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _validate_files(root: Path, expected_files: dict[str, dict[str, object]]) -> None:
    for name, expected in expected_files.items():
        path = root / name
        if (
            not path.is_file()
            or path.stat().st_size != expected["bytes"]
            or sha256(path) != expected["sha256"]
        ):
            raise RuntimeError(f"msner_faster_whisper_component_changed:{name}")


def _wav_seconds(path: Path, expected_sample_rate: int) -> float:
    import av

    with av.open(str(path), mode="r") as source:
        if len(source.streams.audio) != 1:
            raise RuntimeError(f"msner_faster_whisper_audio_changed:{path.name}")
        stream = source.streams.audio[0]
        codec = stream.codec_context
        if (
            codec.channels != 1
            or codec.sample_rate != expected_sample_rate
            or codec.name != "pcm_f32le"
            or stream.duration is None
        ):
            raise RuntimeError(f"msner_faster_whisper_audio_changed:{path.name}")
        return float(stream.duration * stream.time_base)


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


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _peak_rss_bytes() -> int:
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    get_current_process.restype = wintypes.HANDLE
    get_process_memory_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    get_process_memory_info.restype = wintypes.BOOL
    if not get_process_memory_info(
        get_current_process(), ctypes.byref(counters), counters.cb
    ):
        raise ctypes.WinError()
    return int(counters.PeakWorkingSetSize)


def evaluate(arguments: argparse.Namespace) -> dict[str, object]:
    repository_root = arguments.repository_root.resolve(strict=True)
    artifact_path = arguments.artifact.resolve()
    detail_path = arguments.detail_output.resolve()
    if artifact_path.exists() or detail_path.exists():
        raise RuntimeError("msner_faster_whisper_output_exists")
    if detail_path.is_relative_to(repository_root):
        raise RuntimeError("msner_faster_whisper_detail_must_stay_external")

    baseline = _load_module(
        "baxy_msner_faster_whisper_baseline_contract",
        repository_root
        / "experiments/stt_quality/evaluate_msner_spanish_entity_development.py",
    )
    extraction_path = arguments.extraction.resolve(strict=True)
    extraction = json.loads(extraction_path.read_text(encoding="utf-8-sig"))
    manifest_path, cases = baseline._validate_extraction(extraction, repository_root)
    if len(cases) != EXPECTED_CASES:
        raise RuntimeError("msner_faster_whisper_population_changed")

    model_root = arguments.model_directory.resolve(strict=True)
    runtime_dll_directory = arguments.runtime_dll_directory.resolve(strict=True)
    _validate_files(model_root, MODEL_FILES)
    if any(version(name) != expected for name, expected in PACKAGE_VERSIONS.items()):
        raise RuntimeError("msner_faster_whisper_packages_changed")

    frozen = _load_module(
        "baxy_msner_faster_whisper_frozen_stt",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    scoring = _load_module(
        "baxy_msner_faster_whisper_entity_scoring",
        repository_root / "experiments/stt_quality/msner_entity_scoring.py",
    )
    wake_tree = frozen._program_tree(repository_root)
    if wake_tree.get("sha256") != EXPECTED_WAKE_TREE_SHA256:
        raise RuntimeError("msner_faster_whisper_wake_tree_changed")

    dll_files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for pattern in ("cublas*.dll", "cudnn*.dll", "cudart*.dll")
        for path in sorted(runtime_dll_directory.glob(pattern))
    }
    if not REQUIRED_RUNTIME_DLLS.issubset(dll_files):
        raise RuntimeError("msner_faster_whisper_cuda_runtime_missing")
    dll_handle = os.add_dll_directory(str(runtime_dll_directory))
    os.environ["PATH"] = (
        str(runtime_dll_directory) + os.pathsep + os.environ.get("PATH", "")
    )
    os.environ["OMP_NUM_THREADS"] = str(arguments.cpu_threads)

    from faster_whisper import WhisperModel
    import ctranslate2

    if ctranslate2.get_cuda_device_count() < 1:
        raise RuntimeError("msner_faster_whisper_cuda_unavailable")
    load_started = time.perf_counter()
    model = WhisperModel(
        str(model_root),
        device="cuda",
        compute_type="float16",
        cpu_threads=arguments.cpu_threads,
        local_files_only=True,
    )
    load_seconds = time.perf_counter() - load_started
    started = time.perf_counter()
    candidate_rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        audio_path = Path(case["audioPath"])
        audio_seconds = _wav_seconds(audio_path, frozen.SAMPLE_RATE)
        transcript = ""
        detected_language = ""
        language_probability: float | None = None
        error: str | None = None
        decode_started = time.perf_counter()
        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=arguments.language,
                beam_size=arguments.beam_size,
                best_of=arguments.beam_size,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=False,
                without_timestamps=False,
                max_new_tokens=arguments.max_new_tokens,
            )
            transcript = " ".join(
                segment.text.strip() for segment in segments
            ).strip()
            detected_language = str(info.language)
            language_probability = float(info.language_probability)
        except Exception as exception:  # noqa: BLE001 - preserve every failure
            error = type(exception).__name__
        latency = time.perf_counter() - decode_started
        candidate_rows.append(
            {
                "caseId": case["caseId"],
                "productTranscript": transcript,
                "detectedLanguage": detected_language,
                "languageProbability": language_probability,
                "latencySeconds": latency,
                "realTimeFactor": latency / max(0.001, audio_seconds),
                "audioSeconds": audio_seconds,
                "error": error,
                "referenceSha256": case["referenceSha256"],
            }
        )
        if index % 10 == 0 or index == len(cases):
            print(json.dumps({"progress": index, "total": len(cases)}), flush=True)

    # Candidate output is immutable before any oracle text is opened.
    if sha256(manifest_path) != extraction["extraction"]["manifestSha256"]:
        raise RuntimeError("msner_faster_whisper_manifest_changed")
    reference_rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(reference_rows) != len(candidate_rows):
        raise RuntimeError("msner_faster_whisper_reference_population_changed")

    results: list[dict[str, Any]] = []
    per_type: dict[str, dict[str, int]] = {}
    for candidate, reference_row in zip(candidate_rows, reference_rows, strict=True):
        reference = str(reference_row["reference"])
        if (
            candidate["caseId"] != reference_row.get("caseId")
            or hashlib.sha256(reference.encode("utf-8")).hexdigest()
            != candidate["referenceSha256"]
        ):
            raise RuntimeError("msner_faster_whisper_reference_changed")
        entity_score = scoring.score_entity_preservation(
            reference=reference,
            label_ids=list(reference_row["unifiedEntities"]),
            hypothesis=str(candidate["productTranscript"]),
            normalize_tokens=frozen._scoring_tokens,
        )
        reference_tokens = frozen._scoring_tokens(reference)
        hypothesis_tokens = frozen._scoring_tokens(
            str(candidate["productTranscript"])
        )
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
    latencies = [float(row["latencySeconds"]) for row in results]
    real_time_factors = [float(row["realTimeFactor"]) for row in results]
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
        "entityTokenRecall": round(entity_tokens_preserved / max(1, entity_tokens), 6),
        "latencyP50Seconds": _nearest_rank(latencies, 0.50),
        "latencyP95Seconds": _nearest_rank(latencies, 0.95),
        "realTimeFactorP50": _nearest_rank(real_time_factors, 0.50),
        "realTimeFactorP95": _nearest_rank(real_time_factors, 0.95),
        "peakRssBytesObserved": _peak_rss_bytes(),
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
        "engine": "faster_whisper_large_v3_turbo_cuda",
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
        "engine": "faster_whisper_large_v3_turbo_cuda",
        "status": "passed" if all(checks.values()) else "failed",
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "inference": {
            "language": arguments.language,
            "beamSize": arguments.beam_size,
            "bestOf": arguments.beam_size,
            "temperature": 0.0,
            "conditionOnPreviousText": False,
            "vadFilter": False,
            "withoutTimestamps": False,
            "maxNewTokens": arguments.max_new_tokens,
            "hotwords": None,
        },
        "modelRuntime": {
            "path": model_root.as_posix(),
            "files": MODEL_FILES,
            "loadSeconds": load_seconds,
            "packages": PACKAGE_VERSIONS,
            "cudaDeviceCount": ctranslate2.get_cuda_device_count(),
            "runtimeDlls": dll_files,
        },
        "runtime": {
            "python": Path(sys.executable).resolve(strict=True).as_posix(),
            "pythonSha256": sha256(Path(sys.executable).resolve(strict=True)),
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
    del model
    dll_handle.close()
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--runtime-dll-directory", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--language", default="es")
    parser.add_argument("--beam-size", type=int, default=1)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--cpu-threads", type=int, default=8)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if arguments.language not in {"es", "auto"}:
        raise RuntimeError("msner_faster_whisper_language_invalid")
    if arguments.language == "auto":
        arguments.language = None
    if (
        arguments.beam_size < 1
        or arguments.max_new_tokens < 1
        or arguments.cpu_threads < 1
    ):
        raise RuntimeError("msner_faster_whisper_runtime_arguments_invalid")
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
