"""Uso real tanda 7 (2026-09-25, official window): a conversation is one message after another.

Half of the tanda were conversations where each message depends on the one before («¿y el finde?», «actually
make it 9», «y quién fue el top scorer», «cómo se llama esta?»), and a third of those follow-ups were understood.
The owner's method of the same day (artifacts/comprobaciones/C03/PROPUESTA_METODO_COMPRENSION_2026-09-25.md)
answers it with one mechanism, not a rule per phrase. One owner per rule:

1. A clock said with its minutes is read by its hour («remind me at 7:30 to call grandma» was asked «when and
   what?»: the 30 was read as the hour). Owner: semantic/patterns._incomplete_scheduled_request (the hour digits).
2. The trigger, by form: a message that leans on the turn before — a connector or a correction first, a bare
   part with no verb (a day, a place, an amount, «otra»), «allá», «esta», «eso», «it», a question with no object,
   a short question about something already named — is rewritten in context; a complete new request and talk
   never are. Owner: semantic/dialogue.leans_on_context (through dependency → «followup»).
3. The dialogue state: the last thing of each kind the conversation verified (place, day, what plays, the alarm and
   the reminder set, the topic searched, the last request that ran), written only from verified results. Owner:
   semantic/dialogue.DialogueState, kept by the serve loop from message.compose.
4. The rewrite: the model writes the follow-up as a request that stands alone, with the state and the previous
   turns; only words said or verified pass, and the readers must read it in the family it continues (or read no
   effect). A correction of the alarm or timer just set replaces it. A connector before a complete request is
   dropped without the model. Owner: __main__._rearm_in_context.
5. No inventing: a place said only through a person («at my sister's») is asked, never read as this PC's town
   (owner: semantic/system.weather_place_known_only_through_someone); a search whose results are about something
   else than the subject asked is reported as not found (owner: llm._search_report_off_subject).
6. «cancel the last timer» cancels the last scheduled alarm like «cancel the last alarm» (owner:
   semantic/notes, the notification cancel reader).

Every list mixes Spanish, English and Spanglish and holds phrasings never seen in a run.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue
from baxy_mind.semantic.reading import read

OPERATIONS = (
    "audio.volume", "audio.volume.adjust", "audio.mute", "system.settings.set", "system.settings.adjust",
    "media.control", "media.play.query", "media.play.youtube", "media.status", "weather.current", "web.search",
    "notification.schedule", "notification.cancel.latest", "notification.cancel.at", "notification.list",
    "reminder.create", "reminder.list", "system.time", "calendar.event.list", "app.open",
)


# ---------------------------------------------------------------- 1. a clock with its minutes


@pytest.mark.parametrize(
    "text",
    [
        "remind me at 7:30 to call grandma",  # tanda 7 t24 (after «and»)
        "remind me to water the plants at 19:45",
        "recuérdame a las 7:30 llamar a la abuela",
        "avísame a las 8:15 que saque la ropa",
        "recordame a las 21:05 sacar la basura",
    ],
)
def test_a_clock_with_minutes_is_read_by_its_hour(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("reminder.create",)
    assert reading.clarification is None


@pytest.mark.parametrize("text", ["recuérdame a las 99 comprar pan", "remind me at 13 pm to call mom"])
def test_an_hour_no_day_has_is_still_asked(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is not None


# ---------------------------------------------------------------- 2. the trigger, by form


def _slot(*antecedents: str, reply: str = "Listo.") -> dialogue.DialogueSlot:
    return dialogue.DialogueSlot(None, None, tuple(antecedents), reply)


@pytest.mark.parametrize(
    "text",
    [
        "¿y para el domingo?",
        "and what about tomorrow?",
        "and in Lisbon?",
        "mejor que sean 7",
        "nah, make it 20",
        "no, a las 9",  # an hour is no destination: it replaces the hour said
        "esa no, pon otra",
        "not that one",
        "another one please",
        "quién canta esta",
        "what's this called",
        "cómo se llama esto?",
        "is the museum open on sundays",
        "does it have parking",
        "¿y cuánto cuesta la entrada?",
        "qué tengo programado",
        "what do I have scheduled?",
        "y la temperatura?",
        "a qué hora amanece por allá mañana",
        "¿y Messi?",
        "y quién metió los goles",
        "wait, make it 15",
        "escríbeme un poema sobre eso",
        "y ponme una alarma a las 7 de la mañana para el gym",
    ],
)
def test_a_message_that_leans_on_the_turn_before_is_a_followup(text):
    assert dialogue.dependency(text, _slot("che, ¿llueve mañana?")) == "followup"


@pytest.mark.parametrize("text", ["¿y en Rosario?", "y en Córdoba entonces", "no, en YouTube"])
def test_only_a_new_place_is_still_a_destination(text):
    assert dialogue.dependency(text, _slot("che, ¿llueve mañana?")) == "destination"


@pytest.mark.parametrize(
    "text",
    [
        # A complete new request, said with its own verb and object, or its own subject.
        "pon música de Soda Stereo en Spotify",
        "abre el bloc de notas",
        "what's the weather in Madrid tomorrow",
        "quién inventó el teléfono",
        "¿y quién ganó el Mundial 2022?",
        "is Madrid bigger than Lisbon",
        "set a timer for 5 minutes",
        "is there rain tomorrow",
        # Talk, closing and prohibitions.
        "gracias!",
        "ok great",
        "no, that's all, thanks",
        "jajaja",
        "no pongas nada",
    ],
)
def test_a_complete_request_or_talk_is_never_a_followup(text):
    assert dialogue.dependency(text, _slot("che, ¿llueve mañana?")) != "followup"


def test_without_a_turn_before_nothing_is_a_followup():
    assert dialogue.dependency("¿y el domingo?", _slot()) is None


@pytest.mark.parametrize(
    ("text", "replaces"),
    [
        ("actually make it 9", True),
        ("mejor que sean 6", True),
        ("no, a las 8", True),
        ("9", True),
        ("y otro de 20 para el arroz", False),
        ("and another one at 8", False),
        ("¿y a las 8?", False),
    ],
)
def test_a_correction_replaces_what_was_done_and_an_addition_does_not(text, replaces):
    assert dialogue.followup(text).replaces_last is replaces


# ---------------------------------------------------------------- 3. the dialogue state


def _verified(operation: str, observed: dict | None = None, *, verified: bool = True) -> dict:
    return {
        "kind": "operation", "operation": operation, "polarity": "success" if verified else "failure",
        "verified": verified, "succeeded": verified, "observed": observed,
    }


def _state(*steps: tuple[str, str, dict]) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    for request, operation, observed in steps:
        state.expect(request, [operation])
        state.record(_verified(operation, observed))
    return state


def test_the_state_keeps_the_last_verified_thing_of_each_kind():
    state = _state(
        ("che, ¿llueve el domingo?", "weather.current", {"location": "Córdoba", "country": "Argentina"}),
        ("ponme un temporizador de 8 minutos para los huevos", "notification.schedule",
         {"kind": "alarm", "title": "temporizador de 8 minutos para los huevos", "dueUtc": "2026-09-25T12:08:00Z",
          "taskName": "BAXY-Alarm-1"}),
        ("pon algo de Soda Stereo en Spotify", "media.play.query",
         {"title": "De Música Ligera", "artist": "Soda Stereo", "query": "soda stereo"}),
    )
    lines = " | ".join(line for _, line in state.lines())
    assert "Córdoba, Argentina" in lines and "el domingo" in lines
    assert "temporizador de 8 minutos para los huevos" in lines and "BAXY-Alarm-1" in lines
    assert "De Música Ligera — Soda Stereo" in lines
    assert state.request == "pon algo de Soda Stereo en Spotify"
    assert state.operations == ("media.play.query",)
    assert state.families == {"weather", "notification", "media"}


def test_the_state_is_written_only_by_a_verified_result_of_the_decided_operation():
    state = dialogue.DialogueState()
    state.expect("¿llueve mañana en Rosario?", ["weather.current"])
    state.record(_verified("weather.current", {"location": "Rosario"}, verified=False))  # not verified
    state.record(_verified("media.status", {"title": "Otra"}))  # not the decided operation
    # Nothing is verified; the request is still the one the last turn decided (tanda 8), never a fact.
    assert state.lines() == [] and state.operations == () and state.request == "¿llueve mañana en Rosario?"
    state.expect("¿qué hora es?", [])  # a conversation turn decides no operation
    state.record(_verified("weather.current", {"location": "Rosario"}))
    assert state.lines() == []
    state.expect("¿llueve mañana en Rosario?", ["weather.current"])
    state.record(_verified("weather.current", {"location": "Rosario"}))
    assert any("Rosario" in line for _, line in state.lines())
    state.reset()
    assert state.lines() == [] and state.operations == () and state.families == set()


@pytest.mark.parametrize(
    ("said", "spanish", "cancel"),
    [
        ("ponme un temporizador de 8 minutos para los huevos", True, "cancela el último temporizador"),
        ("set a timer for the tea, 4 minutes", False, "cancel the last timer"),
        ("pon una alarma a las 7 de la mañana", True, "cancela la última alarma"),
        ("wake me up at 6 am", False, "cancel the last alarm"),
    ],
)
def test_the_state_names_what_a_correction_replaces(said, spanish, cancel):
    state = _state((said, "notification.schedule", {"kind": "alarm", "title": said}))
    assert state.cancel_last_alarm(spanish) == cancel
    assert dialogue.DialogueState().cancel_last_alarm(spanish) is None


# ---------------------------------------------------------------- 4. the rewrite in context


class _Scripted:
    """A model that writes the rewrites a good model would, and records what it was shown."""

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers
        self.seen: list[dict] = []

    def rewrite_in_context(self, text, context, *, dependency="", verified=(), **_kwargs):
        self.seen.append({"text": text, "context": list(context), "dependency": dependency, "verified": list(verified)})
        if text not in self.answers:
            raise AssertionError(f"the model is not asked about {text!r}")
        return self.answers[text]

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("the readers own the rewritten request")

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _message(*turns: str) -> dict:
    """A conversation: user and BAXY turns alternate, the last one is the person's new message."""

    history = [
        {"role": "user" if index % 2 == 0 else "assistant", "content": turn} for index, turn in enumerate(turns)
    ]
    return {"id": "tanda-07", "text": turns[-1], "history": history}


