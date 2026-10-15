"""Ronda 24, destino por estructura y nunca por contenido (pasada r23: t-drag-2, t-file-3, t-form-4).

The mind hands the shell what the request's structure names of the window where it happens, in three lists:
``referentLabels`` (a menu, a panel, a tab: they make a window fit), ``referentDialogs`` (a dialog: it adds only when
already open, so one still closed never blocks the mission) and ``referentItems`` (a quoted name said beside them: content
that adds to a window that fits and never makes one fit). The final names a window by its title only when it was asked
for (``windowAsked``). The shell's side is tested in ComputerUseDestinationStructureTests.cs.
"""

from __future__ import annotations

import pytest

from baxy_mind import operation_floor
from baxy_mind import cu_finals
from baxy_mind.semantic import cu_tipos, missions

APPS = ("BAXY", "Bloc de notas", "Microsoft Edge", "Paint", "PowerPoint", "Spotify", "Word")

T_DRAG_2 = "En el panel de miniaturas arrastra la diapositiva «Tres» para que quede la primera"
T_FORM_4 = "Ponme el texto seleccionado en Arial, tamaño 20 y en cursiva, desde el cuadro de diálogo de Fuente"
T_FILE_3 = "Save this drawing as baxy-dibujo.png in Documents\\baxy-prueba-v3"


@pytest.fixture(autouse=True)
def _no_file_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(missions, "_file_taken", lambda _path: False)


def _referent(arguments: dict) -> dict:
    return {key: value for key, value in arguments.items() if key.startswith("referent")}


def test_t_drag_2_the_quoted_name_is_an_item_never_a_label() -> None:
    # Estabilización L: t-drag-2 itself drags (the known limit, no arguments for the engine); its referent is read on
    # the same order with a click.
    assert missions.free_form_arguments(T_DRAG_2, APPS) is None
    said = "En el panel de miniaturas seleccioná la diapositiva «Tres»"
    arguments = missions.free_form_arguments(said, APPS)
    assert arguments is not None
    assert _referent(arguments) == {"referentLabels": ["miniaturas"], "referentItems": ["tres"]}
    assert missions.engine_destination_said(said, APPS)


def test_t_form_4_the_dialog_goes_apart_and_the_selection_stays() -> None:
    arguments = missions.free_form_arguments(T_FORM_4, APPS)
    assert arguments is not None
    assert _referent(arguments) == {"referentDialogs": ["fuente"], "referentSelection": True}
    # The engine still has a place: the window the shell finds by the selection.
    assert missions.engine_destination_said(T_FORM_4, APPS)


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("from the Font dialog box set Arial", {"referentDialogs": ["font"]}),
        ("en el diálogo Guardar como escribí informe", {"referentDialogs": ["guardar"]}),
        ("desde el menú Imagen > Girar, gira 90°", {"referentLabels": ["imagen", "girar"]}),
        ("en la pestaña Insertar agregá la imagen «logo»", {"referentLabels": ["insertar"], "referentItems": ["logo"]}),
    ],
)
def test_each_name_goes_to_the_list_of_its_container(said: str, expected: dict) -> None:
    assert missions.referent_cues(said) == expected


def test_contracase_a_quoted_name_alone_is_still_no_referent() -> None:
    # «hacé clic en «Aceptar»» names no window: no structure, no items either.
    assert missions.referent_cues("hacé clic en «Aceptar»") == {}
    arguments = missions.free_form_arguments("hacé clic en «Aceptar»", APPS)
    assert arguments is None or not _referent(arguments)


def test_contracase_a_verb_after_the_dialog_is_no_dialog_name() -> None:
    # Revisión 3 de r21 (B2) still holds for dialogs: «en el diálogo escribí hola» names no dialog.
    assert missions.referent_cues("en el dialogo escribí hola") == {}


def test_referent_names_by_container_marks_dialogs() -> None:
    assert cu_tipos.referent_names_by_container("desde el cuadro de dialogo de fuente") == (("fuente", True),)
    assert cu_tipos.referent_names_by_container("desde el menu imagen > girar") == (("imagen", False), ("girar", False))
    assert cu_tipos.referent_names_by_container("use the font dialog") == (("font", True),)
    # The flat reading of before keeps every name.
    assert cu_tipos.referent_names("desde el cuadro de dialogo de fuente en el panel de miniaturas") == ("fuente", "miniaturas")


def test_t_file_3_a_save_as_with_no_window_named_is_asked_about() -> None:
    # Estabilización L: «Save this drawing as …» names no window; the turn asks which one (the shell no longer weighs
    # the documents that can save: the save referent and its «not found» stops are retired).
    arguments = missions.free_form_arguments(T_FILE_3, APPS)
    assert arguments is not None
    assert not any(key.startswith("referent") for key in arguments)
    causes = operation_floor.floor_data()["computerUse"]["causes"]
    assert "computer_use_destination_save_as_not_found" not in causes


def _failed(window_asked: bool | None) -> dict:
    observed: dict = {
        "goal": T_DRAG_2,
        "reached": False,
        "steps": [],
        "window": {"title": "Spotify Premium"},
        "stoppedBy": "computer_use_no_step_visible",
    }
    if window_asked is not None:
        observed["windowAsked"] = window_asked
    return observed


@pytest.mark.parametrize("english", [False, True])
def test_t_drag_2_the_final_never_names_a_window_nobody_asked_for(english: bool) -> None:
    final = cu_finals.floor_sentence(_failed(False), english, False)
    assert final
    assert "Spotify" not in final


@pytest.mark.parametrize("english", [False, True])
def test_contracase_a_window_asked_for_is_still_named(english: bool) -> None:
    # Bound, tied, pointed at, or a fact of before the round without the mark: its title still names the place.
    for asked in (True, None):
        assert "Spotify Premium" in cu_finals.floor_sentence(_failed(asked), english, False)


def test_contracase_an_application_said_is_named_whatever_the_window() -> None:
    observed = _failed(False)
    observed["application"] = "PowerPoint"
    final = cu_finals.floor_sentence(observed, False, False)
    assert "PowerPoint" in final and "Spotify" not in final
