"""Reparaciones pedidas por el corredor (2026-09-21) antes de medir winget, Steam,
energía y comandos: «quitá 7-Zip» es una desinstalación; «Plants vs. Zombies»
nombra el juego con su sufijo de edición; «shut down the computer», «turn off
the pc» y «reiniciá» a secas son la transición de energía con su acción
fundamentada; un comando sin carpeta corre en la carpeta propia del producto y
uno «en el escritorio» lleva esa carpeta conocida."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent

APPS = ("Spotify", "Discord", "Steam", "7-Zip")
GAMES = (("steam", "3590", "Plants vs. Zombies: Game of the Year"), ("steam", "461040", "PICO PARK:Classic Edition"))
AVAILABLE = frozenset({"package.install.prepare", "package.install.commit", "package.uninstall", "system.power", "game.install.named", "game.uninstall.named", "game.entitlement.named", "app.open", "shell.command.run", "bluetooth.radio.set"})
POWER_SCHEMA = {"type": "object", "properties": {"action": {"type": "string", "enum": ["lock", "restart", "shutdown", "signout", "sleep"]}}, "required": ["action"], "additionalProperties": False}
SHELL_SCHEMA = {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": ["string", "null"]}}, "required": ["command"], "additionalProperties": False}


@pytest.mark.parametrize("text", ["quitá 7-Zip", "desinstalá 7-Zip", "eliminá 7-Zip"])
def test_removal_verbs_uninstall_a_catalog_program(text: str) -> None:
    software = effect_intent.software_package_request(text, APPS)
    assert software is not None and software[0] == "uninstall" and software[2] is True
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("package.uninstall",)


@pytest.mark.parametrize(("text", "title"), [("desinstalá Plants vs. Zombies", "Plants vs. Zombies: Game of the Year"), ("desinstalá PICO PARK", "PICO PARK:Classic Edition")])
def test_an_installed_game_named_without_its_edition_is_uninstalled_from_steam(text: str, title: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("game.uninstall.named",)
    catalog = effect_intent.build_game_catalog_index(GAMES)
    assert mind._explicit_arguments_from_evidence("game.uninstall.named", text, APPS, catalog) == {"title": title, "store": "steam"}


@pytest.mark.parametrize(
    ("text", "action"),
    [("shut down the computer", "shutdown"), ("turn off the pc", "shutdown"), ("apagá la computadora", "shutdown"), ("reiniciá", "restart"), ("reiniciá la PC", "restart"), ("reboot the computer", "restart")],
)
def test_power_orders_ground_their_action(text: str, action: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is not None and intent.operations == ("system.power",)
    assert mind._ground_explicit_arguments("system.power", text, POWER_SCHEMA) == {"action": action}


@pytest.mark.parametrize("text", ["turn off the lights", "apagá", "reiniciá el router", "shut down spotify"])
def test_what_is_not_the_pc_is_not_a_power_order(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, GAMES)
    assert intent is None or "system.power" not in intent.operations


@pytest.mark.parametrize(
    ("text", "arguments"),
    [
        ("ejecuta pytest", {"command": "pytest", "cwd": None}),
        ("ejecutá dir en el escritorio", {"command": "dir", "cwd": "desktop"}),
        ("corré git status en documentos/proyecto", {"command": "git status", "cwd": "documents/proyecto"}),
        ("run ls in downloads", {"command": "ls", "cwd": "downloads"}),
    ],
)
def test_a_command_names_its_known_folder_or_none(text: str, arguments: dict) -> None:
    assert mind._ground_explicit_arguments("shell.command.run", text, SHELL_SCHEMA) == arguments
