"""Ronda 21, destino por contenido sin app nombrada (pasada r18: t-file-1, t-file-3, t-menu-4, t-form-4, t-drag-2).

A request that names no application looked only at the window in front, the person's own; since ronda 20 P3 such a
request did not even reach the engine (``engine_destination_said``). The mind now reads what the request names of the
window where it happens — a menu, a dialog, a panel or a tab by its name, a selection, a document with something to
save — and hands it to the shell as the mission's ``referent*`` arguments; the shell binds the one window that shows it
or asks which (``ComputerUseDestination``, tested in ComputerUseDestinationTests.cs). The case texts are the lote's own
(scripts/cu_live/cases/*.turns).
"""

from __future__ import annotations

import pytest

from baxy_mind import operation_floor
from baxy_mind import cu_projection
from baxy_mind.semantic import cu_tipos, missions

APPS = ("BAXY", "Bloc de notas", "Microsoft Edge", "OneNote", "Paint", "PowerPoint", "Spotify", "Steam", "Word")

T_FILE_1 = "guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3"
T_FILE_3 = "Save this drawing as baxy-dibujo.png in Documents\\baxy-prueba-v3"
T_MENU_4 = "Gira la imagen 90 grados a la derecha desde el menú Imagen > Girar"
T_FORM_4 = "Ponme el texto seleccionado en Arial, tamaño 20 y en cursiva, desde el cuadro de diálogo de Fuente"
T_DRAG_2 = "En el panel de miniaturas arrastra la diapositiva «Tres» para que quede la primera"

NOTEPAD_TURN = ("en el bloc de notas escribí la lista del súper",)


@pytest.fixture(autouse=True)
def _no_file_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(missions, "_file_taken", lambda _path: False)


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        (T_MENU_4, {"referentLabels": ["imagen", "girar"]}),
        # Ronda 24 (pasada r23): a dialog said goes apart (one still closed is seen nowhere) and a quoted name is content.
        (T_FORM_4, {"referentDialogs": ["fuente"], "referentSelection": True}),
        # Estabilización L: T_DRAG_2 drags (the known limit); its referent is read on the same order with a click.
        ("En el panel de miniaturas seleccioná la diapositiva «Tres»", {"referentLabels": ["miniaturas"], "referentItems": ["tres"]}),
        ("Open the Format menu and choose Font", {"referentLabels": ["format"]}),
    ],
)
def test_the_referent_of_a_request_without_application(said: str, expected: dict) -> None:
    arguments = missions.free_form_arguments(said, APPS)
    assert arguments is not None
    assert "application" not in arguments
    assert {key: value for key, value in arguments.items() if key.startswith("referent")} == expected
    # The engine has a place: the window that shows it, which the shell looks for.
    assert missions.engine_destination_said(said, APPS)
    # Estabilización R21: the dead wrapper engine_has_a_destination read the same arguments; the referent is what
    # makes the place.
    assert missions._by_referent(arguments)


@pytest.mark.parametrize("said", [T_FILE_1, T_FILE_3])
def test_a_save_of_what_is_shown_with_no_window_named_is_asked_about(said: str) -> None:
    # Estabilización L: «guardá esto», «this drawing» with no window named is never the window in front nor one the
    # engine guesses among the open ones (the save referent is retired): with no application it acts in no window.
    arguments = missions.free_form_arguments(said, APPS)
    assert arguments is not None
    assert "frontWindow" not in arguments
    assert not any(key.startswith("referent") for key in arguments)
    assert not missions.engine_destination_said(said, APPS)


@pytest.mark.parametrize("said", [
    "en esta ventana guardá esto como baxy-nota1.txt en Documentos, en la carpeta baxy-prueba-v3",
    "in this window save this as baxy-nota1.txt in Documents\\baxy-prueba-v3",
])
def test_ronda_23_contracase_en_esta_ventana_stays_absolute(said: str) -> None:
    # «esto» of a save is a referent (no frontWindow); the window in front named as such is the destination, and no
    # window is looked for in its place.
    arguments = missions.free_form_arguments(said, APPS)
    assert arguments is not None
    assert arguments.get("frontWindow") is True
    assert not any(key.startswith("referent") for key in arguments)


