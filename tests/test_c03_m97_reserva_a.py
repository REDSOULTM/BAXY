"""M97 (2026-09-30): the class-A causes of the independent audit of the reserve v3w-hold failures, and the empty or
generic finals of the official-window DEV-D run v3x.

The reserve is a measurement corpus: none of its texts is written here; every phrasing below is our own, of the same
shape as the rows it stands for. DEV-D rows are named by their id (development set).

1. A silence order for a span of time is the mute (owner's rule: BAXY mutes and says nothing turns the sound back on);
   a reply that promises the timer is refused.
2. A limit never mangles the verb asked (an order's stem too, not only an infinitive's), never says a vulgarity the
   person did not, and never denies the person's own act (D-p29-t3 «I do not watch movies…»).
3. False limits: a reply, an answer or a notice to someone is a message to them; someone looked up in the contacts to
   be mailed is the recipient of that mail; what a mail asks someone else to do is its content.
4. The person's own: a genre next to their list names it even with a taste; which alarms are set is read by listing
   them; «what is happening» between two hours, and being free at an hour, are agenda reads of that time.
5. Empty finals: a decided limit whose wording failed any contract is recovered as the limit (D-s064); talk whose
   wording failed is answered by the composer as talk; an hour asked of the forecast has a final (D-s014); the first
   draft that never came still reaches the last resort.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.llm import ConversationReplyContractError
from baxy_mind.semantic import reading as semantic_reading
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.audio import asks_a_timed_silence
from baxy_mind.semantic.messaging import contact_found_then_mailed, message_request_any_channel
from baxy_mind.semantic.notes import agenda_read_request, happening_in_a_span_of_hours
from baxy_mind.semantic.patterns import (
    _music_clause_names_content,
    known_unsupported_effect_request,
    resolve_explicit_clarification_intent,
)
from baxy_mind.semantic.temporal import agenda_window

OPERATIONS = (
    "audio.mute", "calendar.event.list", "calendar.event.create", "email.send", "email.latest.reply", "system.status",
    "media.play.query", "media.play.youtube", "message.recipient.resolve", "message.send", "notification.diagnose",
    "notification.list", "notification.schedule", "system.settings.set", "web.news.headlines", "web.search",
    "weather.current",
)


def _effects(text: str) -> tuple[str, ...] | None:
    found = semantic_reading.read(text, available_operations=OPERATIONS).effects
    return None if found is None else tuple(found.operations)


# ------------------------------------------------------------------ 1. a silence for a span of time


@pytest.mark.parametrize(
    "text",
    [
        "quédate callado un rato",
        "por favor, silencia todo por media hora",
        "mutea por veinte minutos",
        "mute it for a couple of hours",
        "be quiet for a bit please",
        "ponlo en silencio por otra hora",
        "callense por diez minutos",
    ],
)
def test_a_silence_for_a_span_is_the_mute(text: str) -> None:
    assert _effects(text) == ("audio.mute",), text
    assert _explicit_arguments_from_evidence("audio.mute", text) == {"state": True}
    assert asks_a_timed_silence(text)


@pytest.mark.parametrize(
    "text",
    [
        "cállate",  # said alone to BAXY it may be about his voice
        "apaga la luz por dos horas",
        "silencia a Pedro por una hora",
        "cállate la boca",
    ],
)
def test_what_is_no_timed_mute_is_not_read_as_one(text: str) -> None:
    assert _effects(text) != ("audio.mute",), text
    assert not asks_a_timed_silence(text)


def _mute_facts() -> dict:
    situation = {"kind": "operation", "operation": "audio.mute", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": {"muted": True}}
    return {"situation": json.dumps(situation), "operation": "audio.mute", "seen": {"muted": True}}


def test_the_mute_reply_never_promises_the_timer() -> None:
    text = "silencia todo por media hora"
    assert llm.compose_visible_defect("Silencié el sonido por media hora.", "status", text, _mute_facts()) == (
        "timed_mute_promised"
    )
    for reply in (
        "Silencié el sonido; sigue así hasta que me pidas reactivarlo.",
        "Silencié el sonido. No lo reactivo solo cuando pase la media hora.",
    ):
        assert llm.compose_visible_defect(reply, "status", text, _mute_facts()) != "timed_mute_promised", reply
    # A mute with no span is judged as before.
    assert llm.compose_visible_defect("Silencié el sonido por media hora.", "status", "silencia el sonido",
                                      _mute_facts()) != "timed_mute_promised"


# ------------------------------------------------------------------ 2. the wording of a limit


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        ("Eso no lo hago: no silento las alarmas.", "silencia las alarmas de la oficina"),
        ("No recuerdito cumpleaños.", "recuérdame los cumpleaños de mis primos"),
        ("Eso no lo hago: no cago por un rato.", "quédate callado por un rato"),
    ],
)
def test_a_limit_with_a_broken_or_vulgar_verb_is_refused(reply: str, asked: str) -> None:
    assert llm.limit_voice_defect(reply, asked) == "limit_broken_person"
    assert llm._unsupported_answer_contract_failure(reply, asked) == "unsupported_broken_person"


@pytest.mark.parametrize(
    ("reply", "asked"),
    [
        ("No silencio alarmas de otros equipos.", "silencia las alarmas de la oficina"),
        ("No cancelo reuniones.", "cancela mis reuniones del lunes"),
        ("No reproduzco audiolibros.", "reproduce el audiolibro"),
        ("No agendo citas médicas.", "agenda una cita con el dentista"),
        ("Eso no lo hago: no reservo mesas.", "haz una reserva en la cantina"),
    ],
)
def test_a_plain_limit_with_the_verb_asked_passes(reply: str, asked: str) -> None:
    assert llm.limit_voice_defect(reply, asked) == ""


def test_a_vulgarity_the_person_said_first_is_theirs() -> None:
    assert llm.visible_reply_says_a_vulgarity("Eso no lo hago: no cago por un rato.", "quédate callado")
    assert not llm.visible_reply_says_a_vulgarity("No repito «mierda».", "repite mierda")
    # Ordinary words that only look alike are not vulgar.
    assert not llm.visible_reply_says_a_vulgarity("Abrí la computadora en el cono sur.", "")


def test_a_limit_never_denies_the_persons_own_act() -> None:
    # DEV-D v3x D-p29-t3.
    request = "Scary stories sounds great to me. I would like to watch this movie with English subtitles."
    assert llm.limit_voice_defect("I do not watch movies with English subtitles.", request) == "limit_persons_act"
    assert llm.limit_voice_defect("I don't put on movies with subtitles.", request) == ""
    assert llm.limit_voice_defect("No veo series con subtítulos.", "quiero ver la serie con subtítulos") == (
        "limit_persons_act"
    )


# ------------------------------------------------------------------ 3. false limits


@pytest.mark.parametrize(
    "text",
    [
        "respóndele a Marta que llego en diez minutos",
        "puedes contestarle a Raúl que mañana no puedo",
        "reply to Pedro saying I'll be late",
        "reply ok to Pedro",
        "informa a mi equipo que la reunión se pasa al jueves",
        "inform the team that the demo moved",
    ],
)
def test_a_reply_or_a_notice_to_someone_is_a_message(text: str) -> None:
    assert message_request_any_channel(text) is not None, text
    assert _effects(text) == ("message.recipient.resolve", "message.send"), text


@pytest.mark.parametrize(
    "text", ["reply yes to the email", "responde al último correo diciendo que sí", "reply to the last mail saying ok"],
)
def test_a_reply_to_a_mail_is_no_message_to_someone(text: str) -> None:
    assert message_request_any_channel(text) is None, text


@pytest.mark.parametrize(
    "text",
    [
        "look up pedro in my contacts and send him an email",
        "busca a carmen en mis contactos y mándale un correo",
        "encuentra a julián en mi agenda y envíale un correo electrónico",
    ],
)
def test_someone_looked_up_to_be_mailed_is_the_mails_recipient(text: str) -> None:
    assert contact_found_then_mailed(text)
    assert not known_unsupported_effect_request(text, OPERATIONS)
    clarification = resolve_explicit_clarification_intent(text, OPERATIONS)
    assert clarification is not None and clarification.operations == ("email.send",)
    assert clarification.missing_fields == ("to",)
    # The contacts alone stay the limit they were.
    assert known_unsupported_effect_request("busca a carmen en mis contactos", OPERATIONS)


def test_what_a_mail_asks_someone_else_to_do_is_its_content() -> None:
    for text in (
        "mándele un correo a mi secretaria Marta para cancelar las reuniones del viernes",
        "envíale un mail a Tomás para que anule las citas de mañana",
    ):
        assert not known_unsupported_effect_request(text, OPERATIONS), text
        clarification = resolve_explicit_clarification_intent(text, OPERATIONS)
        assert clarification is not None and clarification.operations == ("email.send",), text
    # BAXY's own cancelling of the person's meetings stays the limit.
    assert known_unsupported_effect_request("cancela mis reuniones del viernes", OPERATIONS)


# ------------------------------------------------------------------ 4. the person's own


@pytest.mark.parametrize(
    "clause",
    ["pon mi lista de reproducción de cumbia favorita", "play my favorite blues playlist",
     "pon mi playlist de rock que más me gusta"],
)
def test_a_genre_next_to_the_list_names_content_even_with_a_taste(clause: str) -> None:
    assert _music_clause_names_content(clause), clause


@pytest.mark.parametrize(
    "clause",
    ["pon mi playlist favorita", "pon mis canciones preferidas", "pon mi lista de canciones de siempre",
     "pon mi cantante de jazz favorito",
     # The person's own list named by its purpose is still asked, never searched (tanda 4).
     "play my workout playlist", "pon mi playlist de viaje largo"],
)
def test_how_the_collection_is_qualified_still_names_nothing(clause: str) -> None:
    assert not _music_clause_names_content(clause), clause


@pytest.mark.parametrize(
    "text",
    ["dime qué alarmas tengo puestas", "is there an alarm set for seven", "hay alguna alarma puesta para las ocho",
     "¿tengo alguna alarma para mañana a las seis?", "show me what alarms are active"],
)
def test_which_alarms_are_set_is_read_by_listing_them(text: str) -> None:
    assert _effects(text) == ("notification.list",), text


def test_the_persons_lists_on_the_machine_are_not_its_status() -> None:
    for text in ("qué listas tengo en mi notebook", "which notes are on my laptop"):
        assert _effects(text) != ("system.status",), text
    assert _effects("cómo está mi notebook") == ("system.status",)


def test_without_the_listing_the_alarm_check_keeps_its_diagnosis() -> None:
    from baxy_mind.semantic.patterns import resolve_explicit_effects

    found = resolve_explicit_effects("is there an alarm set for seven", {"notification.diagnose"})
    assert found is not None and found.operations == ("notification.diagnose",)


@pytest.mark.parametrize(
    "text",
    [
        "qué hay entre las tres y las cinco de la tarde",
        "what's going on between two and four this afternoon",
        "qué pasa mañana de diez a doce",
        "what is happening after nine and before eleven",
        "qué está pasando después de las dos y antes de las cuatro",
    ],
)
def test_what_happens_between_two_hours_is_the_agenda(text: str) -> None:
    assert happening_in_a_span_of_hours(llm._reading_fold(text))
    assert _effects(text) == ("calendar.event.list",), text


@pytest.mark.parametrize("text", ["qué pasa hoy en el mundo", "what is happening in Peru", "qué está pasando en Chile"])
def test_what_happens_with_no_hours_is_still_the_news(text: str) -> None:
    assert not happening_in_a_span_of_hours(llm._reading_fold(text))
    assert _effects(text) != ("calendar.event.list",), text


def test_a_span_said_by_its_two_edges_is_that_window() -> None:
    now = datetime(2026, 3, 4, 8, 0)
    start, end = agenda_window("what is happening after nine and before eleven a.m.", now)
    assert (start.hour, end.hour, start.date(), end.date()) == (9, 11, now.date(), now.date())
    start, end = agenda_window("que esta pasando despues de las dos y antes de las cuatro de la tarde", now)
    assert (start.hour, end.hour) == (14, 16)


@pytest.mark.parametrize("text", ["estoy libre a las cinco de la tarde", "am i free at three pm",
                                  "¿estoy ocupado mañana a las nueve?"])
def test_free_or_busy_at_an_hour_is_the_agenda(text: str) -> None:
    assert agenda_read_request(text), text


def test_an_hour_with_no_day_is_read_on_today() -> None:
    now = datetime(2026, 3, 4, 8, 0)
    start, end = agenda_window("estoy libre a las cinco de la tarde", now)
    assert (start, end) == (datetime(2026, 3, 4), datetime(2026, 3, 5))
    # With nothing said, the days ahead, as before.
    start, end = agenda_window("que tengo por venir", now)
    assert start == now and (end - start).days >= 7


# ------------------------------------------------------------------ 5. empty finals


def test_a_decided_limit_whose_wording_failed_any_contract_is_the_limit() -> None:
    # DEV-D v3x D-s064: «shaped_presentation» on a decided limit was recovered as an empty conversation and the App
    # published «No he podido procesar tu solicitud porque no entendí bien tu mensaje».
    error = ConversationReplyContractError("shaped_presentation", "unsupported")
    assert sidecar._turn_failure_kind(error) == sidecar.LIMIT_WORDING_FAILURE
    assert sidecar._turn_failure_kind(ConversationReplyContractError("echo", "knowledge")) == (
        sidecar.CONVERSATION_WORDING_FAILURE
    )


class _Composer:
    """The recovery's composer: what it is asked, and its answer for each intent."""

    def __init__(self, replies: dict[str, str]) -> None:  # noqa: D107
        self.replies = replies
        self.asked: list[str] = []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("an understood turn is not asked what the person wants")

    def compose_user_message(self, _text: str, intent: str, _facts: dict) -> str:
        self.asked.append(intent)
        return self.replies.get(intent, "")


