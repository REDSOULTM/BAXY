"""M91 (2026-09-30, the reserve held-out v3t at 85.6 %): the rows v3m had right and v3t broke, and the general causes
of the largest failure groups the readers own.

The reserve is a measurement corpus: none of its texts is written here. Every phrasing below is our own, of the same
shape as the rows it stands for.

1. Where the person is is no data of theirs («para mi zona», «cercanos a mí», «in my hometown»), nor are the options
   the public offers them («my options for a bus»), nor an occasion said as what a public thing is for («una receta
   para la comida de mañana»).
2. A new list asked for is complete when it is made; only an entry that names nothing is asked (M84 kept).
3. «dame una lista de tareas por hacer» may be the person's to-do list: the readers leave it to the decider.
4. «tell me the … that …» is said to BAXY, not a message to someone called «me …».
5. A lone interjection («vaya», «venga») is no usted order.
6. Something put into the calendar, in any person or place of the sentence, is no read of it; an order on its way is
   no agenda either.
7. Teams playing are sport, not what this PC plays.
8. Heavy, damp heat said by its feel is the weather; «hacer bueno» too.
9. A long question with its question mark dropped still opens asking («qué día…», «puedo saber…», «cuánto pago…»).
10. The radio with no station, said to anyone or as a change of station, asks which; a change to a named dial tunes it.
11. The next or previous episode of a show moves what plays, not the browser.
12. The dish a video or a recipe is for is no errand.
13. The last mail, contact or call is the person's, never a public «last».
"""

from __future__ import annotations

from baxy_mind import __main__ as sidecar
from baxy_mind import effect_intent
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider
from baxy_mind.semantic import reading as semantic_reading
from baxy_mind.semantic.guards import _unresolved_input_kind
from baxy_mind.semantic.media import _media_transport_action, radio_station_query
from baxy_mind.semantic.notes import agenda_read_request, list_creation_said
from baxy_mind.semantic.patterns import (
    conversation_only_content_request,
    known_unsupported_effect_request,
    resolve_explicit_clarification_intent,
)
from baxy_mind.semantic.system import physical_world_request
from baxy_mind.semantic.temporal import spoken_clock
from baxy_mind.semantic.web import names_own_data, near_the_person, record_fact_query

OPERATIONS = (
    "audio.mute", "browser.navigate", "calendar.event.create", "calendar.event.list", "capture.active.window",
    "email.latest.read", "media.control", "media.play.query", "media.play.youtube", "media.status",
    "message.recipient.resolve", "message.send", "notification.schedule", "ocr.read", "reminder.create",
    "reminder.list", "task.create", "task.list", "weather.current", "web.search",
)


def _effects(text: str) -> tuple[str, ...] | None:
    found = semantic_reading.read(text, available_operations=OPERATIONS).effects
    return None if found is None else tuple(found.operations)


# ------------------------------------------------------------------ helpers of the decided turn


