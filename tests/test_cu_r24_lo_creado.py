"""Ronda 24, lo que la misión creó es suyo (pasada r23 v3-11 t1): «Agregar página» made «Sin título - OneNote», a
title that never names the thing; the same fact the App keeps as the mission's created document proves the creation,
and a mission that stops says what it created before what it typed. The App's side is ComputerUseLoopTests.Ownership
and tests/data/cu_floor_twins.json («cu-left-created-document»).

Encargo EX: the mind no longer keeps a twin of the App's rule (the first look, the «Sin título» counted before and after
the click): it reads the App's record on the click, «createdDocument» (HistoryForMind). The counting cases live in
ComputerUseLoopTests.Ownership (NoteCreatedDocument with NotesListing, controlsBeforeClick, countsBeforeClick)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import cu_creation
from baxy_mind import cu_finals

GOAL = "crear una pagina nueva"


def _view(title: str, first_look: str) -> dict:
    return {"window": {"title": title}, "firstLook": first_look, "controls": [], "newText": []}


def _click(label: str, created: str | None = None) -> dict:
    click = {"operation": "input.visible.click", "label": label, "ok": True}
    if created is not None:
        click["createdDocument"] = created
    return click


def test_an_untitled_page_the_app_recorded_proves_the_creation() -> None:
    done = cu_creation._created_by_diff(GOAL, _view("Sin título - OneNote", "Lista del super - OneNote\nLista del super"),
                                        [_click("Agregar página", created="Sin título")])
    assert done is not None
    assert done["operation"] == "done"
    assert done["arguments"]["evidence"] == "Sin título - OneNote"


def test_an_untitled_page_the_app_did_not_record_proves_nothing() -> None:
    # Contracase: the App recorded no creation (the first look already had a page without a title, or the click chose
    # an existing page): the mind never judges it again on the view.
    assert cu_creation._created_by_diff(GOAL, _view("Sin título - OneNote", "Lista del super - OneNote\nSin título"),
                                        [_click("Agregar página")]) is None
    assert cu_creation._created_by_diff(GOAL, _view("Sin título - OneNote", "Lista del super - OneNote"),
                                        [_click("Agregar página")]) is None


def test_selecting_an_existing_page_proves_nothing() -> None:
    # Contracase: a click on an existing page creates nothing, whatever its title.
    assert cu_creation._created_by_diff(GOAL, _view("Sin título - OneNote", "Lista del super - OneNote"),
                                        [_click("Sin título")]) is None
    assert cu_creation._created_by_diff(GOAL, _view("Recetas - OneNote", "Lista del super - OneNote"),
                                        [_click("Recetas")]) is None


def test_a_record_of_another_document_proves_nothing() -> None:
    # Contracase: the window now titles a document other than the one the App recorded (the person's page in front).
    assert cu_creation._created_by_diff(GOAL, _view("Informe sin titulo final del mes - OneNote", "Lista del super - OneNote"),
                                        [_click("Agregar página", created="Sin título")]) is None


def test_what_was_left_counts_what_was_created() -> None:
    steps = [
        {"step": 1, "operation": "input.visible.click", "label": "Agregar página", "ok": True, "createdDocument": "Sin título"},
        {"step": 2, "operation": "input.text.type", "text": "comprar pan", "ok": True},
    ]
    assert cu_finals._typed_left(steps, False) == "; antes de parar creé «Sin título» con «Agregar página» y escribí «comprar pan»"
    assert cu_finals._typed_left(steps[:1], True) == "; before stopping I created «Sin título» with «Agregar página»"
    # Contracase: with nothing created the sentence is the typed one, as before.
    assert cu_finals._typed_left(steps[1:], False) == "; antes de parar escribí «comprar pan»"


def _listing(untitled: int, title: str = "Sin título - OneNote") -> dict:
    # Revisión 3 de r24 (B1): as the provider gives them, one ListItem «Sin título» whose «repeated» counts the others.
    controls = [{"i": 0, "kind": "Button", "name": "Agregar página"}, {"i": 1, "kind": "TabItem", "name": "Trabajo"}]
    if untitled:
        controls.append({"i": 2, "kind": "ListItem", "name": "Sin título", "repeated": untitled - 1})
    view = {"window": {"title": title}, "controls": controls, "newText": []}
    view["firstLook"] = "Lista del super - OneNote\nLista del super\n" + "Sin título\n" * 7
    return view


def test_one_more_untitled_page_counts_only_through_the_app_s_record() -> None:
    # Revisión 2-3 de r24 (B1, pasada r23 v3-11): seven «Sin título» of the person's before «Agregar página» and eight
    # after. The App counts them (OneMoreAfterCommand) and records the page on the click; the mind reads that record.
    click = {"step": 1, "kind": "Button", **_click("Agregar página", created="Sin título")}
    done = cu_creation._created_by_diff(GOAL, _listing(8), [click])
    assert done is not None and done["arguments"]["evidence"] == "Sin título - OneNote"
    # Contracase: eight listed after the click and no record (the App's count did not hold): nothing is proved here.
    unrecorded = {"step": 1, "kind": "Button", **_click("Agregar página")}
    assert cu_creation._created_by_diff(GOAL, _listing(8), [unrecorded]) is None
