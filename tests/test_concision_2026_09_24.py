"""Owner rule 2026-09-24: «es un agente que debe responder corto… conciso y resumido, pero aún así hablar bien…
que te responda conciso y de una». And: a lookup is invisible — no «según…», no site or service named.

Measured before (tanda-01..05, uso-real-01..03, 942 finals): weather finals median 33 words / p90 49, two to four
sentences, because the weather validator demanded the temperature (and the place) whatever was asked — «¿Cuál es la
tasa de humedad de hoy?» → temperature + sky + humidity; the weather instruction always asked for «the current
temperature and sky» and then the asked thing. Conversation replies closed with offers and emojis in 16 % of turns
(«¿Necesitas ayuda con algo en particular? 😄»); knowledge answers ran to four sentences under a 256-token budget;
a story asked for was cut by a 128-token budget and published mid-sentence («…donde»).

Owners: llm._weather_answer_instruction / _weather_fact_defect (asked fact required, other readings optional),
semantic/web.weather_asked_measures, llm._conversation_max_tokens / _complete_sentences, the prompts SYSTEM_PROMPT,
USER_MESSAGE_PROMPT, FREE_CONTENT / CONTENT_DRAFT / ROLEPLAY_DRAFT. Every list mixes Spanish, English and Spanglish
and holds phrasings never seen in a run.
"""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm
from baxy_mind import compose_instructions
from baxy_mind import payload_fact_checks
from baxy_mind import conversation_shape
from baxy_mind import reply_budget
from baxy_mind import weather_facts
from baxy_mind import llm_prompts
from baxy_mind.semantic.web import weather_asked_measures

SEEN = {
    "location": "Rosario",
    "region": "Santa Fe",
    "country": "Argentina",
    "locatedBy": "public_ip_address",
    "temperatureC": 17.3,
    "apparentC": 16.0,
    "humidityPercent": 71,
    "windKmh": 6.1,
    "precipitationMm": 0.0,
    "condition": "nublado",
    "today": {"maxC": 21.0, "minC": 11.2, "rainProbabilityPercent": 6, "sunrise": "07:02", "sunset": "19:21"},
    "tomorrow": {"maxC": 22.5, "minC": 12.5, "rainProbabilityPercent": 35, "condition": "nublado",
                 "sunrise": "07:01", "sunset": "19:22"},
}
PAYLOAD = {"operation": "weather.current", "seen": SEEN}


# --- which measure the question names ----------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("text", "measures"),
    [
        ("¿qué tan húmedo está afuera?", {"humidity"}),
        ("cuánta humedad hay ahorita", {"humidity"}),
        ("is it humid out rn", {"humidity"}),
        ("how windy is it right now", {"wind"}),
        ("¿hay mucho viento hoy o no?", {"wind"}),
        ("what does it feel like outside, la sensación térmica", {"apparent"}),
        ("what's the real feel today", {"apparent"}),
        ("¿a cuántos grados estamos?", {"temperature"}),
        ("qué temperatura y qué humedad hay", {"temperature", "humidity"}),
        ("¿qué tiempo hace hoy?", set()),
        ("va a llover el finde?", set()),
    ],
)
def test_the_measures_a_weather_question_names(text: str, measures: set[str]) -> None:
    assert weather_asked_measures(text) == frozenset(measures)


# --- the validator demands the asked fact, not the rest of the read ----------------------------------------------

