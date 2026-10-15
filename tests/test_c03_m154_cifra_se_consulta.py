"""M154 (2026-10-04, App run v4u-devH; owner rules D35 and D52): a figure that changes — an exchange rate, an amount in
another currency — is looked up, never said from memory.

- H-w05-t4 «and in pesos chilenos?» after «Hoy el Bitcoin está en 85.000 dólares.»: the decider in context restated
  «¿Cuántos pesos chilenos son 85.000 dólares?» and talked; the talk said «Today Bitcoin is at 1,850,000 Chilean
  pesos.», forty times off (v4s had looked it up).
- H-s087 «¿cuánto son 350 dólares en euros, más o menos?» → «Son aproximadamente 320 euros.» (v4s and v4u). The
  first-turn market reader read «más o menos» as a sum, and the decider talked.
- DEV-I I-w17-t3 «¿y eso cuánto sería en pesos mexicanos, más o menos?» after «La libra está a 1,17 euros…»: the
  isolated decider talked.

Why it went through: nothing turned a talk on a currency conversion into the search (M53/M104 look up a recipe, a plot
or a figure of the world, never one computed from numbers said), and the talk guard (M95, ``llm.talk_memory_figures``)
judges only years once the conversation writes numbers, since a figure may be computed from them; an amount in another
currency is not, without the rate.

Now (``semantic.web.currency_conversion_request``): a talk on a currency conversion or an exchange rate is
``web.search`` with the request made of what was said — the person's words, their request before with the currency now
wanted, the decider's restatement when its currencies were said, or BAXY's amount in the currency asked. A rate of
BAXY's figure in the same currency (M118 «¿y eso cuánto sale por mes?»), a percentage, units of measure, a currency
named as a fact and the peso of a body are left as they were. The talk guard holds an amount in a currency the
conversation did not say when a conversion was asked and no rate between the two was said.

Second part (coordinator, same family): first messages asking a changing fact of the world with the person's reason
beside it — I-s053 «baxy fijate en cuanto cerro el blue hoy que tengo que cambiar unos dolares…», I-s066, I-s078, G-s071,
H-s055, H-s093 «whats the dollar to mexican peso rate todya, im wiring money to my cousin in guadalajara». The decider
looked them up (its arguments were audited) and M81 asked back, reading «tengo que», «my cousin», «mi viejo» in the
whole message as the person's own data. As M138 did for what follows a question mark, the reason said after the
question and who asked or claims it, said before, are its context (``semantic.notes.question_with_its_reason``); the
question, the decider's restatement and its query are still read for the person's own data.

Rows are quoted with their real text; every other phrasing is our own.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import talk_memory_figures
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.notes import question_with_its_reason
from baxy_mind.semantic.web import asks_currency_conversion, currency_conversion_request
from baxy_mind import turn_decide
from baxy_mind import context_decision
from baxy_mind import direct_arguments
from baxy_mind import argument_payload

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "x-maxUtf8Bytes": 400, "x-nonWhitespace": True},
        "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        "nearby": {"type": "boolean"},
    },
    "required": ["query"],
    "additionalProperties": False,
}


def _tool(operation: str) -> dict[str, Any]:
    schema = (
        SEARCH_SCHEMA if operation == "web.search"
        else {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    )
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "read_only", "parameters": schema}}


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_a, **_k):
        return self.decision

    def prepare_decision(self, *_a, **_k):
        return None

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Cuál?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué quieres que haga?"

    def clarify_unresolved_input(self, *_a, **_k):
        return "¿Qué quieres decir?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def prepare_chat(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


class _Abstaining:
    """The model's own extraction abstains: only BAXY's steps ground the arguments."""

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> argument_payload.DirectArgumentExtraction:
        return argument_payload.DirectArgumentExtraction(arguments=None, evidence=(), fallback_question="¿Qué busco?")

    def formulate_missing_argument_question(self, *_args: object, **_kwargs: object) -> str:
        return "¿Qué busco?"


def _history(said: list[str]) -> list[dict[str, str]]:
    """``said``: the conversation, user first and alternating, ending in the person's message."""

    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]


def _tools() -> dict[str, dict[str, Any]]:
    return {name: _tool(name) for name in OPERATIONS}


