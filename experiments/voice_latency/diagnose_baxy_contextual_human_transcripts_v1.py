"""Record opened-human aggregate transcript shapes for contextual diagnosis."""

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
        raise RuntimeError(f"baxy_contextual_human_diagnostic_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V5 = load_component(
    "evaluate_baxy_contextual_consensus_development_v5.py",
    "_baxy_contextual_human_diagnostic_v5",
)


def evaluate(*, output_path: Path, inner_output_path: Path, **arguments: object) -> dict[str, object]:
    if output_path.exists() or inner_output_path.exists():
        raise ValueError("baxy_contextual_human_diagnostic_output_exists")
    decoded: dict[str, list[dict[str, object]]] = {}

    def observe(
        phase: str,
        proposals: list[dict[str, object]],
        transcripts: dict[int, str],
    ) -> None:
        decoded[phase] = [
            {
                "label": proposal.get("label"),
                "viewStartSample": proposal.get("viewStartSample"),
                "transcript": " ".join(transcripts[id(proposal)].casefold().split()),
            }
            for proposal in proposals
        ]

    inner = _V5.evaluate(
        output_path=inner_output_path,
        decode_observer=observe,
        **arguments,
    )
    report: dict[str, object] = {
        "schema": "baxy.contextual-human-transcript-diagnostic.v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_human_development_contextual_failure_analysis",
        "sources": {"innerReportSha256": _V5._PRODUCT.sha256(inner_output_path)},
        "decoded": decoded,
        "developmentOnly": True,
        "blindHumanAudioAccessed": False,
        "normalizedTranscriptsRetained": True,
        "filenamesRetained": False,
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
    parser.add_argument("--expanded-corpus-manifest", type=Path, required=True)
    parser.add_argument("--stage1-model", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--fusion-manifest", type=Path, required=True)
    parser.add_argument("--stt-directory", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--prior-contextual-development", type=Path, required=True)
    parser.add_argument("--failed-negative-regression", type=Path, required=True)
    parser.add_argument("--inner-output", type=Path, required=True)
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
        inner_output_path=arguments.inner_output,
        output_path=arguments.output,
        stt_batch_size=arguments.stt_batch_size,
    )
    print(json.dumps({name: len(rows) for name, rows in report["decoded"].items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