def test_talk_whose_wording_failed_is_answered_as_talk() -> None:
    composer = _Composer({"conversation": "¡Qué bien! Que te vaya genial en la reunión del mediodía."})
    result = sidecar._recover_failed_turn(
        {"id": "m97", "text": "hoy almuerzo con mi jefa a las doce", "history": []},
        composer,
        failure_kinds=(sidecar.CONVERSATION_WORDING_FAILURE, sidecar.CONVERSATION_WORDING_FAILURE),
    )
    assert composer.asked == ["conversation"]
    assert result["kind"] == "conversation" and result["reply"].startswith("¡Qué bien!")


def test_talk_the_composer_cannot_answer_asks_back_instead_of_publishing_nothing() -> None:
    composer = _Composer({"clarification": "¿Quieres que lo anote en tu agenda?"})
    result = sidecar._recover_failed_turn(
        {"id": "m97", "text": "hoy almuerzo con mi jefa a las doce", "history": []},
        composer,
        failure_kinds=(sidecar.CONVERSATION_WORDING_FAILURE, sidecar.CONVERSATION_WORDING_FAILURE),
    )
    assert composer.asked == ["conversation", "clarification"]
    assert result["kind"] == "clarify" and result["question"] == "¿Quieres que lo anote en tu agenda?"