def _turn(said: list[str], decision: ContextDecision) -> dict:
    tools = _tools()
    return turn_decide._prepare_turn_result(
        {"id": "m154", "text": said[-1], "history": _history(said)},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (),
        tool_by_name=tools, dialogue_state=DialogueState(),
    )


def _decided(said: list[str], decision: ContextDecision) -> dict:
    """The contextual decider's turn alone, with its decision already given."""

    return context_decision._context_decided_result(
        {"id": "m154", "text": said[-1], "history": _history(said)},
        llm=_Decider(decision), planner_catalog=PlannerCatalog(list(_tools().values())), decided_beforehand=decision,
    )


def _query(said: list[str], objective: str) -> str | None:
    arguments, _ = direct_arguments._direct_arguments_result(
        {"operation": "web.search", "text": objective, "history": _history(said)},
        llm=_Abstaining(), tool=_tool("web.search"), dialogue_state=DialogueState(),
    )
    return None if arguments is None else arguments.get("query")


def _talk(request: str) -> ContextDecision:
    return ContextDecision(request, "talk", (), "")


# ------------------------------------------------------------------ 1. the rows, with the decider's v4u decision

H_W05 = [
    "qué news hay hoy en Chile?",
    "Titulares de hoy: 1) el Banco Central mantuvo la tasa en 4,5 %; 2) la Línea 7 del Metro parte su marcha blanca; "
    "3) un sistema frontal traerá lluvia a la zona central el sábado.",
    "ok la número dos, can you dig a bit deeper? quiero saber cuándo la voy a poder usar",
    "La Línea 7 une Renca con Vitacura; en marcha blanca funciona de 7:00 a 21:00 sin cobro y abre comercialmente en "
    "noviembre.",
    "ok y cuánto está el bitcoin en dólares",
    # v4u's own reply to t3.
    "Hoy el Bitcoin está en 85.000 dólares.",
    "and in pesos chilenos?",
]


def test_h_w05_t4_the_bitcoin_in_another_currency_is_looked_up_as_the_request_before_it() -> None:
    result = _turn(H_W05, _talk("¿Cuántos pesos chilenos son 85.000 dólares?"))
    assert (result["kind"], result["operation"]) == ("action", "web.search")
    # The person's request before, in the currency now wanted: the bitcoin stays what is priced.
    assert result["objective"] == "ok y cuánto está el bitcoin en pesos chilenos"
    assert _query(H_W05, result["objective"]) == "cuanto esta el bitcoin en pesos chilenos"


def test_h_w05_t4_with_the_set_history_too() -> None:
    said = [*H_W05[:5], "El bitcoin está en unos 98.400 dólares ahora.", H_W05[-1]]
    result = _turn(said, _talk("¿Cuántos pesos chilenos son 98.400 dólares?"))
    assert (result["kind"], result["operation"], result["objective"]) == (
        "action", "web.search", "ok y cuánto está el bitcoin en pesos chilenos",
    )


H_S087 = "¿cuánto son 350 dólares en euros, más o menos?"


def test_h_s087_an_amount_in_another_currency_said_first_is_looked_up_with_the_persons_words() -> None:
    result = _turn([H_S087], _talk("¿Cuántos euros son 350 dólares?"))
    assert (result["kind"], result["operation"]) == ("action", "web.search")
    assert _query([H_S087], H_S087) == H_S087


H_S093 = "whats the dollar to mexican peso rate todya, im wiring money to my cousin in guadalajara"


def test_h_s093_the_rate_the_decider_looked_up_is_not_asked_back_over_the_persons_reason() -> None:
    searched = ContextDecision(
        "What's the USD to Mexican peso rate today?", "action", ("web.search",), "",
        (("query", "USD to Mexican peso exchange rate today"),),
    )
    result = _decided([H_S093], searched)
    assert (result["kind"], result["operation"]) == ("action", "web.search")


I_W17 = [
    "¿podrías decirme cómo está el dólar hoy, por favor?",
    "Ahora el dólar está a 0,92 euros, casi plano respecto a ayer.",
    "¿y la libra, cómo anda?",
    "La libra está a 1,17 euros, subiendo un poco.",
    "¿y eso cuánto sería en pesos mexicanos, más o menos?",
]