def test_no_window_is_ever_looked_for_a_save_of_what_is_shown() -> None:
    # The save referent the shell weighed (referentUnsaved) is retired: no arguments carry it, after a reply of BAXY's
    # (M67: «esto» is that reply, the typed write keeps it) or not.
    arguments = missions.free_form_arguments(T_FILE_1, APPS)
    assert arguments is not None
    assert not any(key.startswith("referent") for key in arguments) and "frontWindow" not in arguments


@pytest.mark.parametrize("said", ["hacé clic en Aceptar", "hacé clic en «Aceptar»", "escribí hola", "gira la imagen"])
def test_contracase_a_request_without_referent_keeps_todays_route(said: str) -> None:
    arguments = missions.free_form_arguments(said, APPS)
    assert arguments is not None
    assert not any(key.startswith("referent") for key in arguments), arguments
    assert not missions.engine_destination_said(said, APPS)


@pytest.mark.parametrize(
    "said",
    ["poné en negrita el texto seleccionado", "copiá el texto seleccionado", "agrandá la letra de la selección"],
)
def test_revision_1_b2_a_selection_alone_keeps_its_typed_route(said: str) -> None:
    # Revision 1 of r21 (B2): before the round these went by their typed route; a selection names no window, so the
    # engine is not handed them on its account (the shell would weigh windows by a selection it cannot see).
    assert missions.referent_cues(said) == {"referentSelection": True}
    assert not missions.engine_destination_said(said, APPS)


def test_contracase_an_application_said_is_the_destination_and_no_referent_is_sent() -> None:
    said = "en Paint gira la imagen desde el menú Imagen > Girar"
    arguments = missions.free_form_arguments(said, APPS)
    assert arguments is not None
    assert arguments.get("application") == "Paint"
    assert not any(key.startswith("referent") for key in arguments)


def test_contracase_the_conversations_application_stays_out_of_a_typed_route_p3() -> None:
    # «recargá la página de chrome» after a turn in the Bloc de notas is not handed to the engine (ronda 20 P3); a
    # request with a referent in a conversation that has an application keeps that application, and no referent.
    assert not missions.engine_destination_said("recargá la página de chrome", APPS, NOTEPAD_TURN)
    arguments = missions.free_form_arguments("abrí el menú Formato", APPS, NOTEPAD_TURN)
    assert arguments is not None
    assert arguments.get("application") == "Bloc de notas"
    assert not any(key.startswith("referent") for key in arguments)
    assert not missions.engine_destination_said("abrí el menú Formato", APPS, NOTEPAD_TURN)


@pytest.mark.parametrize(
    "said",
    [
        'escribí "abrí el menú Archivo"',
        "escribí: desde el cuadro de diálogo de Fuente",
        "abrí el menú contextual",
        "abrí el menú de inicio",
        "abrí una pestaña nueva",
        "cerrá la pestaña actual",
    ],
)
def test_contracase_words_that_name_no_window(said: str) -> None:
    # A dictated text is the text, not a place; «contextual», «inicio» name no window's menu.
    assert "referentLabels" not in missions.referent_cues(said), said


def test_referent_names_reads_every_piece_of_a_menu_route() -> None:
    assert cu_tipos.referent_names("desde el menu archivo > exportar > png") == ("archivo", "exportar", "png")
    assert cu_tipos.referent_names("en la pestana de vista") == ("vista",)
    assert cu_tipos.referent_names("use the view tab") == ("view",)
    assert cu_tipos.referent_names("en el panel lateral") == ()


def test_the_final_of_an_ambiguous_destination_names_the_windows_and_asks() -> None:
    observed = {
        "goal": T_MENU_4, "reached": False, "steps": [], "stoppedBy": "computer_use_destination_ambiguous",
        "destinationCandidates": ["uno.png - Paint", "dos.png - Paint"],
    }
    seen = cu_projection.project_seen(observed, "es")
    assert "«uno.png - Paint»" in seen["stoppedBecause"] and "«dos.png - Paint»" in seen["stoppedBecause"]
    assert "decime en cuál" in seen["stoppedBecause"]
    english = cu_projection.project_seen(observed, "en")
    assert "tell me which one" in english["stoppedBecause"]
    # Contracase: none found is an honest limit that opened nothing.
    seen = cu_projection.project_seen({**observed, "stoppedBy": "computer_use_destination_not_found",
                                      "destinationCandidates": []}, "es")
    assert seen["stoppedBecause"] == operation_floor.floor_data()["computerUse"]["causes"][
        "computer_use_destination_not_found"]["es"]
    assert "destinationCandidates" not in seen



