"""Diagnostic-only inherited Qwen profile; no runtime registration change."""
import json
import os
from pathlib import Path

from baxy_mind.llm import LlmRuntime

_original_post = LlmRuntime._post
_audit = Path(os.environ["BAXY_C03_SAMPLING_AUDIT"])


def _profile_post(self, payload, *args, **kwargs):
    if Path(str(getattr(self, "_gguf", ""))).name.casefold() != "qwen3-8b-q4_k_m.gguf":
        return _original_post(self, payload, *args, **kwargs)
    adjusted = dict(payload, temperature=0.7, top_p=0.8, top_k=20, min_p=0.0)
    with _audit.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "temperature": 0.7,
                                 "top_p": 0.8, "top_k": 20, "min_p": 0,
                                 "max_tokens": adjusted.get("max_tokens"),
                                 "grammar": "grammar" in adjusted,
                                 "thinking": adjusted.get("chat_template_kwargs")}) + "\n")
    return _original_post(self, adjusted, *args, **kwargs)


LlmRuntime._post = _profile_post
