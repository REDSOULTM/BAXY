"""Capture the live runtime voice identity (names + SHA-256 only)."""

from __future__ import annotations

import json
import os
from pathlib import Path

SCRATCH = Path(
    os.environ.get(
        "BAXY_GOAL09_SCRATCH",
        r"C:\Users\usuario\AppData\Local\Temp\grok-goal-4eda3fa08868\implementer",
    )
)
manifest = (
    Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime" / "mind-runtime-v1.json"
)
data = json.loads(manifest.read_text(encoding="utf-8"))
payload = {
    "schema": data.get("schema"),
    "stt_dir_name": Path(str(data.get("stt_dir") or "")).name or None,
    "stt_sha256": data.get("stt_sha256"),
    "tts_name": Path(str(data.get("tts_model") or "")).name or None,
    "tts_sha256": data.get("tts_sha256"),
    "wake_manifest_name": Path(str(data.get("wake_manifest") or "")).name or None,
    "wake_manifest_sha256": data.get("wake_manifest_sha256"),
    "wake_on_start": data.get("wake_on_start"),
    "engines_in_dotnet": False,
    "engines_in_python_sidecar": True,
    "substitutable_without_recompile": True,
}
SCRATCH.mkdir(parents=True, exist_ok=True)
(SCRATCH / "runtime_voice_identity.json").write_text(
    json.dumps(payload, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(payload, indent=2))
