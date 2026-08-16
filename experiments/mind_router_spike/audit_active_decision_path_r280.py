"""R280: which decision path does the registered runtime actually exercise?

R277 located ``tool_choice: "required"`` in ``_post_native_tool_selection`` and
priced its consequence over V8. That pricing stands, because V8 ran on Qwen3-4B.
It does **not** transfer to the runtime registered today.

``_native_tool_policy_enabled`` is switched on only when the GGUF filename
contains ``qwen3``. The registered manifest points at a Gemma-4 model, so the
forced-tool-choice path is never reached and ``tool_choice`` is never sent. Any
claim that the forced contract explains a Gemma-4 measurement is wrong.

This program reads the registered manifest and the runtime source. It starts no
model, enables no provider and executes no effect.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Any

SCHEMA = "baxy.active-decision-path.r280.v1"
LLM_SOURCE = "src/baxy_mind/llm.py"
RESULT_PATH = "artifacts/audit/active_decision_path_r280.json"
GATE_TOKEN = "qwen3"


def registered_manifest() -> Path:
    return (
        Path(os.environ.get("LOCALAPPDATA", Path.cwd()))
        / "BAXYRuntime"
        / "mind-runtime-v1.json"
    )


def _gate_token_from_source(root: Path) -> str | None:
    """Read the literal the runtime tests the GGUF filename against."""

    module = ast.parse((root / LLM_SOURCE).read_text(encoding="utf-8"))
    for node in ast.walk(module):
        if not isinstance(node, ast.Compare):
            continue
        rendered = ast.unparse(node)
        if "casefold()" not in rendered or "gguf" not in rendered.casefold():
            continue
        left = node.left
        if isinstance(left, ast.Constant) and isinstance(left.value, str):
            return left.value
    return None


def build(root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    manifest_path = manifest_path or registered_manifest()
    manifest_present = manifest_path.is_file()
    gguf_name: str | None = None
    if manifest_present:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        gguf = manifest.get("gguf")
        gguf_name = Path(gguf).name if gguf else None

    token = _gate_token_from_source(root) or GATE_TOKEN
    native_enabled = bool(gguf_name and token in gguf_name.casefold())

    return {
        "schema": SCHEMA,
        "authority": "read_only_runtime_path_attribution_not_a_promotion",
        "verdict": (
            "forced_tool_choice_path_active"
            if native_enabled
            else "forced_tool_choice_path_not_reached_by_the_registered_model"
        ),
        "registeredRuntime": {
            "manifestPresent": manifest_present,
            "ggufName": gguf_name,
            "manifestIsVersioned": False,
        },
        "gate": {
            "source": f"{LLM_SOURCE}:_native_tool_policy_enabled",
            "filenameTokenRequired": token,
            "nativeToolPolicyEnabled": native_enabled,
            "toolChoiceSentByRegisteredRuntime": native_enabled,
        },
        "correctsR277": {
            "v8PricingStillValid": True,
            "v8Model": "active_qwen3_4b_instruct_awq_q4_k_m",
            "v8ModelSha256": (
                "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
            ),
            "r276Model": "gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf",
            "r276UnsolicitedEffectsExplainedByForcedToolChoice": False,
            "reason": (
                "V8 ran on Qwen3-4B, where the gate is on, so R277's V8 counts hold. "
                "R276 ran on Gemma-4, where the gate is off, so its 24 unsolicited "
                "effects cannot be attributed to the forced contract."
            ),
        },
        "constraints": {
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "next_requirement": (
            "The tool_choice A/B proposed by R277 does not apply to the registered "
            "runtime while a Gemma-4 model is active. Either measure the JSON decision "
            "path that Gemma-4 actually takes, or preregister a model change first. Do "
            "not carry a Qwen3-era mechanism into a Gemma-4 measurement."
        ),
        "overall_goal_met": False,
        "section_7_met": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="R280 active decision path audit")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()

    root = Path(arguments.repository_root).resolve()
    result = build(root)
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
