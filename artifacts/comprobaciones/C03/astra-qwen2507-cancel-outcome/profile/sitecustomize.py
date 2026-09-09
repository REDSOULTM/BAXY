"""Diagnostic-only inherited Qwen profile; no runtime registration change."""
import json
import os
import time
import threading
from pathlib import Path

from baxy_mind.llm import LlmRuntime

_original_post = LlmRuntime._post
_audit = Path(os.environ["BAXY_C03_SAMPLING_AUDIT"])


def _profile_post(self, payload, *args, **kwargs):
    if Path(str(getattr(self, "_gguf", ""))).name.casefold() != "qwen3-4b-instruct-2507-q4_k_m.gguf":
        return _original_post(self, payload, *args, **kwargs)
    adjusted = dict(payload, temperature=0.7, top_p=0.8, top_k=20, min_p=0.0)
    started = time.monotonic()
    call_id = f"{os.getpid()}:{threading.get_ident()}:{time.monotonic_ns()}"
    request_id = str(getattr(self, "_request_identity", ""))
    prompt = str(adjusted.get("messages", [{}])[0].get("content", ""))[:96]
    with _audit.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": os.getpid(), "callId": call_id, "requestId": request_id, "phase": "begin", "prompt": prompt, "temperature": 0.7,
                                 "top_p": 0.8, "top_k": 20, "min_p": 0,
                                 "max_tokens": adjusted.get("max_tokens"),
                                 "grammar": "grammar" in adjusted,
                                 "thinking": adjusted.get("chat_template_kwargs")}) + "\n")
    error = None
    try:
        response = _original_post(self, adjusted, *args, **kwargs)
        if prompt.startswith("Clasifica semánticamente el pedido actual"):
            with _audit.with_name("effect-shape.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"requestId":request_id, "user":adjusted["messages"][-1]["content"], "response":response.get("choices", [{}])[0].get("message")})+"\n")
        with _audit.with_name("decode-results.jsonl").open("a", encoding="utf-8") as stream:
            choice = response.get("choices", [{}])[0]
            stream.write(json.dumps({"requestId": request_id, "callId": call_id,
                                     "finishReason": choice.get("finish_reason"),
                                     "usage": response.get("usage")}) + "\n")
        return response
    except Exception as exc:
        error = type(exc).__name__
        raise
    finally:
        with _audit.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"callId": call_id, "requestId": request_id,
                                     "phase": "end", "seconds": round(time.monotonic()-started, 3),
                                     "error": error}) + "\n")


LlmRuntime._post = _profile_post

