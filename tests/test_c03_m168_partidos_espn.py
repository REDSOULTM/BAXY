"""M168 (2026-10-05, D77: horarios de partidos desde la API pública de ESPN; App runs v4y-devG, v4y-devH, v4y-devI).

web.search asked only Wikipedia and the news feed when a team plays, and found nothing: G-w42-t1 «when do the Lakers play
next?» → «I could not find when the Lakers play next.», H-w44-t1 «what time does the arsenal match kick off tonight»,
I-w12-t3 «y cuando jeuga de nuevo» (Boca), I-w26-t1 «a que hora juega chile el martes», I-w29-t2 «and when do they play
next». Without the moment in the conversation, the notice that follows was asked instead of set: G-w42-t2 «remind me
half an hour before that», H-w44-t2 «remind me twenty minutes before that», I-w12-t4 «ponem una alarma una hora antes»,
I-w26-t2 «recuerdame una hora antes de eso», I-w29-t3 «put a reminder on an hour ahead of tip-off so I don't miss it».

1. The provider (src/Baxy.Providers.Windows/External/EspnScheduleSource.cs, tested in .NET with ESPN's real answers)
   answers with one English sentence and authority ``espn_public_schedule``. The mind treats it as a structured source:
   the report says it in the person's language, and the weekday, the clock (either dial), the month, «tonight», «de
   visitante» are the read's; a weekday, clock, score or name the read does not give is not, and a start time ESPN has
   not announced (TBD) has no clock.
2. The moment BAXY then said is counted from: «ahead of» is «before»; a length with nothing after it but the end
   («una hora antes») counts from the moment just given when a notice is asked; the start of a match («antes del
   partido», «before tip-off») is the newest line that tells a match, not the notice set for it; «a las 23:30 hora
   local» and «a las 19:30 horas» are 23:30 and 19:30 (they were read 23:00 and 19:00).
3. When the readers do not read the order as written («ponem», «put a reminder») and the decider chose the notice, the
   moment is still the count, not the model's sum.

BAXY's replies below are the ones the composer writes from ESPN's read (our own wording, in the shape of the fixtures of
EspnScheduleSourceTests); every phrasing beyond the rows is our own.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from baxy_mind import llm
from baxy_mind.semantic import temporal
from baxy_mind.semantic.decider import ContextDecision
from test_c03_m148_avisos_eso_y_cuentas import REMINDER, SCHEDULE, _arguments, _local
from test_c03_m152_aviso_antes_de_lo_dicho import _turn

# Monday 5 October 2026, the day ESPN's answers were read (Santiago, UTC-03:00).
TODAY = date(2026, 10, 5)


@pytest.fixture(autouse=True)
def _fixed_day(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_report_today", lambda: TODAY)


def _espn(snippet: str, title: str, query: str) -> dict:
    return {"seen": {"version": 1, "query": query, "count": 1, "authority": "espn_public_schedule",
                     "results": [{"title": title, "url": "https://www.espn.com/nba/game/_/gameId/401898716", "snippet": snippet}]},
            "operation": "web.search"}


LAKERS = _espn("Next game: Los Angeles Lakers play away against Sacramento Kings on Monday 2026-10-05 at 23:00 local "
               "time (UTC-03:00), NBA Preseason, at Golden 1 Center.", "Los Angeles Lakers vs Sacramento Kings",
               "When do the Lakers play next?")
BOCA = _espn("Next match: Boca Juniors play away against Instituto (Córdoba) on Friday 2026-10-09 at 19:30 local time "
             "(UTC-03:00), Argentine Liga Profesional de Fútbol, at Monumental Presidente Perón.",
             "Boca Juniors vs Instituto (Córdoba)", "¿Cuándo juega Boca de nuevo?")
BOCA_TBD = _espn("Next match: Boca Juniors play at home against Talleres (Córdoba) on Sunday 2026-10-18 (the start time "
                 "is still to be announced, TBD), Argentine Liga Profesional de Fútbol, at Alberto José Armando (La "
                 "Bombonera).", "Boca Juniors vs Talleres (Córdoba)", "¿A qué hora juega Boca contra Talleres?")
BOCA_LAST = _espn("Last match: Boca Juniors beat Unión (Santa Fe) 3-0 at home, on Friday 2026-10-02 at 21:30 local time "
                  "(UTC-03:00), Argentine Liga Profesional de Fútbol, at Alberto José Armando (La Bombonera).",
                  "Boca Juniors vs Unión (Santa Fe)", "¿Cómo salió Boca anoche?")
CHILE = _espn("Next match: Chile play away against Mexico on Tuesday 2026-10-06 at 23:30 local time (UTC-03:00), "
              "International Friendly, at Los Angeles Memorial Coliseum.", "Chile vs Mexico",
              "¿A qué hora juega Chile el martes?")
G42 = "when do the Lakers play next? my buddy wants to come over and watch it"
I12 = "y cuando jeuga de nuevo"
I26 = "a que hora juega chile el martes"


# ------------------------------------------------------------------ 1. the report of ESPN's read


@pytest.mark.parametrize(
    ("payload", "said", "draft"),
    [
        # G-w42-t1, H-w23-t4, in English and on either dial, «tonight» for today's date.
        (LAKERS, G42, "The Lakers play the Sacramento Kings on Monday at 23:00."),
        (LAKERS, G42, "The Lakers play the Kings tonight, Monday, at 11:00 pm."),
        (LAKERS, G42, "Next up, the Lakers visit the Kings on Monday, October 5 at 11 pm."),
        (LAKERS, "ok who are the lakers playing tonight", "Tonight the Lakers play the Sacramento Kings at 11 pm."),
        # I-w12-t3, I-w26-t1 in Spanish: the weekday, the month, «de visitante», «hora local» are the read's.
        (BOCA, I12, "Boca juega el viernes 9 de octubre a las 19:30 contra Instituto, de visitante."),
        (BOCA, I12, "Boca juega el viernes a las 19:30 contra Instituto en Córdoba."),
        (CHILE, I26, "Chile juega el martes a las 23:30 contra México, en Los Ángeles."),
        (CHILE, I26, "Chile juega el martes a las 23:30 hora local contra México."),
        # A start time not announced yet, said so; I-w12-t1 the last result.
        (BOCA_TBD, "a q hora juega boca contra talleres",
         "Boca recibe a Talleres el domingo 18 de octubre; la hora aún no se ha anunciado."),
        (BOCA_LAST, "che como salio boca anoche?", "Boca le ganó 3 a 0 a Unión en la Bombonera el viernes."),
        (BOCA_LAST, "che como salio boca anoche?", "Boca le ganó 3-0 a Unión de Santa Fe el viernes."),
    ],
)
def test_the_match_read_is_said_in_the_persons_words(payload: dict, said: str, draft: str) -> None:
    assert llm._payload_fact_defect(draft, payload, said, said=said) == ""


@pytest.mark.parametrize(
    ("payload", "said", "draft", "unread"),
    [
        # The written answer of G-w42-t2's history, over another read: another rival, another day.
        (LAKERS, G42, "The Lakers play the Nuggets on Friday at 22:30.", "friday"),
        (LAKERS, G42, "The Lakers play the Kings on Monday at 22:00.", "at 22:00"),
        (LAKERS, "ok who are the lakers playing tonight", "Tonight the Lakers play the Golden State Warriors at 11 pm.",
         "warriors"),
        # A translated sentence was judged only by its numbers: the weekday and the rival are judged too.
        (BOCA, I12, "Boca juega el sábado a las 19:30 contra Instituto.", "sabado"),
        (BOCA, I12, "Boca juega el viernes a las 20:30 contra Instituto.", "a las 20:30"),
        (CHILE, I26, "Chile juega el martes a las 23:30 contra Perú.", "peru"),
        # No clock when ESPN gave none; no other score, no other result.
        (BOCA_TBD, "a q hora juega boca contra talleres", "Boca recibe a Talleres el domingo 18 de octubre a las 15:00.",
         "a las 15:00"),
        (BOCA_LAST, "che como salio boca anoche?", "Boca le ganó 2 a 0 a Unión el viernes.", "2 a 0"),
        (BOCA_LAST, "che como salio boca anoche?", "Boca perdió con Unión el viernes.", "perdio"),
    ],
)
def test_what_the_read_does_not_give_is_unsourced(payload: dict, said: str, draft: str, unread: str) -> None:
    assert llm._payload_fact_defect(draft, payload, said, said=said) == "search_report_unsourced_claim"
    assert unread in llm._search_report_unsourced_words(draft, payload, said)


def test_a_weekday_the_person_said_may_be_said_back() -> None:
    # «¿Juega Chile el lunes?» answered with the match on Tuesday: the person's Monday is theirs to repeat.
    draft = "Chile no juega el lunes; juega el martes a las 23:30 contra México."
    assert llm._match_report_unread(draft, CHILE, "¿juega chile el lunes?") == []


def test_espn_is_a_structured_source() -> None:
    assert "espn_public_schedule" in llm._SEARCH_STRUCTURED_AUTHORITIES
    # Its one result is about the team by construction: never «no pertinent result».
    draft = "Boca juega el viernes a las 19:30 contra Instituto."
    assert not llm._search_report_from_no_pertinent_result(draft, BOCA, I12)


def test_another_source_is_judged_as_before() -> None:
    # What does not change: Wikipedia («¿quién es LeBron?»), the news feed («noticias del Barça»), Frankfurter («¿cuánto
    # está el dólar?») have no match read, and nothing of the match's is added to their grounds.
    wikipedia = {"seen": {"query": "¿Quién es LeBron James?", "count": 1, "authority": "wikipedia_es_api", "results": [
        {"title": "LeBron James", "url": "https://es.wikipedia.org/wiki/LeBron_James",
         "snippet": "LeBron Raymone James (Akron, 30 de diciembre de 1984) es un jugador de baloncesto estadounidense."}]},
        "operation": "web.search"}
    news = {"seen": {"query": "noticias del Barça", "count": 1, "authority": "google_news_rss_search", "results": [
        {"title": "El Barça gana en Montjuïc", "url": "https://news.google.com/rss/articles/x",
         "snippet": "Mundo Deportivo, Sun, 04 Oct 2026 20:00:00 GMT"}]}, "operation": "web.search"}
    rate = {"seen": {"query": "¿Cuánto está el dólar?", "count": 1, "authority": "frankfurter_reference_rates", "results": [
        {"title": "1 USD = 981.19 CLP", "url": "https://api.frankfurter.dev/v2/rates",
         "snippet": "Reference rate on 2026-10-02: 1 USD = 981.19 CLP."}]}, "operation": "web.search"}
    for payload in (wikipedia, news, rate):
        assert llm._match_reads(payload) == [] and llm._match_report_grounds(payload) == ""
        assert llm._match_report_unread("El sábado a las 15:00 contra Perú.", payload, "") == []
    # The Frankfurter report of M146 still passes, and a wrong figure still does not.
    said = "oye, ¿me podrias decir a como anda el dolar hoy?"
    assert llm._payload_fact_defect("Hoy el dólar está a 981.19 pesos chilenos.", rate, said, said=said) == ""
    assert llm._payload_fact_defect("Hoy el dólar está a 975 pesos chilenos.", rate, said, said=said) \
        == "search_report_unsourced_claim"


# ------------------------------------------------------------------ 2. the moment said back is counted from


def test_a_clock_with_its_minutes_is_not_a_length() -> None:
    def read(text: str) -> list[tuple[int, int]]:
        return [(clock.hour, clock.minute) for clock in temporal.spoken_clocks(llm._reading_fold(text))]

    assert read("Chile juega el martes a las 23:30 hora local contra México.") == [(23, 30)]
    assert read("América juega el sábado a las 19:30 horas contra Necaxa.") == [(19, 30)]
    assert read("kick-off at 15:45 local time") == [(15, 45)]
    # What does not change: a length is no clock, with or without «a las».
    assert read("a las dos horas de empezar") == []
    assert read("ponme una alarma en 2 horas") == []
    assert read("at five minutes past the hour") == []
    assert read("América juega el sábado a las 21:00 horas contra Necaxa.") == [(21, 0)]


@pytest.mark.parametrize(
    ("text", "reply", "earlier", "counted"),
    [
        # G-w42-t2, H-w44-t2, I-w26-t2 with the moment ESPN gave.
        ("remind me half an hour before that", "The Lakers play the Sacramento Kings on Monday at 23:00.", (),
         "remind me on Monday at 22:30"),
        ("remind me twenty minutes before that", "Arsenal host Leeds United on Saturday at 08:30.", (),
         "remind me on Saturday at 08:10"),
        ("recuerdame una hora antes de eso", "Chile juega el martes a las 23:30 hora local contra México.", (),
         "recuerdame el martes a las 22:30"),
        # I-w12-t4: bare, at the end of the message.
        ("ponem una alarma una hora antes", "Boca juega el viernes 9 de octubre a las 19:30 contra Instituto, de visitante.",
         (), "ponem una alarma el viernes 9 de octubre a las 18:30"),
        ("remind me an hour before.", "The Lakers play the Kings on Monday at 23:00.", (), "remind me on Monday at 22:00."),
        # I-w29-t3: «ahead of tip-off», the line that tells the game.
        ("put a reminder on an hour ahead of tip-off so I don't miss it", "The Lakers play the Kings on Monday at 23:00.",
         (), "put a reminder on Monday at 22:00 for the tip-off so I don't miss it"),
        # I-w12-t5: «antes del partido» after the alarm set for it counts from the match, not from the alarm.
        ("uh no, correla a 30 min antes del partido asi llego del laburo",
         "Listo, alarma el viernes 9 de octubre a las 18:30 para el partido de Boca.",
         ("ponem una alarma una hora antes", "Boca juega el viernes 9 de octubre a las 19:30 contra Instituto, de visitante."),
         "uh no, correla a el viernes 9 de octubre a las 19:00 para el partido asi llego del laburo"),
        # What does not change: M84's «ese partido», M110's «la junta» and «kick-off» said in the line.
        ("ponme recordatorio una ora antes d ese partido", "América juega el sábado a las 21:00 contra Necaxa.", (),
         "ponme recordatorio el sábado a las 20:00 para el partido"),
        ("Set an alarm for half an hour before kick-off, then",
         "Arsenal host Brentford on Saturday, kick-off 15:00 at the Emirates.", (),
         "Set an alarm for Saturday at 14:30 for the kick-off, then"),
    ],
)
def test_the_moment_baxy_gave_is_counted_from(text: str, reply: str, earlier: tuple, counted: str) -> None:
    assert temporal.anchored_offset_request(text, reply, earlier) == counted


@pytest.mark.parametrize(
    ("text", "reply"),
    [
        # A notice moved earlier or later is a move, not a count from the reply.
        ("make it ten minutes earlier", "Listo, alarma a las 7:00."),
        ("y ponla media hora antes", "Listo, alarma a las 7:00."),
        # A bare length that asks no notice.
        ("una hora antes", "Boca juega el viernes a las 19:30."),
        ("salgo una hora antes", "Boca juega el viernes a las 19:30."),
        # A bare length after a reply with no single moment.
        ("ponme una alarma una hora antes", "No encontré cuándo juega Boca."),
        ("ponme una alarma una hora antes", "Boca juega el viernes a las 19:30 y el martes a las 21:00."),
    ],
)
def test_no_count_where_nothing_is_pointed_at(text: str, reply: str) -> None:
    assert temporal.anchored_offset_request(text, reply, ()) is None


# ------------------------------------------------------------------ 3. the rows, turn by turn


LIVED_WITH_ESPN = {
    "G-w42-t2": ([G42, "The Lakers play the Sacramento Kings on Monday at 23:00.", "remind me half an hour before that"],
                 (22, 30)),
    "H-w44-t2": (["what time does the arsenal match kick off tonight", "Arsenal host Leeds United on Saturday at 08:30.",
                  "remind me twenty minutes before that"], (8, 10)),
    "I-w26-t2": ([I26, "Chile juega el martes a las 23:30 hora local contra México.", "recuerdame una hora antes de eso"],
                 (22, 30)),
}


@pytest.mark.parametrize("row", sorted(LIVED_WITH_ESPN))
def test_the_notice_after_the_match_is_set_at_the_count(row: str) -> None:
    said, clock = LIVED_WITH_ESPN[row]
    # As in the App runs, the decider asked for the time; the count from BAXY's answer is the request.
    result = _turn(said, ContextDecision(said[-1], "clarify", (), ""))
    assert result["kind"] == "action"
    schema = SCHEDULE if result["operation"] == "notification.schedule" else REMINDER
    arguments_, question = _arguments(result["operation"], result["objective"], said, schema=schema)
    assert question == "" and (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == clock


I12_LIVED = [
    "che como salio boca anoche?", "Boca le ganó 3 a 0 a Unión el viernes en la Bombonera.",
    I12, "Boca juega el viernes 9 de octubre a las 19:30 contra Instituto, de visitante.",
    "ponem una alarma una hora antes",
]
I29_LIVED = [
    "hey did the Lakers pull it off last night? I fell asleep in the third",
    "I couldn't find whether the Lakers won last night.",
    "and when do they play next", "The Lakers play the Sacramento Kings on Monday at 23:00.",
    "put a reminder on an hour ahead of tip-off so I don't miss it",
]


@pytest.mark.parametrize(
    ("said", "decision", "objective"),
    [
        # I-w12-t4: the decider chose the alarm and restated the count, or summed it wrong; the count is the request.
        (I12_LIVED, ContextDecision("Ponme una alarma una hora antes del partido de Boca.", "action",
                                    ("notification.schedule",), ""),
         "ponem una alarma el viernes 9 de octubre a las 18:30"),
        (I12_LIVED, ContextDecision("Ponme una alarma el viernes 9 de octubre a las 19:00.", "action",
                                    ("notification.schedule",), ""),
         "ponem una alarma el viernes 9 de octubre a las 18:30"),
        # I-w29-t3.
        (I29_LIVED, ContextDecision("Set a reminder an hour before the Lakers tip-off.", "action", ("reminder.create",), ""),
         "put a reminder on Monday at 22:00 for the tip-off so I don't miss it"),
        # The decider's own request that says the counted moment stands (M144).
        (I12_LIVED, ContextDecision("Ponme una alarma el viernes 9 de octubre a las 18:30 para el partido de Boca.",
                                    "action", ("notification.schedule",), ""),
         "Ponme una alarma el viernes 9 de octubre a las 18:30 para el partido de Boca."),
    ],
)
def test_an_order_the_readers_do_not_read_keeps_the_count(said: list[str], decision: ContextDecision,
                                                         objective: str) -> None:
    result = _turn(said, decision)
    assert result["kind"] == "action" and result["objective"] == objective


def test_i_w12_t4_rings_at_half_past_six() -> None:
    arguments_, question = _arguments("notification.schedule", "ponem una alarma el viernes 9 de octubre a las 18:30",
                                      I12_LIVED, schema=SCHEDULE)
    assert question == "" and arguments_["kind"] == "alarm"
    assert (_local(arguments_["dueUtc"]).month, _local(arguments_["dueUtc"]).day) == (10, 9)
    assert (_local(arguments_["dueUtc"]).hour, _local(arguments_["dueUtc"]).minute) == (18, 30)


def test_with_no_moment_the_question_stands() -> None:
    # What does not change: the conversation as the App lived it (nothing found), and the same order with no conversation.
    lived = [G42, "I could not find when the Lakers play next.", "remind me half an hour before that"]
    assert _turn(lived, ContextDecision(lived[-1], "clarify", (), ""))["kind"] == "clarify"
    alone = ["ponme una alarma una hora antes"]
    assert _turn(alone, ContextDecision(alone[-1], "clarify", (), ""))["kind"] == "clarify"
    lived_es = [I12, "No encontré cuándo juega Boca de nuevo.", "ponem una alarma una hora antes"]
    result = _turn(lived_es, ContextDecision("Ponme una alarma una hora antes.", "action", ("notification.schedule",), ""))
    assert result["objective"] != "ponem una alarma el viernes 9 de octubre a las 18:30"


def test_the_payload_receipt_shape_is_the_providers() -> None:
    # The receipt the .NET provider writes (ExternalAdaptersTests.WhenATeamPlaysIsAnsweredByEspnsCalendar) as the mind
    # receives it: its authority and the one sentence the moment is read from.
    observed = json.loads(json.dumps(LAKERS["seen"]))
    assert observed["authority"] == "espn_public_schedule"
    assert llm._match_reads(LAKERS) == [("monday", date(2026, 10, 5), (23, 0))]
    assert llm._match_reads(BOCA_TBD) == [("sunday", date(2026, 10, 18), None)]
