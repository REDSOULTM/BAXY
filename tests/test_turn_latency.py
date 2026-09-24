"""Latency of the model path (tandas 04f/05, 2026-09-24): no decode the answer waits for in vain.

The official window showed plain conversation at 5-11 s; the owner's bar is five seconds for anything
easy and three of silence. Three serial costs sat in front of every model-path answer:

* the native selector decoded whole prose answers (up to 256 tokens) that nobody reads -- only the chat
  stage words a reply -- and the catalogue probe paid that again;
* the in-progress notice was composed before the decision started, so the answer waited for it;
* the effect guard G ran after the selector although it reads only the request text.

Each cut keeps every decision identical; only when the work happens changes.
"""

from __future__ import annotations

import json
import threading
import time

from baxy_mind import llm as llm_module
from baxy_mind.__main__ import _emit_early_turn_signal, _prepare_turn_result
from baxy_mind.first_signal import PATH_MODEL
from baxy_mind.llm_transport import ChatCompletionCancelled
from baxy_mind.llm import (
    NATIVE_SELECTION_CALL_TOKENS,
    NATIVE_SELECTION_PROSE_TOKENS,
    SEMANTIC_EFFECT_GUARD_PROMPT,
    LlmRuntime,
)
from baxy_mind.planner import PlannerCatalog

_WAIT = 5.0


def _candidate(name: str, description: str) -> dict[str, object]:
    return {
        "name": name,
        "description": description,
        "arguments_schema": {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False,
        },
    }


def _choice(message: dict[str, object], finish_reason: str) -> dict[str, object]:
    return {"choices": [{"finish_reason": finish_reason, "message": message}]}


def _select(runtime: LlmRuntime, text: str = "how long should i boil noodles for") -> dict[str, object]:
    return runtime._post_native_tool_selection(
        text, ["system.time"], {"system.time": {"description": "Read the local clock."}}, [],
    )


# --- the selector's prose ---------------------------------------------------


def test_selector_prose_is_cut_at_its_budget_and_selects_nothing() -> None:
    runtime = object.__new__(LlmRuntime)
    sent: list[dict[str, object]] = []

    def post(payload: dict[str, object]) -> dict[str, object]:
        sent.append(payload)
        return _choice({"content": "Usually, boil noodles for eight to ten minutes until"}, "length")

    runtime._post = post  # type: ignore[method-assign]
    result = _select(runtime)

    assert [payload["max_tokens"] for payload in sent] == [NATIVE_SELECTION_PROSE_TOKENS]
    assert result["mode"] == "conversation"
    assert result["effect_operations"] == []


def test_a_call_cut_by_the_prose_budget_is_decoded_again_with_the_full_budget() -> None:
    runtime = object.__new__(LlmRuntime)
    sent: list[dict[str, object]] = []
    replies = [
        _choice({"content": '<tool_call>\n{"name": "baxy_system__time", "argu'}, "length"),
        _choice({"content": "", "tool_calls": [
            {"function": {"name": "baxy_system__time", "arguments": "{}"}},
        ]}, "tool_calls"),
    ]

    def post(payload: dict[str, object]) -> dict[str, object]:
        sent.append(payload)
        return replies[len(sent) - 1]

    runtime._post = post  # type: ignore[method-assign]
    result = _select(runtime, "dime la hora")

    assert [payload["max_tokens"] for payload in sent] == [
        NATIVE_SELECTION_PROSE_TOKENS, NATIVE_SELECTION_CALL_TOKENS,
    ]
    # The same request, only a larger budget: the slot still holds its prompt.
    assert {key: value for key, value in sent[0].items() if key != "max_tokens"} == {
        key: value for key, value in sent[1].items() if key != "max_tokens"
    }
    assert result["mode"] == "action"
    assert result["effect_operations"] == ["system.time"]


def test_a_parsed_call_cut_by_the_budget_is_decoded_again_too() -> None:
    runtime = object.__new__(LlmRuntime)
    sent: list[int] = []
    call = {"function": {"name": "baxy_system__time", "arguments": "{}"}}

    def post(payload: dict[str, object]) -> dict[str, object]:
        sent.append(int(payload["max_tokens"]))  # type: ignore[arg-type]
        finish = "length" if len(sent) == 1 else "tool_calls"
        return _choice({"content": "", "tool_calls": [call]}, finish)

    runtime._post = post  # type: ignore[method-assign]
    assert _select(runtime, "dime la hora")["effect_operations"] == ["system.time"]
    assert sent == [NATIVE_SELECTION_PROSE_TOKENS, NATIVE_SELECTION_CALL_TOKENS]


def test_a_complete_reply_inside_the_budget_is_one_decode() -> None:
    runtime = object.__new__(LlmRuntime)
    sent: list[int] = []

    def post(payload: dict[str, object]) -> dict[str, object]:
        sent.append(int(payload["max_tokens"]))  # type: ignore[arg-type]
        return _choice({"content": "", "tool_calls": [
            {"function": {"name": "baxy_system__time", "arguments": "{}"}},
        ]}, "tool_calls")

    runtime._post = post  # type: ignore[method-assign]
    assert _select(runtime, "dime la hora")["mode"] == "action"
    assert sent == [NATIVE_SELECTION_PROSE_TOKENS]


