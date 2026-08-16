from __future__ import annotations

import importlib.util
from pathlib import Path
import sys



def _module():
    script = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "voice_latency"
        / "evaluate_baxy_wake_cascade_openslr_exact_parallel_v2.py"
    )
    spec = importlib.util.spec_from_file_location(
        "baxy_wake_cascade_openslr_exact_parallel", script
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parallel_checkpoint_round_trips(tmp_path: Path) -> None:
    gate = _module()
    path = tmp_path / "parallel.json"
    identities = {"screenCheckpointSha256": "a" * 64, "workers": "8"}
    gate._write_checkpoint(
        path,
        identities=identities,
        completed_records=128,
        exact_proposals=103,
        strong_false=[],
        elapsed_seconds=12.5,
    )
    assert gate._load_checkpoint(path, identities) == (128, 103, [], 12.5)
