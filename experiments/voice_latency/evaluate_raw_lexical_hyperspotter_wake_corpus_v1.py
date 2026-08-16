"""Evaluate literal contextual ASR plus fast HyperSpotter on RAW room audio."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_baxy_hyperspotter_fusion_product_candidate_v1 as hyper  # noqa: E402
import evaluate_raw_lexical_fusion_wake_corpus_v1 as lexical_gate  # noqa: E402
import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_multiverifier_wake_physical_room_gate_v1 as multi  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402


SCHEMA = "baxy.raw-lexical-hyperspotter-wake-corpus-development.v1"
SAMPLE_RATE = 16_000
HYPERSPOTTER_LOGIT = 0.5


def lexical_hyperspotter_decision(
    *, lexical_evidence: bool, hyperspotter_logit: float
) -> tuple[bool, str]:
    if not lexical_evidence:
        return False, "literal_alias_absent"
    if not np.isfinite(hyperspotter_logit) or hyperspotter_logit < HYPERSPOTTER_LOGIT:
        return False, "hyperspotter_rejected"
    return True, "literal_alias_and_hyperspotter"


class FastHyperspotter:
    def __init__(self, fusion_manifest: Path, ctc_manifest: Path) -> None:
        candidate = hyper.load_fusion_candidate(fusion_manifest, ctc_manifest)
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(candidate["graph_path"]),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._mel_filters = np.asarray(candidate["mel_filters"], dtype=np.float32)
        self.identities = {
            "fusionManifestSha256": hyper.sha256(candidate["manifest_path"]),
            "graphSha256": hyper.sha256(candidate["graph_path"]),
            "melFiltersSha256": hyper.sha256(candidate["mel_path"]),
        }
        self.score(np.zeros(hyper.AUDIO_SAMPLES, dtype=np.float32))

    def score(self, audio: np.ndarray) -> float:
        values = multi.fixed_three_second_audio(audio)
        logmel = hyper.numpy_log_mel_spectrogram(values, self._mel_filters)
        logits = self._session.run(
            ["logits"],
            {"logmel": logmel[None, :, :]},
        )[0]
        if logits.shape != (1, len(hyper.ALIASES)) or not np.isfinite(logits).all():
            raise ValueError("raw_lexical_hyperspotter_logits_invalid")
        return float(np.max(logits))


def _evaluate_group(
    paths: list[Path],
    *,
    recognizer: object,
    hotwords: str,
    verifier: FastHyperspotter,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    logits: list[float] = []
    for index, path in enumerate(paths):
        audio, sample_rate = room._read_pcm16(path)
        audio = room._resample(audio, sample_rate, SAMPLE_RATE)
        started = time.perf_counter()
        transcript, _ = lexical._decode(recognizer, audio, hotwords=hotwords)
        logit = verifier.score(audio)
        evidence = lexical_gate.contextual_lexical_evidence(transcript)
        accepted, reason = lexical_hyperspotter_decision(
            lexical_evidence=evidence,
            hyperspotter_logit=logit,
        )
        latencies.append(time.perf_counter() - started)
        logits.append(logit)
        records.append(
            {
                "record": index,
                "audioSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "transcriptSha256": hashlib.sha256(
                    transcript.encode("utf-8")
                ).hexdigest(),
                "lexicalEvidence": evidence,
                "hyperspotterMaximumLogit": logit,
                "accepted": accepted,
                "reason": reason,
            }
        )
    return {
        "files": len(paths),
        "acceptedFiles": sum(bool(record["accepted"]) for record in records),
        "decisionSeconds": lexical_gate._summary(latencies),
        "hyperspotterMaximumLogits": lexical_gate._summary(logits),
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
    verifier = FastHyperspotter(
        args.fusion_manifest.resolve(strict=True),
        args.ctc_verifier_manifest.resolve(strict=True),
    )
    started = time.perf_counter()
    positive = _evaluate_group(
        room._wav_paths(corpus / "positive", None),
        recognizer=recognizer,
        hotwords=hotwords,
        verifier=verifier,
    )
    negative = _evaluate_group(
        room._wav_paths(corpus / "negative", None),
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
        "scope": "opened_known_playback_wasapi_raw_literal_fast_wake",
        "policy": {
            "contextualHotwords": ["baxy", "baxi"],
            "literalAliasRequired": True,
            "hyperspotterMaximumLogitGte": HYPERSPOTTER_LOGIT,
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
            "hyperspotter": verifier.identities,
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
