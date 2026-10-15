"""Una ruta de carpeta va a la barra de dirección (pasada r9 v3: t-scroll-4, v3-48) con vistas reales congeladas.

Medido: en el Explorador (t-scroll-4, «abrí C:\\Windows\\System32 … y seleccioná calc.exe») la rutina de búsqueda hizo
clic en «Buscar en Este equipo» y escribió «c:\\windows\\system32» allí: quedó una búsqueda vacía. En 7-Zip (v3-48, «andá
a la carpeta Documentos\\baxy-prueba-v3») la rutina pulsó ctrl_k, Escape y ctrl_f en una ventana sin búsqueda y la
misión paró sin navegar; la vista sí listaba el cuadro de dirección (un Edit sin nombre arriba, de casi todo el ancho).
Regla general: una ruta se escribe en el campo de dirección (por su nombre, o el campo sin nombre que cruza la parte
de arriba de la ventana), reemplazando lo que tenga, y Enter; sin campo listado, la tecla de la barra de dirección
(ctrl_l) una vez. Nunca en un buscador.

Revisión adversarial de la rama: sólo una carpeta que existe en una unidad local (Enter sobre un archivo lo abre o lo
ejecuta; una ruta UNC es un acceso de red no pedido); el campo con nombre de dirección sólo arriba, mostrando dónde
está la ventana y sin nada que envíe (un formulario con «Dirección de correo» y «Enviar»); ctrl_l nunca sobre el
trabajo de la persona ni se teclea después en otro campo que no sea de dirección; el Enter de una ruta probada en el
campo de dirección de una ventana leída detrás no pregunta como si fuera un mensaje; un clic fallido no se repite.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import known_folders
from baxy_mind import cu_address
from baxy_mind import cu_rules

_DATA = json.loads((Path(__file__).parent / "data" / "cu_v3_vistas_direccion.json").read_text(encoding="utf-8"))
# Where this PC keeps the person's documents in these tests: a real folder, so «is it a folder» is answered by the disk.
_ROOT: dict[str, Path] = {}


@pytest.fixture(autouse=True)
def _documents_here(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    (documents / "baxy-prueba-v3").mkdir(parents=True)
    (documents / "informe").mkdir()
    (tmp_path / "Downloads").mkdir()
    (tmp_path / "Downloads" / "setup.exe").write_bytes(b"MZ")
    _ROOT["documents"] = documents
    _ROOT["downloads"] = tmp_path / "Downloads"
    monkeypatch.setattr(known_folders, "known_folder", lambda folder: str(_ROOT[folder]) if folder in _ROOT else None)


def _path_7z() -> str:
    return str(_ROOT["documents"] / "baxy-prueba-v3")


def _view(name: str) -> dict:
    return copy.deepcopy(_DATA[name]["vista"])


def _opened(app: str) -> dict:
    return {"step": 1, "operation": "app.open", "appId": app, "ok": True, "changed": True}


def _click(step: int, label: str, index: int | None = None, ok: bool = True) -> dict:
    entry = {"step": step, "operation": "input.visible.click", "label": label, "ok": ok, "changed": ok}
    if index is not None:
        entry["index"] = index
    return entry


def _typed(step: int, text: str, ok: bool = True) -> dict:
    return {"step": step, "operation": "input.text.type", "text": text, "ok": ok, "changed": ok}


def _key(step: int, key: str, ok: bool = True) -> dict:
    return {"step": step, "operation": "input.key.press", "key": key, "ok": ok, "changed": ok}


GOAL_7Z = "ir a documentos\\baxy-prueba-v3"


# ---------------------------------------------------------------- v3-48: el cuadro de dirección sin nombre de 7-Zip


def test_v3_48_the_unnamed_wide_field_at_the_top_is_clicked_first_never_a_search_key() -> None:
    view = _view("sietezip_raiz")
    step = cu_rules.deterministic_step(goal=GOAL_7Z, view=view, history=[_opened("7-Zip File Manager")])
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"]["index"] == 11


def test_v3_48_then_the_rooted_path_replaces_what_the_field_holds() -> None:
    view = _view("sietezip_raiz")
    history = [_opened("7-Zip File Manager"), _click(2, "(edit)", 11)]
    step = cu_rules.deterministic_step(goal=GOAL_7Z, view=view, history=history)
    assert step == {
        "operation": "input.text.type",
        "arguments": {"text": _path_7z(), "index": 11, "replace": True},
        "reason": cu_address._REASON_ADDRESS,
    }


def test_v3_48_and_enter_goes_there_once_without_asking() -> None:
    # The real view was read behind the person's window (foreground false, no focus): the path is proven in the
    # address box by the click right before it, and nothing in the view may hand a text to a person, so the Enter
    # carries no message_composer target (RiskPolicy would stop the mission to ask).
    view = _view("sietezip_raiz")
    history = [_opened("7-Zip File Manager"), _click(2, "(edit)", 11), _typed(3, _path_7z())]
    step = cu_rules.deterministic_step(goal=GOAL_7Z, view=view, history=history)
    assert step is not None and step["operation"] == "input.key.press"
    assert step["arguments"] == {"key": "enter"}
    # After the Enter the arrival check or the model decide: no second typing, no search key.
    after = cu_address._address_step("documentos\\baxy-prueba-v3", view, [*history, _key(4, "enter")])
    assert after is None


def test_v3_48_the_enter_is_free_when_the_field_shows_the_path_too() -> None:
    view = _view("sietezip_raiz")
    field = next(control for control in view["controls"] if control["i"] == 11)
    field["value"] = _path_7z()
    history = [_opened("7-Zip File Manager"), _key(2, "tab"), _typed(3, _path_7z())]
    step = cu_address._address_step("documentos\\baxy-prueba-v3", view, history)
    assert step is not None and step["arguments"] == {"key": "enter"}


def test_counter_case_the_enter_asks_when_another_box_may_hold_a_message() -> None:
    view = _view("sietezip_raiz")
    view["controls"].append({"i": 40, "kind": "Edit", "name": "(edit)", "state": "",
                             "rect": {"x": 230, "y": 800, "w": 900, "h": 20}, "zone": "B"})
    history = [_opened("7-Zip File Manager"), _click(2, "(edit)", 11), _typed(3, _path_7z())]
    step = cu_address._address_step("documentos\\baxy-prueba-v3", view, history)
    assert step is not None and step["arguments"].get("target") == "message_composer"


def test_counter_case_the_enter_asks_when_nothing_proves_where_the_path_went() -> None:
    view = _view("sietezip_raiz")
    history = [_opened("7-Zip File Manager"), _key(2, "tab"), _typed(3, _path_7z())]
    step = cu_address._address_step("documentos\\baxy-prueba-v3", view, history)
    assert step is not None and step["arguments"].get("target") == "message_composer"


def test_counter_case_a_narrow_unnamed_field_is_no_address() -> None:
    view = _view("sietezip_raiz")
    field = next(control for control in view["controls"] if control["i"] == 11)
    field["rect"]["w"] = 200
    assert cu_address._address_field(view) is None
    step = cu_address._address_step("documentos\\baxy-prueba-v3", view, [_opened("7-Zip File Manager")])
    assert step is not None and step["arguments"] == {"key": "ctrl_l"}


def test_counter_case_a_failed_typing_is_not_followed_by_enter() -> None:
    view = _view("sietezip_raiz")
    history = [_opened("7-Zip File Manager"), _click(2, "(edit)", 11), _typed(3, _path_7z(), ok=False)]
    assert cu_address._address_step("documentos\\baxy-prueba-v3", view, history) is None


def test_counter_case_a_failed_click_on_the_field_is_not_repeated() -> None:
    view = _view("sietezip_raiz")
    history = [_opened("7-Zip File Manager"), _click(2, "(edit)", 11, ok=False)]
    assert cu_address._address_step("documentos\\baxy-prueba-v3", view, history) is None


# ---------------------------------------------------------------- sólo una carpeta local que existe


@pytest.mark.parametrize("target", [
    "{downloads}\\setup.exe",          # a file: Enter in the address field would launch it
    "c:\\windows\\system32\\calc.exe",  # t-scroll-4's file, never its folder
    "documentos\\no-existe",            # no such folder
    "\\\\servidor\\compartida",          # a share on another machine: a network access nobody asked for
    "proyectos\\baxy",                  # relative, no known folder roots it: a search in a browser
])
def test_counter_case_only_an_existing_local_folder_goes_to_the_address_field(target: str) -> None:
    target = target.format(downloads=_ROOT["downloads"])
    assert cu_address._address_path(target) is None
    view = _view("sietezip_raiz")
    history = [_opened("7-Zip File Manager"), _click(2, "(edit)", 11), _typed(3, target)]
    assert cu_address._address_step(target, view, history[:1]) is None
    assert cu_address._address_step(target, view, history[:2]) is None
    assert cu_address._address_step(target, view, history) is None
    step = cu_rules.deterministic_step(goal="ir a " + target, view=view, history=history)
    assert step is None or step["arguments"].get("key") != "enter" or "target" in step["arguments"]


def test_a_unc_share_is_never_looked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_disk(self: Path) -> bool:
        raise AssertionError("no lookup of " + str(self))

    monkeypatch.setattr(Path, "is_dir", no_disk)
    assert cu_address._address_path("\\\\servidor\\compartida\\carpeta") is None


# ---------------------------------------------------------------- t-scroll-4: el Explorador, nunca su buscador


GOAL_EXPLORER = "ir a c:\\windows\\system32"


def test_t_scroll_4_a_path_never_goes_to_the_search_box() -> None:
    view = _view("explorador_este_equipo")
    # The view as it was: no address field among the listed controls, the search box «Buscar en Este equipo» is.
    history = [_click(1, "Downloads"), _click(2, "Este equipo"), _click(3, "Sistema")]
    step = cu_rules.deterministic_step(goal=GOAL_EXPLORER, view=view, history=history)
    assert step is not None and step["operation"] == "input.key.press" and step["arguments"]["key"] == "ctrl_l"


def test_t_scroll_4_the_address_field_the_key_focused_takes_the_path() -> None:
    view = _view("explorador_este_equipo")
    view["controls"].append({"i": 60, "kind": "Edit", "name": "Dirección", "state": "focused", "value": "Este equipo",
                             "rect": {"x": 700, "y": 60, "w": 600, "h": 30}, "zone": "T"})
    history = [_click(1, "Downloads"), _key(2, "ctrl_l")]
    step = cu_rules.deterministic_step(goal=GOAL_EXPLORER, view=view, history=history)
    assert step is not None and step["operation"] == "input.text.type"
    assert step["arguments"] == {"text": "c:\\windows\\system32", "index": 60, "replace": True}


def test_t_scroll_4_an_unlisted_field_the_key_focused_takes_the_path_by_its_focus() -> None:
    view = _view("explorador_este_equipo")
    view["window"]["focused"] = {"kind": "Edit", "name": "Dirección", "nameSource": "", "value": "Este equipo"}
    history = [_click(1, "Downloads"), _key(2, "ctrl_l")]
    step = cu_rules.deterministic_step(goal=GOAL_EXPLORER, view=view, history=history)
    assert step is not None and step["arguments"] == {"text": "c:\\windows\\system32"}


def test_counter_case_the_search_box_with_the_keyboard_after_the_key_gets_nothing() -> None:
    view = _view("explorador_este_equipo")
    view["window"]["focused"] = {"kind": "Edit", "name": "Buscar en Este equipo", "nameSource": "", "value": ""}
    history = [_click(1, "Downloads"), _key(2, "ctrl_l")]
    assert cu_address._address_step(GOAL_EXPLORER[len("ir a "):], view, history) is None


def test_counter_case_a_place_that_is_no_path_keeps_the_old_way() -> None:
    view = _view("explorador_este_equipo")
    assert cu_address._address_step("descargas", view, []) is None
    step = cu_rules.deterministic_step(goal="ir a descargas", view=view, history=[])
    assert step is None or step["arguments"].get("key") != "ctrl_l"


# ---------------------------------------------------------------- un formulario nunca es la barra de dirección


def _form(name: str, zone: str, value: str | None = None, send: bool = True) -> dict:
    field = {"i": 3, "kind": "Edit", "name": name, "state": "focused",
             "rect": {"x": 100, "y": 60 if zone == "T" else 400, "w": 1000, "h": 30}, "zone": zone}
    if value is not None:
        field["value"] = value
    controls = [field]
    if send:
        controls.append({"i": 4, "kind": "Button", "name": "Enviar", "rect": {"x": 100, "y": 450, "w": 100, "h": 30}, "zone": "M"})
    return {"window": {"title": "Contacto", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800},
                       "focused": {"kind": "Edit", "name": name, "nameSource": "", "value": value}},
            "controls": controls}


@pytest.mark.parametrize(("name", "zone", "value", "send"), [
    ("Dirección de correo electrónico", "M", None, True),    # the review's form, anywhere in the window
    ("Dirección de correo electrónico", "T", None, True),    # at the top too: the view has «Enviar»
    ("Dirección", "T", "Av. Libertad 123", False),           # a shipping address: it holds what the person wrote
    ("Dirección", "M", "C:\\Users", False),                  # a field showing a path, not at the top
])
def test_counter_case_a_form_field_named_address_is_no_address_bar(name: str, zone: str, value: str | None, send: bool) -> None:
    view = _form(name, zone, value, send)
    assert cu_address._address_field(view) is None
    step = cu_rules.deterministic_step(goal="ir a documentos\\informe", view=view, history=[])
    assert step is None or step["operation"] != "input.text.type"
    # Neither after the address bar's key: the keyboard is still on the person's field.
    after = cu_address._address_step("documentos\\informe", view, [_key(1, "ctrl_l")])
    assert after is None


def test_a_named_address_bar_at_the_top_showing_where_the_window_is_takes_the_path() -> None:
    view = _form("Barra de direcciones y de búsqueda", "T", "https://example.org/inicio", send=False)
    field = cu_address._address_field(view)
    assert field is not None and field["i"] == 3


# ---------------------------------------------------------------- ctrl_l nunca sobre el trabajo de la persona


def _notes(document: bool = False) -> dict:
    kind = "Document" if document else "Edit"
    return {"window": {"title": "notas.txt - Editor", "rect": {"x": 0, "y": 0, "w": 1200, "h": 800},
                       "focused": {"kind": kind, "name": "Notas", "nameSource": "", "value": "lo que escribí"}},
            "controls": [{"i": 1, "kind": kind, "name": "Notas", "state": "focused", "value": "lo que escribí",
                          "rect": {"x": 0, "y": 300, "w": 1200, "h": 400}, "zone": "M"}]}


@pytest.mark.parametrize("document", [False, True])
def test_counter_case_the_address_key_is_not_pressed_on_the_persons_text(document: bool) -> None:
    view = _notes(document)
    assert cu_address._address_step("c:\\windows\\system32", view, []) is None
    step = cu_rules.deterministic_step(goal=GOAL_EXPLORER, view=view, history=[])
    assert step is None or step["arguments"].get("key") != "ctrl_l"


def test_counter_case_after_the_key_a_field_that_is_no_address_gets_no_path() -> None:
    view = _notes()
    view["controls"][0]["state"] = ""
    view["window"]["focused"] = {"kind": "Edit", "name": "Notas", "nameSource": "", "value": "lo que escribí"}
    view["controls"] = []
    assert cu_address._address_step("c:\\windows\\system32", view, [_key(1, "ctrl_l")]) is None


# ---------------------------------------------------------------- carpetas conocidas


def test_known_folder_rooting_leaves_absolute_and_unknown_paths() -> None:
    assert known_folders.rooted("Documentos\\baxy-prueba-v3") == _path_7z()
    assert known_folders.rooted("c:\\windows\\system32") == "c:\\windows\\system32"
    assert known_folders.rooted("proyectos\\baxy") == "proyectos\\baxy"
