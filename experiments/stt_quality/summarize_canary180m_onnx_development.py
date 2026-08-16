"""Publish the development-only Canary 180M ONNX candidate verdict."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT_SCHEMA = "baxy.stt-canary180m-onnx-development.v1"
VERDICT_SCHEMA = "baxy.stt-canary180m-onnx-development-verdict.v1"
EXPECTED_WAKE_TREE_SHA256 = (
    "756a5b311b20ed833da182595766c9d577cca89f20d7a4355eb972576f0f90c0"
)
REPORTS = {
    "audioArenaCanary": ROOT
    / "artifacts/development/stt_audio_arena_canary180m_onnx_cpu_development_v1.json",
    "minds14Canary": ROOT
    / "artifacts/development/stt_minds14_canary180m_onnx_cpu_development_v1.json",
    "minds14Parakeet": ROOT
    / "artifacts/development/stt_minds14_parakeet_greedy_development_v2.json",
    "minds14Nemotron": ROOT
    / "artifacts/development/stt_minds14_nemotron_auto_development_v3.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"canary_verdict_report_invalid:{path}")
    return value


def _intent_correct(case: dict[str, Any]) -> bool:
    oracle = case.get("intentOracle")
    return isinstance(oracle, dict) and bool(oracle.get("transcriptCorrect"))


def build_verdict(repository_root: Path = ROOT) -> dict[str, object]:
    repository_root = repository_root.resolve(strict=True)
    paths = {
        key: repository_root / path.relative_to(ROOT) for key, path in REPORTS.items()
    }
    reports = {key: _read(path) for key, path in paths.items()}
    audio = reports["audioArenaCanary"]
    minds = reports["minds14Canary"]
    parakeet = reports["minds14Parakeet"]
    nemotron = reports["minds14Nemotron"]
    for source, report in (("audio_arena", audio), ("minds14", minds)):
        if (
            report.get("schema") != REPORT_SCHEMA
            or report.get("source") != source
            or report.get("partition") != "development"
            or report.get("blindHoldoutOpened") is not False
            or report.get("candidatePromoted") is not False
            or report.get("effectsExecuted") != 0
            or report.get("wakeProgramTree", {}).get("sha256")
            != EXPECTED_WAKE_TREE_SHA256
        ):
            raise RuntimeError(f"canary_verdict_candidate_report_invalid:{source}")

    canary_rows = {str(row["caseId"]): row for row in minds["cases"]}
    parakeet_rows = {str(row["caseId"]): row for row in parakeet["cases"]}
    nemotron_rows = {str(row["caseId"]): row for row in nemotron["cases"]}
    identities = set(canary_rows)
    if (
        len(identities) != 84
        or identities != set(parakeet_rows)
        or identities != set(nemotron_rows)
    ):
        raise RuntimeError("canary_verdict_minds_population_mismatch")
    unique_beyond_nemotron = sorted(
        identity
        for identity in identities
        if _intent_correct(canary_rows[identity])
        and not _intent_correct(nemotron_rows[identity])
    )
    parakeet_rescues = sorted(
        identity
        for identity in identities
        if _intent_correct(canary_rows[identity])
        and not _intent_correct(parakeet_rows[identity])
    )
    audio_metrics = audio["aggregate"]["metrics"]
    minds_metrics = minds["aggregate"]["metrics"]
    return {
        "schema": VERDICT_SCHEMA,
        "publishedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": "rejected",
        "candidate": {
            "name": "nvidia/canary-180m-flash int8",
            "runtime": "sherpa-onnx 1.13.4 CPU",
            "threadsPerRecognizer": 8,
            "loadedLanguages": ["en", "es"],
        },
        "evidence": {
            key: {
                "path": path.relative_to(repository_root).as_posix(),
                "sha256": sha256(path),
            }
            for key, path in paths.items()
        },
        "results": {
            "audioArena": {
                "cases": audio_metrics["cases"],
                "corpusWer": audio_metrics["corpusWer"],
                "criticalAnchors": audio_metrics["criticalAnchors"],
                "criticalAnchorsPreserved": audio_metrics[
                    "criticalAnchorsPreserved"
                ],
                "criticalAnchorRecall": audio_metrics["criticalAnchorRecall"],
                "latencyP50Seconds": audio_metrics["latencyP50Seconds"],
                "latencyP95Seconds": audio_metrics["latencyP95Seconds"],
            },
            "minds14": {
                "cases": minds_metrics["cases"],
                "nonemptyRate": minds_metrics["nonemptyRate"],
                "transcriptIntentAccuracy": minds_metrics[
                    "transcriptIntentAccuracy"
                ],
                "intentSemanticPreservation": minds_metrics[
                    "intentSemanticPreservation"
                ],
                "finalizationLatencyP95Seconds": minds_metrics[
                    "finalizationLatencyP95Seconds"
                ],
                "realTimeFactorP95": minds_metrics["realTimeFactorP95"],
                "peakRssBytesObserved": minds["engineRuntime"][
                    "peakRssBytesObserved"
                ],
                "emptyTranscripts": sum(
                    not bool(row["nonempty"]) for row in canary_rows.values()
                ),
                "parakeetIntentRescues": parakeet_rescues,
                "uniqueIntentRescuesBeyondNemotron": unique_beyond_nemotron,
            },
        },
        "decision": {
            "primaryEngine": "rejected",
            "fallbackEngine": "rejected",
            "candidatePromoted": False,
            "reasons": [
                "audio_arena_critical_anchor_recall_below_0_99",
                "minds14_nonempty_rate_below_1_0",
                "minds14_intent_accuracy_below_0_95",
                "minds14_semantic_preservation_below_0_99",
                "no_unique_minds14_intent_rescue_beyond_nemotron",
                "explicit_language_required_and_code_switch_not_supported",
            ],
            "nextArchitecture": (
                "multilingual auto-language acoustic consensus with direct semantic evidence"
            ),
        },
        "developmentOnly": True,
        "blindHoldoutOpened": False,
        "thresholdsChanged": False,
        "wakeProgramTreeSha256": EXPECTED_WAKE_TREE_SHA256,
        "effectsExecuted": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists():
        raise RuntimeError("canary_verdict_output_exists")
    verdict = build_verdict(arguments.repository_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {"output": str(output), "status": verdict["status"], "sha256": sha256(output)}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
