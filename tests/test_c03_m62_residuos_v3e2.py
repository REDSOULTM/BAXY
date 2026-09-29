"""M62: the residues of the official-window run v3e2-final (2026-09-29), fixed in general and pinned on the real
messages and payloads (situations and drafts from its compose-audit.jsonl, in tests/data/c03_m62_v3e2_situations.json).

- F-s040 «Cancela las alarmas, por favor.»: the offer said «ocho alarmas» over six times and sixteen alarms read (20 of
  38 notifications, several alarms at the same minute). The count said is the alarms named; the yes is offered only
  when it can cancel exactly those (notification.cancel.at picks one alarm per clock); the read asks for 50.
- F-s019 «Cambia la alarma despertador de las 8:00 a las 9:00.»: «el reloj de notificaciones no se encontró» was the
  bare code notification_clock_not_found; its fact is that nothing rings at that time.
- F-s044 «change the reminder for the chef's table group from 3 to 4»: the new clock takes the part of the day the
  old one was said with before; otherwise only that is asked, in the person's language.
- F-w13-t2 «y si cargo 40 litros cuanto me sale»: «$73.000 por 40 litros» was a full tank's price; the total is
  computed (40 × $1.460 = $58.400) and any other amount for that quantity is vetoed.
- F-p07-t1 «…weather in Foster City later today.»: later today is answered with today's read, not 11.7 °C at 00:45.
- F-p07-t4 «Okay, that's all; see ya!» → «Have a great day, BAXY!»: BAXY never calls the person BAXY.
- F-w11-t1 «pideme unos tacos al pastor…» → «No hago tacos al pastor.»: the recovered limit made the tacos again.
- F-s064 «ahora sígueme, repite todo lo que diga» → «No hago el pedido.»: the limit named «the request», not the act.
- F-p05-t1 «Encuentra aparcamiento en Plaza del Polvorista»: the car parks were told by their whole addresses.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import llm
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic import quantities
from baxy_mind.semantic import temporal
from baxy_mind.semantic.dialogue import DialogueState, offered_alarm_clocks
from baxy_mind.semantic.patterns import echo_mode_request
from baxy_mind.semantic.web import weather_asks_later_in_the_day

RECORDED = json.loads((Path(__file__).parent / "data" / "c03_m62_v3e2_situations.json").read_text(encoding="utf-8"))


def _situation(case: str) -> dict:
    return copy.deepcopy(RECORDED[case]["situation"])


class _Drafts(LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats)."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.requests.append(copy.deepcopy(payload))
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _compose(drafts: list[str], user_text: str, intent: str, situation: dict | str) -> tuple[str, _Drafts]:
    writer = _Drafts(drafts)
    raw = situation if isinstance(situation, str) else json.dumps(situation, ensure_ascii=False)
    return writer.compose_user_message(user_text, intent, {"situation": raw}), writer


# ------------------------------------------------------------------ F-s040: the offer counts what it names

F_S040 = "Cancela las alarmas, por favor."


def test_f_s040_the_offer_is_said_from_the_alarms_alone() -> None:
    payload = llm._compose_situation_payload(_situation("F-s040"), "es", F_S040)
    seen = payload["seen"]
    assert seen["alarmCount"] == 16, "the sixteen alarms read, not the 38 notifications nor the reminders"
    assert [entry["time"] for entry in seen["alarms"]] == ["05:20", "06:00", "06:45", "08:30", "08:40", "09:00"]
    assert [entry.get("howMany", 1) for entry in seen["alarms"]] == [1, 1, 3, 4, 3, 4]
    # Several alarms ring at one minute and the read was cut: the yes could not cancel exactly these.
    assert seen["offer"] == "which" and seen["moreNotRead"] is True
    assert "count" not in seen and "scheduled" not in seen


def test_f_s040_the_recorded_offer_is_refused_and_the_final_asks_which() -> None:
    payload = llm._compose_situation_payload(_situation("F-s040"), "es", F_S040)
    published = "Hay ocho alarmas a las 05:20, 06:00, 06:45, 08:30, 08:40 y 09:00; ¿las cancelo todas?"
    assert llm._payload_fact_defect(published, payload, F_S040) == "alarm_offer_not_whole"
    final, writer = _compose(RECORDED["F-s040"]["drafts"], F_S040, "status", _situation("F-s040"))
    assert final == "Tienes 16 alarmas (05:20, 06:00, 06:45 (×3), 08:30 (×4), 08:40 (×3) y 09:00 (×4)). ¿Cuál cancelo?"
    assert "seen.alarmCount" in json.dumps(writer.requests[0]["messages"], ensure_ascii=False)


def _tomorrow_utc(hour: int, minute: int) -> str:
    local = (datetime.now().astimezone() + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _alarms_read(*clocks: tuple[int, int], truncated: bool = False) -> dict:
    notifications = [
        {"kind": "alarm", "nextRunUtc": _tomorrow_utc(hour, minute), "state": "Ready"} for hour, minute in clocks
    ] + [{"kind": "reminder", "title": "pagar la luz", "nextRunUtc": _tomorrow_utc(18, 0), "state": "Ready"}]
    return {
        "kind": "operation", "operation": "notification.list", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {
            "version": 1, "count": len(notifications), "notifications": notifications, "staleTaskCount": 0,
            "resultLimit": 50, "resultsMayBeTruncated": truncated,
            "authority": "windows_task_scheduler_notification_list_postread",
        },
    }


def test_f_s040_the_number_said_is_the_alarms_named() -> None:
    situation = _alarms_read((7, 0), (8, 30), (12, 0))
    payload = llm._compose_situation_payload(situation, "es", F_S040)
    assert payload["seen"]["offer"] == "all" and payload["seen"]["alarmCount"] == 3
    assert llm._payload_fact_defect(
        "Tienes 3 alarmas para mañana (07:00, 08:30 y 12:00). ¿Las cancelo todas?", payload, F_S040,
    ) == ""
    assert llm._payload_fact_defect(
        "Hay ocho alarmas a las 07:00, 08:30 y 12:00; ¿las cancelo todas?", payload, F_S040,
    ) == "alarm_count_wrong"


@pytest.mark.parametrize(
    ("clocks", "truncated", "offered"),
    [
        (((7, 0), (8, 30)), False, ((7, 0), (8, 30))),
        (((7, 0), (7, 0), (8, 30)), False, None),  # two alarms at 7:00: cancel.at cannot tell them apart
        (((7, 0), (8, 30)), True, None),  # a cut read does not hold every alarm
        (tuple((hour, 0) for hour in range(6, 15)), False, None),  # nine: more than a plan holds
    ],
)
def test_f_s040_the_yes_is_offered_only_when_it_cancels_exactly_those(clocks, truncated, offered) -> None:
    situation = _alarms_read(*clocks, truncated=truncated)
    assert offered_alarm_clocks(situation["observed"]) == offered
    state = DialogueState()
    state.expect(F_S040, ["notification.list"])
    state.record(situation)
    accepted = state.accepted_alarm_cancellation("sí")
    assert (accepted is not None) == (offered is not None)
    payload = llm._compose_situation_payload(situation, "es", F_S040)
    assert payload["seen"]["offer"] == ("all" if offered is not None else "which")


def test_f_s040_the_recorded_read_offers_no_yes() -> None:
    assert offered_alarm_clocks(_situation("F-s040")["observed"]) is None
    state = DialogueState()
    state.expect(F_S040, ["notification.list"])
    state.record(_situation("F-s040"))
    assert state.accepted_alarm_cancellation("sí") is None


def test_f_s040_the_alarms_are_read_up_to_the_catalog_limit() -> None:
    schema = {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
              "required": [], "additionalProperties": False}
    assert mind._ground_explicit_arguments("notification.list", F_S040, schema) == {"limit": 50}
    assert mind._ground_explicit_arguments("notification.list", "¿qué alarmas tengo?", schema) == {}


# ------------------------------------------------------------------ F-s019: no alarm at that time, said plainly

F_S019 = "Cambia la alarma despertador de las 8:00 a las 9:00."


def test_f_s019_no_alarm_at_that_time_is_a_fact_not_a_code() -> None:
    payload = llm._compose_situation_payload(_situation("F-s019"), "es", F_S019)
    cause = payload["reason"]["cause"]
    assert cause == llm._CAUSE_FACT["notification_clock_not_found"]
    assert "clock" not in cause.split(",")[0] or "no alarm or reminder" in cause
    assert "notification clock" not in json.dumps(payload)
    assert llm._failure_is_an_absence(_situation("F-s019"))
    assert llm._cause_in_prose("notification_clock_ambiguous", "es") == llm._CAUSE_FACT["notification_clock_ambiguous"]


def test_f_s019_the_plain_answer_is_published() -> None:
    final, _ = _compose(
        ["No hay ninguna alarma a las 8:00, así que no cambié nada. ¿Quieres que ponga una a las 9:00?"],
        F_S019, "error", _situation("F-s019"),
    )
    assert final == "No hay ninguna alarma a las 8:00, así que no cambié nada. ¿Quieres que ponga una a las 9:00?"


# ------------------------------------------------------------------ F-s044: the part of the day is inherited

F_S044 = "change the reminder for the chef's table group from 3 to 4"
SCHEDULE_SCHEMA = {
    "type": "object",
    "properties": {
        "dueUtc": {"type": "string", "minLength": 1, "maxLength": 64},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
    },
    "required": ["dueUtc", "kind"],
    "additionalProperties": False,
}


def test_f_s044_the_new_clock_takes_the_part_of_day_said_before() -> None:
    change = temporal.notification_change(F_S044)
    assert change is not None and change.clocks_lack_the_part_of_day()
    assert temporal.change_part_of_day(change, ()) is None
    history = [
        {"role": "user", "content": "remind me about the chef's table group at 3 pm"},
        {"role": "assistant", "content": "Done: I'll remind you at 15:00."},
        {"role": "user", "content": F_S044},
    ]
    said = [item["content"] for item in reversed(history) if item["content"] != F_S044]
    assert temporal.change_part_of_day(change, said) == "pm"
    assert change.schedule_arguments("pm")["dueUtc"] == "at 4 pm"
    grounded = mind._ground_explicit_arguments("notification.schedule", F_S044, SCHEDULE_SCHEMA, history=history)
    assert grounded is not None and grounded["kind"] == "reminder"
    due = datetime.fromisoformat(grounded["dueUtc"].replace("Z", "+00:00")).astimezone()
    assert (due.hour, due.minute) == (16, 0)


def test_f_s044_with_nothing_said_before_it_is_asked() -> None:
    assert mind._ground_explicit_arguments("notification.schedule", F_S044, SCHEDULE_SCHEMA, history=[]) is None


@pytest.mark.parametrize(
    ("request_text", "said", "part", "due"),
    [
        ("Cambia la alarma de las 3 a las 4", ["Listo, tu alarma suena a las 15:00."], "pm", "a las 4 p. m."),
        ("Cambia la alarma de las 3 a las 4", ["pon una alarma a las 3 de la madrugada"], "am", "a las 4 a. m."),
        ("Cambia la alarma de las 15:00 a las 4", [], "pm", "a las 4 p. m."),
        ("Cambia la alarma de las 3 a las 4", ["pon una alarma a las 7 de la tarde"], None, "a las 4"),
    ],
)
def test_f_s044_spanish_and_24_hour_clocks(request_text: str, said: list[str], part, due: str) -> None:
    change = temporal.notification_change(request_text)
    assert temporal.change_part_of_day(change, said) == part
    assert change.schedule_arguments(part)["dueUtc"] == due


class _Question(LlmRuntime):
    def __init__(self) -> None:  # noqa: D107
        self._gguf = None
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload, _label):  # noqa: ANN001, ANN201
        self.payloads.append(payload)
        return {"requested_fields": ["dueUtc"], "question": "Is that 4 in the morning or in the afternoon?"}


def test_f_s044_only_the_part_of_the_day_is_asked_in_english() -> None:
    writer = _Question()
    tool = {"function": {"canonical_name": "notification.schedule", "description": "Programa una alarma.",
                         "parameters": SCHEDULE_SCHEMA}}
    question = writer.formulate_missing_argument_question(
        F_S044, F_S044, tool, ("dueUtc",), response_language="en",
        ask_as={"dueUtc": "only whether 4 is in the morning or in the afternoon or evening"},
    )
    assert question.endswith("?")
    sent = json.dumps(writer.payloads[0]["messages"], ensure_ascii=False)
    assert "only whether 4 is in the morning" in sent
    assert "in the person's own words" not in sent


# ------------------------------------------------------------------ F-w13-t2: the total is computed

F_W13_T2 = "y si cargo 40 litros cuanto me sale"
F_W13_T2_DECIDED = "¿Cuánto me sale cargar 40 litros de nafta Super en Córdoba?"


def test_f_w13_t2_the_total_is_computed_from_the_unit_price_read() -> None:
    payload = llm._compose_situation_payload(_situation("F-w13-t2"), "es", F_W13_T2_DECIDED)
    assert payload["calculation"] == ["40 litros × $1.460 por litro = $58.400"]
    evidence = llm._search_results_text(payload)
    # «El litro de Diésel … trepa ahora a $755» is another fuel: the request that names «nafta Super» prices only it;
    # the bare follow-up names none, so both litre prices are its.
    assert [item.total for item in quantities.priced_totals(F_W13_T2_DECIDED, evidence)] == [58400]
    assert sorted(item.total for item in quantities.priced_totals(F_W13_T2, evidence)) == [30200, 58400]


@pytest.mark.parametrize("request_text", [F_W13_T2, F_W13_T2_DECIDED])
def test_f_w13_t2_a_tanks_price_for_forty_litres_is_vetoed(request_text: str) -> None:
    payload = llm._compose_situation_payload(_situation("F-w13-t2"), "es", request_text)
    published = RECORDED["F-w13-t2"]["drafts"][0]
    assert published == "En Córdoba el litro de nafta súper cuesta $1.460, lo que suma $73.000 por 40 litros."
    assert llm._payload_fact_defect(published, payload, request_text) == "underived_price"
    good = "En Córdoba, 40 litros de nafta súper te salen $58.400 ($1.460 el litro)."
    assert llm._payload_fact_defect(good, payload, request_text) == ""


def test_f_w13_t2_the_retry_is_told_the_calculation() -> None:
    final, writer = _compose(
        [RECORDED["F-w13-t2"]["drafts"][0], "En Córdoba, 40 litros de nafta súper te salen $58.400 ($1.460 el litro)."],
        F_W13_T2_DECIDED, "status", _situation("F-w13-t2"),
    )
    assert final == "En Córdoba, 40 litros de nafta súper te salen $58.400 ($1.460 el litro)."
    retry = json.dumps(writer.requests[1]["messages"], ensure_ascii=False)
    assert "40 litros × $1.460 por litro = $58.400" in retry and "$73.000" in retry


@pytest.mark.parametrize(
    ("request_text", "evidence", "expected"),
    [
        ("how much for 10 gallons", "Regular gas is $3.45 per gallon today", "10 gallons × $3.45 per gallon = $34.50"),
        ("2 kilos de pan", "el kilo de pan cuesta 1.200 pesos", "2 kilos × 1.200 pesos por kilo = 2.400 pesos"),
    ],
)
def test_priced_totals_other_units_and_currencies(request_text: str, evidence: str, expected: str) -> None:
    language = "en" if request_text.startswith("how") else "es"
    assert [item.sentence for item in quantities.priced_totals(request_text, evidence, language)] == [expected]


def test_priced_totals_need_one_quantity_and_a_unit_price() -> None:
    assert quantities.priced_totals("¿cuánto cuesta la nafta?", "el litro se ubica en $1.460") == []
    assert quantities.priced_totals("40 litros", "la nafta quedó en $716") == []
    assert quantities.underived_price("Sale $73.000.", "¿cuánto cuesta la nafta?", "el litro está a $1.460") == ""


# ------------------------------------------------------------------ F-p07-t1: later today is today's read

F_P07_T1 = "I must verify the weather in Foster City later today."


def test_f_p07_t1_later_today_is_answered_with_todays_read() -> None:
    assert weather_asks_later_in_the_day(F_P07_T1)
    assert weather_asks_later_in_the_day("¿qué tiempo hará esta tarde en Lima?")
    assert not weather_asks_later_in_the_day("¿qué tiempo hará mañana por la tarde?")
    assert not weather_asks_later_in_the_day("what's the weather in Foster City?")
    payload = llm._compose_situation_payload(_situation("F-p07-t1"), "en", F_P07_T1)
    published = RECORDED["F-p07-t1"]["drafts"][0]
    assert published == "It is 11.7°C and clear in Foster City, so you should wear a light jacket."
    assert llm._weather_fact_defect(published, payload, F_P07_T1) == "missing_state"
    good = "Later today in Foster City it will reach 30 °C, with a low of 9.3 °C and a 0% chance of rain."
    assert llm._weather_fact_defect(good, payload, F_P07_T1) == ""
    assert "today.maxC" in llm._weather_answer_instruction(F_P07_T1, "en")


def test_f_p07_t1_the_deterministic_final_carries_today() -> None:
    situation = _situation("F-p07-t1")
    payload = llm._compose_situation_payload(situation, "en", F_P07_T1)
    assert llm._deterministic_final(situation, payload, F_P07_T1, "en") == (
        "In Foster City it is 11.7 °C now, despejado; today: 9.3 to 30 °C, 0% chance of rain."
    )


# ------------------------------------------------------------------ F-p07-t4: BAXY does not call the person BAXY


@pytest.mark.parametrize(
    ("reply", "vocative"),
    [
        ("Have a great day, BAXY!", True),
        ("Bye BAXY.", True),
        ("BAXY, que tengas buen día.", True),
        ("¡Hasta luego, BAXY!", True),
        ("Have a great day!", False),
        ("Hola, soy BAXY. ¿En qué puedo ayudarte hoy?", False),
        ("I'm BAXY, your assistant.", False),
    ],
)
def test_f_p07_t4_the_person_is_not_called_baxy(reply: str, vocative: bool) -> None:
    assert llm.visible_reply_calls_the_person_baxy(reply) is vocative
    english = reply.startswith(("Have", "Bye", "I'm"))
    request = "Okay, that's all; see ya!" if english else "Vale, eso es todo, ¡nos vemos!"
    assert (llm.compose_visible_defect(reply, "conversation", request, {}) == "person_called_baxy") is vocative


def test_f_p07_t4_the_talk_reply_is_refused() -> None:
    assert llm._shaped_conversation_answer_violates_contract("Have a great day, BAXY!", "Okay, that's all; see ya!", None)
    assert not llm._shaped_conversation_answer_violates_contract("Have a great day!", "Okay, that's all; see ya!", None)


# ------------------------------------------------------------------ F-w11-t1 and F-s064: the limit names the act

F_W11_T1 = "pideme unos tacos al pastor porfa q ya va a empesar el partido"
F_S064 = "ahora sígueme, repite todo lo que diga"
LIMIT = {"kind": "failure", "polarity": "failure", "cause": "out_of_catalog"}


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        ("No hago tacos al pastor porque eso está fuera de mis funciones.", "limit_changed_act"),
        ("No hago tacos al pastor.", "limit_changed_act"),
        ("No preparo tacos al pastor.", "limit_changed_act"),
        ("Eso no lo hago: no pido comida.", ""),
        ("No pido tacos al pastor.", ""),
        ("No hago pedidos de comida.", ""),
    ],
)
def test_f_w11_t1_ordering_is_not_making(reply: str, defect: str) -> None:
    assert llm.limit_voice_defect(reply, F_W11_T1) == defect
    if defect:
        assert llm._unsupported_answer_contract_failure(reply, F_W11_T1) == "unsupported_changed_act"


def test_f_w11_t1_the_recovered_limit_is_the_model_s_and_names_ordering() -> None:
    final, writer = _compose(
        ["No hago tacos al pastor porque eso está fuera de mis funciones.", "Eso no lo hago: no pido comida."],
        F_W11_T1, "error", LIMIT,
    )
    assert final == "Eso no lo hago: no pido comida."
    assert "pedir o encargar" in json.dumps(writer.requests[1]["messages"], ensure_ascii=False)


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        ("No hago el pedido.", "limit_names_no_act"),
        ("No hago el pedido porque está fuera de lo que hago.", "limit_names_no_act"),
        ("Eso no lo hago: no repito todo lo que dices.", ""),
        ("No repito todo lo que dices.", ""),
    ],
)
def test_f_s064_the_limit_names_repeating(reply: str, defect: str) -> None:
    # Owner rule (uso real tanda 5, 2026-09-24): repeating everything from now on is a mode BAXY does not keep, so the
    # decision is the limit; what was wrong is its wording.
    assert echo_mode_request(F_S064)
    assert llm.limit_voice_defect(reply, F_S064) == defect
    assert llm.limit_voice_defect("No hago el pedido de agregar el número de móvil de Pedro.", "agrega el número de "
                                  "móvil de Pedro a mis contactos") == "limit_names_no_act"


def test_f_s064_the_recovered_limit_is_rewritten() -> None:
    final, _ = _compose(
        ["No hago el pedido porque está fuera de lo que hago.", "Eso no lo hago: no repito todo lo que dices."],
        F_S064, "error", LIMIT,
    )
    assert final == "Eso no lo hago: no repito todo lo que dices."


# ------------------------------------------------------------------ F-p05-t1: the places, near and briefly

F_P05_T1 = "Encuentra aparcamiento en Plaza del Polvorista"


def _places_with_distances() -> dict:
    situation = _situation("F-p05-t1")
    # Distances as the provider now writes them (M62, OpenStreetMapPlaceSource.Places); these are illustrative.
    for item, meters in zip(situation["observed"]["results"], (150, 430, 450, 480, 620)):
        item["distanceMeters"] = meters
    return situation


def test_f_p05_t1_the_whole_address_is_refused() -> None:
    situation = _places_with_distances()
    payload = llm._compose_situation_payload(situation, "es", F_P05_T1)
    published = RECORDED["F-p05-t1"]["drafts"][-1]
    assert published.startswith("Encontré aparcamiento en Calle Aurora, Valdelagrana, El Puerto de Santa María")
    assert llm._payload_fact_defect(published, payload, F_P05_T1) == "places_whole_address"
    good = "Hay aparcamiento a 150 m, en la Calle Aurora, y a 430 m, en la Avenida de Valdelagrana."
    assert llm._payload_fact_defect(good, payload, F_P05_T1) == ""


def test_f_p05_t1_the_deterministic_final_says_how_far() -> None:
    situation = _places_with_distances()
    payload = llm._compose_situation_payload(situation, "es", F_P05_T1)
    assert llm._deterministic_final(situation, payload, F_P05_T1, "es") == (
        "Encontré: Calle Aurora (a 150 m), Avenida de Valdelagrana (a 430 m) y Avenida de Europa (a 450 m)."
    )


def test_f_p05_t1_none_near_is_said_plainly() -> None:
    assert "nothing of that kind was found near" in llm._cause_in_prose("web_search_places_not_found_near", "es")
