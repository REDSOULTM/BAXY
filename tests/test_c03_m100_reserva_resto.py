"""M100 (2026-10-01): the class-A causes of the independent audit of the reserve v3w-hold failures that M97 left open.

The reserve is a measurement corpus: none of its texts is written here; every phrasing below is our own, of the same
shape as the rows it stands for (cause codes of the audit, scratchpad reserva_audit/INFORME.md).

1. A1 — the person's own things read with the right store: an event or who they meet is the calendar (never a task
   search nor the internal due step); whether a reminder was set, or asked for, is read; whether someone has a
   birthday is the calendar; what is left on the list is the list; wanting to know about this song is what plays.
2. A2 — their own mail and contacts: the mail asked with «hay» left out, and whether someone got in touch, read the
   latest mail; a mail address or contact details of someone named by one bare name is the plain limit.
3. A10 — reminders said other ways: «recuerda que me + subjunctive», a purpose after the order, being notified wished
   for, and a reminder ordered for something unnamed (never a listing of the reminders).
4. A7 — «play» said as «jugar»: «juega de nuevo» plays again, «jugar» after the media named plays it.
5. A14 — the music player opened to play something plays it; A3 — sounds or songs given are played.
6. A13 — a reply to the latest mail goes with the words the person said; with none, what to answer is asked.
"""

from __future__ import annotations

import pytest

from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider
from baxy_mind.semantic import reading as semantic_reading
from baxy_mind.semantic.games import steam_library_title
from baxy_mind.semantic.media import player_opened_to_play, spoken_media_order
from baxy_mind.semantic.messaging import contact_book_request, inbox_read_request, latest_mail_reply_without_words
from baxy_mind.semantic.notes import agenda_read_request, names_own_event, reminder_inventory_question
from baxy_mind.semantic.patterns import known_unsupported_effect_request, resolve_explicit_clarification_intent
from baxy_mind import context_decision

OPERATIONS = (
    "app.open", "calendar.event.create", "calendar.event.list", "email.latest.read", "email.latest.reply",
    "email.send", "game.entitlement.named", "game.launch", "media.control", "media.play.query", "media.play.youtube",
    "media.status", "message.recipient.resolve", "message.send", "note.list", "notification.list",
    "notification.list.due", "notification.schedule", "reminder.create", "reminder.list", "task.list", "task.search",
    "web.search",
)


def _effects(text: str) -> tuple[str, ...] | None:
    found = semantic_reading.read(text, available_operations=OPERATIONS).effects
    return None if found is None else tuple(found.operations)


