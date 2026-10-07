"""Revisión 2026-10-07 del lector de modos y del marco «… en <app>» (computer use v2).

Un cambio de modo se comprueba con lo que la ventana muestra del modo (su ítem elegido, su título, su página o su
cabecera nueva, ``header:X``), nunca con un clic sobre algo que contenga el nombre: la tarjeta de actividad de
Discord que dice «cotele», la carpeta «Descargas» o el ajuste «dark» también se clican. «cambiá/pasá/switch to» sin
palabra de modo ni nombre de modo es ir a un lugar.
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


def test_changing_to_a_place_or_a_mode_is_never_proved_by_a_click_on_its_name() -> None:
    for said in (
        "en Discord cambiá a cotele",
        "en el explorador pasá a descargas",
        "en Configuración switch to dark mode",
        "in the calculator switch to scientific mode",
        "en la calculadora cambiá a científica",
        "en la calculadora poné el modo científico",
        "en Configuración poné el modo avión",
    ):
        terms = _terms(said)
        assert not any("stepDone:input.visible.click" in term for term in terms), (said, terms)


def test_a_mode_said_by_its_word_or_its_name_shows_in_the_header() -> None:
    assert "control:dark:selected" in _terms("en Configuración switch to dark mode")
    scientific = _terms("en la calculadora cambiá a científica")
    assert {"header:cientifica", "header:scientific", "header:cientifico"} <= set(scientific)
    assert "header:standard" in _terms("en la calculadora pasate a la estándar")
    assert "header:programmer" in _terms("en la calculadora cambiá a programador")
    assert _mission("in the calculator switch to scientific mode").goal == "ir a scientific"


def test_a_place_with_no_mode_said_has_no_header() -> None:
    for said in ("en Discord cambiá a cotele", "en el explorador pasá a descargas", "en Discord pasate a general"):
        assert not any(term.startswith("header:") for term in _terms(said)), said
    assert _mission("en el explorador pasá a descargas").goal == "ir a descargas"


def test_putting_a_switch_mode_on_is_the_switch_on_only() -> None:
    # The settings page «Modo avión» is selected and titled with it while the switch stays off.
    assert _mission("en Configuración poné el modo avión").success_check == (
        "control:modo avion:on|control:airplane mode:on|control:modo de avion:on|control:avion:selected"
    )
    put = _terms("en la calculadora poné el modo científico")
    assert put[0] == "control:modo cientifico:on"
    assert "header:cientifica" in put


def test_changing_to_a_place_drops_its_place_noun_and_keeps_a_view_whole() -> None:
    assert _mission("en Discord cambiá al canal general").goal == "ir a general"
    assert _mission("en Discord pasá a la sala de voz de juegos").goal == "ir a juegos"
    assert _mission("en el explorador cambiá a la vista previa").goal == "ir a vista previa"
    assert _mission("en el explorador switch over to downloads").goal == "ir a downloads"
    # A tab is still a tab.
    assert _mission("en Google Chrome change to the Gmail tab").goal == "ir a la pestaña gmail"


def test_the_last_en_frames_a_place_never_a_literal() -> None:
    clicked = _mission("hacé clic en Ajustes en Steam")
    assert (clicked.application, clicked.goal) == ("Steam", "hacer clic en ajustes")
    for said in ("escribí Cuphead en el buscador en Steam", "buscá Hades en la tienda en Steam"):
        mission = missions.mission_request(said, APPS)
        assert mission is None or " en " not in mission.goal, (said, mission)


def test_a_mode_is_named_by_its_word_or_its_own_name_only() -> None:
    assert missions.mode_named("modo científico") == "cientifico"
    assert missions.mode_named("scientific mode") == "scientific"
    assert missions.mode_named("cientifica") == "cientifica"
    assert missions.mode_named("vista previa") == "vista previa"
    # A place keeps the gender said: «partido» is no mode, so no «partida».
    assert missions.mode_named("partido") is None and missions.mode_named("descargas") is None
    assert set(missions.mode_names("científico")) == {"cientifico", "cientifica", "scientific"}
    assert missions.gender_twin("científico") == "cientifica"


def test_the_modes_have_their_other_language_names() -> None:
    for spanish, english in (("cientifica", "scientific"), ("estandar", "standard"), ("programador", "programmer"),
                             ("grafica", "graphing"), ("conversor", "converter")):
        assert english in missions.label_alternatives(spanish), spanish
        assert spanish in missions.label_alternatives(english), english
