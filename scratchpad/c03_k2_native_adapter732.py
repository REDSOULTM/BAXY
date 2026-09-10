"""Experimental K2 transport profile; never imported by production by default."""
from __future__ import annotations

import copy
import itertools
import json
import os
from pathlib import Path
import threading
import time

from baxy_mind import llm


PROFILE = {
    "temperature": 1.0, "top_p": 0.95, "top_k": 0, "min_p": 0.0,
    "repeat_penalty": 1.0, "presence_penalty": 0.0, "max_tokens": 4096,
}


def adapt_payload(payload):
    """Keep all messages/contracts; apply the measured practical native recipe."""
    adapted = copy.deepcopy(payload)
    adapted.update(PROFILE)
    adapted.setdefault("seed", 0)  # Preserve per-role/retry seed diversity.
    template = adapted.setdefault("chat_template_kwargs", {})
    template.pop("enable_thinking", None)
    template["reasoning_effort"] = "high"
    return adapted


def install(private: Path, model: str, endpoint: str):
    """Return an explicit uninstall function; retain original HTTP machinery."""
    assert private.is_dir()
    original_post = llm.LlmRuntime._post
    lock, sequence = threading.Lock(), itertools.count()

    def log(value):
        with lock, (private / "adapter-http.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": time.monotonic(), "pid": os.getpid(), **value},
                                    ensure_ascii=False) + "\n")

    def native_post(self, payload, timeout=None, *, max_attempts=2, cancellation=None):
        assert str(Path(self._gguf).resolve()) == str(Path(model).resolve())
        assert self._endpoint == endpoint
        assert getattr(self, "_cpu_prose_adapter", None) is None
        number = next(sequence)
        wire = adapt_payload(payload)
        log({"id": number, "stage": "request", "input": payload, "wire": wire,
             "requested_timeout": timeout, "max_attempts": max_attempts,
             "effective_timeout": self._effective_request_timeout(timeout)})

        def endpoint_for_attempt():
            self._ensure_started()
            assert self._endpoint == endpoint
            return self._endpoint

        try:
            response = llm.post_chat_completion(
                wire, endpoint_for_attempt=endpoint_for_attempt,
                timeout_for_attempt=lambda: self._effective_request_timeout(timeout),
                max_attempts=max_attempts, cancellation=cancellation,
                connection_pool=getattr(self, "_http_connection_pool", None),
            )
        except Exception as error:
            log({"id": number, "stage": "failure", "type": type(error).__name__,
                 "detail": str(error)})
            raise
        log({"id": number, "stage": "response", "response": response})
        return response

    llm.LlmRuntime._post = native_post

    def uninstall():
        assert llm.LlmRuntime._post is native_post
        llm.LlmRuntime._post = original_post

    return uninstall
