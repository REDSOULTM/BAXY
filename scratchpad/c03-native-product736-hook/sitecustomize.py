"""Explicit, private product experiment; native profile plus boundary logging."""
import copy
import itertools
import json
import os
from pathlib import Path
import threading
import time

from baxy_mind import llm
import c03_k2_native_adapter732 as native
from c03_k2_native_adapter734 import install

private = Path(os.environ["BAXY_C03_COMPARE_PRIVATE"])
profile = os.environ["BAXY_C03_COMPARE_MODEL"]
assert private.is_absolute() and private.is_dir() and profile in {"k2", "qwen"}
lock, sequence = threading.Lock(), itertools.count()


def log(filename, value):
    with lock, (private / filename).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": time.monotonic(), "pid": os.getpid(), **value},
                                ensure_ascii=False) + "\n")


if profile == "qwen":
    def adapt_qwen(payload):
        wire = copy.deepcopy(payload)
        wire.update(temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
                    repeat_penalty=1.0, presence_penalty=0.0, max_tokens=4096)
        wire.setdefault("seed", 0)
        template = wire.get("chat_template_kwargs", {})
        template.pop("enable_thinking", None)
        template.pop("reasoning_effort", None)
        if not template:
            wire.pop("chat_template_kwargs", None)
        return wire

    native.adapt_payload = adapt_qwen

uninstall = install(private, os.environ["BAXY_MIND_LLM_GGUF"],
                    os.environ["BAXY_MIND_LLM_ENDPOINT"])
original_init = llm.LlmRuntime.__init__
original_post = llm.LlmRuntime._post
original_decide = llm.LlmRuntime.decide_turn
original_guard = llm.LlmRuntime._verify_semantic_effect_shape


def observe_init(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    assert self._native_tool_policy_enabled and not self._parallel_turn_verification
    assert self._endpoint == os.environ["BAXY_MIND_LLM_ENDPOINT"]
    self._c03_native_profile736 = profile
    log("runtime-init.jsonl", {"profile": profile, "endpoint": self._endpoint,
        "model": self._gguf, "native_policy": self._native_tool_policy_enabled,
        "parallel_verification": self._parallel_turn_verification,
        "request_timeout": self._request_timeout})


def observe_post(self, payload, *args, **kwargs):
    number = next(sequence)
    log("http-posts.jsonl", {"id": number, "stage": "request", "payload": payload})
    try:
        response = original_post(self, payload, *args, **kwargs)
    except Exception as error:
        log("http-posts.jsonl", {"id": number, "stage": "failure",
            "errorType": type(error).__name__, "detail": str(error)})
        raise
    log("http-posts.jsonl", {"id": number, "stage": "response", "response": response})
    return response


def observe_decide(self, text, candidates, *, history=None, evidence=None):
    number = next(sequence)
    log("decision-boundary.jsonl", {"id": number, "stage": "input", "text": text,
        "candidates": candidates, "history": history, "evidence": evidence})
    try:
        result = original_decide(self, text, candidates, history=history, evidence=evidence)
    except Exception as error:
        log("decision-boundary.jsonl", {"id": number, "stage": "failure",
            "errorType": type(error).__name__, "detail": str(error)})
        raise
    log("decision-boundary.jsonl", {"id": number, "stage": "output", "result": result})
    return result


def observe_guard(self, text):
    log("legacy-guard.jsonl", {"stage": "input", "text": text})
    return original_guard(self, text)


llm.LlmRuntime.__init__ = observe_init
llm.LlmRuntime._post = observe_post
llm.LlmRuntime.decide_turn = observe_decide
llm.LlmRuntime._verify_semantic_effect_shape = observe_guard
log("hook-ready.jsonl", {"profile": profile, "adapter": "native736"})
