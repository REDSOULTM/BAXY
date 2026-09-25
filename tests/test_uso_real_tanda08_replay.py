"""Uso real, replay of tandas 7b and 8 through the real dialogue flow (2026-09-25): follow-ups 8/15 and 6/9.

The root replayed both tandas turn by turn with the model (rewrite p50 ~850 ms). What failed, one owner per rule:

1. A short or chat form is its full words: «¿y el finde?» → «¿va a llover el fin de semana?» was rejected as words
   nobody said. Owner: semantic/normalize.spelled_out, used by semantic/dialogue.rewrite_stays_in_context.
2. A clock read elsewhere names a place, and the last place wins: «y si allá son las 9…» after «qué hora es en
   Madrid» was rewritten with the weather read two turns before. Owner: semantic/dialogue.DialogueState.record.
3. What the person's words already say with the last turn is not left to the model: a new amount, hour or day for
   the last request («actually make it 9» → the timer with 9, cancelling the one just set), the song a music turn
   left playing («cómo se llama esta?»), the kinds just set («what have I got set right now?»). Owners:
   semantic/dialogue.corrected_request, .as_the_song, .DialogueState.listing_request, used by
   __main__._rearm_in_context.
4. A list read said with its pronoun, «otra vez» before it or an opener («vale, léemela otra vez la lista de la
   compra»). Owner: semantic/notes._WHOLE_LIST_READ, _LIST_READ_OPENER.
5. A bare number answers the question BAXY asked: «¿cuánto…?» an amount, a level question or none the level to end
   at («40 percent» after «How bright should the screen be adjusted to?»). Owner: semantic/levels.answers_with_amount
   through semantic/patterns.output_level_request.
6. «súbele al volumen»: «le» doubles the object said after it; the message is no reference to rewrite. Owner:
   semantic/dialogue._object_pronoun.
7. The rewrite is shown only the worked conversations of its message's shape (the twelve cost ~750 prompt tokens).
   Owner: semantic/dialogue.shape, llm.rewrite_in_context.

Every list holds fresh phrasings (Spanish dialects, English, Spanglish); none is a literal of the tandas.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.semantic import dialogue, levels
from baxy_mind.semantic.normalize import spelled_out
from baxy_mind.semantic.reading import read

OPERATIONS = (
    "audio.volume", "audio.volume.adjust", "audio.mute", "system.settings.set", "system.settings.adjust",
    "media.control", "media.play.query", "media.status", "weather.current", "web.search", "app.open",
    "notification.schedule", "notification.cancel.latest", "notification.list", "reminder.create", "reminder.list",
    "system.time", "task.create", "task.search", "task.list",
)


class _Scripted:
    """A model that writes the rewrite a good model would; a missing text means it must not be asked."""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self.answers = answers or {}
        self.seen: list[dict] = []

    def rewrite_in_context(self, text, context, **kwargs):
        self.seen.append({"text": text, **kwargs})
        if text not in self.answers:
            raise AssertionError(f"the model is not asked about {text!r}")
        return self.answers[text]


def _message(*turns: str) -> dict:
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": turn} for index, turn in enumerate(turns)
    ]
    return {"id": "replay", "text": turns[-1], "history": history}


def _rearm(message: dict, model: _Scripted, state: dialogue.DialogueState | None):
    return sidecar._rearm_in_context(message, llm=model, available_operations=OPERATIONS, dialogue_state=state)


def _verified(operation: str, observed: dict | None = None) -> dict:
    return {"kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
            "observed": observed}


def _state(*steps: tuple[str, str, dict | None]) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    for request, operation, observed in steps:
        state.expect(request, [operation])
        state.record(_verified(operation, observed))
    return state


def _effects(text: str) -> tuple[str, ...]:
    found = read(text, available_operations=OPERATIONS).effects
    return tuple(found.operations) if found is not None else ()


# ---------------------------------------------------------------- 1. short and chat forms are their full words


def test_a_short_form_is_spelled_out_in_full_words_and_only_as_a_whole_word():
    assert spelled_out("y pal finde porfa") == "y para el fin de semana por favor"
    assert spelled_out("what about tmrw pls") == "what about tomorrow please"
    assert spelled_out("papa fideos kilo") == "papa fideos kilo"  # no short form inside a word


@pytest.mark.parametrize(
    ("said", "text", "rewrite"),
    [
        ("oye, ¿va a llover hoy?", "¿y pal finde?", "¿va a llover para el fin de semana?"),
        ("che, ¿llueve hoy en Salta?", "¿y el fin de semana?", "¿llueve el finde en Salta?"),
        ("will it rain today in Leeds?", "what about tmrw", "will it rain tomorrow in Leeds?"),
        ("pon el temporizador de la pizza, 12 minutos", "y tb uno pal pan", "pon también uno para el pan"),
    ],
)
def test_a_rewrite_in_the_full_words_of_a_short_form_stays_in_context(said, text, rewrite):
    slot = dialogue.read_slot({}, [{"role": "user", "content": said}, {"role": "assistant", "content": "Listo."}], text)
    assert dialogue.rewrite_stays_in_context(rewrite, text, slot)


def test_a_word_nobody_said_is_still_rejected_after_spelling_out():
    slot = dialogue.read_slot({}, [{"role": "user", "content": "oye, ¿va a llover hoy?"}], "¿y el finde?")
    assert not dialogue.rewrite_stays_in_context("¿va a nevar el fin de semana?", "¿y el finde?", slot)


# ---------------------------------------------------------------- 2. the last place read wins


def test_a_clock_read_elsewhere_is_the_last_place():
    state = _state(("¿llueve en Rosario?", "weather.current", {"location": "Rosario", "country": "Argentina"}))
    state.expect("oye, qué hora es en Oaxaca", ["system.time"])
    state.record(_verified("system.time", {"utc": "2026-09-25T06:08:59Z",
                                           "place": {"name": "Oaxaca", "country": "México", "timeZone": "x"}}))
    places = [line for _, line in state.lines() if line.startswith("lugar")]
    assert places == ["lugar (place): Oaxaca, México"]
    # The local clock names no place: the place stays the last one read.
    state.expect("¿y qué hora es acá?", ["system.time"])
    state.record(_verified("system.time", {"utc": "2026-09-25T06:09:10Z", "localUtcOffsetMinutes": -180}))
    assert [line for _, line in state.lines() if line.startswith("lugar")] == places


# ---------------------------------------------------------------- 3. what the words already say with the last turn


@pytest.mark.parametrize(
    ("said", "text", "corrected"),
    [
        ("pon un temporizador de 10 minutos pa los fideos", "nah, que sean 7", "pon un temporizador de 7 minutos pa los fideos"),
        ("set a timer for the rice, 20 minutes", "actually make it fifteen", "set a timer for the rice, 15 minutes"),
        ("ponme una alarma a las 7 de la mañana", "no, mejor a las 7 y media", "ponme una alarma a las 7 y media de la mañana"),
        ("despertame mañana a las 6", "mejor a las 5 y cuarto", "despertame mañana a las 5 y cuarto"),
        ("wake me up at 6 am", "no wait, at 7", "wake me up at 7 am"),
        ("wake me up at 6 am", "no, at 7 pm", "wake me up at 7 pm"),
    ],
)
def test_a_correction_is_the_last_request_with_its_new_value(said, text, corrected):
    assert dialogue.corrected_request(said, text) == corrected


@pytest.mark.parametrize(
    ("said", "text"),
    [
        ("pon un temporizador de 10 minutos", "y otro de 20 pal arroz"),  # an addition
        ("pon un temporizador de 10 minutos", "¿y a las 8?"),  # continued, not corrected
        ("pon música de Charly García", "mejor 5"),  # no value of that kind
        ("pon una alarma a las 7", "mejor en Spotify"),  # not a value
    ],
)
def test_an_addition_or_a_request_without_that_value_is_not_corrected(said, text):
    assert dialogue.corrected_request(said, text) is None


def test_the_correction_of_the_timer_just_set_cancels_it_without_the_model():
    request = "pon un temporizador de 10 minutos pa los fideos"
    state = _state((request, "notification.schedule", {"kind": "alarm", "title": "fideos", "taskName": "BAXY-Alarm-7"}))
    result = _rearm(_message(request, "Listo, suena en 10 minutos.", "nah, que sean 7"), _Scripted(), state)
    assert result == ("cancela el último temporizador y pon un temporizador de 7 minutos pa los fideos", "pattern")
    assert _effects(result[0]) == ("notification.cancel.latest", "notification.schedule")


@pytest.mark.parametrize("text", ["¿y cómo se llama esta?", "quién canta esto?", "what's this one called", "who sings it"])
def test_a_bare_pointer_after_music_is_the_song_playing(text):
    state = _state(("ponme algo de Los Prisioneros", "media.play.query", {"query": "los prisioneros"}))
    result = _rearm(_message("ponme algo de Los Prisioneros", "Listo.", text), _Scripted(), state)
    assert result is not None and result[1] == "pattern"
    assert _effects(result[0]) == ("media.status",)


def test_a_bare_pointer_after_something_else_is_left_to_the_model():
    state = _state(("¿llueve hoy?", "weather.current", {"location": "Quito"}))
    model = _Scripted({"cómo se llama esto?": "cómo se llama esto?"})
    assert _rearm(_message("¿llueve hoy?", "Hoy no llueve en Quito.", "cómo se llama esto?"), model, state) is None
    assert model.seen


@pytest.mark.parametrize(
    ("text", "rearmed"),
    [
        ("¿qué tengo puesto hasta ahora?", "qué alarmas, temporizadores y recordatorios tengo puesto hasta ahora"),
        ("which do I have set now?", "which alarms, timers and reminders do I have set now"),
    ],
)
def test_what_the_person_holds_right_after_setting_it_names_the_kinds_set(text, rearmed):
    state = _state(("pon un temporizador de 5 minutos pal té", "notification.schedule", {"title": "té"}),
                   ("recordame a las 8 llamar a la vieja", "reminder.create", None))
    result = _rearm(_message("recordame a las 8 llamar a la vieja", "Listo.", text), _Scripted(), state)
    assert result == (rearmed, "pattern")
    assert _effects(rearmed) == ("notification.list", "reminder.list")


def test_only_the_kinds_this_conversation_set_are_named():
    state = _state(("set an alarm at 6 am", "notification.schedule", {"title": "alarm"}))
    assert state.listing_request("what have I got set?") == "what alarms and timers have I got set"


def test_what_the_person_holds_after_a_list_is_not_the_alarms():
    state = _state(("anota en la lista del súper yerba", "task.create", None))
    assert state.listing_request("¿qué llevo ya?") is None


# ---------------------------------------------------------------- 4. a list read, said as people say it


@pytest.mark.parametrize(
    "text",
    [
        "dale, léemela de nuevo la lista del súper",
        "ok, repítemela otra vez la lista de compras",
        "bueno, léeme otra vez mi lista de tareas",
        "vale, dime otra vez la lista de la compra",
        "léemelas nuevamente mis listas",
    ],
)
def test_a_list_read_with_its_pronoun_again_or_an_opener_is_read(text):
    assert _effects(text) in {("task.search",), ("task.list",)}


# ---------------------------------------------------------------- 5. a bare number answers BAXY's question


@pytest.mark.parametrize(
    ("question", "answer", "amount"),
    [
        ("¿Cuánto le bajo?", "20", True),
        ("How much darker should I make it?", "30 percent", True),
        ("¿A qué nivel la dejo?", "20", False),
        ("¿A cuánto querés el volumen?", "unos 20", False),
        ("What level do you want?", "20 percent", False),
        ("How bright should the screen be?", "20", False),
        ("Listo.", "20", False),  # no question
        (None, "20", False),
        ("¿A qué nivel?", "en 20", True),  # the answer itself says it is an amount
        ("What level?", "20 more", True),
    ],
)
def test_a_bare_number_answers_with_what_the_question_asked(question, answer, amount):
    assert levels.answers_with_amount(question, answer) is amount


@pytest.mark.parametrize(
    ("said", "question", "answer", "operation"),
    [
        ("la pantalla está re brillante", "¿A qué nivel te la dejo?", "30", "system.settings.set"),
        ("the screen is way too bright", "How bright should it be?", "35 percent", "system.settings.set"),
        ("the screen is way too bright", "How much darker should I make it?", "35 percent", "system.settings.adjust"),
        ("bájale al volumen", "¿Cuánto le bajo?", "unos 10", "audio.volume.adjust"),
        ("bájale al volumen", "¿A qué nivel lo pongo?", "unos 10", "audio.volume"),
    ],
)
def test_the_answer_after_a_question_of_baxy_is_read_by_that_question(said, question, answer, operation):
    result = _rearm(_message(said, question, answer), _Scripted(), dialogue.DialogueState())
    assert result is not None and result[1] == "pattern"
    assert _effects(result[0]) == (operation,)


# ---------------------------------------------------------------- 6. «le» doubling an object said


@pytest.mark.parametrize("text", ["oye súbele al volumen po", "dale a la música más fuerte", "bájale a las alertas"])
def test_le_with_its_object_said_after_it_is_no_reference(text):
    slot = dialogue.DialogueSlot(None, None, ("please use whisper mode",), "please use whisper mode")
    assert dialogue.dependency(text, slot) != "reference"


def test_le_with_only_a_level_after_it_still_refers_back():
    slot = dialogue.DialogueSlot(None, None, ("pon música de Soda",), "Listo.")
    assert dialogue.dependency("súbele al 50", slot) == "reference"


# ---------------------------------------------------------------- 7. the rewrite sees the conversations of its shape


@pytest.mark.parametrize(
    ("text", "dependency", "shape"),
    [
        ("¿y el domingo?", "followup", "time"),
        ("nah, que sean 20", "followup", "amount"),
        ("¿y a qué hora anochece por allá?", "followup", "place"),
        ("esa no, otra más cumbiera", "followup", "another"),
        ("¿y eso más 15?", "followup", "pointer"),
        ("¿qué me falta?", "followup", "listing"),
        ("¿y quién la dirigió?", "followup", "question"),
        ("ah y dos limones", "followup", "item"),
        ("20", "answer", "answer"),
    ],
)
def test_the_shape_of_a_message_that_depends_on_the_context(text, dependency, shape):
    assert dialogue.shape(text, dependency) == shape


def test_a_rewrite_is_shown_only_the_worked_conversations_of_its_shape():
    runtime = object.__new__(llm.LlmRuntime)
    seen: list[dict] = []

    def post(payload: dict, **_kwargs: object) -> dict:
        seen.append(payload)
        return {"choices": [{"message": {"content": json.dumps({"request": "pon un temporizador de 9 minutos"})}}]}

    runtime._post = post  # type: ignore[method-assign]
    runtime.rewrite_in_context("nah, que sean 9", [("persona", "pon un temporizador de 11 minutos")],
                               dependency="followup", shape="amount")
    shown = [json.loads(message["content"])["request"] for message in seen[0]["messages"]
             if message["role"] == "assistant"]
    expected = [example[4] for example in llm._REWRITE_EXAMPLES if "amount" in example[0]]
    assert shown == expected[: llm._REWRITE_EXAMPLES_SHOWN] and len(shown) < len(llm._REWRITE_EXAMPLES)
