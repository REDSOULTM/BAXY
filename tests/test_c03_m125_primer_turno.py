"""M125 (D58, 2026-10-02): the decider reads the person's conversation, never BAXY's opening.

Evidence (window v4i-devF at 8a65e023): every new conversation starts with BAXY's composed welcome («Hola, soy BAXY.
¿En qué puedo ayudarte hoy?», 101 of 101 sessions; 183 of 183 on v4i-devD), the App sends every message of the
conversation as history (``BuildMindHistory``), and the decider put it first in the prompt of every first and second
turn: F-s002, the first decided turn after the warm-up, read 42 prompt tokens in the app against 23 in the isolated
decider, the 19 tokens of that welcome as an assistant message. The LoRA was trained and measured on histories that
start with the person. Of the 41 DEV-E turns the isolated decider gets right and the app wrong, 24 are first turns.
"""

from __future__ import annotations

import json
from typing import Any

from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic import decider

SYSTEM = "S"
WELCOME = {"role": "assistant", "content": "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?"}


def _said(messages: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(message["role"], message["content"]) for message in messages]


def test_a_first_turn_reads_only_the_message_as_the_app_sends_it() -> None:
    text = "colocame narcos en netflx x fa"
    # The App's history ends with the message itself.
    sent = decider.messages(SYSTEM, text, [WELCOME, {"role": "user", "content": text}])
    assert sent == decider.messages(SYSTEM, text, [])
    assert _said(sent) == [("system", SYSTEM), ("user", text)]


def test_a_start_up_notice_before_the_person_spoke_is_not_conversation_either() -> None:
    notice = {"role": "assistant", "content": "Se descartó el plan pendiente de la sesión anterior."}
    sent = decider.messages(SYSTEM, "abre spotify", [WELCOME, notice])
    assert _said(sent) == [("system", SYSTEM), ("user", "abre spotify")]


def test_a_second_turn_reads_the_first_exchange_without_the_welcome() -> None:
    history = [
        WELCOME,
        {"role": "user", "content": "léeme el último correo"},
        {"role": "assistant", "content": "Es de Mariana: la junta pasa a las 11:30."},
        {"role": "user", "content": "apúntame eso en pendientes"},
    ]
    sent = decider.messages(SYSTEM, "apúntame eso en pendientes", history)
    assert _said(sent) == [
        ("system", SYSTEM),
        ("user", "léeme el último correo"),
        ("assistant", "Es de Mariana: la junta pasa a las 11:30."),
        ("user", "apúntame eso en pendientes"),
    ]


def test_baxy_s_replies_inside_the_conversation_are_kept() -> None:
    # A greeting answered mid-conversation is a turn: «hola» was said, BAXY greeted back.
    history = [
        WELCOME,
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "¡Hola! ¿Qué necesitas?"},
        {"role": "assistant", "content": "Tu alarma de las 7 sonó."},
    ]
    sent = decider.messages(SYSTEM, "apágala", history)
    assert _said(sent)[1:] == [
        ("user", "hola"),
        ("assistant", "¡Hola! ¿Qué necesitas?"),
        ("assistant", "Tu alarma de las 7 sonó."),
        ("user", "apágala"),
    ]
    # The last four turns may begin with BAXY's reply: only what came before the person's first message goes.
    longer = [
        {"role": "user", "content": "pon música"},
        {"role": "assistant", "content": "Suena Lofi."},
        {"role": "assistant", "content": "Volumen al 40."},
        {"role": "user", "content": "más fuerte"},
        {"role": "assistant", "content": "¿Cuánto más?"},
    ]
    assert _said(decider.messages(SYSTEM, "al 60", longer))[1] == ("assistant", "Suena Lofi.")


class _Runtime(LlmRuntime):
    """The runtime without a server: ``_post`` records the request the decider sends."""

    def __init__(self) -> None:
        self._gguf = None
        self._parallel_turn_verification = False
        self.posts: list[dict[str, Any]] = []

    def _post(self, payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        self.posts.append(payload)
        content = json.dumps({"request": "Abre Spotify.", "decision": "talk", "operations": [], "question": ""})
        return {"choices": [{"message": {"content": content}}]}


def test_the_decider_request_of_a_first_turn_is_the_isolated_one_byte_for_byte() -> None:
    tools = (("app.open", "Abre una aplicación."), ("web.search", "Busca en la web."))
    signatures = {"app.open": ("appId",), "web.search": ("query",)}
    runtime = _Runtime()
    runtime.decide_in_context(
        "abre spotify", [WELCOME, {"role": "user", "content": "abre spotify"}], tools, signatures=signatures,
    )
    assert runtime.posts[0] == runtime._decider_payload("abre spotify", [], tools, signatures)[0]
    assert [message["role"] for message in runtime.posts[0]["messages"]] == ["system", "user"]
