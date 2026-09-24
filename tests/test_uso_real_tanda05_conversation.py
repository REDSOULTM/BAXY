"""Uso real tanda 5 (2026-09-24, official window): conversational behaviours, one owner per rule.

1. Saying back a previous message is conversation over the dialogue: «¿puedes reproducir mis últimas palabras?»
   played media and then asked which words. The person's previous message (or BAXY's own, «¿qué dijiste?») is
   the literal of the reply; the model words the sentence around a marker and never sees it. Owner:
   llm._literal_recall_reference / _recalled_speaker, composed by LlmRuntime._compose_literal_answer.
2. A parrot mode is a limit, never acknowledged: «di lo mismo que yo hasta que te avise» → «Claro, estaré
   atento» and later «No hay más repeticiones por finalizar». Owner: semantic/patterns.echo_mode_request, a known
   unsupported contract.
3. A die, a coin or a number within a range is drawn by the mind: «roll that dice, ai» was searched on the web.
   The drawn value is the one literal of the sentence. Owner: llm.random_draw_request / _drawn_literal.
4. A definition asked with a telling verb is the stable knowledge path: «Me podrias indicar que es el futbol
   americano y sus reglas para jugar?» took 19.3 s through the whole model path and the reply ran out of the turn
   (clarification route). Owner: __main__._explicit_stable_no_effect_turn_decision (definition).
5. Asking what is new greets: «¿qué dices de nuevo?» was answered with an invented list of capabilities. Owner:
   __main__._SOCIAL_ACTS (wellbeing).

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run, with negative controls.
"""

from __future__ import annotations

import copy

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.__main__ import _prepare_turn_result
from baxy_mind.llm import (
    LlmRuntime,
    RandomDraw,
    _conversation_presentation_shape,
    _literal_recall_reference,
    _recalled_speaker,
    random_draw_request,
)
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.patterns import echo_mode_request, known_unsupported_effect_request
from test_c03_pointless_questions import _NoEvidence, _tool

OPERATIONS = ("media.play.query", "media.play.youtube", "web.search", "audio.volume", "system.time")

HISTORY = [
    {"role": "user", "content": "pon el volumen en 10"},
    {"role": "assistant", "content": "El volumen está en 10."},
]


# ------------------------------------------------------------ 1. recall of a previous message


@pytest.mark.parametrize(
    "text",
    [
        "¿puedes reproducir mis últimas palabras?",
        "repite lo que te dije",
        "repíteme lo que acabo de decir, porfa",
        "¿qué te dije?",
        "qué fue lo último que te dije",
        "¿cuál fue mi último mensaje?",
        "dime mi mensaje anterior",
        "what did I just say?",
        "can you repeat what I said?",
        "read back my last message please",
        "what were my last words",
        "oye baxy, repeat mis últimas palabras",
    ],
)
def test_the_persons_previous_message_is_said_back_whole(text):
    history = [*HISTORY, {"role": "user", "content": text}]
    assert _recalled_speaker(text) == "user"
    assert _literal_recall_reference(history, text) == "pon el volumen en 10"


@pytest.mark.parametrize(
    "text",
    [
        "¿qué dijiste?",
        "repite lo que me dijiste",
        "repíteme tu última respuesta",
        "what did you just say?",
        "repeat your last answer",
        "say again what you said",
    ],
)
def test_baxys_own_previous_message_is_said_back_whole(text):
    history = [*HISTORY, {"role": "user", "content": text}]
    assert _recalled_speaker(text) == "assistant"
    assert _literal_recall_reference(history, text) == "El volumen está en 10."


@pytest.mark.parametrize(
    "text",
    [
        "¿qué dije sobre la reunión?",
        "repite la última canción",
        "reproduce mi última playlist",
        "reproduce las últimas noticias",
        "repite lo que diga",
        "what did I say yesterday about the trip",
        "repeat after me: hola",
        "repite eso",
        "repeat that again",
        "¿qué dices?",
        "what did she say?",
    ],
)
def test_other_asks_are_not_a_recall_of_the_previous_message(text):
    history = [*HISTORY, {"role": "user", "content": text}]
    assert _recalled_speaker(text) is None
    assert _literal_recall_reference(history, text) is None