def _rearm(message: dict, model: _Scripted, state: dialogue.DialogueState | None):
    return sidecar._rearm_in_context(message, llm=model, available_operations=OPERATIONS, dialogue_state=state)


_WEATHER = ("che, ¿llueve mañana?", "weather.current", {"location": "Córdoba", "region": "Córdoba", "country": "Argentina"})


def test_a_new_day_for_the_weather_is_the_same_question_that_day():
    model = _Scripted({"¿y el domingo?": "¿llueve el domingo?"})
    result = _rearm(_message("che, ¿llueve mañana?", "Mañana no llueve.", "¿y el domingo?"), model, _state(_WEATHER))
    assert result == ("¿llueve el domingo?", "model")
    assert model.seen[0]["dependency"] == "followup"
    assert any("Córdoba" in line for _, line in model.seen[0]["verified"])


def test_a_new_place_is_joined_to_the_verified_request_without_the_model():
    state = _state(("¿llueve el domingo?", "weather.current", {"location": "Córdoba"}))
    message = _message("che, ¿llueve mañana?", "No.", "¿y el domingo?", "Tampoco.", "¿y en Rosario?")
    assert _rearm(message, _Scripted({}), state) == ("¿llueve el domingo en Rosario", "pattern")


def test_alla_is_the_verified_place():
    state = _state(("¿llueve el domingo en Rosario", "weather.current", {"location": "Rosario", "country": "Argentina"}))
    text = "a qué hora sale el sol por allá el sábado"
    model = _Scripted({text: "a qué hora sale el sol en Rosario el sábado"})
    message = _message("¿y en Rosario?", "El domingo no llueve en Rosario.", text)
    assert _rearm(message, model, state) == ("a qué hora sale el sol en Rosario el sábado", "model")