@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("¿qué tan húmedo está afuera?", "La humedad está en 71 %."),
        ("is it humid out rn", "Humidity is at 71%."),
        ("how windy is it right now", "The wind is blowing at 6.1 km/h."),
        ("¿hay mucho viento hoy o no?", "No mucho: el viento está en 6 km/h."),
        ("la sensación térmica ahorita?", "Se siente como 16 °C."),
        ("what's the real feel today", "It feels like 16°C."),
        # «¿lloverá?» asks the rain; the temperature is not demanded next to it.
        ("¿lloverá?", "Hay un 6 % de probabilidad de lluvia hoy y un 35 % mañana."),
        ("is it gonna llover mañana", "Mañana hay un 35 % de probabilidad de lluvia."),
    ],
)
def test_a_narrow_question_is_answered_by_its_value_alone(asked: str, reply: str) -> None:
    assert weather_facts._weather_fact_defect(reply, PAYLOAD, asked) == ""
    assert payload_fact_checks._payload_fact_defect(reply, PAYLOAD, asked) == ""


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        # The asked fact is still required: the rest of the read does not replace it.
        ("¿qué tan húmedo está afuera?", "Hoy en Rosario hace 17,3 °C y está nublado."),
        ("how windy is it right now", "It's 17.3°C and cloudy in Rosario."),
        ("la sensación térmica ahorita?", "Hace 17,3 °C."),
        ("¿lloverá?", "Está nublado en Rosario."),
    ],
)
def test_the_asked_fact_is_still_demanded(asked: str, reply: str) -> None:
    assert weather_facts._weather_fact_defect(reply, PAYLOAD, asked) == "missing_state"


def test_a_narrow_answer_still_carries_only_observed_numbers() -> None:
    assert weather_facts._weather_fact_defect("La humedad está en 50 %.", PAYLOAD, "¿qué tan húmedo está afuera?") == "invented_number"


def test_a_place_the_person_named_is_still_named_in_a_narrow_answer() -> None:
    asked = "what's the humidity like in Rosario"
    assert weather_facts._weather_fact_defect("Humidity is 71%.", PAYLOAD, asked) == "missing_state"
    assert weather_facts._weather_fact_defect("In Rosario the humidity is 71%.", PAYLOAD, asked) == ""


@pytest.mark.parametrize("asked", ["¿qué tiempo hace hoy?", "how's the weather looking", "dime el clima de hoy porfa"])
def test_a_general_question_still_gets_the_temperature_and_the_place(asked: str) -> None:
    assert weather_facts._weather_fact_defect("En Rosario hay 17 °C y está nublado.", PAYLOAD, asked) == ""
    assert weather_facts._weather_fact_defect("Está nublado en Rosario.", PAYLOAD, asked) == "missing_state"
    assert weather_facts._weather_fact_defect("Hay 17 °C y está nublado.", PAYLOAD, asked) == "missing_state"


# --- the instruction asks for the one thing asked, and names no service --------------------------------------------

@pytest.mark.parametrize(
    ("asked", "language", "named", "not_named"),
    [
        ("¿qué tan húmedo está afuera?", "es", "humidityPercent", "Di la temperatura actual y el cielo"),
        ("how windy is it right now", "en", "windKmh", "Say the current temperature and sky"),
        ("what does it feel like outside", "en", "apparentC", "Say the current temperature and sky"),
        ("¿a qué hora se pone el sol mañana?", "es", "sale o se pone el sol", "Di la temperatura actual y el cielo"),
        ("va a llover el finde?", "es", "probabilidad de lluvia", "Di la temperatura actual y el cielo"),
        ("where am i right now", "en", "nothing about the weather", "Say the current temperature and sky"),
        ("¿qué tiempo hace hoy?", "es", "Di la temperatura actual y el cielo", "humedad (humidityPercent)"),
    ],
)
def test_the_weather_instruction_names_only_the_asked_focus(
    asked: str, language: str, named: str, not_named: str,
) -> None:
    instruction = weather_facts._weather_answer_instruction(asked, language)
    assert named in instruction
    assert not_named not in instruction
    assert "one short sentence" in instruction or "una oración corta" in instruction


@pytest.mark.parametrize("asked", ["where am i right now", "¿en qué ciudad estoy?", "qué tiempo hace", "humidity?"])
@pytest.mark.parametrize("language", ["es", "en"])
def test_the_weather_instruction_never_invites_naming_the_lookup(asked: str, language: str) -> None:
    folded = weather_facts._weather_answer_instruction(asked, language).casefold()
    for narration in ("public forecast service", "servicio público", "internet address", "dirección pública",
                      "public news feed", "canal público"):
        assert narration not in folded
    assert "where it was read" in folded or "de dónde se leyó" in folded


