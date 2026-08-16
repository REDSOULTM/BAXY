from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "preregister_mswc_spanish_qbye_fresh_gate_v2.py"
)
SPEC = importlib.util.spec_from_file_location(
    "preregister_mswc_spanish_qbye_fresh_gate_v2", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sha256_is_stable(tmp_path: Path) -> None:
    value = tmp_path / "value.bin"
    value.write_bytes(b"baxy-fresh-gate")
    assert (
        MODULE.sha256(value)
        == "aa5cd2ea84856f4428344f3b060b6921434ee51fff4772f10d644de7fc7c910d"
    )
