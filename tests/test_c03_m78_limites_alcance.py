"""M78: limits said only when true, never false, and said when the ask is beyond what can be read.

Pinned on the independent review of the official-window DEV-D run v3l (REVIEW.reviewed.jsonl, «límites o alcance»),
with the real weather reads of that run (tests/data/c03_m78_v3l_weather_situations.json, from its compose-audit.jsonl):

- Weather beyond the read: p20-t1 «I need weather info for the 1st of March.», p20-t2 «…weather info for March 2nd.»
  (published «The weather in Palo Alto on March 2 is currently 28.7°C»), p25-t2 «…on the 5th of March…» got today's
  weather; p21-t1 «…for Marshall on the 5th» got today's too, while the 5th is a day of the read; s048 «Estara alto the
  air quality the next week?» got today's index. A named date is that day of the read or a day it does not reach; the
  air is read only as it is now (semantic.web.weather_asked_date, llm._weather_asked_reach). The reach is said as the
  reach of a verified read («only goes up to…», «queda fuera»), never as a failure the composer and the App reverse.
- False limits: s010 «deactivates the speaker now» (decider «Turn off the speaker.», limit) is audio.mute; p12-t2
  «Bring up 24/7 stores near me» after «Which request should I cancel?» (decider «Cancel the request to bring up…»,
  limit) is a search. A limit the decider gives is re-read on its restatement's canonical surface and on the message
  as said when it is a complete request (__main__._served_surface_reread). p35-t1 «Has un análisis de FODA sobre la
  empresa Adidas…» → «No hago análisis de FODA.»: a business analysis is content written here, never a limit
  (semantic.patterns.conversation_only_content_request; both decision paths).
- Limit wording: s004 «recomprar el último billete de tren a huesca» → «No recomprobo billetes de tren.» (the limit
  contract refused it; the recovered limit, judged by limit_voice_defect only, published it); w06-t3 «¿Me pedirías
  una muzza grande…?» → «No hago pizzas.» («pedirías» is ordering: semantic.conversation.asks_to_order).
- s099 «your speech slower it» → «I speak slowly now.»: no operation changes the voice's speed or loudness; saying it
  now speaks slower is a claimed effect (llm.visible_reply_claims_an_effect).
- w20-t4 «…en los datos de situation»: the facts' field names are machinery (copied_instruction).
"""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider
from baxy_mind.semantic.conversation import asks_to_order
from baxy_mind.semantic.patterns import conversation_only_content_request
from baxy_mind.semantic.web import weather_asked_date, weather_asks_later_time, weather_names_date

WEATHER = json.loads(
    (Path(__file__).parent / "data" / "c03_m78_v3l_weather_situations.json").read_text(encoding="utf-8")
)
TODAY = date(2026, 9, 29)


def _situation(case: str) -> dict:
    return copy.deepcopy(WEATHER[case]["situation"])


def _payload(case: str, user_text: str, language: str = "en") -> dict:
    return llm._compose_situation_payload(_situation(case), language, user_text)


# ------------------------------------------------------------------ the date a weather question names


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        ("I need weather info for the 1st of March.", date(2027, 3, 1)),  # M78 (DEV-D v3l p20-t1)
        ("The city is Palo Alto, and weather info for March 2nd.", date(2027, 3, 2)),  # p20-t2
        ("What's the weather in Palo Alto on March 2?", date(2027, 3, 2)),  # p20-t2, the decider's restatement
        ("I want to check the weather for Marshall on the 5th.", date(2026, 10, 5)),  # p21-t1
        ("I see, can you check on the 5th of March to be more specific", date(2027, 3, 5)),  # p25-t2
        ("¿qué tiempo hará el 3 de octubre en Madrid?", date(2026, 10, 3)),
        ("clima para el veinte de diciembre", date(2026, 12, 20)),
        ("will it rain on october 1st", date(2026, 10, 1)),
        ("¿cómo estará el tiempo el día 30?", date(2026, 9, 30)),
    ],
)
def test_a_weather_question_names_its_date(text: str, asked: date) -> None:
    assert weather_names_date(text)
    assert weather_asked_date(text, TODAY) == asked
    assert weather_asks_later_time(text)


