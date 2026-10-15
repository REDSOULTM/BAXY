"""Estabilización, encargo imp-steam: los imprescindibles de Steam del dueño (lanzar un juego instalado; instalar y
desinstalar con confirmación) por un mecanismo general en datos.

El título se traduce a su número por los manifiestos instalados y, si no está instalado, por la búsqueda pública de la
tienda que declara data/app_places.v1.json («titles»; antes, 13 títulos fijos en SteamLocalAdapter.KnownTitleAppIds).
Instalar y desinstalar abren la dirección del dato («acts») y confirman el diálogo propio de Steam con el clic de la
misión (sus nombres, «confirm»), y el manifiesto lo prueba (antes la desinstalación tecleaba app_uninstall en la consola).
Los casos en vivo (scripts/cu_live/cases/imp-steam-*) sólo instalan o desinstalan Super Meat Boy (40800), el juego que el
dueño dejó para estas pruebas, y el arnés lo deja como lo encontró.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from baxy_mind.compose_situation import _CAUSE_FACT
from baxy_mind.semantic import app_places, arguments, patterns
from baxy_mind.semantic.catalog import build_game_catalog_index

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "src" / "baxy_mind" / "data" / "app_places.v1.json").read_text(encoding="utf-8"))
LIVE = ROOT / "scripts" / "cu_live"
OPERATIONS = tuple(sorted(set(re.findall(
    r'Descriptor\(\s*"([a-z][a-z0-9._]+)"',
    (ROOT / "src" / "Baxy.Kernel" / "Operations" / "ProductCatalog.cs").read_text(encoding="utf-8"),
))))
NAMES = ("Steam", "Spotify", "Paint", "Bloc de notas", "Configuración", "Discord")
INSTALLED = (("steam", "268910", "Cuphead"), ("steam", "252950", "Rocket League"))
WITH_SMB = INSTALLED + (("steam", "40800", "Super Meat Boy"),)


# ------------------------------------------------------------------------------------------------ el dato


def test_the_acts_and_the_title_search_are_steams_data_and_no_place_of_the_mind() -> None:
    steam = DATA["applications"]["Steam"]
    assert steam["acts"]["install"] == {"address": "steam://install/{game}", "confirm": ["Instalar", "Install"]}
    assert steam["acts"]["uninstall"] == {"address": "steam://uninstall/{game}", "confirm": ["Desinstalar", "Uninstall"]}
    assert steam["acts"]["launch"] == {"address": "steam://rungameid/{game}", "confirm": ["Jugar", "Play"]}
    assert steam["titles"]["address"].startswith("https://") and steam["titles"]["address"].count("{title}") == 1
    # An act is never a place the mind opens by app.open: only its typed operation starts it.
    assert not set(steam["acts"]) & set(steam["places"])
    for goal in ("ir a install", "ir a instalar super meat boy", "ir a uninstall", "ir a launch"):
        assert app_places.place_of("Steam", goal, INSTALLED) is None, goal


def test_the_new_dialog_causes_are_facts_in_data() -> None:
    for code in ("steam_install_dialog_not_confirmed", "steam_uninstall_dialog_not_confirmed"):
        assert "dialog was left open" in _CAUSE_FACT[code]


# ------------------------------------------------------------------------------- la mente: la ruta tipada


@pytest.mark.parametrize(("said", "games", "operation", "expected"), [
    ("instalá Super Meat Boy en Steam", INSTALLED, "game.install.named", {"title": "Super Meat Boy", "store": "steam"}),
    ("install Super Meat Boy on Steam", INSTALLED, "game.install.named", {"title": "Super Meat Boy", "store": "steam"}),
    ("desinstalá Super Meat Boy en Steam", WITH_SMB, "game.uninstall.named", {"title": "Super Meat Boy", "store": "steam"}),
    ("uninstall Super Meat Boy from Steam", WITH_SMB, "game.uninstall.named", {"title": "Super Meat Boy", "store": "steam"}),
    ("lanzá Cuphead", INSTALLED, "game.launch", {"appId": "268910"}),
])
def test_the_owners_steam_orders_reach_their_typed_operation(
    said: str, games: tuple, operation: str, expected: dict,
) -> None:
    intent = patterns.resolve_explicit_effects(said, OPERATIONS, NAMES, games)
    assert intent is not None and intent.operations == (operation,)
    assert arguments._explicit_arguments_from_evidence(operation, said, NAMES, build_game_catalog_index(games)) == expected


def test_a_game_page_is_still_a_place_and_never_an_install() -> None:
    # Contracase (encargo C): «la página de» un juego instalado se abre por su dirección, sin instalar ni lanzar.
    intent = patterns.resolve_explicit_effects("abrí la página de Rocket League en Steam", OPERATIONS, NAMES, INSTALLED)
    assert intent is not None and not {"game.install.named", "game.launch"} & set(intent.operations)


# ------------------------------------------------------------------------------------------------ el arnés


def test_the_steam_game_state_is_ascii_and_installs_only_the_owners_test_game() -> None:
    raw = (LIVE / "estado" / "steam_juego.ps1").read_bytes()
    assert raw.isascii() and b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("ascii")
    assert "$PruebaInstalable='40800'" in text
    # Installing or uninstalling any other game is refused before anything is opened.
    assert "if($soloLectura -notcontains $accion -and $appid -ne $PruebaInstalable)" in text
    # Steam is never started by the harness.
    assert "steam_no_abierto" in text and "start-process steam" not in text.lower()


def test_the_imp_steam_cases_start_from_their_states_and_end_as_they_found_super_meat_boy() -> None:
    casos = json.loads((LIVE / "estado" / "casos.json").read_text(encoding="utf-8"))
    pre = casos["precondicion"]
    for case, read, inverted in (
        ("imp-steam-instalar", "leer_instalado", "desinstalado"),
        ("imp-steam-instalar-normal", "leer_instalado", "desinstalado"),
        ("imp-steam-desinstalar", "leer_desinstalado", "instalado"),
    ):
        assert (LIVE / "cases" / f"{case}.turns").is_file(), case
        assert pre[case]["lee"] == f"steam_juego:40800:{read}"
        assert pre[case]["invierte"] == f"steam_juego:40800:{inverted}"
        assert pre[case]["devuelve"] == "steam_juego:40800:devolver"
    assert pre["imp-steam-lanzar"]["devuelve"] == "steam_juego:268910:cerrado"
    assert (LIVE / "cases" / "imp-steam-lanzar.turns").read_text(encoding="utf-8").strip() == "lanzá Cuphead"
    normal = (LIVE / "cases" / "MODO_NORMAL.txt").read_text(encoding="utf-8").split()
    assert "imp-steam-instalar-normal" in normal
    assert (LIVE / "cases" / "imp-steam-instalar-normal.turns").read_text(encoding="utf-8").splitlines() == [
        "instalá Super Meat Boy en Steam", "no",
    ]