def test_the_prose_budget_still_holds_a_preamble_and_the_longest_call() -> None:
    # One call of a catalogue leaf is at most 26 Qwen3 tokens with its end marker
    # (measured over the served catalogue's 204 wire names). A budget below twice
    # that would cut a call that follows a one-sentence preamble.
    assert NATIVE_SELECTION_PROSE_TOKENS >= 2 * 26
    assert NATIVE_SELECTION_CALL_TOKENS == 256


# --- the in-progress notice -------------------------------------------------


def test_the_notice_is_worded_beside_the_caller_never_in_front_of_it() -> None:
    release = threading.Event()
    signals: list[dict[str, object]] = []
    signaled: list[bool] = []

    class Composer:
        @staticmethod
        def compose_user_message(*_args: object, **_kwargs: object) -> str:
            assert release.wait(_WAIT)
            return "Estoy revisando la solicitud."

    started = time.monotonic()
    worker = _emit_early_turn_signal(
        path=PATH_MODEL, objective="how long should i boil noodles for", request_id="t7",
        on_signal=signals.append, already_signaled=signaled, llm=Composer(),
    )
    assert worker is not None
    assert time.monotonic() - started < 1.0
    assert signals == []
    # Reserved while it is being worded: a second stage does not word another.
    assert signaled == [True]
    assert _emit_early_turn_signal(
        path=PATH_MODEL, objective="x", request_id="t7",
        on_signal=signals.append, already_signaled=signaled, llm=Composer(),
    ) is None
    release.set()
    worker.join(_WAIT)
    assert [signal["id"] for signal in signals] == ["t7"]
    assert signals[0]["asserted_result"] is False