def test_a_place_nobody_said_is_never_taken():
    state = _state(("¿llueve el domingo en Rosario", "weather.current", {"location": "Rosario"}))
    text = "a qué hora sale el sol por allá el sábado"
    model = _Scripted({text: "a qué hora sale el sol en Mendoza el sábado"})
    assert _rearm(_message("¿y en Rosario?", "No llueve.", text), model, state) is None


@pytest.mark.parametrize(
    ("said", "text", "rewrite", "rearmed"),
    [
        (
            "ponme un temporizador de 8 minutos para los huevos", "mejor que sean 6",
            "ponme un temporizador de 6 minutos para los huevos",
            "cancela el último temporizador y ponme un temporizador de 6 minutos para los huevos",
        ),
        (
            "set a timer for the tea, 4 minutes", "wait, make it 5", "set a timer for the tea, 5 minutes",
            "cancel the last timer and set a timer for the tea, 5 minutes",
        ),
        (
            "pon una alarma a las 7 de la mañana", "no, a las 8", "pon una alarma a las 8 de la mañana",
            "cancela la última alarma y pon una alarma a las 8 de la mañana",
        ),
    ],
)
def test_a_correction_of_the_timer_just_set_replaces_it(said, text, rewrite, rearmed):
    # Replay of tanda 7b: the correction is the request with its new value, joined without the model (the model's
    # «make the timer for the pasta 9 minutes» was read by nobody); the model is not asked.
    state = _state((said, "notification.schedule", {"kind": "alarm", "title": said, "taskName": "BAXY-Alarm-2"}))
    result = _rearm(_message(said, "Listo, quedó programado.", text), _Scripted({}), state)
    assert result == (rearmed, "pattern") and rearmed.endswith(rewrite)
    assert read(rearmed, available_operations=OPERATIONS).effects.operations == (
        "notification.cancel.latest", "notification.schedule",
    )