def test_the_quoted_literal_recall_keeps_its_own_contract():
    history = [{"role": "user", "content": "Explica por qué «Nimbo8979» suena amistosa."}]
    assert _literal_recall_reference(history, "¿Qué palabra mencioné antes?") == "Nimbo8979"


def test_a_reply_laid_out_in_lines_is_said_back_as_one_run_of_its_words():
    history = [
        {"role": "user", "content": "how long should i cook the steak"},
        {"role": "assistant", "content": "It depends on the thickness:\n- Rare: 2 minutes\n- Medium: 4 minutes"},
    ]
    assert _literal_recall_reference(history, "what did you just say?") == (
        "It depends on the thickness: - Rare: 2 minutes - Medium: 4 minutes"
    )


def _marker_runtime(scaffold: str, seen: list[dict]) -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)

    def post(payload: dict) -> dict:
        seen.append(payload)
        return {"choices": [{"message": {"content": scaffold}}]}

    runtime._post = post  # type: ignore[method-assign]
    return runtime


# Tanda 5c: worded around an opaque marker, the small model refused, glued or dropped the text; given the
# message as the fact of the turn it says it back verbatim. The mind still checks the literal comes back whole.
def test_the_recall_is_said_back_from_the_fact_of_the_turn():
    seen: list[dict] = []
    runtime = _marker_runtime("Dijiste: «pon el volumen en 10».", seen)
    current = "¿puedes reproducir mis últimas palabras?"
    reply, calls = runtime.chat(
        current,
        history=[*HISTORY, {"role": "user", "content": current}],
        temperature=0.0,
        conversation_kind="followup",
        response_language="es",
    )
    assert reply == "Dijiste: «pon el volumen en 10»."
    assert calls == []
    assert len(seen) == 1
    assert "textual: «pon el volumen en 10»" in seen[0]["messages"][0]["content"]
    assert "último mensaje de la persona" in seen[0]["messages"][0]["content"]


def test_a_quoted_order_said_back_is_not_an_effect_claim():
    # The recalled words may be an order or a done effect; only the words around them are BAXY's.
    seen: list[dict] = []
    runtime = _marker_runtime("Tu último mensaje fue: ya apagué la luz y subí el volumen", seen)
    history = [
        {"role": "user", "content": "ya apagué la luz y subí el volumen"},
        {"role": "assistant", "content": "Entendido."},
    ]
    reply, _ = runtime.chat("what did I just say?", history=history, temperature=0.0,
                            conversation_kind="followup", response_language="en")
    assert reply == "Tu último mensaje fue: ya apagué la luz y subí el volumen"
    assert len(seen) == 1


class _ConversationLlm:
    """A runtime that must not run the model path for a closed conversation turn."""

    def __init__(self) -> None:
        self.chats: list[dict] = []

    @staticmethod
    def decide_turn(*_args, **_kwargs):
        raise AssertionError("a closed conversation turn does not run the policy")

    def chat(self, text, **kwargs):
        self.chats.append({"text": text, **kwargs})
        return "Respuesta de prueba.", []

    @staticmethod
    def public_lookup_requested(_text):
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text):
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text):
        raise AssertionError("the closed route already owns the language")

    @staticmethod
    def consume_deferred_response_language(_text):
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text):
        return None


def _turn(text, history=(), runtime=None):
    tools = {operation: _tool(operation, required=("query",)) for operation in OPERATIONS}
    runtime = runtime or _ConversationLlm()
    result = _prepare_turn_result(
        {"id": "tanda-05", "text": text, "history": [*history, {"role": "user", "content": text}]},
        llm=runtime,
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )
    return result, runtime


@pytest.mark.parametrize(
    "text",
    ["¿puedes reproducir mis últimas palabras?", "reproduce lo que te dije", "what did I just say?", "¿qué dijiste?"],
)
def test_a_recall_turn_is_conversation_never_media_playback(text):
    result, runtime = _turn(text, HISTORY)
    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert runtime.chats and runtime.chats[0]["history"]


# ------------------------------------------------------------ 2. the parrot mode is a limit


