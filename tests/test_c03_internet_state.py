"""Local connectivity questions must not acquire authority to search the web."""
import pytest

from baxy_mind.effect_intent import resolve_explicit_effects


AVAILABLE = {"network.status", "wifi.status", "web.search", "system.time", "note.create"}


@pytest.mark.parametrize("user_text", [
    "Is this computer connected to the internet?",
    "Is my PC connected to the internet right now?",
    "Is the computer connected to internet?",
    "Am I connected to the internet?",
    "Is this machine online?",
    "¿Está este equipo conectado a internet?",
    "¿Está mi PC conectado a internet ahora?",
    "Revisa si mi computador está conectado a internet.",
    "Comprueba si este equipo está conectado a internet.",
    "Check whether this computer is connected to the internet.",
])
def test_local_internet_connection_question_reads_only_connectivity(user_text: str) -> None:
    result = resolve_explicit_effects(user_text, AVAILABLE)
    assert result is not None
    assert result.operations == ("network.status",)


@pytest.mark.parametrize("user_text", [
    "Is this computer connected to the internet?",
    "¿Está este equipo conectado a internet?",
])
def test_missing_connectivity_operation_does_not_substitute_web_search(user_text: str) -> None:
    assert resolve_explicit_effects(user_text, AVAILABLE - {"network.status"}) is None


@pytest.mark.parametrize("user_text", [
    "Search the internet for network troubleshooting guides.",
    "Busca en internet cómo funciona una conexión de red.",
])
def test_actual_web_search_keeps_its_own_operation(user_text: str) -> None:
    result = resolve_explicit_effects(user_text, AVAILABLE)
    assert result is not None
    assert result.operations == ("web.search",)


@pytest.mark.parametrize("user_text", [
    "How does a computer connect to the internet?",
    "¿Cómo se conecta un computador a internet?",
    "Is the computer in that movie connected to the internet?",
    "Is my phone connected to the internet?",
    "Don't check whether this computer is connected to the internet.",
    "No compruebes si este equipo está conectado a internet.",
    'Create a note called "Is this computer connected to the internet?".',
])
def test_neighbouring_intents_do_not_gain_a_local_connectivity_read(user_text: str) -> None:
    result = resolve_explicit_effects(user_text, AVAILABLE)
    assert result is None or "network.status" not in result.operations


def test_connectivity_question_does_not_swallow_another_requested_read() -> None:
    result = resolve_explicit_effects(
        "Is this computer connected to the internet, and what time is it?", AVAILABLE,
    )
    assert result is None or result.operations == ("network.status", "system.time")
