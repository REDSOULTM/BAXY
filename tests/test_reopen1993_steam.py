"""Auditoría semántica 2026-09-20 (REOPEN1957/1993, grupo S; D1/D11): la
encuesta pide descargar, instalar y desinstalar juegos en Steam y Epic, no
leer la biblioteca. Las 20 filas de descarga/instalación (H0049, H0118,
H0272, H0382, H0390, H0434, H0482, H0659, H0671, H0680, H0295, H0345, H0387,
H0396, H0643, H0721, H0456, H0571, H0578) van a game.install.named con la
tienda nombrada; las de desinstalar (H0039, H0612, H0620) a
game.uninstall.named; lanzar lo no instalado conserva la lectura (INSTALL1633)."""

from __future__ import annotations

import pytest

from baxy_mind import effect_intent
from baxy_mind import compose_situation
from baxy_mind import deterministic_finals
from baxy_mind import operation_floor
from baxy_mind import argument_grounding

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
    grounded = argument_grounding._ground_explicit_arguments("game.install.named", text, SCHEMA, APPS, effect_intent.build_game_catalog_index(GAMES))
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
    grounded = argument_grounding._ground_explicit_arguments("game.uninstall.named", text, SCHEMA, APPS, effect_intent.build_game_catalog_index(GAMES))
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


def _installed(operation: str, observed: dict) -> dict:
    return {"kind": "operation", "operation": operation, "polarity": "success", "verified": True, "succeeded": True,
            "observed": {"version": 1, **observed}}


# Encargo IMP2 (imp1 imp-steam-instalar, 2026-10-12): over a verified install whose manifest said «queued» the writer
# drafted «Super Meat Boy ya está instalado en Steam, pero no se ha descargado…» — the receipt's «state» never reached
# its payload, so the instruction and the veto that read it (llm_compose, payload_fact_checks._game_library_fact_defect)
# never ran. The launcher's manifest state is said by the floor before any draft (operation_floor.v1.json «told» by
# «state»): a download started is never «ya estaba instalado», and only a state already there says so.
@pytest.mark.parametrize(
    ("operation", "observed", "said"),
    [
        ("game.install.named", {"jobId": "steam_job_d0f718abb62c271e6665a051", "appId": "40800", "name": "Super Meat Boy",
                                "state": "queued", "bytesDownloaded": 0, "bytesTotal": 0,
                                "authority": "steam_manifest_transition"},
         "Listo, empecé a instalar el juego «Super Meat Boy»."),
        ("game.install.named", {"appId": "1", "name": "Fall Guys", "state": "downloading", "bytesDownloaded": 10},
         "Listo, empecé a instalar el juego «Fall Guys»."),
        ("game.install.named", {"appId": "1", "name": "Fall Guys", "state": "installed"}, "Listo, instalé el juego «Fall Guys»."),
        ("game.install.named", {"appId": "1", "name": "Fall Guys", "state": "already_installed",
                                "authority": "steam_local_appmanifest"},
         "El juego «Fall Guys» ya estaba instalado; no descargué nada."),
        ("game.uninstall.named", {"appId": "620", "name": "Portal 2", "state": "manifest_removed"},
         "Listo, desinstalé el juego «Portal 2»."),
    ],
)
def test_the_manifest_state_is_said_by_the_floor_first(operation: str, observed: dict, said: str) -> None:
    situation = _installed(operation, observed)
    assert operation_floor.tells_first(situation) is True
    assert deterministic_finals._floor_first_final(situation, {}, "instalá el juego en Steam", "es") == said


def test_contracase_an_install_not_verified_keeps_its_own_floor() -> None:
    situation = {"kind": "operation", "operation": "game.install.named", "polarity": "failure", "verified": False,
                 "succeeded": False, "error": "steam_install_transition_not_verified", "effectUncertain": True,
                 "observed": {"appId": "40800", "name": "Super Meat Boy"}}
    final = operation_floor.floor_final(situation, False)
    assert "ya estaba" not in final and "empecé a instalar" not in final


def test_the_absences_have_their_own_cause_facts() -> None:
    for code in ("steam_entitlement_not_verified", "steam_game_not_installed", "steam_uninstall_not_verified", "epic_entitlement_not_verified", "epic_install_not_verified"):
        assert code in compose_situation._CAUSE_FACT
