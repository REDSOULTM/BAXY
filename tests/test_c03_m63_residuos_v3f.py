"""M63: residues of the official-window run v3f-final (2026-09-29), fixed in general and pinned on the real payloads
and drafts (tests/data/c03_m63_v3f_situations.json, from its compose-audit.jsonl and events.jsonl).

- F-s019 «Cambia la alarma despertador de las 8:00 a las 9:00.»: the mind published «No se pudo cambiar la alarma
  porque no estaba configurada para las 8:00. ¿Te gustaría que la establezca para las 9:00?» and the App dropped it as
  missing_literal_fact (a failure with no clock read took the person's own clocks for invented ones). The clocks the
  person named are theirs to hear back in any equivalent form; mind and App judge the same (the App's half is
  tests/Baxy.Integration.Tests/M63ResiduosV3fTests.cs).
- F-w01-t6 «¿va a llover donde vive mi hermana?» → «en ñuñoa» → «…mañana: llovizna, de 7,9 a 23 °C, 0 % de lluvia.»:
  the forecast's drizzle beside its own 0 % chance, and no plain answer. «¿va a llover?» is answered yes or no by the
  chance; a sky that says otherwise goes with «aunque»; said as two facts it is vetoed, and the last resort says it
  plainly.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import compose_payload
from baxy_mind import deterministic_finals
from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic.temporal import named_clock_dial
from baxy_mind.semantic.web import weather_asks_whether_it_rains

RECORDED = json.loads((Path(__file__).parent / "data" / "c03_m63_v3f_situations.json").read_text(encoding="utf-8"))


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


def _compose(drafts: list[str], user_text: str, intent: str, situation: dict) -> tuple[str, _Drafts]:
    writer = _Drafts(drafts)
    return writer.compose_user_message(
        user_text, intent, {"situation": json.dumps(situation, ensure_ascii=False)}
    ), writer


# ------------------------------------------------------------------ F-s019: the person's clocks are not invented

F_S019 = "Cambia la alarma despertador de las 8:00 a las 9:00."


def test_f_s019_the_reply_the_app_dropped_is_the_one_published() -> None:
    real = RECORDED["F-s019"]["drafts"][0]["draft"]
    assert RECORDED["F-s019"]["appRejected"] == {"reason": "missing_literal_fact;retry_exhausted", "reply": real}
    final, writer = _compose([real], F_S019, "error", _situation("F-s019"))
    assert final == real
    assert len(writer.requests) == 1


@pytest.mark.parametrize(
    "said",
    ["8:00", "08:00", "8:00 a. m.", "las 8 de la mañana", "8 am", "las 20:00", "8 pm"],
)
def test_f_s019_every_form_of_the_clock_is_the_same_time(said: str) -> None:
    assert (8, 0) in named_clock_dial(f"Cambia la alarma de las {said} a las 9:30")
    assert (9, 30) in named_clock_dial(f"Cambia la alarma de las {said} a las 9:30")


@pytest.mark.parametrize(
    "reply",
    [
        "No hay ninguna alarma a las 08:00. ¿Quieres que ponga una a las 09:00?",
        "No hay ninguna alarma a las 8:00 a. m., así que no cambié nada. ¿La pongo a las 9:00?",
    ],
)
def test_f_s019_the_clocks_named_in_another_form_pass(reply: str) -> None:
    facts = {"situation": json.dumps(_situation("F-s019"), ensure_ascii=False)}
    assert visible_defect.compose_visible_defect(reply, "error", F_S019, facts) == ""


@pytest.mark.parametrize(
    "reply",
    [
        "No hay ninguna alarma a las 7:00. ¿Quieres que ponga una a las 9:00?",
        "No hay ninguna alarma a las 8:00. ¿Quieres que ponga una a las 9:30?",
    ],
)
def test_f_s019_a_clock_nobody_named_is_still_invented(reply: str) -> None:
    facts = {"situation": json.dumps(_situation("F-s019"), ensure_ascii=False)}
    assert visible_defect.compose_visible_defect(reply, "error", F_S019, facts) == "extra_claim"


def test_f_s019_a_failure_that_read_a_clock_is_not_judged_here() -> None:
    # The twin of the App's InventedClock: with a clock in the read, the clock checks of that read apply instead.
    situation = _situation("F-s019")
    situation["reason"]["observed"] = {"dueUtc": "2026-09-30T11:00:00Z"}
    facts = {"situation": json.dumps(situation, ensure_ascii=False)}
    assert visible_defect.compose_visible_defect("No hay ninguna alarma a las 7:00.", "error", F_S019, facts) == ""


# ------------------------------------------------------------------ F-w01-t6: «¿va a llover?» said plainly

F_W01_T6 = "¿Va a llover en Ñuñoa?"
PLAIN = (
    "En Ñuñoa no se espera lluvia: hoy 4 % y mañana 0 % de probabilidad, aunque el pronóstico de mañana "
    "marca llovizna."
)


def _weather_payload(user_text: str, language: str = "es") -> dict:
    return compose_payload._compose_situation_payload(_situation("F-w01-t6"), language, user_text)


def test_f_w01_t6_the_published_contradiction_is_vetoed() -> None:
    published = RECORDED["F-w01-t6"]["published"]
    assert published == "En Ñuñoa hay 12,4 °C ahora, nublado; mañana: llovizna, de 7,9 a 23 °C, 0 % de lluvia."
    assert payload_fact_checks._payload_fact_defect(published, _weather_payload(F_W01_T6), F_W01_T6) == "weather_contradiction"
    assert payload_fact_checks._payload_fact_defect(
        "En Ñuñoa mañana habrá llovizna con un 0 % de probabilidad de lluvia.",
        _weather_payload(F_W01_T6), F_W01_T6,
    ) == "weather_contradiction"


def test_f_w01_t6_the_last_resort_answers_plainly_after_the_run_drafts() -> None:
    drafts = [entry["draft"] for entry in RECORDED["F-w01-t6"]["drafts"]]
    final, _ = _compose(drafts, F_W01_T6, "status", _situation("F-w01-t6"))
    assert final == PLAIN
    assert payload_fact_checks._payload_fact_defect(PLAIN, _weather_payload(F_W01_T6), F_W01_T6) == ""


def test_f_w01_t6_the_prompt_asks_for_the_plain_answer() -> None:
    _, writer = _compose([PLAIN], F_W01_T6, "status", _situation("F-w01-t6"))
    prompt = json.dumps(writer.requests[0]["messages"], ensure_ascii=False)
    assert "Di primero si va a llover" in prompt and "«aunque»" in prompt


@pytest.mark.parametrize(
    ("reply", "defect"),
    [
        ("No, en Ñuñoa no se espera lluvia: hoy 4 % y mañana 0 % de probabilidad.", ""),
        ("En Ñuñoa no hay mucha probabilidad de lluvia: hoy 4 % y mañana 0 %.", ""),
        ("No, en Ñuñoa no lloverá: 4 % hoy y 0 % mañana, aunque mañana se pronostica llovizna.", ""),
        # The chances alone still answer it (owner 2026-09-24, test_concision_2026_09_24.py).
        ("En Ñuñoa la probabilidad de lluvia es del 4 % hoy y del 0 % mañana.", ""),
        # A yes against a 4 % and a 0 % chance.
        ("Sí, en Ñuñoa va a llover: hoy 4 % y mañana 0 %.", "reversed_result"),
    ],
)
def test_f_w01_t6_the_answer_is_the_chance_s(reply: str, defect: str) -> None:
    assert payload_fact_checks._payload_fact_defect(reply, _weather_payload(F_W01_T6), F_W01_T6) == defect


def test_f_w01_t6_asked_for_the_chance_the_figure_is_the_answer() -> None:
    asked = "¿Qué probabilidad de lluvia hay en Ñuñoa?"
    assert not weather_asks_whether_it_rains(asked)
    reply = "En Ñuñoa la probabilidad de lluvia es del 4 % hoy y del 0 % mañana."
    assert payload_fact_checks._payload_fact_defect(reply, _weather_payload(asked), asked) == ""


@pytest.mark.parametrize(
    ("asked", "whether"),
    [
        ("¿Va a llover en Ñuñoa?", True),
        ("¿lloverá mañana?", True),
        ("will it rain tomorrow in Ñuñoa?", True),
        # Rain gear and later days are answered with the chance of the day (uso real tandas 2, 6, 8).
        ("¿me llevo el paraguas?", False),
        ("¿va a llover el fin de semana?", False),
        ("will it rain on tuesday", False),
        ("¿cuántos milímetros van a caer?", False),
        ("what's the chance of rain today", False),
        ("¿qué tiempo hará mañana?", False),
    ],
)
def test_the_yes_or_no_rain_question_is_read(asked: str, whether: bool) -> None:
    assert weather_asks_whether_it_rains(asked) is whether


def test_the_last_resort_for_one_day_and_in_english() -> None:
    tomorrow = "¿Lloverá mañana en Ñuñoa?"
    text = deterministic_finals._deterministic_final(_situation("F-w01-t6"), _weather_payload(tomorrow), tomorrow, "es")
    assert text == "En Ñuñoa no se espera lluvia mañana: 0 % de probabilidad, aunque el pronóstico marca llovizna."
    assert payload_fact_checks._payload_fact_defect(text, _weather_payload(tomorrow), tomorrow) == ""
    english = "Will it rain in Ñuñoa?"
    text = deterministic_finals._deterministic_final(_situation("F-w01-t6"), _weather_payload(english, "en"), english, "en")
    # Uso real v3 tanda 1 (t1-c06): the English final says the sky in English («drizzle», not the read's «llovizna»).
    assert text == (
        "In Ñuñoa no rain is expected: 4% today and 0% tomorrow, though tomorrow's forecast shows drizzle."
    )
    assert payload_fact_checks._payload_fact_defect(text, _weather_payload(english, "en"), english) == ""
    # A later day keeps its figures: its sky agrees with its 61 % chance.
    friday = "¿Llueve el viernes en Ñuñoa?"
    text = deterministic_finals._deterministic_final(_situation("F-w01-t6"), _weather_payload(friday), friday, "es")
    assert text == "En Ñuñoa, el viernes: llovizna, de 11 a 21,3 °C, 61 % de lluvia."


def test_a_forecast_day_whose_sky_contradicts_its_chance_is_told_with_a_concession() -> None:
    asked = "¿Qué tiempo hará mañana en Ñuñoa?"
    text = deterministic_finals._deterministic_final(_situation("F-w01-t6"), _weather_payload(asked), asked, "es")
    assert text == "En Ñuñoa, mañana: de 7,9 a 23 °C, 0 % de lluvia, aunque el pronóstico marca llovizna."
    assert payload_fact_checks._payload_fact_defect(text, _weather_payload(asked), asked) == ""
