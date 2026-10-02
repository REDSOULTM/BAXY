"""M117 (2026-10-01): BAXY's own time around the model, cut without changing a decision.

Evidence (window runs v4f-devF, v4e2-devF, v4e-devD, v4d-devD; shell trace, turn audit): a decided turn spent ≈0.35 s
p50 in turn.decide beyond the decider's own prefill and decode. Replayed offline with the model answering the app's
recorded decision, the readers cost 0.20 s p50 per turn on DEV-F (0.13 s on DEV-D), 0.18 s of it before the decider
was asked: the same clauses folded, stripped and split again thousands of times per turn (2.0 M folds, 631 k envelope
strips in 280 turns). Two cuts, both checked on the 1 224 replayed turns (identical results and model calls):

* the pure readings of a text are kept (``normalize.fold``, the ``grammar`` readings): 0.20 → 0.05 s p50 (DEV-F);
* a follow-up's contextual decision starts with the turn, beside the conversation readers
  (``LlmRuntime.prepare_decision``), and is handed over only to the same request, byte for byte (replayed: every
  decision asked was the one prepared); a first message the readers prove spends no decode on it;
* the decider's catalog prompt is read into its slot when the catalog is configured (``LlmRuntime.warm_decider``):
  the first decided turn of every run prefilled ≈6 400 tokens (3.7–3.9 s).
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import LlmRuntime
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import grammar
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.normalize import _fold_text, fold

# ------------------------------------------------------------------ pure readings are kept, never changed


def test_fold_reads_as_before_and_keeps_its_readings() -> None:
    assert fold(" Súbelo  YA ") == "subelo ya"
    assert fold(None) == "" and fold(0) == "" and fold(12) == "12"
    assert fold("Canción") is fold("Canción")
    assert 0 < _fold_text.cache_info().maxsize <= 16384


TEXTS = (
    "Hola baxy, ¿podrías poner el volumen al 40 por favor?",
    "no, mejor abre spotify y pon algo tranqui gracias",
    "anota que mañana compro pan y después abre el calendario",
    "ok, recuérdame llamar a mamá a las 6",
    "",
)


@pytest.mark.parametrize("text", TEXTS)
def test_a_kept_reading_is_the_reading_itself(text: str) -> None:
    folded = fold(text)
    for reading in (
        grammar._strip_request_envelope,
        grammar._strip_trailing_social_closure,
        grammar._request_head,
        grammar._request_body_surface,
        grammar._literal_note_payload_request,
        grammar._request_clauses,
    ):
        for value in (text, folded):
            kept = reading(value)
            assert kept == reading.__wrapped__(value)
            # Handed back as computed: never a value a caller could change for the next one.
            assert isinstance(kept, (str, bool, tuple))


# ------------------------------------------------------------------ the decision starts with the turn


def _reply(request: str) -> dict[str, Any]:
    content = json.dumps({"request": request, "decision": "talk", "operations": [], "question": ""})
    return {"choices": [{"message": {"content": content}}], "timings": {"prompt_n": 23, "predicted_n": 40}}


class _Runtime(LlmRuntime):
    """The runtime without a server: ``_post`` records each request the decider would send."""

    def __init__(self, *, parallel: bool = True, gate: threading.Event | None = None) -> None:
        self._gguf = None
        self._parallel_turn_verification = parallel
        self.posts: list[tuple[dict[str, Any], dict[str, Any]]] = []
        self.gate = gate
        self.cancellations: list[Any] = []

    def _post(self, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.posts.append((payload, kwargs))
        if kwargs.get("cancellation") is not None:
            self.cancellations.append(kwargs["cancellation"])
        if self.gate is not None:
            self.gate.wait(5)
        return _reply(payload["messages"][-1]["content"])


TOOLS = (("app.open", "Abre una aplicación."), ("web.search", "Busca en la web."))
SIGNATURES = {"app.open": ("appId",), "web.search": ("query",)}


def _wait_posts(runtime: _Runtime, count: int) -> None:
    deadline = time.monotonic() + 5
    while len(runtime.posts) < count and time.monotonic() < deadline:
        time.sleep(0.005)


def test_a_prepared_decision_is_the_one_request_the_turn_sends() -> None:
    runtime = _Runtime()
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", [], TOOLS, signatures=SIGNATURES)
    _wait_posts(runtime, 1)
    decided = runtime.decide_in_context("abre spotify", [], TOOLS, signatures=SIGNATURES)
    assert decided.request == "abre spotify" and decided.decision == "talk"
    assert len(runtime.posts) == 1
    payload, kwargs = runtime.posts[0]
    assert kwargs["reserved_slot"] is True
    # Byte for byte the request decide_in_context builds on its own.
    assert payload == runtime._decider_payload("abre spotify", [], TOOLS, SIGNATURES)[0]
    assert runtime._last_decider_timings == {"prompt_n": 23, "prompt_ms": None, "predicted_n": 40, "predicted_ms": None}
    runtime.end_request()


def test_another_request_is_asked_again_and_the_prepared_one_retired() -> None:
    runtime = _Runtime()
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", [], TOOLS, signatures=SIGNATURES)
    _wait_posts(runtime, 1)
    decided = runtime.decide_in_context("busca el clima", [], TOOLS, signatures=SIGNATURES)
    assert decided.request == "busca el clima"
    assert [payload["messages"][-1]["content"] for payload, _ in runtime.posts] == ["abre spotify", "busca el clima"]
    assert runtime.cancellations[0].cancelled
    runtime.end_request()


def test_a_turn_the_readers_decide_retires_its_prepared_decision() -> None:
    gate = threading.Event()
    runtime = _Runtime(gate=gate)
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", [], TOOLS, signatures=SIGNATURES)
    _wait_posts(runtime, 1)
    runtime.end_request()
    assert runtime.cancellations[0].cancelled
    assert runtime._prepared_decision is None
    gate.set()


def test_the_single_slot_profile_never_prepares() -> None:
    runtime = _Runtime(parallel=False)
    runtime.begin_request(10.0)
    runtime.prepare_decision("abre spotify", [], TOOLS, signatures=SIGNATURES)
    assert runtime._prepared_decision is None and runtime.posts == []
    runtime.decide_in_context("abre spotify", [], TOOLS, signatures=SIGNATURES)
    assert len(runtime.posts) == 1 and "cancellation" not in runtime.posts[0][1]
    runtime.end_request()


def test_a_prepared_decision_still_waits_inside_the_turn_budget() -> None:
    gate = threading.Event()
    runtime = _Runtime(gate=gate)
    runtime.begin_request(0.3)
    runtime.prepare_decision("abre spotify", [], TOOLS, signatures=SIGNATURES)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        runtime.decide_in_context("abre spotify", [], TOOLS, signatures=SIGNATURES)
    assert time.monotonic() - started < 2.0
    assert runtime.cancellations[0].cancelled
    gate.set()
    runtime.end_request()


def test_the_catalog_prompt_is_read_once_before_the_first_turn() -> None:
    runtime = _Runtime()
    runtime.warm_decider(TOOLS, signatures=SIGNATURES)
    _wait_posts(runtime, 1)
    payload, kwargs = runtime.posts[0]
    assert kwargs["reserved_slot"] is True and payload["max_tokens"] == 1
    decided = runtime._decider_payload("abre spotify", [], TOOLS, SIGNATURES)[0]
    # The same system prompt (the catalog) every decision begins with; only the message differs.
    assert payload["messages"][0] == decided["messages"][0]
    assert payload["response_format"] == decided["response_format"]
    single = _Runtime(parallel=False)
    single.warm_decider(TOOLS, signatures=SIGNATURES)
    assert single.posts == []


def test_the_configured_catalog_warms_the_decider_it_will_ask() -> None:
    warmed: list[tuple[object, ...]] = []

    class _Warm:
        @staticmethod
        def warm_decider(tools: Any, *, signatures: Any = None) -> None:
            warmed.append((tuple(tools), signatures))

    catalog = PlannerCatalog([_tool(name) for name in ("web.search", "memory.save")])
    sidecar._warm_context_decider(_Warm(), catalog)
    assert warmed == [sidecar._decider_catalog(catalog)]
    sidecar._warm_context_decider(object(), catalog)  # a runtime without it is left as it is


# ------------------------------------------------------------------ the turn prepares what it will ask


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }


class _Decider:
    def __init__(self) -> None:
        self.prepared: list[tuple[object, ...]] = []
        self.asked: list[tuple[object, ...]] = []

    def prepare_decision(self, text: str, history: object, tools: Any, *, signatures: Any = None) -> None:
        self.prepared.append((text, json.dumps(history), tuple(tools), signatures))

    def decide_in_context(self, text: str, history: object, tools: Any, **kwargs: Any) -> ContextDecision:
        self.asked.append((text, json.dumps(history), tuple(tools), kwargs.get("signatures")))
        return ContextDecision(request="Busca quién ganó el partido de anoche.", decision="action",
                               operations=("web.search",), question="")

    @staticmethod
    def chat(*_args: object, **_kwargs: object) -> tuple[str, list]:
        return "Vale.", []


@pytest.mark.parametrize(
    "history",
    [[], [{"role": "user", "content": "hola"}, {"role": "assistant", "content": "Hola, ¿en qué te ayudo?"}]],
)
def test_the_turn_prepares_exactly_what_the_decider_is_asked(history: list[dict[str, str]]) -> None:
    text = "oye y quien gano el partido anoche"
    tools = {name: _tool(name) for name in ("web.search", "app.open", "memory.save")}
    llm = _Decider()
    result = sidecar._prepare_turn_result(
        {"id": "m117", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )
    if history:
        # A follow-up is the decider's (Fase 3.5b F4): it starts with the turn and is asked exactly what was prepared.
        assert result["kind"] == "action" and result["operation"] == "web.search"
        assert llm.asked == llm.prepared[-1:]
        # The decider reads the memory lines too (M114): the prepared request carries the same catalog.
        assert "memory.save" in {name for name, _ in llm.prepared[-1][2]}
    else:
        # A first message goes through every reader first; one they prove spends no decode on a guess.
        assert not llm.prepared and not llm.asked
