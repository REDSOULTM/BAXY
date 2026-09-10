"""A measured topic and its request keep their meaning across word order."""

import pytest

from baxy_mind.__main__ import _ground_explicit_arguments, _SYSTEM_STATUS_SCOPES
from baxy_mind.effect_intent import operation_domain_is_grounded, resolve_explicit_effects


STATUS_SCHEMA = {
    "type": "object",
    "properties": {"scope": {"type": "string", "enum": sorted(_SYSTEM_STATUS_SCOPES)}},
    "required": [],
    "additionalProperties": False,
}

SCOPES = [
    ("disco C", "disk C", "cuánto espacio está ocupado", "how much space is occupied", "disk"),
    ("RAM", "RAM", "cuánta memoria queda libre", "how much memory is free", "memory"),
    ("CPU", "CPU", "qué modelo tengo", "which model I have", "cpu"),
    ("GPU", "GPU", "qué modelo está instalado", "which model is installed", "gpu_identity"),
    ("batería", "battery", "cuánta carga queda", "how much charge remains", "battery"),
]


@pytest.mark.parametrize("es,en,query_es,query_en,scope", SCOPES)
@pytest.mark.parametrize("form", range(10))
def test_topic_order_language_and_courtesy_preserve_operation_and_arguments(
    es: str, en: str, query_es: str, query_en: str, scope: str, form: int,
) -> None:
    text = [
        f"Sobre mi {es}, dime {query_es}.",
        f"Respecto a {es}, comprueba {query_es}.",
        f"En cuanto a {es}, muéstrame {query_es}.",
        f"Baxy, por favor: sobre {es}, dime {query_es}.",
        f"About my {en}, tell me {query_en}.",
        f"Regarding the {en}; show me {query_en}.",
        f"As for this {en}, check {query_en}.",
        f"Sobre mi {es}, tell me {query_en}.",
        f"About the {en}, dime {query_es}.",
        f"Comprueba {query_es} en mi {es}.",
    ][form]
    result = resolve_explicit_effects(text, {"system.status"})
    assert result is not None
    assert result.operations == ("system.status",)
    assert operation_domain_is_grounded(text, "system.status") is True
    assert _ground_explicit_arguments("system.status", text, STATUS_SCHEMA) == {"scope": scope}
    assert _ground_explicit_arguments(
        "system.status", result.evidence[0], STATUS_SCHEMA,
    ) == {"scope": scope}


@pytest.mark.parametrize(
    "text",
    [
        "Sobre mi RAM, ayer había más libre.",
        "About my CPU, tell me which model I had last year.",
        "Regarding the battery, show me how much charge it will have tomorrow.",
        "Sobre la batería de mi auto, dime cuánta carga queda.",
        "About my phone CPU, tell me which model I have.",
        "About a CPU, tell me how much memory is installed.",
        "Respecto a otra GPU, comprueba qué modelo está instalado.",
        "De mi memoria del colegio, dime qué recuerdo queda.",
        "Sobre el disco de música, dime cuánto dura.",
        "Sobre mi GPU, dime cuál me recomiendas comprar.",
        "Del disco C, no me digas cuánto espacio está ocupado.",
        "Respecto a RAM, no compruebes cuánta queda libre.",
        "About my CPU, do not check the current load.",
        "Repite: «Del disco C, dime cuánto espacio está ocupado».",
        "Translate 'About my CPU, tell me which model I have'.",
        "«Del disco C, dime cuánto espacio está ocupado».",
        "Del disco C, «dime cuánto espacio está ocupado».",
        "Sobre la red neuronal, dime cómo está la conexión.",
        "About my CPU, explain how processors work.",
        "Sobre RAM, si fuera otro equipo dime cuánta tendría.",
        "Sobre GPU, escribe una nota que diga cuánto se está usando.",
        "About my RAM, tell me how much more I should buy.",
        "Tell me how much RAM costs.",
        "About my RAM, tell me how to check how much is free.",
        "About my RAM, tell me how much is free without using tools.",
    ],
)
def test_topics_never_turn_content_or_unobservable_states_into_current_reads(text: str) -> None:
    assert resolve_explicit_effects(text, {"system.status"}) is None


@pytest.mark.parametrize(
    "text,scope",
    [
        ("Tell me how much RAM is free.", "memory"),
        ("Tell me how much disk space is occupied.", "disk"),
        ("Tell me how much battery charge remains.", "battery"),
        ("Sobre CPU y RAM, comprueba el uso actual.", "cpu_memory"),
        ("About the CPU and RAM, show me the current usage.", "cpu_memory"),
        ("Sobre Windows y RAM, dime la versión instalada y cuánta memoria tengo.", "os_memory"),
    ],
)
def test_live_quantities_and_catalog_combined_scopes(text: str, scope: str) -> None:
    result = resolve_explicit_effects(text, {"system.status"})
    assert result is not None and result.operations == ("system.status",)
    assert _ground_explicit_arguments("system.status", text, STATUS_SCHEMA) == {"scope": scope}


def test_fronted_topic_stays_in_the_original_evidence_order() -> None:
    text = "respecto a cpu, comprueba que modelo tengo."
    result = resolve_explicit_effects(text, {"system.status"})
    assert result is not None and result.evidence == (text,)


@pytest.mark.parametrize(
    "text",
    [
        "Sobre CPU y batería, comprueba el uso actual.",
        "Sobre mi RAM, dime cuánta queda libre y borra carta.txt.",
        "About my RAM, check how much is free and open Notepad.",
        "Sobre la batería, dime cuánta carga queda y qué hora es.",
    ],
)
def test_a_status_read_cannot_silently_replace_an_unavailable_remainder(text: str) -> None:
    assert resolve_explicit_effects(text, {"system.status"}) is None
