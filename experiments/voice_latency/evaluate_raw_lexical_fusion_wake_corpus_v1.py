"""Evaluate literal contextual ASR plus frozen phonetic fusion on RAW audio."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_hyperspotter_fusion_physical_room_gate_v1 as fusion  # noqa: E402
import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_multiverifier_wake_physical_room_gate_v1 as multi  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402
from baxy_mind.voice import _fold  # noqa: E402


SCHEMA = "baxy.raw-lexical-fusion-wake-corpus-development.v1"
SAMPLE_RATE = 16_000
FUSION_MARGIN = -4.5
_WORD = re.compile(r"[^\W_]+", flags=re.UNICODE)
_ALIASES = ("baxy", "baxi", "baksi", "backsy", "backsie", "basi", "bokse", "бокс")


def contextual_lexical_evidence(transcript: str) -> bool:
    words = tuple(_fold(match.group(0)) for match in _WORD.finditer(transcript))
    return any(
        word == alias
        or (
            word.startswith(alias)
            and len(word) <= len(alias) + 5
        )
        for word in words
        for alias in _ALIASES
    )


def lexical_fusion_decision(
    *, lexical_evidence: bool, fusion_margin: float
) -> tuple[bool, str]:
    if not lexical_evidence:
        return False, "literal_alias_absent"
    if not np.isfinite(fusion_margin) or fusion_margin < FUSION_MARGIN:
        return False, "phonetic_fusion_rejected"
    return True, "literal_alias_and_phonetic_fusion"


def _summary(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"minimum": None, "p50": None, "p95": None, "maximum": None}
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum": float(np.min(array)),
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "maximum": float(np.max(array)),
    }


def _evaluate_group(
    paths: list[Path],
    *,
    recognizer: object,
    hotwords: str,
    verifier: fusion.HyperspotterFusionDetector,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    margins: list[float] = []
    for index, path in enumerate(paths):
        audio, sample_rate = room._read_pcm16(path)
        audio = room._resample(audio, sample_rate, SAMPLE_RATE)
        started = time.perf_counter()
        transcript, _ = lexical._decode(recognizer, audio, hotwords=hotwords)
        margin = float(verifier._score(multi.fixed_three_second_audio(audio)))
        evidence = contextual_lexical_evidence(transcript)
        accepted, reason = lexical_fusion_decision(
            lexical_evidence=evidence,
            fusion_margin=margin,
        )
        latencies.append(time.perf_counter() - started)
        margins.append(margin)
        records.append(
            {
                "record": index,
                "audioSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "transcriptSha256": hashlib.sha256(
                    transcript.encode("utf-8")
                ).hexdigest(),
                "lexicalEvidence": evidence,
                "fusionMargin": margin,
                "accepted": accepted,
                "reason": reason,
            }
        )
    return {
        "files": len(paths),
        "acceptedFiles": sum(bool(record["accepted"]) for record in records),
        "decisionSeconds": _summary(latencies),
        "fusionMargins": _summary(margins),
        "records": records,
        "transcriptTextRetained": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpus = args.corpus.resolve(strict=True)
    manifest_path = corpus / "manifest.v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("blindHumanPartitionAccessed") is not False:
        raise SystemExit("Corpus blind-boundary attestation is missing.")
    if manifest.get("physicalPath", {}).get("captureTransport") != "wasapi_raw_iaudioclient2":
        raise SystemExit("Corpus is not an attested WASAPI RAW capture.")

    stt_directory = args.stt_directory.resolve(strict=True)
    recognizer, hotwords = lexical._recognizer(stt_directory, 5.0)
    verifier = fusion.HyperspotterFusionDetector(
        fusion_manifest_path=args.fusion_manifest.resolve(strict=True),
        ctc_manifest_path=args.ctc_verifier_manifest.resolve(strict=True),
        model_name="baxy-hyperspotter-ctc-v2",
        phrase="Baxy",
        hop_samples=8_000,
        debounce_seconds=2.0,
        threads=4,
    )
    positives = room._wav_paths(corpus / "positive", None)
    negatives = room._wav_paths(corpus / "negative", None)
    started = time.perf_counter()
    positive = _evaluate_group(
        positives,
        recognizer=recognizer,
        hotwords=hotwords,
        verifier=verifier,
    )
    negative = _evaluate_group(
        negatives,
        recognizer=recognizer,
        hotwords=hotwords,
        verifier=verifier,
    )
    passed = (
        positive["acceptedFiles"] == positive["files"]
        and negative["acceptedFiles"] == 0
    )
    report = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_known_playback_wasapi_raw_literal_wake",
        "policy": {
            "contextualHotwords": ["baxy", "baxi"],
            "literalAliasRequired": True,
            "fusionMarginGte": FUSION_MARGIN,
        },
        "models": {
            "stt": {
                name: room._sha256(stt_directory / filename)
                for name, filename in {
                    "encoderSha256": "encoder.int8.onnx",
                    "decoderSha256": "decoder.int8.onnx",
                    "joinerSha256": "joiner.int8.onnx",
                    "tokensSha256": "tokens.txt",
                }.items()
            },
            "fusion": verifier.source_identities,
        },
        "corpusManifestSha256": room._sha256(manifest_path),
        "positive": positive,
        "negative": negative,
        "elapsedWallSeconds": time.perf_counter() - started,
        "openedDevelopmentPassed": passed,
        "candidateFrozen": passed,
        "blindHumanPartitionAccessed": False,
        "promotable": False,
        "developmentOnly": True,
        "effectsExecuted": 0,
        "filenamesOrTranscriptsRetained": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "passed": passed,
                "positive": positive["acceptedFiles"],
                "negative": negative["acceptedFiles"],
                "latencyP50": positive["decisionSeconds"]["p50"],
                "latencyP95": positive["decisionSeconds"]["p95"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
