from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
SCRIPT = SCRIPTS / "measure_turn_policy_v52_mtop_validation.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "measure_turn_policy_v52_mtop_validation",
    SCRIPT,
)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


def test_input_snapshot_detects_same_size_replacement(
    tmp_path: Path,
) -> None:
    corpus_path = tmp_path / "development.jsonl"
    manifest_path = tmp_path / "manifest.json"
    corpus_path.write_bytes(b'{"version":"a"}\n')
    manifest_path.write_bytes(b'{"version":"a"}\n')
    _, corpus = runner._capture_file(corpus_path)
    _, manifest = runner._capture_file(manifest_path)
    identity = runner.DevelopmentInputIdentity(
        corpus=corpus,
        manifest=manifest,
    )

    runner._assert_input_identity_stable(identity)
    corpus_path.write_bytes(b'{"version":"b"}\n')

    with pytest.raises(
        RuntimeError,
        match="MTOP corpus changed during measurement",
    ):
        runner._assert_input_identity_stable(identity)


def test_missing_information_projection_opens_candidate_path() -> None:
    row = {
        "projection": {
            "disposition": "candidate_missing_information",
            "candidate_operations": ["media.seek.relative"],
            "reason": "contract_supported_missing_information",
        }
    }

    assert runner._class_label(row) == "candidate"
    assert runner._single_operation(row) == "media.seek.relative"


def test_current_snapshot_rejects_prior_embedding_cache() -> None:
    expected = runner._embedding_cache_identity(
        runner.EXPECTED_CORPUS_SHA256,
        29_976,
    )

    assert expected["corpus_sha256"] == (
        "ed1871262bdb78a53e219ac6ebd7b995879c60eba29ec5d9203217480a142802"
    )
    assert expected["corpus_sha256"] != (
        "e606fa9c3ea6b4f1dd5632ef77c43e918c8a375f74cabfd78374c7db157c196c"
    )