def test_a_talk_reply_that_says_the_message_back_is_not_published() -> None:
    text = "hoy almuerzo con mi jefa a las doce"
    composer = _Composer({"conversation": text})
    result = sidecar._recover_failed_turn(
        {"id": "m97", "text": text, "history": []},
        composer,
        failure_kinds=(sidecar.CONVERSATION_WORDING_FAILURE,),
    )
    assert result.get("reply") != text


def _weather(location: str = "Temuco") -> tuple[dict, dict]:
    seen = {
        "location": location, "temperatureC": 9.4, "apparentC": 7, "humidityPercent": 81, "windKmh": 11.2,
        "precipitationMm": 0, "uvIndex": 0, "weatherCode": 3, "condition": "nublado",
        "today": {"date": "2026-03-04", "weekday": "miércoles", "maxC": 17.5, "minC": 6.5,
                  "rainProbabilityPercent": 20, "uvIndexMax": 4.1, "sunrise": "07:41", "sunset": "20:12"},
    }
    situation = {"kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": {"version": 1, **seen}}
    return situation, {"operation": "weather.current", "seen": seen}


def test_an_hour_asked_of_the_forecast_has_a_final() -> None:
    # DEV-D v3x D-s014 «¿qué previsión de tiempo hay para las cuatro?»: both honest drafts gave today's range and died
    # on missing_state, and no final could pass.
    text = "¿qué previsión de tiempo hay para las cuatro?"
    situation, payload = _weather()
    draft = "No tengo el pronóstico para las cuatro, pero hoy en Temuco irá de 6,5 a 17,5 °C, con 20 % de lluvia."
    assert llm._weather_fact_defect(draft, payload, text) == ""
    final = llm._deterministic_final(situation, payload, text, "es")
    assert "por horas" in final and "Temuco" in final and "17,5" in final
    assert llm._payload_fact_defect(final, payload, text, said=text) == ""


class _Silent(llm.LlmRuntime):
    """A writer that never answers: every post runs out of time."""

    def __init__(self) -> None:  # noqa: D107
        self._gguf = None

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        raise TimeoutError("se agotó el presupuesto de composición")


def test_a_first_draft_that_never_came_still_reaches_the_last_resort() -> None:
    text = "¿qué previsión de tiempo hay para las cuatro?"
    situation, payload = _weather()
    facts = {**payload, "situation": json.dumps(situation, ensure_ascii=False)}
    final = _Silent().compose_user_message(text, "status", facts)
    assert "por horas" in final and "Temuco" in final
