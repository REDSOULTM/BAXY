"""Uso real tanda 8 (2026-09-25, official window): the follow-up sees what a person would.

The contextual rewrite of 9ccfafd3 passed a replay that simulated the dialogue state and barely worked live (first
pass 53 %): the turns audit showed the rewrite firing and the model keeping «y eso por 12?», «40 percent», «is the
entrance free», and good rewrites rejected. One owner per rule:

1. The last turn is the frame. The state followed only verified turns, so after an answer, a question or a failure
   its «last request» was an older one: «y eso por 12?» after a number computed in conversation was told to change
   «ábreme la calculadora», and «no, mejor a las 6:15» (a correction of the alarm still being asked for) was judged
   against the clock read two turns before and rejected. Every turn's decided request is now the last one, with the
   operations it was about; what a verified result says is kept per kind as before. Owner:
   semantic/dialogue.DialogueState (fed by the serve loop), __main__._rearm_in_context (the continued operations).
2. A question BAXY asked belongs to the request before it even when the shell holds none (a recovered question):
   a yes or a value after it is an answer to that request («40 percent»). Owner: semantic/dialogue.read_slot.
3. Talk is the whole message: «ah, y tomates» starts with an interjection and adds to the list. Owner:
   semantic/dialogue._SOCIAL.
4. A question about what the person holds with no object («¿qué llevo ya?», «what have I got so far?») leans on the
   turn before. Owner: semantic/dialogue._OWN_LISTING.

Every list holds fresh phrasings (Spanish dialects, English, Spanglish); none is a literal of the tanda.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import dialogue

OPERATIONS = (
    "audio.volume", "audio.volume.adjust", "audio.mute", "system.settings.set", "system.settings.adjust",
    "media.control", "media.play.query", "media.status", "weather.current", "web.search", "app.open",
    "notification.schedule", "notification.cancel.latest", "notification.list", "reminder.create", "reminder.list",
    "system.time", "task.create", "task.search",
)


class _Scripted:
    """A model that writes the rewrite a good model would, and records what it was shown."""

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.seen: list[dict] = []

    def rewrite_in_context(self, text, context, *, dependency="", verified=(), **_kwargs):
        self.seen.append({"text": text, "context": list(context), "dependency": dependency, "verified": list(verified)})
        if text not in self.answers:
            raise AssertionError(f"the model is not asked about {text!r}")
        return self.answers[text]


def _message(*turns: str) -> dict:
    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": turn} for index, turn in enumerate(turns)
    ]
    return {"id": "tanda-08", "text": turns[-1], "history": history}


def _rearm(message: dict, model: _Scripted, state: dialogue.DialogueState | None):
    return sidecar._rearm_in_context(message, llm=model, available_operations=OPERATIONS, dialogue_state=state)


def _verified(operation: str, observed: dict | None = None) -> dict:
    return {"kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
            "observed": observed}


# ---------------------------------------------------------------- 1. the last turn is the frame


def test_every_turn_is_the_last_request_and_only_verified_results_are_facts():
    state = dialogue.DialogueState()
    state.expect("ábreme el bloc de notas", ["app.open"])
    state.record(_verified("app.open", {"name": "Bloc de notas"}))
    assert state.request == "ábreme el bloc de notas" and state.operations == ("app.open",)
    assert any("ábreme el bloc de notas" in line for _, line in state.lines())
    state.expect("oye cuánto da 1200 entre 8", [])  # answered in conversation
    assert state.request == "oye cuánto da 1200 entre 8"
    assert state.operations == () and state.intended == ()
    # The request done two turns before is no longer «the last request done».
    assert not any("bloc de notas" in line for _, line in state.lines())
    assert state.families == {"app"}


@pytest.mark.parametrize(
    ("asked", "answer", "text", "rewrite"),
    [
        ("oye cuánto da 1200 entre 8", "1200 entre 8 da 150.", "¿y eso por 3?", "cuánto da 150 por 3"),
        ("how much is 64 times 3", "64 times 3 is 192.", "and half of that?", "how much is half of 192"),
        ("wey cuánto es el 15 % de 380", "El 15 % de 380 es 57.", "y eso más 20?", "cuánto es 57 más 20"),
    ],
)
def test_a_number_computed_in_conversation_is_what_the_follow_up_continues(asked, answer, text, rewrite):
    state = dialogue.DialogueState()
    state.expect("pon la calculadora", ["app.open"])
    state.record(_verified("app.open"))
    state.expect(asked, [])
    model = _Scripted({text: rewrite})
    assert _rearm(_message(asked, answer, text), model, state) == (rewrite, "model")
    # The model saw the answer, not the older request as the one to change.
    assert ("BAXY", answer) in model.seen[0]["context"]
    assert not any("calculadora" in line for _, line in model.seen[0]["verified"])


@pytest.mark.parametrize(
    ("said", "question", "text", "rewrite"),
    [
        ("ponme una alarma a las 7 pa mañana", "¿A las 7 de la mañana o de la tarde?", "no, mejor a las 7:20",
         "ponme una alarma a las 7:20 pa mañana"),
        ("set an alarm for 5 tomorrow", "5 in the morning or in the afternoon?", "actually, make it 5:40",
         "set an alarm for 5:40 tomorrow"),
    ],
)
def test_a_correction_of_the_alarm_still_asked_for_completes_it_and_replaces_nothing(said, question, text, rewrite):
    state = dialogue.DialogueState()
    state.expect("qué hora es en Lima", ["system.time"])
    state.record(_verified("system.time", {"location": "Lima"}))
    state.expect(said, ["notification.schedule"])  # the turn asked; nothing was set
    result = _rearm(_message(said, question, text), _Scripted({text: rewrite}), state)
    assert result == (rewrite, "model")
    assert state.cancel_last_alarm(True) is None


def test_a_correction_of_the_alarm_just_set_still_replaces_it():
    request = "pon una alarma a las 6 de la mañana"
    state = dialogue.DialogueState()
    state.expect(request, ["notification.schedule"])
    state.record(_verified("notification.schedule", {"kind": "alarm", "title": request}))
    text, rewrite = "no, a las 6 y cuarto", "pon una alarma a las 6 y cuarto de la mañana"
    result = _rearm(_message(request, "Listo, suena a las 6:00.", text), _Scripted({text: rewrite}), state)
    assert result == ("cancela la última alarma y " + rewrite, "model")


def test_an_alarm_set_turns_ago_is_not_what_a_correction_replaces():
    state = dialogue.DialogueState()
    state.expect("pon una alarma a las 6 de la mañana", ["notification.schedule"])
    state.record(_verified("notification.schedule", {"kind": "alarm", "title": "alarma"}))
    state.expect("¿llueve hoy?", ["weather.current"])
    state.record(_verified("weather.current", {"location": "Quito"}))
    assert state.cancel_last_alarm(True) is None


# ---------------------------------------------------------------- 2. a question BAXY asked


@pytest.mark.parametrize(
    ("said", "question", "text", "rewrite"),
    [
        ("the monitor is way too bright", "What brightness level do you want?", "70 percent",
         "set the monitor brightness to 70 percent"),
        ("la pantalla está re oscura", "¿A qué nivel de brillo la pongo?", "al 70", "pon el brillo de la pantalla al 70"),
    ],
)
def test_a_value_after_a_question_of_baxy_answers_the_request_before_it(said, question, text, rewrite):
    message = _message(said, question, text)  # the shell holds no request: the question was a recovered one
    slot = dialogue.read_slot(message, message["history"], text)
    assert slot.pending_request == said and not slot.held
    assert dialogue.dependency(text, slot) == "answer"
    assert _rearm(message, _Scripted({text: rewrite}), dialogue.DialogueState()) == (rewrite, "model")


@pytest.mark.parametrize(
    ("rewrite", "stays"),
    [
        ("set the monitor brightness to 70 percent", True),  # «set» frames it; every thing named was said
        ("pon el brillo del monitor al 70 por ciento", False),  # «brillo» nobody said
        ("set the volume to 70 percent", False),  # another object
        ("turn off the monitor", False),  # another action: «off» nobody said
    ],
)
def test_the_frame_of_a_request_is_free_and_every_thing_it_names_was_said(rewrite, stays):
    message = _message("the monitor is way too bright", "What level do you want?", "70 percent")
    slot = dialogue.read_slot(message, message["history"], "70 percent")
    assert dialogue.rewrite_stays_in_context(rewrite, "70 percent", slot) is stays


@pytest.mark.parametrize("text", ["abre la calculadora", "pon música de Queen", "what's the weather in Oslo"])
def test_a_complete_request_after_a_question_of_baxy_is_not_an_answer(text):
    message = _message("la pantalla está re oscura", "¿A qué nivel de brillo la pongo?", text)
    assert dialogue.dependency(text, dialogue.read_slot(message, message["history"], text)) != "answer"


def test_a_question_the_shell_holds_is_still_answered_by_a_short_message():
    message = {**_message("anota en la lista del súper", "¿Qué anoto?", "pan y queso"),
               "pendingObjective": "anota en la lista del súper"}
    slot = dialogue.read_slot(message, message["history"], "pan y queso")
    assert slot.held and dialogue.dependency("pan y queso", slot) == "answer"


# ---------------------------------------------------------------- 3. talk is the whole message


@pytest.mark.parametrize("text", ["oh, y también cebollas", "ah y dos kilos de papas", "ah, y también unas manzanas"])
def test_an_interjection_before_a_request_is_not_talk(text):
    slot = dialogue.DialogueSlot(None, None, ("apunta en la lista del súper arroz",), "Anotado.")
    assert dialogue.dependency(text, slot) is not None


@pytest.mark.parametrize(
    "text", ["jaja qué bueno", "ok great", "no, that's all, thanks", "genial, muchas gracias baxy", "ah"],
)
def test_thanks_reactions_and_closings_are_still_talk(text):
    slot = dialogue.DialogueSlot(None, None, ("apunta en la lista del súper arroz",), "Anotado.")
    assert dialogue.dependency(text, slot) is None


# ---------------------------------------------------------------- 4. what the person holds, with no object


@pytest.mark.parametrize(
    "text", ["¿qué tengo ya?", "¿y qué me falta?", "what have I got so far?", "qué llevamos hasta ahora", "cuántos llevo"],
)
def test_a_question_about_what_the_person_holds_leans_on_the_turn_before(text):
    assert dialogue.leans_on_context(text)


@pytest.mark.parametrize("text", ["qué hora es", "what do I have to do today to renew my passport", "qué tengo que llevar a la playa"])
def test_a_question_with_its_own_object_does_not(text):
    assert not dialogue.leans_on_context(text)