@pytest.mark.parametrize(
    "text",
    ["¿qué tiempo hace hoy?", "what's the weather in Denver", "¿va a llover mañana?", "clima de la semana",
     "Estara alto the air quality the next week?", "¿hace 20 grados?"],
)
def test_no_date_is_named(text: str) -> None:
    assert not weather_names_date(text)
    assert weather_asked_date(text, TODAY) is None


def test_a_later_time_of_the_air_is_asked() -> None:
    assert weather_asks_later_time("Estara alto the air quality the next week?")  # M78 (DEV-D v3l s048)
    assert weather_asks_later_time("¿cómo estará el aire mañana?")
    assert not weather_asks_later_time("Whats the air quality hoy?")


# ------------------------------------------------------------------ what the narrator gets


@pytest.mark.parametrize(
    ("case", "user_text", "asked"),
    [
        ("D-p20-t1", "I need weather info for the 1st of March.", "2027-03-01"),
        ("D-p20-t2", "What's the weather in Palo Alto on March 2?", "2027-03-02"),
        ("D-p25-t2", "Check the weather in Curico on March 5.", "2027-03-05"),
    ],
)
def test_a_date_the_read_does_not_reach_sends_no_figure_of_today(case: str, user_text: str, asked: str) -> None:
    seen = _payload(case, user_text)["seen"]
    assert seen["outOfReach"] == {
        "read": "forecast", "askedDate": asked, "readFrom": "2026-09-29", "readUntil": "2026-10-05",
    }
    assert set(seen) <= {"location", "region", "country", "outOfReach"}


def test_a_date_the_read_covers_sends_that_day() -> None:
    seen = _payload("D-p21-t1", "I want to check the weather for Marshall on the 5th.")["seen"]
    assert seen["askedDay"]["date"] == "2026-10-05"
    assert "temperatureC" not in seen and "today" not in seen


def test_the_air_at_a_later_time_is_beyond_the_read() -> None:
    seen = _payload("D-s048", "Estara alto the air quality the next week?")["seen"]
    assert seen["outOfReach"] == {"read": "airQuality", "readFor": "now"}
    assert "airQuality" not in seen


def test_today_named_by_its_date_is_the_read_now() -> None:
    seen = _payload("D-p20-t1", "what's the weather on September 29?")["seen"]
    assert "outOfReach" not in seen and "askedDay" not in seen and "temperatureC" in seen


# ------------------------------------------------------------------ what the reply may say


@pytest.mark.parametrize(
    ("case", "user_text", "reply"),
    [
        # The published replies of v3l: today's read given for another day.
        ("D-p20-t2", "What's the weather in Palo Alto on March 2?", WEATHER["D-p20-t2"]["published"]),
        ("D-p20-t1", "I need weather info for the 1st of March.", WEATHER["D-p20-t1"]["published"]),
        ("D-p25-t2", "Check the weather in Curico on March 5.", WEATHER["D-p25-t2"]["published"]),
        ("D-s048", "Estara alto the air quality the next week?", WEATHER["D-s048"]["published"]),
    ],
)
def test_the_published_reply_for_a_time_beyond_the_read_is_vetoed(case: str, user_text: str, reply: str) -> None:
    assert llm._payload_fact_defect(reply, _payload(case, user_text), user_text) == "invented_number"


@pytest.mark.parametrize(
    ("case", "user_text", "reply", "defect"),
    [
        ("D-p20-t2", "What's the weather in Palo Alto on March 2?",
         "The forecast for Palo Alto only goes up to October 5; March 2 is beyond it.", ""),
        ("D-p20-t1", "I need weather info for the 1st of March.",
         "The forecast doesn't reach March 1st yet.", ""),
        ("D-p25-t2", "Revisa el clima en Curicó el 5 de marzo.",
         "El pronóstico llega hasta el 5 de octubre; el 5 de marzo queda fuera.", ""),
        ("D-p25-t2", "Check the weather in Curico on March 5.", "March 5 is sunny in Curicó.", "missing_state"),
        ("D-s048", "Estara alto the air quality the next week?",
         "The air quality is only read as it is now, not for next week.", ""),
    ],
)
def test_the_limit_of_the_read_is_said(case: str, user_text: str, reply: str, defect: str) -> None:
    assert llm._payload_fact_defect(reply, _payload(case, user_text), user_text) == defect


