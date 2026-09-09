"""Evaluate preregistered real-audio STT partitions without executing effects.

The workflow is intentionally two-stage:

1. ``contract`` validates every immutable input and writes a pre-open contract.
2. ``evaluate`` refuses to decode unless that contract matches this exact
   evaluator, runtime, source preregistration, ffmpeg binary, and wake program
   tree.

Development recordings are opened first.  A blind contract additionally
requires green development reports produced by the same evaluator/runtime.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


CONTRACT_SCHEMA = "baxy.stt-evaluator-preopen-contract.v3"
REPORT_SCHEMA = "baxy.stt-real-audio-evaluation.v3"
FUSION_REPORT_SCHEMA = "baxy.stt-bounded-completion-fallback-evaluation.v3"
AUDIO_ARENA_SCHEMA = "baxy.stt-real-audio-preregistration.v1"
MIAMI_SCHEMA = "baxy.stt-natural-codeswitch-preregistration.v1"
MINDS_SCHEMA = "baxy.stt-minds14-preregistration.v1"
# Re-sealed against the tree this evaluator will actually measure. See
# audit_fresh_postweight_stt_sources.py for the full lineage: the previous
# value belonged to the consumed and rejected wake v17 campaign, and the tree
# had already drifted past it before the request-completion repair landed. Goal
# 10.2.5 re-sealed this unmeasured expectation after changing only the ONNX
# scheduling policy; model, hop, score and reserved corpora remain unchanged.
# C01 2026-09-03: tree drifted when scripts/goal095_09512_integrate.py was
# updated after the previous pin. C02 must revalidate historical campaign
# hashes against this tree; the corpora and engines are unchanged.
# C03 2026-09-04: tree drifted when public compose gained a Granite 4.2
# sampling/prompt profile. Corpora and engines are unchanged.
# C03 2026-09-05: empty-seen English compose no longer asks to name seen.
# C03 2026-09-05: identity-on-clock extra_claim no longer matches «time zone».
# C03 2026-09-05: Granite compose dropped «vive en el PC» / first-person-if-acted.
# C03 2026-09-05: clock+audio extras name both facts, not only the clock.
# C03 2026-09-05: continue-with-constraint compose sends situation facts only.
# C03 2026-09-05 (Opus): el árbol se movió al añadir
# src/baxy_mind/request_reading.py (lectura única del pedido), delegar en
# ella llm.py y __main__.py, y añadir dos ficheros de entrada al censo de
# prosa. Corpus, motores y hashes STT/TTS/wake del runtime registrado no
# cambian: esta actualización no afirma una medida de voz nueva.
# C03 2026-09-05 (Opus): el censo de prosa visible salta los docstrings de
# Python, como ya saltaba los comentarios. Corpus, motores y hashes
# STT/TTS/wake del runtime registrado no cambian: esta actualización no
# afirma una medida de voz nueva.
# C03 2026-09-05 (Opus): el compositor recibe el tema de un seguimiento
# elíptico y una explicación no puede ser sólo otra pregunta. Corpus,
# motores y hashes STT/TTS/wake del runtime registrado no cambian: esta
# actualización no afirma una medida de voz nueva.
# C03 2026-09-06 (Astra): pedido y contexto conservados en composicion;
# se retiran el saludo literal y el retorno de borradores rechazados.
# Cambia el arbol de programa esperado, no los corpus ni los motores
# STT/TTS/wake. No acredita una nueva aceptacion de voz.
# C03 Astra: hora AM/PM, tema y causa anidada conservados; lectura de explain.
# Prosa: conocimiento separado de observaciones, sin saludo recortado ni intro fija.
# C03 555: contextual interpretation is not a visible-answer fallback.
# Historical STT/wake campaign pins remain unchanged; this declaration does
# not claim new audio acceptance.
EXPECTED_PROGRAM_TREE_SHA256 = (
    "5a3d37d79c0e4b7366c3d7857b699a32c9d6e1b84df9d794f89bc3dea890415d"
)
SAMPLE_RATE = 16_000
SILENCE_SAMPLES = SAMPLE_RATE // 5
FFMPEG_SHA256 = "227af0691433b703ffc5725e47f7d06eefc34b4a72e7870e73d30e2cda483ecf"
MINDS_SOURCE_FILES = {
    "MInDS-14.zip": {
        "bytes": 471_355_396,
        "sha256": "595c040b4c5fba0cfa55138f4954ef68ee4d38bad2bb46d620feb75b40f476fc",
    },
    "extracted/MInDS-14/audio.zip": {
        "bytes": 471_788_974,
        "sha256": "e8f7d9bcd2fffc902291a4fa41aeb30115949221449f1b058c65ef059b67f2b1",
    },
    "extracted/MInDS-14/text.zip": {
        "bytes": 469_800,
        "sha256": "4aa76a05fa8a8aeb1301e7dd8148031e7948516a82b9e990409c46bd0fff9316",
    },
}
NEMOTRON_SOURCE_FILES = {
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
TIMESTAMP_PATTERN = re.compile(
    r"^(?P<start>\d\d:\d\d:\d\d\.\d{3})\s+-->\s+"
    r"(?P<end>\d\d:\d\d:\d\d\.\d{3})$"
)
NOTE_PATTERN = re.compile(r"^NOTE\s+(?P<recording>\S+)\s+offset=.*$")
WORD_PATTERN = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?", re.IGNORECASE)
CHAT_ANNOTATION_PATTERN = re.compile(
    r"\[(?:/{1,2}|x\s*\d+|=!.*?|\?|%.*?|\+.*?|\^.*?)\]",
    re.IGNORECASE,
)
CRITICAL_PATTERN = re.compile(
    r"(?:\b[A-Z]{2,}(?:-\d+)?\b|\b\d+(?::\d+)?(?:st|nd|rd|th)?\b|"
    r"\b(?:[A-Za-z]-){2,}[A-Za-z]\b)"
)
MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
}
ORDINAL_EQUIVALENTS = {
    "first": "1",
    "second": "2",
    "third": "3",
    "fourth": "4",
    "fifth": "5",
    "sixth": "6",
    "seventh": "7",
    "eighth": "8",
    "ninth": "9",
    "tenth": "10",
    "eleventh": "11",
    "twelfth": "12",
    "primero": "1",
    "primera": "1",
    "segundo": "2",
    "segunda": "2",
    "tercero": "3",
    "tercera": "3",
    "cuarto": "4",
    "cuarta": "4",
    "quinto": "5",
    "quinta": "5",
}
SCORING_NORMALIZATION = (
    "unicode-fold; punctuation-insensitive; HH:MM equivalent to HHMM; "
    "English/Spanish ordinal words equivalent to ordinal digits"
)
ENGLISH_HINTS = {
    "a",
    "and",
    "are",
    "do",
    "for",
    "have",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "that",
    "the",
    "this",
    "to",
    "we",
    "what",
    "you",
}
SPANISH_HINTS = {
    "a",
    "como",
    "con",
    "de",
    "el",
    "ella",
    "en",
    "es",
    "la",
    "las",
    "lo",
    "los",
    "no",
    "para",
    "por",
    "que",
    "se",
    "si",
    "un",
    "una",
    "y",
    "yo",
}
THRESHOLDS: dict[str, dict[str, dict[str, float | int]]] = {
    "audio_arena": {
        "development": {
            "expectedCases": 12,
            "minimumUsableRatio": 1.0,
            "maximumCorpusWer": 0.20,
            "maximumCaseWerP95": 0.50,
            "minimumCriticalAnchorRecall": 0.99,
            "minimumNonemptyRate": 1.0,
            "maximumLatencyP50Seconds": 1.5,
            "maximumLatencyP95Seconds": 2.0,
        },
        "blind": {
            "expectedCases": 50,
            "minimumUsableRatio": 1.0,
            "maximumCorpusWer": 0.20,
            "maximumCaseWerP95": 0.50,
            "minimumCriticalAnchorRecall": 0.99,
            "minimumNonemptyRate": 1.0,
            "maximumLatencyP50Seconds": 1.5,
            "maximumLatencyP95Seconds": 2.0,
        },
    },
    "miami": {
        "development": {
            "expectedCases": 48,
            "minimumUsableRatio": 0.80,
            "maximumCorpusWer": 0.35,
            "maximumCaseWerP95": 0.75,
            "minimumNonemptyRate": 1.0,
            "maximumLatencyP50Seconds": 1.5,
            "maximumLatencyP95Seconds": 2.0,
        },
        "blind": {
            "expectedCases": 96,
            "minimumUsableRatio": 0.80,
            "maximumCorpusWer": 0.35,
            "maximumCaseWerP95": 0.75,
            "minimumNonemptyRate": 1.0,
            "maximumLatencyP50Seconds": 1.5,
            "maximumLatencyP95Seconds": 2.0,
        },
    },
    "minds14": {
        "development": {
            "expectedCases": 84,
            "minimumUsableRatio": 1.0,
            "minimumTranscriptIntentAccuracy": 0.95,
            "minimumIntentSemanticPreservation": 0.99,
            "minimumNonemptyRate": 1.0,
            "maximumFinalizationLatencyP95Seconds": 1.5,
            "maximumRealTimeFactorP95": 0.50,
        },
        "blind": {
            "expectedCases": 196,
            "minimumUsableRatio": 1.0,
            "minimumTranscriptIntentAccuracy": 0.95,
            "minimumIntentSemanticPreservation": 0.99,
            "minimumNonemptyRate": 1.0,
            "maximumFinalizationLatencyP95Seconds": 1.5,
            "maximumRealTimeFactorP95": 0.50,
        },
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"json_object_required:{path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _relative(repository_root: Path, path: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return resolved.relative_to(repository_root).as_posix()
    except ValueError:
        return resolved.as_posix()


def _program_tree(repository_root: Path) -> dict[str, object]:
    roots = (
        repository_root / "experiments" / "voice_latency",
        repository_root / "scripts",
        repository_root / "src" / "baxy_mind",
    )
    files: dict[str, Path] = {}
    for root in roots:
        for path in root.rglob("*.py"):
            if path.is_file() and not path.is_symlink():
                files[path.relative_to(repository_root).as_posix()] = path
    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\n")
        digest.update(_sha256(files[relative]).encode("ascii"))
        digest.update(b"\n")
    result = {
        "schema": "baxy.wake-validation-program-tree.v1",
        "roots": [
            "experiments/voice_latency",
            "scripts",
            "src/baxy_mind",
        ],
        "pythonFiles": len(files),
        "sha256": digest.hexdigest(),
    }
    if result["sha256"] != EXPECTED_PROGRAM_TREE_SHA256:
        raise RuntimeError("wake_program_tree_changed")
    return result


def _validate_preregistration(path: Path, expected_schema: str) -> dict[str, Any]:
    receipt = _read_json(path)
    if receipt.get("schema") != expected_schema:
        raise RuntimeError(f"stt_preregistration_schema_mismatch:{path}")
    if receipt.get("evaluationStatus") != "unopened":
        raise RuntimeError(f"stt_preregistration_already_opened:{path}")
    if receipt.get("modelAudioDecoded") is not False:
        raise RuntimeError(f"stt_preregistration_decode_state_invalid:{path}")
    if receipt.get("corpusSelectionFrozen") is not True:
        raise RuntimeError(f"stt_preregistration_selection_not_frozen:{path}")
    if receipt.get("wakeProgramTree", {}).get("sha256") != EXPECTED_PROGRAM_TREE_SHA256:
        raise RuntimeError(f"stt_preregistration_program_tree_mismatch:{path}")
    return receipt


def _validate_ffmpeg(path: Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    digest = _sha256(resolved)
    if digest != FFMPEG_SHA256:
        raise RuntimeError("ffmpeg_hash_mismatch")
    completed = subprocess.run(
        [str(resolved), "-version"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "path": resolved.as_posix(),
        "sha256": digest,
        "version": completed.stdout.splitlines()[0],
    }


def _validate_minds_source_root(path: Path) -> dict[str, object]:
    root = path.resolve(strict=True)
    files: dict[str, object] = {}
    for relative, expected in MINDS_SOURCE_FILES.items():
        source = root / Path(relative)
        observed = {
            "path": source.resolve(strict=True).as_posix(),
            "bytes": source.stat().st_size,
            "sha256": _sha256(source),
        }
        if (
            observed["bytes"] != expected["bytes"]
            or observed["sha256"] != expected["sha256"]
        ):
            raise RuntimeError(f"minds14_source_file_changed:{relative}")
        files[relative] = observed
    audio_zip = root / "extracted" / "MInDS-14" / "audio.zip"
    text_zip = root / "extracted" / "MInDS-14" / "text.zip"
    with zipfile.ZipFile(audio_zip) as archive:
        audio_entries = set(archive.namelist())
    with zipfile.ZipFile(text_zip) as archive:
        text_entries = set(archive.namelist())
    if not {"en-US.csv", "es-ES.csv"}.issubset(text_entries):
        raise RuntimeError("minds14_text_entries_missing")
    return {
        "root": root.as_posix(),
        "files": files,
        "audioEntries": len(audio_entries),
        "textEntries": len(text_entries),
        "sourceCommit": "8a7e41314267b68ddb15d3c9da012b9c98bf2a78",
    }


def _validate_nemotron_directory(path: Path) -> dict[str, object]:
    root = path.resolve(strict=True)
    files: dict[str, object] = {}
    for name, expected in NEMOTRON_SOURCE_FILES.items():
        source = root / name
        observed = {
            "bytes": source.resolve(strict=True).stat().st_size,
            "sha256": _sha256(source),
        }
        if observed != expected:
            raise RuntimeError(f"nemotron_source_file_changed:{name}")
        files[name] = observed
    return {
        "path": root.as_posix(),
        "model": "nvidia/nemotron-3.5-asr-streaming-0.6b",
        "conversion": ("k2-fsa/sherpa-onnx 560ms int8 release 2026-06-11"),
        "files": files,
    }


def _validate_runtime_manifest(path: Path) -> tuple[dict[str, Any], dict[str, object]]:
    resolved = path.resolve(strict=True)
    manifest = _read_json(resolved)
    if manifest.get("schema") != "baxy-mind-runtime-v1":
        raise RuntimeError("mind_runtime_manifest_schema_mismatch")
    python = Path(str(manifest.get("python", ""))).resolve(strict=True)
    stt_directory = Path(str(manifest.get("stt_dir", ""))).resolve(strict=True)
    if _sha256(python) != manifest.get("python_sha256"):
        raise RuntimeError("mind_runtime_python_hash_mismatch")
    required_stt = {
        "encoder.int8.onnx",
        "decoder.int8.onnx",
        "joiner.int8.onnx",
        "tokens.txt",
    }
    if {
        path.name for path in stt_directory.iterdir() if path.is_file()
    } != required_stt:
        raise RuntimeError("mind_runtime_stt_file_set_mismatch")
    return manifest, {
        "path": resolved.as_posix(),
        "sha256": _sha256(resolved),
        "python": python.as_posix(),
        "pythonSha256": manifest["python_sha256"],
        "sttDirectory": stt_directory.as_posix(),
        "sttSha256": manifest["stt_sha256"],
    }


def _validate_development_reports(
    report_paths: list[Path],
    evaluator_sha256: str,
    fusion_evaluator_sha256: str,
    stt_sha256: str,
) -> list[dict[str, object]]:
    if len(report_paths) != 2:
        raise RuntimeError("blind_contract_requires_two_development_reports")
    summaries: list[dict[str, object]] = []
    sources: set[str] = set()
    for path in report_paths:
        report = _read_json(path)
        if report.get("schema") != FUSION_REPORT_SCHEMA:
            raise RuntimeError(f"development_report_schema_mismatch:{path}")
        if report.get("partition") != "development" or report.get("status") != "passed":
            raise RuntimeError(f"development_report_not_green:{path}")
        if report.get("fusionEvaluator", {}).get("sha256") != fusion_evaluator_sha256:
            raise RuntimeError(f"development_report_fusion_evaluator_mismatch:{path}")
        inputs = report.get("inputs", {})
        if any(
            inputs.get(name, {}).get("sha256") != evaluator_sha256
            for name in ("primary", "fallback")
        ):
            raise RuntimeError(f"development_report_evaluator_mismatch:{path}")
        if inputs.get("runtime", {}).get("sttSha256") != stt_sha256:
            raise RuntimeError(f"development_report_runtime_mismatch:{path}")
        if (
            report.get("policy", {}).get("primary") != "parakeet_greedy"
            or report.get("policy", {}).get("fallback") != "nemotron_auto"
        ):
            raise RuntimeError(f"development_report_policy_mismatch:{path}")
        checks = report.get("aggregate", {}).get("checks", {})
        if not checks or not all(checks.values()):
            raise RuntimeError(f"development_report_checks_not_green:{path}")
        source = str(report.get("source"))
        sources.add(source)
        summaries.append(
            {
                "path": path.resolve(strict=True).as_posix(),
                "sha256": _sha256(path),
                "source": source,
                "status": "passed",
            }
        )
    if sources != {"audio_arena", "minds14"}:
        raise RuntimeError("blind_contract_development_sources_incomplete")
    return sorted(summaries, key=lambda item: str(item["source"]))


def build_contract(arguments: argparse.Namespace) -> dict[str, Any]:
    repository_root = arguments.repository_root.resolve(strict=True)
    evaluator_path = Path(__file__).resolve(strict=True)
    evaluator_sha256 = _sha256(evaluator_path)
    fusion_evaluator_path = arguments.fusion_evaluator.resolve(strict=True)
    fusion_evaluator_sha256 = _sha256(fusion_evaluator_path)
    audio_path = arguments.audio_arena_prereg.resolve(strict=True)
    miami_path = arguments.miami_prereg.resolve(strict=True)
    minds_path = arguments.minds_prereg.resolve(strict=True)
    _validate_preregistration(audio_path, AUDIO_ARENA_SCHEMA)
    _validate_preregistration(miami_path, MIAMI_SCHEMA)
    _validate_preregistration(minds_path, MINDS_SCHEMA)
    runtime_manifest, runtime = _validate_runtime_manifest(arguments.runtime_manifest)
    ffmpeg = _validate_ffmpeg(arguments.ffmpeg)
    minds_source = _validate_minds_source_root(arguments.minds_original_root)
    nemotron = _validate_nemotron_directory(arguments.nemotron_directory)
    development_reports: list[dict[str, object]] = []
    if arguments.role == "blind":
        development_reports = _validate_development_reports(
            arguments.development_report,
            evaluator_sha256,
            fusion_evaluator_sha256,
            str(runtime_manifest["stt_sha256"]),
        )
    return {
        "schema": CONTRACT_SCHEMA,
        "createdAtUtc": arguments.created_at_utc,
        "role": arguments.role,
        "modelAudioDecoded": False,
        "evaluator": {
            "path": _relative(repository_root, evaluator_path),
            "sha256": evaluator_sha256,
        },
        "fusionEvaluator": {
            "path": _relative(repository_root, fusion_evaluator_path),
            "sha256": fusion_evaluator_sha256,
        },
        "candidatePolicy": {
            "primary": "parakeet_greedy",
            "fallback": "nemotron_auto",
            "selector": "bounded_completion_v2",
        },
        "preregistrations": {
            "audio_arena": {
                "path": _relative(repository_root, audio_path),
                "sha256": _sha256(audio_path),
            },
            "miami": {
                "path": _relative(repository_root, miami_path),
                "sha256": _sha256(miami_path),
            },
            "minds14": {
                "path": _relative(repository_root, minds_path),
                "sha256": _sha256(minds_path),
            },
        },
        "runtime": runtime,
        "ffmpeg": ffmpeg,
        "minds14Source": minds_source,
        "nemotron": nemotron,
        "thresholds": THRESHOLDS,
        "scoringNormalization": SCORING_NORMALIZATION,
        "developmentReports": development_reports,
        "wakeProgramTree": _program_tree(repository_root),
        "effectsExecuted": 0,
    }


def _validate_contract(
    *, repository_root: Path, contract_path: Path, source: str, partition: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = _read_json(contract_path)
    if contract.get("schema") != CONTRACT_SCHEMA:
        raise RuntimeError("stt_evaluator_contract_schema_mismatch")
    if contract.get("role") != partition:
        raise RuntimeError("stt_evaluator_contract_partition_mismatch")
    if contract.get("modelAudioDecoded") is not False:
        raise RuntimeError("stt_evaluator_contract_decode_state_invalid")
    evaluator_path = Path(__file__).resolve(strict=True)
    if contract.get("evaluator", {}).get("sha256") != _sha256(evaluator_path):
        raise RuntimeError("stt_evaluator_contract_code_changed")
    if (
        contract.get("wakeProgramTree", {}).get("sha256")
        != _program_tree(repository_root)["sha256"]
    ):
        raise RuntimeError("stt_evaluator_contract_program_tree_changed")
    if contract.get("thresholds") != THRESHOLDS:
        raise RuntimeError("stt_evaluator_contract_thresholds_changed")
    if contract.get("scoringNormalization") != SCORING_NORMALIZATION:
        raise RuntimeError("stt_evaluator_contract_scoring_changed")

    preregistrations: dict[str, dict[str, str]] = contract["preregistrations"]
    resolved: dict[str, dict[str, Any]] = {}
    for name, schema in (
        ("audio_arena", AUDIO_ARENA_SCHEMA),
        ("miami", MIAMI_SCHEMA),
        ("minds14", MINDS_SCHEMA),
    ):
        entry = preregistrations[name]
        path = Path(entry["path"])
        if not path.is_absolute():
            path = repository_root / path
        if _sha256(path) != entry["sha256"]:
            raise RuntimeError(f"stt_evaluator_contract_prereg_changed:{name}")
        resolved[name] = _validate_preregistration(path, schema)

    runtime_path = Path(contract["runtime"]["path"])
    runtime_manifest, runtime = _validate_runtime_manifest(runtime_path)
    if runtime["sha256"] != contract["runtime"]["sha256"]:
        raise RuntimeError("stt_evaluator_contract_runtime_manifest_changed")
    if runtime["sttSha256"] != contract["runtime"]["sttSha256"]:
        raise RuntimeError("stt_evaluator_contract_stt_changed")
    ffmpeg_path = Path(contract["ffmpeg"]["path"])
    if _validate_ffmpeg(ffmpeg_path)["sha256"] != contract["ffmpeg"]["sha256"]:
        raise RuntimeError("stt_evaluator_contract_ffmpeg_changed")
    minds_source = _validate_minds_source_root(
        Path(str(contract["minds14Source"]["root"]))
    )
    if minds_source != contract["minds14Source"]:
        raise RuntimeError("stt_evaluator_contract_minds14_source_changed")
    nemotron = _validate_nemotron_directory(Path(str(contract["nemotron"]["path"])))
    if nemotron != contract["nemotron"]:
        raise RuntimeError("stt_evaluator_contract_nemotron_changed")
    fusion_evaluator_path = Path(str(contract["fusionEvaluator"]["path"]))
    if not fusion_evaluator_path.is_absolute():
        fusion_evaluator_path = repository_root / fusion_evaluator_path
    fusion_evaluator_sha256 = _sha256(fusion_evaluator_path)
    if fusion_evaluator_sha256 != contract["fusionEvaluator"]["sha256"]:
        raise RuntimeError("stt_evaluator_contract_fusion_evaluator_changed")
    if contract.get("candidatePolicy") != {
        "primary": "parakeet_greedy",
        "fallback": "nemotron_auto",
        "selector": "bounded_completion_v2",
    }:
        raise RuntimeError("stt_evaluator_contract_candidate_policy_changed")
    if partition == "blind":
        _validate_development_reports(
            [Path(item["path"]) for item in contract["developmentReports"]],
            _sha256(evaluator_path),
            fusion_evaluator_sha256,
            str(runtime_manifest["stt_sha256"]),
        )
    return contract, resolved[source], runtime


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )


def _clean_reference(text: str) -> str:
    value = html.unescape(text)
    value = re.sub(r"<[^>]+>", " ", value)
    value = CHAT_ANNOTATION_PATTERN.sub(" ", value)
    value = re.sub(r"\[:\s*([^\]]+)\]", r" \1 ", value)
    value = re.sub(r"&=[^\s]+", " ", value)
    value = re.sub(r"\b(?:xxx|www|yyy)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"@[A-Za-z0-9:_-]+", " ", value)
    return " ".join(value.split())


def _tokens(text: str) -> list[str]:
    return WORD_PATTERN.findall(_fold(_clean_reference(text)))


def _scoring_tokens(text: str) -> list[str]:
    value = _fold(_clean_reference(text))
    value = re.sub(r"\b(\d{1,2}):(\d{2})\b", r"\1\2", value)
    tokens = WORD_PATTERN.findall(value)
    normalized: list[str] = []
    for token in tokens:
        ordinal_digit = re.fullmatch(r"(\d+)(?:st|nd|rd|th)", token)
        if ordinal_digit is not None:
            normalized.append(ordinal_digit.group(1))
        else:
            normalized.append(ORDINAL_EQUIVALENTS.get(token, token))
    return normalized


def _edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for reference_index, reference_token in enumerate(reference, start=1):
        current = [reference_index]
        for hypothesis_index, hypothesis_token in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[hypothesis_index] + 1,
                    previous[hypothesis_index - 1]
                    + (reference_token != hypothesis_token),
                )
            )
        previous = current
    return previous[-1]


def _nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _critical_anchors(reference: str) -> list[str]:
    anchors = [match.group(0) for match in CRITICAL_PATTERN.finditer(reference)]
    spelled_names = {
        "".join(_tokens(anchor))
        for anchor in anchors
        if len(_tokens(anchor)) >= 3
        and all(len(token) == 1 for token in _tokens(anchor))
    }
    for match in re.finditer(r"\b[A-Z][a-z]{2,}\b", reference):
        plain = match.group(0)
        prefix = reference[: match.start()].rstrip()
        starts_sentence = not prefix or prefix[-1] in ".!?"
        if plain.casefold() in MONTHS:
            anchors.append(plain)
        elif not starts_sentence and plain.casefold() not in spelled_names:
            anchors.append(plain)
    return list(dict.fromkeys(anchor for anchor in anchors if anchor))


def _anchor_present(anchor: str, transcript: str) -> bool:
    anchor_tokens = _scoring_tokens(anchor)
    transcript_tokens = _scoring_tokens(transcript)
    if not anchor_tokens:
        return True
    width = len(anchor_tokens)
    if any(
        transcript_tokens[index : index + width] == anchor_tokens
        for index in range(len(transcript_tokens) - width + 1)
    ):
        return True
    if width >= 3 and all(len(token) == 1 for token in anchor_tokens):
        return "".join(anchor_tokens) in "".join(transcript_tokens)
    return False


def _language_class(reference: str) -> str:
    tokens = _tokens(reference)
    english = sum(token in ENGLISH_HINTS for token in tokens)
    spanish = sum(token in SPANISH_HINTS for token in tokens)
    if english >= 2 and spanish >= 2:
        return "code_switch"
    if spanish > english:
        return "es"
    if english > spanish:
        return "en"
    return "undetermined"


def _decode_wav(source: wave.Wave_read, identity: str) -> np.ndarray:
    if source.getsampwidth() != 2:
        raise RuntimeError(f"wav_not_pcm16:{identity}")
    channels = source.getnchannels()
    source_rate = source.getframerate()
    audio = np.frombuffer(source.readframes(source.getnframes()), dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1).astype(np.int16)
    values = audio.astype(np.float32) / 32768.0
    if source_rate != SAMPLE_RATE:
        target_samples = round(len(values) * SAMPLE_RATE / source_rate)
        values = np.interp(
            np.linspace(0, len(values) - 1, target_samples),
            np.arange(len(values)),
            values,
        ).astype(np.float32)
    return values


def _load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        return _decode_wav(source, str(path))


def _load_wav_bytes(payload: bytes, identity: str, ffmpeg: Path) -> np.ndarray:
    try:
        with wave.open(io.BytesIO(payload), "rb") as source:
            return _decode_wav(source, identity)
    except wave.Error as error:
        if "unknown format" not in str(error):
            raise
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "f32le",
            "pipe:1",
        ],
        input=payload,
        check=True,
        capture_output=True,
    )
    audio = np.frombuffer(completed.stdout, dtype="<f4").astype(np.float32)
    if not len(audio):
        raise RuntimeError(f"ffmpeg_empty_wav:{identity}")
    return audio


def _load_mp3_segment(
    *, ffmpeg: Path, source: Path, start_ms: int, duration_ms: int
) -> np.ndarray:
    completed = subprocess.run(
        [
            str(ffmpeg),
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start_ms / 1000:.3f}",
            "-i",
            str(source),
            "-t",
            f"{duration_ms / 1000:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "f32le",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    )
    audio = np.frombuffer(completed.stdout, dtype="<f4").astype(np.float32)
    if not len(audio):
        raise RuntimeError("ffmpeg_empty_audio")
    return audio


def _with_silence(audio: np.ndarray) -> np.ndarray:
    return np.concatenate(
        [
            np.zeros(SILENCE_SAMPLES, dtype=np.float32),
            audio,
            np.zeros(SILENCE_SAMPLES, dtype=np.float32),
        ]
    )


class ProductStt:
    def __init__(self, repository_root: Path) -> None:
        sys.path.insert(0, str(repository_root / "src"))
        from baxy_mind.voice import VoiceEngine

        self._engine = VoiceEngine(lambda _text: None)
        started = time.perf_counter()
        self._engine.load()
        self.load_seconds = time.perf_counter() - started
        self.status = self._engine.status()
        self._recognizer = self._engine._recognizer  # noqa: SLF001
        self._corrector = self._engine._corrector  # noqa: SLF001
        if self._recognizer is None:
            raise RuntimeError("product_stt_recognizer_missing")
        self.last_diagnostics: dict[str, float] = {}

    def transcribe(
        self, audio: np.ndarray, _language: str | None = None
    ) -> tuple[str, str, float]:
        stream = self._recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, _with_silence(audio))
        started = time.perf_counter()
        self._recognizer.decode_stream(stream)
        latency = time.perf_counter() - started
        raw = str(stream.result.text or "").strip()
        corrected = self._corrector.correct(raw) if raw and self._corrector else raw
        self.last_diagnostics = {
            "finalizationLatencySeconds": latency,
            "maximumChunkDecodeSeconds": latency,
        }
        return raw, corrected, latency


class ParakeetGreedyStt:
    def __init__(self, model_directory: Path) -> None:
        import os

        import sherpa_onnx

        started = time.perf_counter()
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(model_directory / "encoder.int8.onnx"),
            decoder=str(model_directory / "decoder.int8.onnx"),
            joiner=str(model_directory / "joiner.int8.onnx"),
            tokens=str(model_directory / "tokens.txt"),
            num_threads=max(2, min(6, (os.cpu_count() or 4) // 2)),
            model_type="nemo_transducer",
            decoding_method="greedy_search",
        )
        self.load_seconds = time.perf_counter() - started
        self.status = {
            "loaded": True,
            "model": "parakeet-tdt-0.6b-v3-int8",
            "provider": "cpu",
            "decodingMethod": "greedy_search",
        }
        self.last_diagnostics: dict[str, float] = {}
        stream = self._recognizer.create_stream()
        stream.accept_waveform(
            SAMPLE_RATE, np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
        )
        self._recognizer.decode_stream(stream)

    def transcribe(
        self, audio: np.ndarray, _language: str | None = None
    ) -> tuple[str, str, float]:
        stream = self._recognizer.create_stream()
        stream.accept_waveform(SAMPLE_RATE, _with_silence(audio))
        started = time.perf_counter()
        self._recognizer.decode_stream(stream)
        latency = time.perf_counter() - started
        text = str(stream.result.text or "").strip()
        self.last_diagnostics = {
            "finalizationLatencySeconds": latency,
            "maximumChunkDecodeSeconds": latency,
        }
        return text, text, latency


class NemotronStreamingStt:
    def __init__(self, model_directory: Path, language_mode: str) -> None:
        import os

        import sherpa_onnx

        self._language_mode = language_mode
        started = time.perf_counter()
        self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            encoder=str(model_directory / "encoder.int8.onnx"),
            decoder=str(model_directory / "decoder.int8.onnx"),
            joiner=str(model_directory / "joiner.int8.onnx"),
            tokens=str(model_directory / "tokens.txt"),
            num_threads=max(2, min(6, (os.cpu_count() or 4) // 2)),
            model_type="nemo_transducer",
            decoding_method="greedy_search",
            enable_endpoint_detection=False,
            provider="cpu",
        )
        self.load_seconds = time.perf_counter() - started
        self.status = {
            "loaded": True,
            "model": "nemotron-3.5-asr-streaming-0.6b-560ms-int8",
            "provider": "cpu",
            "languageMode": language_mode,
        }
        self.last_diagnostics: dict[str, float] = {}

    def transcribe(
        self, audio: np.ndarray, language: str | None = None
    ) -> tuple[str, str, float]:
        stream = self._recognizer.create_stream()
        selected_language = (
            "auto" if self._language_mode == "auto" else str(language or "auto")
        )
        stream.set_option("language", selected_language)
        chunk_samples = round(SAMPLE_RATE * 0.16)
        chunk_decode_seconds: list[float] = []
        started = time.perf_counter()
        for offset in range(0, len(audio), chunk_samples):
            stream.accept_waveform(
                SAMPLE_RATE,
                np.asarray(audio[offset : offset + chunk_samples], dtype=np.float32),
            )
            chunk_started = time.perf_counter()
            while self._recognizer.is_ready(stream):
                self._recognizer.decode_stream(stream)
            chunk_decode_seconds.append(time.perf_counter() - chunk_started)
        finalization_started = time.perf_counter()
        stream.input_finished()
        while self._recognizer.is_ready(stream):
            self._recognizer.decode_stream(stream)
        try:
            result = self._recognizer.get_result_all(stream)
        except Exception:  # noqa: BLE001 - older sherpa compatibility
            result = stream.result
        finalization = time.perf_counter() - finalization_started
        latency = time.perf_counter() - started
        text = str(getattr(result, "text", "") or "").strip()
        self.last_diagnostics = {
            "finalizationLatencySeconds": finalization,
            "maximumChunkDecodeSeconds": max(chunk_decode_seconds, default=0.0),
        }
        return text, text, latency


def _audio_arena_references(
    *, source_root: Path, partition: str, selected_paths: set[str]
) -> dict[str, dict[str, Any]]:
    metadata_path = source_root / "metadata.jsonl"
    references: dict[str, dict[str, Any]] = {}
    if partition == "development":
        with metadata_path.open("r", encoding="utf-8") as source:
            for turn_id in range(6):
                row = json.loads(next(source))
                expected = f"real_audio/person1/turn_{turn_id:03d}.wav"
                if row.get("file_name") != expected:
                    raise RuntimeError("audio_arena_metadata_order_changed")
                for speaker in ("person1", "person2"):
                    clone = dict(row)
                    clone["file_name"] = f"real_audio/{speaker}/turn_{turn_id:03d}.wav"
                    references[clone["file_name"]] = clone
        return references

    with metadata_path.open("r", encoding="utf-8") as source:
        for line in source:
            row = json.loads(line)
            file_name = str(row.get("file_name", ""))
            if file_name in selected_paths:
                references[file_name] = row
    if set(references) != selected_paths:
        raise RuntimeError("audio_arena_reference_partition_incomplete")
    return references


def _audio_arena_cases(prereg: dict[str, Any], partition: str) -> list[dict[str, Any]]:
    source_root = Path(prereg["source"]["localRoot"]).resolve(strict=True)
    if partition == "blind":
        records = [dict(record) for record in prereg["selection"]["records"]]
    else:
        records = []
        for speaker in ("person1", "person2"):
            for turn_id in prereg["selection"][
                "excludedBecauseReferenceTextWasInspectedInThisCampaign"
            ]:
                path = source_root / "real_audio" / speaker / f"turn_{turn_id:03d}.wav"
                records.append(
                    {
                        "path": path.relative_to(source_root).as_posix(),
                        "speaker": speaker,
                        "turnId": turn_id,
                        "bytes": path.stat().st_size,
                        "sha256": _sha256(path),
                    }
                )
    selected_paths = {str(record["path"]) for record in records}
    references = _audio_arena_references(
        source_root=source_root,
        partition=partition,
        selected_paths=selected_paths,
    )
    cases: list[dict[str, Any]] = []
    for record in records:
        path = source_root / str(record["path"])
        if path.stat().st_size != record["bytes"] or _sha256(path) != record["sha256"]:
            raise RuntimeError(f"audio_arena_selected_file_changed:{record['path']}")
        reference_row = references[str(record["path"])]
        cases.append(
            {
                "caseId": f"audio-arena-{record['speaker']}-{int(record['turnId']):03d}",
                "speaker": record["speaker"],
                "turnId": record["turnId"],
                "path": path,
                "reference": str(reference_row["input_text"]),
                "metadata": {
                    "requiredFunctionCall": reference_row.get("required_function_call"),
                    "categories": reference_row.get("categories"),
                },
            }
        )
    return cases


def _vtt_reference_map(vtt_path: Path) -> dict[tuple[str, int], str]:
    references: dict[tuple[str, int], str] = {}
    current_recording: str | None = None
    current_key: tuple[str, int] | None = None
    current_lines: list[str] = []
    ordinal = 0

    def finish() -> None:
        nonlocal current_key, current_lines
        if current_key is not None:
            references[current_key] = " ".join(current_lines).strip()
        current_key = None
        current_lines = []

    with vtt_path.open("r", encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.rstrip("\r\n")
            note = NOTE_PATTERN.fullmatch(line)
            if note is not None:
                finish()
                current_recording = note.group("recording")
                ordinal = 0
                continue
            if TIMESTAMP_PATTERN.fullmatch(line) is not None:
                finish()
                if current_recording is None:
                    raise RuntimeError("vtt_timestamp_before_recording")
                current_key = (current_recording, ordinal)
                ordinal += 1
                continue
            if current_key is not None and line:
                current_lines.append(line)
        finish()
    return references


def _miami_cases(prereg: dict[str, Any], partition: str) -> list[dict[str, Any]]:
    source_root = Path(prereg["retrievalMirror"]["localRoot"]).resolve(strict=True)
    mp3 = source_root / "miamiCorpus_merged.mp3"
    vtt = source_root / "miamiCorpus_merged.vtt"
    expected_files = prereg["retrievalMirror"]["files"]
    for path in (mp3, vtt):
        expected = expected_files[path.name]
        if (
            path.stat().st_size != expected["bytes"]
            or _sha256(path) != expected["sha256"]
        ):
            raise RuntimeError(f"miami_source_file_changed:{path.name}")
    key = "blindSegments" if partition == "blind" else "developmentSegments"
    records = prereg["selection"][key]
    references = _vtt_reference_map(vtt)
    cases: list[dict[str, Any]] = []
    for record in records:
        identity = (str(record["recordingId"]), int(record["cueOrdinal"]))
        if identity not in references:
            raise RuntimeError(f"miami_reference_missing:{identity}")
        cases.append(
            {
                "caseId": f"miami-{identity[0]}-{identity[1]:04d}",
                "recordingId": identity[0],
                "cueOrdinal": identity[1],
                "path": mp3,
                "globalStartMs": int(record["globalStartMs"]),
                "durationMs": int(record["durationMs"]),
                "reference": references[identity],
            }
        )
    return cases


def _minds14_references(
    *, text_zip: Path, selected_paths: set[str]
) -> dict[str, dict[str, str]]:
    references: dict[str, dict[str, str]] = {}
    with zipfile.ZipFile(text_zip) as archive:
        for language in ("en-US", "es-ES"):
            with archive.open(f"{language}.csv") as raw:
                with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                    rows = csv.DictReader(text)
                    if rows.fieldnames != [
                        "filepath",
                        "text_asr",
                        "text_translated",
                        "intent",
                    ]:
                        raise RuntimeError(f"minds14_csv_schema_changed:{language}")
                    for row in rows:
                        path = str(row["filepath"])
                        if path in selected_paths:
                            references[path] = {
                                "reference": str(row["text_asr"]),
                                "intent": str(row["intent"]).casefold(),
                                "language": language,
                            }
    if set(references) != selected_paths:
        raise RuntimeError("minds14_reference_partition_incomplete")
    return references


def _minds14_cases(
    prereg: dict[str, Any], partition: str, source_root: Path
) -> list[dict[str, Any]]:
    key = "blindRecords" if partition == "blind" else "developmentRecords"
    records = [dict(record) for record in prereg["selection"][key]]
    selected_paths = {str(record["path"]) for record in records}
    text_zip = source_root / "extracted" / "MInDS-14" / "text.zip"
    audio_zip = source_root / "extracted" / "MInDS-14" / "audio.zip"
    references = _minds14_references(
        text_zip=text_zip,
        selected_paths=selected_paths,
    )
    cases: list[dict[str, Any]] = []
    with zipfile.ZipFile(audio_zip) as archive:
        entries = {item.filename: item for item in archive.infolist()}
        for record in records:
            path = str(record["path"])
            if path not in entries:
                raise RuntimeError(f"minds14_audio_entry_missing:{path}")
            reference = references[path]
            if reference["intent"] != str(record["intent"]).casefold():
                raise RuntimeError(f"minds14_intent_changed:{path}")
            if reference["language"] != str(record["language"]):
                raise RuntimeError(f"minds14_language_changed:{path}")
            info = entries[path]
            cases.append(
                {
                    "caseId": f"minds14-{record['language']}-{record['rowIndex']:04d}",
                    "selectedPath": path,
                    "audioZip": audio_zip,
                    "audioEntry": path,
                    "audioEntryBytes": info.file_size,
                    "audioEntryCrc32": f"{info.CRC:08x}",
                    "reference": reference["reference"],
                    "languageClass": (
                        "english" if record["language"] == "en-US" else "spanish"
                    ),
                    "language": record["language"],
                    "intent": record["intent"],
                }
            )
    return cases


def _score_minds14_intents(
    *, prereg: dict[str, Any], source_root: Path, results: list[dict[str, Any]]
) -> dict[str, Any]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion
    from sklearn.svm import LinearSVC

    reserved = {
        str(record["path"])
        for key in ("developmentRecords", "blindRecords")
        for record in prereg["selection"][key]
    }
    training: list[tuple[str, str, str]] = []
    text_zip = source_root / "extracted" / "MInDS-14" / "text.zip"
    with zipfile.ZipFile(text_zip) as archive:
        for language in ("en-US", "es-ES"):
            with archive.open(f"{language}.csv") as raw:
                with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
                    for row in csv.DictReader(text):
                        path = str(row["filepath"])
                        if path not in reserved:
                            training.append(
                                (
                                    path,
                                    str(row["text_asr"]),
                                    str(row["intent"]).casefold(),
                                )
                            )
    if len(training) != 769 or len({row[2] for row in training}) != 14:
        raise RuntimeError("minds14_intent_oracle_training_population_changed")
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                ),
            ),
            (
                "character",
                TfidfVectorizer(
                    analyzer="char_wb",
                    strip_accents="unicode",
                    ngram_range=(3, 5),
                    sublinear_tf=True,
                    min_df=2,
                    max_features=50_000,
                ),
            ),
        ]
    )
    training_vectors = features.fit_transform([row[1] for row in training])
    classifier = LinearSVC(C=0.5, class_weight="balanced")
    classifier.fit(training_vectors, [row[2] for row in training])
    reference_predictions = classifier.predict(
        features.transform([str(result["reference"]) for result in results])
    )
    transcript_predictions = classifier.predict(
        features.transform([str(result["productTranscript"]) for result in results])
    )
    for result, reference_prediction, transcript_prediction in zip(
        results,
        reference_predictions,
        transcript_predictions,
        strict=True,
    ):
        gold = str(result["intent"])
        transcript_nonempty = bool(result["productTranscript"])
        result["intentOracle"] = {
            "gold": gold,
            "referencePrediction": str(reference_prediction),
            "transcriptPrediction": str(transcript_prediction),
            "referenceCorrect": str(reference_prediction) == gold,
            "transcriptCorrect": transcript_nonempty
            and str(transcript_prediction) == gold,
            "semanticPreserved": transcript_nonempty
            and str(transcript_prediction) == str(reference_prediction),
        }
    digest = hashlib.sha256()
    for path, text, intent in sorted(training):
        digest.update(
            json.dumps(
                [path, text, intent],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return {
        "schema": "baxy.minds14-intent-oracle.v1",
        "trainingCases": len(training),
        "reservedCasesExcluded": len(reserved),
        "trainingManifestSha256": digest.hexdigest(),
        "classifier": {
            "type": "tfidf-word-character-linear-svc",
            "wordNgrams": [1, 2],
            "characterNgrams": [3, 5],
            "characterMaxFeatures": 50_000,
            "c": 0.5,
            "classWeight": "balanced",
        },
        "blindRowsUsedForTraining": 0,
    }


def _case_result(
    *, case: dict[str, Any], audio: np.ndarray, product_stt: Any
) -> dict[str, Any]:
    reference = _clean_reference(str(case["reference"]))
    strict_reference_tokens = _tokens(reference)
    reference_tokens = _scoring_tokens(reference)
    result: dict[str, Any] = {
        key: value
        for key, value in case.items()
        if key not in {"path", "reference", "audioZip"}
    }
    result["reference"] = reference
    result["referenceTokens"] = len(reference_tokens)
    result["strictReferenceTokens"] = len(strict_reference_tokens)
    result["audioSeconds"] = round(len(audio) / SAMPLE_RATE, 6)
    result["languageClass"] = str(
        case.get("languageClass") or _language_class(reference)
    )
    result["usableReference"] = len(reference_tokens) >= 2
    try:
        raw, corrected, latency = product_stt.transcribe(
            audio, str(case.get("language") or "auto")
        )
        diagnostics = dict(product_stt.last_diagnostics)
        corrected_tokens = _scoring_tokens(corrected)
        distance = _edit_distance(reference_tokens, corrected_tokens)
        raw_distance = _edit_distance(reference_tokens, _scoring_tokens(raw))
        strict_distance = _edit_distance(strict_reference_tokens, _tokens(corrected))
        anchors = _critical_anchors(reference)
        preserved = [anchor for anchor in anchors if _anchor_present(anchor, corrected)]
        result.update(
            {
                "rawTranscript": raw,
                "productTranscript": corrected,
                "nonempty": bool(corrected_tokens),
                "wordErrors": distance,
                "rawWordErrors": raw_distance,
                "wer": round(distance / max(1, len(reference_tokens)), 6),
                "rawWer": round(raw_distance / max(1, len(reference_tokens)), 6),
                "strictWordErrors": strict_distance,
                "strictWer": round(
                    strict_distance / max(1, len(strict_reference_tokens)), 6
                ),
                "criticalAnchors": anchors,
                "criticalAnchorsPreserved": preserved,
                "intentPreservationProxy": (
                    distance / max(1, len(reference_tokens)) <= 0.50
                    and len(preserved) == len(anchors)
                ),
                "latencySeconds": round(latency, 6),
                "finalizationLatencySeconds": round(
                    float(diagnostics["finalizationLatencySeconds"]), 6
                ),
                "maximumChunkDecodeSeconds": round(
                    float(diagnostics["maximumChunkDecodeSeconds"]), 6
                ),
                "realTimeFactor": round(
                    latency / max(0.001, len(audio) / SAMPLE_RATE), 6
                ),
                "error": None,
            }
        )
    except Exception as error:  # noqa: BLE001 - preserve every evaluation failure
        result.update(
            {
                "rawTranscript": "",
                "productTranscript": "",
                "nonempty": False,
                "wordErrors": len(reference_tokens),
                "rawWordErrors": len(reference_tokens),
                "wer": 1.0,
                "rawWer": 1.0,
                "strictWordErrors": len(strict_reference_tokens),
                "strictWer": 1.0,
                "criticalAnchors": _critical_anchors(reference),
                "criticalAnchorsPreserved": [],
                "intentPreservationProxy": False,
                "latencySeconds": None,
                "finalizationLatencySeconds": None,
                "maximumChunkDecodeSeconds": None,
                "realTimeFactor": None,
                "error": f"{type(error).__name__}:{error}",
            }
        )
    return result


def _group_summaries(
    results: list[dict[str, Any]], field: str
) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        value = result.get(field)
        if value is not None:
            groups.setdefault(str(value), []).append(result)
    summaries: dict[str, dict[str, Any]] = {}
    for value, members in sorted(groups.items()):
        reference_tokens = sum(int(item["referenceTokens"]) for item in members)
        word_errors = sum(int(item["wordErrors"]) for item in members)
        anchors = sum(len(item["criticalAnchors"]) for item in members)
        preserved = sum(len(item["criticalAnchorsPreserved"]) for item in members)
        case_wers = [float(item["wer"]) for item in members]
        summaries[value] = {
            "cases": len(members),
            "corpusWer": round(word_errors / max(1, reference_tokens), 6),
            "caseWerP95": _nearest_rank(case_wers, 0.95),
            "nonemptyRate": round(
                sum(bool(item["nonempty"]) for item in members) / len(members), 6
            ),
            "criticalAnchorRecall": (
                1.0 if anchors == 0 else round(preserved / anchors, 6)
            ),
            "intentPreservationProxy": round(
                sum(bool(item["intentPreservationProxy"]) for item in members)
                / len(members),
                6,
            ),
        }
    return summaries


def _aggregate(
    *, source: str, partition: str, results: list[dict[str, Any]]
) -> dict[str, Any]:
    usable = [result for result in results if result["usableReference"]]
    latencies = [
        float(result["latencySeconds"])
        for result in usable
        if result["latencySeconds"] is not None
    ]
    finalization_latencies = [
        float(result["finalizationLatencySeconds"])
        for result in usable
        if result["finalizationLatencySeconds"] is not None
    ]
    real_time_factors = [
        float(result["realTimeFactor"])
        for result in usable
        if result["realTimeFactor"] is not None
    ]
    case_wers = [float(result["wer"]) for result in usable]
    reference_tokens = sum(int(result["referenceTokens"]) for result in usable)
    word_errors = sum(int(result["wordErrors"]) for result in usable)
    strict_reference_tokens = sum(
        int(result["strictReferenceTokens"]) for result in usable
    )
    strict_word_errors = sum(int(result["strictWordErrors"]) for result in usable)
    anchors = sum(len(result["criticalAnchors"]) for result in usable)
    anchors_preserved = sum(
        len(result["criticalAnchorsPreserved"]) for result in usable
    )
    by_language = _group_summaries(usable, "languageClass")
    by_intent = _group_summaries(usable, "intent")
    intent_oracle_results = [
        result for result in usable if isinstance(result.get("intentOracle"), dict)
    ]
    metrics = {
        "cases": len(results),
        "usableCases": len(usable),
        "usableRatio": round(len(usable) / max(1, len(results)), 6),
        "nonemptyRate": round(
            sum(bool(result["nonempty"]) for result in usable) / max(1, len(usable)),
            6,
        ),
        "decodeErrors": sum(result["error"] is not None for result in results),
        "referenceTokens": reference_tokens,
        "wordErrors": word_errors,
        "corpusWer": round(word_errors / max(1, reference_tokens), 6),
        "strictReferenceTokens": strict_reference_tokens,
        "strictWordErrors": strict_word_errors,
        "strictCorpusWer": round(
            strict_word_errors / max(1, strict_reference_tokens), 6
        ),
        "caseWerP50": _nearest_rank(case_wers, 0.50),
        "caseWerP95": _nearest_rank(case_wers, 0.95),
        "criticalAnchors": anchors,
        "criticalAnchorsPreserved": anchors_preserved,
        "criticalAnchorRecall": (
            1.0 if anchors == 0 else round(anchors_preserved / anchors, 6)
        ),
        "intentPreservationProxy": round(
            sum(bool(result["intentPreservationProxy"]) for result in usable)
            / max(1, len(usable)),
            6,
        ),
        "latencyP50Seconds": _nearest_rank(latencies, 0.50),
        "latencyP95Seconds": _nearest_rank(latencies, 0.95),
        "finalizationLatencyP50Seconds": _nearest_rank(finalization_latencies, 0.50),
        "finalizationLatencyP95Seconds": _nearest_rank(finalization_latencies, 0.95),
        "realTimeFactorP50": _nearest_rank(real_time_factors, 0.50),
        "realTimeFactorP95": _nearest_rank(real_time_factors, 0.95),
        "byLanguage": by_language,
        "byIntent": by_intent,
    }
    if intent_oracle_results:
        metrics.update(
            {
                "referenceIntentOracleAccuracy": round(
                    sum(
                        bool(result["intentOracle"]["referenceCorrect"])
                        for result in intent_oracle_results
                    )
                    / len(intent_oracle_results),
                    6,
                ),
                "transcriptIntentAccuracy": round(
                    sum(
                        bool(result["intentOracle"]["transcriptCorrect"])
                        for result in intent_oracle_results
                    )
                    / len(intent_oracle_results),
                    6,
                ),
                "intentSemanticPreservation": round(
                    sum(
                        bool(result["intentOracle"]["semanticPreserved"])
                        for result in intent_oracle_results
                    )
                    / len(intent_oracle_results),
                    6,
                ),
            }
        )
    threshold = THRESHOLDS[source][partition]
    checks = {
        "expectedCases": metrics["cases"] == threshold["expectedCases"],
        "usableRatio": metrics["usableRatio"] >= threshold["minimumUsableRatio"],
        "nonemptyRate": metrics["nonemptyRate"] >= threshold["minimumNonemptyRate"],
        "decodeErrors": metrics["decodeErrors"] == 0,
    }
    if "maximumCorpusWer" in threshold:
        checks["corpusWer"] = metrics["corpusWer"] <= threshold["maximumCorpusWer"]
    if "maximumCaseWerP95" in threshold:
        checks["caseWerP95"] = metrics["caseWerP95"] <= threshold["maximumCaseWerP95"]
    if "maximumLatencyP50Seconds" in threshold:
        checks["latencyP50"] = (
            metrics["latencyP50Seconds"] <= threshold["maximumLatencyP50Seconds"]
        )
    if "maximumLatencyP95Seconds" in threshold:
        checks["latencyP95"] = (
            metrics["latencyP95Seconds"] <= threshold["maximumLatencyP95Seconds"]
        )
    if "minimumCriticalAnchorRecall" in threshold:
        checks["criticalAnchorRecall"] = (
            metrics["criticalAnchorRecall"] >= threshold["minimumCriticalAnchorRecall"]
        )
    if "minimumIntentPreservationProxy" in threshold:
        checks["intentPreservationProxy"] = (
            metrics["intentPreservationProxy"]
            >= threshold["minimumIntentPreservationProxy"]
        )
    if "maximumLanguageCorpusWer" in threshold:
        checks["languageCorpusWer"] = bool(by_language) and all(
            group["corpusWer"] <= threshold["maximumLanguageCorpusWer"]
            for group in by_language.values()
        )
    if "minimumTranscriptIntentAccuracy" in threshold:
        checks["transcriptIntentAccuracy"] = (
            metrics.get("transcriptIntentAccuracy", 0.0)
            >= threshold["minimumTranscriptIntentAccuracy"]
        )
    if "minimumIntentSemanticPreservation" in threshold:
        checks["intentSemanticPreservation"] = (
            metrics.get("intentSemanticPreservation", 0.0)
            >= threshold["minimumIntentSemanticPreservation"]
        )
    if "maximumFinalizationLatencyP95Seconds" in threshold:
        checks["finalizationLatencyP95"] = (
            metrics["finalizationLatencyP95Seconds"]
            <= threshold["maximumFinalizationLatencyP95Seconds"]
        )
    if "maximumRealTimeFactorP95" in threshold:
        checks["realTimeFactorP95"] = (
            metrics["realTimeFactorP95"] <= threshold["maximumRealTimeFactorP95"]
        )
    return {"metrics": metrics, "threshold": threshold, "checks": checks}


def evaluate(arguments: argparse.Namespace) -> dict[str, Any]:
    repository_root = arguments.repository_root.resolve(strict=True)
    contract_path = arguments.contract.resolve(strict=True)
    contract, prereg, runtime = _validate_contract(
        repository_root=repository_root,
        contract_path=contract_path,
        source=arguments.source,
        partition=arguments.partition,
    )
    if arguments.partition == "blind" and arguments.engine not in {
        "parakeet_greedy",
        "nemotron_auto",
    }:
        raise RuntimeError("blind_contract_engine_not_preregistered")
    if arguments.source == "audio_arena":
        cases = _audio_arena_cases(prereg, arguments.partition)
    elif arguments.source == "minds14":
        cases = _minds14_cases(
            prereg,
            arguments.partition,
            Path(str(contract["minds14Source"]["root"])),
        )
    else:
        cases = _miami_cases(prereg, arguments.partition)
    ffmpeg = Path(contract["ffmpeg"]["path"])
    if arguments.engine == "product_parakeet":
        product_stt: Any = ProductStt(repository_root)
    elif arguments.engine == "parakeet_greedy":
        product_stt = ParakeetGreedyStt(Path(str(runtime["sttDirectory"])))
    else:
        product_stt = NemotronStreamingStt(
            Path(str(contract["nemotron"]["path"])),
            "auto" if arguments.engine == "nemotron_auto" else "explicit",
        )
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    for index, case in enumerate(cases, start=1):
        if arguments.source == "audio_arena":
            audio = _load_wav(case["path"])
        elif arguments.source == "minds14":
            with zipfile.ZipFile(case["audioZip"]) as archive:
                audio = _load_wav_bytes(
                    archive.read(case["audioEntry"]),
                    str(case["audioEntry"]),
                    ffmpeg,
                )
        else:
            audio = _load_mp3_segment(
                ffmpeg=ffmpeg,
                source=case["path"],
                start_ms=case["globalStartMs"],
                duration_ms=case["durationMs"],
            )
        results.append(_case_result(case=case, audio=audio, product_stt=product_stt))
        if index % 10 == 0 or index == len(cases):
            print(
                json.dumps(
                    {
                        "progress": index,
                        "total": len(cases),
                        "source": arguments.source,
                        "engine": arguments.engine,
                    }
                ),
                flush=True,
            )
    intent_oracle: dict[str, Any] | None = None
    if arguments.source == "minds14":
        intent_oracle = _score_minds14_intents(
            prereg=prereg,
            source_root=Path(str(contract["minds14Source"]["root"])),
            results=results,
        )
    aggregate = _aggregate(
        source=arguments.source,
        partition=arguments.partition,
        results=results,
    )
    passed = all(aggregate["checks"].values())
    return {
        "schema": REPORT_SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "source": arguments.source,
        "partition": arguments.partition,
        "engine": arguments.engine,
        "status": "passed" if passed else "failed",
        "contract": {
            "path": _relative(repository_root, contract_path),
            "sha256": _sha256(contract_path),
        },
        "evaluator": {
            "path": _relative(repository_root, Path(__file__)),
            "sha256": _sha256(Path(__file__)),
        },
        "runtime": runtime,
        "engineRuntime": {
            "loadSeconds": round(product_stt.load_seconds, 6),
            "status": product_stt.status,
        },
        "intentOracle": intent_oracle,
        "scoringNormalization": SCORING_NORMALIZATION,
        "elapsedSeconds": round(time.perf_counter() - started, 6),
        "aggregate": aggregate,
        "cases": results,
        "effectsExecuted": 0,
    }


def _contract_command(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--role", choices=("development", "blind"), required=True)
    parser.add_argument("--created-at-utc", required=True)
    parser.add_argument("--audio-arena-prereg", type=Path, required=True)
    parser.add_argument("--miami-prereg", type=Path, required=True)
    parser.add_argument("--minds-prereg", type=Path, required=True)
    parser.add_argument("--minds-original-root", type=Path, required=True)
    parser.add_argument("--nemotron-directory", type=Path, required=True)
    parser.add_argument("--fusion-evaluator", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--development-report", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)


def _evaluate_command(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument(
        "--source", choices=("audio_arena", "miami", "minds14"), required=True
    )
    parser.add_argument("--partition", choices=("development", "blind"), required=True)
    parser.add_argument(
        "--engine",
        choices=(
            "product_parakeet",
            "parakeet_greedy",
            "nemotron_auto",
            "nemotron_explicit",
        ),
        default="product_parakeet",
    )
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    _contract_command(commands.add_parser("contract"))
    _evaluate_command(commands.add_parser("evaluate"))
    arguments = parser.parse_args()
    if arguments.command == "contract":
        result = build_contract(arguments)
    else:
        result = evaluate(arguments)
    _write_json(arguments.output, result)
    summary = {
        "output": str(arguments.output),
        "schema": result["schema"],
        "status": result.get("status"),
        "role": result.get("role"),
        "source": result.get("source"),
        "engine": result.get("engine"),
        "partition": result.get("partition"),
        "sha256": _sha256(arguments.output),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
