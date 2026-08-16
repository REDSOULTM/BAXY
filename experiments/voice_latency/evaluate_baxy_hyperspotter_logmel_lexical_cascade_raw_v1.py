"""Evaluate the frozen HyperSpotter -> log-Mel -> lexical wake cascade.

The two upstream HyperSpotter reports are immutable candidate generators.  A
compact ONNX verifier scores only the exact rolling windows that generated a
candidate.  Parakeet runs only for candidates below the acoustic threshold and
may rescue only an entire transcript that normalizes to one exact BAXY alias.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
import unicodedata
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (ROOT / "src", ROOT / "scripts", HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import audit_baxy_hyperspotter_fusion_product_candidate_v1 as hyper  # noqa: E402
import evaluate_raw_lexical_fusion_wake_corpus_v1 as summaries  # noqa: E402
import evaluate_raw_rolling_multialias_wake_corpus_v2 as upstream  # noqa: E402
import run_lexical_wake_physical_room_gate_v1 as lexical  # noqa: E402
import run_wakeword_physical_room_gate as room  # noqa: E402


SCHEMA = "baxy.hyperspotter-logmel-lexical-cascade-raw-development.v1"
UPSTREAM_SCHEMA = "baxy.raw-rolling-multialias-wake-corpus-development.v2"
SAMPLE_RATE = 16_000
LOGMEL_FRAMES = 300
LOGMEL_BINS = 80
EXACT_ALIASES = frozenset(("baxy", "baxi", "boxy"))


def normalize_lexical_transcript(text: str) -> str:
    folded = unicodedata.normalize("NFKD", str(text)).casefold()
    folded = "".join(character for character in folded if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", folded).strip()


def has_strict_exact_alias(text: str) -> bool:
    return normalize_lexical_transcript(text) in EXACT_ALIASES


def has_strict_leading_alias(text: str) -> bool:
    words = normalize_lexical_transcript(text).split()
    return bool(words) and words[0] in EXACT_ALIASES


def cascade_decision(
    *, upstream_candidate: bool, logmel_score: float | None, threshold: float,
    lexical_exact_alias: bool,
) -> tuple[bool, str]:
    if not upstream_candidate:
        return False, "no_upstream_candidate"
    if logmel_score is None or not math.isfinite(logmel_score):
        raise ValueError("baxy_wake_cascade_logmel_score_invalid")
    if logmel_score >= threshold:
        return True, "logmel_verifier"
    if lexical_exact_alias:
        return True, "strict_lexical_rescue"
    return False, "candidate_rejected"


def candidate_window_indexes(
    reports: list[dict[str, object]], section: str, record_index: int
) -> tuple[int, ...]:
    indexes: set[int] = set()
    for report in reports:
        group = report.get(section)
        records = group.get("records") if isinstance(group, dict) else None
        if not isinstance(records, list) or record_index >= len(records):
            raise ValueError("baxy_wake_cascade_upstream_records_invalid")
        record = records[record_index]
        if not isinstance(record, dict) or record.get("record") != record_index:
            raise ValueError("baxy_wake_cascade_upstream_record_order_invalid")
        if record.get("accepted") is True:
            window_index = record.get("firstAcceptedWindowIndex")
            if not isinstance(window_index, int) or window_index < 0:
                raise ValueError("baxy_wake_cascade_candidate_window_invalid")
            indexes.add(window_index)
        elif record.get("accepted") is not False:
            raise ValueError("baxy_wake_cascade_upstream_decision_invalid")
    return tuple(sorted(indexes))


def verifier_window_indexes(candidate_indexes: tuple[int, ...]) -> tuple[int, ...]:
    """Return the rolling history already available at the first candidate."""

    if not candidate_indexes:
        return ()
    return tuple(range(candidate_indexes[0] + 1))


def _validate_reports(
    reports: list[dict[str, object]], *, corpus_manifest_sha256: str,
    groups: dict[str, list[Path]],
) -> None:
    if len(reports) < 2:
        raise ValueError("baxy_wake_cascade_upstream_ensemble_incomplete")
    for report in reports:
        if (
            report.get("schema") != UPSTREAM_SCHEMA
            or report.get("corpusManifestSha256") != corpus_manifest_sha256
            or report.get("blindHumanPartitionAccessed") is not False
        ):
            raise ValueError("baxy_wake_cascade_upstream_boundary_invalid")
        for section, paths in groups.items():
            group = report.get(section)
            records = group.get("records") if isinstance(group, dict) else None
            if (
                not isinstance(records, list)
                or group.get("files") != len(paths)
                or len(records) != len(paths)
            ):
                raise ValueError("baxy_wake_cascade_upstream_count_invalid")
            for index, (record, path) in enumerate(zip(records, paths)):
                if (
                    not isinstance(record, dict)
                    or record.get("record") != index
                    or record.get("audioSha256") != room._sha256(path)
                ):
                    raise ValueError("baxy_wake_cascade_upstream_audio_drift")


def _recognizer(stt_directory: Path) -> tuple[Any, dict[str, str]]:
    import sherpa_onnx

    required = {
        "encoder": stt_directory / "encoder.int8.onnx",
        "decoder": stt_directory / "decoder.int8.onnx",
        "joiner": stt_directory / "joiner.int8.onnx",
        "tokens": stt_directory / "tokens.txt",
    }
    if any(not path.is_file() for path in required.values()):
        raise ValueError("baxy_wake_cascade_stt_bundle_incomplete")
    recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(required["encoder"]),
        decoder=str(required["decoder"]),
        joiner=str(required["joiner"]),
        tokens=str(required["tokens"]),
        num_threads=4,
        model_type="nemo_transducer",
        decoding_method="modified_beam_search",
        max_active_paths=8,
    )
    return recognizer, {
        name + "Sha256": room._sha256(path) for name, path in required.items()
    }


class LogMelVerifier:
    def __init__(self, model_path: Path, mel_filters: np.ndarray) -> None:
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = 4
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(model_path), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self._mel_filters = np.asarray(mel_filters, dtype=np.float32)
        if self._mel_filters.shape != (LOGMEL_BINS, 201):
            raise ValueError("baxy_wake_cascade_mel_filters_invalid")
        self.model_sha256 = room._sha256(model_path)
        self.score_windows((np.zeros(48_000, dtype=np.float32),))

    def score_windows(self, windows: tuple[np.ndarray, ...]) -> np.ndarray:
        if not windows:
            return np.empty(0, dtype=np.float32)
        features = np.stack(
            [hyper.numpy_log_mel_spectrogram(window, self._mel_filters) for window in windows]
        ).astype(np.float32)
        if features.shape[1:] != (LOGMEL_FRAMES, LOGMEL_BINS):
            raise ValueError("baxy_wake_cascade_logmel_shape_invalid")
        result = self._session.run(["wake_logit"], {"logmel": features})[0]
        scores = np.asarray(result, dtype=np.float32).reshape(-1)
        if len(scores) != len(windows) or not np.isfinite(scores).all():
            raise ValueError("baxy_wake_cascade_model_output_invalid")
        return scores


def _evaluate_group(
    paths: list[Path], *, section: str, reports: list[dict[str, object]],
    verifier: LogMelVerifier, recognizer: Any, threshold: float,
) -> dict[str, object]:
    records: list[dict[str, object]] = []
    latencies: list[float] = []
    scores: list[float] = []
    for index, path in enumerate(paths):
        audio, sample_rate = room._read_pcm16(path)
        audio = room._resample(audio, sample_rate, SAMPLE_RATE)
        window_indexes = candidate_window_indexes(reports, section, index)
        history_indexes = verifier_window_indexes(window_indexes)
        started = time.perf_counter()
        score: float | None = None
        transcript_hash: str | None = None
        lexical_exact = False
        if window_indexes:
            rolling_windows = upstream.continuous_rolling_windows(audio)
            if any(value >= len(rolling_windows) for value in history_indexes):
                raise ValueError("baxy_wake_cascade_candidate_window_out_of_range")
            candidate_windows = tuple(rolling_windows[value] for value in history_indexes)
            candidate_scores = verifier.score_windows(candidate_windows)
            score = float(np.max(candidate_scores))
            scores.append(score)
            if score < threshold:
                transcript, _ = lexical._decode(recognizer, audio)
                transcript_hash = hashlib.sha256(transcript.encode("utf-8")).hexdigest()
                lexical_exact = has_strict_leading_alias(transcript)
        accepted, reason = cascade_decision(
            upstream_candidate=bool(window_indexes),
            logmel_score=score,
            threshold=threshold,
            lexical_exact_alias=lexical_exact,
        )
        latencies.append(time.perf_counter() - started)
        records.append(
            {
                "record": index,
                "audioSha256": room._sha256(path),
                "upstreamCandidate": bool(window_indexes),
                "candidateWindowIndexes": list(window_indexes),
                "verifierWindowIndexes": list(history_indexes),
                "logmelVerifierScore": score,
                "lexicalVerifierInvoked": bool(window_indexes) and score is not None and score < threshold,
                "lexicalTranscriptSha256": transcript_hash,
                "lexicalExactAlias": lexical_exact,
                "accepted": accepted,
                "reason": reason,
            }
        )
    return {
        "files": len(paths),
        "upstreamCandidateFiles": sum(bool(record["upstreamCandidate"]) for record in records),
        "logmelAcceptedFiles": sum(
            record["logmelVerifierScore"] is not None
            and float(record["logmelVerifierScore"]) >= threshold
            for record in records
        ),
        "lexicalInvocations": sum(bool(record["lexicalVerifierInvoked"]) for record in records),
        "lexicalAcceptedFiles": sum(record["reason"] == "strict_lexical_rescue" for record in records),
        "acceptedFiles": sum(bool(record["accepted"]) for record in records),
        "verificationSeconds": summaries._summary(latencies),
        "candidateLogmelScores": summaries._summary(scores) if scores else None,
        "records": records,
        "transcriptTextRetained": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--candidate-report", type=Path, action="append", required=True)
    parser.add_argument("--logmel-verifier", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--threshold", type=float, default=3.0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--role", choices=("development", "validation"), required=True)
    args = parser.parse_args()

    if not math.isfinite(args.threshold):
        raise SystemExit("Threshold must be finite.")
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Output already exists.")
    corpus = args.corpus.resolve(strict=True)
    manifest_path = (corpus / "manifest.v1.json").resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("blindHumanPartitionAccessed") is not False
        or manifest.get("physicalPath", {}).get("captureTransport") != "wasapi_raw_iaudioclient2"
    ):
        raise SystemExit("Corpus is not an opened attested WASAPI RAW capture.")
    groups = {
        "positive": room._wav_paths(corpus / "positive", None),
        "negative": room._wav_paths(corpus / "negative", None),
    }
    report_paths = [path.resolve(strict=True) for path in args.candidate_report]
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    corpus_manifest_sha256 = room._sha256(manifest_path)
    _validate_reports(
        reports, corpus_manifest_sha256=corpus_manifest_sha256, groups=groups
    )

    fusion = hyper.load_fusion_candidate(
        args.fusion_manifest.resolve(strict=True),
        args.ctc_verifier_manifest.resolve(strict=True),
    )
    verifier = LogMelVerifier(
        args.logmel_verifier.resolve(strict=True), fusion["mel_filters"]
    )
    recognizer, stt_identities = _recognizer(args.stt_directory.resolve(strict=True))
    started = time.perf_counter()
    positive = _evaluate_group(
        groups["positive"], section="positive", reports=reports,
        verifier=verifier, recognizer=recognizer, threshold=args.threshold,
    )
    negative = _evaluate_group(
        groups["negative"], section="negative", reports=reports,
        verifier=verifier, recognizer=recognizer, threshold=args.threshold,
    )
    passed = (
        positive["acceptedFiles"] == positive["files"]
        and negative["acceptedFiles"] == 0
    )
    result = {
        "schema": SCHEMA,
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_known_playback_raw_candidate_window_cascade",
        "role": args.role,
        "policy": {
            "upstream": "union_of_frozen_same_window_multialias_reports",
            "logmelWindowScope": "rolling_history_through_first_upstream_candidate",
            "logmelVerifierScoreGte": args.threshold,
            "lexicalFallback": "full_utterance_leading_exact_normalized_alias",
            "exactAliases": sorted(EXACT_ALIASES),
        },
        "models": {
            "fusionManifestSha256": room._sha256(fusion["manifest_path"]),
            "melFiltersSha256": room._sha256(fusion["mel_path"]),
            "upstreamReportSha256": [room._sha256(path) for path in report_paths],
            "logmelVerifierSha256": verifier.model_sha256,
            "parakeet": stt_identities,
        },
        "corpusManifestSha256": corpus_manifest_sha256,
        "positive": positive,
        "negative": negative,
        "elapsedWallSeconds": time.perf_counter() - started,
        "openedCorpusPassed": passed,
        "candidateFrozen": passed and args.role == "development",
        "blindHumanPartitionAccessed": False,
        "promotable": passed and args.role == "validation",
        "developmentOnly": True,
        "effectsExecuted": 0,
        "filenamesOrTranscriptsRetained": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({
        "passed": passed,
        "positive": positive["acceptedFiles"],
        "negative": negative["acceptedFiles"],
        "lexicalInvocations": positive["lexicalInvocations"] + negative["lexicalInvocations"],
        "verificationP95": positive["verificationSeconds"]["p95"],
    }, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
