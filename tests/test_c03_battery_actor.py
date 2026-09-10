"""A measured PC battery does not belong to the assistant."""
import copy
import json

import pytest

from baxy_mind import llm
from test_c03_cpu_actor import Recorder


def facts(mission=False, present=True, percent=17):
    battery = {"isPresent": present, "chargePercent": percent if present else None,
               "isCharging": False if present else None, "isAcOnline": True}
    situation = {"kind": "operation", "operation": "system.status", "verified": True,
                 "succeeded": True, "polarity": "success", "observed": {
                     "scope": "battery", "battery": battery, "failures": []}}
    if mission:
        situation = {"kind": "status", "cause": "mission_completed", "polarity": "success",
                     "steps": [json.dumps(situation)]}
    return {"situation": situation}


@pytest.mark.parametrize("mission", [False, True])
@pytest.mark.parametrize("reply", [
    "Tengo el 100% de batería.", "Tengo un 17 por ciento de batería.",
    "Me queda 17% de batería.", "Estoy al 17% de batería.",
    "Mi batería tiene un 17%.", "Estoy cargando la batería.",
    "Estoy descargando la batería.", "No tengo batería.",
    "I have 17% battery.", "I have 17 percent of battery.",
    "My battery is at 17%.", "I'm charging.", "I am not charging.",
    "I don't have a battery.", "I have no battery.", "I'm discharging.",
])
def test_battery_measurement_rejects_first_person_hardware(reply, mission):
    text = "How much battery is left?" if reply.startswith(("I ", "I'm", "My ")) else "Estado de la batería"
    assert llm.compose_visible_defect(reply, "status", text, facts(mission)) == "wrong_machine_actor"


@pytest.mark.parametrize("mission", [False, True])
@pytest.mark.parametrize("reply", [
    "Te queda un 17% de batería.", "La batería tiene un 17% de carga.",
    "El PC tiene un 17% de batería.", "The battery is at 17%.",
    "Your battery is at 17%.", "This computer has 17% battery remaining.",
    "Tengo una lectura de la batería: 17%.", "I have checked the battery: 17%.",
])
def test_machine_user_and_reading_subjects_are_not_assistant_hardware(reply, mission):
    text = "How much battery is left?" if reply.startswith(("The ", "Your ", "This ", "I ")) else "Estado de la batería"
    assert llm.compose_visible_defect(reply, "status", text, facts(mission)) != "wrong_machine_actor"


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("model", ["Qwen3-4B-Instruct-2507-Q4_K_M.gguf", "Other-4B.gguf"])
def test_existing_actor_repair_preserves_question_facts_and_model_recipe(present, model):
    bad = "Tengo un 17% de batería." if present else "No tengo batería."
    good = "La batería tiene un 17% de carga." if present else "Este PC no tiene batería."
    source = facts(present=present)
    before = copy.deepcopy(source)
    client = Recorder([bad, good], model=model)
    assert client.compose_user_message("cuánta batería tengo", "status", source) == good
    assert source == before
    first, retry = client.payloads
    assert retry["messages"][:-2] == first["messages"]
    assert retry["messages"][-2] == {"role": "assistant", "content": bad}
    assert retry["max_tokens"] == first["max_tokens"]
    if model.startswith("Other"):
        assert retry["temperature"] == 0.0
        assert "top_k" not in retry
    else:
        assert retry["temperature"] == 0.7
        assert (retry["top_p"], retry["top_k"], retry["min_p"]) == (0.8, 20, 0.0)


def test_persistent_wrong_battery_actor_is_not_published():
    client = Recorder(["Tengo el 17% de batería."] * 3)
    assert client.compose_user_message("cuánta batería tengo", "status", facts()) == ""
    assert len(client.payloads) == 3


@pytest.mark.parametrize("observed", [{}, {"battery": {}}, {"memory": {"total": 17}}])
def test_battery_actor_requires_an_actual_battery_observation(observed):
    source = {"situation": {"kind": "operation", "operation": "system.status", "observed": observed}}
    assert llm.compose_visible_defect("Tengo un 17% de batería.", "status", "Estado de la batería", source) != "wrong_machine_actor"
