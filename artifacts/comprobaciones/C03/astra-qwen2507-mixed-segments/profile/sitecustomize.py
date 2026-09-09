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

# Diagnostic representation experiment: two model-authored complementary parts.
# No authored visible response, no second decode, no authority-bearing fields.
_sampled_post = LlmRuntime._post


def _segmented_post(self, payload, *args, **kwargs):
    messages = payload.get("messages", [])
    is_mixed_public = any(
        "Política interna de idioma: responde naturalmente en el mismo " in str(m.get("content", ""))
        or "Idioma obligatorio: spanglish natural, combinando frases en " in str(m.get("content", ""))
        for m in messages
    )
    if not is_mixed_public:
        return _sampled_post(self, payload, *args, **kwargs)
    adjusted = dict(payload)
    adjusted["messages"] = [dict(m) for m in messages]
    adjusted["messages"][0]["content"] += (
        "\nReturn your response as JSON with two complementary parts: "
        "spanish contains Spanish prose, english contains English prose. "
        "Together they are ONE coherent, natural spanglish response to the request. "
        "Do not translate or repeat one part in the other; distribute the information "
        "between them. Both parts are addressed directly to the person and will "
        "appear in that order, separated only by a space. Preserve all verified "
        "facts and the purpose of this response. No language labels in the prose."
    )
    adjusted["response_format"] = {"type": "json_schema", "json_schema": {
        "name": "mixed_public_response", "strict": True, "schema": {
            "type": "object", "properties": {
                "spanish": {"type": "string", "minLength": 1},
                "english": {"type": "string", "minLength": 1}},
            "required": ["spanish", "english"], "additionalProperties": False}}}
    response = _sampled_post(self, adjusted, *args, **kwargs)
    raw = response["choices"][0]["message"]["content"]
    with _audit.with_name("segments.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"requestId": str(getattr(self,"_request_identity","")),
                                 "raw": raw, "finishReason": response["choices"][0].get("finish_reason")}, ensure_ascii=False)+"\n")
    parts = json.loads(raw)
    if set(parts) != {"spanish", "english"} or not all(isinstance(v,str) and v.strip() for v in parts.values()):
        raise ValueError("invalid_mixed_public_response")
    response["choices"][0]["message"]["content"] = parts["spanish"].strip()+" "+parts["english"].strip()
    return response


LlmRuntime._post = _segmented_post
