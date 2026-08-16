from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "build_openslr_librispeech_manifest.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_openslr_librispeech_manifest", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_read_transcripts_collects_all_chapters(tmp_path: Path) -> None:
    chapter = tmp_path / "1" / "2"
    chapter.mkdir(parents=True)
    (chapter / "1-2.trans.txt").write_text(
        "1-2-3 HELLO WORLD\n1-2-4 BACK SEAT\n", encoding="utf-8"
    )

    assert MODULE.read_transcripts(tmp_path) == {
        "1-2-3": "HELLO WORLD",
        "1-2-4": "BACK SEAT",
    }


def test_read_transcripts_rejects_duplicate_utterance(tmp_path: Path) -> None:
    for directory in (tmp_path / "a", tmp_path / "b"):
        directory.mkdir()
        (directory / "part.trans.txt").write_text(
            "1-2-3 TEXT\n", encoding="utf-8"
        )

    with pytest.raises(ValueError, match="librispeech_duplicate_utterance"):
        MODULE.read_transcripts(tmp_path)


def test_product_negative_holdout_profile_is_official_and_not_development() -> None:
    profile = MODULE.SUBSETS["train-clean-100"]

    assert profile["md5"] == "2a93770f6d5c6c964bc36631d331a522"
    assert profile["sha256"] == (
        "d4ddd1d5a6ab303066f14971d768ee43278a5f2a0aa43dc716b0e64ecbbbf6e2"
    )
    assert profile["candidate_development_use"] is False
    assert profile["schema"] == (
        "baxy.openslr-librispeech-negative-holdout.v1"
    )