def test_i_w17_t3_the_restatement_with_the_amount_said_is_what_is_looked_up() -> None:
    result = _turn(I_W17, _talk("¿Cuántos pesos mexicanos son 1,17 euros?"))
    assert (result["kind"], result["operation"], result["objective"]) == (
        "action", "web.search", "¿Cuántos pesos mexicanos son 1,17 euros?",
    )


# ------------------------------------------------------------------ 2. our own variants, es and en, first and follow-up


@pytest.mark.parametrize(
    "text",
    [
        "¿cuántos yenes son 100 dólares?",
        "how much is 20 euros in dollars",
        "convierte 50 libras esterlinas a euros",
        "what's the exchange rate between the euro and the yen",
        "oye, ¿a cómo está el euro en pesos chilenos hoy?",
        "200 canadian dollars to us dollars?",
    ],
)
def test_a_first_message_asking_a_currency_conversion_is_looked_up(text: str) -> None:
    assert asks_currency_conversion(text)
    result = _turn([text], _talk(text))
    assert (result["kind"], result["operation"]) == ("action", "web.search")


@pytest.mark.parametrize(
    ("said", "restated", "objective"),
    [
        # The restatement names both currencies, each said: it is the request.
        (["cuánto cuesta el pasaje a Miami", "El pasaje sale 450 dólares ida y vuelta.", "y en euros?"],
         "¿Cuántos euros son 450 dólares?", "¿Cuántos euros son 450 dólares?"),
        # No usable restatement: BAXY's amount, in the currency asked, with the person's «in».
        (["what does the PS5 Pro cost over there?", "It costs 799 dollars.", "how much is that in yen"],
         "how much is that in yen", "799 dollars in yen"),
        (["y la mudanza cuánto sale", "Sale 18 500 pesos mexicanos con embalaje.", "¿y eso cuánto sería en dólares?"],
         "¿y eso cuánto sería en dólares?", "18500 pesos mexicanos en dólares"),
        # The request before asked in a currency: the same request in the one wanted now.
        (["¿cuánto son 350 dólares en euros?", "350 dólares son unos 300 euros.", "¿y en yenes?"],
         "¿y en yenes?", "¿cuánto son 350 dólares en yenes?"),
        (["how much is an ounce of gold in dollars", "An ounce of gold is about 2,650 dollars.", "and in euros?"],
         "and in euros?", "how much is an ounce of gold in euros"),
    ],
)
def test_a_follow_up_naming_the_currency_wanted_is_looked_up_with_what_was_said(
    said: list[str], restated: str, objective: str,
) -> None:
    result = _turn(said, _talk(restated))
    assert (result["kind"], result["operation"], result["objective"]) == ("action", "web.search", objective)


def test_a_restatement_with_a_currency_nobody_said_is_not_the_request() -> None:
    said = ["cuánto cuesta el pasaje a Miami", "El pasaje sale 450 dólares ida y vuelta.", "y en euros?"]
    # «libras» was never said: BAXY's own amount goes in the currency asked instead.
    assert currency_conversion_request(said[-1], "¿Cuántos euros son 450 libras?", said[1], said[0]) == (
        "450 dólares en euros"
    )


# ------------------------------------------------------------------ 3. what must not change


