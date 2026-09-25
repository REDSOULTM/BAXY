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