@pytest.mark.parametrize(
    "text",
    [
        "di lo mismo que yo hasta que te avise",
        "repite todo lo que yo diga",
        "a partir de ahora imita lo que digo",
        "repíteme cada cosa que te escriba",
        "hazte el loro un rato",
        "activa el modo loro",
        "repeat everything I say",
        "say the same as me until I say stop",
        "from now on repeat whatever I type",
        "repeat after me until I tell you to stop",
        "please echo mode on",
    ],
)
def test_a_parrot_mode_is_a_known_limit(text):
    assert echo_mode_request(text)
    assert known_unsupported_effect_request(text, OPERATIONS)
    # Never acknowledged as a conduct directive («Claro, estaré atento»).
    assert _conversation_presentation_shape(text, conversation_kind="unsupported", has_history=True) is None


@pytest.mark.parametrize(
    "text",
    [
        "repite lo que dije",
        "repeat what I said",
        "di hola",
        "repeat after me: hola",
        "copia lo que escribo en el portapapeles",
        "dime lo que quieras",
        "a partir de ahora háblame en inglés",
        "imítame",
    ],
)
def test_other_repetitions_are_not_the_parrot_mode(text):
    assert not echo_mode_request(text)


def test_the_parrot_mode_turn_is_a_limit_in_conversation():
    result, runtime = _turn("di lo mismo que yo hasta que te avise", HISTORY)
    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert runtime.chats[0]["conversation_kind"] == "unsupported"


def test_a_conduct_directive_is_still_acknowledged():
    assert _conversation_presentation_shape(
        "a partir de ahora háblame más formal", conversation_kind="knowledge", has_history=True,
    ) == "constraint_ack"


# ------------------------------------------------------------ 3. dice, coins and numbers are drawn


@pytest.mark.parametrize(
    ("text", "draw"),
    [
        ("roll that dice, ai", RandomDraw("die")),
        ("tira un dado", RandomDraw("die")),
        ("¿puedes lanzar dos dados?", RandomDraw("die", count=2)),
        ("tírame un dado de 20 caras porfa", RandomDraw("die", high=20)),
        ("roll a d20", RandomDraw("die", high=20)),
        ("oye baxy roll 2d6", RandomDraw("die", count=2)),
        ("roll un dado porfa", RandomDraw("die")),
        ("hazme una tirada de dados", RandomDraw("die")),
        ("lanza una moneda", RandomDraw("coin", high=2)),
        ("flip a coin for me", RandomDraw("coin", high=2)),
        ("¿cara o sello?", RandomDraw("coin", high=2, faces=("cara", "sello"))),
        ("heads or tails", RandomDraw("coin", high=2, faces=("heads", "tails"))),
        ("dame un número del 1 al 10", RandomDraw("number", low=1, high=10)),
        ("elige un número al azar entre 5 y 50", RandomDraw("number", low=5, high=50)),
        ("give me a random number between 1 and 100", RandomDraw("number", low=1, high=100)),
        ("pick a number from 3 to 9 please", RandomDraw("number", low=3, high=9)),
    ],
)
def test_a_draw_is_read_whole(text, draw):
    assert random_draw_request(text) == draw


@pytest.mark.parametrize(
    "text",
    [
        "tira la basura",
        "roll the window down",
        "lanza Steam",
        "tira los dados de Monopoly en la mesa",
        "¿qué es un dado?",
        "how many sides does a die have",
        "dame un número de teléfono",
        "dame un número del 10 al 1",
        "tira 50 dados",
        "tira un dado y abre Spotify",
    ],
)
def test_other_requests_are_not_a_draw(text):
    assert random_draw_request(text) is None


class _FixedDraw:
    def __init__(self, *values: int) -> None:
        self.values = list(values)

    def randint(self, low: int, high: int) -> int:
        value = self.values.pop(0)
        assert low <= value <= high
        return value

    @staticmethod
    def choice(options):
        return options[-1]


