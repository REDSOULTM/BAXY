"""Export the fixed BAXY HyperSpotter/CTC fusion as a CPU ONNX candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import time

import numpy as np


def load_component(filename: str, name: str) -> object:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"baxy_hyper_export_component_invalid:{filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_BASE = load_component(
    "train_baxy_hyperspotter_binary_v1.py", "_baxy_hyper_export_base_v1"
)
_EVALUATOR = load_component(
    "evaluate_baxy_hyperspotter_human_development_v1.py",
    "_baxy_hyper_export_evaluator_v1",
)


def policy_from_report(report: dict[str, object]) -> dict[str, float | str]:
    selection = report.get("policy_selection")
    legacy = report.get("legacy_selection_metrics")
    expanded = report.get("expanded_independent_metrics")
    fusion = report.get("fixed_policy_ctc_fusion")
    if (
        report.get("schema")
        != "baxy.baxy-hyperspotter-ctc-continuous-development.v4"
        or report.get("blind_human_audio_accessed") is not False
        or not isinstance(selection, dict)
        or not isinstance(selection.get("selected"), dict)
        or not isinstance(legacy, dict)
        or not isinstance(expanded, dict)
        or not isinstance(fusion, dict)
        or legacy.get("fixed_positive_hits") != 14
        or legacy.get("fixed_false_hits") != 0
        or expanded.get("fixed_positive_hits") != 4
        or expanded.get("fixed_false_hits") != 0
        or fusion.get("fused_positive_hits") != 18
        or fusion.get("fused_false_hits") != 0
    ):
        raise ValueError("baxy_hyper_export_policy_evidence_invalid")
    selected = selection["selected"]
    if selected.get("feature") != "full_clip_margin":
        raise ValueError("baxy_hyper_export_policy_feature_invalid")
    return {
        "ctc_feature": "full_clip_margin",
        "ctc_center": float(selected["feature_center"]),
        "ctc_scale": float(selected["feature_scale"]),
        "ctc_weight": float(selected["beta"]),
        "decision_threshold": float(selected["threshold"]),
    }


def numpy_log_mel_spectrogram(audio: np.ndarray, mel_filters: np.ndarray) -> np.ndarray:
    values = np.asarray(audio, dtype=np.float32).reshape(-1)
    filters = np.asarray(mel_filters, dtype=np.float32)
    if values.shape != (48_000,) or filters.shape != (80, 201):
        raise ValueError("baxy_hyper_export_logmel_shape_invalid")
    padded = np.pad(values, (200, 200), mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(padded, 400)[::160]
    window = np.hanning(401)[:-1].astype(np.float32)
    stft = np.fft.rfft(frames * window[None, :], n=400, axis=1)
    magnitudes = (np.abs(stft) ** 2).astype(np.float32).T[:, :-1]
    mel = filters @ magnitudes
    log_spec = np.log10(np.maximum(mel, np.float32(1e-10)))
    log_spec = np.maximum(log_spec, np.max(log_spec) - np.float32(8.0))
    result = ((log_spec + np.float32(4.0)) / np.float32(4.0)).T.astype(
        np.float32
    )
    if result.shape != (300, 80) or not np.isfinite(result).all():
        raise ValueError("baxy_hyper_export_logmel_invalid")
    return result


def export(
    *,
    hyperspotter_root: Path,
    hyperspotter_site_packages: Path,
    official_checkpoint_path: Path,
    candidate_checkpoint_path: Path,
    policy_report_path: Path,
    mel_filter_archive_path: Path,
    ctc_verifier_manifest_path: Path,
    output_directory: Path,
) -> dict[str, object]:
    inputs = [
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
        policy_report_path,
        mel_filter_archive_path,
        ctc_verifier_manifest_path,
    ]
    (
        hyperspotter_root,
        hyperspotter_site_packages,
        official_checkpoint_path,
        candidate_checkpoint_path,
        policy_report_path,
        mel_filter_archive_path,
        ctc_verifier_manifest_path,
    ) = [path.resolve(strict=True) for path in inputs]
    output_directory = output_directory.resolve()
    partial = output_directory.with_name(output_directory.name + ".partial")
    if output_directory.exists() or partial.exists():
        raise FileExistsError("baxy_hyper_export_output_exists")
    policy_report = _BASE._LOGMEL.read_object(policy_report_path)
    policy = policy_from_report(policy_report)
    ctc_manifest = _BASE._LOGMEL.read_object(ctc_verifier_manifest_path)
    if ctc_manifest.get("schema") != "baxy-wake-verifier-v1":
        raise ValueError("baxy_hyper_export_ctc_manifest_invalid")

    model, tokenizer, torch, _device, checkpoint = _EVALUATOR.load_candidate(
        hyperspotter_root=hyperspotter_root,
        hyperspotter_site_packages=hyperspotter_site_packages,
        official_checkpoint_path=official_checkpoint_path,
        candidate_checkpoint_path=candidate_checkpoint_path,
        device="cpu",
    )
    import torch.nn as nn

    aliases = list(checkpoint["aliases"])
    keyword_ids = tokenizer(aliases)["input_ids"]
    keyword_lengths = torch.tensor([len(value) for value in keyword_ids], dtype=torch.long)
    keyword_values = nn.utils.rnn.pad_sequence(
        [torch.tensor(value, dtype=torch.long) for value in keyword_ids],
        padding_value=tokenizer.pad_token_id,
        batch_first=True,
    )
    with torch.no_grad():
        alias_weights = model.get_text_weights(keyword_values, keyword_lengths).detach().clone()

    class StaticAliasModel(nn.Module):
        def __init__(self, source: object, weights: object) -> None:
            super().__init__()
            self.audio_encoder = source.audio_encoder
            self.classifier = source.perceiver_classifier
            self.register_buffer("alias_weights", weights)

        def forward(self, logmel: object) -> object:
            lengths = torch.full((1,), 300, dtype=torch.long, device=logmel.device)
            encoded, _ = self.audio_encoder(logmel.transpose(1, 2), lengths)
            encoded = encoded[:, :74, :]
            mask = torch.ones((1, 74), dtype=torch.bool, device=logmel.device)
            outputs = [
                self.classifier(
                    encoded,
                    self.alias_weights[index : index + 1],
                    mask=mask,
                )
                for index in range(len(aliases))
            ]
            return torch.cat(outputs, dim=1)

    wrapper = StaticAliasModel(model, alias_weights).eval()
    example = torch.zeros((1, 300, 80), dtype=torch.float32)
    with torch.no_grad():
        expected = wrapper(example).numpy()
    partial.mkdir(parents=True)
    graph_path = partial / "baxy-hyperspotter-fixed3s.onnx"
    started = time.perf_counter()
    torch.onnx.export(
        wrapper,
        (example,),
        str(graph_path),
        input_names=["logmel"],
        output_names=["logits"],
        opset_version=18,
        dynamo=False,
        do_constant_folding=True,
    )
    export_seconds = time.perf_counter() - started
    with np.load(mel_filter_archive_path, allow_pickle=False) as archive:
        mel_filters = np.asarray(archive["mel_80"], dtype=np.float32)
    if mel_filters.shape != (80, 201):
        raise ValueError("baxy_hyper_export_mel_filters_invalid")
    mel_path = partial / "mel_80.npy"
    np.save(mel_path, mel_filters, allow_pickle=False)

    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        str(graph_path), sess_options=options, providers=["CPUExecutionProvider"]
    )
    actual = session.run(["logits"], {"logmel": example.numpy()})[0]
    maximum_export_error = float(np.max(np.abs(actual - expected)))
    if maximum_export_error > 1e-4:
        raise ValueError("baxy_hyper_export_onnx_parity_invalid")
    manifest: dict[str, object] = {
        "schema": "baxy-hyperspotter-fusion-v1",
        "measuredAtUtc": datetime.now(timezone.utc).isoformat(),
        "backend": "onnxruntime-hyperspotter-fixed-aliases-plus-phoneme-ctc",
        "graph": graph_path.name,
        "graphSha256": _BASE._LOGMEL.sha256(graph_path),
        "graphBytes": graph_path.stat().st_size,
        "melFilters": mel_path.name,
        "melFiltersSha256": _BASE._LOGMEL.sha256(mel_path),
        "melFiltersShape": [80, 201],
        "aliases": aliases,
        "sampleRate": 16_000,
        "audioSamples": 48_000,
        "logmelFrames": 300,
        "logmelBins": 80,
        "policy": policy,
        "ctcVerifierManifestSha256": _BASE._LOGMEL.sha256(
            ctc_verifier_manifest_path
        ),
        "sources": {
            "officialCheckpointSha256": _BASE._LOGMEL.sha256(
                official_checkpoint_path
            ),
            "candidateCheckpointSha256": _BASE._LOGMEL.sha256(
                candidate_checkpoint_path
            ),
            "policyReportSha256": _BASE._LOGMEL.sha256(policy_report_path),
            "melFilterArchiveSha256": _BASE._LOGMEL.sha256(
                mel_filter_archive_path
            ),
        },
        "export": {
            "opset": 18,
            "seconds": export_seconds,
            "maximumZeroInputLogitError": maximum_export_error,
            "fixedBatch": 1,
            "fixedAudioDurationSeconds": 3.0,
        },
        "approved": False,
        "developmentOnly": True,
        "blindHumanAudioAccessed": False,
        "effectsExecuted": 0,
    }
    manifest_path = partial / "baxy-hyperspotter-fusion-v1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    bundle = {
        "schema": "baxy.hyperspotter-fusion-candidate-bundle.v1",
        "manifest": manifest_path.name,
        "manifestSha256": _BASE._LOGMEL.sha256(manifest_path),
        "files": [graph_path.name, mel_path.name],
        "approved": False,
        "effectsExecuted": 0,
    }
    (partial / "candidate.bundle.v1.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.rename(output_directory)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyperspotter-root", type=Path, required=True)
    parser.add_argument("--hyperspotter-site-packages", type=Path, required=True)
    parser.add_argument("--official-checkpoint", type=Path, required=True)
    parser.add_argument("--candidate-checkpoint", type=Path, required=True)
    parser.add_argument("--policy-report", type=Path, required=True)
    parser.add_argument("--mel-filter-archive", type=Path, required=True)
    parser.add_argument("--ctc-verifier-manifest", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    manifest = export(
        hyperspotter_root=arguments.hyperspotter_root,
        hyperspotter_site_packages=arguments.hyperspotter_site_packages,
        official_checkpoint_path=arguments.official_checkpoint,
        candidate_checkpoint_path=arguments.candidate_checkpoint,
        policy_report_path=arguments.policy_report,
        mel_filter_archive_path=arguments.mel_filter_archive,
        ctc_verifier_manifest_path=arguments.ctc_verifier_manifest,
        output_directory=arguments.output_directory,
    )
    print(
        json.dumps(
            {
                "graphBytes": manifest["graphBytes"],
                "graphSha256": manifest["graphSha256"],
                "policy": manifest["policy"],
                "export": manifest["export"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
