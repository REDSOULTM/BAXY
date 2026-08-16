"""Evaluate the selected QbyT verifier on exact opened-human fusion views."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_qbyt_contextual_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V5 = load_component(
    "evaluate_baxy_contextual_consensus_development_v5.py",
    "_baxy_qbyt_contextual_v5",
)
_QBYT = load_component("qbyt_wake_verifier.py", "_baxy_qbyt_contextual_verifier")


def qbyt_same_view_policy(
    *,
    established: bool,
    fixed: bool,
    full_hot: bool,
    observation: object,
    base_signals: object,
) -> dict[str, bool]:
    del established, full_hot
    accepted = observation.get("acceptedByView", {}) if isinstance(observation, dict) else {}
    acoustic = observation.get("acousticByView", {}) if isinstance(observation, dict) else {}
    qbyt = bool(
        fixed
        and any(
            acoustic.get(start) is True and accepted.get(start) is True
            for start in acoustic
        )
    )
    dual = bool(
        isinstance(base_signals, dict)
        and base_signals.get("sameViewDualDecode") is True
    )
    return {"sameViewQbyT": qbyt, "sameViewQbyTOrDualDecode": qbyt or dual}


def evaluate(
    *,
    qbyt_candidate_path: Path,
    teacher_directory: Path,
    output_path: Path,
    device: str,
    sherpa_site_packages_path: Path | None = None,
    **arguments: object,
) -> dict[str, object]:
    candidate = _QBYT.load_candidate(qbyt_candidate_path, teacher_directory)
    verifier = _QBYT.Wav2Vec2QbyTVerifier(candidate, device=device)
    if sherpa_site_packages_path is not None:
        sys.path.append(str(sherpa_site_packages_path.resolve(strict=True)))

    fallback_diagnostics: list[dict[str, object]] = []
    fallback_policy_index = 0

    def observe(
        views: object,
        margins: object,
        probabilities: object,
        wake: object,
        metadata: object,
    ) -> object:
        del probabilities, wake
        scores = {start: verifier.score(audio) for start, audio in views.items()}
        observation = {
            "scoresByView": scores,
            "acceptedByView": {
                start: score >= float(candidate["threshold"])
                for start, score in scores.items()
            },
            "acousticByView": {
                start: float(margin) >= 0.0 for start, margin in margins.items()
            },
        }
        if (
            isinstance(metadata, dict)
            and metadata.get("fixed") is True
            and metadata.get("established") is False
        ):
            fusion_scores = [
                score
                for start, score in scores.items()
                if observation["acousticByView"].get(start) is True
            ]
            fallback_diagnostics.append(
                {
                    "maximumFusionPassingQbyTScore": max(fusion_scores),
                    "qbytAccepted": max(fusion_scores)
                    >= float(candidate["threshold"]),
                }
            )
        return observation

    def policy_with_diagnostics(**values: object) -> dict[str, bool]:
        nonlocal fallback_policy_index
        result = qbyt_same_view_policy(**values)
        if values.get("fixed") is True and values.get("established") is False:
            fallback_diagnostics[fallback_policy_index]["dualDecodeAccepted"] = bool(
                isinstance(values.get("base_signals"), dict)
                and values["base_signals"].get("sameViewDualDecode") is True
            )
            fallback_policy_index += 1
        return result

    report = _V5.evaluate(
        output_path=output_path,
        fixed_view_audio_observer=observe,
        additional_policy_factory=policy_with_diagnostics,
        **arguments,
    )
    report["schema"] = "baxy.qbyt-contextual-development.v9"
    report["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = "opened_human_development_exact_fusion_view_qbyt"
    report["qbytContract"] = {
        "candidateSha256": _V5._PRODUCT.sha256(candidate["path"]),
        "sameExactFusionView": True,
        "selectedAfterOpened100hContextualFailure": True,
        "freshHoldoutClaimSupported": False,
    }
    report["qbytFallbackDiagnostics"] = fallback_diagnostics
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
    parser.add_argument("--qbyt-candidate", type=Path, required=True)
    parser.add_argument("--teacher-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--sherpa-site-packages", type=Path)
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
        qbyt_candidate_path=arguments.qbyt_candidate,
        teacher_directory=arguments.teacher_directory,
        output_path=arguments.output,
        device=arguments.device,
        sherpa_site_packages_path=arguments.sherpa_site_packages,
        stt_batch_size=arguments.stt_batch_size,
    )
    summary = report["policySummaries"]["sameViewQbyTOrDualDecode"]
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["gatePassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