class _Decider:
    """A contextual decider that answers one recorded-shape decision."""

    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = ()) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=operations, question="")

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return self.decided

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres que responda?"


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def _decided(text: str, model: _Decider) -> dict[str, object]:
    return context_decision._context_decided_result(
        {"id": "m100", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog([_tool(name) for name in OPERATIONS]),
    )


# ------------------------------------------------------------------ 1. A1: the person's own things, the right store


@pytest.mark.parametrize(
    ("text", "restated", "chosen"),
    [
        ("a qué hora empieza la cena de gala del sábado", "¿A qué hora empieza la cena de gala?", "task.search"),
        ("con quién me reúno mañana", "¿Con quién me reúno mañana?", "task.search"),
        ("who am I meeting this afternoon", "Who am I meeting this afternoon?", "task.search"),
        ("tell me when the dentist appointment is", "When is the dentist appointment?", "task.search"),
        ("party reminders between six and eight", "Show my party reminders from 6 to 8.", "notification.list.due"),
    ],
)
def test_an_event_or_who_one_meets_is_read_from_the_calendar(text: str, restated: str, chosen: str) -> None:
    assert names_own_event(text)
    result = _decided(text, _Decider(restated, "action", (chosen,)))
    assert result["kind"] == "action" and result["operation"] == "calendar.event.list", result


@pytest.mark.parametrize(
    "text", ["busca la tarea de la reunión con Ana", "find my task about the dinner", "qué notas tengo de la cita"],
)
def test_a_task_or_a_note_named_keeps_the_store_chosen(text: str) -> None:
    assert not names_own_event(text)
    result = _decided(text, _Decider(text, "action", ("task.search",)))
    assert result["operation"] == "task.search"


@pytest.mark.parametrize(
    ("text", "reads"),
    [
        ("¿ya creaste el recordatorio del médico?", ("reminder.list",)),
        ("has puesto la alarma para el lunes", ("notification.list",)),
        ("did you set the reminder for the rent", ("reminder.list",)),
        ("te pedí que me recordaras algo ayer", ("reminder.list",)),
        ("did I ask you to remind me about the plants", ("reminder.list",)),
    ],
)
def test_whether_a_reminder_was_set_or_asked_is_read(text: str, reads: tuple[str, ...]) -> None:
    assert reminder_inventory_question(text) == reads
    assert _effects(text) == reads, text


@pytest.mark.parametrize("text", ["pon un recordatorio para el médico", "recuérdame que pague la luz"])
def test_an_order_to_set_one_is_no_question_whether_it_was(text: str) -> None:
    assert reminder_inventory_question(text) == ()


@pytest.mark.parametrize(
    "text",
    ["¿hoy es el cumpleaños de alguien?", "alguien cumple años esta semana", "is it anyone's birthday tomorrow",
     "hay algún cumpleaños el sábado"],
)
def test_whether_someone_has_a_birthday_is_the_calendar(text: str) -> None:
    assert agenda_read_request(text)
    assert _effects(text) == ("calendar.event.list",), text


def test_a_public_birthday_is_not_the_calendar() -> None:
    assert not agenda_read_request("es el cumpleaños de alguien famoso hoy")


@pytest.mark.parametrize(
    "text", ["oye, queda algo pendiente en mi lista", "hay algo que falte todavía en la lista",
             "anything still left on my to do list"],
)
def test_what_is_left_on_the_list_is_the_list(text: str) -> None:
    assert _effects(text) == ("task.list",), text


@pytest.mark.parametrize(
    "text", ["me gustaría saber quién es este artista", "I want to know more about this track",
             "cuéntame de esta canción"],
)
def test_wanting_to_know_about_this_song_reads_what_plays(text: str) -> None:
    assert _effects(text) == ("media.status",), text


def test_this_topic_of_the_conversation_is_no_song() -> None:
    assert _effects("quiero saber más de este tema") != ("media.status",)


# ------------------------------------------------------------------ 2. A2: their own mail and contacts


@pytest.mark.parametrize(
    "text",
    ["¿algún correo del banco?", "algún mail con novedades de la mudanza", "any emails about the lease",
     "¿se ha puesto en contacto conmigo Marta?", "ya Lucho se puso en contacto", "has Diane got in touch yet",
     "did the landlord contact me"],
)
def test_the_mail_asked_and_whoever_got_in_touch_read_the_latest_mail(text: str) -> None:
    assert inbox_read_request(text)
    assert _effects(text) == ("email.latest.read",), text


@pytest.mark.parametrize(
    "text",
    ["algún correo para mandarle a Pedro", "ponte en contacto con Pedro", "did you get in touch with the plumber",
     "me puse en contacto con el banco"],
)
def test_writing_reaching_out_or_telling_is_no_read_of_the_mail(text: str) -> None:
    assert not inbox_read_request(text)


@pytest.mark.parametrize(
    "text",
    ["what is the email address for wendy", "cuál es la dirección de correo electrónico de flor",
     "¿me puedes dar los datos de contacto de nuria?", "puede decirme la información de contacto de jordi"],
)
def test_the_contact_of_someone_named_by_one_name_is_the_limit(text: str) -> None:
    assert contact_book_request(text)
    assert known_unsupported_effect_request(text, OPERATIONS)


@pytest.mark.parametrize(
    "text", ["what is the email address for amazon customer service", "dame la información de contacto del banco"],
)
def test_a_company_said_with_more_is_not_the_book(text: str) -> None:
    assert not contact_book_request(text)


# ------------------------------------------------------------------ 3. A10: reminders said other ways


def _asked(text: str) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    found = resolve_explicit_clarification_intent(text, OPERATIONS)
    return None if found is None else (found.operations, found.missing_fields)


@pytest.mark.parametrize(
    "text",
    ["recuerda que me tome la pastilla", "recuerda que me estire para que no me duela la espalda",
     "recuérdame beber agua para no deshidratarme"],
)
def test_a_reminder_said_with_recuerda_or_a_purpose_asks_when(text: str) -> None:
    assert _asked(text) == (("reminder.create",), ("due_time",)), text


def test_recuerda_que_me_with_a_statement_is_no_reminder() -> None:
    assert _asked("recuerda que me gusta el té sin azúcar") is None


@pytest.mark.parametrize(
    "text",
    ["me gustaría ser avisado de la reunión mañana a las diez de la mañana",
     "quisiera que me avises de la clase el jueves a las cinco de la tarde",
     "I'd like to be reminded of the rent tomorrow at 9 am"],
)
def test_being_notified_wished_for_is_the_reminder(text: str) -> None:
    assert _effects(text) == ("reminder.create",), text


@pytest.mark.parametrize(
    "text", ["necesito algo todos los martes pon un recordatorio", "quiero algo cada viernes, ponme un recordatorio"],
)
def test_a_reminder_for_something_unnamed_asks_what_and_when(text: str) -> None:
    assert _effects(text) is None
    assert _asked(text) == (("reminder.create",), ("what_to_remind_or_notify_about", "due_time"))


def test_reading_the_reminders_still_reads_them() -> None:
    assert _effects("necesito ver mis recordatorios") == ("reminder.list",)


# ------------------------------------------------------------------ 4. A7: «play» said as «jugar»


@pytest.mark.parametrize("text", ["juega de nuevo", "jugala otra vez por favor"])
def test_playing_again_is_no_game(text: str) -> None:
    assert steam_library_title(text) is None
    assert spoken_media_order(text) is not None
    assert _effects(text) == ("media.play.query",), text


@pytest.mark.parametrize("text", ["abre los medios y juega villancicos", "reproductor abierto jugar campanas de belén"])
def test_jugar_after_the_media_plays_it(text: str) -> None:
    assert _effects(text) in {("media.play.query",), ("media.play.youtube",)}, text


def test_a_game_named_is_still_read_from_the_library() -> None:
    assert steam_library_title("juega hollow knight") == "hollow knight"
    assert spoken_media_order("abre la música y juega a las cartas") is None


# ------------------------------------------------------------------ 5. A14 and A3: music asked another way


@pytest.mark.parametrize(
    ("text", "order"),
    [
        ("abre spotify y abre gimnasio", "pon gimnasio en spotify"),
        ("inicia la aplicación de música y reproduce una canción", "pon una canción en spotify"),
        ("open the music app and play a song for me", "play a song for me on spotify"),
    ],
)
def test_the_player_opened_to_play_plays(text: str, order: str) -> None:
    assert player_opened_to_play(text) == order
    assert _effects(text) == ("media.play.query",), text


def test_opening_the_player_alone_opens_it() -> None:
    assert player_opened_to_play("abre spotify") is None


@pytest.mark.parametrize("text", ["dame sonidos relajantes", "danos unas buenas canciones", "give me some good sounds"])
def test_sounds_or_songs_given_are_played(text: str) -> None:
    assert spoken_media_order(text) is not None
    assert _effects(text) in {("media.play.query",), ("media.play.youtube",)}, text


# ------------------------------------------------------------------ 6. A13: the reply carries the person's words


@pytest.mark.parametrize(
    "text",
    ["hay que contestar ese mail cuanto antes", "the newest email should be replied to today",
     "este correo tiene que ser respondido urgente", "responde el correo que me mandó Juan"],
)
def test_a_reply_asked_without_its_words(text: str) -> None:
    assert latest_mail_reply_without_words(text)


@pytest.mark.parametrize(
    "text",
    ["responde al último correo diciendo que llego a las tres", "reply to the last email saying thanks",
     "responde «sí» al último correo", "reply yes to that email", "contesta el último correo que sí voy",
     "answer the latest email with sounds good", "respóndele que mañana lo vemos",
     "responde el último correo: perfecto, gracias", "reply thank you to John", "dile que sí",
     "contesta el correo de Marta avisándole que llego el lunes"],
)
def test_a_reply_with_its_words_or_no_reply_asked(text: str) -> None:
    assert not latest_mail_reply_without_words(text)


def test_the_latest_mail_is_never_answered_with_how_soon() -> None:
    text = "hay que contestar el último correo lo más pronto posible"
    result = _decided(text, _Decider("Answer the last email with «lo más pronto posible».", "action",
                                     ("email.latest.reply",)))
    assert result["kind"] == "clarify" and result["intentOperations"] == ["email.latest.reply"], result
    said = "responde al último correo diciendo que llego tarde"
    kept = _decided(said, _Decider("Responde al último correo: «llego tarde».", "action", ("email.latest.reply",)))
    assert kept["kind"] == "action" and kept["operation"] == "email.latest.reply"


# ------------------------------------------------------------------ 7. a reply to someone with no client named (742 review)
# The 742 replay of HEAD (M97) moved «respondele a mamá que sí» (H0108, H0423) to the resolve/send plan, the shape
# «dile a mi amiga que…» (H0584) has had since M91b. With no client named the recipient is looked up in the clients
# (channel «any», REOPEN1993 grupo E: one verified hit or the step fails saying so) and message.send keeps the App's
# confirmation in normal mode (Baxy.Kernel RiskPolicy, OperationRegistryTests): nothing reaches anyone unconfirmed.


@pytest.mark.parametrize("text", ["contéstale a mi hermano que sí", "respóndele a Lucía que ya salgo",
                                  "dile a mi abuela que la llamo luego"])
def test_a_reply_to_someone_with_no_client_looks_them_up_in_the_clients(text: str) -> None:
    from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence

    assert _effects(text) == ("message.recipient.resolve", "message.send"), text
    assert _explicit_arguments_from_evidence("message.recipient.resolve", text)["channel"] == "any"


def test_a_client_named_is_where_the_recipient_is_looked_up() -> None:
    from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence

    text = "respóndele a Lucía que ya salgo por whatsapp"
    assert _effects(text) == ("message.recipient.resolve", "message.send")
    assert _explicit_arguments_from_evidence("message.recipient.resolve", text)["channel"] == "whatsapp"