# Tanda 5b (official window): «roll that dice, ai» died twice when the draft named the die («de 6 caras») and the
# marker check refused it. The drawn value is the mind's own, not untrusted text: the model sees it and writes it;
# the check keeps it the only result (the value, numbers of the request and the die's faces, nothing else).
def test_the_die_is_drawn_by_the_mind_and_the_model_words_it(monkeypatch):
    monkeypatch.setattr(llm, "_DRAW", _FixedDraw(4))
    seen: list[dict] = []
    runtime = _marker_runtime("You rolled a 4.", seen)
    reply, calls = runtime.chat("roll that dice, ai", history=[], temperature=0.0,
                                conversation_kind="social", response_language="en")
    assert reply == "You rolled a 4."
    assert calls == []
    assert "salió 4." in seen[0]["messages"][0]["content"]


def test_the_faces_of_the_die_may_be_named_with_the_value(monkeypatch):
    monkeypatch.setattr(llm, "_DRAW", _FixedDraw(5))
    reply, _ = _marker_runtime("Salió un 5 en el dado de 6 caras.", []).chat(
        "roll that dice, ai", history=[], temperature=0.0, conversation_kind="social", response_language="es",
    )
    assert reply == "Salió un 5 en el dado de 6 caras."


def test_several_dice_and_a_coin_are_said_in_the_request_language(monkeypatch):
    monkeypatch.setattr(llm, "_DRAW", _FixedDraw(3, 6))
    reply, _ = _marker_runtime("Salieron 3 y 6.", []).chat(
        "tira dos dados", history=[], temperature=0.0, conversation_kind="social", response_language="es",
    )
    assert reply == "Salieron 3 y 6."
    monkeypatch.setattr(llm, "_DRAW", _FixedDraw())
    reply, _ = _marker_runtime("Salió cruz.", []).chat(
        "lanza una moneda", history=[], temperature=0.0, conversation_kind="social", response_language="es",
    )
    assert reply == "Salió cruz."


@pytest.mark.parametrize("draft", ["Salió un 3, no, un 5.", "5", "¿5?", "Salió 7.", "Salió un 5, y luego un 2."])
def test_a_wording_that_invents_another_number_or_says_only_the_value_is_refused(monkeypatch, draft):
    monkeypatch.setattr(llm, "_DRAW", _FixedDraw(5))
    with pytest.raises(ValueError):
        _marker_runtime(draft, []).chat(
            "tira un dado", history=[], temperature=0.0, conversation_kind="social", response_language="es",
        )


def test_the_sides_the_person_named_may_be_said_again(monkeypatch):
    monkeypatch.setattr(llm, "_DRAW", _FixedDraw(17))
    reply, _ = _marker_runtime("En el dado de 20 caras salió 17.", []).chat(
        "tira un dado de 20 caras", history=[], temperature=0.0, conversation_kind="social",
        response_language="es",
    )
    assert reply == "En el dado de 20 caras salió 17."


@pytest.mark.parametrize("text", ["roll that dice, ai", "lanza una moneda", "dame un número del 1 al 6"])
def test_a_draw_turn_is_conversation_never_a_web_search(text):
    result, runtime = _turn(text, HISTORY)
    assert result["kind"] == "conversation"
    assert result["effectOperations"] == []
    assert runtime.chats[0]["conversation_kind"] == "social"


# ------------------------------------------------------------ 4. definitions asked with a telling verb


@pytest.mark.parametrize(
    "text",
    [
        "Me podrias indicar que es el futbol americano y sus reglas para jugar?",
        "¿me puedes decir qué es la fotosíntesis?",
        "explícame qué son los axiomas de Peano",
        "indícame qué es un agujero negro",
        "tell me what is a black hole",
        "cuéntame qué es el béisbol",
        "tell me qué es el cricket",
    ],
)
def test_a_definition_asked_with_a_telling_verb_is_stable_knowledge(text):
    decision = sidecar._explicit_stable_no_effect_turn_decision(text)
    assert decision is not None and decision["conversation_kind"] == "knowledge"


@pytest.mark.parametrize(
    "text",
    ["dime qué es lo que está sonando", "dime qué hora es", "indícame el volumen actual", "dime la fecha"],
)
def test_a_live_read_asked_with_a_telling_verb_is_not_a_definition(text):
    decision = sidecar._explicit_stable_no_effect_turn_decision(text)
    assert decision is None or decision["conversation_kind"] != "knowledge"


