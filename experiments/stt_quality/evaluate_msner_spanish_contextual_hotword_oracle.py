"""Probe Parakeet contextual hotwords on opened MSNER Spanish development data.

This is intentionally an oracle-contained mechanism diagnostic: each selected
missed entity is supplied to the recognizer.  It cannot promote a product
candidate or authorize opening either blind partition.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import ctypes
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


SCHEMA = "baxy.msner-spanish-contextual-hotword-oracle-development.v2"
SOURCE_ARTIFACT_SHA256 = (
    "e988aab17c350aa0c026673a3b4f00b0173b7e5b57de945dbb29d5974f258a12"
)
SOURCE_DETAIL_SHA256 = (
    "1d0b32a62b2ebe25854fe62e5bc9118eeea85b9389cb5ebe52a80ceefab8d9be"
)
EXTRACTION_SHA256 = (
    "e85fc53af410a753f23c6f790bc53bb41eac1c1b45902d34e2391e88b3194b54"
)
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)
EXPECTED_SELECTED_CASES = 15
EXPECTED_TARGET_ENTITIES = 18
MAXIMUM_HOTWORDS = 64
MAX_ACTIVE_PATHS = 8
HOTWORDS_SCORE = 5.0
INVALID_V1_ARTIFACT_SHA256 = (
    "f8a3ae6d662a31e7923ead6741a44afc3f2fb7bab53c23d661fd57bcb63852a8"
)
INVALID_V1_DETAIL_SHA256 = (
    "66ddd7588b3891cdf0cd3f27f4d299cde9242ac1f7893968c1b2a0f3f4ab13cb"
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
    "expectedSelectedCases": EXPECTED_SELECTED_CASES,
    "expectedTargetEntities": EXPECTED_TARGET_ENTITIES,
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
        raise RuntimeError(f"msner_contextual_import_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


@contextmanager
def _capture_native_stderr(path: Path):
    """Append native sherpa diagnostics emitted directly to descriptor 2."""

    with path.open("ab", buffering=0) as sink:
        saved = os.dup(2)
        os.dup2(sink.fileno(), 2)
        try:
            yield
        finally:
            try:
                ctypes.CDLL("msvcrt").fflush(None)
            except OSError:
                pass
            os.dup2(saved, 2)
            os.close(saved)


def _sequence_present(tokens: list[str], sequence: list[str]) -> bool:
    if not sequence:
        return False
    return any(
        tokens[index : index + len(sequence)] == sequence
        for index in range(len(tokens) - len(sequence) + 1)
    )


def _surface_key(surface: str, normalize_tokens) -> tuple[str, ...]:
    return tuple(normalize_tokens(surface))


def build_oracle_case_specs(
    rows: list[dict[str, Any]],
    *,
    normalize_tokens,
    maximum_hotwords: int = MAXIMUM_HOTWORDS,
) -> list[dict[str, Any]]:
    """Select only named misses whose exact surface occurs in another case."""

    inventory: dict[tuple[str, ...], dict[str, Any]] = defaultdict(
        lambda: {"surfaces": Counter(), "caseIds": set(), "occurrences": []}
    )
    for row in rows:
        case_id = str(row["caseId"])
        for entity_index, entity in enumerate(row["entityCommitments"]):
            if str(entity["type"]) in NUMERIC_TYPES:
                continue
            surface = str(entity["surface"])
            key = _surface_key(surface, normalize_tokens)
            if not key:
                continue
            item = inventory[key]
            item["surfaces"][surface] += 1
            item["caseIds"].add(case_id)
            item["occurrences"].append((case_id, entity_index))

    selected: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row["caseId"])
        targets: list[dict[str, Any]] = []
        reference_keys: set[tuple[str, ...]] = set()
        for entity_index, entity in enumerate(row["entityCommitments"]):
            if str(entity["type"]) in NUMERIC_TYPES:
                continue
            surface = str(entity["surface"])
            key = _surface_key(surface, normalize_tokens)
            if not key:
                continue
            reference_keys.add(key)
            if (
                entity.get("exactlyPreserved") is False
                and bool(inventory[key]["caseIds"] - {case_id})
            ):
                targets.append(
                    {
                        "entityIndex": entity_index,
                        "type": str(entity["type"]),
                        "surface": surface,
                        "surfaceKey": key,
                    }
                )
        if not targets:
            continue

        target_keys = {target["surfaceKey"] for target in targets}
        target_terms = list(
            dict.fromkeys(str(target["surface"]) for target in targets)
        )
        ranked_distractors: list[tuple[int, tuple[str, ...], str]] = []
        for key, item in inventory.items():
            if key in reference_keys or key in target_keys:
                continue
            other_occurrences = sum(
                occurrence_case != case_id
                for occurrence_case, _index in item["occurrences"]
            )
            if not other_occurrences:
                continue
            canonical = sorted(
                item["surfaces"],
                key=lambda value: (-item["surfaces"][value], value.casefold()),
            )[0]
            ranked_distractors.append((other_occurrences, key, canonical))
        ranked_distractors.sort(key=lambda item: (-item[0], item[1], item[2]))
        distractors = [
            surface
            for _count, _key, surface in ranked_distractors[
                : max(0, maximum_hotwords - len(target_terms))
            ]
        ]
        selected.append(
            {
                "caseId": case_id,
                "targets": targets,
                "targetTerms": target_terms,
                "distractorTerms": distractors,
                "hotwordTerms": [*target_terms, *distractors],
            }
        )
    return selected


class ContextualRecognizer:
    """Parakeet modified-beam recognizer matching the product experiment knobs."""

    def __init__(self, model_root: Path, bpe_vocab: Path) -> None:
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
            hotwords_score=HOTWORDS_SCORE,
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
        latency = time.perf_counter() - started
        return str(stream.result.text or "").strip(), latency


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    repository_root = arguments.repository_root.resolve(strict=True)
    output = arguments.output.resolve()
    detail_output = arguments.detail_output.resolve()
    native_stderr_output = arguments.native_stderr_output.resolve()
    bpe_vocab_output = arguments.derived_bpe_vocab.resolve()
    if (
        output.exists()
        or detail_output.exists()
        or native_stderr_output.exists()
        or bpe_vocab_output.exists()
    ):
        raise RuntimeError("msner_contextual_output_exists")
    if any(
        path.is_relative_to(repository_root)
        for path in (detail_output, native_stderr_output, bpe_vocab_output)
    ):
        raise RuntimeError("msner_contextual_detail_must_stay_outside_repository")

    source_artifact_path = arguments.source_artifact.resolve(strict=True)
    source_detail_path = arguments.source_detail.resolve(strict=True)
    extraction_path = arguments.extraction.resolve(strict=True)
    source_artifact = json.loads(source_artifact_path.read_text(encoding="utf-8-sig"))
    source_detail = json.loads(source_detail_path.read_text(encoding="utf-8-sig"))
    extraction = json.loads(extraction_path.read_text(encoding="utf-8-sig"))
    if (
        sha256(source_artifact_path) != SOURCE_ARTIFACT_SHA256
        or sha256(source_detail_path) != SOURCE_DETAIL_SHA256
        or sha256(extraction_path) != EXTRACTION_SHA256
        or source_artifact.get("detail", {}).get("sha256")
        != SOURCE_DETAIL_SHA256
        or source_artifact.get("wakeProgramTree", {}).get("sha256")
        != EXPECTED_WAKE_TREE_SHA256
        or source_artifact.get("validationBlindOpened") is not False
        or source_artifact.get("finalBlindOpened") is not False
        or source_detail.get("validationBlindOpened") is not False
        or source_detail.get("finalBlindOpened") is not False
        or source_artifact.get("effectsExecuted") != 0
        or source_detail.get("effectsExecuted") != 0
        or len(source_detail.get("cases", [])) != 504
    ):
        raise RuntimeError("msner_contextual_source_invalid")

    baseline = _load_module(
        "baxy_msner_contextual_baseline",
        repository_root
        / "experiments/stt_quality/evaluate_msner_spanish_entity_development.py",
    )
    frozen = _load_module(
        "baxy_msner_contextual_frozen",
        repository_root / "experiments/stt_quality/evaluate_reserved_stt.py",
    )
    scorer = _load_module(
        "baxy_msner_contextual_scorer",
        repository_root / "experiments/stt_quality/msner_entity_scoring.py",
    )
    numeric = _load_module(
        "baxy_msner_contextual_numeric",
        repository_root / "experiments/stt_quality/spanish_numeric_semantics.py",
    )
    compiler = _load_module(
        "baxy_msner_contextual_compiler",
        repository_root / "experiments/stt_quality/contextual_hotwords.py",
    )

    wake_tree = frozen._program_tree(repository_root)
    if wake_tree.get("sha256") != EXPECTED_WAKE_TREE_SHA256:
        raise RuntimeError("msner_contextual_wake_tree_changed")
    _manifest, audio_cases = baseline._validate_extraction(extraction, repository_root)
    audio_by_case = {case["caseId"]: case for case in audio_cases}

    runtime_path = arguments.runtime_manifest.resolve(strict=True)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8-sig"))
    runtime_python = Path(str(runtime["python"])).resolve(strict=True)
    model_root = Path(str(runtime["stt_dir"])).resolve(strict=True)
    ffmpeg = arguments.ffmpeg.resolve(strict=True)
    if (
        runtime.get("schema") != "baxy-mind-runtime-v1"
        or runtime_python != Path(sys.executable).resolve(strict=True)
        or sha256(ffmpeg) != baseline.FFMPEG_SHA256
    ):
        raise RuntimeError("msner_contextual_runtime_invalid")
    baseline._validate_model(model_root)

    rows = list(source_detail["cases"])
    row_by_case = {str(row["caseId"]): row for row in rows}
    specs = build_oracle_case_specs(
        rows,
        normalize_tokens=numeric.semantic_tokens,
    )
    target_count = sum(len(spec["targets"]) for spec in specs)
    if len(specs) != EXPECTED_SELECTED_CASES or target_count != EXPECTED_TARGET_ENTITIES:
        raise RuntimeError(
            f"msner_contextual_selection_changed:{len(specs)}:{target_count}"
        )

    import psutil

    process = psutil.Process()
    peak_rss = process.memory_info().rss
    tokens_path = model_root / "tokens.txt"
    compiler.write_minimum_piece_vocab(tokens_path, bpe_vocab_output)
    native_stderr_output.parent.mkdir(parents=True, exist_ok=True)
    native_stderr_output.write_bytes(b"")
    recognizer = ContextualRecognizer(model_root, bpe_vocab_output)
    peak_rss = max(peak_rss, process.memory_info().rss)
    started = time.perf_counter()
    detail_cases: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        case_id = str(spec["caseId"])
        baseline_row = row_by_case[case_id]
        audio_case = audio_by_case[case_id]
        compiled_bpe_paths, compilation = compiler.compile_hotwords(
            tokens_path,
            spec["hotwordTerms"],
            maximum_terms=MAXIMUM_HOTWORDS,
        )
        stream_hotwords = compiler.compile_stream_phrases(
            spec["hotwordTerms"],
            maximum_terms=MAXIMUM_HOTWORDS,
        )
        encoded_surfaces = {
            str(item["surface"])
            for item in compilation
            if item["encoded"] is True
        }
        if (
            not set(spec["targetTerms"]).issubset(encoded_surfaces)
            or not compiled_bpe_paths
            or not stream_hotwords
        ):
            raise RuntimeError(f"msner_contextual_target_unencodable:{case_id}")
        audio_path = Path(str(audio_case["audioPath"]))
        audio = frozen._load_wav_bytes(
            audio_path.read_bytes(), str(audio_path), ffmpeg
        )
        transcript = ""
        latency: float | None = None
        error: str | None = None
        try:
            with _capture_native_stderr(native_stderr_output):
                transcript, latency = recognizer.transcribe(
                    audio, stream_hotwords, frozen
                )
        except Exception as exception:  # noqa: BLE001 - preserve diagnostic failure
            error = type(exception).__name__
        peak_rss = max(peak_rss, process.memory_info().rss)

        reference = str(baseline_row["reference"])
        labels = list(baseline_row["unifiedEntities"])
        baseline_transcript = str(baseline_row["productTranscript"])
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
        baseline_commitments = baseline_score["entityCommitments"]
        contextual_commitments = contextual_score["entityCommitments"]
        target_indices = {int(target["entityIndex"]) for target in spec["targets"]}
        targets_recovered = sum(
            contextual_commitments[target_index]["exactlyPreserved"] is True
            for target_index in target_indices
        )
        damaged_indices = [
            entity_index
            for entity_index, (before, after) in enumerate(
                zip(baseline_commitments, contextual_commitments, strict=True)
            )
            if before["exactlyPreserved"] is True
            and after["exactlyPreserved"] is False
        ]
        non_target_recoveries = [
            entity_index
            for entity_index, (before, after) in enumerate(
                zip(baseline_commitments, contextual_commitments, strict=True)
            )
            if entity_index not in target_indices
            and before["exactlyPreserved"] is False
            and after["exactlyPreserved"] is True
        ]
        reference_tokens = numeric.semantic_tokens(reference)
        baseline_tokens = numeric.semantic_tokens(baseline_transcript)
        contextual_tokens = numeric.semantic_tokens(transcript)
        distractor_false_insertions = [
            term
            for term in spec["distractorTerms"]
            if not _sequence_present(reference_tokens, numeric.semantic_tokens(term))
            and not _sequence_present(baseline_tokens, numeric.semantic_tokens(term))
            and _sequence_present(contextual_tokens, numeric.semantic_tokens(term))
        ]
        audio_seconds = len(audio) / frozen.SAMPLE_RATE
        baseline_errors = frozen._edit_distance(reference_tokens, baseline_tokens)
        contextual_errors = frozen._edit_distance(reference_tokens, contextual_tokens)
        detail_cases.append(
            {
                "caseId": case_id,
                "reference": reference,
                "baselineTranscript": baseline_transcript,
                "contextualTranscript": transcript,
                "targets": spec["targets"],
                "targetTerms": spec["targetTerms"],
                "distractorTerms": spec["distractorTerms"],
                "compiledBpePaths": compiled_bpe_paths,
                "streamHotwords": stream_hotwords,
                "compilation": compilation,
                "targetsRecovered": targets_recovered,
                "previouslyCorrectEntityDamages": damaged_indices,
                "nonTargetEntityRecoveries": non_target_recoveries,
                "distractorFalseInsertions": distractor_false_insertions,
                "baselineSemanticWordErrors": baseline_errors,
                "contextualSemanticWordErrors": contextual_errors,
                "semanticReferenceTokens": len(reference_tokens),
                "latencySeconds": latency,
                "realTimeFactor": (
                    None if latency is None else latency / max(0.001, audio_seconds)
                ),
                "audioSeconds": audio_seconds,
                "error": error,
                "baselineScore": baseline_score,
                "contextualScore": contextual_score,
            }
        )
        print(json.dumps({"progress": index, "total": len(specs)}), flush=True)

    latencies = [
        float(row["latencySeconds"])
        for row in detail_cases
        if row["latencySeconds"] is not None
    ]
    rtfs = [
        float(row["realTimeFactor"])
        for row in detail_cases
        if row["realTimeFactor"] is not None
    ]
    targets_recovered = sum(int(row["targetsRecovered"]) for row in detail_cases)
    damages = sum(
        len(row["previouslyCorrectEntityDamages"]) for row in detail_cases
    )
    false_insertions = sum(
        len(row["distractorFalseInsertions"]) for row in detail_cases
    )
    baseline_errors = sum(
        int(row["baselineSemanticWordErrors"]) for row in detail_cases
    )
    contextual_errors = sum(
        int(row["contextualSemanticWordErrors"]) for row in detail_cases
    )
    reference_tokens = sum(int(row["semanticReferenceTokens"]) for row in detail_cases)
    elapsed = time.perf_counter() - started
    native_stderr = native_stderr_output.read_text(
        encoding="utf-8", errors="replace"
    )
    native_encoding_errors = native_stderr.count("Cannot find ID for token") + (
        native_stderr.count("Encode hotwords failed")
    )
    metrics = {
        "selectedCases": len(detail_cases),
        "targetEntities": target_count,
        "targetsRecovered": targets_recovered,
        "targetRecoveryRate": round(targets_recovered / max(1, target_count), 6),
        "previouslyCorrectEntityDamages": damages,
        "nonTargetEntityRecoveries": sum(
            len(row["nonTargetEntityRecoveries"]) for row in detail_cases
        ),
        "distractorFalseInsertions": false_insertions,
        "semanticReferenceTokens": reference_tokens,
        "baselineSemanticWordErrors": baseline_errors,
        "contextualSemanticWordErrors": contextual_errors,
        "semanticWordErrorDelta": contextual_errors - baseline_errors,
        "baselineSemanticWer": round(baseline_errors / max(1, reference_tokens), 6),
        "contextualSemanticWer": round(
            contextual_errors / max(1, reference_tokens), 6
        ),
        "decodeErrors": sum(row["error"] is not None for row in detail_cases),
        "nativeHotwordEncodingErrors": native_encoding_errors,
        "nonemptyRate": round(
            sum(bool(numeric.semantic_tokens(str(row["contextualTranscript"]))) for row in detail_cases)
            / max(1, len(detail_cases)),
            6,
        ),
        "latencyP50Seconds": _nearest_rank(latencies, 0.50),
        "latencyP95Seconds": _nearest_rank(latencies, 0.95),
        "realTimeFactorP50": _nearest_rank(rtfs, 0.50),
        "realTimeFactorP95": _nearest_rank(rtfs, 0.95),
        "peakRssBytesObserved": peak_rss,
        "elapsedSeconds": elapsed,
        "rowsPerSecond": len(detail_cases) / max(0.001, elapsed),
    }
    checks = {
        "selectedCases": metrics["selectedCases"]
        == THRESHOLDS["expectedSelectedCases"],
        "targetEntities": metrics["targetEntities"]
        == THRESHOLDS["expectedTargetEntities"],
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

    detail = {
        "schema": SCHEMA,
        "partition": "development",
        "diagnosticKind": "oracle_contained_contextual_hotwords",
        "oracleTargetProvidedToAsr": True,
        "candidatePromotable": False,
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "cases": detail_cases,
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
    compiler_path = Path(compiler.__file__).resolve(strict=True)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "partition": "development",
        "status": "passed" if all(checks.values()) else "failed",
        "diagnosticKind": "oracle_contained_contextual_hotwords",
        "oracleTargetProvidedToAsr": True,
        "candidatePromotable": False,
        "configuration": {
            "decodingMethod": "modified_beam_search",
            "maxActivePaths": MAX_ACTIVE_PATHS,
            "hotwordsScore": HOTWORDS_SCORE,
            "maximumHotwords": MAXIMUM_HOTWORDS,
            "modelingUnit": "bpe",
            "derivedBpeVocabScoring": "minus_one_per_token_minimum_piece_path",
        },
        "metrics": metrics,
        "checks": checks,
        "thresholds": THRESHOLDS,
        "decision": {
            "candidatePromoted": False,
            "validationBlindMayOpen": False,
            "finalBlindMayOpen": False,
            "nextStepIfPassed": "develop_reference_independent_context_retrieval",
            "nextStepIfFailed": "reject_product_score_contextual_hotword_path",
        },
        "source": {
            "supersedesInvalidDiagnostic": {
                "artifactSha256": INVALID_V1_ARTIFACT_SHA256,
                "detailSha256": INVALID_V1_DETAIL_SHA256,
                "reason": "default_cjkchar_retokenized_bpe_paths_and_sherpa_skipped_hotwords",
            },
            "artifact": {
                "path": source_artifact_path.relative_to(repository_root).as_posix(),
                "sha256": SOURCE_ARTIFACT_SHA256,
            },
            "baselineDetail": {
                "path": source_detail_path.as_posix(),
                "sha256": SOURCE_DETAIL_SHA256,
            },
            "diagnosticDetail": {
                "path": detail_output.as_posix(),
                "sha256": sha256(detail_output),
            },
            "extraction": {
                "path": extraction_path.relative_to(repository_root).as_posix(),
                "sha256": EXTRACTION_SHA256,
            },
        },
        "runtime": {
            "manifest": runtime_path.as_posix(),
            "manifestSha256": sha256(runtime_path),
            "python": runtime_python.as_posix(),
            "pythonSha256": sha256(runtime_python),
            "modelRoot": model_root.as_posix(),
            "modelFiles": baseline.MODEL_FILES,
            "recognizerLoadSeconds": recognizer.load_seconds,
            "derivedBpeVocab": {
                "path": bpe_vocab_output.as_posix(),
                "sha256": sha256(bpe_vocab_output),
            },
            "nativeStderr": {
                "path": native_stderr_output.as_posix(),
                "sha256": sha256(native_stderr_output),
            },
        },
        "evaluator": {
            "path": evaluator_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(evaluator_path),
        },
        "contextualCompiler": {
            "path": compiler_path.relative_to(repository_root).as_posix(),
            "sha256": sha256(compiler_path),
        },
        "caseCommitments": [
            {
                "caseId": row["caseId"],
                "targetCount": len(row["targets"]),
                "targetsRecovered": row["targetsRecovered"],
                "previouslyCorrectEntityDamages": len(
                    row["previouslyCorrectEntityDamages"]
                ),
                "distractorFalseInsertions": len(row["distractorFalseInsertions"]),
                "baselineTranscriptSha256": hashlib.sha256(
                    str(row["baselineTranscript"]).encode("utf-8")
                ).hexdigest(),
                "contextualTranscriptSha256": hashlib.sha256(
                    str(row["contextualTranscript"]).encode("utf-8")
                ).hexdigest(),
                "compiledBpePathsSha256": hashlib.sha256(
                    str(row["compiledBpePaths"]).encode("utf-8")
                ).hexdigest(),
                "streamHotwordsSha256": hashlib.sha256(
                    str(row["streamHotwords"]).encode("utf-8")
                ).hexdigest(),
            }
            for row in detail_cases
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
    parser.add_argument("--source-artifact", type=Path, required=True)
    parser.add_argument("--source-detail", type=Path, required=True)
    parser.add_argument("--extraction", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--native-stderr-output", type=Path, required=True)
    parser.add_argument("--derived-bpe-vocab", type=Path, required=True)
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