def test_the_day_asked_is_answered_with_its_figures() -> None:
    user_text = "I want to check the weather for Marshall on the 5th."
    payload = _payload("D-p21-t1", user_text)
    day = payload["seen"]["askedDay"]
    assert llm._payload_fact_defect(WEATHER["D-p21-t1"]["published"], payload, user_text) == "invented_number"
    good = f"In Marshall on October 5: {day['condition']}, {day['minC']} to {day['maxC']} °C."
    assert llm._payload_fact_defect(good, payload, user_text) == ""


@pytest.mark.parametrize(
    ("case", "user_text", "language", "expected"),
    [
        ("D-p20-t2", "What's the weather in Palo Alto on March 2?", "en",
         "The forecast for Palo Alto only goes up to October 5; March 2 is beyond it."),
        ("D-p25-t2", "Revisa el clima en Curicó el 5 de marzo.", "es",
         "El pronóstico de Curicó llega sólo hasta el 5 de octubre; el 5 de marzo queda fuera."),
        ("D-s048", "Estara alto the air quality the next week?", "en",
         "The air quality is only read as it is now, not for a later time."),
    ],
)
def test_the_last_resort_says_the_limit(case: str, user_text: str, language: str, expected: str) -> None:
    payload = _payload(case, user_text, language)
    text = llm._deterministic_final(_situation(case), payload, user_text, language)
    assert text == expected
    assert llm._payload_fact_defect(text, payload, user_text) == ""
    # Said as the reach of a verified read, not as a failure: neither the composer nor the App reverses it.
    facts = {"situation": json.dumps(_situation(case), ensure_ascii=False)}
    assert llm.compose_visible_defect(text, "status", user_text, facts) == ""


def test_a_limit_said_as_a_failure_over_the_read_is_vetoed() -> None:
    # «No puedo ver…» over a verified read is a failure the read did not have (and the App reverses it).
    facts = {"situation": json.dumps(_situation("D-p20-t2"), ensure_ascii=False)}
    said = "I can't see the weather in Palo Alto for March 2; the forecast only reaches October 5."
    assert llm.compose_visible_defect(said, "status", "What's the weather in Palo Alto on March 2?", facts) != ""


def test_the_last_resort_gives_the_day_asked() -> None:
    user_text = "I want to check the weather for Marshall on the 5th."
    payload = _payload("D-p21-t1", user_text)
    text = llm._deterministic_final(_situation("D-p21-t1"), payload, user_text, "en")
    assert text.startswith("In Marshall, October 5: ")
    assert llm._payload_fact_defect(text, payload, user_text) == ""


def test_the_instruction_asks_for_the_day_or_the_limit() -> None:
    focus = llm._weather_answer_instruction("What's the weather in Palo Alto on March 2?", "en")
    assert "seen.outOfReach" in focus and "seen.askedDay" in focus
    assert "covers today and tomorrow only" not in focus
    air = llm._weather_answer_instruction("Estara alto the air quality the next week?", "en")
    assert "only as it is now" in air


class _Drafts(llm.LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats)."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


@pytest.mark.parametrize(
    ("case", "user_text", "limit"),
    [
        ("D-p20-t2", "What's the weather in Palo Alto on March 2?",
         "The forecast for Palo Alto only goes up to October 5; March 2 is beyond it."),
        ("D-s048", "Estara alto the air quality the next week?",
         "The air quality is only read as it is now, not for next week."),
    ],
)
def test_the_composer_publishes_the_limit_not_todays_read(case: str, user_text: str, limit: str) -> None:
    writer = _Drafts([WEATHER[case]["published"], limit])
    published = writer.compose_user_message(
        user_text, "status", {"situation": json.dumps(_situation(case), ensure_ascii=False)},
    )
    assert published == limit


# ------------------------------------------------------------------ a limit the decider gives to what BAXY serves

OPERATIONS = ("audio.mute", "audio.volume.adjust", "media.control", "web.search", "notification.schedule", "task.create")


