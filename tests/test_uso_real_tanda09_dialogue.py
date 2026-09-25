"""Uso real tanda 9 (2026-09-25, official window, first pass): the follow-up shapes the dialogue slot had not met.

One owner per rule:

1. A noun or an adjective that ends like a verb with its pronoun («…les», «…la») is not one: a complete request
   was sent to the rewrite and came back with a place of two turns before. A verb with its clitic is an infinitive
   or a gerund, an order the readers know with the clitic removed, or a word first in its clause. Owner:
   semantic/dialogue._object_pronoun.
2. A question word after the preposition asks a question of its own («¿en qué lugar te…?»): a complete question
   about BAXY was read as a new destination for the topic before and answered about that topic. Owner:
   semantic/dialogue._NOT_ASKED in _DESTINATION_ONLY and _PLACE_FRAGMENT.
3. An order that leaves its object out right after something played acts on what plays: «pausalo un toque» was kept
   as said and refused, «dale, seguí» was not understood. A pronoun or no object at all after the verb is what the
   last turn acted on, named as the readers name it (a song, a video), and the request must read an effect of that
   family; an agreement before a pause («dale,») is a filler. Owners: semantic/dialogue._bare_order, .with_object,
   .things_acted_on, ._FILLER; __main__._rearm_in_context.
4. An order to raise or lower the sound said with why («… que está muy fuerte», «… it's way too loud») is that order:
   it was answered «No bajé nada». The reason after it is a state; a relative change still asks how much (owner rule
   H0027). Owner: semantic/levels.read (_REASON).
5. «más», «otra vez», «a bit more» alone right after an effect are that request once more, as it was said (the
   same amount again; a change still missing its amount asks it again); «¿y más?» asks for more of an answer. «a bit
   more» is no destination. Owners: semantic/dialogue._AGAIN_FRAGMENT, .again; __main__._rearm_in_context.
6. A value pointed at with a demonstrative («ese tiempo», «esa cantidad», «that long») is the one BAXY's last
   answer gave: «ponme un timer de ese tiempo» after a cooking time was asked «¿Cuál es la hora exacta?». Only one
   value of that kind (a duration for a time, a percent for a level), never a range; the effect is the one the
   message itself asks for. Owners: semantic/dialogue._VALUE_POINTER, .value_from_reply;
   __main__._rearm_in_context (continuing accepts what the message asks for).
7. A day said in the other language, or typed with its stem kept («tomorow»), is the same word in the language of
   the message for the rewrite's check: «… mañana …» after «tomorow», «… today» after «hoy» were rejected. Into
   another language it is still a word the model brought (tanda 7's rule stands). Owner:
   semantic/dialogue.rewrite_stays_in_context (_SAME_DAY).
8. The weather asked with the day or a connector first («y mañana va a hacer más calor?») or by how the air feels
   («is it humid?», «hotter», «colder») is the weather read; both went to a web search that found nothing. Owner:
   semantic/web._live_weather_request (_LEADING_CONNECTOR_OR_DAY), _WEATHER_WORDS.
9. A value said with a copula («it will be for 3:30 pm», «it should be afternoon 3:45», «que sea a las 8») is that
   value: after BAXY's question it answers it, after an alarm just set it corrects it. An hour is a clock by its
   form too («3:45», «4 pm», the part of the day first); the alarm just set is replaced, and a clock that replaces
   one said «for» is said «at» («for 3:45» also names the alarm set for then). Both turns ended in ⚠. Owners:
   semantic/dialogue._VALUE_FRAME, _CLOCK_HOUR, _PART_OF_DAY_FIRST, Followup.value, corrected_request.

Every list holds fresh phrasings (Spanish dialects, English, Spanglish); none is a literal of the tanda.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import dialogue, levels

OPERATIONS = (
    "audio.volume", "audio.volume.adjust", "audio.mute", "system.settings.set", "system.settings.adjust",
    "media.control", "media.play.query", "media.play.youtube", "media.status", "weather.current", "web.search",
    "web.news.headlines", "app.open", "app.close", "notification.schedule", "notification.cancel.latest",
    "notification.cancel.at", "notification.list", "reminder.create", "reminder.list", "system.time", "task.create",
    "task.search",
)


class _Scripted:
    """A model that writes the rewrite a good model would; a missing text means it must not be asked."""

    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self.answers = answers or {}
        self.seen: list[dict] = []

    def rewrite_in_context(self, text, context, **kwargs):
        self.seen.append({"text": text, "context": list(context), **kwargs})
        if text not in self.answers:
            raise AssertionError(f"the model is not asked about {text!r}")
        return self.answers[text]


def _message(*turns: str) -> dict:
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": turn} for index, turn in enumerate(turns)
    ]
    return {"id": "tanda-09", "text": turns[-1], "history": history}


def _rearm(message: dict, model: _Scripted, state: dialogue.DialogueState | None = None):
    return sidecar._rearm_in_context(message, llm=model, available_operations=OPERATIONS, dialogue_state=state)


def _verified(operation: str, observed: dict | None = None) -> dict:
    return {"kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
            "observed": observed or {}}


def _state(request: str, operation: str) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(request, [operation])
    state.record(_verified(operation))
    return state


def _dependency(before: tuple[str, ...], text: str) -> str | None:
    message = _message(*before, text)
    return dialogue.dependency(text, dialogue.read_slot(message, message["history"], text))


_WEATHER = ("¿cómo está el clima en Rosario?", "En Rosario hay 18 °C y está despejado.")


# ---------------------------------------------------------------- 1. a word that only ends like a clitic


@pytest.mark.parametrize(
    "text",
    [
        "cómo se preparan unos tamales",  # a plural noun in -les
        "qué canales internacionales dan fútbol hoy",  # an adjective in -les
        "dime las noticias locales",
        "hey baxy cancela la alarma de las 7",  # an order that ends in -la is the order itself
        "cancela recordatorios",
        "pon música con canela de fondo",  # a noun in -ela
        "háblame de la escuela de mi abuela",
    ],
)
def test_a_noun_or_an_order_that_only_ends_like_a_clitic_is_read_on_its_own(text):
    assert _dependency(_WEATHER, text) is None
    # Nothing is sent to the model: a complete request never inherits the place before it.
    assert _rearm(_message(*_WEATHER, text), _Scripted()) is None


@pytest.mark.parametrize(
    "text",
    [
        "cerralo",  # an order the readers know, with its pronoun
        "y apagalo ya",
        "pausala",
        "ok compartilo en mi instagram",  # a verb no reader knows, first in its clause
        "podés guardarlo",  # an infinitive with its clitic
        "bájale un poquito",  # an amount is not the dative's object
        "subile un toque",
    ],
)
def test_a_verb_with_its_pronoun_still_leans_on_the_turn_before(text):
    assert _dependency(("abrí el reproductor", "Listo, el reproductor está abierto."), text) == "reference"


@pytest.mark.parametrize("text", ["mandale un mensaje", "devolvele el sonido", "pasale la foto"])
def test_a_dative_with_its_object_said_stands_on_its_own(text):
    assert _dependency(("abrí el chat", "Listo."), text) is None


# ---------------------------------------------------------------- 2. a complete question never inherits


_TOPIC = ("explícame qué es el patrón observer", "El patrón Observer define una dependencia uno a muchos…")


@pytest.mark.parametrize(
    "text",
    [
        "¿en qué ciudad te crearon?",
        "¿desde cuándo existes?",
        "¿con quién hablo?",
        "¿en qué año naciste?",
        "in which country were you built?",
        "¿por qué te llamas así?",
    ],
)
def test_a_question_after_a_preposition_is_its_own_question(text):
    assert _dependency(_TOPIC, text) is None
    assert _rearm(_message(*_TOPIC, text), _Scripted()) is None


@pytest.mark.parametrize(("text", "dependency"), [("no, por telegram mejor", "destination"), ("¿y en Cusco?", "destination")])
def test_a_new_destination_or_place_still_continues(text, dependency):
    assert _dependency(("mandá el resumen por mail", "Listo, lo mandé por mail."), text) == dependency


# ---------------------------------------------------------------- 3. an order on what just played


_PLAYED = ("ponme el último tema de Duki en youtube", "Está sonando «Rockstar» de Duki en YouTube.")


@pytest.mark.parametrize(
    "text",
    ["pausalo", "pausámelo un ratito", "dale, pausalo un toque", "stop it", "pause it for a sec", "pausa un momento"],
)
def test_pausing_what_just_played_needs_no_model(text):
    state = _state(_PLAYED[0], "media.play.youtube")
    result = _rearm(_message(*_PLAYED, text), _Scripted(), state)
    assert result is not None and result[1] == "pattern"
    assert set(sidecar.resolve_explicit_effects(result[0], OPERATIONS).operations) == {"media.control"}


@pytest.mark.parametrize("text", ["ok, seguí", "dale, seguilo", "resume it", "sigue", "continuá porfa"])
def test_resuming_what_was_paused_needs_no_model(text):
    state = _state("pausa la canción", "media.control")
    result = _rearm(_message("pausa la canción", "Listo, la pausé.", text), _Scripted(), state)
    assert result is not None and result[1] == "pattern"
    assert set(sidecar.resolve_explicit_effects(result[0], OPERATIONS).operations) == {"media.control"}


def test_an_order_left_without_object_after_something_else_is_not_about_music():
    state = _state("¿qué hora es en Lima?", "system.time")
    # Nothing played: the song is not what «pausalo» points at, and the model is asked instead.
    model = _Scripted({"pausalo": "pausalo"})
    assert _rearm(_message("¿qué hora es en Lima?", "En Lima son las 10:20.", "pausalo"), model, state) is None
    assert model.seen


@pytest.mark.parametrize("text", ["sigue lloviendo en Lima?", "pausa Spotify", "resume the download"])
def test_an_order_that_says_its_object_is_not_a_bare_order(text):
    assert _dependency(_PLAYED, text) != "reference"


# ---------------------------------------------------------------- 4. an order said with its reason


@pytest.mark.parametrize(
    ("text", "direction", "target"),
    [
        ("bajale un toque que está re fuerte", "down", None),
        ("súbele porque no se escucha nada", "up", None),
        ("turn it down it's way too loud", "down", None),
        ("baja el volumen que me duele la cabeza", "down", None),
        ("pon el volumen al 30 que están durmiendo", None, 30),
    ],
)
def test_an_order_said_with_why_is_the_order(text, direction, target):
    level = levels.read(text)
    assert level is not None and level.direction == direction and level.target == target
    asked = sidecar.resolve_explicit_clarification_intent(text, OPERATIONS)
    if target is None:
        # A relative change without an amount asks how much; it never takes a default step.
        assert asked is not None and asked.operations == ("audio.volume.adjust",) and asked.missing_fields == ("amount",)


@pytest.mark.parametrize("text", ["baja que está lloviendo", "sube a ver que pasa", "la música que suena es de Duki"])
def test_a_reason_never_makes_a_level_of_what_is_not_one(text):
    assert levels.read(text) is None


def test_lowering_what_plays_with_its_reason_is_the_volume_question():
    state = _state(_PLAYED[0], "media.play.youtube")
    # Read as it arrived: the level readers ask how much.
    assert _rearm(_message(*_PLAYED, "bajale un poco que está a full"), _Scripted(), state) is None


# ---------------------------------------------------------------- 5. once more


@pytest.mark.parametrize(
    ("said", "operation", "text"),
    [
        ("bajá el volumen en 10", "audio.volume.adjust", "más"),
        ("turn the volume up by 20", "audio.volume.adjust", "a bit more"),
        ("salta la canción", "media.control", "otra vez"),
        ("sube el brillo en 15", "system.settings.adjust", "un poco más"),
    ],
)
def test_once_more_is_the_last_request_again(said, operation, text):
    state = _state(said, operation)
    assert _rearm(_message(said, "Listo.", text), _Scripted(), state) == (said, "pattern")


def test_asking_for_more_of_an_answer_is_not_the_request_again():
    state = _state("¿va a llover hoy en Quito?", "weather.current")
    model = _Scripted({"¿y más?": "¿y más?"})
    assert _rearm(_message("¿va a llover hoy en Quito?", "No, hoy no llueve en Quito.", "¿y más?"), model, state) is None
    assert model.seen  # the model decides; the weather read is not repeated by pattern


def test_a_bit_more_is_not_a_destination():
    assert _dependency(("turn the volume up by 20", "Done."), "a bit more") == "followup"


# ---------------------------------------------------------------- 6. a value BAXY just gave


@pytest.mark.parametrize(
    ("asked", "answer", "text", "rewrite"),
    [
        ("cuánto se cocina el arroz blanco", "El arroz blanco se cocina unos 18 minutos a fuego bajo.",
         "pon un temporizador de ese tiempo", "pon un temporizador de 18 minutos"),
        ("how long should I steep green tea", "Green tea steeps best for 3 minutes.",
         "set a timer for that long", "set a timer for 3 minutes"),
        ("qué volumen es cómodo para leer", "Para leer con música, un 25 % suele ir bien.",
         "deja el volumen en ese nivel", "deja el volumen en 25 %"),
    ],
)
def test_a_value_pointed_at_is_the_one_baxy_just_gave(asked, answer, text, rewrite):
    state = dialogue.DialogueState()
    state.expect(asked, [])  # answered in conversation: no operation to continue
    assert _rearm(_message(asked, answer, text), _Scripted(), state) == (rewrite, "pattern")


@pytest.mark.parametrize(
    "answer",
    [
        "Entre 8 y 10 minutos, hasta que cambien de color.",  # a range names no one value
        "Unos 8 minutos si son chicos, 12 si son grandes.",  # two values
        "Hasta que se ablanden.",  # none
    ],
)
def test_without_one_value_the_model_decides(answer):
    text = "ponme un timer de ese tiempo"
    model = _Scripted({text: text})
    assert _rearm(_message("cuánto hiervo los tomatillos", answer, text), model, dialogue.DialogueState()) is None
    assert model.seen and model.seen[0]["shape"] == "pointer"


def test_a_rewrite_that_reads_what_the_message_itself_asks_for_is_kept():
    # The last turn was talk (no operation); the timer is the person's own order, completed by the model.
    text, rewrite = "ponme un timer de ese tiempo", "ponme un timer de 30 minutos"
    result = _rearm(
        _message("cuánto hiervo los tomatillos", "Entre 25 y 30 minutos.", text), _Scripted({text: rewrite}),
        dialogue.DialogueState(),
    )
    assert result == (rewrite, "model")


# ---------------------------------------------------------------- 7. a day said in the other language


@pytest.mark.parametrize(
    ("turns", "rewrite", "stays"),
    [
        (("¿llueve hoy en Lima?", "No, hoy no llueve en Lima.", "and is it windy?"), "is it windy in Lima today", True),
        (("what's the weather like", "It's 20 °C in Lima.", "y el tmrw?"), "¿y mañana en Lima?", True),
        (("clima del sábado", "El sábado habrá sol.", "y el sunday?"), "¿y el domingo?", True),
        # Into a language that is not the message's, the day is still a word the model brought (tanda 7).
        (("clima del sábado", "El sábado habrá sol.", "and on sunday?"), "¿y el domingo?", False),
        # A day nobody said in any language is still a word the model brought.
        (("¿llueve hoy en Lima?", "No, hoy no llueve en Lima.", "and is it windy?"), "is it windy in Lima on friday", False),
    ],
)
def test_a_day_said_in_the_other_language_is_the_same_word(turns, rewrite, stays):
    message = _message(*turns)
    slot = dialogue.read_slot(message, message["history"], turns[-1])
    assert dialogue.rewrite_stays_in_context(rewrite, turns[-1], slot) is stays


# ---------------------------------------------------------------- 8. the weather asked with the day first


@pytest.mark.parametrize(
    "text",
    [
        "y el finde va a hacer frío?",
        "pasado mañana va a llover en Cusco?",
        "and tomorrow, will it be colder?",
        "is it muggy out there?",
        "will it be warmer this weekend?",
        "y esta noche va a hacer más frío?",
    ],
)
def test_the_weather_with_the_day_first_or_how_it_feels_is_the_weather_read(text):
    assert sidecar.resolve_explicit_effects(text, OPERATIONS).operations == ("weather.current",)


@pytest.mark.parametrize(
    "text", ["y mañana qué hago", "mañana abre el museo?", "and tomorrow what time is the game"],
)
def test_a_day_first_does_not_make_the_weather_of_what_is_not(text):
    found = sidecar.resolve_explicit_effects(text, OPERATIONS)
    assert found is None or "weather.current" not in found.operations


# ---------------------------------------------------------------- 9. a value said with a copula


@pytest.mark.parametrize("text", ["It'll be at 6:10 am.", "it should be 7 pm", "que sea a las 9 y media", "5:20"])
def test_a_value_after_baxys_question_answers_it(text):
    turns = ("can you list my alarms?", "You have two alarms.", "sure, go ahead", "What would you like me to do?")
    message = _message(*turns, text)
    slot = dialogue.read_slot(message, message["history"], text)
    assert dialogue.dependency(text, slot) == "answer"


@pytest.mark.parametrize(
    ("said", "text", "rewrite"),
    [
        ("set an alarm for 6:30 am", "no, it should be morning 6:50", "cancel the last alarm and set an alarm at 6:50 am"),
        ("set an alarm at 7 am", "actually 7:15", "cancel the last alarm and set an alarm at 7:15 am"),
        ("ponme una alarma a las 8 de la mañana", "no, que sea a las 8 y media",
         "cancela la última alarma y ponme una alarma a las 8 y media de la mañana"),
        ("pon una alarma a las 5", "mejor por la tarde 5:40", "cancela la última alarma y pon una alarma a las 5:40 de la tarde"),
    ],
)
def test_a_correction_of_the_alarm_just_set_replaces_it_with_the_value_said(said, text, rewrite):
    state = dialogue.DialogueState()
    state.expect(said, ["notification.schedule"])
    state.record(_verified("notification.schedule", {"kind": "alarm", "title": said}))
    assert _rearm(_message(said, "Listo.", text), _Scripted(), state) == (rewrite, "pattern")


@pytest.mark.parametrize("text", ["for 9", "at 7"])
def test_a_number_without_a_clock_form_stays_an_amount(text):
    assert dialogue.shape(text, "followup") == "amount"