# ------------------------------------------------------------ 5. what is new greets


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("¿qué dices de nuevo?", "es"),
        ("¿qué hay de nuevo?", "es"),
        ("¿qué onda?", "es"),
        ("¿qué me cuentas?", "es"),
        ("hola, ¿qué hay de nuevo?", "es"),
        ("what's new?", "en"),
        ("what's up", "en"),
        ("hey, what is new", "en"),
    ],
)
def test_asking_what_is_new_is_a_greeting(text, language):
    decision = sidecar._explicit_social_turn_decision(text)
    assert decision is not None
    assert decision["conversation_kind"] == "social"
    assert decision["response_language"] == language


@pytest.mark.parametrize(
    "text",
    ["¿qué dices?", "¿qué hay de nuevo en Chile hoy?", "what's new in the news today", "¿qué hay en mi escritorio?"],
)
def test_other_questions_are_not_a_greeting(text):
    assert sidecar._explicit_social_turn_decision(text) is None


# Tanda 5b (official window): «No puedo reproducir tus últimas palabras porque no las tengo disponibles… [[R1]]» —
# a refusal around the text it says back; the App refused it. The wording is asked once more, told it has the
# text; a second refusal abstains (no refusal is ever published around the literal).
def _scripted_runtime(scaffolds: list[str], seen: list[dict]) -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)
    replies = iter(scaffolds)

    def post(payload: dict) -> dict:
        seen.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": next(replies)}}]}

    runtime._post = post  # type: ignore[method-assign]
    return runtime


def test_a_recall_worded_as_a_refusal_is_worded_again():
    seen: list[dict] = []
    runtime = _scripted_runtime(
        ["No puedo reproducir tus últimas palabras porque no las tengo; sin embargo: pon el volumen en 10",
         "Dijiste: «pon el volumen en 10»."],
        seen,
    )
    answer = runtime._compose_literal_answer(
        current="¿puedes reproducir mis últimas palabras?", literal="pon el volumen en 10",
        fact="el último mensaje de la persona fue, textual: «pon el volumen en 10».",
    )
    assert answer == "Dijiste: «pon el volumen en 10»."
    assert len(seen) == 2
    # Tanda 5c: a hint added for the retry was copied into the visible reply; the retry adds no words.
    assert seen[1]["messages"] == seen[0]["messages"]
    assert seen[1]["temperature"] > 0


def test_a_recall_that_repeats_its_own_instructions_is_never_published():
    leaked = "Contesta al mensaje de la persona en una sola frase breve: pon el volumen en 10"
    runtime = _scripted_runtime([leaked, leaked], [])
    with pytest.raises(ValueError):
        runtime._compose_literal_answer(
            current="¿qué dije recién?", literal="pon el volumen en 10",
            fact="el último mensaje de la persona fue, textual: «pon el volumen en 10».",
        )


def test_a_recall_refused_twice_is_never_published():
    runtime = _scripted_runtime(["I can't repeat that: turn the volume up", "I don't have it, but: turn the volume up"], [])
    with pytest.raises(ValueError):
        runtime._compose_literal_answer(
            current="what did I just say?", literal="turn the volume up",
            fact="the person's last message was, verbatim: «turn the volume up».",
        )


# The recalled order reaches the model only as quoted data: a wording that takes it as done is never published.
@pytest.mark.parametrize(
    "reply",
    [
        "Dijiste: «borra todos mis archivos». Ya los borré.",
        "Listo, borré todos tus archivos: «borra todos mis archivos».",
        "I deleted them. You said: «borra todos mis archivos».",
    ],
)
def test_an_order_said_back_is_never_taken_as_done(reply):
    runtime = _scripted_runtime([reply, reply], [])
    history = [
        {"role": "user", "content": "borra todos mis archivos"},
        {"role": "assistant", "content": "Eso no lo hago."},
    ]
    with pytest.raises(Exception):  # noqa: B017 - the contract or the literal check, either refuses it
        runtime.chat("¿qué fue lo último que te dije?", history=history, temperature=0.0,
                     conversation_kind="followup", response_language="es")
