"""REOPEN1957 H0170/H0376 «conectate al wifi de casa» (D24, grupo H): «casa» no
es un SSID. El primer turno lista las redes guardadas y conecta la asociada al
lugar; sin asociación, el final nombra las guardadas y pregunta cuál es. La
respuesta con el nombre conecta esa red y la deja asociada al lugar. «wifi de
la luna» (H0739) sigue siendo un fallo honesto por nombre inexistente."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({"wifi.profile.list", "wifi.connect.named", "wifi.ensure.connected", "wifi.status", "app.open"})
SCHEMA = {
    "type": "object",
    "properties": {"place": {"type": ["string", "null"], "enum": ["casa", "oficina", "trabajo", None]}, "profileName": {"type": "string"}},
    "required": ["profileName"],
    "additionalProperties": False,
}
QUESTION = "Todavía no sé cuál de tus redes guardadas es la de casa: tenés Fibertel-2G y Vecino. ¿Cuál es?"


def _history(*turns: tuple[str, str]) -> list[dict[str, str]]:
    return [{"role": role, "content": content} for role, content in turns]


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("conectate al wifi de casa", "casa"),
        ("conéctate al wifi de casa", "casa"),
        ("connect to my home wifi", "casa"),
        ("cambia el wifi al de casa", "casa"),
        ("conectate a la red wifi de mi casa", "casa"),
        ("conectame al wifi del trabajo", "trabajo"),
        ("connect to the office wifi", "oficina"),
    ],
)
def test_a_place_lists_the_saved_networks_and_connects_by_association(text: str, place: str) -> None:
    assert effect_intent.wifi_place_request(text) == place
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("wifi.profile.list", "wifi.connect.named")
    assert mind._ground_explicit_arguments("wifi.connect.named", text, SCHEMA) == {"profileName": place, "place": place}
    assert effect_intent.operation_domain_is_grounded(text, "wifi.profile.list") is True
    assert effect_intent.operation_domain_is_grounded(text, "wifi.connect.named") is True


@pytest.mark.parametrize("text", ["conectate al wifi de la luna", "conectate al wifi de Galaxy", "Connect to the Wi-Fi network called Home", "cambia el wifi a EV 2"])
def test_a_name_that_is_not_a_place_stays_a_profile_name(text: str) -> None:
    assert effect_intent.wifi_place_request(text) is None
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, (), ())
    assert intent is not None and intent.operations == ("wifi.connect.named",)
    grounded = mind._ground_explicit_arguments("wifi.connect.named", text, SCHEMA)
    assert grounded is not None and "place" not in grounded


def test_a_negation_asks_for_nothing() -> None:
    assert effect_intent.wifi_place_request("no te conectes al wifi de casa") is None
    assert effect_intent.resolve_explicit_effects("no te conectes al wifi de casa", AVAILABLE, (), ()) is None


@pytest.mark.parametrize(
    ("answer", "name"),
    [("Fibertel-2G", "Fibertel-2G"), ("es la Fibertel-2G", "Fibertel-2G"), ("se llama Vecino", "Vecino"), ("la de casa es Fibertel-2G", "Fibertel-2G"), ("it's Fibertel-2G", "Fibertel-2G")],
)
def test_the_answer_names_the_network_and_keeps_the_place(answer: str, name: str) -> None:
    history = _history(("user", "conectate al wifi de casa"), ("assistant", QUESTION), ("user", answer))
    assert effect_intent.wifi_place_answer(answer, history) == (name, "casa")
    intent = effect_intent.wifi_place_answer_intent(answer, history, AVAILABLE)
    assert intent is not None and intent.operations == ("wifi.connect.named",)
    assert mind._ground_explicit_arguments("wifi.connect.named", answer, SCHEMA, history=history) == {"profileName": name, "place": "casa"}


@pytest.mark.parametrize("answer", ["hola", "no", "abrí spotify", "Fibertel-2G y Vecino", "¿cuál tenés?", "gracias"])
def test_what_is_not_a_name_is_not_read_as_one(answer: str) -> None:
    history = _history(("user", "conectate al wifi de casa"), ("assistant", QUESTION), ("user", answer))
    assert effect_intent.wifi_place_answer(answer, history) is None


def test_a_bare_name_needs_the_question_but_an_explicit_form_does_not() -> None:
    after_success = _history(("user", "conectate al wifi de casa"), ("assistant", "Listo, te conecté a la red de casa."))
    assert effect_intent.wifi_place_answer("Fibertel-2G", after_success) is None
    assert effect_intent.wifi_place_answer("la de casa es Fibertel-2G", after_success) == ("Fibertel-2G", "casa")
    unrelated = _history(("user", "abrí spotify"), ("assistant", QUESTION))
    assert effect_intent.wifi_place_answer("Fibertel-2G", unrelated) is None


def test_the_unknown_place_failure_is_not_replanned() -> None:
    assert "wifi_place_unknown" in mind._NO_REPLAN_ERROR_CODES
    assert "wifi_place_unknown" in llm._CAUSE_FACT


def _failed_mission_payload() -> dict:
    situation = {
        "kind": "failure",
        "cause": "mission_failed",
        "polarity": "failure",
        "steps": [
            '{"kind":"operation","operation":"wifi.profile.list","polarity":"success","verified":true,"succeeded":true,'
            '"observed":{"version":1,"profiles":[{"profileId":"w1","label":"Fibertel-2G"},{"profileId":"w2","label":"Vecino"}],"authority":"netsh_wlan_profile_snapshot"}}'
        ],
        "reason": {"kind": "operation", "operation": "wifi.connect.named", "polarity": "failure", "verified": False, "succeeded": False, "cause": "wifi_place_unknown"},
    }
    return llm._compose_situation_payload(situation, "es", "conectate al wifi de casa")


def test_the_failed_mission_carries_the_saved_networks_and_the_place() -> None:
    payload = _failed_mission_payload()
    assert payload["seen"] == {"savedNetworks": ["Fibertel-2G", "Vecino"], "place": "casa"}
    assert "completedStepsInOrder" not in payload
    assert payload["reason"]["cause"] == llm._CAUSE_FACT["wifi_place_unknown"]


@pytest.mark.parametrize(
    ("text", "defect"),
    [
        ("Todavía no sé cuál de tus redes guardadas es la de casa: tenés Fibertel-2G y Vecino. ¿Cuál es?", ""),
        ("Te conecté a la red de casa.", "missing_state"),
        ("¿Cuál es la de casa? Ya te conecté.", "reversed_polarity"),
        ("No sé cuál es la de casa. ¿Cuál es?", "missing_state"),
    ],
)
def test_the_reply_lists_the_saved_networks_and_asks(text: str, defect: str) -> None:
    assert llm._payload_fact_defect(text, _failed_mission_payload(), "conectate al wifi de casa") == defect


def test_a_verified_connect_by_place_says_it_connected() -> None:
    payload = {"operation": "wifi.connect.named", "seen": {"connected": True, "place": "casa"}}
    assert llm._payload_fact_defect("Listo, te conecté a la red de casa.", payload, "conectate al wifi de casa") == ""
    assert llm._payload_fact_defect("La red de casa es Fibertel.", payload, "conectate al wifi de casa") == "missing_state"