def test_the_composer_sends_the_focused_weather_instruction() -> None:
    class Recorder(llm.LlmRuntime):
        def __init__(self, replies: list[str]) -> None:
            self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
            self.replies = iter(replies)
            self.requests: list[dict] = []

        def _post(self, payload: dict, **_: object) -> dict:
            self.requests.append(payload)
            return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}

    situation = {
        "kind": "operation", "operation": "weather.current", "polarity": "success", "verified": True,
        "succeeded": True, "observed": {"version": 1, **SEEN, "authority": "open_meteo_forecast_v1"},
    }
    client = Recorder(["La humedad está en 71 %."])
    reply = client.compose_user_message("cuánta humedad hay ahorita", "status", {"situation": json.dumps(situation)})
    assert reply == "La humedad está en 71 %."
    sent = client.requests[0]["messages"][-1]["content"]
    assert "la humedad (humidityPercent)" in sent
    assert "Di la temperatura actual y el cielo" not in sent
    assert len(client.requests) == 1


# --- other reports that recited unasked facts ---------------------------------------------------------------------

def test_minimizing_the_windows_does_not_demand_saying_nothing_was_closed() -> None:
    situation = {"kind": "operation", "operation": "window.minimize.all", "polarity": "success",
                 "verified": True, "succeeded": True, "observed": {"minimized": 6}}
    shape = compose_instructions._compose_shape_instruction(situation, "es", "ve al escritorio")
    assert "that nothing was closed" not in shape
    assert "never say any was closed" in shape


def test_news_headlines_are_quoted_without_outlets() -> None:
    class Recorder(llm.LlmRuntime):
        def __init__(self) -> None:
            self._gguf = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
            self.requests: list[dict] = []

        def _post(self, payload: dict, **_: object) -> dict:
            self.requests.append(payload)
            return {"choices": [{"message": {"content": "Titulares de hoy: A; B; C."}, "finish_reason": "stop"}]}

    headlines = [{"title": t, "source": s, "publishedAt": "Mon, 21 Sep 2026 10:00:00 GMT"}
                 for t, s in (("A", "BBC"), ("B", "Emol"), ("C", "dw.com"))]
    situation = {"kind": "operation", "operation": "web.news.headlines", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": {"count": 3, "headlines": headlines}}
    client = Recorder()
    client.compose_user_message("qué hay de nuevo hoy en las news", "status", {"situation": json.dumps(situation)})
    sent = client.requests[0]["messages"][-1]["content"]
    assert "sin nombrar medios" in sent or "without naming outlets" in sent
    assert "entre paréntesis" not in sent and "in parentheses" not in sent


# --- conversation: budgets sized to the shape, and no half sentence ------------------------------------------------

@pytest.mark.parametrize(
    "text",
    ["qué es un agujero negro", "what's the difference between inches and cm", "oye, why is the sky blue?",
     "explícame qué hace la RAM"],
)
@pytest.mark.parametrize("kind", ["knowledge", None])
def test_a_plain_answer_has_a_one_or_two_sentence_budget(text: str, kind: str | None) -> None:
    assert reply_budget._conversation_max_tokens(None, kind, text) == 128


@pytest.mark.parametrize(
    "text",
    ["explícame paso a paso cómo se cambia una llanta", "give me a detailed rundown of how vaccines work",
     "hazme una lista de los planetas", "cuéntame todo sobre el fútbol americano y sus reglas",
     "tell me a short story about a robot", "write me a poem pa' mi amiga"],
)
def test_a_request_for_more_keeps_room_for_it(text: str) -> None:
    assert reply_budget._conversation_max_tokens(None, "knowledge", text) == 256


def test_budgets_by_shape_and_kind() -> None:
    assert reply_budget._conversation_max_tokens("content_draft", "knowledge", "haz un relato del año 2090") == 320
    assert reply_budget._conversation_max_tokens("roleplay_draft", None, "simula una charla", retry=True) == 320
    assert reply_budget._conversation_max_tokens("free_content", "social", "tell me a joke") == 160
    assert reply_budget._conversation_max_tokens("identity", None, "quién eres") == 128
    assert reply_budget._conversation_max_tokens(None, "social", "epa, qué tal") == 64
    assert reply_budget._conversation_max_tokens(None, "unsupported", "pide un uber") == 96
    # Verification 2026-09-25: the JSON-wrapped repair holds two sentences (96 cut «Por dios, odio estos fallos»).
    assert reply_budget._conversation_max_tokens(None, "knowledge", "qué es un átomo", retry=True) == 160
    assert reply_budget._conversation_max_tokens(None, "social", "por dios, odio estos fallos", retry=True) == 160


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("Primera frase completa. Segunda cortada a mit", "Primera frase completa."),
        ("It depends on thickness. For medium-rare: 3 minutes per side! Then let it", "It depends on thickness. For medium-rare: 3 minutes per side!"),
        ("«Hola», dijo el robot. «¿Qué tal?» Y lue", "«Hola», dijo el robot. «¿Qué tal?»"),
        ("sin ningún final", ""),
    ],
)
def test_a_cut_decode_keeps_its_finished_sentences(text: str, kept: str) -> None:
    assert conversation_shape._complete_sentences(text) == kept


