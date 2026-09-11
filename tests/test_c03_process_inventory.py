"""Process reads keep current measurements and request scope through product seams."""

import copy

import pytest

from baxy_mind.__main__ import _ground_explicit_arguments
from baxy_mind.effect_intent import operation_domain_is_grounded, resolve_explicit_effects
from baxy_mind.llm import _compose_situation_payload


SCHEMA = {
    "type": "object", "additionalProperties": False, "required": [],
    "properties": {
        "sort": {"type": "string", "enum": ["cpu", "memory", "name"]},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
    },
}
REQUESTS = [
    "¿Qué proceso me come tanta RAM?",
    "Qué procesos están corriendo?", "Qué procesos tengo dando vueltas?",
    "Cuántos procesos tengo corriendo?", "Cuántos procesos hay corriendo?",
    "Qué app usa más memoria?", "Lista los procesos por nombre.",
    "Dime cuáles son los procesos que ves ahora.", "Lista cinco procesos que estén corriendo.",
    "Show the running processes on this PC.", "Which processes are running right now?",
    "List the processes by name.", "Mostrame los running processes.",
    "Dime el número de procesos que hay corriendo.", "Cuenta los procesos activos del PC.",
    "Quiero saber cuántos procesos pudiste observar.", "Qué cantidad de procesos está funcionando?",
    "How many processes are running on this PC?", "Count the running processes.",
    "What is the observed process count?", "Cuántos processes están running?",
    "Dime cuántos procesos hay, sin listarlos.", "Lista los tres procesos que más RAM usan.",
    "Qué proceso ocupa más memoria RAM?", "Ordena los procesos por consumo de memoria.",
    "Qué dos procesos tienen más memoria residente?", "Show the top three processes by memory usage.",
    "Which process uses the most RAM?", "List five processes with the largest working set.",
    "Mostrame el top 2 de processes por RAM.", "Dime qué procesos consumen más memoria, con sus valores.",
    "Cuáles son los dos procesos que más CPU usan ahora?", "Qué proceso está consumiendo más CPU?",
    "Quiero ver los procesos que más procesador consumen ahora.",
    "Which processes are using the most CPU right now?", "Show the top three processes by current CPU usage.",
    "Which process is using the most CPU at the moment?", "List two processes by current CPU consumption.",
    "Dame el top 3 de processes por CPU actual.", "Qué procesos están gastando más recursos?",
    "Which processes are consuming the most resources?", "Lista los procesos.",
    "Enumera los procesos activos.", "Tell me the observed process count.",
    "Which app is using the most RAM?", "Qué aplicación está consumiendo más memoria?",
    "Muestra los procesos en ejecución.", "Show the top seven active processes by memory.",
    "Lista los primeros veinte procesos por CPU.", "Count active processes, please.",
    "Dime cuáles son los procesos activos del computador.",
]


@pytest.mark.parametrize("text", REQUESTS)
def test_current_process_questions_reach_the_existing_read_operation(text):
    assert operation_domain_is_grounded(text, "system.process.list")
    result = resolve_explicit_effects(text, {"system.process.list", "system.status"})
    assert result is not None and result.operations == ("system.process.list",)
    assert _ground_explicit_arguments("system.process.list", result.evidence[0], SCHEMA) is not None


@pytest.mark.parametrize("text", [
    "Explica los procesos biológicos.", "Lista procesos judiciales.",
    "Show the hiring processes in our business.", "Explain how a computer process works.",
    "Qué procesos estaban corriendo ayer?", "What is CPU usage?",
    "No listes los procesos.", "Don't show running processes.",
    "Traduce 'show running processes'.", "Dime cuánta RAM tiene mi PC.",
    "Abre una app.", "Escribe una nota sobre procesos activos.",
])
def test_process_vocabulary_does_not_authorize_an_unrequested_inventory(text):
    result = resolve_explicit_effects(text, {"system.process.list", "system.status"})
    assert result is None or "system.process.list" not in result.operations