@pytest.mark.parametrize(
    ("said", "decision"),
    [
        # M118: a rate of BAXY's figure in the same currency is worked out from its numbers.
        (["cuánto pago de luz al año", "Pagas 1.200.000 pesos al año.", "¿y eso cuánto sale por mes?"],
         _talk("¿Cuánto son 1.200.000 pesos por mes?")),
        (["how much do I spend on rent a year", "You spend 18,000 dollars a year.", "and how much is that per month?"],
         _talk("How much is 18,000 dollars per month?")),
        # A percentage, units of measure, a currency named as a fact.
        (["¿cuánto es 15 % de 200?"], _talk("¿Cuánto es el 15 % de 200?")),
        (["cuántos centímetros son 3 pulgadas"], _talk("¿Cuántos centímetros son 3 pulgadas?")),
        (["qué moneda usan en Japón"], _talk("¿Qué moneda usan en Japón?")),
        (["what currency do they use in Switzerland?"], _talk("What currency is used in Switzerland?")),
        (["¿por qué el dólar sube frente al euro?"], _talk("¿Por qué el dólar sube frente al euro?")),
        (["oye baxy cuanto es el 18% de 450 pesos de propina"], _talk("¿Cuánto es el 18 % de 450 pesos?")),
        (["cuanto son 180 libras en kilos mas o menos"], _talk("¿Cuántos kilos son 180 libras?")),
        # «pesos» of a body or of a gym, and a weight follow-up.
        (["¿cuál es mi peso ideal en libras?"], _talk("¿Cuál es mi peso ideal en libras?")),
        (["levanto pesos de 20 kilos, ¿cuánto es eso en libras?"], _talk("¿Cuántas libras son 20 kilos?")),
        (["¿cuánto peso?", "Pesas 80 kilos, según tu última nota.", "¿y en libras?"], _talk("¿Cuántas libras son 80 kilos?")),
        # Spending told, not a conversion asked.
        (["gasté 50 dólares en la tienda y 20 euros en el bar"], _talk("Gasté 50 dólares y 20 euros.")),
    ],
)
def test_what_is_no_currency_conversion_keeps_the_deciders_talk(said: list[str], decision: ContextDecision) -> None:
    result = _turn(said, decision)
    assert result["kind"] == "conversation"


def test_a_question_back_on_one_currency_stays_a_question() -> None:
    # G-s078-like: where the cousin lives is the person's; one currency named, no conversion asked.
    text = "eh, ¿a cuánto está el dólar donde vive mi primo?"
    result = _decided([text], ContextDecision(text, "clarify", (), "¿Dónde vive tu primo?"))
    assert result["kind"] == "clarify"


def test_code_that_converts_currencies_is_written() -> None:
    text = "escríbeme una función en python que convierta dólares a euros"
    result = _turn([text], _talk("Escribe una función en Python que convierta dólares a euros."))
    assert result["kind"] == "conversation"


# ------------------------------------------------------------------ 4. the talk guard (M95 with D52)

BITCOIN = ["ok y cuánto está el bitcoin en dólares", "Hoy el Bitcoin está en 85.000 dólares."]


@pytest.mark.parametrize(
    ("reply", "asked", "dialogue", "held"),
    [
        ("Son aproximadamente 320 euros.", H_S087, [], ["320"]),
        ("Today Bitcoin is at 1,850,000 Chilean pesos.", "and in pesos chilenos?", BITCOIN, ["1,850,000"]),
        ("With the dollar at 945 pesos, that is about 80 million Chilean pesos.", "and in pesos chilenos?", BITCOIN,
         ["945", "80"]),
        ("350 dólares son unos 300 euros.", "¿cuánto son 350 dólares en euros?", [], ["300"]),
    ],
)
def test_an_amount_in_another_currency_from_memory_is_held(
    reply: str, asked: str, dialogue: list[str], held: list[str],
) -> None:
    assert talk_memory_figures.talk_memory_figures(reply, asked, dialogue, dialogue[:1]) == held


@pytest.mark.parametrize(
    ("reply", "asked", "dialogue"),
    [
        # The rate was said: what follows from it is computed.
        ("Son unos 94.500 pesos.", "¿y 100 dólares cuántos pesos son?", ["a cuánto está el dólar", "Hoy el dólar está a 945 pesos."]),
        # M118, a percentage, a fact about a currency.
        ("Son 100.000 pesos por mes.", "¿y eso cuánto sale por mes?", ["cuánto pago al año", "Pagas 1.200.000 pesos al año."]),
        ("El 18 % de 450 pesos son 81 pesos.", "oye baxy cuanto es el 18% de 450 pesos de propina", []),
        ("En Japón usan el yen.", "qué moneda usan en Japón", []),
        ("180 libras son unos 81,6 kilos.", "cuanto son 180 libras en kilos mas o menos", []),
    ],
)
def test_what_is_computed_or_no_conversion_passes(reply: str, asked: str, dialogue: list[str]) -> None:
    assert talk_memory_figures.talk_memory_figures(reply, asked, dialogue, dialogue[:1]) == []


# ------------------------------------------------------------------ 5. the reason beside the question is no own data (M81)


def _searched(request: str, query: str) -> ContextDecision:
    return ContextDecision(request, "action", ("web.search",), "", (("query", query),))


