from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "voice_latency"))
from evaluate_openslr_anchor_qbt_development import select_broad_records  # noqa: E402


def test_select_broad_records_uses_raw_score_not_old_proposal_flag() -> None:
    corpus = [
        {"utterance_id": "a", "relative_path": "a.flac", "sha256": "x"},
        {"utterance_id": "b", "relative_path": "b.flac", "sha256": "y"},
    ]
    scan = [
        {
            "utterance_id": "a",
            "relative_path": "a.flac",
            "wav_sha256": "x",
            "max_score": 0.021,
            "proposal": False,
        },
        {
            "utterance_id": "b",
            "relative_path": "b.flac",
            "wav_sha256": "y",
            "max_score": 0.019,
            "proposal": True,
        },
    ]
    selected = select_broad_records(corpus, scan, 0.02)
    assert [item[0]["utterance_id"] for item in selected] == ["a"]


def test_select_broad_records_rejects_identity_mismatch() -> None:
    with pytest.raises(ValueError, match="identity_mismatch"):
        select_broad_records(
            [{"utterance_id": "a", "relative_path": "a.flac", "sha256": "x"}],
            [
                {
                    "utterance_id": "a",
                    "relative_path": "other.flac",
                    "wav_sha256": "x",
                    "max_score": 0.5,
                }
            ],
            0.02,
        )
