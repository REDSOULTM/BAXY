"""Fase 3.5: the dialogue slot decides when a message depends on the previous turns.

The phrases here are deliberately not the owner's test nor the held-out script: the slot is a
rule about the shape of dialogue (a bare answer, «sí», a new destination, a pronoun object, a
lookup without topic), not a list of sentences.
"""

from __future__ import annotations

import pytest

from baxy_mind.semantic import dialogue as dialogue_slot
from baxy_mind.semantic.dialogue import DialogueSlot


def _slot(pending: str | None = None, antecedents=(), reply: str | None = None) -> DialogueSlot:
    return DialogueSlot(pending, reply if pending else None, tuple(antecedents), reply)


@pytest.mark.parametrize(
    "text",
    ["35", "treinta", "al 80%", "unos diez", "sí", "dale, sí", "ok", "no, en Spotify", "por WhatsApp mejor"],
)
def test_a_short_answer_to_the_pending_question_depends_on_it(text):
    slot = _slot("subí el brillo", ["subí el brillo"], "¿Cuánto lo subo?")
    assert dialogue_slot.dependency(text, slot) == "answer"


@pytest.mark.parametrize(
    "text",
    [
        "gracias",
        "jaja qué bueno",
        "ayer me quedé dormido viendo una serie larguísima",
        "la verdad es que hoy no tengo ganas de nada",
    ],
)
def test_talk_never_fills_the_slot_even_with_a_question_pending(text):
    slot = _slot("subí el brillo", ["subí el brillo"], "¿Cuánto lo subo?")
    assert dialogue_slot.dependency(text, slot) is None


@pytest.mark.parametrize(
    "text, antecedent",
    [
        ("apagalo", "prendé el bluetooth"),
        ("ahora cerrala", "abrí la calculadora"),
        ("buscalo en internet", "me recomendaron un libro que se llama Dune"),
        ("lo subís a 60", "poné el volumen en 30"),
    ],
)
def test_a_pronoun_object_is_a_reference(text, antecedent):
    assert dialogue_slot.dependency(text, _slot(None, [antecedent], "Listo.")) == "reference"


@pytest.mark.parametrize(
    "text, antecedent",
    [
        ("averiguá quién ganó", "anoche jugó Boca contra River"),
        ("fijate si ya salió el tráiler", "estoy esperando la nueva de Dune"),
    ],
)
def test_a_lookup_without_its_topic_depends_on_the_last_one(text, antecedent):
    assert dialogue_slot.dependency(text, _slot(None, [antecedent], "Qué bueno.")) == "topic"


def test_without_context_nothing_depends_on_it():
    assert dialogue_slot.dependency("apagalo", _slot()) is None
    assert dialogue_slot.dependency("35", _slot()) is None


@pytest.mark.parametrize(
    "pending, answer, joined",
    [
        ("subí el brillo", "treinta", "subí el brillo 30"),
        ("bajá la música", "a 10", "bajá la música a 10"),
        ("poné algo de jazz en Spotify", "no, en YouTube", "poné algo de jazz en YouTube"),
        ("abrí una canción de rock", "en YouTube mejor", "abrí una canción de rock en YouTube"),
        ("abrí el explorador", "sí, dale", "abrí el explorador"),
    ],
)
def test_the_pending_request_is_completed_in_the_persons_own_words(pending, answer, joined):
    assert dialogue_slot.joined_answer(pending, answer) == joined


def test_a_rewrite_may_only_use_words_already_said():
    slot = _slot(None, ["prendé el bluetooth"], "Listo, el Bluetooth está encendido.")
    assert dialogue_slot.rewrite_stays_in_context("apagá el bluetooth", "apagalo", slot)
    assert not dialogue_slot.rewrite_stays_in_context("apagá el wifi", "apagalo", slot)
    assert not dialogue_slot.rewrite_stays_in_context("abrí Spotify y apagá el bluetooth", "apagalo", slot)


