"""Tanda 7 (2026-09-25, official window): the latency regression against tanda 6c on the same build.

- Deterministic decisions (a volume, a mute, a timer, a paused track) took 1.3–1.9 s in ``turn.decide`` with no
  model call at all. One decision reads ~770 distinct patterns and the ``re`` module keeps 512 compiled, so every
  turn compiled ~600 of them again: 95 % of a deterministic decision was compiling regular expressions, and the
  same cost sat under every model-path turn's own readers and vetoes. The readers' shared primitives
  (``grammar._match``/``_has``/``_head_is``) now compile each pattern once for the life of the mind.
- A reply whose wording failed its contracts (``shaped_presentation``, ``wrong_language``) sends the turn to its
  second attempt; the retried decision reached the same reply and decoded the same greedy drafts again (the same
  token counts, 0.8–1.2 s) only to be rejected the same way. The turn is still retried — a different decision
  still gets its own reply — but the same greedy reply asked again under the same inputs is refused with the
  verdict it already had.

The phrasings below are not the tanda's: they are paraphrases (es/en/spanglish).
"""

from __future__ import annotations

import re

import pytest

from baxy_mind.llm import ConversationReplyContractError, LlmRuntime
from baxy_mind.semantic import grammar
from baxy_mind.semantic.reading import read

_OPERATIONS = (
    "audio.mute", "audio.volume", "audio.volume.adjust", "notification.schedule",
    "media.control", "weather.current", "system.settings.set", "window.minimize.all", "web.search",
)
_REQUESTS = (
    "vuelve a activar el parlante",
    "turn the speakers back on please",
    "ponle el volumen en 20",
    "súbele unos 10 al sonido",
    "pon una alarma en 7 minutos",
    "set me a timer for 12 minutes for the rice",
    "sigue con la canción que estaba en pausa",
    "is it going to rain later today",
    "baja el brightness a 40 por ciento",
    "llévame al escritorio",
)


# ------------------------------------------------------------------ the readers compile each pattern once


@pytest.mark.parametrize(
    ("text", "pattern"),
    [
        ("Pon el VOLUMEN a 20", r"\bvolumen\b"),
        ("turn the Speakers on", r"\bspeakers?\b"),
        ("nada que ver", r"\bvolumen\b"),
        ("ALARMA en 7", r"(?P<n>\d+)"),
    ],
)
def test_a_reader_match_is_the_case_insensitive_search_it_always_was(text: str, pattern: str) -> None:
    expected = re.search(pattern, text, re.IGNORECASE)
    found = grammar._match(text, pattern)

    assert (found is None) == (expected is None)
    if expected is not None:
        assert found is not None
        assert found.span() == expected.span()
        assert found.groupdict() == expected.groupdict()
    assert grammar._has(text, pattern) is (expected is not None)


@pytest.mark.parametrize(
    ("head", "pattern"),
    [("subele", r"sube"), ("SUBELE", r"sube"), ("ponme", r"pon(?:me)?"), ("ponme", r"baja"), ("apagala", r"apaga")],
)
def test_a_head_is_read_in_all_its_forms_without_case(head: str, pattern: str) -> None:
    expected = any(re.fullmatch(pattern, form, re.IGNORECASE) for form in grammar._head_forms(head))

    assert grammar._head_is(head, pattern) is expected


def test_reading_a_request_again_compiles_nothing() -> None:
    for text in _REQUESTS:
        read(text, available_operations=_OPERATIONS)
    compiled = grammar._compiled.cache_info().misses

    for text in _REQUESTS:
        read(text, available_operations=_OPERATIONS)

    assert grammar._compiled.cache_info().misses == compiled


def test_the_readers_whole_working_set_stays_compiled() -> None:
    for text in _REQUESTS:
        read(text, available_operations=_OPERATIONS)
    info = grammar._compiled.cache_info()

    # Every pattern ever compiled is still held: evicting one would bring the per-turn compilation back.
    assert info.misses == info.currsize < info.maxsize


# ------------------------------------------------------------------ a rejected greedy reply is not worded twice


_ASKED = "explícame despacio cómo se hace un buen asado"
_ANSWER = "Un buen asado empieza con brasas parejas y paciencia: la carne se da vuelta una sola vez."


def _runtime(content: str) -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)
    runtime._request_attempt = 0
    runtime._speculative_chat_handoff = None
    runtime._deferred_language_work = None
    runtime.posts = []  # type: ignore[attr-defined]

    def post(payload: dict[str, object], *_args: object, **_kwargs: object) -> dict[str, object]:
        runtime.posts.append(payload.get("temperature"))  # type: ignore[attr-defined]
        return {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}

    runtime._post = post  # type: ignore[method-assign]
    runtime.begin_request(10.0)
    return runtime


def _reply_arguments(**overrides: object) -> dict[str, object]:
    return {
        "history": [{"role": "assistant", "content": "Hola, soy BAXY."}],
        "tools": None,
        "temperature": 0.0,
        "conversation_kind": "knowledge",
        "authenticated_operations": (),
        "served_operations": (),
        "response_language": "es",
        **overrides,
    }


def _rejected(runtime: LlmRuntime, **overrides: object) -> str:
    with pytest.raises(ConversationReplyContractError) as failure:
        runtime.chat(_ASKED, **_reply_arguments(**overrides))
    return failure.value.audit_reason


def test_the_retried_turn_does_not_decode_the_same_rejected_reply_again() -> None:
    runtime = _runtime(_ASKED)  # an echo: every draft fails its contract
    first = _rejected(runtime)
    decoded = len(runtime.posts)  # type: ignore[attr-defined]
    assert decoded == 2  # the draft and its bounded repair

    runtime.begin_request_attempt(10.0, attempt=1)

    assert _rejected(runtime) == first
    assert len(runtime.posts) == decoded  # type: ignore[attr-defined]


def test_a_different_reply_on_the_retry_is_worded_and_judged_itself() -> None:
    runtime = _runtime(_ASKED)
    _rejected(runtime)
    decoded = len(runtime.posts)  # type: ignore[attr-defined]

    runtime.begin_request_attempt(10.0, attempt=1)
    # The retried decision words it over another dialogue: other inputs, another verdict.
    _rejected(runtime, history=[{"role": "assistant", "content": "Listo, la alarma quedó puesta."}])

    assert len(runtime.posts) > decoded  # type: ignore[attr-defined]


def test_a_sampled_reply_is_always_worded_again() -> None:
    runtime = _runtime(_ASKED)
    _rejected(runtime, temperature=0.4)
    decoded = len(runtime.posts)  # type: ignore[attr-defined]

    runtime.begin_request_attempt(10.0, attempt=1)
    _rejected(runtime, temperature=0.4)

    assert len(runtime.posts) == 2 * decoded  # type: ignore[attr-defined]


def test_a_new_request_forgets_the_verdicts_of_the_last_one() -> None:
    runtime = _runtime(_ASKED)
    _rejected(runtime)
    decoded = len(runtime.posts)  # type: ignore[attr-defined]

    runtime.begin_request(10.0)
    _rejected(runtime)

    assert len(runtime.posts) == 2 * decoded  # type: ignore[attr-defined]


def test_a_reply_that_passes_is_never_withheld() -> None:
    runtime = _runtime(_ANSWER)
    assert runtime.chat(_ASKED, **_reply_arguments()) == (_ANSWER, [])

    runtime.begin_request_attempt(10.0, attempt=1)
    assert runtime.chat(_ASKED, **_reply_arguments()) == (_ANSWER, [])
    assert len(runtime.posts) == 2  # type: ignore[attr-defined]