def test_another_timer_is_added_not_replaced():
    request = "ponme un temporizador de 8 minutos para los huevos"
    state = _state((request, "notification.schedule", {"kind": "alarm", "title": request}))
    text = "y otro de 20 minutos para el arroz"
    rewrite = "ponme un temporizador de 20 minutos para el arroz"
    assert _rearm(_message(request, "Listo.", text), _Scripted({text: rewrite}), state) == (rewrite, "model")


def test_this_one_is_what_is_playing():
    state = _state(("pon algo de Soda Stereo en Spotify", "media.play.query",
                    {"title": "De Música Ligera", "artist": "Soda Stereo", "query": "soda stereo"}))
    message = _message("pon algo de Soda Stereo en Spotify", "Suena De Música Ligera.", "qué tema es este")
    rearmed = _rearm(message, _Scripted({}), state)
    assert rearmed is not None and rearmed[1] == "pattern"
    assert read(rearmed[0], available_operations=OPERATIONS).effects.operations == ("media.status",)


def test_another_song_is_asked_with_what_was_asked_before():
    state = _state(("pon algo de Soda Stereo en Spotify", "media.play.query", {"title": "Persiana Americana"}))
    text = "esa no, otra más tranqui"
    rewrite = "pon otra canción más tranqui de Soda Stereo en Spotify"
    message = _message("pon algo de Soda Stereo en Spotify", "Suena Persiana Americana.", text)
    assert _rearm(message, _Scripted({text: rewrite}), state) == (rewrite, "model")


def test_a_question_about_the_same_game_carries_its_topic():
    state = _state(("quién ganó el clásico ayer", "web.search", {"query": "quién ganó el clásico ayer", "results": []}))
    text = "y quién metió los goles"
    rewrite = "quién metió los goles en el clásico de ayer"
    message = _message("quién ganó el clásico ayer", "Ganó River 2 a 1.", text)
    assert _rearm(message, _Scripted({text: rewrite}), state) == (rewrite, "model")


