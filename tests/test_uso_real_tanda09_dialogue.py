"""Uso real tanda 9 (2026-09-25, official window, first pass): the follow-up shapes the dialogue slot had not met.

One owner per rule:

1. A noun or an adjective that ends like a verb with its pronoun («…les», «…la») is not one: a complete request
   was sent to the rewrite and came back with a place of two turns before. A verb with its clitic is an infinitive
   or a gerund, an order the readers know with the clitic removed, or a word first in its clause. Owner:
   semantic/dialogue._object_pronoun.
2. A question word after the preposition asks a question of its own («¿en qué lugar te…?»): a complete question
   about BAXY was read as a new destination for the topic before and answered about that topic. Owner:
   semantic/dialogue._NOT_ASKED in _DESTINATION_ONLY and _PLACE_FRAGMENT.

Every list holds fresh phrasings (Spanish dialects, English, Spanglish); none is a literal of the tanda.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import dialogue

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
