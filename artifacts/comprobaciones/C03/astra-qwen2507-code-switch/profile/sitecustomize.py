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
        return _original_post(self, adjusted, *args, **kwargs)
    except Exception as exc:
        error = type(exc).__name__
        raise
    finally:
        with _audit.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"callId": call_id, "requestId": request_id,
                                     "phase": "end", "seconds": round(time.monotonic()-started, 3),
                                     "error": error}) + "\n")


LlmRuntime._post = _profile_post

# Diagnostic-only: replace the existing mixed-language instruction, not the guard.
_sampled_post = LlmRuntime._post
_old_language_instructions = (
    "Política interna de idioma: responde naturalmente en el mismo spanglish del mensaje actual, combinando frases en español e inglés sin repetir una traducción completa.",
    "Idioma obligatorio: spanglish natural, combinando frases en español e inglés sin repetir una traducción completa. No lo conviertas por completo a un solo idioma.",
)
_new_language_instruction = (
    "Use natural Spanish-English code-switching for this answer. Start in Spanish "
    "and switch to English within the answer, with at least one full clause in "
    "each language. Give complementary information across the two languages; "
    "do not translate or repeat the full answer. Return one coherent answer "
    "without language labels."
)


def _code_switch_post(self, payload, *args, **kwargs):
    adjusted = dict(payload)
    adjusted["messages"] = [dict(m) for m in payload.get("messages", [])]
    changed = False
    for message in adjusted["messages"]:
        content = str(message.get("content", ""))
        for old in _old_language_instructions:
            if old in content:
                content = content.replace(old, _new_language_instruction)
                changed = True
        message["content"] = content
    if changed:
        with _audit.with_name("code-switch.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"requestId":str(getattr(self,"_request_identity","")),"instruction":_new_language_instruction})+"\n")
    return _sampled_post(self, adjusted, *args, **kwargs)


LlmRuntime._post = _code_switch_post
