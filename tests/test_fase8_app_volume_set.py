"""Fase 8 (D7/D18) «poné el volumen de Spotify al 40»: an absolute level for one
application's own volume is audio.app.volume.set with the catalog name and the
level; the relative readers keep «subí/bajá … en 20», the system readers keep
every request that names no application, and «al máximo»/«a la mitad» are
levels too."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent

APPS = ("Spotify", "Discord", "Steam", "Google Chrome")
AVAILABLE = frozenset({"audio.app.volume.set", "audio.app.volume.adjust", "audio.volume", "audio.volume.adjust", "audio.mute", "app.open"})


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("poné el volumen de Spotify al 40", 40),
        ("pon el volumen de spotify en 40%", 40),
        ("poné spotify al 40", 40),
        ("dejá el volumen de Spotify a 25", 25),
        ("fijá el volumen de Discord al 70 por favor", 70),
        ("poné el volumen de spotify al máximo", 100),
        ("dejá spotify a la mitad", 50),
        ("set spotify volume to 40", 40),
        ("set the volume of Spotify to 60%", 60),
        ("put Discord volume to 30", 30),
    ],
)
def test_an_absolute_application_level_is_set(text: str, level: int) -> None:
    assert effect_intent.app_volume_set_request(text, APPS) == (("Discord" if "discord" in text.lower() else "Spotify"), level)
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == ("audio.app.volume.set",)
    catalog = effect_intent.build_game_catalog_index(())
    expected_app = "Discord" if "discord" in text.lower() else "Spotify"
    assert mind._explicit_arguments_from_evidence("audio.app.volume.set", text, APPS, catalog) == {"app": expected_app, "level": level}


@pytest.mark.parametrize(
    "text",
    [
        "subí el volumen de spotify en 20",
        "bajá el volumen de Spotify",
        "poné el volumen al 40",
        "poné el volumen del sistema al 40",
        "set the volume to 40",
        "poné el brillo al 40",
        "poné spotify al 140",
        "no pongas el volumen de spotify al 40",
        "poné el volumen de Photoshop al 40",
    ],
)
def test_relative_system_or_unknown_targets_are_not_absolute_application_levels(text: str) -> None:
    assert effect_intent.app_volume_set_request(text, APPS) is None
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is None or "audio.app.volume.set" not in intent.operations