class _ModelPathLlm:
    """A model-path conversation whose notice may only finish after the decision started."""

    def __init__(self) -> None:
        self.decided = threading.Event()
        self.notice_saw_decision: list[bool] = []

    def compose_user_message(self, *_args: object, **_kwargs: object) -> str:
        self.notice_saw_decision.append(self.decided.wait(_WAIT))
        return "Estoy revisando la solicitud."

    def decide_turn(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        self.decided.set()
        return {
            "mode": "conversation", "operation": None, "question": "",
            "conversation_kind": "knowledge", "effect_count": "zero",
            "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "en",
        }

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return False, None

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "en"

    @staticmethod
    def chat(*_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "About eight to ten minutes, until al dente.", []


class _NoEvidence:
    @staticmethod
    def candidate_families(_text: str, _encoder: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


def test_a_model_path_decision_does_not_wait_for_its_notice() -> None:
    llm = _ModelPathLlm()
    signals: list[dict[str, object]] = []
    tool = {
        "type": "function",
        "function": {
            "name": "system_time", "canonical_name": "system.time",
            "description": "Read the local clock.", "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [],
                           "additionalProperties": False},
        },
    }
    result = _prepare_turn_result(
        {"id": "t7", "text": "how long should i boil noodles for"},
        llm=llm,
        planner_catalog=PlannerCatalog([tool]),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={"system.time": tool},
        on_signal=signals.append,
    )
    assert result["kind"] == "conversation"
    deadline = time.monotonic() + _WAIT
    while not llm.notice_saw_decision and time.monotonic() < deadline:
        time.sleep(0.01)
    # The notice was still being worded when the decision began.
    assert llm.notice_saw_decision == [True]


# --- the effect guard beside the selector -----------------------------------


def _parallel_runtime(selection: dict[str, object], guard_post) -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._parallel_turn_verification = True
    runtime._semantic_effect_cache = {}
    runtime._response_language_cache = {}
    runtime._request_attempt = 0
    guard_started = threading.Event()
    runtime.guard_started = guard_started  # type: ignore[attr-defined]
    runtime.posts = []  # type: ignore[attr-defined]

    def post(payload: dict[str, object], *_args: object, **kwargs: object) -> dict[str, object]:
        messages = payload["messages"]
        if messages[0]["content"] == SEMANTIC_EFFECT_GUARD_PROMPT:  # type: ignore[index]
            runtime.posts.append("guard")  # type: ignore[attr-defined]
            guard_started.set()
            return guard_post(kwargs.get("cancellation"))
        runtime.posts.append("selector")  # type: ignore[attr-defined]
        # The selector only answers once G is decoding beside it.
        assert guard_started.wait(_WAIT)
        return selection

    runtime._post = post  # type: ignore[method-assign]
    return runtime


_CONVERSATION = _choice({"content": "Usually eight to ten minutes."}, "stop")
_ACTION = _choice({"content": "", "tool_calls": [
    {"function": {"name": "baxy_system__time", "arguments": "{}"}},
]}, "tool_calls")


def _guard_reply(_cancellation: object) -> dict[str, object]:
    return _choice(
        {"content": '{"request_type": "stable_conversation", "effect_count": "zero"}'}, "stop",
    )


def test_the_guard_decodes_beside_the_selector_and_serves_the_later_read() -> None:
    runtime = _parallel_runtime(_CONVERSATION, _guard_reply)
    text = "how long should i boil noodles for"
    result = runtime.decide_turn(text, [_candidate("system.time", "Read the local clock.")])

    assert result["mode"] == "conversation"
    assert runtime._semantic_effect_cache[text] == ("no_effect", "zero")
    before = list(runtime.posts)  # type: ignore[attr-defined]
    # The effect-shape and public-lookup reads after the decision cost nothing.
    assert runtime._verify_semantic_effect_shape(text) == ("no_effect", "zero")
    assert runtime.public_lookup_requested(text) is False
    assert runtime.posts == before == ["guard", "selector"]  # type: ignore[attr-defined]


def test_an_action_retires_the_guard_without_waiting_for_it() -> None:
    cancelled = threading.Event()

    def guard_until_cancelled(cancellation: object) -> dict[str, object]:
        deadline = time.monotonic() + _WAIT
        while not getattr(cancellation, "cancelled", False):
            assert time.monotonic() < deadline, "the guard was never retired"
            time.sleep(0.005)
        cancelled.set()
        raise ChatCompletionCancelled("retired")

    runtime = _parallel_runtime(_ACTION, guard_until_cancelled)
    result = runtime.decide_turn(
        "dime la hora", [_candidate("system.time", "Read the local clock.")],
    )
    assert result["mode"] == "action"
    assert result["effect_operations"] == ["system.time"]
    assert cancelled.wait(_WAIT)
    assert "dime la hora" not in runtime._semantic_effect_cache


def test_a_failed_selection_retires_the_guard() -> None:
    cancelled = threading.Event()

    def guard_until_cancelled(cancellation: object) -> dict[str, object]:
        deadline = time.monotonic() + _WAIT
        while not getattr(cancellation, "cancelled", False):
            assert time.monotonic() < deadline
            time.sleep(0.005)
        cancelled.set()
        raise ChatCompletionCancelled("retired")

    runtime = _parallel_runtime(_choice({"content": None}, "length"), guard_until_cancelled)
    try:
        runtime.decide_turn("dime la hora", [_candidate("system.time", "Read the local clock.")])
    except ValueError:
        pass
    else:  # pragma: no cover - the reply above is invalid
        raise AssertionError("an invalid selection must fail")
    assert cancelled.wait(_WAIT)


def test_each_model_call_can_be_timed_without_the_persons_words(tmp_path, monkeypatch) -> None:
    audit = tmp_path / "calls.jsonl"
    monkeypatch.setenv("BAXY_MIND_MODEL_CALL_AUDIT_PATH", str(audit))
    replies: list[object] = [
        {
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            "timings": {"cache_n": 380, "prompt_n": 12, "prompt_ms": 30.5,
                        "predicted_n": 20, "predicted_ms": 246.0},
        },
        TimeoutError("se agotó el presupuesto local del LLM"),
    ]

    def fake_post(*_args: object, **_kwargs: object) -> object:
        reply = replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    monkeypatch.setattr(llm_module, "post_chat_completion", fake_post)
    runtime = object.__new__(LlmRuntime)
    runtime._request_identity = "35"
    payload = {
        "messages": [
            {"role": "system", "content": SEMANTIC_EFFECT_GUARD_PROMPT},
            {"role": "user", "content": "Mensaje actual:\nmi clave secreta es 1234"},
        ],
        "max_tokens": 64,
    }
    runtime._post(payload)
    try:
        runtime._post(payload)
    except TimeoutError:
        pass
    else:  # pragma: no cover
        raise AssertionError("the failure must reach the caller")

    rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert [row["error"] for row in rows] == ["", "TimeoutError"]
    assert rows[0]["request"] == "35"
    assert rows[0]["prompt_head"] == SEMANTIC_EFFECT_GUARD_PROMPT[:40]
    assert (rows[0]["cache_n"], rows[0]["prompt_n"], rows[0]["predicted_n"]) == (380, 12, 20)
    assert rows[0]["max_tokens"] == 64 and rows[0]["elapsed_ms"] >= 0
    assert "1234" not in audit.read_text(encoding="utf-8")


def test_one_slot_profiles_keep_the_guard_where_it_was() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._parallel_turn_verification = False
    posts: list[str] = []

    def post(payload: dict[str, object], *_args: object, **_kwargs: object) -> dict[str, object]:
        posts.append("guard" if payload["messages"][0]["content"] == SEMANTIC_EFFECT_GUARD_PROMPT else "selector")  # type: ignore[index]
        return _CONVERSATION

    runtime._post = post  # type: ignore[method-assign]
    runtime.decide_turn("how long", [_candidate("system.time", "Read the local clock.")])
    assert posts == ["selector"]
    assert llm_module.LlmRuntime._run_with_completion_cancellation  # shared by both cascades
