from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_endpoint_voice_runtime_v1.py"
)
SPEC = importlib.util.spec_from_file_location("evaluate_endpoint_voice_runtime", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_runtime_probe_requires_all_external_assets() -> None:
    parser = MODULE._parser()
    required = {
        action.dest for action in parser._actions if getattr(action, "required", False)
    }

    assert required == {"cascade_manifest", "stt_directory", "corpus", "output"}
    assert MODULE.SCHEMA == "baxy.endpoint-voice-runtime-development.v1"
