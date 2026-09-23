"""Fase 3.5: request forms layer C showed that the pattern did not read.

A vocative with another assistant's name, the machine as the object of a silence verb, a bare
«captura» as the whole request and a place said before the order. Phrases are not the corpus rows.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind.effect_intent import EffectIntent
from baxy_mind.semantic.audio import _audio_mute_domain
from baxy_mind.semantic.grammar import _fold, _strip_request_envelope


@pytest.mark.parametrize(
    ("text", "stripped"),
    [
        ("Gemma, subí el brillo", "subi el brillo"),
        ("hey carter abrí la calculadora", "abri la calculadora"),
        ("Alexa: poné algo de jazz", "pone algo de jazz"),
    ],
)
def test_another_assistants_name_as_a_vocative_is_only_an_address(text, stripped):
    assert _strip_request_envelope(_fold(text)).strip(" .") == stripped


def test_an_assistant_name_inside_the_request_stays():
    assert "gemma" in _strip_request_envelope(_fold("escribí gemma en el bloc de notas"))


@pytest.mark.parametrize("text", ["silenciá la notebook", "mute this laptop", "desmuteá el equipo porfa", "unmute my computer"])
def test_the_machine_as_the_object_of_a_silence_verb_is_global_audio(text):
    assert _audio_mute_domain(_fold(text))


@pytest.mark.parametrize("text", ["apagá la notebook", "silenciá la notebook de mi primo"])
def test_shutdown_and_someone_elses_machine_are_not_global_silence(text):
    assert not _audio_mute_domain(_fold(text))


def _resolve_place(text: str) -> EffectIntent | None:
    folded = _fold(text)
    if folded.startswith(("pone ", "pon ", "play ")) and folded.endswith(("youtube", "spotify")):
        return EffectIntent(("stub.play",), (text,))
    return None


@pytest.mark.parametrize(
    ("text", "reordered"),
    [
        ("en Spotify poné algo de rock", "poné algo de rock en Spotify"),
        ("on YouTube play the new Coldplay single", "play the new Coldplay single on YouTube"),
    ],
)
def test_a_place_said_before_the_order_is_read_after_it(text, reordered):
    found = mind._fronted_place_request(text, _resolve_place)
    assert found is not None and found.evidence == (reordered,)


@pytest.mark.parametrize("text", ["en Spotify hay mucha música", "en mi casa pon la mesa"])
def test_a_place_before_talk_or_before_an_unreadable_order_stays_as_it_was(text):
    assert mind._fronted_place_request(text, _resolve_place) is None


@pytest.mark.parametrize("text", ["presioná enter en Slack", "pulsá la tecla intro en Word", "oprimí enter"])
def test_a_key_is_never_a_visible_control_to_click(text):
    from baxy_mind.semantic.ui import _visible_click_label

    assert _visible_click_label(text) is None


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("decime la hora exacta porfa", "system.time"),
        ("quisiera saber quién es Rosalía", "web.search"),
        ("¿sabés qué es Hollow Knight?", "web.search"),
        ("qué programa está en primer plano", "window.active"),
    ],
)
def test_plain_reads_are_read_not_confirmed(text, operation):
    from baxy_mind.semantic.network import _direct_current_time_request
    from baxy_mind.semantic.web import _entity_lookup_query

    if operation == "system.time":
        assert _direct_current_time_request(_fold(text).strip(" ."))
    elif operation == "web.search":
        assert _entity_lookup_query(text) is not None
    else:
        from baxy_mind.effect_intent import resolve_explicit_effects

        found = resolve_explicit_effects(text, ("window.active",))
        assert found is not None and found.operations == ("window.active",)


def test_the_pronoun_after_a_question_about_a_public_work_is_that_work():
    from baxy_mind.semantic import dialogue

    assert dialogue.asked_about("¿La última temporada de Dark vale la pena?") == "última temporada de Dark"
    assert dialogue.substituted_reference("bueno, averigualo", "¿Dune 2 vale la pena?") == "averigua Dune 2"
    assert dialogue.asked_about("abrí Spotify") is None


def _resolve_play(order: str) -> EffectIntent | None:
    folded = _fold(order)
    return EffectIntent(("stub.play",), (order,)) if folded.startswith(("pon ", "play ")) and len(folded.split()) > 2 else None


@pytest.mark.parametrize(
    ("text", "order"),
    [
        ("quiero una canción de Bad Bunny", "pon una canción de Bad Bunny"),
        ("tengo ganas de escuchar a Los Redondos", "pon Los Redondos"),
        ("I would like to listen to some jazz", "play some jazz"),
    ],
)
def test_a_desire_to_listen_is_the_order_to_play(text, order):
    found = mind._desired_media_request(text, _resolve_play)
    assert found is not None and found.evidence == (order,)


@pytest.mark.parametrize("text", ["quiero que me escuches", "quiero escuchar tu opinión sobre esto"])
def test_a_desire_that_is_not_media_stays_as_it_was(text):
    found = mind._desired_media_request(text, lambda order: None)
    assert found is None


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("dejá el volumen al mínimo", "audio.volume"),
        ("bajá el volumen 15 puntos", "audio.volume.adjust"),
        ("subí el volumen 5 puntos porfa", "audio.volume.adjust"),
    ],
)
def test_volume_levels_and_voseo_amounts(text, operation):
    from baxy_mind.effect_intent import resolve_explicit_effects

    found = resolve_explicit_effects(text, ("audio.volume", "audio.volume.adjust"))
    assert found is not None and found.operations == (operation,)


@pytest.mark.parametrize(("text", "state"), [("devolveme el audio", False), ("recuperá el sonido", False), ("silenciá todo", True)])
def test_restoring_the_sound_is_unmute_in_the_arguments_too(text, state):
    assert mind._explicit_arguments_from_evidence("audio.mute", text) == {"state": state}