class _Decider:
    """A contextual decider that returns one fixed decision."""

    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = (), **arguments: object) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(
            request=request, decision=decision, operations=operations, question="", arguments=tuple(arguments.items()),
        )

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return self.decided

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres poner en la lista?"


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
    return sidecar._context_decided_result(
        {"id": "m91", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog([_tool(name) for name in ("task.create", "web.search", "weather.current")]),
    )


# ------------------------------------------------------------------ 1. where the person is, their options, occasions


def test_where_the_person_is_is_looked_up_near_them() -> None:
    for text in (
        "índice de robos para mi zona este año",
        "horarios de buses cercanos a mí",
        "conciertos de jazz this weekend in my hometown",
        "any food festivals going on in my home town",
        "farmacias de turno por mi barrio",
    ):
        assert not names_own_data(text), text
        assert near_the_person(text), text
    # The person's own things stay theirs.
    for text in ("cuántos de mis amigos viven en Lima", "what's on my calendar", "dónde dejé mis llaves"):
        assert names_own_data(text), text


def test_the_options_open_to_the_person_are_public() -> None:
    for text in ("what are my options for a bus to Denver on Friday", "cuáles son mis opciones de vuelo a Lima"):
        assert not names_own_data(text), text
    assert names_own_data("which of my contacts lives in Denver")


def test_an_occasion_said_as_what_a_public_thing_is_for_is_no_question_about_it() -> None:
    for text in ("busca una receta para la comida de mañana", "ideas de postres para la fiesta del sábado",
                 "find a playlist for tonight's dinner"):
        assert not names_own_data(text), text
    # The occasion asked about is still the person's.
    for text in ("a qué hora es la comida de mañana", "where is tonight's dinner"):
        assert names_own_data(text), text


def test_the_decided_search_near_the_person_is_kept() -> None:
    text = "horarios de buses cercanos a mí"
    result = _decided(text, _Decider(text, "action", ("web.search",), query="horarios de buses", nearby=True))
    assert result["kind"] == "action" and result["operation"] == "web.search"


# ------------------------------------------------------------------ 2. a new list


def test_a_new_list_asked_for_is_made_and_an_unnamed_entry_is_asked() -> None:
    for text in ("crea una lista nueva para el supermercado", "quiero hacer la lista del viaje de este mes",
                 "make a new list for the camping trip"):
        assert list_creation_said(effect_intent._fold(text)), text
        result = _decided(text, _Decider(text, "action", ("task.create",), title="lista"))
        assert result["kind"] == "action" and result["operation"] == "task.create", text
    text = "añade un elemento a mi lista del gimnasio"
    assert not list_creation_said(effect_intent._fold(text))
    assert _decided(text, _Decider(text, "action", ("task.create",), title="gimnasio"))["kind"] == "clarify"


# ------------------------------------------------------------------ 3. the things to do


def test_the_things_to_do_are_left_to_the_decider() -> None:
    for text in ("dame una lista de tareas por hacer", "dame una lista de cosas por hacer hoy"):
        assert not conversation_only_content_request(text), text
    assert conversation_only_content_request("dame una lista de ideas para una fiesta infantil")


# ------------------------------------------------------------------ 4. «tell me … that …»


def test_tell_me_the_thing_that_was_is_said_to_baxy() -> None:
    text = "tell me the saddest poem that was ever written"
    assert _effects(text) is None
    assert resolve_explicit_clarification_intent(text, OPERATIONS) is None
    assert _effects("tell Marta that the meeting moved") == ("message.recipient.resolve", "message.send")


# ------------------------------------------------------------------ 5. a lone interjection


def test_a_lone_interjection_is_no_order() -> None:
    for text in ("vaya", "¡Venga!", "oiga"):
        assert _effects(text) is None, text
    assert _effects("silencie") is not None


# ------------------------------------------------------------------ 6. the calendar written, and orders on their way


def test_something_put_into_the_calendar_is_no_read_of_it() -> None:
    for text in (
        "ponga la cena con Rosa del viernes en mi calendario",
        "block my calendar on Thursday afternoon",
        "I want the dentist on Monday put on the calendar",
    ):
        assert not agenda_read_request(text), text
        assert _effects(text) != ("calendar.event.list",), text
    assert _effects("show me the events in my calendar for tomorrow") == ("calendar.event.list",)
    assert _effects("what does my coming week look like") == ("calendar.event.list",)


def test_an_order_on_its_way_is_no_agenda() -> None:
    assert not agenda_read_request("when will my pizza be delivered")
    assert not agenda_read_request("cuándo llega mi pedido de la farmacia")
    assert agenda_read_request("cuándo es mi cita con el dentista")


# ------------------------------------------------------------------ 7. sport is not what plays


def test_teams_playing_are_not_what_this_pc_plays() -> None:
    assert _effects("which teams are playing tonight in the champions league") != ("media.status",)
    assert _effects("what song is playing") == ("media.status",)


# ------------------------------------------------------------------ 8. the weather by its feel


def test_heavy_damp_heat_and_a_nice_day_are_the_weather() -> None:
    for text in ("is tomorrow going to be sticky", "va a ser una tarde bochornosa", "¿hará bueno el domingo?"):
        assert _effects(text) == ("weather.current",), text
    assert _effects("create sticky notes for the meeting") != ("weather.current",)


# ------------------------------------------------------------------ 9. a long question without its question mark


def test_a_long_question_without_its_mark_is_still_asked() -> None:
    for text in (
        "qué día de la semana cayó el veinte de mayo de mil novecientos noventa y uno según el calendario",
        "puedo saber lo que tengo pendiente para el próximo martes a las cinco de la tarde en la oficina",
        "si una manzana cuesta dos euros y una pera tres euros cuánto pago si compro cuatro manzanas y dos peras",
    ):
        assert _unresolved_input_kind(text) is None, text
    overheard = "y entonces le dije a mi hermano que la próxima semana íbamos a ir todos juntos al campo con los niños"
    assert _unresolved_input_kind(overheard) == "overheard_speech"


# ------------------------------------------------------------------ 10. the radio


def test_the_radio_with_no_station_asks_which_and_a_dial_change_tunes_it() -> None:
    for text in ("que alguien encienda la radio", "could you turn on the radio", "help me listen to the radio",
                 "cambia la emisora de radio"):
        asked = resolve_explicit_clarification_intent(text, OPERATIONS)
        assert asked is not None and asked.missing_fields == ("station_or_genre",), text
    assert radio_station_query("cambia la emisora a la noventa y uno punto tres") == "91.3 FM en vivo"
    assert _effects("switch the station to ninety five point five") == ("media.play.youtube",)


# ------------------------------------------------------------------ 11. episodes


def test_the_next_or_previous_episode_moves_what_plays() -> None:
    assert _media_transport_action("ve al siguiente episodio de la serie") == "next"
    assert _media_transport_action("go back to the last episode of this show") == "previous"
    assert _media_transport_action("inicia el próximo episodio") == "next"
    assert _effects("please go to the next episode of this podcast") == ("media.control",)
    assert "browser.navigate" in (_effects("go to the website of the city museum") or ())


# ------------------------------------------------------------------ 12. the dish a video is for


def test_the_dish_a_video_is_for_is_no_errand() -> None:
    for text in ("muéstrame un video para hacer tortilla de papas", "show me how to cook rice"):
        assert not physical_world_request(effect_intent._fold(text)), text
        assert not known_unsupported_effect_request(text, OPERATIONS), text
    assert physical_world_request(effect_intent._fold("hazme un café con leche"))


# ------------------------------------------------------------------ 13. the person's last mail, contact or call


def test_the_last_mail_or_contact_is_the_persons() -> None:
    assert record_fact_query("what was the last email from the bank") is None
    assert record_fact_query("quién fue el último contacto que me escribió") is None
    assert _effects("what was the last email from the bank") != ("web.search",)
    assert record_fact_query("cuál fue la última película de Pixar") is not None


# ------------------------------------------------------------------ 14. English minutes, «remind me how many», sources


def test_english_minutes_said_after_the_hour_are_read() -> None:
    clock = spoken_clock("wake me up on saturday at seven fifteen pm")
    assert clock is not None and (clock.hour, clock.minute, clock.resolved) == (19, 15, True)
    clock = spoken_clock("set an alarm at eight forty five in the morning")
    assert clock is not None and (clock.hour, clock.minute, clock.resolved) == (8, 45, True)
    assert _effects("set an alarm for monday at six forty am") == ("notification.schedule",)
    # «at five thirty minutes» is a duration, never 5:30.
    clock = spoken_clock("remind me at five thirty minutes from now")
    assert clock is None or clock.minute == 0


def test_remind_me_how_many_asks_to_be_told() -> None:
    assert resolve_explicit_clarification_intent("recuérdame cuántas notas tengo guardadas", OPERATIONS) is None
    assert resolve_explicit_clarification_intent("remind me which lists I have", OPERATIONS) is None
    asked = resolve_explicit_clarification_intent("recuérdame llamar a Pedro", OPERATIONS)
    assert asked is not None and asked.missing_fields == ("due_time",)


def test_news_fetched_from_a_source_is_read_not_bought() -> None:
    assert resolve_explicit_clarification_intent("get me the top stories from the guardian", OPERATIONS) is None
    asked = resolve_explicit_clarification_intent("get me a large pizza from luigi's", OPERATIONS)
    assert asked is not None and asked.missing_fields == ("product_lookup_or_purchase",)


def test_which_coat_to_wear_is_the_weather_but_not_which_to_buy() -> None:
    assert _effects("which coat should I take tonight") == ("weather.current",)
    assert _effects("what jacket should I buy for the winter") != ("weather.current",)


def test_what_is_named_to_hear_on_the_radio_is_tuned() -> None:
    assert radio_station_query("pon los cuarenta principales en la radio") == "radio los cuarenta principales en vivo"
    assert _effects("let's tune in to classic rock on the radio") == ("media.play.youtube",)
    assert _effects("vamos a escuchar la cadena cope") == ("media.play.youtube",)
    # The radio of a room is a device, and nothing named asks which station.
    assert radio_station_query("pon a Sabina en la radio del salón") is None
    assert radio_station_query("pon música en la radio") is None


def test_the_need_of_weather_gear_said_as_a_statement_is_the_weather() -> None:
    assert _effects("tengo que llevarme el abrigo mañana") == ("weather.current",)
    assert _effects("tengo que llevar la chaqueta a la tintorería") != ("weather.current",)


def test_mail_others_sent_to_the_person_is_what_arrived() -> None:
    assert _effects("has Pablo emails me today") == ("email.latest.read",)
    assert _effects("show me the mails sent to me from the bank") == ("email.latest.read",)


def test_being_let_know_or_finding_the_list_reads_it() -> None:
    for text in ("hágame saber la lista", "infórmeme de los elementos de la lista", "encuentre la lista"):
        assert _effects(text) == ("task.list",), text
