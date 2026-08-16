"""Run cached 100 h regression with QbyT-or-plain same-view verification."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_qbyt_dual_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_V2 = load_component(
    "evaluate_baxy_contextual_fusion_negative_regression_v2.py",
    "_baxy_qbyt_dual_v2",
)
_V7 = load_component(
    "evaluate_baxy_explicit_confusable_negative_regression_v7.py",
    "_baxy_qbyt_dual_v7",
)
_QBYT = load_component("qbyt_wake_verifier.py", "_baxy_qbyt_dual_verifier")


def validate_human_evidence(report: object, candidate_sha256: str) -> None:
    if not isinstance(report, dict):
        raise ValueError("baxy_qbyt_dual_human_evidence_invalid")
    summary = report.get("policySummaries", {}).get("sameViewQbyTOrDualDecode", {})
    if (
        report.get("schema") != "baxy.qbyt-contextual-development.v9"
        or summary.get("positiveHits") != 4
        or summary.get("positiveTotal") != 4
        or summary.get("falseHits") != 0
        or summary.get("negativeTotal") != 8
        or summary.get("gatePassed") is not True
        or report.get("qbytContract", {}).get("candidateSha256") != candidate_sha256
        or report.get("blindHumanAudioAccessed") is not False
    ):
        raise ValueError("baxy_qbyt_dual_human_evidence_invalid")


def combine_secondary_evidence(
    *, explicit_sequence_allowed: bool, qbyt_accepted: bool, plain_accepted: bool
) -> bool:
    return bool(explicit_sequence_allowed and (qbyt_accepted or plain_accepted))


class QbyTOrPlainGuard:
    def __init__(
        self,
        *,
        candidate: dict[str, object],
        device: str,
        stt_directory: Path,
        sherpa_site_packages_path: Path | None,
    ) -> None:
        self._candidate = candidate
        self._device = device
        self._stt_directory = stt_directory.resolve(strict=True)
        self._sherpa_site_packages_path = (
            sherpa_site_packages_path.resolve(strict=True)
            if sherpa_site_packages_path is not None
            else None
        )
        self._qbyt: object | None = None
        self._recognizer: object | None = None
        self.confusable_rejected_views = 0
        self.qbyt_accepted_views = 0
        self.plain_decoded_views = 0
        self.plain_accepted_views = 0
        self.view_diagnostics: dict[tuple[int, int], dict[str, object]] = {}

    def _load_qbyt(self) -> object:
        if self._qbyt is None:
            self._qbyt = _QBYT.Wav2Vec2QbyTVerifier(
                self._candidate, device=self._device
            )
        return self._qbyt

    def _load_recognizer(self) -> object:
        if self._recognizer is None:
            if self._sherpa_site_packages_path is not None:
                sys.path.append(str(self._sherpa_site_packages_path))
            import sherpa_onnx

            root = self._stt_directory
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=str(root / "encoder.int8.onnx"),
                decoder=str(root / "decoder.int8.onnx"),
                joiner=str(root / "joiner.int8.onnx"),
                tokens=str(root / "tokens.txt"),
                num_threads=6,
                model_type="nemo_transducer",
                decoding_method="modified_beam_search",
                max_active_paths=8,
                hotwords_score=5.0,
            )
        return self._recognizer

    def __call__(
        self,
        audio: np.ndarray,
        probabilities: np.ndarray,
        wake: object,
        record_index: int,
        start_sample: int,
    ) -> bool:
        key = (record_index, start_sample)
        explicit_allowed = _V7.explicit_confusable_guard(probabilities, wake)
        if not explicit_allowed:
            self.confusable_rejected_views += 1
            self.view_diagnostics[key] = {"explicitAllowed": False}
            return False
        qbyt_accepted, qbyt_score = self._load_qbyt().accepts(audio)
        self.view_diagnostics[key] = {
            "explicitAllowed": True,
            "qbytAccepted": qbyt_accepted,
            "qbytScore": qbyt_score,
        }
        if qbyt_accepted:
            self.qbyt_accepted_views += 1
            return True
        recognizer = self._load_recognizer()
        stream = recognizer.create_stream()
        stream.accept_waveform(16_000, audio)
        recognizer.decode_stream(stream)
        self.plain_decoded_views += 1
        plain = _V2._V4.has_contextual_wake_evidence(
            str(stream.result.text or "").strip(), wake
        )
        if plain:
            self.plain_accepted_views += 1
        self.view_diagnostics[key]["plainAccepted"] = plain
        return combine_secondary_evidence(
            explicit_sequence_allowed=True,
            qbyt_accepted=False,
            plain_accepted=plain,
        )


def evaluate(
    *,
    qbyt_candidate_path: Path,
    human_evidence_path: Path,
    teacher_directory: Path,
    stt_directory: Path,
    sherpa_site_packages_path: Path | None,
    device: str,
    output_path: Path,
    **arguments: object,
) -> dict[str, object]:
    if output_path.exists():
        raise ValueError("baxy_qbyt_dual_output_exists")
    candidate = _QBYT.load_candidate(qbyt_candidate_path, teacher_directory)
    human_path = human_evidence_path.resolve(strict=True)
    candidate_sha = _V2._PRODUCT.sha256(candidate["path"])
    validate_human_evidence(_V2._PRODUCT.read_object(human_path), candidate_sha)
    guard = QbyTOrPlainGuard(
        candidate=candidate,
        device=device,
        stt_directory=stt_directory,
        sherpa_site_packages_path=sherpa_site_packages_path,
    )
    contextual_qbyt_scores: list[float] = []

    def observe_contextual(
        proposal: dict[str, object], transcript: str, evidence: bool
    ) -> None:
        del transcript
        if not evidence:
            return
        key = (int(proposal["recordIndex"]), int(proposal["startSample"]))
        diagnostic = guard.view_diagnostics.get(key, {})
        score = diagnostic.get("qbytScore")
        if isinstance(score, (int, float)):
            contextual_qbyt_scores.append(float(score))
    report = _V2.evaluate(
        output_path=output_path,
        teacher_directory=teacher_directory,
        stt_directory=stt_directory,
        sherpa_site_packages_path=sherpa_site_packages_path,
        secondary_audio_guard=guard,
        secondary_guard_contract={
            "name": "exact_confusable_veto_then_qbyt_or_plain_same_view",
            "exactConfusableVeto": True,
            "qbytOrPlainDecode": True,
            "sameExactCpuFusionView": True,
            "selectedOnOpenedHumanDevelopment": True,
        },
        contextual_result_observer=observe_contextual,
        contextual_hotword_score=5.0,
        contextual_view_policy="same_exact_fusion_view",
        additional_checkpoint_identities={
            "qbytCandidateSha256": candidate_sha,
            "qbytHumanEvidenceSha256": _V2._PRODUCT.sha256(human_path),
            "qbytDualGuardVersion": "v1",
        },
        **arguments,
    )
    report["schema"] = "baxy.qbyt-dual-same-view-negative-regression.v10"
    report["measuredAtUtc"] = datetime.now(timezone.utc).isoformat()
    report["scope"] = "previously_opened_100h_qbyt_or_dual_same_view_regression"
    report["contract"].update(
        {
            "qbytCandidateSha256": candidate_sha,
            "humanEvidenceSha256": _V2._PRODUCT.sha256(human_path),
            "humanDevelopmentGatePassed": True,
            "selectedAfterOpened100hFailureAnalysis": True,
            "freshHoldoutClaimSupported": False,
        }
    )
    report["secondaryDiagnostics"] = {
        "confusableRejectedViews": guard.confusable_rejected_views,
        "qbytAcceptedViews": guard.qbyt_accepted_views,
        "plainDecodedViews": guard.plain_decoded_views,
        "plainAcceptedViews": guard.plain_accepted_views,
        "contextualEvidenceQbyTScores": contextual_qbyt_scores,
    }
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qbyt-candidate", type=Path, required=True)
    parser.add_argument("--human-evidence", type=Path, required=True)
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--cuda-batch-size", type=int, default=32)
    parser.add_argument("--record-batch-size", type=int, default=64)
    parser.add_argument("--stt-batch-size", type=int, default=8)
    parser.add_argument("--stage1-workers", type=int, default=16)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = evaluate(
        qbyt_candidate_path=arguments.qbyt_candidate,
        human_evidence_path=arguments.human_evidence,
        screening_cache_path=arguments.screening_cache,
        expected_sentinel_candidates=arguments.expected_sentinel_candidates,
        fusion_manifest_path=arguments.fusion_manifest,
        ctc_manifest_path=arguments.ctc_verifier_manifest,
        cuda_parity_report_path=arguments.cuda_parity_report,
        teacher_directory=arguments.teacher_directory,
        prior_holdout_report_path=arguments.prior_holdout_report,
        prior_stage1_scan_path=arguments.prior_stage1_scan,
        corpus_manifest_path=arguments.corpus_manifest,
        stage1_model_path=arguments.stage1_model,
        ffmpeg_path=arguments.ffmpeg,
        stt_directory=arguments.stt_directory,
        sherpa_site_packages_path=arguments.sherpa_site_packages,
        output_path=arguments.output,
        device=arguments.device,
        cuda_batch_size=arguments.cuda_batch_size,
        record_batch_size=arguments.record_batch_size,
        stt_batch_size=arguments.stt_batch_size,
        stage1_workers=arguments.stage1_workers,
    )
    print(json.dumps({"passed": report["regressionPassed"], "metrics": report["metrics"]}, sort_keys=True))
    return 0 if report["regressionPassed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
