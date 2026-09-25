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
5. The rewrite is shown worked conversations, one per shape, as turns of the same form as the real input (with only
   rules the 4B model returned the message unchanged), and no hint names a thing of one conversation (the old
   follow-up hint's «goleador del partido» came back in a Lakers rewrite). Owner: llm.rewrite_in_context,
   llm._REWRITE_EXAMPLES.

Every list holds fresh phrasings (Spanish dialects, English, Spanglish); none is a literal of the tanda.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
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
    # An hour said with «a las» is put in place of the one asked about without the model; «make it 5:40» is the
    # model's. Either way nothing is cancelled.
    assert result in {(rewrite, "model"), (rewrite, "pattern")}
    assert state.cancel_last_alarm(True) is None


def test_a_correction_of_the_alarm_just_set_still_replaces_it():
    request = "pon una alarma a las 6 de la mañana"
    state = dialogue.DialogueState()
    state.expect(request, ["notification.schedule"])
    state.record(_verified("notification.schedule", {"kind": "alarm", "title": request}))
    text, rewrite = "no, a las 6 y cuarto", "pon una alarma a las 6 y cuarto de la mañana"
    result = _rearm(_message(request, "Listo, suena a las 6:00.", text), _Scripted({}), state)
    assert result == ("cancela la última alarma y " + rewrite, "pattern")


def test_an_alarm_set_turns_ago_is_not_what_a_correction_replaces():
    state = dialogue.DialogueState()
    state.expect("pon una alarma a las 6 de la mañana", ["notification.schedule"])
    state.record(_verified("notification.schedule", {"kind": "alarm", "title": "alarma"}))
    state.expect("¿llueve hoy?", ["weather.current"])
    state.record(_verified("weather.current", {"location": "Quito"}))
    assert state.cancel_last_alarm(True) is None


def test_the_rewrite_sees_the_last_exchanges_as_the_person_saw_them():
    turns = (
        "anota en la lista del súper yerba y galletas", "Anoté yerba y galletas en la lista del súper.",
        "¿y qué más había?", "En la lista del súper hay yerba, galletas y fideos.",
        "saca los fideos", "Listo, saqué los fideos.",
        "dale, léemela de nuevo",
    )
    message = _message(*turns)
    slot = dialogue.read_slot(message, message["history"], turns[-1])
    assert slot.context_lines() == [
        ("persona" if index % 2 == 0 else "BAXY", turn) for index, turn in enumerate(turns[:-1])
    ]
    # The list named three exchanges back is a word said; a list nobody named is not.
    assert dialogue.rewrite_stays_in_context("léeme la lista del súper de nuevo", turns[-1], slot)
    assert not dialogue.rewrite_stays_in_context("léeme la lista de tareas de nuevo", turns[-1], slot)


# ---------------------------------------------------------------- 2. a question BAXY asked


@pytest.mark.parametrize(
    ("said", "question", "text", "rewrite"),
    [
        # Integration with the tanda-8 vocabulary fix: a brightness complaint is now read, so BAXY asks the amount
        # after it and the level reader joins the answer deterministically (no model call); the request before the
        # question is still what the value completes.
        ("the monitor is way too bright", "How much darker should I make it?", "70 percent", "baja el brillo en 70"),
        ("la pantalla está re oscura", "¿A qué nivel de brillo la pongo?", "al 70", "pon el brillo al 70"),
    ],
)
def test_a_value_after_a_question_of_baxy_answers_the_request_before_it(said, question, text, rewrite):
    message = _message(said, question, text)  # the shell holds no request: the question was a recovered one
    slot = dialogue.read_slot(message, message["history"], text)
    assert slot.pending_request == said and not slot.held
    assert dialogue.dependency(text, slot) == "answer"
    assert _rearm(message, _Scripted({text: rewrite}), dialogue.DialogueState()) in {(rewrite, "model"), (rewrite, "pattern")}


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


# ---------------------------------------------------------------- 5. the rewrite is shown worked conversations


def _rewrite_payload(text: str, context: list[tuple[str, str]], verified: list[tuple[str, str]]) -> dict:
    runtime = object.__new__(llm.LlmRuntime)
    seen: list[dict] = []

    def post(payload: dict, **_kwargs: object) -> dict:
        seen.append(payload)
        return {"choices": [{"message": {"content": json.dumps({"request": "cuánto da 150 por 3"})}}]}

    runtime._post = post  # type: ignore[method-assign]
    assert runtime.rewrite_in_context(text, context, dependency="followup", verified=verified) == "cuánto da 150 por 3"
    return seen[0]


def test_the_rewrite_is_shown_worked_conversations_before_the_real_one():
    context = [("persona", "oye cuánto da 1200 entre 8"), ("BAXY", "1200 entre 8 da 150.")]
    messages = _rewrite_payload("¿y eso por 3?", context, [("verificado", "lugar (place): Quito")])["messages"]
    examples = [message for message in messages[1:-1] if message["role"] in {"user", "assistant"}]
    assert len(examples) == 2 * len(llm._REWRITE_EXAMPLES)
    assert all(json.loads(answer["content"])["request"] for answer in examples[1::2])
    real = messages[-1]
    assert real["role"] == "user"
    assert real["content"] == (
        "Lo verificado en esta conversación:\n- lugar (place): Quito\n\nConversación:\npersona: oye cuánto da 1200 "
        "entre 8\nBAXY: 1200 entre 8 da 150.\n\nÚltimo mensaje: ¿y eso por 3?"
    )
    # The example turns have the real input's form.
    assert all(
        "Conversación:\npersona: " in example["content"] and "\n\nÚltimo mensaje: " in example["content"]
        for example in examples[0::2]
    )


@pytest.mark.parametrize("example", llm._REWRITE_EXAMPLES, ids=lambda example: example[2])
def test_every_worked_example_keeps_the_rule_it_teaches(example):
    verified, context, text, rewrite = example
    slot = dialogue.DialogueSlot(None, None, tuple(line for speaker, line in reversed(context) if speaker == "persona"),
                                 next((line for speaker, line in reversed(context) if speaker == "BAXY"), None))
    assert dialogue.leans_on_context(text) or dialogue.dependency(text, slot) is not None
    assert dialogue.differs(rewrite, text)
    assert dialogue.rewrite_stays_in_context(rewrite, text, slot, [("verificado", line) for line in verified])


_CANCEL_LATEST_SCHEMA = {
    "type": "object",
    "properties": {"kind": {"type": "string", "enum": ["alarm", "reminder"]}},
    "required": ["kind"],
    "additionalProperties": False,
}


@pytest.mark.parametrize(
    ("clause", "kind"),
    [
        ("cancel the last timer", "alarm"),  # tanda 7b: the step of «actually make it 9»
        ("cancela el último temporizador", "alarm"),
        ("quita el último timer", "alarm"),
        ("cancela la última alarma", "alarm"),
        ("borra el último recordatorio", "reminder"),
    ],
)
def test_the_kind_of_the_last_one_cancelled_is_read_from_its_name(clause, kind):
    # A timer is a scheduled alarm; the plan's cancel step no longer asks which kind it is.
    assert sidecar._ground_explicit_arguments("notification.cancel.latest", clause, _CANCEL_LATEST_SCHEMA) == {
        "kind": kind,
    }


def test_the_last_of_two_kinds_named_is_still_asked():
    assert sidecar._ground_explicit_arguments(
        "notification.cancel.latest", "cancela el último temporizador o recordatorio", _CANCEL_LATEST_SCHEMA,
    ) is None


_SEEN = {
    "location": "Valdivia", "country": "Chile", "temperatureC": 9.4, "condition": "nublado",
    "today": {"date": "2026-10-02", "weekday": "viernes", "maxC": 14, "minC": 6, "rainProbabilityPercent": 20},
    "tomorrow": {"date": "2026-10-03", "weekday": "sábado", "maxC": 13, "minC": 5.5, "rainProbabilityPercent": 70,
                 "condition": "lluvia"},
    "laterDays": [{"date": "2026-10-04", "weekday": "domingo", "condition": "chubascos", "maxC": 12, "minC": 6,
                   "rainProbabilityPercent": 85}],
}


def test_a_result_of_the_turn_answers_the_request_as_the_turn_understood_it():
    state = dialogue.DialogueState()
    state.expect("oye, ¿va a llover el fin de semana en Valdivia?", ["weather.current"])  # «¿y el fin de semana?»
    weather = _verified("weather.current", _SEEN)
    assert state.understood("¿y el fin de semana?", weather) == "oye, ¿va a llover el fin de semana en Valdivia?"
    # A notice, another operation's result or a joined answer keeps the person's text.
    assert state.understood("¿y el fin de semana?", {"kind": "status", "cause": "acting"}) == "¿y el fin de semana?"
    assert state.understood("¿y el fin de semana?", _verified("media.status")) == "¿y el fin de semana?"
    state.expect("pon una alarma\nAclaración confiable del usuario: a las 7", ["notification.schedule"])
    assert state.understood("a las 7", _verified("notification.schedule")) == "a las 7"


def test_the_weekend_answer_passes_against_the_understood_request_and_not_the_fragment():
    payload = {"operation": "weather.current", "seen": _SEEN}
    draft = "El fin de semana llueve: 70 % el sábado y 85 % el domingo."
    assert llm._weather_fact_defect(draft, payload, "oye, ¿va a llover el fin de semana?") == ""
    assert llm._weather_fact_defect(draft, payload, "¿y el fin de semana?") == "missing_state"


@pytest.mark.parametrize(
    ("text", "reads"),
    [
        ("what alarms, timers and reminders do I have set right now?", ("notification.list", "reminder.list")),
        ("qué alarmas y recordatorios tengo programados", ("notification.list", "reminder.list")),
        ("cuáles temporizadores tengo puestos ahora mismo", ("notification.list",)),
        ("do I have any timers or reminders set for tomorrow", ("notification.list", "reminder.list")),
        ("¿hay recordatorios pendientes pa hoy?", ("reminder.list",)),
        ("which reminders have I got", ("reminder.list",)),
    ],
)
def test_what_is_set_is_read_back_by_the_kinds_named(text, reads):
    from baxy_mind.semantic.notes import reminder_inventory_question
    from baxy_mind.semantic.reading import read

    assert reminder_inventory_question(text) == reads
    assert read(text, available_operations=OPERATIONS).effects.operations == reads


@pytest.mark.parametrize("text", ["set an alarm and a reminder for 8", "qué alarma me recomiendas", "borra mis alarmas"])
def test_other_requests_about_alarms_are_not_the_listing(text):
    from baxy_mind.semantic.notes import reminder_inventory_question

    assert reminder_inventory_question(text) == ()


def test_what_is_set_after_a_timer_and_a_reminder_is_read_back_in_context():
    from baxy_mind.semantic.notes import reminder_inventory_question

    state = dialogue.DialogueState()
    state.expect("pon un temporizador de 20 minutos para el pan", ["notification.schedule"])
    state.record(_verified("notification.schedule", {"kind": "alarm", "title": "pan"}))
    state.expect("recuérdame a las 9 regar las plantas", ["reminder.create"])
    state.record(_verified("reminder.create", {"title": "regar las plantas"}))
    text = "¿y qué tengo puesto ahora?"
    message = _message("recuérdame a las 9 regar las plantas", "Listo, te aviso a las 9.", text)
    rearmed = _rearm(message, _Scripted({}), state)  # the kinds set are named without the model (tanda 7b replay)
    assert rearmed == ("qué alarmas, temporizadores y recordatorios tengo puesto ahora", "pattern")
    assert reminder_inventory_question(rearmed[0]) == ("notification.list", "reminder.list")


@pytest.mark.parametrize(
    ("text", "entry", "listed"),
    [
        ("apúntame en la lista del súper arroz, aceite y yerba", "arroz, aceite y yerba", "lista del súper"),
        ("anota en mi lista de compras dos kilos de papas", "dos kilos de papas", "lista de compras"),
        ("pon en la lista de tareas: llamar al plomero", "llamar al plomero", "lista de tareas"),
        ("add to my grocery list eggs and bread", "eggs and bread", "grocery list"),
    ],
)
def test_an_entry_said_after_the_list_is_the_same_entry(text, entry, listed):
    from baxy_mind.semantic.notes import list_entry_request
    from baxy_mind.semantic.reading import read

    assert list_entry_request(text) == (entry, listed)
    assert read(text, available_operations=OPERATIONS).effects.operations == ("task.create",)


@pytest.mark.parametrize(
    "text", ["pon en la lista de reproducción esta canción", "apunta en una nota la receta de la abuela",
             "anota en la lista esto"],
)
def test_a_playlist_a_note_or_a_pointed_entry_is_not_a_list_entry(text):
    from baxy_mind.semantic.notes import list_entry_request

    assert list_entry_request(text) is None


@pytest.mark.parametrize(
    "text",
    ["¿qué llevo ya en la lista de la compra?", "¿qué tengo ya en la lista del súper?", "lee la lista del mercado",
     "qué hay hasta ahora en la lista de compras"],
)
def test_what_a_list_holds_so_far_is_a_read_of_it(text):
    from baxy_mind.semantic.reading import read

    assert read(text, available_operations=(*OPERATIONS, "task.list")).effects.operations == ("task.search",)


_RECALL_HISTORY = [
    {"role": "user", "content": "baja el brillo a 30"},
    {"role": "assistant", "content": "El brillo está en 30."},
]


@pytest.mark.parametrize(
    "text",
    [
        "por favor, ¿me puedes repetir lo que te he dicho?",
        "¿me repites lo mismo que te dije?",
        "podrías decirme lo que te había dicho",
        "can you repeat what I've said?",
        "say back the same thing I said",
    ],
)
def test_what_the_person_already_said_is_said_back_in_any_tense(text):
    history = [*_RECALL_HISTORY, {"role": "user", "content": text}]
    assert llm._recalled_speaker(text) == "user"
    assert llm._literal_recall_reference(history, text) == "baja el brillo a 30"


@pytest.mark.parametrize("text", ["¿me repites lo que me has dicho?", "repíteme lo mismo que me dijiste"])
def test_what_baxy_already_said_is_said_back_in_any_tense(text):
    history = [*_RECALL_HISTORY, {"role": "user", "content": text}]
    assert llm._recalled_speaker(text) == "assistant"
    assert llm._literal_recall_reference(history, text) == "El brillo está en 30."


@pytest.mark.parametrize("text", ["repite lo mismo que te diga", "repite lo que digo", "¿me repites la canción?"])
def test_what_is_still_to_be_said_is_not_a_recall(text):
    assert llm._recalled_speaker(text) is None


def test_no_worked_example_or_hint_is_a_phrase_of_a_measured_tanda():
    shown = " ".join(
        [str(part) for example in llm._REWRITE_EXAMPLES for part in example]
        + list(llm._REWRITE_DEPENDENCY_HINTS.values())
    ).casefold()
    for literal in ("2350", "335", "tomates", "top scorer", "lakers", "mar del plata", "finde", "madrid", "6:15",
                    "40 percent", "entrance", "goleador", "boca"):
        assert literal not in shown
