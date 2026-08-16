from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import struct
import wave

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = (
    ROOT
    / "experiments"
    / "wake_validation"
    / "evaluate_hyperspotter_open_vocabulary_wake_pilot_v1.py"
)
SPEC = importlib.util.spec_from_file_location("hyperspotter_pilot", PROGRAM)
assert SPEC is not None and SPEC.loader is not None
PILOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PILOT)


def test_source_tree_hash_ignores_python_cache(tmp_path: Path) -> None:
    (tmp_path / "model.py").write_text("answer = 42\n", encoding="utf-8")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "model.pyc").write_bytes(b"ignored")

    relative = b"model.py"
    file_hash = hashlib.sha256((tmp_path / "model.py").read_bytes()).digest()
    expected = hashlib.sha256(relative + b"\0" + file_hash).hexdigest()

    assert PILOT.source_tree_sha256(tmp_path) == expected


def test_safe_corpus_path_rejects_escape_and_non_wav(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "clip.txt").write_text("no", encoding="utf-8")

    with pytest.raises(ValueError, match="path_escape"):
        PILOT._safe_corpus_path(corpus, "../outside.wav")
    with pytest.raises(ValueError, match="wav_missing"):
        PILOT._safe_corpus_path(corpus, "clip.txt")


def test_manifest_records_validate_labels_counts_and_hashes(tmp_path: Path) -> None:
    positive = tmp_path / "positive"
    negative = tmp_path / "negative"
    positive.mkdir()
    negative.mkdir()
    positive_wav = positive / "a.wav"
    negative_wav = negative / "b.wav"
    positive_wav.write_bytes(b"positive")
    negative_wav.write_bytes(b"negative")
    manifest = {
        "counts": {"positive": 1, "negative": 1},
        "records": [
            {
                "recordId": "positive/000000",
                "output": "positive/a.wav",
                "outputSha256": hashlib.sha256(b"positive").hexdigest(),
            },
            {
                "recordId": "negative/000000",
                "output": "negative/b.wav",
                "outputSha256": hashlib.sha256(b"negative").hexdigest(),
            },
        ],
    }

    grouped = PILOT._manifest_records(
        tmp_path,
        manifest,
        expected_positive=1,
        expected_negative=1,
    )

    assert (
        grouped["positive"][0]["audioSha256"] == hashlib.sha256(b"positive").hexdigest()
    )
    assert (
        grouped["negative"][0]["audioSha256"] == hashlib.sha256(b"negative").hexdigest()
    )


def test_summary_uses_strict_threshold_and_interpolated_percentiles() -> None:
    records = [
        {"probability": 0.1, "runtimeSeconds": 1.0},
        {"probability": 0.5, "runtimeSeconds": 2.0},
        {"probability": 0.9, "runtimeSeconds": 3.0},
    ]

    summary = PILOT.summarize_records(records, 0.5)

    assert summary["acceptedFiles"] == 1
    assert summary["probability"]["p50"] == 0.5
    assert summary["runtimeSeconds"]["p95"] == pytest.approx(2.9)


def test_physical_v17_is_forbidden() -> None:
    with pytest.raises(ValueError, match="physical_v17_forbidden"):
        PILOT._forbid_v17([Path("D:/sealed/physical_v17")])


def test_pcm16_reader_decodes_stereo_to_mono(tmp_path: Path) -> None:
    wav_path = tmp_path / "stereo.wav"
    with wave.open(str(wav_path), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(struct.pack("<hhhh", 32767, -32768, 16384, 16384))

    waveform, sample_rate = PILOT._read_pcm16_wave(wav_path)

    assert sample_rate == 16_000
    assert tuple(waveform.shape) == (1, 2)
    assert waveform[0, 0].item() == pytest.approx(-0.5 / 32768.0)
    assert waveform[0, 1].item() == pytest.approx(0.5)


def test_whisper_encoder_dimensions_cover_published_checkpoint_variants() -> None:
    assert PILOT.whisper_encoder_dimensions("tiny") == (80, 1500, 384, 6, 4)
    assert PILOT.whisper_encoder_dimensions("base") == (80, 1500, 512, 8, 6)
    with pytest.raises(ValueError, match="unexpected_whisper_base"):
        PILOT.whisper_encoder_dimensions("small")
