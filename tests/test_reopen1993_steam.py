"""Auditoría semántica 2026-09-20 (REOPEN1957/1993, grupo S; D1/D11): la
encuesta pide descargar, instalar y desinstalar juegos en Steam y Epic, no
leer la biblioteca. Las 20 filas de descarga/instalación (H0049, H0118,
H0272, H0382, H0390, H0434, H0482, H0659, H0671, H0680, H0295, H0345, H0387,
H0396, H0643, H0721, H0456, H0571, H0578) van a game.install.named con la
tienda nombrada; las de desinstalar (H0039, H0612, H0620) a
game.uninstall.named; lanzar lo no instalado conserva la lectura (INSTALL1633)."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({
    "game.entitlement.named", "game.install.named", "game.uninstall.named", "game.launch",
    "app.open", "app.installed", "web.search", "package.install.prepare", "package.install.commit", "package.uninstall",
})
APPS = ("Spotify", "Steam", "Epic Games Launcher")
GAMES = (("steam", "2767030", "Marvel Rivals"), ("steam", "620", "Portal 2"))
SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "store": {"type": ["string", "null"]}}, "required": ["title"], "additionalProperties": False}


@pytest.mark.parametrize(
    ("text", "title", "store"),
    [
        ("Descarga Worms Rumble en seam", "Worms Rumble", "steam"),
        ("Descarga doom eternal de steam", "doom eternal", "steam"),
        ("instala batman arkham knights en steam", "batman arkham knights", "steam"),
        ("Instala Batman Arkham Knight en Teams", "Batman Arkham Knight", "steam"),
        ("Necesito que instalaes worms rumble en steam", "worms rumble", "steam"),
        ("Descarga diin  eternal de steam", "diin  eternal", "steam"),
        ("Descarga Fall guys en epic games", "Fall guys", "epic"),
        ("Instala Doom Eternal en Steam. El AppID es 782330. Usa steam://install/782330 para abrir el dialogo,", "Doom Eternal", "steam"),
    ],
)
def test_downloads_and_installs_are_the_real_install(text: str, title: str, store: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("game.install.named",)
    assert effect_intent.steam_library_verb(text) == "install"
    grounded = mind._ground_explicit_arguments("game.install.named", text, SCHEMA, APPS, effect_intent.build_game_catalog_index(GAMES))
    assert grounded is not None and grounded["store"] == store
    assert effect_intent._fold(grounded["title"]).split() == effect_intent._fold(title).split()
    assert effect_intent.operation_domain_is_grounded(text, "game.install.named", APPS) is True


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("Desinstala Worms Rumble en Steam", "Worms Rumble"),
        ("Desinstala Portal 2", "Portal 2"),
        ("desinstalá Marvel Rivals", "Marvel Rivals"),
    ],
)
def test_uninstalls_are_the_real_uninstall(text: str, title: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("game.uninstall.named",)
    grounded = mind._ground_explicit_arguments("game.uninstall.named", text, SCHEMA, APPS, effect_intent.build_game_catalog_index(GAMES))
    assert grounded == {"title": title, "store": "steam"}


def test_a_bare_uninstall_of_a_name_that_is_not_installed_stays_the_presence_read() -> None:
    intent = effect_intent.resolve_explicit_effects("Desinstala Worms Rumble", AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("app.installed",)


@pytest.mark.parametrize("text", ["lanzá Mortal Kombat en Steam", "lanzá Mortal Kombat"])
def test_launching_what_is_not_installed_keeps_the_library_read(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("game.entitlement.named",)
    assert effect_intent.steam_library_verb(text) == "launch"


def test_without_the_effects_the_library_read_remains() -> None:
    intent = effect_intent.resolve_explicit_effects("Descarga doom eternal de steam", {"game.entitlement.named", "app.open"}, APPS, GAMES)
    assert intent is not None and intent.operations == ("game.entitlement.named",)


@pytest.mark.parametrize(
    ("text", "payload", "defect"),
    [
        ("Empezó la descarga de Fall Guys en Steam.", {"operation": "game.install.named", "seen": {"name": "Fall Guys", "state": "downloading"}}, ""),
        ("Fall Guys ya está instalado.", {"operation": "game.install.named", "seen": {"name": "Fall Guys", "state": "downloading"}}, "extra_claim"),
        ("Listo.", {"operation": "game.install.named", "seen": {"name": "Fall Guys", "state": "downloading"}}, "missing_state"),
        ("Fall Guys ya estaba instalado; no descargué nada.", {"operation": "game.install.named", "seen": {"name": "Fall Guys", "state": "already_installed"}}, ""),
        ("Desinstalé Portal 2; ya no figura como instalado.", {"operation": "game.uninstall.named", "seen": {"name": "Portal 2", "state": "manifest_removed"}}, ""),
        ("Portal 2 sigue ahí.", {"operation": "game.uninstall.named", "seen": {"name": "Portal 2", "state": "manifest_removed"}}, "missing_state"),
    ],
)
def test_the_reply_matches_the_manifest_state(text: str, payload: dict, defect: str) -> None:
    assert llm._game_library_fact_defect(text, payload) == defect


def test_the_absences_have_their_own_cause_facts() -> None:
    for code in ("steam_entitlement_not_verified", "steam_game_not_installed", "steam_uninstall_not_verified", "epic_entitlement_not_verified", "epic_install_not_verified"):
        assert code in llm._CAUSE_FACT
