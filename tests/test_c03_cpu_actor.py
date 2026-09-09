"""Computer CPU measurements must not become assistant process/ownership claims."""
import json

import pytest

from baxy_mind import llm


def facts(mission=False):
    situation = {"kind": "operation", "operation": "system.status", "observed": {
        "scope": "cpu", "cpu": {"usagePercent": 23.75, "physicalCoreCount": 6,
                                 "logicalProcessorCount": 8, "model": "Example Processor"},
        "failures": [],
    }}
    if mission:
        situation = {"kind": "status", "cause": "mission_completed", "polarity": "success",
                     "steps": [json.dumps(situation)]}
    return {"situation": situation}


@pytest.mark.parametrize("mission", [False, True])
@pytest.mark.parametrize("reply", [
    "Estoy usando un 23,75% de la CPU.",
    "En este momento estoy ocupando un 23,75 por ciento del procesador.",
    "Tengo un procesador Example Processor con 6 núcleos físicos.",
    "Mi equipo tiene 6 núcleos físicos y 8 procesadores lógicos.",
    "I am using 23.75% of the CPU.",
    "I'm consuming 23.75 percent of the processor.",
    "I have an Example Processor with 6 physical cores.",
    "I have 8 logical processors.",
    "My computer has 6 physical cores.",
])
def test_observed_cpu_rejects_assistant_as_owner_or_measured_process(reply, mission):
    user_text = "How much CPU am I using?" if reply.startswith(("I ", "I'm", "My ")) else "cuánta CPU estoy usando"
    assert llm.compose_visible_defect(reply, "status", user_text, facts(mission)) == "wrong_machine_actor"


class Recorder(llm.LlmRuntime):
    def __init__(self, replies, model="Qwen3-4B-Instruct-2507-Q4_K_M.gguf"):
        self._gguf = model
        self.replies = iter(replies)
        self.payloads = []

    def _post(self, payload):
        self.payloads.append(payload)
        return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}


@pytest.mark.parametrize("reply", [
    "Estás usando un 23,75% de la CPU.",
    "Este equipo está usando un 23,75% de la CPU.",
    "El uso de la CPU es del 23,75%.",
])
def test_correct_cpu_answer_does_not_spend_a_repair(reply):
    client = Recorder([reply])
    assert client.compose_user_message("cuánta CPU estoy usando", "status", facts()) == reply
    assert len(client.payloads) == 1
    assert client.payloads[0]["temperature"] == 0.0


def test_repair_keeps_actual_draft_facts_and_question_with_qualified_sampling():
    bad = "Estoy usando un 23,75% de la CPU."
    good = "Este equipo está usando un 23,75% de la CPU."
    client = Recorder([bad, good])
    assert client.compose_user_message("cuánta CPU estoy usando", "status", facts()) == good
    first, retry = client.payloads
    assert retry["messages"][:2] == first["messages"]
    assert retry["messages"][-2] == {"role": "assistant", "content": bad}
    assert retry["messages"][-1]["role"] == "user"
    assert retry["temperature"] == 0.7
    assert retry["top_p"] == 0.8
    assert retry["top_k"] == 20
    assert retry["min_p"] == retry["presence_penalty"] == retry["seed"] == 0
    assert retry["repeat_penalty"] == 1.0
    assert retry["max_tokens"] == first["max_tokens"]


def test_second_repair_uses_latest_rejected_draft_and_never_demands_first_person():
    first = "Estoy usando un 23,75% de la CPU."
    second = "Mi equipo está usando un 23,75% de la CPU."
    good = "Este equipo está usando un 23,75% de la CPU."
    client = Recorder([first, second, good])
    assert client.compose_user_message("cuánta CPU estoy usando", "status", facts()) == good
    assert len(client.payloads) == 3
    assert client.payloads[2]["messages"][-2]["content"] == second
    assert "First person" not in json.dumps(client.payloads[2]["messages"])


def test_persistent_wrong_actor_exhausts_the_existing_bound_without_publishing_it():
    client = Recorder(["Estoy usando un 23,75% de la CPU."] * 3)
    assert client.compose_user_message("cuánta CPU estoy usando", "status", facts()) == ""
    assert len(client.payloads) == 3


def test_other_model_does_not_inherit_qwen_sampling():
    good = "Este equipo está usando un 23,75% de la CPU."
    client = Recorder(["Estoy usando un 23,75% de la CPU.", good], model="Other-4B.gguf")
    assert client.compose_user_message("cuánta CPU estoy usando", "status", facts()) == good
    assert client.payloads[1]["temperature"] == 0.0
    assert "top_k" not in client.payloads[1]


@pytest.mark.parametrize("situation", [
    {"kind": "knowledge"},
    {"kind": "operation", "operation": "process.list", "observed": {"processes": [{"cpuPercent": 23.75}]}},
    {"kind": "operation", "operation": "audio.status", "observed": {"level": 23}},
    {"kind": "operation", "operation": "system.status", "observed": {"cpu": {}}},
])
def test_missing_whole_cpu_observation_does_not_activate_machine_actor_repair(situation):
    result = llm.compose_visible_defect("Estoy usando un 23,75% de la CPU.", "status", "Describe el uso", {"situation": situation})
    assert result != "wrong_machine_actor"


@pytest.mark.parametrize("reply", ["I have checked the CPU.", "Estoy midiendo el uso de CPU."])
def test_reading_activity_is_not_cpu_ownership_or_process_usage(reply):
    assert llm.compose_visible_defect(reply, "status", "Read the CPU usage", facts()) != "wrong_machine_actor"


@pytest.mark.parametrize("reply", [
    "Este equipo está usando un 99% de la CPU.",
    "Este equipo tiene 8 núcleos físicos y 6 procesadores lógicos.",
    "This computer has 8 physical cores and 6 logical processors.",
    "Physical core count: 8. Logical processor count: 6.",
    "The CPU usage is 99 PERCENT.",
    "The CPU usage is -23.75 per cent.",
    "El uso es del −23,75 porciento.",
    "Este equipo tiene -6 núcleos físicos.",
    "Physical cores: 8. Logical processors: 6.",
])
def test_repair_cannot_change_observed_cpu_quantities(reply):
    user_text = "Show CPU usage and core counts" if reply.startswith(("The ", "This ", "Physical ")) else "Describe el uso de CPU"
    assert llm.compose_visible_defect(reply, "status", user_text, facts()) == "wrong_machine_value"


@pytest.mark.parametrize("reply", [
    "El uso es del 23,75% de la CPU.",
    "El uso es del 23.8 por ciento de la CPU.",
    "CPU usage is 24 percent.",
    "Tiene 6 núcleos físicos y 8 procesadores lógicos.",
    "Physical core count: 6. Logical processor count: 8.",
])
def test_cpu_quantities_allow_decimal_locale_display_rounding_and_labels(reply):
    user_text = "Show CPU usage and core counts" if reply.startswith(("CPU ", "Physical ")) else "Describe el uso de CPU"
    assert llm.compose_visible_defect(reply, "status", user_text, facts()) == ""


def test_wrong_quantity_in_actor_repair_is_rejected_before_existing_last_attempt():
    good = "Este equipo está usando un 23,75% de la CPU."
    client = Recorder(["Estoy usando un 23,75% de la CPU.", "Este equipo está usando un 99% de la CPU.", good])
    assert client.compose_user_message("cuánta CPU estoy usando", "status", facts()) == good
    assert len(client.payloads) == 3