@pytest.mark.parametrize(
    ("text", "decision"),
    [
        # The rows, with the isolated decider's search (the App's decider gave the same fields).
        ("baxy fijate en cuanto cerro el blue hoy que tengo que cambiar unos dolares para pagar el alquiler",
         _searched("Fijate en cuánto cerró el dólar hoy para cambiar unos dólares y pagar el alquiler.",
                   "¿Cuánto cerró el dólar hoy en Argentina?")),
        ("oye cachai a cuánto está el dólar hoy día, es que tengo que pagarle al gringo del depto",
         _searched("¿A cuánto está el dólar hoy en Argentina?", "¿A cuánto está el dólar hoy en Argentina?")),
        ("che, nada, mi viejo me preguntó cuántos habitantes tiene Mar del Plata y la verdad ni idea, fijate vos",
         _searched("¿Cuántos habitantes tiene Mar del Plata?", "¿Cuántos habitantes tiene Mar del Plata?")),
        ("che, viste a cómo anda el dólar blue hoy, tengo que cambiar unos mangos antes del viaje",
         _searched("¿A cuánto está hoy el dólar blue?", "dólar blue hoy Argentina")),
        ("oye, mi cuñado jura que el Betis va segundo en la Liga ahora mismo, ¿me miras la clasificación a ver si es "
         "verdad o me está vacilando?",
         _searched("Busca la clasificación de la Liga de España para ver si el Betis está segundo.",
                   "Clasificación Liga España Betis segundo.")),
        (H_S093, _searched("What's the USD to Mexican peso rate today?", "USD to Mexican peso exchange rate today")),
        # Our own, es and en.
        ("qué tiempo hace en Curicó, voy a ir a la playa con mis primos",
         _searched("¿Qué tiempo hace en Curicó?", "clima Curicó hoy")),
        ("my brother swears the Lakers won last night, can you check?",
         _searched("Did the Lakers win last night?", "Lakers result last night")),
        ("what's the euro at today, I'm paying my landlord in euros",
         _searched("What's the euro exchange rate today?", "euro exchange rate today")),
    ],
)
def test_a_public_question_with_the_persons_reason_is_looked_up(text: str, decision: ContextDecision) -> None:
    assert question_with_its_reason(text) is not None
    result = _decided([text], decision)
    assert (result["kind"], result["operation"]) == ("action", "web.search")


@pytest.mark.parametrize(
    ("text", "decision"),
    [
        # The person's own data is the question itself.
        ("eh, ¿a cuánto está el dólar donde vive mi primo?", _searched("¿A cuánto está el dólar hoy?", "dólar hoy")),
        ("oiga parce, ¿a qué hora es que juega mi equipo hoy?", _searched("¿A qué hora juega mi equipo hoy?", "partido hoy")),
        ("tengo que cambiar dólares", _searched("Cambiar dólares", "dónde cambiar dólares")),
        # The question asks about the person who asked it («su casa»): they stay in it.
        ("mi mamá pregunta si va a llover en su casa", _searched("¿Va a llover en la casa de mamá?", "lluvia")),
        # A thing the need picks out is no reason: «el auto que tengo que comprar».
        ("¿cuánto cuesta el auto que tengo que comprar?", _searched("¿Cuánto cuesta el auto?", "precio auto")),
        # The question is the person's own, with a reason after it.
        ("¿cuándo es mi cita con el dentista?, tengo que saberlo", _searched("¿Cuándo es mi cita?", "cita dentista")),
        # The reason is clean, but what the decider would look up names the person's own data.
        ("qué tiempo hace allá, voy a ir a ver a mi abuela", _searched("¿Qué tiempo hace donde vive mi abuela?", "clima")),
    ],
)
def test_the_persons_own_data_in_the_question_is_still_asked(text: str, decision: ContextDecision) -> None:
    result = _decided([text], decision)
    assert result["kind"] == "clarify"


@pytest.mark.parametrize(
    "text",
    [
        "a cuánto me queda la cuenta del depto",
        "tengo que cambiar dólares",
        "¿cuánto es lo que tengo que pagar de luz?",
        "Life is boring and i need to spend my leisure time by watching movie. Will you find a good movie to watch?",
    ],
)
def test_no_reason_is_read_apart_from_these(text: str) -> None:
    assert question_with_its_reason(text) is None