class _LimitingDecider:
    """The contextual decider of v3l: it restates the message and decides a limit."""

    def __init__(self, restated: str) -> None:  # noqa: D107
        self.restated = restated
        self.chats = 0

    def decide_in_context(self, text: str, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return decider.ContextDecision(request=self.restated, decision="limit", operations=(), question="")

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Eso no lo hago.", []

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def formulate_explicit_clarification_question(*_args: object, **_kwargs: object) -> str:
        return "¿A qué hora?"

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "en"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "en"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


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


def _turn(text: str, restated: str, history: list[tuple[str, str]] = ()) -> tuple[dict[str, object], _LimitingDecider]:
    tools = {name: _tool(name) for name in OPERATIONS}
    model = _LimitingDecider(restated)
    turns = [{"role": role, "content": content} for role, content in history]
    result = sidecar._prepare_turn_result(
        {"id": "m78", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )
    return result, model


WELCOME = [("assistant", "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?")]


def test_a_limit_on_words_the_restatement_serves_is_the_served_request() -> None:
    # M78 (DEV-D v3l s010): «Turn off the speaker.» stands for «Turn off the audio.», audio.mute.
    result, model = _turn("deactivates the speaker now", "Turn off the speaker.", WELCOME)
    assert result["kind"] == "action" and result["operation"] == "audio.mute"
    assert result["objective"] == "Turn off the audio."
    assert model.chats == 0


def test_a_complete_request_after_a_question_is_that_request() -> None:
    # M78 (DEV-D v3l p12-t2): the decider joined the new request to the question about cancelling and refused it.
    history = [("user", "Okay but please cancel that request"), ("assistant", "Which request should I cancel?")]
    result, model = _turn("Bring up 24/7 stores near me", "Cancel the request to bring up 24/7 stores near me.", history)
    assert result["kind"] == "action" and result["operation"] == "web.search"
    assert model.chats == 0


@pytest.mark.parametrize(
    ("text", "restated", "history"),
    [
        # v3l w02-t4, an honest limit: the restatement itself names an alarm, but moving it to the phone is no
        # operation; it is not re-read, so no question about an alarm replaces the limit.
        ("y pásala al celu mejor en la app del reloj", "Pon la alarma en el celular usando la app del reloj.",
         [("user", "pon una alarma a las 7"), ("assistant", "Listo, alarma a las 7:00.")]),
        ("turn up the lights in here please", "Turn up the lights in here.", WELCOME),  # v3l s084
        ("Saca una foto en modo ráfaga", "Saca una foto en modo ráfaga.", WELCOME),  # v3l p07-t1
        ("get me takeaway food", "Get me takeaway food.", WELCOME),  # v3l s103
    ],
)
def test_a_limit_of_what_baxy_does_not_have_stays_a_limit(text: str, restated: str, history: list) -> None:
    result, model = _turn(text, restated, history)
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"
    assert model.chats == 1


# ------------------------------------------------------------------ content is written, never refused

FODA = (
    "Has un análisis de FODA sobre la empresa Adidas. utiliza un tono casual. Un lenguaje coloquial y un tono "
    "emocional, como el de un humano. A la vez hazlo con la experiencia que tendría un experto en marketing."
)


@pytest.mark.parametrize(
    "text",
    [
        FODA,  # M78 (DEV-D v3l p35-t1)
        "Make a SWOT analysis of Tesla.",
        "hazme un análisis DAFO de mi emprendimiento de café",
        "¿puedes hacer un análisis de mercado de las zapatillas deportivas?",
        "write a competitor analysis for a small bakery",
        "prepara un análisis PESTEL de Chile",
    ],
)
def test_a_business_analysis_is_content_written_here(text: str) -> None:
    assert conversation_only_content_request(text)


@pytest.mark.parametrize(
    "text",
    ["haz un análisis del disco", "analiza mi pc", "create a list called groceries", "busca un análisis FODA de Nike",
     "guarda un análisis FODA de Nike en un archivo", "¿has visto una lista de compras?"],
)
def test_what_is_not_an_analysis_to_write_stays_what_it_was(text: str) -> None:
    assert not conversation_only_content_request(text)


def test_a_limit_the_decider_gives_to_content_is_talk() -> None:
    text = "Make a SWOT analysis of my coffee shop."
    result, model = _turn(text, text, WELCOME)
    assert result["kind"] == "conversation" and result["conversationKind"] == "knowledge"
    assert model.chats == 1


@pytest.mark.parametrize("text", [FODA, "Make a SWOT analysis of Tesla."])
def test_the_foda_request_is_answered_not_refused_nor_asked(text: str) -> None:
    # D59.8 (owner, 2026-10-02): a named organization's analysis is written from what is read about it first
    # (test_c03_m121_d59_b): the turn looks it up, never refuses or asks.
    result, model = _turn(text, text)
    assert result["kind"] == "action" and result["operation"] == "web.search"
    assert model.chats == 0


# ------------------------------------------------------------------ the wording of a limit


def test_a_recovered_limit_with_a_verb_form_that_does_not_exist_is_vetoed() -> None:
    # M78 (DEV-D v3l s004): the limit contract refused it; the recovered limit is judged by limit_voice_defect.
    request = "recomprar el último billete de tren a huesca"
    assert llm.limit_voice_defect("No recomprobo billetes de tren.", request) == "limit_broken_person"
    assert llm.limit_voice_defect("No recompro billetes de tren.", request) == ""
    facts = {"situation": json.dumps({"kind": "failure", "cause": "out_of_catalog", "polarity": "failure"})}
    assert llm.compose_visible_defect("No recomprobo billetes de tren.", "error", request, facts) == (
        "limit_broken_person"
    )


@pytest.mark.parametrize(
    "request_text",
    [
        "Gracias, sos un crack. ¿Me pedirías una muzza grande a la pizzería de la esquina?",  # M78 (DEV-D v3l w06-t3)
        "¿me pedirías un taxi?",
        "pídeme unas empanadas",
        "que me pidan una pizza",
        "could you order me a pizza",
    ],
)
def test_ordering_in_any_person_is_ordering(request_text: str) -> None:
    assert asks_to_order(request_text)
    assert llm.limit_voice_defect("No hago pizzas.", request_text) == "limit_changed_act"


def test_asking_for_the_order_state_is_not_ordering() -> None:
    assert not asks_to_order("¿ya llegó mi pedido?")


# ------------------------------------------------------------------ BAXY's voice


@pytest.mark.parametrize(
    "reply",
    [
        "I speak slowly now.",  # M78 (DEV-D v3l s099)
        "Okay, I'll speak slower.",
        "Sure, I'm now talking more slowly.",
        "Listo, ahora hablo más despacio.",
        "De acuerdo, hablaré más lento.",
        "Vale, voy a hablarte más fuerte.",
    ],
)
def test_a_voice_change_nothing_made_is_a_claimed_effect(reply: str) -> None:
    assert llm.visible_reply_claims_an_effect(reply, "your speech slower it")


@pytest.mark.parametrize(
    "reply",
    [
        "I can't change how fast my voice speaks.",
        "No puedo hablar más despacio: la velocidad de mi voz no la cambio.",
        "De acuerdo, te hablaré en español.",
        "Claro, seré más breve.",
        "People speak faster when they are nervous.",
    ],
)
def test_saying_the_voice_limit_or_a_manner_of_words_is_not(reply: str) -> None:
    assert not llm.visible_reply_claims_an_effect(reply, "your speech slower it")


# ------------------------------------------------------------------ the facts' field names


def test_the_facts_field_names_are_not_told() -> None:
    # M78 (DEV-D v3l w20-t4).
    reply = (
        "Estás ejecutando como usuario en REDNOTE y la versión de Python no se puede determinar sin información "
        "adicional en los datos de situation."
    )
    facts = {"situation": json.dumps({"kind": "operation", "operation": "system.identity", "polarity": "success",
                                      "verified": True, "succeeded": True,
                                      "observed": {"userName": "usuario", "machineName": "REDNOTE"}})}
    assert llm.compose_visible_defect(reply, "status", "and which one tengo instalada yo?", facts) == (
        "copied_instruction"
    )
