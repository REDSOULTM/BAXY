"""Map the safe operating region of Parakeet hotwords on MSNER development.

Every target remains oracle-provided.  The matrix is an upper-bound mechanism
diagnostic only; it cannot promote a candidate or open a blind partition.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any


SCHEMA = "baxy.msner-spanish-contextual-hotword-oracle-matrix.v1"
BASELINE_ARTIFACT_SHA256 = (
    "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
)
BASELINE_DETAIL_SHA256 = (
    "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
)
ORACLE_V2_ARTIFACT_SHA256 = (
    "6100a75aba1ec69fc535bf48abc8f96592c645d195675d50e50ece4e11bd6d79"
)
ORACLE_V2_DETAIL_SHA256 = (
    "2838d74689636ac8cb60938bf56133f97198378f6be897d5e133cc54ab97252d"
)
EXTRACTION_SHA256 = (
    "e85fc53af410a753f23c6f790bc53bb41eac1c1b45902d34e2391e88b3194b54"
)
DERIVED_BPE_VOCAB_SHA256 = (
    "a97e38c51a58af225e45571f2c032056240a7680ed7172e265839d7e63a4fead"
)
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)
EXPECTED_CASES = 15
EXPECTED_TARGETS = 18
MAX_ACTIVE_PATHS = 8
SCORES = (0.75, 1.5, 3.0, 5.0)
SHORTLISTS: tuple[tuple[str, int | None], ...] = (
    ("targets_only", None),
    ("maximum_4", 4),
    ("maximum_8", 8),
)
THRESHOLDS = {
    "expectedCases": EXPECTED_CASES,
    "expectedTargets": EXPECTED_TARGETS,
    "minimumTargetRecoveryRate": 0.80,
    "maximumPreviouslyCorrectEntityDamages": 0,
    "maximumDistractorFalseInsertions": 0,
    "maximumSemanticWordErrorDelta": 0,
    "maximumDecodeErrors": 0,
    "maximumNativeHotwordEncodingErrors": 0,
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
        raise RuntimeError(f"msner_contextual_matrix_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _native_error_count(value: str) -> int:
    return value.count("Cannot find ID for token") + value.count(
        "Encode hotwords failed"
    )


def _checks(metrics: dict[str, Any]) -> dict[str, bool]:
    return {
        "selectedCases": metrics["selectedCases"] == THRESHOLDS["expectedCases"],
        "targetEntities": metrics["targetEntities"]
        == THRESHOLDS["expectedTargets"],
        "targetRecoveryRate": metrics["targetRecoveryRate"]
        >= THRESHOLDS["minimumTargetRecoveryRate"],
        "previouslyCorrectEntityDamages": metrics["previouslyCorrectEntityDamages"]
        <= THRESHOLDS["maximumPreviouslyCorrectEntityDamages"],
        "distractorFalseInsertions": metrics["distractorFalseInsertions"]
        <= THRESHOLDS["maximumDistractorFalseInsertions"],
        "semanticWordErrorDelta": metrics["semanticWordErrorDelta"]
        <= THRESHOLDS["maximumSemanticWordErrorDelta"],
        "decodeErrors": metrics["decodeErrors"]
        <= THRESHOLDS["maximumDecodeErrors"],
        "nativeHotwordEncodingErrors": metrics["nativeHotwordEncodingErrors"]
        <= THRESHOLDS["maximumNativeHotwordEncodingErrors"],
        "latencyP95": metrics["latencyP95Seconds"]
        <= THRESHOLDS["maximumLatencyP95Seconds"],
        "realTimeFactorP95": metrics["realTimeFactorP95"]
        <= THRESHOLDS["maximumRealTimeFactorP95"],
        "peakRss": metrics["peakRssBytesObserved"]
        <= THRESHOLDS["maximumPeakRssBytes"],
        "effectsExecuted": True,
    }


class MatrixRecognizer:
    def __init__(self, model_root: Path, bpe_vocab: Path, score: float) -> None:
        import numpy as np
        import sherpa_onnx

        started = time.perf_counter()
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(model_root / "encoder.int8.onnx"),
            decoder=str(model_root / "decoder.int8.onnx"),
            joiner=str(model_root / "joiner.int8.onnx"),
            tokens=str(model_root / "tokens.txt"),
            num_threads=max(2, min(6, (os.cpu_count() or 4) // 2)),
            model_type="nemo_transducer",
            decoding_method="modified_beam_search",
            max_active_paths=MAX_ACTIVE_PATHS,
            hotwords_score=score,
            modeling_unit="bpe",
            bpe_vocab=str(bpe_vocab),
        )
        self.load_seconds = time.perf_counter() - started
        stream = self._recognizer.create_stream()
        stream.accept_waveform(16_000, np.zeros(8_000, dtype=np.float32))
        self._recognizer.decode_stream(stream)

    def transcribe(self, audio, hotwords: str, frozen) -> tuple[str, float]:
        stream = self._recognizer.create_stream(hotwords=hotwords)
        stream.accept_waveform(frozen.SAMPLE_RATE, frozen._with_silence(audio))
        started = time.perf_counter()
        self._recognizer.decode_stream(stream)
        return str(stream.result.text or "").strip(), time.perf_counter() - started


def _terms_for(case: dict[str, Any], maximum: int | None) -> list[str]:
    targets = list(dict.fromkeys(str(term) for term in case["targetTerms"]))
    if maximum is None:
        return targets
    capacity = max(0, maximum - len(targets))
    return [*targets, *(str(term) for term in case["distractorTerms"][:capacity])]


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    repository_root = arguments.repository_root.resolve(strict=True)
    output = arguments.output.resolve()
    detail_output = arguments.detail_output.resolve()
    native_stderr_output = arguments.native_stderr_output.resolve()
    if any(path.exists() for path in (output, detail_output, native_stderr_output)):
        raise RuntimeError("msner_contextual_matrix_output_exists")
    if any(
        path.is_relative_to(repository_root)
        for path in (detail_output, native_stderr_output)
    ):
        raise RuntimeError("msner_contextual_matrix_detail_must_be_external")

    source_paths = {
        "baselineArtifact": arguments.baseline_artifact.resolve(strict=True),
        "baselineDetail": arguments.baseline_detail.resolve(strict=True),
        "oracleV2Artifact": arguments.oracle_v2_artifact.resolve(strict=True),
        "oracleV2Detail": arguments.oracle_v2_detail.resolve(strict=True),
        "extraction": arguments.extraction.resolve(strict=True),
        "derivedBpeVocab": arguments.derived_bpe_vocab.resolve(strict=True),
    }
    expected_hashes = {
        "baselineArtifact": BASELINE_ARTIFACT_SHA256,
        "baselineDetail": BASELINE_DETAIL_SHA256,
        "oracleV2Artifact": ORACLE_V2_ARTIFACT_SHA256,
        "oracleV2Detail": ORACLE_V2_DETAIL_SHA256,
        "extraction": EXTRACTION_SHA256,
        "derivedBpeVocab": DERIVED_BPE_VOCAB_SHA256,
    }
    if any(sha256(source_paths[key]) != value for key, value in expected_hashes.items()):
        raise RuntimeError("msner_contextual_matrix_source_hash_changed")
    baseline_artifact = json.loads(
        source_paths["baselineArtifact"].read_text(encoding="utf-8-sig")
    )
    baseline_detail = json.loads(
        source_paths["baselineDetail"].read_text(encoding="utf-8-sig")
    )
    oracle_artifact = json.loads(
        source_paths["oracleV2Artifact"].read_text(encoding="utf-8-sig")
    )
    oracle_detail = json.loads(
        source_paths["oracleV2Detail"].read_text(encoding="utf-8-sig")
    )
    extraction = json.loads(
        source_paths["extraction"].read_text(encoding="utf-8-sig")
    )
    if (
        oracle_artifact.get("status") != "failed"
        or oracle_artifact.get("metrics", {}).get("nativeHotwordEncodingErrors") != 0
        or oracle_artifact.get("oracleTargetProvidedToAsr") is not True
        or len(oracle_detail.get("cases", [])) != EXPECTED_CASES
        or baseline_artifact.get("validationBlindOpened") is not False
        or baseline_artifact.get("finalBlindOpened") is not False
        or baseline_artifact.get("wakeProgramTree", {}).get("sha256")
        != EXPECTED_WAKE_TREE_SHA256
        or any(
            source.get("effectsExecuted") != 0
            for source in (baseline_artifact, baseline_detail, oracle_detail)
        )
    ):
        raise RuntimeError("msner_contextual_matrix_source_invalid")

    baseline_evaluator = _load_module(
        "baxy_msner_matrix_baseline",
        repository_root
        / "experiments/stt_quality/evaluate_msner_spanish_entity_development.py",
    )
    oracle_evaluator = _load_module(
        "baxy_msner_matrix_oracle",
        repository_root
        / "experiments/stt_quality/evaluate_msner_spanish_contextual_hotword_oracle.py",
    )
    frozen = _load_module(
        "baxy_msner_matrix_frozen",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    scorer = _load_module(
        "baxy_msner_matrix_scorer",
        repository_root / "experiments/stt_quality/msner_entity_scoring.py",
    )
    numeric = _load_module(
        "baxy_msner_matrix_numeric",
        repository_root / "experiments/stt_quality/spanish_numeric_semantics.py",
    )
    compiler = _load_module(
        "baxy_msner_matrix_compiler",
        repository_root / "experiments/stt_quality/contextual_hotwords.py",
    )

    wake_tree = frozen._program_tree(repository_root)
    if wake_tree.get("sha256") != EXPECTED_WAKE_TREE_SHA256:
        raise RuntimeError("msner_contextual_matrix_wake_tree_changed")
    _manifest, audio_cases = baseline_evaluator._validate_extraction(
        extraction, repository_root
    )
    audio_by_case = {case["caseId"]: case for case in audio_cases}
    baseline_by_case = {
        str(case["caseId"]): case for case in baseline_detail["cases"]
    }

    runtime_path = arguments.runtime_manifest.resolve(strict=True)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8-sig"))
    runtime_python = Path(str(runtime["python"])).resolve(strict=True)
    model_root = Path(str(runtime["stt_dir"])).resolve(strict=True)
    ffmpeg = arguments.ffmpeg.resolve(strict=True)
    if (
        runtime.get("schema") != "baxy-mind-runtime-v1"
        or runtime_python != Path(sys.executable).resolve(strict=True)
        or sha256(ffmpeg) != baseline_evaluator.FFMPEG_SHA256
    ):
        raise RuntimeError("msner_contextual_matrix_runtime_invalid")
    baseline_evaluator._validate_model(model_root)

    selected_cases = list(oracle_detail["cases"])
    if sum(len(case["targets"]) for case in selected_cases) != EXPECTED_TARGETS:
        raise RuntimeError("msner_contextual_matrix_target_population_changed")
    loaded_audio: dict[str, Any] = {}
    for case in selected_cases:
        case_id = str(case["caseId"])
        audio_path = Path(str(audio_by_case[case_id]["audioPath"]))
        loaded_audio[case_id] = frozen._load_wav_bytes(
            audio_path.read_bytes(), str(audio_path), ffmpeg
        )

    import psutil

    native_stderr_output.parent.mkdir(parents=True, exist_ok=True)
    native_stderr_output.write_bytes(b"")
    process = psutil.Process()
    peak_rss = process.memory_info().rss
    run_started = time.perf_counter()
    configuration_details: list[dict[str, Any]] = []
    load_seconds: dict[str, float] = {}
    progress = 0
    total = len(SCORES) * len(SHORTLISTS) * len(selected_cases)
    for score in SCORES:
        recognizer = MatrixRecognizer(
            model_root, source_paths["derivedBpeVocab"], score
        )
        load_seconds[str(score)] = recognizer.load_seconds
        peak_rss = max(peak_rss, process.memory_info().rss)
        for shortlist_name, maximum in SHORTLISTS:
            native_start = native_stderr_output.stat().st_size
            case_results: list[dict[str, Any]] = []
            for selected in selected_cases:
                case_id = str(selected["caseId"])
                baseline_row = baseline_by_case[case_id]
                terms = _terms_for(selected, maximum)
                stream_hotwords = compiler.compile_stream_phrases(
                    terms, maximum_terms=max(len(terms), 1)
                )
                transcript = ""
                latency: float | None = None
                error: str | None = None
                try:
                    with oracle_evaluator._capture_native_stderr(
                        native_stderr_output
                    ):
                        transcript, latency = recognizer.transcribe(
                            loaded_audio[case_id], stream_hotwords, frozen
                        )
                except Exception as exception:  # noqa: BLE001
                    error = type(exception).__name__
                peak_rss = max(peak_rss, process.memory_info().rss)

                reference = str(baseline_row["reference"])
                baseline_transcript = str(baseline_row["productTranscript"])
                labels = list(baseline_row["unifiedEntities"])
                baseline_score = scorer.score_entity_preservation(
                    reference=reference,
                    label_ids=labels,
                    hypothesis=baseline_transcript,
                    normalize_tokens=numeric.semantic_tokens,
                )
                contextual_score = scorer.score_entity_preservation(
                    reference=reference,
                    label_ids=labels,
                    hypothesis=transcript,
                    normalize_tokens=numeric.semantic_tokens,
                )
                before = baseline_score["entityCommitments"]
                after = contextual_score["entityCommitments"]
                target_indices = {
                    int(target["entityIndex"]) for target in selected["targets"]
                }
                reference_tokens = numeric.semantic_tokens(reference)
                baseline_tokens = numeric.semantic_tokens(baseline_transcript)
                contextual_tokens = numeric.semantic_tokens(transcript)
                selected_distractors = terms[len(selected["targetTerms"]) :]
                distractor_false_insertions = [
                    term
                    for term in selected_distractors
                    if not oracle_evaluator._sequence_present(
                        reference_tokens, numeric.semantic_tokens(term)
                    )
                    and not oracle_evaluator._sequence_present(
                        baseline_tokens, numeric.semantic_tokens(term)
                    )
                    and oracle_evaluator._sequence_present(
                        contextual_tokens, numeric.semantic_tokens(term)
                    )
                ]
                audio_seconds = len(loaded_audio[case_id]) / frozen.SAMPLE_RATE
                case_results.append(
                    {
                        "caseId": case_id,
                        "terms": terms,
                        "streamHotwords": stream_hotwords,
                        "baselineTranscript": baseline_transcript,
                        "contextualTranscript": transcript,
                        "targets": selected["targets"],
                        "targetsRecovered": sum(
                            after[index]["exactlyPreserved"] is True
                            for index in target_indices
                        ),
                        "previouslyCorrectEntityDamages": [
                            index
                            for index, (old, new) in enumerate(
                                zip(before, after, strict=True)
                            )
                            if old["exactlyPreserved"] is True
                            and new["exactlyPreserved"] is False
                        ],
                        "distractorFalseInsertions": distractor_false_insertions,
                        "semanticReferenceTokens": len(reference_tokens),
                        "baselineSemanticWordErrors": frozen._edit_distance(
                            reference_tokens, baseline_tokens
                        ),
                        "contextualSemanticWordErrors": frozen._edit_distance(
                            reference_tokens, contextual_tokens
                        ),
                        "latencySeconds": latency,
                        "realTimeFactor": (
                            None
                            if latency is None
                            else latency / max(0.001, audio_seconds)
                        ),
                        "error": error,
                    }
                )
                progress += 1
                if progress % 15 == 0 or progress == total:
                    print(json.dumps({"progress": progress, "total": total}), flush=True)

            native_bytes = native_stderr_output.read_bytes()[native_start:]
            native_text = native_bytes.decode("utf-8", errors="replace")
            latencies = [
                float(case["latencySeconds"])
                for case in case_results
                if case["latencySeconds"] is not None
            ]
            rtfs = [
                float(case["realTimeFactor"])
                for case in case_results
                if case["realTimeFactor"] is not None
            ]
            baseline_errors = sum(
                int(case["baselineSemanticWordErrors"]) for case in case_results
            )
            contextual_errors = sum(
                int(case["contextualSemanticWordErrors"]) for case in case_results
            )
            reference_tokens = sum(
                int(case["semanticReferenceTokens"]) for case in case_results
            )
            recovered = sum(int(case["targetsRecovered"]) for case in case_results)
            metrics = {
                "selectedCases": len(case_results),
                "targetEntities": EXPECTED_TARGETS,
                "targetsRecovered": recovered,
                "targetRecoveryRate": round(recovered / EXPECTED_TARGETS, 6),
                "previouslyCorrectEntityDamages": sum(
                    len(case["previouslyCorrectEntityDamages"])
                    for case in case_results
                ),
                "distractorFalseInsertions": sum(
                    len(case["distractorFalseInsertions"])
                    for case in case_results
                ),
                "semanticReferenceTokens": reference_tokens,
                "baselineSemanticWordErrors": baseline_errors,
                "contextualSemanticWordErrors": contextual_errors,
                "semanticWordErrorDelta": contextual_errors - baseline_errors,
                "contextualSemanticWer": round(
                    contextual_errors / max(1, reference_tokens), 6
                ),
                "decodeErrors": sum(case["error"] is not None for case in case_results),
                "nativeHotwordEncodingErrors": _native_error_count(native_text),
                "latencyP50Seconds": _nearest_rank(latencies, 0.50),
                "latencyP95Seconds": _nearest_rank(latencies, 0.95),
                "realTimeFactorP50": _nearest_rank(rtfs, 0.50),
                "realTimeFactorP95": _nearest_rank(rtfs, 0.95),
                "peakRssBytesObserved": peak_rss,
            }
            checks = _checks(metrics)
            configuration_details.append(
                {
                    "configurationId": f"score_{score:g}_{shortlist_name}",
                    "hotwordsScore": score,
                    "shortlist": shortlist_name,
                    "maximumTerms": maximum,
                    "metrics": metrics,
                    "checks": checks,
                    "passed": all(checks.values()),
                    "cases": case_results,
                }
            )

    passing = [
        item["configurationId"] for item in configuration_details if item["passed"]
    ]
    ranked = sorted(
        configuration_details,
        key=lambda item: (
            -item["metrics"]["targetRecoveryRate"],
            item["metrics"]["previouslyCorrectEntityDamages"],
            item["metrics"]["distractorFalseInsertions"],
            item["metrics"]["semanticWordErrorDelta"],
            item["metrics"]["latencyP95Seconds"],
        ),
    )
    elapsed = time.perf_counter() - run_started
    aggregate_configurations = [
        {
            key: value
            for key, value in configuration.items()
            if key != "cases"
        }
        for configuration in configuration_details
    ]
    detail = {
        "schema": SCHEMA,
        "partition": "development",
        "oracleTargetProvidedToAsr": True,
        "candidatePromotable": False,
        "thresholds": THRESHOLDS,
        "configurations": configuration_details,
        "developmentRowsOpened": True,
        "validationBlindOpened": False,
        "finalBlindOpened": False,
        "effectsExecuted": 0,
    }
    detail_output.parent.mkdir(parents=True, exist_ok=True)
    detail_output.write_text(
        json.dumps(detail, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    evaluator_path = Path(__file__).resolve(strict=True)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "status": "passed" if passing else "failed",
        "oracleTargetProvidedToAsr": True,
        "candidatePromotable": False,
        "matrix": {
            "scores": list(SCORES),
            "shortlists": [name for name, _maximum in SHORTLISTS],
            "configurations": aggregate_configurations,
            "passingConfigurations": passing,
            "bestObservedConfiguration": ranked[0]["configurationId"],
            "elapsedSeconds": elapsed,
        },
        "thresholds": THRESHOLDS,
        "decision": {
            "candidatePromoted": False,
            "contextualHotwordArchitectureRetained": bool(passing),
            "validationBlindMayOpen": False,
            "finalBlindMayOpen": False,
            "nextStep": (
                "develop_reference_independent_selector"
                if passing
                else "reject_sherpa_contextual_hotwords_and_pivot"
            ),
        },
        "sources": {
            key: {"path": path.as_posix(), "sha256": expected_hashes[key]}
            for key, path in source_paths.items()
        },
        "detail": {"path": detail_output.as_posix(), "sha256": sha256(detail_output)},
        "nativeStderr": {
            "path": native_stderr_output.as_posix(),
            "sha256": sha256(native_stderr_output),
            "encodingErrors": _native_error_count(
                native_stderr_output.read_text(encoding="utf-8", errors="replace")
            ),
        },
        "runtime": {
            "manifest": runtime_path.as_posix(),
            "manifestSha256": sha256(runtime_path),
            "python": runtime_python.as_posix(),
            "pythonSha256": sha256(runtime_python),
            "modelRoot": model_root.as_posix(),
            "modelFiles": baseline_evaluator.MODEL_FILES,
            "recognizerLoadSecondsByScore": load_seconds,
            "peakRssBytesObserved": peak_rss,
        },
        "evaluator": {
            "path": evaluator_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(evaluator_path),
        },
        "configurationCommitments": [
            {
                "configurationId": configuration["configurationId"],
                "transcriptSetSha256": hashlib.sha256(
                    json.dumps(
                        [
                            {
                                "caseId": case["caseId"],
                                "transcriptSha256": hashlib.sha256(
                                    str(case["contextualTranscript"]).encode("utf-8")
                                ).hexdigest(),
                            }
                            for case in configuration["cases"]
                        ],
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            }
            for configuration in configuration_details
        ],
        "developmentRowsOpened": True,
        "validationBlindOpened": False,
        "finalBlindOpened": False,
        "wakeProgramTree": wake_tree,
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
    parser.add_argument("--baseline-artifact", type=Path, required=True)
    parser.add_argument("--baseline-detail", type=Path, required=True)
    parser.add_argument("--oracle-v2-artifact", type=Path, required=True)
    parser.add_argument("--oracle-v2-detail", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--derived-bpe-vocab", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--native-stderr-output", type=Path, required=True)
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
