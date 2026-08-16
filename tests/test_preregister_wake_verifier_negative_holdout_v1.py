from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "experiments" / "voice_latency" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ASSEMBLER = _load("assemble_wake_verifier_candidate_v1")
PREREGISTER = _load("preregister_wake_verifier_negative_holdout_v1")


def test_preregistration_freezes_assets_sources_and_statistical_gate(
    tmp_path: Path,
) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    stage1 = assets / "stage1.onnx"
    graph = assets / "verifier.onnx"
    data = assets / "verifier.onnx.data"
    vocabulary = assets / "vocab.json"
    stage1.write_bytes(b"stage1")
    graph.write_bytes(b"graph")
    data.write_bytes(b"data")
    vocabulary.write_text("{}", encoding="utf-8")
    candidate = tmp_path / "candidate"
    ASSEMBLER.assemble(
        stage1_model=stage1,
        verifier_graph=graph,
        vocabulary=vocabulary,
        output_directory=candidate,
    )
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "schema": "baxy.openslr-librispeech-negative-holdout.v1",
                "metrics": {"audio_hours": 100.0},
                "candidate_scored": False,
            }
        ),
        encoding="utf-8",
    )
    source = tmp_path / "source"
    paths = (
        "src/baxy_mind/wakeword.py",
        "src/baxy_mind/wake_verifier.py",
        "src/baxy_mind/voice.py",
        "experiments/voice_latency/scan_openslr_librispeech_livekit_development.py",
        "experiments/voice_latency/evaluate_wake_verifier_negative_holdout_v1.py",
        "experiments/voice_latency/evaluate_wake_verifier_product_capture_development_v1.py",
        "experiments/voice_latency/build_livekit_mel_overlap_models_v1.py",
    )
    for relative in paths:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    stt = tmp_path / "stt"
    stt.mkdir()
    for name in PREREGISTER.STT_FILES:
        (stt / name).write_bytes(name.encode())
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"ffmpeg")
    verifier_manifest = candidate / "baxy-wake-verifier-v1.json"
    verifier_manifest_sha256 = PREREGISTER.sha256(verifier_manifest)
    wake_manifest = json.loads(
        (candidate / "baxy-wakeword-v1.json").read_text(encoding="utf-8")
    )
    positive_development = tmp_path / "positive-development.json"
    positive_development.write_text(
        json.dumps(
            {
                "schema": "baxy.wake-verifier-product-capture-development.v1",
                "sources": {
                    "stage1_model_sha256": wake_manifest["sha256"],
                    "verifier_manifest_sha256": verifier_manifest_sha256,
                },
                "contract": {
                    "first_causal_broad_hit": True,
                    "stt_decode_schedule": "single_stream_product_equivalent",
                    "stage1_hop_samples": 2_560,
                    "audio_frame_samples": 512,
                    "pre_roll_seconds": 5.0,
                    "pre_roll_samples": 79_872,
                    "trailing_silence_samples": 10_752,
                    "verification_samples": 48_000,
                    "primary_view_start_samples": 64_000,
                    "activity_lookback_samples": 2_560,
                    "activity_alignment_samples": 320,
                    "activity_vad_threshold": 0.1,
                    "maximum_turn_samples": 480_000,
                },
                "metrics": {
                    "gate_passed": True,
                    "positive_accepted": 14,
                    "positive_total": 14,
                    "hard_negative_false_accepts": 0,
                },
                "candidate_frozen": False,
                "product_operating_point": True,
                "blind_human_partition_accessed": False,
                "effects_executed": 0,
            }
        ),
        encoding="utf-8",
    )
    negative_development = tmp_path / "negative-development.json"
    overlap_directory = tmp_path / "overlap"
    overlap_directory.mkdir()
    overlap_raw = overlap_directory / "raw.onnx"
    overlap_post = overlap_directory / "post.onnx"
    overlap_raw.write_bytes(b"raw")
    overlap_post.write_bytes(b"post")
    mel_overlap_report = overlap_directory / "report.json"
    mel_overlap_report.write_text(
        json.dumps(
            {
                "schema": "baxy.livekit-mel-overlap-models.v1",
                "assets": {
                    "raw": overlap_raw.name,
                    "raw_sha256": PREREGISTER.sha256(overlap_raw),
                    "post": overlap_post.name,
                    "post_sha256": PREREGISTER.sha256(overlap_post),
                },
                "contract": {
                    "exact_decisions_remain_owned_by_original_runtime": True,
                    "audio_frame_samples": 512,
                    "stage1_hop_samples": 2_560,
                },
                "equivalence": {
                    "bitwise_equal": True,
                    "maximum_absolute_difference": 0.0,
                },
                "candidate_frozen": False,
                "product_runtime_asset": False,
                "blind_human_partition_accessed": False,
                "effects_executed": 0,
            }
        ),
        encoding="utf-8",
    )
    negative_scan = tmp_path / "negative-scan.json"
    negative_scan.write_text(
        json.dumps(
            {
                "schema": (
                    "baxy.openslr-librispeech-livekit-development-scan.v1"
                ),
                "model_sha256": wake_manifest["sha256"],
                "retention_threshold": 0.0175,
                "proposal_threshold": 0.035,
                "hop_samples": 2_560,
                "audio_frame_samples": 512,
                "product_runtime_equivalent_schedule": True,
                "runtime": {
                    "mel_overlap_raw_sha256": PREREGISTER.sha256(overlap_raw),
                    "mel_overlap_post_sha256": PREREGISTER.sha256(overlap_post),
                },
                "candidate_development_use": True,
            }
        ),
        encoding="utf-8",
    )
    negative_development.write_text(
        json.dumps(
            {
                "schema": "baxy.wake-verifier-negative-development.v1",
                "stage1_scan": str(negative_scan),
                "stage1_scan_sha256": PREREGISTER.sha256(negative_scan),
                "verifier_manifest_sha256": verifier_manifest_sha256,
                "metrics": {"negative_false_activations": 0},
                "runtime": {
                    "stt_decode_schedule": "single_stream_product_equivalent",
                    "strong_stage1_transcript_elision": False,
                },
                "development_gate_passed": True,
                "candidate_development_use": True,
                "candidate_frozen": False,
                "product_operating_point": False,
                "blind_human_partition_accessed": False,
                "effects_executed": 0,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "preregistration.json"

    report = PREREGISTER.preregister(
        candidate_directory=candidate,
        negative_corpus_manifest=corpus,
        positive_development_report=positive_development,
        negative_development_report=negative_development,
        mel_overlap_report=mel_overlap_report,
        stt_directory=stt,
        ffmpeg_path=ffmpeg,
        source_root=source,
        output_path=output,
    )

    assert report["candidate_frozen"] is True
    assert report["negative_holdout_scored"] is False
    assert report["negative_exposure_hours"] == 100.0
    assert report["gate"]["minimum_exposure_hours"] > 29.9
    assert len(report["evaluation_script_sha256"]) == 64
    assert report["primary_view_start_samples"] == 64_000
    assert report["activity_vad_threshold"] == 0.1
    assert report["stage1_pre_roll_samples"] == 79_872
    assert report["trailing_silence_samples"] == 10_752
    assert report["mel_overlap_raw_sha256"] == PREREGISTER.sha256(overlap_raw)