class ChatRecorder(llm.LlmRuntime):
    def __init__(self, replies: list[tuple[str, str]]) -> None:
        self._gguf = "granite-4.2-3b-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.payloads: list[dict] = []

    def _post(self, payload: dict, **_: object) -> dict:
        self.payloads.append(payload)
        content, finish = next(self.replies)
        return {"choices": [{"message": {"content": content}, "finish_reason": finish}]}


def test_a_reply_stopped_by_its_budget_is_published_up_to_its_last_finished_sentence() -> None:
    client = ChatRecorder([("Un agujero negro es una región donde la gravedad no deja escapar la luz. Se forma cuando", "length")])
    answer, _ = client.chat("qué es un agujero negro", history=[], conversation_kind="knowledge", response_language="es")
    assert answer == "Un agujero negro es una región donde la gravedad no deja escapar la luz."
    assert len(client.payloads) == 1


def test_a_cut_reply_with_no_finished_sentence_is_written_again() -> None:
    client = ChatRecorder([
        ("A black hole is a region of spacetime where", "length"),
        (json.dumps({"answer": "A black hole is a region where gravity lets nothing escape, not even light."}), "stop"),
    ])
    answer, _ = client.chat("what's a black hole", history=[], conversation_kind="knowledge", response_language="en")
    assert answer == "A black hole is a region where gravity lets nothing escape, not even light."
    assert len(client.payloads) == 2


# --- the prompts carry the rule, and write no visible sentence ----------------------------------------------------

def test_the_conversation_prompt_asks_for_a_concise_direct_answer() -> None:
    prompt = llm_prompts.SYSTEM_PROMPT
    assert "una o dos oraciones" in prompt
    assert "no cierres ofreciendo ayuda" in prompt
    assert "no uses emojis" in prompt
    assert "sin atribuirlos a fuentes" in prompt
    # Content asked for keeps its needed length.
    assert "relato" in prompt and "extensión que ese contenido necesita" in prompt


def test_a_social_turn_is_one_sentence_without_an_offer() -> None:
    client = ChatRecorder([("¡Epa! Aquí ando.", "stop")])
    answer, _ = client.chat("epa", history=[], conversation_kind="social", response_language="es")
    assert answer == "¡Epa! Aquí ando."
    policy = " ".join(str(message["content"]) for message in client.payloads[0]["messages"][1:-1])
    assert "en una oración" in policy and "ni ofrecer ayuda" in policy
    assert client.payloads[0]["max_tokens"] == 64


def test_the_report_prompt_asks_for_the_asked_thing_only() -> None:
    prompt = llm_prompts.USER_MESSAGE_PROMPT
    assert "una o dos frases" in prompt and "sólo lo pedido" in prompt
    assert "sin ofertas ni emojis" in prompt
    # The failure cause is never cut for brevity.
    assert "Conserva la causa de un fallo" in prompt


@pytest.mark.parametrize("prompt", [llm_prompts.FREE_CONTENT_PRESENTATION_PROMPT, llm_prompts.CONTENT_DRAFT_PRESENTATION_PROMPT,
                                    llm_prompts.ROLEPLAY_DRAFT_PRESENTATION_PROMPT])
def test_written_content_starts_with_the_content(prompt: str) -> None:
    folded = prompt.casefold()
    assert "preamble" in folded or "preámbulo" in folded
    assert "emoji" in folded