@pytest.mark.parametrize(("text", "expected"), [
    ("Lista los procesos que más RAM consumen, top 5", {"sort": "memory", "limit": 5}),
    ("Lista cinco procesos que estén corriendo.", {"limit": 5}),
    ("Which process uses the most RAM?", {"sort": "memory", "limit": 1}),
    ("Show the top three processes by current CPU usage.", {"sort": "cpu", "limit": 3}),
    ("Qué dos procesos tienen más memoria residente?", {"sort": "memory", "limit": 2}),
    ("List five processes with the largest working set.", {"sort": "memory", "limit": 5}),
    ("Lista los primeros veinte procesos por CPU.", {"sort": "cpu", "limit": 20}),
    ("List the processes by name.", {"sort": "name"}),
])
def test_rank_and_spoken_size_are_retained_before_argument_inference(text, expected):
    assert _ground_explicit_arguments("system.process.list", text, SCHEMA) == expected


@pytest.mark.parametrize("text", [
    "List the top 51 processes by RAM.", "Lista top 0 de procesos por CPU.",
    "Show process PID 123 using CPU.", "Lista procesos con CPU mayor que 20%.",
    "Lista procesos usando más de 2 GB de memoria.", "Lista procesos por CPU y RAM.",
])
def test_pid_threshold_and_unsupported_page_sizes_are_not_silently_reinterpreted(text):
    assert _ground_explicit_arguments("system.process.list", text, SCHEMA) is None


def situation(sort="memory"):
    return {"kind": "operation", "operation": "system.process.list", "verified": True,
            "succeeded": True, "polarity": "success", "observed": {
                "version": 2, "sort": sort, "observationScope": "accessible_processes",
                "observedProcessCount": 207, "returnedProcessCount": 2, "logicalProcessorCount": 8,
                "processes": [
                    {"name": "Editor", "processId": 731, "workingSetBytes": 125_000_000,
                     "totalProcessorSeconds": 9000, "cpuUsagePercent": 12.5, "sampleDurationSeconds": 0.25},
                    {"name": "Editor", "processId": 927, "workingSetBytes": 64_000_000,
                     "totalProcessorSeconds": 1, "cpuUsagePercent": 3.5, "sampleDurationSeconds": 0.25},
                ],
            }}


@pytest.mark.parametrize("text", [
    "Cuántos procesos hay corriendo?", "Dime cuántos procesos hay, sin listarlos.",
    "Count the running processes.", "What is the observed process count?",
])
def test_count_composition_keeps_observation_scope_without_competing_row_count(text):
    source = situation()
    original = copy.deepcopy(source)
    seen = _compose_situation_payload(source, "es", text)["seen"]
    assert seen == {
        "observedProcessCount": {"value": 207, "unit": "accessible process instances observed before row selection"},
        "observationScope": (
            "processes accessible during this observation; "
            "completeness for the whole PC is not established"
        ),
    }
    assert source == original


@pytest.mark.parametrize("sort", ["memory", "cpu"])
def test_resource_projection_keeps_instance_identity_and_correct_measurement(sort):
    source = situation(sort)
    original = copy.deepcopy(source)
    seen = _compose_situation_payload(source, "en", "List the running processes.")["seen"]
    assert seen["observedProcessCount"] == {
        "value": 207, "unit": "accessible process instances observed before row selection",
    }
    assert seen["returnedProcessCount"] == {"value": 2, "unit": "selected process rows supplied from that observation"}
    assert [row["process_identity"] for row in seen["processes"]] == [
        "Editor (PID 731)", "Editor (PID 927)",
    ]
    first = seen["processes"][0]
    if sort == "cpu":
        assert first["current_cpu_usage"] == {"value": 12.5, "unit": "%"}
        assert first["sampleDurationSeconds"] == 0.25
    else:
        assert first["resident_memory"] == {"value": 125, "unit": "MB"}
    assert "totalProcessorSeconds" not in first
    assert source == original