@pytest.mark.parametrize(
    "code", ["computer_use_destination_not_found", "computer_use_destination_persons_window", "computer_use_destination_unlisted"]
)
def test_revision_1_b3_the_finals_claim_only_what_was_looked_at(code: str) -> None:
    # Revision 1 of r21 (B3): protected windows are never read and the person's window is never taken, so no final says
    # that no open window shows what was named; the person's window fitting is said as such.
    causes = operation_floor.floor_data()["computerUse"]["causes"]
    for language in ("es", "en"):
        said = causes[code][language]
        assert "ninguna ventana abierta muestra" not in said and "no open window shows" not in said
        seen = cu_projection.project_seen(
            {"goal": T_MENU_4, "reached": False, "steps": [], "stoppedBy": code}, language)
        assert seen["stoppedBecause"] == said
    assert "que pude mirar" in causes["computer_use_destination_not_found"]["es"]
    assert "estás trabajando" in causes["computer_use_destination_persons_window"]["es"]


def test_ronda_23_a_save_of_what_is_shown_is_asked_about_in_both_languages() -> None:
    # Ronda 23 (r21 t-file-1) asked which window after looking for one; estabilización L asks before anything, short.
    causes = operation_floor.floor_data()["computerUse"]["causes"]
    assert "computer_use_destination_unsaved_not_found" not in causes
    # With no application the mission acts in no window and asks which one, in both languages.
    for language in ("es", "en"):
        assert causes["computer_use_no_application"][language].rstrip().endswith(("cuál", "which one"))


EXPLORER_APPS = APPS + ("Explorador de archivos",)


@pytest.mark.parametrize(
    "said",
    [
        "andá a Descargas en el panel de la izquierda",
        "cambiá a la pestaña de la derecha",
        "pasá a la pestaña de al lado",
        "en el dialogo escribí hola",
        "en el diálogo escribi hola",
        "en el panel seleccioná todo",
        "andá al menú de arriba y abrí Archivo",
        "abrí la pestaña de la izquierda",
        "en el panel de abajo hacé clic en Aceptar",
    ],
)
def test_revision_3_b2_a_place_a_relation_or_a_verb_is_no_name(said: str) -> None:
    # Revisión 3 de r21 (B2): «izquierda», «derecha», «al lado», «arriba» say where; «escribí», «seleccioná» are the
    # order. None is the name of a menu, a panel or a tab: no referent, and the request keeps its route of before the
    # round (engine_destination_said False), never a false «no encontré lo que nombraste».
    arguments = missions.free_form_arguments(said, EXPLORER_APPS)
    assert arguments is not None
    assert "referentLabels" not in arguments, arguments
    assert not missions.engine_destination_said(said, EXPLORER_APPS)


@pytest.mark.parametrize(
    ("said", "labels"),
    [
        ("desde la pestaña Revisar activá el control de cambios", ["revisar"]),
        ("desde la pestaña Insertar agregá una tabla", ["insertar"]),
        ("open the Insert tab and add a table", ["insert"]),
        ("en el panel de miniaturas seleccioná la segunda", ["miniaturas"]),
    ],
)
def test_revision_3_b2_contracase_a_command_named_by_its_infinitive_stays_a_name(said: str, labels: list[str]) -> None:
    # An infinitive is a command's own name in the windows («Insertar», «Revisar»); in English the name goes before
    # the container and no order starts at it.
    arguments = missions.free_form_arguments(said, EXPLORER_APPS)
    assert arguments is not None
    assert arguments.get("referentLabels") == labels


@pytest.mark.parametrize("said", [
    "guardá esta página como pagina.html en Documentos",
    "guardá esto como copia.txt en Documentos",
    "guardá este documento como informe2.docx en Documentos",
])
def test_ronda_23_revision_1_b1_a_save_of_what_is_shown_is_asked_about_never_weighed(said: str) -> None:
    # Revision 1 of r23 (B1) sent the referent alone and the shell weighed the window in front; estabilización L: with
    # no window named no window is weighed: the mission acts in none (computer_use_no_application).
    arguments = missions.free_form_arguments(said, APPS)
    assert arguments is not None
    assert not any(key.startswith("referent") for key in arguments)
    assert "frontWindow" not in arguments and "application" not in arguments
    assert str(arguments.get("successCheck", "")).startswith("file:")
