"""Revisión 2026-10-07 (y) del lector de misiones: vistas, modos sin nombre conocido, alias que pasaban a la primera
mirada, el reproductor heredado y los nombres con «&».

«la vista de X» va a X (sólo «vista previa», sin «de», guarda la palabra); un modo que ninguna ventana ofrece por su
nombre («modo avión», «dark mode») se prueba con su interruptor encendido o el ítem X elegido, nunca con la página,
el título o la cabecera de la página del interruptor.
"""

from __future__ import annotations

from baxy_mind.semantic import missions

APPS = ("Steam", "Discord", "Calculadora", "Configuración", "Explorador de archivos", "Paint", "Google Chrome")


def _mission(said: str) -> missions.MissionRequest:
    mission = missions.mission_request(said, APPS)
    assert mission is not None, said
    return mission


def _terms(said: str) -> list[str]:
    check = _mission(said).success_check
    assert check, said
    return check.split("|")


def test_the_view_of_x_goes_to_x_and_mode_named_reads_the_same() -> None:
    details = _mission("en el explorador cambiá a la vista de detalles")
    assert details.goal == "ir a detalles"
    assert {"control:detalles:selected", "control:details:selected"} <= set(details.success_check.split("|"))
    assert not any("vista" in term for term in details.success_check.split("|"))
    assert _mission("en el explorador cambiá a la vista de iconos grandes").goal == "ir a iconos grandes"
    apps = _mission("en Configuración cambiá a la vista de apps")
    assert apps.goal == "ir a apps" and "control:apps:selected" in apps.success_check.split("|")
    assert _mission("in File Explorer switch to the details view").goal == "ir a details"
    # «poné la vista de iconos grandes»: the goal keeps the view word; the engine goes to what mode_named reads.
    put = _mission("en el explorador poné la vista de iconos grandes")
    assert put.goal == "activar vista de iconos grandes"
    assert missions.mode_named("vista de iconos grandes") == "iconos grandes"
    assert "control:iconos grandes:selected" in put.success_check.split("|")
    assert missions.mode_named("vista de detalles") == "detalles"
    assert missions.mode_named("details view") == "details"


def test_a_compound_view_stays_whole_and_is_never_its_only_name() -> None:
    assert _mission("en el explorador cambiá a la vista previa").goal == "ir a vista previa"
    assert missions.mode_named("vista previa") == "vista previa"
    whole = _mission("en el explorador cambiá a la vista detalles")
    assert whole.goal == "ir a vista detalles"
    assert {"control:vista detalles:selected", "control:detalles:selected", "control:details:selected"} <= set(
        whole.success_check.split("|")
    )


def test_a_mode_no_window_offers_by_name_is_its_switch_on_or_the_item_chosen() -> None:
    for said, switch, item in (
        ("en Configuración cambiá al modo avión", "control:modo avion:on", "control:avion:selected"),
        ("en Configuración switch to airplane mode", "control:airplane mode:on", "control:airplane:selected"),
        ("en Configuración poné el modo oscuro", "control:modo oscuro:on", "control:oscuro:selected"),
    ):
        terms = _terms(said)
        assert switch in terms and item in terms, (said, terms)
        assert all(term.startswith("control:") and term.endswith((":on", ":selected")) for term in terms), (said, terms)
        assert not any(term.startswith(("title:", "page:", "header:")) for term in terms), (said, terms)
    assert _mission("en Configuración cambiá al modo avión").goal == "activar modo avion"
    assert _mission("en Configuración switch to airplane mode").goal == "activar airplane mode"
    # A mode a window offers by name is still chosen and shown.
    assert _mission("in the calculator switch to scientific mode").goal == "ir a scientific"
    assert "header:cientifico" in _terms("en la calculadora poné el modo científico")


def test_start_and_menu_acts_carry_no_other_name() -> None:
    start = _terms("in Settings go to Start")
    assert not any("inicio" in term for term in start), start
    assert not any(term.endswith(":start") or ":start:" in term for term in _terms("en Configuración andá a inicio"))
    for word, other in (("archivo", "file"), ("vista", "view"), ("nuevo", "new"), ("abrir", "open")):
        assert other not in missions.label_alternatives(word), word
        assert word not in missions.label_alternatives(other), other
    # Everything else keeps its other names.
    assert "home" in missions.label_alternatives("inicio")
    assert "edit" in missions.label_alternatives("editar")


def test_windows_media_player_is_the_legacy_player_when_both_are_installed() -> None:
    both = ("Windows Media Player Legacy", "Reproductor multimedia")
    assert missions.catalog_application("windows media player", both) == "Windows Media Player Legacy"
    assert missions.catalog_application("windows media player", ("Reproductor multimedia",)) == "Reproductor multimedia"
    assert missions.catalog_application("media player", both) == "Reproductor multimedia"


def test_a_name_said_with_an_ampersand_is_never_checked_by_a_short_piece() -> None:
    for said in ("in Settings go to Q&A", "in Settings go to AT&T"):
        mission = _mission(said)
        check = mission.success_check or ""
        assert not any(term.split(":")[1] in {"q", "a", "at", "t"} for term in check.split("|") if ":" in term), check
    assert _terms("in Settings go to Rock & Roll")[0] == "control:rock:current"
    # A name of the tables keeps its first piece, which the place holds in either spelling.
    time = _terms("in Settings go to Time & Language")
    assert "control:time:current" in time and all("&" not in term for term in time)
