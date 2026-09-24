"""Local clock requests must survive selection and the shared domain gate."""

import pytest

from baxy_mind.effect_intent import (
    operation_domain_is_grounded,
    resolve_explicit_effects,
)


@pytest.mark.parametrize("wrapper", ["{}", "Baxy, {}", "Por favor, {}"])
@pytest.mark.parametrize("utterance", [
    "mostrame la hora", "mostrame la fecha", "pasame la hora",
    "muéstrame la fecha actual", "pásame la fecha de hoy",
    "enséñame la hora local", "dame la fecha", "decime la hora actual",
    "indícame la fecha de hoy", "comprueba la hora local",
    "What is the current local date?", "What is the local time?",
    "Show me the current date", "Give me the local time",
    "Check the current local time", "Tell me today's date",
    "mostrame the current date", "Show me la hora actual",
    "¿Puedes pasarme la hora?", "¿Podrías decirme la fecha?",
    "puedes darme la hora", "puedes mostrarme la fecha",
    "podrías enseñarme la hora local", "puedes indicarme la fecha actual",
    "puedes consultar la hora", "puedes comprobar la fecha de hoy",
])
def test_local_clock_reads_share_selection_and_grounding(
    utterance: str, wrapper: str,
) -> None:
    text = wrapper.format(utterance)
    result = resolve_explicit_effects(text, {"system.time"})
    assert result is not None
    assert result.operations == ("system.time",)
    assert operation_domain_is_grounded(text, "system.time") is True
    assert resolve_explicit_effects(text, {"system.status"}) is None


@pytest.mark.parametrize("text", [
    "mostrame la hora de cierre", "pasame la fecha de la reunión",
    "Show me the date of the event", "Give me the time needed to download it",
    # Tanda 4: «Dime la hora en Madrid» is now the clock read with Madrid's zone
    # (test_uso_real_tanda04_web_answers_time); refused or reported, it is still none.
    "What is the current date in Tokyo?", "No me digas la hora en Madrid",
    "Ayer te pedí la hora en Madrid",
    "What is the CPU time?", "Explícame la fecha", "Define local time",
    "Ayer te pedí la hora", "I asked you for the date yesterday",
    "Si te pidiera la hora, ¿qué harías?", "If I ask for the date, what happens?",
    "No me muestres la hora", "Do not show me the current date",
    "Escribe una nota que diga mostrame la hora",
    "Write a note saying show me the current date",
    "Cambia la fecha", "Set the local time",
    # «¿Qué fecha será mañana?» left this list in tanda 6 (owner order 2026-09-24): the date of a day counted from
    # today is arithmetic on this PC's clock (test_uso_real_tanda06_false_dates). A date named by itself still is not.
    "¿Qué día de la semana será el 4 de julio?",
])
def test_clock_mentions_do_not_authorize_a_current_local_read(text: str) -> None:
    result = resolve_explicit_effects(text, {"system.time"})
    assert result is None or "system.time" not in result.operations
    assert operation_domain_is_grounded(text, "system.time") is False


@pytest.mark.parametrize("text, expected", [
    ("Mostrame la hora y revisa la batería", ("system.time", "system.status")),
    ("Revisa la batería y pasame la fecha", ("system.status", "system.time")),
    ("Show me the current date and check the CPU", ("system.time", "system.status")),
    ("Check the CPU and give me the local time", ("system.status", "system.time")),
    ("Mostrame la fecha y no abras Steam", ("system.time",)),
    ("Give me the local time and do not mute the audio", ("system.time",)),
])
def test_clock_clauses_preserve_other_requests_and_prohibitions(
    text: str, expected: tuple[str, ...],
) -> None:
    result = resolve_explicit_effects(
        text, {"system.time", "system.status", "app.open", "audio.mute"},
    )
    assert result is not None
    assert result.operations == expected
    assert operation_domain_is_grounded(text, "system.time") is True