def test_a_name_nobody_said_is_never_added_to_the_topic():
    state = _state(("quién ganó el clásico ayer", "web.search", {"query": "quién ganó el clásico ayer"}))
    text = "y quién metió los goles"
    model = _Scripted({text: "quién metió los goles del Barcelona en el clásico de ayer"})
    assert _rearm(_message("quién ganó el clásico ayer", "Ganó River.", text), model, state) is None


def test_what_was_set_is_listed_back():
    state = _state(
        ("ponme un temporizador de 8 minutos para los huevos", "notification.schedule", {"title": "huevos"}),
        ("recordame a las 21:05 sacar la basura", "reminder.create", None),
    )
    text = "qué tengo programado"
    message = _message("recordame a las 21:05 sacar la basura", "Listo.", text)
    # Replay of tanda 7b: the model kept «what have I got set right now?»; the kinds set are named without it.
    assert _rearm(message, _Scripted({}), state) == ("qué alarmas, temporizadores y recordatorios tengo programado", "pattern")


def test_a_complete_request_after_a_connector_is_itself_without_the_model():
    text = "y ponme una alarma a las 7 de la mañana para el gym"
    message = _message("ponme un temporizador de 8 minutos para los huevos", "Listo.", text)
    assert _rearm(message, _Scripted({}), None) == ("ponme una alarma a las 7 de la mañana para el gym", "pattern")


@pytest.mark.parametrize(
    "text",
    ["pon música de Soda Stereo en Spotify", "¡gracias, genial!", "¿y quién ganó el Mundial 2022?", "abre el bloc de notas"],
)
def test_a_complete_request_or_talk_is_never_rewritten(text):
    assert _rearm(_message("che, ¿llueve mañana?", "No llueve.", text), _Scripted({}), _state(_WEATHER)) is None


def test_after_a_turn_about_something_else_nothing_carries_from_before():
    # The weather, then music: «¿y mañana?» continues the music now, and a weather rewrite adds an effect.
    state = _state(_WEATHER, ("pon algo de Soda Stereo en Spotify", "media.play.query", {"title": "Persiana Americana"}))
    message = _message("che, ¿llueve mañana?", "No.", "pon algo de Soda Stereo en Spotify", "Suena.", "¿y mañana?")
    assert _rearm(message, _Scripted({"¿y mañana?": "¿llueve mañana?"}), state) is None


# ---------------------------------------------------------------- 4b. the whole turn


def _tool(operation: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"), "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.", "risk": "low_reversible",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


class _NoEvidence:
    @staticmethod
    def candidate_families(*_args: object) -> tuple[str, ...]:
        return ()

    @staticmethod
    def retrieve(*_args: object, **_kwargs: object) -> list[object]:
        return []


def _turn(message: dict, model: _Scripted, state: dialogue.DialogueState) -> dict:
    tools = [_tool(name) for name in OPERATIONS]
    return sidecar._prepare_turn_result(
        message,
        llm=model,
        planner_catalog=PlannerCatalog(tools),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name={tool["function"]["canonical_name"]: tool for tool in tools},
        dialogue_state=state,
    )


@pytest.mark.parametrize(
    ("said", "operation", "observed", "reply", "text", "rewrite", "operations"),
    [
        (
            "will it rain tomorrow in Lisbon?", "weather.current", {"location": "Lisbon", "country": "Portugal"},
            "No rain tomorrow in Lisbon.", "what about sunday?", "will it rain sunday in Lisbon?",
            ["weather.current"],
        ),
        (  # spanglish, rioplatense
            "¿va a llover mañana en Buenos Aires?", "weather.current", {"location": "Buenos Aires"},
            "Mañana no llueve.", "¿y el weekend?", "¿va a llover el weekend en Buenos Aires?", ["weather.current"],
        ),
        (
            "pon algo de Soda Stereo en Spotify", "media.play.query", {"title": "Persiana Americana — Soda Stereo"},
            "Suena Persiana Americana.", "cómo se llama esta?", "cómo se llama esta canción", ["media.status"],
        ),
    ],
)
def test_the_followup_turn_is_decided_by_the_readers_as_the_rewritten_request(
    said, operation, observed, reply, text, rewrite, operations,
):
    result = _turn(_message(said, reply, text), _Scripted({text: rewrite}), _state((said, operation, observed)))
    assert result["kind"] == "action" and result["effectOperations"] == operations
    assert result["objective"] == rewrite


def test_a_rewrite_in_words_nobody_said_leaves_the_message_as_it_arrived():
    # A translated rewrite («domingo» for «sunday») is a word the model brought in.
    model = _Scripted({"what about sunday?": "¿llueve el domingo?"})
    message = _message("che, ¿llueve mañana?", "No.", "what about sunday?")
    assert _rearm(message, model, _state(_WEATHER)) is None


def test_the_timer_correction_turn_is_one_plan_that_replaces_it():
    request = "set a timer for the tea, 4 minutes"
    state = _state((request, "notification.schedule", {"kind": "alarm", "title": request}))
    model = _Scripted({"actually, make it 6": "set a timer for the tea, 6 minutes"})
    result = _turn(_message(request, "Done.", "actually, make it 6"), model, state)
    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]


