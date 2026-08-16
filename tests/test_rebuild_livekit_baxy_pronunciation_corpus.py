from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import wave


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "rebuild_livekit_baxy_pronunciation_corpus.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_pronunciation_rebuild", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_wav(path: Path, marker: int) -> None:
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(marker.to_bytes(2, "little", signed=True) * 160)


def test_rebuild_keeps_only_odd_indices_and_archives_everything(tmp_path: Path) -> None:
    split = tmp_path / "positive_train"
    split.mkdir()
    for index in range(6):
        _write_wav(split / f"clip_{index:06d}.wav", index + 1)

    result = MODULE.rebuild_split(split, "positive_train_before_fix")

    assert result["source_count"] == 6
    assert result["accepted_count"] == 3
    assert result["rejected_count"] == 3
    archive = tmp_path / "positive_train_before_fix"
    assert len(list(archive.glob("*.wav"))) == 6
    assert [path.name for path in sorted(split.glob("*.wav"))] == [
        "clip_000000.wav",
        "clip_000001.wav",
        "clip_000002.wav",
    ]
    for dense, old_index in enumerate((1, 3, 5)):
        assert os.stat(split / f"clip_{dense:06d}.wav").st_ino == os.stat(
            archive / f"clip_{old_index:06d}.wav"
        ).st_ino


def test_rebuild_rejects_non_dense_source(tmp_path: Path) -> None:
    split = tmp_path / "positive_train"
    split.mkdir()
    _write_wav(split / "clip_000001.wav", 1)

    try:
        MODULE.rebuild_split(split, "archive")
    except ValueError as error:
        assert str(error) == "source_split_is_not_dense"
    else:
        raise AssertionError("non-dense split was accepted")
