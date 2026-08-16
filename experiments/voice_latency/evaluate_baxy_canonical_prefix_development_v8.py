"""Test a bounded canonical-prefix lexical guard on opened human audio."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_canonical_prefix_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V5 = load_component(
    "evaluate_baxy_contextual_consensus_development_v5.py",
    "_baxy_canonical_prefix_v5",
)


def canonical_prefix_evidence(transcript: str, wake: object) -> bool:
    words = wake.lexical_words(transcript)
    if not words:
        return False
    first = words[0]
    return any(
        first.startswith(prefix) and len(first) <= len(prefix) + 3
        for prefix in ("baxy", "baxi")
    )


def evaluate(*, output_path: Path, **arguments: object) -> dict[str, object]:
    report = _V5.evaluate(
        output_path=output_path,
        hot_evidence_predicate=canonical_prefix_evidence,
        **arguments,
    )
    report["schema"] = "baxy.canonical-prefix-contextual-development.v8"
    report["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = "opened_human_development_canonical_prefix_selection"
    report["lexicalGuard"] = {
        "position": "first_normalized_word",
        "prefixes": ["baxy", "baxi"],
        "maximumSuffixCharacters": 3,
        "selectedAfterOpened100hFailureAnalysis": True,
        "freshHoldoutClaimSupported": False,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expanded-corpus-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--prior-contextual-development", type=Path, required=True)
    parser.add_argument("--failed-negative-regression", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        expanded_corpus_manifest_path=arguments.expanded_corpus_manifest,
        stage1_model_path=arguments.stage1_model,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        fusion_manifest_path=arguments.fusion_manifest,
        stt_directory=arguments.stt_directory,
        ffmpeg_path=arguments.ffmpeg,
        prior_contextual_development_path=arguments.prior_contextual_development,
        failed_negative_regression_path=arguments.failed_negative_regression,
        output_path=arguments.output,
        stt_batch_size=arguments.stt_batch_size,
    )
    summary = report["policySummaries"]["sameViewHot"]
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["gatePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
