"""R281: make the active runtime auditable from the tree.

The runtime manifest lives in ``%LOCALAPPDATA%\\BAXYRuntime`` and is not
versioned, so until now nothing in the repository recorded which model a sealed
measurement actually used. R280 showed the cost: the meta document still claimed
Qwen3-4B while the machine ran Gemma-4, and a Qwen3-era mechanism was carried
into a Gemma-4 measurement.

This program reads the registered manifest and writes a versioned expectation
recording the identity of the model, server and interpreter in play. A test then
compares the local manifest against that expectation, so any model swap turns a
gate red instead of passing unnoticed.

It starts no model, enables no provider and executes no effect. It never writes
the manifest: the repository follows the machine, not the other way round.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = "baxy.registered-runtime-expectation.r281.v1"
RESULT_PATH = "artifacts/runtime/registered_runtime_expectation_r281.json"
NATIVE_TOOL_POLICY_TOKEN = "qwen3"


def registered_manifest_path() -> Path:
    return (
        Path(os.environ.get("LOCALAPPDATA", Path.cwd()))
        / "BAXYRuntime"
        / "mind-runtime-v1.json"
    )


def read_manifest(path: Path | None = None) -> dict[str, Any] | None:
    path = path or registered_manifest_path()
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def describe(manifest: dict[str, Any]) -> dict[str, Any]:
    """Identity only: names and hashes, never absolute machine paths."""

    gguf_name = Path(manifest["gguf"]).name if manifest.get("gguf") else None
    return {
        "ggufName": gguf_name,
        "ggufSha256": manifest.get("gguf_sha256"),
        "llamaServerName": (
            Path(manifest["llama_server"]).name
            if manifest.get("llama_server")
            else None
        ),
        "llamaServerSha256": manifest.get("llama_server_sha256"),
        "pythonSha256": manifest.get("python_sha256"),
        "gpuLayers": manifest.get("ngl"),
        "wakeOnStart": manifest.get("wake_on_start"),
        "nativeToolPolicyEnabled": bool(
            gguf_name and NATIVE_TOOL_POLICY_TOKEN in gguf_name.casefold()
        ),
    }


def build(manifest_path: Path | None = None) -> dict[str, Any]:
    manifest = read_manifest(manifest_path)
    return {
        "schema": SCHEMA,
        "authority": "versioned_expectation_of_the_local_runtime_not_a_promotion",
        "manifestIsVersioned": False,
        "manifestPresent": manifest is not None,
        "expected": describe(manifest) if manifest else None,
        "whyThisExists": (
            "R280 found the meta document claiming Qwen3-4B while the machine ran "
            "Gemma-4, and the decision path differs between them. Recording the identity "
            "here turns a silent model swap into a red gate."
        ),
        "constraints": {
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "overall_goal_met": False,
        "section_7_met": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="R281 registered runtime attestation")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()

    root = Path(arguments.repository_root).resolve()
    result = build()
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if arguments.write:
        destination = root / RESULT_PATH
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(rendered.encode("utf-8"))
        print(f"wrote {RESULT_PATH}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
