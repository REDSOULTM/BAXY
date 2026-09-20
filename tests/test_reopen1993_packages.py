"""Auditoría semántica 2026-09-20 (REOPEN1993, grupo G): «instala Photoshop»
(H0167, H0217, H0457, H0583), «instala Spotify» (H0651), «desinstalá Discord»
(H0089) y «desinstalá Spotify» (H0574) son pedidos al gestor de paquetes de
Windows, no lecturas de la biblioteca de Steam."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent, llm

AVAILABLE = frozenset({
    "package.install.prepare", "package.install.commit", "package.uninstall", "app.installed",
    "game.entitlement.named", "app.open", "web.search", "game.install.named",
    "software.python.package.status",
})
APPS = ("Spotify", "Discord", "Steam", "Google Chrome")


@pytest.mark.parametrize(
    ("text", "operations", "reading"),
    [
        ("instala Photoshop", ("package.install.prepare", "package.install.commit"), ("install", "Photoshop", False)),
        ("instalá Photoshop", ("package.install.prepare", "package.install.commit"), ("install", "Photoshop", False)),
        ("Instala photoshop´", ("package.install.prepare", "package.install.commit"), ("install", "photoshop", False)),
        ("instala 7zip", ("package.install.prepare", "package.install.commit"), ("install", "7zip", False)),
        # INSTALL1625: installing what the Start catalog already holds is its presence.
        ("instala Spotify", ("app.installed",), ("install", "Spotify", True)),
        ("desinstalá Discord", ("package.uninstall",), ("uninstall", "Discord", True)),
        ("desinstalá Spotify", ("package.uninstall",), ("uninstall", "Spotify", True)),
        # Removing what is not installed stays the honest presence read.
        ("desinstalá Photoshop", ("app.installed",), ("uninstall", "Photoshop", False)),
    ],
)
def test_software_requests_go_to_the_package_manager(text: str, operations: tuple[str, ...], reading: tuple) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == operations
    assert effect_intent.software_package_request(text, APPS) == reading


@pytest.mark.parametrize(
    ("text", "operations"),
    [
        ("instala requests con pip", ("software.python.package.status",)),
        ("Descarga Worms Rumble en Steam", ("game.entitlement.named",)),
    ],
)
def test_games_and_pip_keep_their_own_readers(text: str, operations: tuple[str, ...]) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPS, ())
    assert intent is not None and intent.operations == operations
    assert effect_intent.software_package_request(text, APPS) is None


@pytest.mark.parametrize("text", ["no instales nada", "instala todo", "desinstalá algo"])
def test_negations_and_pronouns_abstain(text: str) -> None:
    assert effect_intent.software_package_request(text, APPS) is None


def test_the_package_name_is_grounded_as_written_or_as_the_catalog_names_it() -> None:
    prepare = {"type": "object", "properties": {"packageId": {"type": "string"}, "version": {"type": ["string", "null"]}}, "required": ["packageId"], "additionalProperties": False}
    uninstall = {"type": "object", "properties": {"packageId": {"type": "string"}}, "required": ["packageId"], "additionalProperties": False}
    assert mind._ground_explicit_arguments("package.install.prepare", "instala Photoshop", prepare, APPS) == {"packageId": "Photoshop", "version": None}
    assert mind._ground_explicit_arguments("package.uninstall", "desinstalá Discord", uninstall, APPS) == {"packageId": "Discord"}
    assert mind._ground_explicit_arguments("package.uninstall", "instala Photoshop", uninstall, APPS) is None


def test_domain_gates_admit_the_new_readings() -> None:
    assert effect_intent.operation_domain_is_grounded("desinstalá Discord", "package.uninstall", APPS) is True
    assert effect_intent.operation_domain_is_grounded("instala Photoshop", "package.install.prepare", APPS) is True
    assert effect_intent.operation_domain_is_grounded("instala Photoshop", "package.uninstall", APPS) is False


@pytest.mark.parametrize(
    ("text", "payload", "defect"),
    [
        ("Desinstalé Discord; ya no está entre los paquetes instalados.", {"operation": "package.uninstall", "seen": {"name": "Discord", "removed": True, "uninstalling": False}}, ""),
        ("Ya no está entre los paquetes instalados.", {"operation": "package.uninstall", "seen": {"name": "Discord", "removed": True, "uninstalling": False}}, "missing_state"),
        ("Desinstalé Discord.", {"operation": "package.uninstall", "seen": {"name": "Discord", "removed": False, "uninstalling": True}}, "extra_claim"),
        ("El desinstalador de Discord sigue corriendo.", {"operation": "package.uninstall", "seen": {"name": "Discord", "removed": False, "uninstalling": True}}, ""),
        ("Instalé VLC media player; ya figura entre los instalados.", {"operation": "package.install.commit", "seen": {"name": "VLC media player", "installed": True, "installing": False}}, ""),
        ("Empezó la instalación de VLC media player; el instalador sigue corriendo.", {"operation": "package.install.commit", "seen": {"name": "VLC media player", "installed": False, "installing": True}}, ""),
    ],
)
def test_the_reply_names_the_package_and_never_claims_more_than_seen(text: str, payload: dict, defect: str) -> None:
    assert llm._package_fact_defect(text, payload) == defect


def test_the_absences_have_their_own_cause_facts() -> None:
    for code in ("winget_package_not_resolved", "winget_package_ambiguous", "winget_package_not_installed",
                 "winget_install_not_verified", "winget_uninstall_not_verified", "winget_adapter_unavailable"):
        assert code in llm._CAUSE_FACT
