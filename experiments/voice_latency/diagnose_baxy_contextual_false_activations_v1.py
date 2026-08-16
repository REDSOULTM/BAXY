"""Expose aggregate lexical causes of opened-corpus contextual false accepts.

This is a development diagnostic, not an operating-point evaluator.  It reuses
the completed acoustic screening cache and records only normalized transcript
strings emitted by the bounded same-view Parakeet pass.  No filename, corpus
identifier, or audio is retained.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path


def load_component(filename: str, name: str) -> object:
    import importlib.util

    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_contextual_diagnostic_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V7 = load_component(
    "evaluate_baxy_explicit_confusable_negative_regression_v7.py",
    "_baxy_contextual_diagnostic_v7",
)


def summarize_transcripts(
    transcripts: list[str], evidence: list[bool]
) -> dict[str, object]:
    if len(transcripts) != len(evidence):
        raise ValueError("baxy_contextual_diagnostic_alignment_invalid")
    normalized = [" ".join(value.casefold().split()) for value in transcripts]
    accepted = [value for value, keep in zip(normalized, evidence, strict=True) if keep]
    return {
        "decodedCaptures": len(normalized),
        "lexicalEvidenceCaptures": len(accepted),
        "distinctDecodedTranscripts": len(set(normalized)),
        "distinctLexicalEvidenceTranscripts": len(set(accepted)),
        "lexicalEvidenceTranscriptCounts": dict(sorted(Counter(accepted).items())),
    }


def diagnose(*, output_path: Path, inner_output_path: Path, **arguments: object) -> dict[str, object]:
    if output_path.exists() or inner_output_path.exists():
        raise ValueError("baxy_contextual_diagnostic_output_exists")
    transcripts: list[str] = []
    evidence: list[bool] = []
    original = _V7._V2._V4.has_contextual_wake_evidence

    def observe(transcript: str, wake: object) -> bool:
        decision = bool(original(transcript, wake))
        transcripts.append(str(transcript))
        evidence.append(decision)
        return decision

    _V7._V2._V4.has_contextual_wake_evidence = observe
    try:
        inner = _V7.evaluate(output_path=inner_output_path, **arguments)
    finally:
        _V7._V2._V4.has_contextual_wake_evidence = original

    summary = summarize_transcripts(transcripts, evidence)
    if (
        summary["decodedCaptures"] != inner["metrics"]["contextualDecodedCaptures"]
        or inner.get("regressionPassed") is not False
    ):
        raise ValueError("baxy_contextual_diagnostic_inner_result_invalid")
    report: dict[str, object] = {
        "schema": "baxy.contextual-false-activation-diagnostic.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "previously_opened_100h_same_view_lexical_failure_analysis",
        "sources": {
            "innerReportSha256": _V7._V2._PRODUCT.sha256(inner_output_path),
        },
        "metrics": summary,
        "developmentOnly": True,
        "negativeCorpusPreviouslyAccessed": True,
        "normalizedTranscriptsRetained": True,
        "filenamesOrCorpusIdentifiersRetained": False,
        "audioRetained": False,
        "candidateFrozen": False,
        "productOperatingPoint": False,
        "effectsExecuted": 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ensemble-report", type=Path, required=True)
    parser.add_argument("--screening-cache", type=Path, required=True)
    parser.add_argument("--expected-sentinel-candidates", type=int, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--cuda-parity-report", type=Path, required=True)
    parser.add_argument("--teacher-directory", type=Path, required=True)
    parser.add_argument("--prior-holdout-report", type=Path, required=True)
    parser.add_argument("--prior-stage1-scan", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--sherpa-site-packages", type=Path)
    parser.add_argument("--inner-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cuda-batch-size", type=int, default=32)
    parser.add_argument("--record-batch-size", type=int, default=64)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    parser.add_argument("--stage1-workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    values = vars(arguments)
    report = diagnose(
        output_path=values.pop("output"),
        inner_output_path=values.pop("inner_output"),
        ensemble_report_path=values.pop("ensemble_report"),
        screening_cache_path=values.pop("screening_cache"),
        expected_sentinel_candidates=values.pop("expected_sentinel_candidates"),
        fusion_manifest_path=values.pop("fusion_manifest"),
        ctc_manifest_path=values.pop("ctc_verifier_manifest"),
        cuda_parity_report_path=values.pop("cuda_parity_report"),
        teacher_directory=values.pop("teacher_directory"),
        prior_holdout_report_path=values.pop("prior_holdout_report"),
        prior_stage1_scan_path=values.pop("prior_stage1_scan"),
        corpus_manifest_path=values.pop("corpus_manifest"),
        stage1_model_path=values.pop("stage1_model"),
        ffmpeg_path=values.pop("ffmpeg"),
        stt_directory=values.pop("stt_directory"),
        sherpa_site_packages_path=values.pop("sherpa_site_packages"),
        **values,
    )
    print(json.dumps(report["metrics"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
