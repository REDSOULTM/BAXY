"""REOPEN1993 (D24, regla del dueño «lo mal dicho lo arregla BAXY»): lanzar un
juego instalado nombrado sin su sufijo de edición («PICO PARK» por «PICO
PARK:Classic Edition»), con «ve a» o «start» como verbo, y con «jugá» en voseo,
es game.launch de ese único título; con la biblioteca sin el título (H0083
«lanzá Mortal Kombat en Steam») queda la lectura honesta de la biblioteca."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent

APPS = ("Spotify", "Discord", "Steam", "7-Zip")
GAMES = (
    ("steam", "3590", "Plants vs. Zombies: Game of the Year"),
    ("steam", "461040", "PICO PARK:Classic Edition"),
    ("steam", "2767030", "Marvel Rivals"),
)
AVAILABLE = frozenset({"game.launch", "game.entitlement.named", "game.install.named", "game.uninstall.named", "app.open", "web.search", "web.navigate"})


@pytest.mark.parametrize(
    ("text", "app_id"),
    [
        ("abrí PICO PARK", "461040"),
        ("lanzá PICO PARK", "461040"),
        ("jugá PICO PARK", "461040"),
        ("Ve a Mad de Rivals.", "2767030"),
        ("ve a Marvel Rivals", "2767030"),
        ("start Marvel Rivals", "2767030"),
        ("abrí Plants vs. Zombies", "3590"),
    ],
)
def test_an_installed_title_named_without_its_edition_or_by_go_to_is_launched(text: str, app_id: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("game.launch",)
    catalog = effect_intent.build_game_catalog_index(GAMES)
    assert mind._explicit_arguments_from_evidence("game.launch", text, APPS, catalog) == {"appId": app_id}


@pytest.mark.parametrize("text", ["lanzá Mortal Kombat en Steam", "lanzá Mortal Kombat"])
def test_a_title_absent_from_the_library_is_read_not_launched(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("game.entitlement.named",)


@pytest.mark.parametrize("text", ["ve a la configuración", "ve a youtube", "entrá a Discord", "iniciá sesión"])
def test_go_to_orders_that_name_no_installed_game_are_not_launches(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is None or "game.launch" not in intent.operations


@pytest.mark.parametrize(
    "text",
    [
        "Instala Plants vs. Zombies en Steam. El AppID es 3590. Usa steam://install/3590 para abrir el dialogo,",
        "Descarga Plants vs. Zombies en Steam. IMPORTANTE: primero busca el AppID via https://store.steampowered.co",
    ],
)
def test_a_title_with_its_own_dot_followed_by_install_instructions_is_installed(text: str) -> None:
    # D13: H0396/H0456 measured with Plants vs. Zombies; «vs.» is not the sentence boundary.
    assert effect_intent.steam_library_title(text) == "Plants vs. Zombies"
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE | {"game.install.named"}, APPS, GAMES)
    assert intent is not None and intent.operations == ("game.install.named",)
