"""Pasada r15b, segunda vuelta (2026-10-09): t-menu-2 y t-scroll-3.

t-menu-2 «en baxy-prueba-v3 ordená los archivos por tamaño, con el clic derecho en un espacio vacío, Ordenar por»:
ningún lector lo leyó (la orden se dice en una carpeta de la persona y en ninguna aplicación), el decisor tomó un
input.visible.click suelto (turn_audit: decision_path context_decider, «haz clic derecho en un espacio vacío») y el
final dijo que no había nada seleccionable, con el Explorador abierto en la carpeta. Ahora la orden dicha en una
carpeta se lee en la aplicación que muestra carpetas (``folder_application`` de data/app_aliases.v1.json), yendo antes
a la carpeta: su ruta si es la única con ese nombre bajo las carpetas conocidas, su nombre si hay dos.

t-scroll-3 «Go to Settings, Personalization, Fonts, scroll down to Times New Roman and open its page»: el buscador de
Configuración quedó con «fuetimes new romanntes». La ventana estaba detrás de la de la persona (ningún control con el
teclado), así que el segundo texto se escribió sin vaciar el campo, en el cursor que un clic había dejado dentro de
«fuentes». Ahora el campo que el último clic nombró, si guarda texto y es un buscador, se reemplaza entero por su
índice (SetValue). El «ya estabas» de ese caso es del App (CuV3HonestidadR15b2ScrollMenuTests.cs).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind import known_folders  # noqa: E402
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind.semantic import catalog, missions, patterns  # noqa: E402

START = json.loads((ROOT / "tests" / "data" / "cu_v3_start_catalog.v1.json").read_text(encoding="utf-8"))["names"]
INDEX = catalog.build_application_catalog_index(START)
OPERATIONS = ("app.open", "app.close", "mission.computer.use", "web.search", "browser.navigate", "file.open",
              "note.create", "input.key.press", "input.text.type", "input.visible.click", "window.focus")
T_MENU_2 = "en baxy-prueba-v3 ordená los archivos por tamaño, con el clic derecho en un espacio vacío, Ordenar por"


@pytest.fixture
def documents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The known folders of a PC whose Documentos holds the case's folder (and nothing else known exists)."""

    root = tmp_path / "Documentos"
    (root / "baxy-prueba-v3" / "archivo").mkdir(parents=True)
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: {"documents": str(root)}.get(folder))
    return root


# ------------------------------------------------------------ t-menu-2: una orden dicha en una carpeta


