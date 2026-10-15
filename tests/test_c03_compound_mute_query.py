"""Keep current audio questions separate from conditional computer actions."""
import pytest

from baxy_mind.effect_intent import resolve_explicit_effects

AVAILABLE = {"system.time", "audio.status", "audio.mute", "audio.volume", "app.open", "note.create", "system.power"}


@pytest.mark.parametrize("text,operations", [
    ("Dime la hora y si está silenciado el sonido.", ("system.time", "audio.status")),
    ("What time is it, and is the sound on mute?", ("system.time", "audio.status")),
    ("Dime la fecha y dime si el audio está silenciado.", ("system.time", "audio.status")),
    ("Decime la hora y si el volumen está en silencio.", ("system.time", "audio.status")),
    ("¿Está silenciado el sonido y qué hora es?", ("audio.status", "system.time")),
    ("Is the sound muted, and what time is it?", ("audio.status", "system.time")),
    ("Dime si está silenciado el audio y qué hora es.", ("audio.status", "system.time")),
    ("Check if the sound is muted and what time is it.", ("audio.status", "system.time")),
    ("Dime si el sonido está silenciado.", ("audio.status",)),
    ("Comprueba si el audio está silenciado ahora.", ("audio.status",)),
    ("Check whether the sound is on mute.", ("audio.status",)),
])
def test_current_questions_conserve_all_requested_reads(text, operations):
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None
    assert result.operations == operations


@pytest.mark.parametrize("text", [
    "Dime la hora y si está silenciado el sonido.",
    "What time is it, and is the sound on mute?",
])
@pytest.mark.parametrize("available", [{"system.time"}, {"audio.status"}])
def test_missing_read_never_authorizes_only_the_recognized_subset(text, available):
    assert resolve_explicit_effects(text, available) is None


@pytest.mark.parametrize("text", [
    "Dime la hora y si está silenciado el sonido, apaga el PC.",
    "Dime si está silenciado el sonido y si lo está, abre Steam.",
    "Check if the sound is muted and if it is, open Steam.",
    "Si está silenciado el sonido, abre Steam.",
    "If the sound is muted, shut down the computer.",
    "Dime la hora y si estaba silenciado el sonido ayer.",
    "What time is it and was the sound muted yesterday?",
    "Dime la hora y si está silenciado el televisor.",
    "What time is it and is the microphone muted?",
    'Crea una nota mañana con el texto "si está silenciado el sonido"',
    'Create a note tomorrow with the text "if the sound is muted"',
    'Crea una nota con el texto "si está silenciado" y si está silenciado el sonido, apaga el PC.',
])
def test_conditional_past_and_other_device_requests_do_not_become_current_reads(text):
    assert resolve_explicit_effects(text, AVAILABLE) is None


@pytest.mark.parametrize("text", [
    'Crea una nota titulada Audio con el texto "la hora y si está silenciado el sonido"',
    'Create a note titled Audio with the text "time and is the sound on mute"',
])
def test_quoted_questions_stay_note_content(text):
    result = resolve_explicit_effects(text, AVAILABLE)
    assert result is not None
    assert result.operations == ("note.create",)
