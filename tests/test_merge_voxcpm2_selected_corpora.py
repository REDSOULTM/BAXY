from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "merge_voxcpm2_selected_corpora.py"
)
SPEC = importlib.util.spec_from_file_location("merge_voxcpm2_selected_corpora", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _source(root: Path, policy: str, payload: bytes) -> Path:
    root.mkdir()
    audio = root / "clip_000000.wav"
    audio.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    manifest = root / "manifest.v1.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": MODULE.SCHEMA,
                "class_label": "positive",
                "filter": {"positive_ipa_policy": policy},
                "records": [
                    {
                        "output_index": 0,
                        "output_file": audio.name,
                        "source_index": 0,
                        "persona_id": "speaker",
                        "seed": 1,
                        "phrase_id": policy,
                        "wav": {"sha256": digest},
                    }
                ],
                "blind_human_partition_accessed": False,
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_merge_preserves_bytes_and_per_record_policy(tmp_path: Path) -> None:
    isolated = _source(tmp_path / "isolated", "exact_target", b"isolated")
    context = _source(
        tmp_path / "context", "exact_target_subsequence", b"context"
    )

    result = MODULE.merge_corpora(
        [isolated, context], tmp_path / "merged"
    )

    assert result["counts"]["records"] == 2
    assert result["records"][0]["source_positive_ipa_policy"] == "exact_target"
    assert (
        result["records"][1]["source_positive_ipa_policy"]
        == "exact_target_subsequence"
    )
    assert (tmp_path / "merged" / "clip_000000.wav").read_bytes() == b"isolated"
    assert (tmp_path / "merged" / "clip_000001.wav").read_bytes() == b"context"