def test_an_order_said_in_a_folder_of_the_persons_is_a_mission_in_the_folder_application(
    documents: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The case's PC: the one folder of that name, at a path the going reader takes.
    path = r"D:\Perfil\Documentos\baxy-prueba-v3"
    monkeypatch.setattr(known_folders, "located_folders", lambda name, within=None: ((path,), True))
    mission = missions.mission_request(T_MENU_2, INDEX)
    assert mission is not None
    assert mission.application == "Explorador de archivos"
    goals = [step.goal for step in mission.steps]
    assert goals[0] == f"ir a {path.lower()}"
    # The path keeps its separators whole (review finding 3: a control character once stood for «\b»).
    assert goals[0].endswith("\\documentos\\baxy-prueba-v3") and goals[0].isprintable()
    assert goals[1:3] == ["abrir el menu contextual de espacio vacio", "hacer clic en ordenar por"]
    assert goals[3] == "ordená los archivos por tamaño"  # the person's words, as said
    assert patterns.resolve_explicit_effects(T_MENU_2, OPERATIONS, INDEX).operations == ("mission.computer.use",)


def test_a_path_too_long_to_go_to_is_gone_to_by_the_folders_name(documents: Path) -> None:
    # tmp_path is longer than the going reader's place: the folder's name is gone to, never a free «anda a C:\…».
    mission = missions.mission_request(T_MENU_2, INDEX)
    assert mission is not None and mission.steps[0].goal == "ir a baxy-prueba-v3"


def test_the_folders_are_found_under_the_known_folders(documents: Path) -> None:
    assert known_folders.located_folders("BAXY-prueba-v3") == ((str(documents / "baxy-prueba-v3"),), True)
    assert known_folders.located_folders("documentos") == ((str(documents),), True)
    assert known_folders.located_folders("otra") == ((), True)
    assert known_folders.located_folders("..") == ((), True)
    (documents / "Documentos" / "baxy-prueba-v3").mkdir(parents=True)
    found, told = known_folders.located_folders("baxy-prueba-v3", "documents")
    assert len(found) == 2 and told


def test_two_folders_of_one_name_are_not_guessed_between_the_name_is_gone_to(
    documents: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This PC: Documentos\baxy-prueba-v3 and Documentos\Documentos\baxy-prueba-v3. The window may already show it.
    (documents / "Documentos" / "baxy-prueba-v3").mkdir(parents=True)
    mission = missions.mission_request(T_MENU_2, INDEX)
    assert mission is not None and mission.steps[0].goal == "ir a baxy-prueba-v3"
    assert "title:baxy-prueba-v3" in (mission.steps[0].success_check or "")


def test_a_known_folder_said_is_its_path(documents: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(known_folders, "located_folders", lambda name, within=None: ((r"D:\Perfil\Documentos",), True))
    mission = missions.mission_request("en Documentos ordená los archivos por fecha", INDEX)
    assert mission is not None and mission.application == "Explorador de archivos"
    assert mission.steps[0].goal == r"ir a d:\perfil\documentos"


def test_the_folder_said_in_english_is_read_too(documents: Path) -> None:
    mission = missions.mission_request("in the baxy-prueba-v3 folder, sort the files by size", INDEX)
    assert mission is not None and mission.application == "Explorador de archivos"
    assert [step.goal for step in mission.steps][-1] == "sort the files by size"


@pytest.mark.parametrize("said", [
    "en baxy-prueba-v3 me encanta esta foto",          # a remark said there: no doing
    "en otra-carpeta ordená los archivos por tamaño",  # no folder of that name on this PC
    "en serio, ordená los archivos por tamaño",        # a phrase, no folder
])
def test_what_is_no_doing_in_an_existing_folder_is_no_folder_mission(documents: Path, said: str) -> None:
    assert missions.mission_request(said, INDEX) is None


def test_a_plain_word_said_bare_is_no_folder_even_when_one_has_that_name(documents: Path) -> None:
    # tests/test_cu_v3_nombres.py: «en stream escribí hola» is a word, whatever folders this PC holds.
    (documents / "stream").mkdir()
    (documents / "Proyectos").mkdir()
    assert missions.mission_request("en stream escribí hola", INDEX) is None
    assert missions.mission_request("en Proyectos ordená los archivos por tamaño", INDEX) is None
    said = missions.mission_request("en la carpeta Proyectos ordená los archivos por tamaño", INDEX)
    assert said is not None and said.application == "Explorador de archivos"


def test_an_application_said_in_the_frame_is_still_that_application(documents: Path) -> None:
    (documents / "Paint").mkdir()
    mission = missions.mission_request("en Paint, agarrá el lápiz", INDEX)
    assert mission is None or mission.application == "Paint"


def test_nothing_on_the_disk_is_searched_when_no_doing_is_read(
    documents: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(*_: object, **__: object) -> object:
        raise AssertionError("the disk was searched")

    monkeypatch.setattr(known_folders, "located_folders", refuse)
    assert missions.mission_request("en baxy-prueba-v3 me encanta esta foto", INDEX) is None


# ------------------------------------------------------------ t-scroll-3: el buscador que ya tenía texto

# v2-t-scroll-3, paso 12: la vista tras el clic en el buscador (paso 11), recortada. La ventana está detrás de la de la
# persona: ningún control dice tener el teclado y el buscador guarda «fuentes», que la misión escribió en el paso 6.
SETTINGS_BEHIND = {
    "window": {"title": "Configuración", "process": "SystemSettings", "requested": True, "foreground": False},
    "controls": [
        {"i": 0, "kind": "MenuItem", "name": "Sistema", "state": "collapsed"},
        {"i": 1, "kind": "Button", "name": "Minimizar Configuración", "state": ""},
        {"i": 2, "kind": "Button", "name": "Maximizar Configuración", "state": ""},
        {"i": 3, "kind": "Button", "name": "Cerrar Configuración", "state": ""},
        {"i": 4, "kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "state": "", "value": "fuentes"},
        {"i": 5, "kind": "ListItem", "name": "Configuración de fuentes", "state": "selected"},
        {"i": 6, "kind": "ListItem", "name": "Descargar fuentes para todos los idiomas", "state": ""},
        {"i": 7, "kind": "ListItem", "name": "Aumentar el tamaño del texto", "state": ""},
        {"i": 8, "kind": "ListItem", "name": "Efectos visuales", "state": ""},
    ],
    "text": {},
}
CLICKED_BOX = {"step": 11, "operation": "input.visible.click", "label": "Cuadro de búsqueda, Buscar una opción",
               "index": 4, "ok": True, "kind": "Edit", "surfaceChanged": True}


def _copy(view: dict) -> dict:
    return json.loads(json.dumps(view))


def test_a_search_box_holding_text_with_no_focus_reported_is_replaced_whole_by_its_index() -> None:
    step = cu_rules.deterministic_step(goal="ir a times new roman", view=SETTINGS_BEHIND, history=[CLICKED_BOX])
    # Before: {"text": "times new roman"} at the caret the step-7 click left inside «fuentes» → «fuetimes new romanntes».
    assert step is not None and step["operation"] == "input.text.type"
    assert step["arguments"] == {"text": "times new roman", "index": 4, "replace": True}


def test_an_empty_box_or_one_in_focus_is_typed_as_before() -> None:
    empty = _copy(SETTINGS_BEHIND)
    empty["controls"][4]["value"] = ""
    step = cu_rules.deterministic_step(goal="ir a times new roman", view=empty, history=[CLICKED_BOX])
    assert step is not None and step["arguments"] == {"text": "times new roman"}
    # In focus, the leftover is still selected with the keyboard first (measured «colorespantalla»).
    focused = _copy(SETTINGS_BEHIND)
    focused["controls"][4]["state"] = "focused"
    step = cu_rules.deterministic_step(goal="ir a times new roman", view=focused, history=[CLICKED_BOX])
    assert step is not None and step["arguments"] == {"key": "ctrl_a"}


@pytest.mark.parametrize(("kind", "name"), [
    ("Document", "Cuadro de búsqueda, Buscar una opción"),  # a document is the person's work, whatever its name
    ("Edit", "Asunto"),                                      # a field not named as a search
])
def test_a_document_or_a_field_not_named_as_a_search_is_never_replaced(kind: str, name: str) -> None:
    view = _copy(SETTINGS_BEHIND)
    view["controls"][4].update(kind=kind, name=name)
    clicked = {**CLICKED_BOX, "label": name, "kind": kind}
    step = cu_rules.deterministic_step(goal="ir a times new roman", view=view, history=[clicked])
    assert step is None or step["arguments"].get("replace") is not True, step


def test_a_clicked_search_box_without_an_index_and_no_focus_gets_no_keys() -> None:
    # Review finding 4: no field has the keyboard and the clicked box holding text carries no index to replace it by;
    # a ctrl_a would go to whatever has the keyboard and a plain type would land at the caret inside «fuentes».
    view = _copy(SETTINGS_BEHIND)
    box = dict(view["controls"][4])
    del box["i"]
    step = cu_lookup._type_into(view, [CLICKED_BOX], "times new roman", box)
    assert step is None
    # Counter-cases: the same box with its index is replaced whole; in focus it is selected with the keyboard first.
    step = cu_lookup._type_into(view, [CLICKED_BOX], "times new roman", view["controls"][4])
    assert step is not None and step["arguments"] == {"text": "times new roman", "index": 4, "replace": True}
    focused = _copy(SETTINGS_BEHIND)
    focused["controls"][4]["state"] = "focused"
    step = cu_lookup._type_into(focused, [CLICKED_BOX], "times new roman", None)
    assert step is not None and step["arguments"] == {"key": "ctrl_a"}


def test_the_folder_search_waits_on_the_disk_no_longer_than_its_bound(
    documents: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Review finding 5: the reader walks the disk on a phrase said in a folder with a doing; past
    # _FOLDER_SEARCH_SECONDS it stops and says it did not tell. A clock that jumps past the bound after the first look.
    (documents / "otra" / "mas").mkdir(parents=True)
    ticks = iter([0.0] + [known_folders._FOLDER_SEARCH_SECONDS + 1.0] * 50)
    monkeypatch.setattr(known_folders, "_clock", lambda: next(ticks))
    folders, told = known_folders.located_folders("baxy-prueba-v3")
    assert folders == (str(documents / "baxy-prueba-v3"),) and told is False
    # Cut short, the one folder found may not be the only one: it is gone to by its name, never by its path.
    ticks = iter([0.0] + [known_folders._FOLDER_SEARCH_SECONDS + 1.0] * 50)
    mission = missions.mission_request(T_MENU_2, INDEX)
    assert mission is not None and mission.steps[0].goal == "ir a baxy-prueba-v3"


def test_the_folder_search_tells_within_its_bounds_and_stops_at_its_entry_budget(
    documents: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Counter-case: within the bound the one folder is told as the only one.
    assert known_folders.located_folders("baxy-prueba-v3") == ((str(documents / "baxy-prueba-v3"),), True)
    # The entry budget cuts a wide tree the same way, whatever the clock.
    for number in range(30):
        (documents / f"d{number:02d}").mkdir()
    monkeypatch.setattr(known_folders, "_SEARCH_ENTRIES", 5)
    assert known_folders.located_folders("no-existe")[1] is False