def test_the_slot_reads_the_shell_pending_request_and_the_last_two_user_turns():
    history = [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "¡Hola!"},
        {"role": "user", "content": "subí el brillo"},
        {"role": "assistant", "content": "¿Cuánto lo subo?"},
        {"role": "user", "content": "treinta"},
    ]
    slot = dialogue_slot.read_slot({"pendingObjective": "subí el brillo"}, history, "treinta")
    assert slot.pending_request == "subí el brillo"
    assert slot.pending_question == "¿Cuánto lo subo?"
    assert slot.antecedents == ("subí el brillo", "hola")


@pytest.mark.parametrize(
    "text, antecedent, rearmed",
    [
        ("apagalo", "prendé el bluetooth", "apaga el bluetooth"),
        ("ahora bajala a 10", "poné la música de fondo a 40", "ahora baja la música de fondo a 10"),
        ("cerrala", "abrí la calculadora", "cerra la calculadora"),
    ],
)
def test_a_pronoun_takes_the_object_of_the_previous_order(text, antecedent, rearmed):
    # 2026-09-22: with an antecedent the pronoun is never "whatever window is in front".
    assert dialogue_slot.substituted_reference(text, antecedent) == rearmed


def test_an_indirect_pronoun_or_a_question_is_not_substituted():
    assert dialogue_slot.substituted_reference("devolvele el sonido", "silenciá el sonido") is None
    assert dialogue_slot.substituted_reference("cerralo", "¿qué hora es?") is None


@pytest.mark.parametrize(
    "text",
    ["no", "no, dejalo", "mejor no", "nah, olvidalo", "no gracias", "no hace falta", "no thanks", "never mind", "cancelá"],
)
def test_a_refusal_never_completes_the_pending_request(text):
    slot = _slot("abrí Photoshop", ["abrí Photoshop"], "¿Lo abro?")
    assert dialogue_slot.dependency(text, slot) is None


def test_a_correction_with_a_destination_is_not_a_refusal():
    slot = _slot("poné la de Queen en Spotify", ["poné la de Queen en Spotify"], "¿La pongo?")
    assert dialogue_slot.dependency("no, en YouTube", slot) == "answer"


def _talk(text):
    from baxy_mind import __main__ as mind

    return mind._talk_act_turn_decision(text, None, None)


@pytest.mark.parametrize(
    "text",
    [
        "me encanta cocinar los domingos",
        "ayer fui al cine con mi hermana",
        "uf, qué semana pesada tuve",
        "la verdad a veces creo que la tecnología nos cansa",
        "otra vez fallaste, qué bronca",
        "no lo hiciste, no me mientas",
        "jeje qué gracioso eso",
        "i feel tired today",
    ],
)
def test_talk_that_asks_nothing_is_answered_as_talk(text):
    decision = _talk(text)
    assert decision is not None and decision["mode"] == "conversation" and decision["conversation_kind"] == "social"


@pytest.mark.parametrize(
    "text",
    [
        "me aburro, poné algo de rock",  # an order after the talk
        "odio esta canción, saltala",  # an order
        "yo quiero escuchar jazz",  # a desire is a request
        "te dije que cierres Chrome",  # a reproach that repeats a request
        "estoy con el brillo muy bajo",  # a statement about the PC may be a request
        "otra vez fallaste, buscá bien esta vez",  # a lookup
        "¿me extrañaste?",  # a question is left to the ordinary reading
    ],
)
def test_talk_with_an_order_a_request_or_the_pc_is_left_to_the_reading(text):
    assert _talk(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [("devolvele el volumen", None), ("mandale un audio a Pedro", None), ("prendelo", "reference"), ("devolvele", "reference")],
)
def test_a_dative_clitic_with_its_object_said_is_not_a_reference(text, expected):
    slot = _slot(None, ["silenciá los parlantes"], "Listo.")
    assert dialogue_slot.dependency(text, slot) == expected