# ---------------------------------------------------------------- 5. no inventing


@pytest.mark.parametrize(
    "text",
    [
        "¿Va a llover tomorrow at my sister's?",  # tanda 7 t26
        "va a llover en casa de mi hermana mañana",
        "qué tiempo hace en lo de mi vieja",
        "is it going to rain where my dad lives",
        "will it be cold at my mom's house tomorrow",
    ],
)
def test_a_place_known_only_through_someone_is_asked(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.clarification is not None
    assert reading.clarification.operations == ("weather.current",)
    assert reading.clarification.missing_fields == ("location",)


@pytest.mark.parametrize(
    "text",
    ["va a llover en casa de mi hermana en Lima", "qué clima hace en mi casa", "will it rain at my place", "va a llover mañana"],
)
def test_a_named_town_or_here_is_read(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("weather.current",)
    assert reading.clarification is None


def _search_payload(*snippets: str) -> dict:
    return {
        "operation": "web.search",
        "seen": {
            "query": "top scorer",
            "results": [
                {"title": f"Resultado {index}", "url": f"https://example{index}.org/a", "snippet": snippet}
                for index, snippet in enumerate(snippets)
            ],
        },
    }


def test_a_search_about_something_else_is_reported_as_not_found():
    user = "quién fue el top scorer del game de los Lakers anoche"
    payload = _search_payload("Raphinha es el máximo goleador de LaLiga con 12 goles.", "Tabla de goleadores 2026/27.")
    assert llm._payload_fact_defect("Raphinha fue el top scorer con 12 goles.", payload, user) == "search_report_off_subject"
    assert llm._payload_fact_defect("No encontré quién fue el goleador de ese partido.", payload, user) == ""
    answered = _search_payload("Luka Doncic fue el top scorer de los Lakers anoche con 34 puntos.")
    assert llm._payload_fact_defect("Luka Doncic fue el top scorer con 34 puntos.", answered, user) != (
        "search_report_off_subject"
    )


def test_a_question_without_a_name_is_not_judged_by_its_subject():
    payload = _search_payload("El arcoíris tiene siete colores: rojo, naranja, amarillo, verde, azul, añil y violeta.")
    assert llm._search_report_off_subject("Tiene siete colores.", payload, "cuáles son los colores del arcoíris") is False


# ---------------------------------------------------------------- 6. the last timer cancelled


@pytest.mark.parametrize(
    "text", ["cancel the last timer", "cancela el último temporizador", "quita el último temporizador", "delete the last timer"],
)
def test_the_last_timer_is_cancelled_like_the_last_alarm(text):
    reading = read(text, available_operations=OPERATIONS)
    assert reading.effects is not None and reading.effects.operations == ("notification.cancel.latest",)


def test_all_the_timers_are_not_the_last_one():
    assert read("borra los temporizadores", available_operations=OPERATIONS).effects is None
