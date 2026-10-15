"""M93 (2026-09-30, independent review of the official-window DEV-D run v3u, HEAD 30861483): the rows v3r had right and
v3u broke, and the reviewer's remaining wording and code rows.

Evidence: %LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3u-devD/ (REVIEW.reviewed.jsonl, RUN.jsonl,
compose-audit.jsonl, turn-audit.jsonl, events.jsonl; trace = «t» + ordinal), the rows replayed here kept in
tests/data/c03_m93_v3u_evidence.json. Each test replays the recorded message, the decider's recorded restatement, the
recorded draft and payload the composer judged, or the mind reply the App refused:

1. Search reports: a headline retold with its complement as the one who acts (s021), an undated page's «mañana» said as
   the person's tomorrow (s027), the article named in the passive (s061), a report that only says back the request
   (w06-t4).
2. Reports of an act: a minimize told as a close (s062), a reminder still to ring told as already rung (w18-t4).
3. Weather: the hour asked with no forecast by the hour (s014), today's sunset said of tomorrow (s054).
4. Wording: a limit whose explanation says one act is not another (p02-t1), an English plural on a Spanish noun
   (s042), an invented subjunctive glued to «venga» (w11-t1), a question that offers back the one named (s053).
5. The conversation reply the App refuses as internal_code is refused by the mind first (p31-t2, p35-t3), and how BAXY
   did what it wrote in the conversation is no effect claim (p35-t2).
6. Moments: the passed clock of today asked again saying why (s104); the decider's title in front of a said name
   (w08-t2); the thing a counted moment points at stays, and a date with its own weekday is read (w08-t3).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from baxy_mind import visible_defect
from baxy_mind import conversation_contract
from baxy_mind import reply_claims
from baxy_mind import unsupported_answers
from baxy_mind import limit_voice
from baxy_mind import failure_wording
from baxy_mind import payload_fact_checks
from baxy_mind import weather_facts
from baxy_mind import reply_language_checks
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic.arguments import _canonical_due_utc, _explicit_arguments_from_evidence
from baxy_mind.semantic.decider import faithful_request
from baxy_mind.semantic.dialogue import offers_back_the_named_one
from baxy_mind.semantic.temporal import anchored_offset_request, moment_then_title_reminder
from baxy_mind.semantic.web import weather_asked_clock
from baxy_mind import turn_recovery
from baxy_mind import direct_arguments
from baxy_mind import search_report
from baxy_mind import llm_compose


# Every mind module whose code reads the day a search report is judged on: it is patched in each one.
_REPORT_DAY_READERS = (llm_compose, search_report)

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m93_v3u_evidence.json").read_text(encoding="utf-8"))
TURNS = EVIDENCE["turns"]
RUN_DAY = date(2026, 9, 30)  # the day of the run (events.jsonl: 19:18–19:39 local)


def _draft(ident: str, stage: str) -> dict:
    return next(row for row in TURNS[ident]["drafts"] if row["stage"] == stage)


def _search_payload(row: dict) -> dict:
    payload = row["payload"]
    if "seen" in payload:
        return payload
    # The partial report's own payload: the pertinent results with their text.
    return {"operation": "web.search", "seen": {"results": [
        {"title": item["title"], "snippet": item["text"]} for item in payload["results"]
    ]}}


# ------------------------------------------------------------------ 1. search reports


def test_d_s021_a_headline_keeps_who_does_what() -> None:
    row = _draft("D-s021", "first")
    payload = row["payload"]
    assert "Alemania, campeona del mundo, criticó a Jürgen Klopp" in row["draft"]
    assert search_report._search_report_moves_the_subject(row["draft"], payload) == "Alemania"
    assert payload_fact_checks._payload_fact_defect(row["draft"], payload, TURNS["D-s021"]["text"]) == (
        "search_report_moves_the_subject"
    )
    # Quoted whole, or retold with the one who acts, it is the headline.
    for kept in (
        "«Campeón del mundo con Alemania critica a Jürgen Klopp».",
        "Un campeón del mundo con Alemania critica a Jürgen Klopp.",
        "Dos chilenas fueron elegidas entre las 100 figuras emergentes más influyentes del mundo según revista Time.",
    ):
        assert search_report._search_report_moves_the_subject(kept, payload) == "", kept


def test_d_s027_an_undated_pages_tomorrow_is_no_known_day(monkeypatch: pytest.MonkeyPatch) -> None:
    for module in _REPORT_DAY_READERS:
        monkeypatch.setattr(module, "_report_today", lambda: RUN_DAY)
    row = _draft("D-s027", "first")
    payload = row["payload"]
    snippet = payload["seen"]["results"][0]["snippet"]
    assert "mañana" in snippet and "Pittsburg" in snippet
    assert search_report._search_report_undated_relative_day(row["draft"], payload) == "manana"
    assert payload_fact_checks._payload_fact_defect(row["draft"], payload, TURNS["D-s027"]["text"]) == "search_report_undated_day"
    # The same page with the date of tomorrow written in it gives the day.
    dated = json.loads(json.dumps(payload))
    dated["seen"]["results"][0]["snippet"] = snippet.replace("mañana", "mañana 1 de octubre", 1)
    assert search_report._search_report_undated_relative_day(row["draft"], dated) == ""
    # «de la mañana» is a part of the day, and a sentence with no relative day claims none.
    assert search_report._search_report_undated_relative_day(
        "Hay un evento gratuito en 6th Street & Broadway a las 10 de la mañana.", payload,
    ) == ""


def test_d_s061_the_article_named_in_the_passive_is_the_search_shown() -> None:
    row = _draft("D-s061", "partial_after_not_found")
    assert "como se menciona en el artículo revisado por Nicholas Ferraro" in row["draft"]
    payload = _search_payload(row)
    assert search_report._search_report_shows_the_search(row["draft"], payload, TURNS["D-s061"]["text"])
    # What the page states, said directly, stays: «cientos de miles de empleados» is in its text.
    assert not search_report._search_report_shows_the_search(
        "Sí, McDonald's tiene cientos de miles de empleados en Estados Unidos.", payload, TURNS["D-s061"]["text"],
    )
    for shown in ("As stated in the article, McDonald's has hundreds of thousands of employees.",
                  "Según se indica en la página, hay cientos de miles de empleados."):
        assert search_report._search_report_shows_the_search(shown, payload, TURNS["D-s061"]["text"]), shown


def test_d_w06_t4_a_report_that_only_says_back_the_request() -> None:
    row = _draft("D-w06-t4", "retry")
    payload = row["payload"]
    text = TURNS["D-w06-t4"]["text"]
    assert row["draft"] == "Las pizzerías abiertas están cerca de Curico."
    assert "ERRAZURIZ 2970" in json.dumps(payload, ensure_ascii=False)
    assert search_report._search_report_echoes_the_ask(row["draft"], payload, text)
    assert payload_fact_checks._payload_fact_defect(row["draft"], payload, text) == "search_report_echoes_the_ask"
    assert not search_report._search_report_echoes_the_ask(
        "Giuseppe es una pizzería de Curicó, en Errázuriz 2970.", payload, text,
    )
    # A yes-or-no question answered with its own words is an answer.
    assert not search_report._search_report_echoes_the_ask(
        "Las pizzerías abiertas están cerca de Curico.", payload, "¿hay pizzerías abiertas cerca?",
    )


# ------------------------------------------------------------------ 2. reports of an act


def test_d_s062_a_failed_minimize_is_not_told_as_a_close() -> None:
    row = _draft("D-s062", "retry")
    payload = row["payload"]
    assert payload["reason"]["operation"] == "window.minimize.all"
    assert payload_fact_checks._report_changes_the_act(row["draft"], payload) == "close"
    assert payload_fact_checks._payload_fact_defect(row["draft"], payload, TURNS["D-s062"]["text"]) == "report_changes_the_act"
    assert payload_fact_checks._report_changes_the_act("No pude minimizar las ventanas porque la verificación falló.", payload) == ""
    # A close that says it closed, or an open that says it opened, is its own act.
    closed = {"outcome": "failed", "reason": {"operation": "app.close", "cause": "x"}}
    assert payload_fact_checks._report_changes_the_act("No pude cerrar Spotify.", closed) == ""
    assert payload_fact_checks._report_changes_the_act("Ya estaba abierta la app de Fotos.", {"operation": "app.open", "seen": {}}) == ""


def test_d_w18_t4_a_reminder_still_to_ring_is_not_told_as_rung() -> None:
    row = _draft("D-w18-t4", "first")
    payload = row["payload"]
    assert row["draft"] == "Te he recordado para que tomes un descanso a las 20:23."
    assert payload_fact_checks._payload_fact_defect(row["draft"], payload, TURNS["D-w18-t4"]["text"]) == "schedule_told_as_rung"
    for future in ("Te recordaré que tomes un descanso a las 20:23.", "I'll remind you to take a break at 20:23.",
                   "Listo, a las 20:23 te aviso para que tomes un descanso."):
        assert not payload_fact_checks._schedule_told_as_rung(future, payload), future
    assert payload_fact_checks._schedule_told_as_rung("I reminded you to take a break at 20:23.", payload)


# ------------------------------------------------------------------ 3. weather


def test_d_s014_the_hour_asked_is_said_not_read() -> None:
    text = TURNS["D-s014"]["text"]
    row = _draft("D-s014", "retry")
    payload = row["payload"]
    assert weather_asked_clock(text) == "las cuatro"
    assert weather_facts._weather_fact_defect(row["draft"], payload, text) == "missing_state"
    assert "las cuatro" in weather_facts._weather_focus(text, english=False)
    said = "No tengo el pronóstico por hora; en Curicó ahora hace 16.8 °C y está nublado."
    assert weather_facts._weather_fact_defect(said, payload, text) == ""
    # No clock, or the sun's own time asked: nothing new is required.
    for other in ("¿qué tiempo hace?", "¿a qué hora se pone el sol?", "clima de mañana en Lima"):
        assert weather_asked_clock(other) is None, other


def test_d_s054_todays_sunset_is_not_tomorrows() -> None:
    text = TURNS["D-s054"]["text"]
    row = _draft("D-s054", "first")
    payload = row["payload"]
    assert set(payload["seen"]) >= {"today"} and "tomorrow" not in payload["seen"]
    assert weather_facts._weather_fact_defect(row["draft"], payload, text) == "weather_wrong_day"
    assert weather_facts._weather_fact_defect("Hoy en Curicó el sol se pondrá a las 19:48.", payload, text) == ""
    assert weather_facts._weather_fact_defect("En Curicó el sol se pone a las 19:48 de la tarde.", payload, text) == ""


# ------------------------------------------------------------------ 4. wording


def test_d_p02_t1_one_act_said_not_to_be_another_explains_nothing() -> None:
    text = TURNS["D-p02-t1"]["text"]
    published = TURNS["D-p02-t1"]["published"]
    assert published == "No saco fotos: sacar una foto no es tomarla yo."
    assert limit_voice.limit_voice_defect(published, text) == "limit_act_is_not_act"
    assert unsupported_answers._unsupported_answer_contract_failure(published, text) == "unsupported_limit_act_is_not_act"
    # The limits the reviewer accepted in v3r stay.
    for kept, request in (
        ("No saco fotos: sacar fotos no es lo que hago ahora.", text),
        ("I do not take videos: recording a video in two minutes is not something I do.", "record a video in 2 min"),
        ("Eso no lo hago: los hábitos no los llevo yo.", "márcame el hábito de hoy"),
    ):
        assert limit_voice.limit_voice_defect(kept, request) != "limit_act_is_not_act", kept


def test_d_s042_a_spanish_noun_keeps_its_spanish_plural() -> None:
    text = TURNS["D-s042"]["text"]
    published = TURNS["D-s042"]["published"]
    assert published == "No encargo pastels ni panaderías."
    assert reply_language_checks.visible_reply_breaks_spanish_plural(published, text)
    assert unsupported_answers._unsupported_answer_contract_failure(published, text) == "unsupported_broken_plural"
    for kept in ("No encargo pasteles de camote a panaderías.", "No encargo el pastel de camote."):
        assert not reply_language_checks.visible_reply_breaks_spanish_plural(kept, text), kept
    assert not reply_language_checks.visible_reply_breaks_spanish_plural("I don't order pastels.", "order a pastel")
    assert not reply_language_checks.visible_reply_breaks_spanish_plural("Tienes 3 emails nuevos.", "lee mi email")


def test_d_w11_t1_an_invented_subjunctive_is_invented() -> None:
    row = _draft("D-w11-t1", "retry")
    assert row["draft"].endswith("probabilidad de que llovenga.")
    assert reply_language_checks.visible_reply_invents_a_spanish_infinitive(row["draft"])
    assert visible_defect.compose_visible_defect(row["draft"], "status", TURNS["D-w11-t1"]["text"], {}) == "invented"
    for real in ("tenga", "venga", "mantenga", "convengan", "obtengas", "provenga", "intervengamos", "detenga"):
        assert not reply_language_checks._invented_tener_venir_subjunctive(real), real
    assert not reply_language_checks.visible_reply_invents_a_spanish_infinitive("Mañana hay un 100% de probabilidad de que llueva.")


def test_d_s053_a_question_that_offers_back_the_one_named_asks_nothing() -> None:
    text = TURNS["D-s053"]["text"]
    question = TURNS["D-s053"]["reply"]
    assert question == "¿Te refieres a Miguel o a alguien más?"
    assert offers_back_the_named_one(question, text)
    assert not turn_recovery._recovery_question_is_valid(question, text)
    assert turn_recovery._recovery_question_is_valid("¿Qué Miguel?", text)
    assert not offers_back_the_named_one("¿Te refieres a Miguel Pérez o a otro?", text)
    assert offers_back_the_named_one("Do you mean Miguel or someone else?", text)


# ------------------------------------------------------------------ 5. conversation replies


@pytest.mark.parametrize("ident", ["D-p31-t2", "D-p35-t3"])
def test_the_reply_the_app_refused_is_refused_by_the_mind(ident: str) -> None:
    refused = TURNS[ident]["app_rejected"]
    assert refused["rejection"] == "internal_code"
    assert conversation_contract.conversation_reply_speaks_of_the_system(refused["reply"], TURNS[ident]["text"])
    assert conversation_contract._shaped_conversation_answer_violates_contract(refused["reply"], TURNS[ident]["text"], None)
    # What the App published instead came from a bare conversation payload.
    assert TURNS["D-p35-t3"]["terminal"] == "composition_failed"
    assert not conversation_contract.conversation_reply_speaks_of_the_system(
        "No puedo asegurarlo al cien por cien: lo que te dije sale de lo que sé, así que conviene contrastarlo.",
        TURNS[ident]["text"],
    )


def test_d_p35_t2_how_baxy_did_what_it_wrote_is_no_effect_claim() -> None:
    text = TURNS["D-p35-t2"]["text"]
    assert TURNS["D-p35-t2"]["reply"].startswith("No entendí bien tu pregunta")
    prior = (TURNS["D-p35-t2"]["history"][0]["content"],)
    told = "Lo hice repasando las fortalezas, debilidades, oportunidades y amenazas de Adidas con un tono casual."
    assert reply_claims.conversation_world_claim(told, text, prior) == ""
    assert not conversation_contract._shaped_conversation_answer_violates_contract(told, text, None, prior_requests=prior)
    # After a request on the PC, «lo hice» is still an effect nothing ran.
    assert reply_claims.conversation_world_claim("Lo hice abriendo Spotify.", text, ("abre spotify",)) == "effect_claim"


# ------------------------------------------------------------------ 6. moments


def _tool(name: str) -> dict:
    return {"type": "function", "function": {
        "name": name.replace(".", "_"), "canonical_name": name, "description": "Operación del catálogo.",
        "parameters": {"type": "object", "properties": {"dueUtc": {"type": "string"}, "kind": {"type": "string"},
                                                        "title": {"type": "string"}},
                       "required": ["dueUtc", "kind", "title"], "additionalProperties": False},
    }}


CHILE = timezone(timedelta(hours=-3))
RUN_NOW = datetime(2026, 9, 30, 19, 23, tzinfo=CHILE)  # events.jsonl native-312: «Programa una alarma…» at 19:23:49


def test_d_s104_the_passed_clock_is_asked_again_saying_why() -> None:
    text = TURNS["D-s104"]["text"]
    assert TURNS["D-s104"]["reply"] == "¿A qué día o hora diferente te gustaría que suene la alarma?"
    runtime = object.__new__(LlmRuntime)
    runtime.formulate_missing_argument_question = MagicMock(side_effect=[
        TURNS["D-s104"]["reply"], "Las 18:00 de hoy ya pasaron: ¿a qué otra hora o qué día suena la alarma?",
    ])
    question = direct_arguments._unschedulable_time_question(
        runtime, "notification.schedule", text, text, _tool("notification.schedule"), "es", now=RUN_NOW,
    )
    assert question == "Las 18:00 de hoy ya pasaron: ¿a qué otra hora o qué día suena la alarma?"
    retry = runtime.formulate_missing_argument_question.call_args_list[1].kwargs["ask_as"]["dueUtc"]
    assert TURNS["D-s104"]["reply"] in retry and "already passed" in retry
    # A question that says why is asked once.
    runtime.formulate_missing_argument_question = MagicMock(return_value="Las 18:00 ya pasaron, ¿a qué hora la pongo?")
    direct_arguments._unschedulable_time_question(
        runtime, "notification.schedule", text, text, _tool("notification.schedule"), "es", now=RUN_NOW,
    )
    assert runtime.formulate_missing_argument_question.call_count == 1


def test_d_w08_t2_a_title_the_decider_put_before_a_said_name_goes() -> None:
    # turn-audit (request 1462): decider «¿Cuándo juega el Club América su próximo partido?», fidelity introduced
    # «Club», kind person: the objective became «y cuando juega el sigiente» and the search read the national team.
    history = [turn["content"] for turn in TURNS["D-w08-t2"]["lived"]]
    fidelity = faithful_request("¿Cuándo juega el Club América su próximo partido?", TURNS["D-w08-t2"]["text"],
                                history, now=RUN_NOW.replace(tzinfo=None))
    assert (fidelity.kind, fidelity.request) == ("trimmed", "¿Cuándo juega el América su próximo partido?")
    assert "Selección Mexicana" in TURNS["D-w08-t2"]["published"]
    # A name nobody said stays out, as before.
    assert faithful_request("Abre Spotify", "abrelo", ["pon música"]).kind == "person"


def test_d_w08_t3_the_match_stays_what_the_reminder_is_for() -> None:
    reply = TURNS["D-w08-t3"]["lived"][-1]["content"]
    assert "sábado 3 de octubre de 2026 a las 8:00 pm" in reply
    anchored = anchored_offset_request(TURNS["D-w08-t3"]["text"], reply)
    assert anchored == "ponme recordatorio el sábado 3 de octubre de 2026 a las 19:00 para el partido"
    assert moment_then_title_reminder(anchored) == ("el partido", "el sábado 3 de octubre de 2026 a las 19:00")
    arguments = _explicit_arguments_from_evidence("reminder.create", anchored)
    assert arguments == {"dueUtc": "el sábado 3 de octubre de 2026 a las 19:00", "title": "el partido"}
    now = datetime(2026, 9, 30, 20, 0, tzinfo=CHILE)
    assert _canonical_due_utc(arguments["dueUtc"], anchored, now_utc=now) == "2026-10-03T22:00:00Z"
    # A weekday that is not that date's still disagrees.
    assert _canonical_due_utc("el viernes 3 de octubre de 2026 a las 19:00", "", now_utc=now) is None
    # D61 (owner, 2026-10-02): an hour without its part of the day is the next time it comes, no longer left out.
    assert moment_then_title_reminder("ponme un recordatorio a las 5 para algo") == ("algo", "a las 5")


# ------------------------------------------------------------------ 7. held-out v3v t10: an open not confirmed


def test_heldout_v3v_t10_the_unconfirmed_open_told_honestly_is_published() -> None:
    # app.open inventory_failed in 42 ms (the catalog was already read at startup): the three honest drafts died as
    # reversed_polarity («…la lista de programas y ventanas abiertos») and missing_failure («…no pudo abrirse…»).
    turn = EVIDENCE["heldout_v3v_t10"]
    assert [row["reason"] for row in turn["drafts"]] == ["reversed_polarity", "missing_failure", "reversed_polarity"]
    for row in turn["drafts"]:
        facts = {"situation": row["situation"]}
        assert visible_defect.compose_visible_defect(row["draft"], "error", turn["text"], facts) == "", row["draft"]
        assert payload_fact_checks._payload_fact_defect(row["draft"], row["payload"], turn["text"]) == "", row["draft"]
    facts = {"situation": turn["drafts"][0]["situation"]}
    # An open claimed, or the app said to be open, still reverses the failure.
    for claimed in ("Ya abrí el Bloc de notas.", "El Bloc de notas está abierto, pero no pude confirmarlo.",
                    "El Bloc de notas se abrió."):
        assert visible_defect.compose_visible_defect(claimed, "error", turn["text"], facts) != "", claimed
    # «no pudo abrirse» is a failure told; a sentence without the pronoun after the verb is not read so.
    assert failure_wording._asserts_failure("El Bloc de notas no pudo abrirse.")
    assert not failure_wording._asserts_failure("Napoleón no pudo conquistar Rusia.")
