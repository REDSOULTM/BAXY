"""M178 (2026-10-06, App runs v5a–v5d of DEV-D/F/G/H/I): a notice «N antes de <algo de la conversación>», and a clock
that answers BAXY's question about a notice.

The window runs a conversation in one session, so its history is what BAXY really published in that run. Row by row,
where the hour of the event was and what made the turn ask or set another one:

* D-w08-t3 «ponme recordatorio una ora antes d ese partido» (v5b–v5d) after «América juega contra Monterrey el domingo 11
  de octubre de 2026 a las 00:10 hora local.» (v5b/v5c: «a las 00:00»), BAXY's answer read from ESPN → «¿Te gustaría
  que te envíe un recordatorio una hora antes del partido?». The decider restated «…el sábado 10 de octubre de 2026 a
  las 23:10…», right, but the 10th was a date nobody said, so the person's words were the objective; the count of M84
  (``anchored_offset_request``) gave nothing because an hour before 00:10 leaves that day, and M110's guard (a clock of
  the decider's, none in the message) asked. Fixed: a count that crosses midnight moves the day BAXY named with it.
  With no day named, or a day already past, it still gives nothing.
* F-w46-t4 «a las 5 y 40» (v5d) after «bueno, poneme una alarma para ese día bien temprano» → «¿Qué día exacto quieres
  que suene la alarma?», the day being the Saturday of both forecasts. The decider restated «Pon una alarma el sábado 26
  de octubre a las 5:40.»: Saturday and 5:40 said, the 26th not; the fidelity check could not take the date out (no
  preposition leads it), so «a las 5 y 40» alone was the objective and the arguments step asked «¿Cuándo y qué quieres
  que recuerde la alarma?». In v5a–v5c the decider wrote the right date and it was set. Fixed: a date nobody said
  written right after a weekday that was said goes, the weekday stays (``faithful_request``).
* F-w05-t3, F-w18-t3 (every round): the junta's mail and the council tax letter were never read in the App (Outlook not
  set up, file not found), so their moment was never said; asking is right.
* F-w33-t2, I-w26-t2, G-w42-t2, I-w12-t4, H-w45-t2 (v5b–v5d): set at the moment BAXY said less the length (08:30 → 08:00,
  23:30 → 22:30, …), as D78 scores it. Nothing to fix.
* I-w29-t3 (v5d): BAXY said the game was being played already («…which started on Monday…»), no clock; asking is right.
* F-w34-t4 «Venga, ponme el temporizador para lo de pochar» (every round): the recipe the App found says no minutes for
  any step (M175 covers the written answer, «Pocha … unos 20 minutos»); asking is right.

Every phrasing beyond the rows is our own.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.semantic import decider as semantic_decider
from baxy_mind.semantic import temporal
from baxy_mind.semantic.decider import ContextDecision
from test_c03_m148_avisos_eso_y_cuentas import REMINDER, SCHEDULE, _arguments
from test_c03_m152_aviso_antes_de_lo_dicho import _turn

LOCAL = timezone(timedelta(hours=-3))
# Monday 5 October 2026 at 22:36 in Chile (UTC-3), the evening of the v5d runs.
NOW = datetime(2026, 10, 5, 22, 36, tzinfo=LOCAL)
TODAY = NOW.date()


@pytest.fixture(autouse=True)
def _fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    counted = temporal.anchored_offset_request
    monkeypatch.setattr(
        temporal, "anchored_offset_request",
        lambda *args, **kwargs: counted(*args, **{"today": TODAY, **kwargs}),
    )
    normalize = sidecar._normalize_grounded_operation_arguments
    monkeypatch.setattr(
        sidecar, "_normalize_grounded_operation_arguments",
        lambda *args, **kwargs: normalize(*args, **{**kwargs, "now_utc": kwargs.get("now_utc") or NOW}),
    )


def _rings(operation: str, objective: str, said: list[str]) -> datetime:
    arguments_, question = _arguments(operation, objective, said,
                                      schema=SCHEDULE if operation == "notification.schedule" else REMINDER)
    assert question == "" and arguments_ is not None
    return datetime.fromisoformat(arguments_["dueUtc"].replace("Z", "+00:00")).astimezone(LOCAL)


# ------------------------------------------------------------------ 1. a count that crosses midnight (D-w08-t3)

D08 = [
    "cuanto qedo el america anoche", "No lo encontré.",
    "y cuando juega el sigiente",
    "América juega contra Monterrey el domingo 11 de octubre de 2026 a las 00:10 hora local.",
    "ponme recordatorio una ora antes d ese partido",
]
D08_V5C = [*D08[:3], "El siguiente partido del América es contra Monterrey el domingo 11 de octubre de 2026 a las 00:00 "
           "hora local.", D08[-1]]


@pytest.mark.parametrize(
    ("said", "decision", "clock"),
    [
        # v5d as audited: the decider's right restatement, with a date nobody said, and its notice.
        (D08, ContextDecision("Ponme un recordatorio el sábado 10 de octubre de 2026 a las 23:10 para el partido de "
                              "América.", "action", ("notification.schedule",), ""), (23, 10)),
        # The same with a decider that asked.
        (D08, ContextDecision(D08[-1], "clarify", (), ""), (23, 10)),
        # v5b, v5c: «a las 00:00».
        (D08_V5C, ContextDecision("Ponme un recordatorio el sábado 10 de octubre de 2026 a las 23:00 para el partido.",
                                  "action", ("notification.schedule",), ""), (23, 0)),
    ],
)
def test_d_w08_t3_the_hour_before_midnight_is_the_day_before(said: list[str], decision: ContextDecision,
                                                             clock: tuple[int, int]) -> None:
    result = _turn(said, decision)
    assert result["kind"] == "action"
    assert result["objective"] == f"ponme recordatorio el 10 de octubre a las {clock[0]:02d}:{clock[1]:02d} para el partido"
    rings = _rings(result["operation"], result["objective"], said)
    assert (rings.month, rings.day, rings.hour, rings.minute) == (10, 10, *clock)


@pytest.mark.parametrize(
    ("text", "reply", "counted"),
    [
        # Our own: English, a weekday and a date, half an hour before a quarter past midnight.
        ("remind me half an hour before that", "The Lakers play the Suns on Tuesday, October 13 at 00:15.",
         "remind me on 12 October at 23:45"),
        # Spanish, «mañana» at five past midnight: twenty minutes before is tonight.
        ("avísame veinte minutos antes del partido", "Colo-Colo juega mañana a las 00:05 contra la U.",
         "avísame el 5 de octubre a las 23:45 para el partido"),
        # After, not before: an hour after half past eleven is the next day.
        ("ponme una alarma una hora después de eso", "El concierto termina el viernes 9 de octubre a las 23:30.",
         "ponme una alarma el 10 de octubre a las 00:30"),
        # A day of a weekday name: Sunday 11 at 00:30, so Saturday 10 at 23:30.
        ("put an alarm on an hour before kick-off", "Arsenal play Leeds on Sunday at 00:30.",
         "put an alarm on 10 October at 23:30 for the kick-off"),
        # New Year's Eve: the year of the day moved to is the next coming one, not said.
        ("ponme recordatorio una hora antes de ese partido", "Juegan el 1 de enero a las 00:10.",
         "ponme recordatorio el 31 de diciembre a las 23:10 para el partido"),
    ],
)
def test_the_day_moves_with_the_count(text: str, reply: str, counted: str) -> None:
    assert temporal.anchored_offset_request(text, reply, (), today=TODAY) == counted


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        # No day named: which night is meant is not known.
        ("ponme una alarma una hora antes de eso", "El partido es a las 00:30."),
        ("remind me an hour before that", "Kick-off is at 00:30."),
        # The day before today is past.
        ("ponme una alarma una hora antes de eso", "El partido es hoy a las 00:30."),
        # Two days named, as before.
        ("ponme una alarma una hora antes de eso", "Juegan el sábado a las 00:30 y la revancha el martes."),
        # A length of a day or more is no count from a clock.
        ("recuérdame 24 horas antes de eso", "Juegan el sábado 10 de octubre a las 00:30."),
    ],
)
def test_no_day_to_move_gives_no_count(text: str, reply: str) -> None:
    assert temporal.anchored_offset_request(text, reply, (), today=TODAY) is None


@pytest.mark.parametrize(
    ("text", "reply", "earlier", "counted"),
    [
        # What does not change: a count inside the day (I-w26-t2, I-w12-t4, F-w33-t2 as the App lived them).
        ("recuerdame una hora antes de eso", "Juegan el martes 6 de octubre de 2026 a las 23:30 hora local.", (),
         "recuerdame el martes 6 de octubre de 2026 a las 22:30"),
        ("ponem una alarma una hora antes",
         "El próximo partido de Boca Juniors es contra Instituto (Córdoba) el viernes 9 de octubre de 2026 a las 19:30 "
         "hora local en Monumental Presidente Perón.", (),
         "ponem una alarma el viernes 9 de octubre de 2026 a las 18:30"),
        ("Set an alarm for half an hour before kick-off, then",
         "The Arsenal match on Saturday is at 08:30 local time (UTC-03:00).", (),
         "Set an alarm for Saturday at 08:00 for the kick-off, then"),
        # M110: «la junta» found further back in the conversation.
        ("y ponme un recordatorio una hora antes de la junta", "Listo, le dejé escrito a Paula.",
         ("dejale escrito un wsp a la paula", "Es de Paula Rojas, «Junta trabajo»: propone juntarse el jueves a las "
          "19:00 en el café de Plaza Vergara."),
         "ponme un recordatorio el jueves a las 18:00 para la junta"),
    ],
)
def test_a_count_inside_the_day_is_unchanged(text: str, reply: str, earlier: tuple, counted: str) -> None:
    assert temporal.anchored_offset_request(text, reply, earlier, today=TODAY) == counted


def test_with_the_hour_never_said_the_question_stands() -> None:
    # F-w05-t3 as the App lived it: the mail was never read, so the junta has no hour in this conversation.
    lived = [
        "baxy leeme el ultimo correo porfa", "No puedo leer el correo porque Outlook no está configurado en este equipo.",
        "dejale escrito un wsp a la paula que voy pero llego tipo 7 y media, no lo mandes eso si",
        "Se escribió el mensaje en WhatsApp a Paula diciendo que llegas a las siete y media, pero no se confirmó si se "
        "envió o no.",
        "y ponme un recordatorio una hora antes de la junta",
    ]
    assert _turn(lived, ContextDecision(lived[-1], "clarify", (), ""))["kind"] == "clarify"
    # Two matches at different hours: which one is not known (and a decider that summed one is not followed).
    two = ["cuándo juegan", "Juegan el sábado 10 de octubre a las 00:30 y el martes 13 a las 21:00.",
           "ponme recordatorio una hora antes de ese partido"]
    assert temporal.anchored_offset_request(two[-1], two[1], (), today=TODAY) is None
    assert _turn(two, ContextDecision(two[-1], "clarify", (), ""))["kind"] == "clarify"
    # M165: the moment the same message says is the one counted from, never BAXY's.
    assert temporal.anchored_offset_request(
        "tambien tengo una reunion a las 9, recuerdamelo 15 minutos antes de eso",
        "El partido es el domingo 11 de octubre a las 00:10.", (), today=TODAY,
    ) is None


# ------------------------------------------------------------------ 2. the clock that answers BAXY (F-w46-t4)

F46 = [
    "che, cómo va a estar el clima en Mar del Plata el sábado? nos vamos temprano",
    "En Mar del Plata, el sábado: llovizna, de 9,8 a 11,8 °C, 62 % de lluvia.",
    "uh, y en Necochea?",
    "En Necochea, el sábado: nublado, de 9,8 a 12,3 °C, 59 % de lluvia.",
    "bueno, poneme una alarma para ese día bien temprano",
    "¿Qué día exacto quieres que suene la alarma?",
    "a las 5 y 40",
]


def test_f_w46_t4_the_answered_clock_sets_the_saturday_alarm() -> None:
    decision = ContextDecision("Pon una alarma el sábado 26 de octubre a las 5:40.", "action", ("notification.schedule",), "")
    result = _turn(F46, decision)
    assert result["kind"] == "action" and result["operation"] == "notification.schedule"
    assert result["objective"] == "Pon una alarma el sábado a las 5:40."
    rings = _rings("notification.schedule", result["objective"], F46)
    assert (rings.month, rings.day, rings.hour, rings.minute) == (10, 10, 5, 40)


@pytest.mark.parametrize(
    ("request_", "said", "kept"),
    [
        # Our own, English: the weekday of the forecast, a date of the model's.
        ("Set an alarm on Saturday, October 24 at 5:40.",
         ["at 5:40", "what's the weather doing in Leeds on Saturday?", "On Saturday in Leeds: rain, 9 to 12 °C.",
          "set an alarm for that day, early", "What time should it go off?"],
         "Set an alarm on Saturday at 5:40."),
        # Spanish, a reminder: «el jueves» said, «15 de octubre» not (it is the 8th).
        ("Recuérdame el jueves 15 de octubre a las 7:00 llamar a la Pili.",
         ["a las 7", "el jueves tengo que llamar a la Pili, recuérdamelo", "¿A qué hora te lo recuerdo?"],
         "Recuérdame el jueves a las 7:00 llamar a la Pili."),
        # With its year.
        ("Pon una alarma el sábado 26 de octubre de 2026 a las 5:40.", F46[::-1], "Pon una alarma el sábado a las 5:40."),
    ],
)
def test_a_date_of_the_models_after_a_said_weekday_goes(request_: str, said: list[str], kept: str) -> None:
    fidelity = semantic_decider.faithful_request(request_, said[0], said[1:], now=NOW.replace(tzinfo=None))
    assert (fidelity.kind, fidelity.request) == ("trimmed", kept)


@pytest.mark.parametrize(
    ("request_", "said", "kind", "objective"),
    [
        # The right date of a said weekday is said: the restatement is kept whole.
        ("Pon una alarma el sábado 10 de octubre a las 5:40.", F46[::-1], "kept",
         "Pon una alarma el sábado 10 de octubre a las 5:40."),
        # A weekday nobody said, with its date: the person's words, as before.
        ("Pon una alarma el domingo 26 de octubre a las 5:40.", F46[::-1], "person", "a las 5 y 40"),
        # A date nobody said and no weekday: as before.
        ("Pon una alarma el 26 de octubre a las 5:40.", F46[::-1], "person", "a las 5 y 40"),
        # The weekday said, but the clock is the model's: as before.
        ("Set an alarm on Saturday, October 24 at 6:40.",
         ["at 5:40", "what's the weather doing in Leeds on Saturday?", "On Saturday in Leeds: rain, 9 to 12 °C.",
          "set an alarm for that day, early", "What time should it go off?"], "person", "at 5:40"),
    ],
)
def test_what_else_the_fidelity_check_does_is_unchanged(request_: str, said: list[str], kind: str,
                                                        objective: str) -> None:
    fidelity = semantic_decider.faithful_request(request_, said[0], said[1:], now=NOW.replace(tzinfo=None))
    assert (fidelity.kind, fidelity.request) == (kind, objective)


def test_the_answered_clock_as_v5a_lived_it_is_unchanged() -> None:
    # v5a–v5c: the decider wrote the right date; its request stands and rings on Saturday 10 at 05:40.
    decision = ContextDecision("Pon una alarma el sábado 10 de octubre a las 5:40.", "action",
                               ("notification.schedule",), "")
    result = _turn(F46, decision)
    assert result["objective"] == "Pon una alarma el sábado 10 de octubre a las 5:40."
    rings = _rings("notification.schedule", result["objective"], F46)
    assert (rings.month, rings.day, rings.hour, rings.minute) == (10, 10, 5, 40)


def test_f_w34_t4_with_no_length_said_the_timer_is_asked() -> None:
    # The recipe the App found says no minutes for «pochar»: nothing is counted, the question stands (M175 unchanged).
    said = [
        "Oye, ¿cómo se hace una tortilla de patatas para cuatro personas? Con cebolla, eh, que en casa somos de cebolla",
        "Tortilla de patatas con cebolla:\n- 8 huevos grandes\n- 1 kg de patatas\n\nPreparación:\n1. Pelar, lavar y "
        "secar las patatas, freirlas en aceite caliente.\n2. Cortar la cebolla y dorarla en la sartén hasta que esté "
        "transparente.",
        "Guárdamela en una nota que se llame tortilla",
        "He guardado la nota \"tortilla\" con la receta.",
        "Venga, ponme el temporizador para lo de pochar",
    ]
    assert _turn(said, ContextDecision(said[-1], "clarify", (), ""))["kind"] == "clarify"
    assert date(2026, 10, 5) == TODAY
