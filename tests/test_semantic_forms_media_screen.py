"""Fase 3.5: media and screen forms layer C showed as false limits.

Pausing or resuming a video, film or series controls the same media session as music; what a
message on the screen says is read from the screen; darkening or lightening the screen is its
brightness (without an amount it asks how much, the owner's rule); a desire to listen is music.
Phrases are not the corpus rows.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.effect_intent import (
    EffectIntent,
    resolve_explicit_clarification_intent,
    resolve_explicit_effects,
)
from baxy_mind.semantic.display import screen_light_as_brightness
from baxy_mind.semantic.grammar import _fold


@pytest.mark.parametrize("text", ["pausá la serie", "reanudá el episodio", "pause the movie"])
def test_a_video_session_is_paused_and_resumed_like_music(text):
    found = resolve_explicit_effects(text, ("media.control",))
    assert found is not None and found.operations == ("media.control",)


def test_new_video_content_and_recording_are_not_media_control():
    assert resolve_explicit_effects("pausá la grabación de la reunión", ("media.control",)) is None


@pytest.mark.parametrize("text", ["qué dice el aviso en la pantalla", "what does the error on my screen say"])
def test_what_a_message_on_the_screen_says_is_read_from_the_screen(text):
    found = resolve_explicit_effects(text, ("capture.screenshot", "ocr.read"))
    assert found is not None and found.operations == ("capture.screenshot", "ocr.read")


def test_a_question_about_a_book_is_not_the_screen():
    assert resolve_explicit_effects("qué dice el Quijote al principio", ("capture.screenshot", "ocr.read")) is None


@pytest.mark.parametrize(
    ("text", "normalized"),
    [
        ("atenua la pantalla un poco", "baja el brillo de la pantalla un poco"),
        ("ilumina el monitor", "sube el brillo de la pantalla"),
        ("aclarame esta duda", "aclarame esta duda"),
    ],
)
def test_darkening_or_lightening_the_screen_is_its_brightness(text, normalized):
    assert screen_light_as_brightness(_fold(text)) == normalized


def test_darkening_the_screen_without_an_amount_asks_how_much():
    asked = resolve_explicit_clarification_intent("oscurecé el monitor", ("system.settings.adjust",))
    assert asked is not None and asked.missing_fields == ("amount",)


def _resolve(order: str) -> EffectIntent | None:
    return EffectIntent(("stub.play",), (order,)) if _fold(order).startswith("pon ") else None


@pytest.mark.parametrize(
    ("text", "order"),
    [("me gustaría escuchar cumbia", "pon música de cumbia"), ("quiero escuchar algo tranqui", "pon algo tranqui")],
)
def test_listening_to_a_bare_name_or_genre_is_its_music(text, order):
    found = mind._desired_media_request(text, _resolve)
    assert found is not None and found.evidence == (order,)


@pytest.mark.parametrize(
    ("reply", "claims"),
    [
        ("La caché del navegador guarda las páginas que ya viste, así el programa abre más rápido.", False),
        ("Un comité decide qué archivos se guardan en el programa.", False),
        ("Vacié la caché del programa.", True),
    ],
)
def test_nouns_ending_in_a_stressed_vowel_are_not_a_first_person_claim(reply, claims):
    from baxy_mind import llm

    assert llm.visible_reply_claims_a_completed_effect(reply) is claims
