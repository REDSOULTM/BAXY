"""Menús y teclas de regla (goal v3, pasada r9: t-menu-3, t-long-4, v3-52).

Gemelos sobre las vistas reales del journal (tests/data/cu_menus_teclas_vistas.json) y sus contracasos:

- una ventana con barra de menús sin abrir no recibe atajos a ciegas al buscar un lugar: el paso es del modelo, que ve
  los menús (t-menu-3: «view» era «Ver» y ctrl_k abrió «Vínculo»); una búsqueda pedida sigue usando su atajo;
- si el Escape dejó abierto lo que el atajo trajo, se pulsa su «Cancelar»;
- un atajo que trajo algo no buscado queda gastado para el resto de la misión en esa aplicación;
- un atajo que sólo llevó el teclado al marco de la ventana no trajo nada: sin Escape, que cerraría el diálogo (v3-52);
- un botón de filtros no es la búsqueda de la ventana (v3-52: «Abrir filtros de la escena»).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from baxy_mind.semantic.missions import fold as missions_fold
from baxy_mind import computer_use
from baxy_mind import cu_fields
from baxy_mind import cu_acts
from baxy_mind import cu_history
from baxy_mind import cu_menus
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate

_DATA = Path(__file__).parent / "data" / "cu_menus_teclas_vistas.json"
_VIEWS = {(entry["case"], entry["view"]): entry for entry in json.loads(_DATA.read_text(encoding="utf-8"))}


def _view(case: str, which: str) -> dict:
    entry = copy.deepcopy(_VIEWS[(case, which)])
    return {"window": entry["window"], "controls": entry["controls"], "text": entry["text"]}


def _key(number: int, key: str, *, same: bool | None = None) -> dict:
    step = {"step": number, "operation": "input.key.press", "key": key, "ok": True}
    if same is not None:
        step["sameView"] = same
    return step


_NOT_FOUND = {"step": 1, "operation": "input.visible.click", "label": "view", "ok": False, "error": "visible_button_not_found"}


def _without_menus(view: dict) -> dict:
    view["controls"] = [control for control in view["controls"] if control.get("kind") != "MenuItem"]
    return view


def test_t_menu_3_a_menu_bar_takes_the_place_of_blind_shortcuts() -> None:
    view = _view("t-menu-3", "antes")
    # The goal's name was not found: with «Archivo · Editar · Ver» unopened the step is the model's, never ctrl_k.
    assert cu_rules.deterministic_step(goal="hacer clic en view", view=view, history=[_NOT_FOUND]) is None
    # Contracase: the same window without its menu bar still tries the window's shortcut; ronda 21: over the editor's
    # document only the find (ctrl_f), never ctrl_k, which inserts a link there.
    bare = _without_menus(_view("t-menu-3", "antes"))
    step = cu_rules.deterministic_step(goal="hacer clic en view", view=bare, history=[_NOT_FOUND])
    assert step is not None and step["arguments"] == {"key": "ctrl_f"}
    # Contracase: a search the person asks for keeps the window's find, menus or not.
    searched = cu_rules.deterministic_step(goal="buscar hola", view=_view("t-menu-3", "antes"), history=[])
    assert searched is not None and searched["operation"] == "input.key.press"
    assert searched["arguments"]["key"] in {"ctrl_k", "ctrl_f"}


def test_menus_already_opened_in_the_subgoal_no_longer_hold_the_shortcuts() -> None:
    view = _view("t-menu-3", "antes")
    opened = [
        {"step": number, "operation": "input.visible.click", "label": name, "ok": True}
        for number, name in enumerate(("Archivo", "Editar", "Ver"), start=2)
    ]
    step = cu_lookup._find_step("view", view, [_NOT_FOUND, *opened])
    # Ronda 21: the shortcut over the editor's document is its find, never ctrl_k.
    assert step is not None and step["arguments"] == {"key": "ctrl_f"}


def _appeared(before: dict, after: dict) -> list[str]:
    """What the shell writes on a key's step (``MarkAppeared``): the folded names of the look after it that no control
    of the look before it had."""

    known = {missions_fold(control.get("name")) for control in before["controls"] if control.get("name")}
    names: list[str] = []
    for control in after["controls"]:
        name = missions_fold(control.get("name"))
        if name and name not in known:
            known.add(name)
            names.append(name)
    return names


def _ruled_key(number: int, key: str, *, same: bool | None = None, appeared: list[str] | None = None) -> dict:
    """A key the mind's routine pressed, as the shell records it (``rule``, ``appeared``)."""

    step = {**_key(number, key, same=same), "rule": True, "process": "Notepad"}
    if appeared is not None:
        step["appeared"] = appeared
    return step


def _menu_3_history(*, escape_by_rule: bool = True) -> list[dict]:
    appeared = _appeared(_view("t-menu-3", "antes"), _view("t-menu-3", "tras ctrl_k"))
    escape = _ruled_key(2, "escape", same=True, appeared=[]) if escape_by_rule else _key(2, "escape", same=True)
    return [_ruled_key(1, "ctrl_k", same=False, appeared=appeared), escape]


def test_t_menu_3_an_escape_that_left_the_link_dialog_open_presses_its_cancel() -> None:
    # Live r9: ctrl_k opened «Vínculo», Escape kept the view as it was (journal sequence 944) and ctrl_f followed onto
    # the dialog. The Cancel came with the key: the look before it (sequence 936) had none.
    view = _view("t-menu-3", "tras Escape")
    assert "cancelar" in _menu_3_history()[0]["appeared"]
    step = cu_lookup._find_step("view", view, _menu_3_history())
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": "Cancelar", "index": 2}
    # Right after the key the dialog's empty field is closed with Escape (never typed into).
    assert cu_lookup._find_step("view", _view("t-menu-3", "tras ctrl_k"), [_key(1, "ctrl_k")]) == cu_acts._key("escape")


def test_contracase_an_escape_that_changed_the_view_or_two_cancels_press_nothing() -> None:
    view = _view("t-menu-3", "tras Escape")
    key, _ = _menu_3_history()
    changed = cu_lookup._find_step("view", view, [key, _ruled_key(2, "escape", same=False, appeared=[])])
    assert changed is None or changed.get("arguments", {}).get("label") != "Cancelar"
    twice = _view("t-menu-3", "tras Escape")
    twice["controls"].append({"i": 99, "kind": "Button", "name": "Cancelar", "rect": {"x": 600, "y": 700, "w": 170, "h": 39}})
    doubt = cu_lookup._find_step("view", twice, _menu_3_history())
    assert doubt is None or doubt.get("arguments", {}).get("label") != "Cancelar"


def test_a_key_spent_by_an_earlier_subgoal_is_not_pressed_again_on_that_application() -> None:
    # Ronda 21: the window without its editor's document, whose blind shortcut would be ctrl_f alone whatever was spent.
    bare = _without_menus(_view("t-menu-3", "antes"))
    bare["controls"] = [control for control in bare["controls"] if control.get("kind") != "Document"]
    spent = {"step": 2, "operation": "input.key.press", "key": "ctrl_k", "ok": True, "spent": True, "process": "Notepad"}
    own, keys = cu_history.spent_steps([spent, _NOT_FOUND])
    assert own == [_NOT_FOUND] and keys == (("ctrl_k", "notepad"),)
    token = cu_history._SPENT_KEYS.set(keys)
    try:
        step = cu_lookup._find_step("view", bare, [_NOT_FOUND])
    finally:
        cu_history._SPENT_KEYS.reset(token)
    assert step is not None and step["arguments"] == {"key": "ctrl_f"}
    # Contracase: a key spent on another application is still this one's way.
    token = cu_history._SPENT_KEYS.set((("ctrl_k", "obs64"),))
    try:
        other = cu_lookup._find_step("view", bare, [_NOT_FOUND])
    finally:
        cu_history._SPENT_KEYS.reset(token)
    assert other is not None and other["arguments"] == {"key": "ctrl_k"}


def test_spent_keys_never_count_as_the_subgoals_own_steps() -> None:
    # The first look of a sub-goal has no history of its own: the spent key does not make it look like a step was done
    # (the application is still opened when it is not in front).
    spent = {"step": 2, "operation": "input.key.press", "key": "ctrl_k", "ok": True, "spent": True, "process": "Notepad"}
    view = {"window": {"title": "Escritorio", "process": "explorer"}, "controls": [], "text": {}}
    step = computer_use.decide_step(
        None, objective="en el bloc de notas zoom", goal="hacer clic en view", application="Bloc de notas",
        success_check=None, view=view, history=[spent], budget_left=10, application_names=("Bloc de notas",),
    )
    assert step["operation"] == "app.open"


def test_v3_52_a_key_that_only_focused_the_frame_brings_no_escape() -> None:
    # Live r9: ctrl_k on OBS's «Ajustes» focused «Barra de menús del sistema»; the Escape after it closed the dialog.
    view = _view("v3-52", "Ajustes tras ctrl_k")
    failed = {"step": 3, "operation": "input.visible.click", "label": "Vídeo", "index": 7, "ok": False,
              "error": "visible_button_postread_unchanged"}
    step = cu_lookup._find_step("video", view, [failed, _key(4, "ctrl_k")])
    assert step != cu_acts._key("escape")
    # Contracase: a key that put the keyboard on a field it brought up still closes it.
    field = _view("v3-52", "Ajustes tras ctrl_k")
    field["window"]["focused"] = {"kind": "Edit", "name": "Texto para mostrar", "value": ""}
    field["controls"].append({"i": 60, "kind": "Edit", "name": "Texto para mostrar", "state": "focused", "value": ""})
    assert cu_lookup._find_step("video", field, [failed, _key(4, "ctrl_k")]) == cu_acts._key("escape")


def test_v3_52_a_filters_button_is_no_search() -> None:
    view = _view("v3-52", "principal")
    assert any(control.get("name") == "Abrir filtros de la escena" for control in view["controls"])
    assert cu_lookup._search_affordance(view, []) is None
    # Contracases: a box that filters is a search, and a button that says it searches is one even with filters in it.
    assert cu_fields._is_search_field({"kind": "Edit", "name": "Filtrar"})
    assert cu_fields._is_search_field({"kind": "Button", "name": "Buscar filtros"})
    assert cu_fields._is_search_field({"name": "Filtrar"})
    assert not cu_fields._is_search_field({"kind": "Button", "name": "Abrir filtros de la escena"})


# Review of fable/cu-v3-menus-teclas (head d5fb863cc): its findings, on real views and their contracases.

_SEMEJANZA = Path(__file__).parent / "data" / "cu_semejanza_vistas.json"


def _semejanza(title: str) -> dict:
    entry = next(entry for entry in json.loads(_SEMEJANZA.read_text(encoding="utf-8")) if entry["window"].get("title") == title)
    return {"window": copy.deepcopy(entry["window"]), "controls": copy.deepcopy(entry["controls"])}


def _without_the_hold(goal: str, view: dict, history: list[dict]) -> dict | None:
    token = cu_menus._MENU_BAR_HOLDS.set(False)
    try:
        return cu_rules.deterministic_step(goal=goal, view=view, history=history)
    finally:
        cu_menus._MENU_BAR_HOLDS.reset(token)


def test_finding_1_a_system_menu_or_an_account_without_a_rectangle_is_no_menu_bar() -> None:
    # Six real windows whose menus come with no rectangle (the system menu «Sistema», Office's account, Paint's and
    # Notepad's menus as cu_semejanza_vistas froze them): the routine's way is the same as with no hold at all, ctrl_k,
    # as before the branch.
    for title in ("Seguridad de Windows", "PowerPoint", "Windows PowerShell", "Ajustes", "Sin título - Paint",
                  "*hello world: Bloc de notas"):
        view = _semejanza(title)
        assert cu_menus._menu_bar(view) == [], title
        step = cu_rules.deterministic_step(goal="ir a zzqx", view=view, history=[])
        assert step == _without_the_hold("ir a zzqx", view, []), title
        # Ronda 21: Notepad's view shows its editor's document, where the blind shortcut is the find, never ctrl_k.
        expected = "ctrl_f" if title.endswith("Bloc de notas") else "ctrl_k"
        assert step is not None and step["arguments"] == {"key": expected}, title
    # Every frozen view of that file: the hold changes no step.
    for entry in json.loads(_SEMEJANZA.read_text(encoding="utf-8")):
        view = {"window": entry["window"], "controls": entry["controls"]}
        assert cu_rules.deterministic_step(goal="ir a zzqx", view=view, history=[]) == _without_the_hold("ir a zzqx", view, [])


def test_finding_1_the_real_menu_bars_are_rows_and_the_system_menu_is_left_out() -> None:
    notepad = cu_menus._menu_bar(_view("t-menu-3", "antes"))
    assert [control["name"] for control in notepad] == ["Archivo", "Editar", "Ver"]
    obs = cu_menus._menu_bar(_view("v3-52", "principal"))
    assert len(obs) == 8 and "Sistema" not in {control["name"] for control in obs}
    # OBS's «Ajustes» has only its system menu, drawn in the title bar: no bar, its shortcut is tried.
    assert cu_menus._menu_bar(_view("v3-52", "Ajustes")) == []
    # Contracase: one collapsed MenuItem alone in its row (an account, a lone «Más opciones») is no bar.
    lone = _view("t-menu-3", "antes")
    lone["controls"] = [control for control in lone["controls"] if control.get("name") not in {"Archivo", "Editar"}]
    assert cu_menus._menu_bar(lone) == []


def test_finding_1_minor_two_menus_opened_give_the_routine_its_ways_back() -> None:
    view = _view("v3-52", "principal")
    assert cu_rules.deterministic_step(goal="ir a zzqx", view=view, history=[]) is None
    opened = [{"step": n, "operation": "input.visible.click", "label": name, "ok": True}
              for n, name in enumerate(("Archivo (F)", "Vista"), start=1)]
    step = cu_rules.deterministic_step(goal="ir a zzqx", view=view, history=opened)
    assert step is not None and step["operation"] in {"input.key.press", "input.scroll"}
    # Contracase: one menu opened still leaves the step to the model.
    assert cu_rules.deterministic_step(goal="ir a zzqx", view=view, history=opened[:1]) is None


class _NoneModel:
    """A model that takes no step (``{"act": "none"}``) on every call."""

    def __init__(self) -> None:
        self.calls = 0

    def _post_schema_object(self, payload: dict, what: str) -> dict:
        self.calls += 1
        return {"act": "none", "why": "no veo cómo"}


def test_finding_1_a_model_that_takes_none_of_the_menus_falls_back_to_the_shortcut() -> None:
    model = _NoneModel()
    step = computer_use.decide_step(
        model, objective="en el bloc de notas andá a view", goal="hacer clic en view", application="Bloc de notas",
        success_check=None, view=_view("t-menu-3", "antes"), history=[_NOT_FOUND], budget_left=10,
        application_names=("Bloc de notas",),
    )
    assert model.calls >= 1
    # Ronda 21: over the editor's document the routine's shortcut is the find, never ctrl_k.
    assert step["operation"] == "input.key.press" and step["arguments"] == {"key": "ctrl_f"}
    # Contracase: a window with no bar: the rule's step, the model never asked.
    asked = _NoneModel()
    bare = computer_use.decide_step(
        asked, objective="en el bloc de notas andá a view", goal="hacer clic en view", application="Bloc de notas",
        success_check=None, view=_without_menus(_view("t-menu-3", "antes")), history=[_NOT_FOUND], budget_left=10,
        application_names=("Bloc de notas",),
    )
    assert asked.calls == 0 and bare["arguments"] == {"key": "ctrl_f"}


_COPYING = {
    "window": {"title": "Copiando 3 elementos", "process": "explorer", "focused": None},
    "controls": [
        {"i": 0, "kind": "Text", "name": "Copiando 3 elementos de Documentos a Descargas",
         "rect": {"x": 20, "y": 60, "w": 400, "h": 24}},
        {"i": 1, "kind": "ProgressBar", "name": "Progreso", "rect": {"x": 20, "y": 100, "w": 400, "h": 16}},
        {"i": 2, "kind": "Button", "name": "Cancelar", "rect": {"x": 330, "y": 140, "w": 90, "h": 30}},
    ],
}
_FORM = {
    "window": {"title": "Editar perfil", "process": "msedge", "focused": None},
    "controls": [
        {"i": 0, "kind": "Edit", "name": "Nombre", "value": "Ana editado", "rect": {"x": 40, "y": 120, "w": 300, "h": 32}},
        {"i": 1, "kind": "Button", "name": "Guardar", "rect": {"x": 40, "y": 200, "w": 100, "h": 32}},
        {"i": 2, "kind": "Button", "name": "Cancelar", "rect": {"x": 160, "y": 200, "w": 100, "h": 32}},
    ],
}


def _not_cancel(step: dict | None) -> bool:
    return step is None or step.get("arguments", {}).get("label") != "Cancelar"


def test_finding_2_a_cancel_the_window_already_showed_is_never_pressed() -> None:
    # The review's history: a key that changed nothing and an Escape nobody says the routine pressed.
    loose = [_key(1, "ctrl_f", same=True), _key(2, "escape", same=True)]
    ruled = [_ruled_key(1, "ctrl_f", same=False, appeared=["buscar"]), _ruled_key(2, "escape", same=True, appeared=[])]
    for view, goal, target in ((_COPYING, "ir a descargas", "descargas"), (_FORM, "ir a ajustes", "ajustes")):
        assert _not_cancel(cu_lookup._find_step(target, copy.deepcopy(view), loose)), goal
        assert _not_cancel(cu_rules.deterministic_step(goal=goal, view=copy.deepcopy(view), history=loose)), goal
        # Even after the routine's own Escape on a key that changed the view: the Cancel did not come with the key.
        assert _not_cancel(cu_lookup._find_step(target, copy.deepcopy(view), ruled)), goal
    # Real: OBS's «Ajustes» shows its own «Cancelar» (journal 670 → 674); ctrl_k made nothing appear.
    history = [_ruled_key(1, "ctrl_k", same=False, appeared=[]), _ruled_key(2, "escape", same=True, appeared=[])]
    assert _not_cancel(cu_lookup._find_step("video", _view("v3-52", "Ajustes tras ctrl_k"), history))


def test_finding_2_the_model_s_escape_or_a_key_without_effect_presses_no_cancel() -> None:
    view = _view("t-menu-3", "tras Escape")
    assert _not_cancel(cu_lookup._find_step("view", view, _menu_3_history(escape_by_rule=False)))
    key, escape = _menu_3_history()
    assert _not_cancel(cu_lookup._find_step("view", view, [{**key, "sameView": True}, escape]))
    # A shell that did not say what appeared: nothing is pressed by guess.
    unknown = {name: value for name, value in key.items() if name != "appeared"}
    assert _not_cancel(cu_lookup._find_step("view", view, [unknown, escape]))


def test_finding_3_the_model_cannot_press_a_spent_key_either() -> None:
    view = _view("t-menu-3", "antes")

    def judged(key: str, spent: tuple[tuple[str, str], ...]) -> dict:
        token = cu_history._SPENT_KEYS.set(spent)
        try:
            return cu_validate.validate_decision(
                {"act": "key", "key": key, "why": "busco"}, view=view, last_failed=None, application_names=(),
                history=[_NOT_FOUND], goal="hacer clic en view",
            )
        finally:
            cu_history._SPENT_KEYS.reset(token)

    refused = judged("ctrl_k", (("ctrl_k", "notepad"),))
    assert refused["operation"] == "none" and refused["code"] == "key_spent"
    assert "key_spent" in computer_use._RETRIED
    other = judged("ctrl_f", (("ctrl_k", "notepad"),))
    assert other["operation"] == "input.key.press" and other["arguments"]["key"] == "ctrl_f"
    # Contracase: spent on another application, the key is the model's.
    allowed = judged("ctrl_k", (("ctrl_k", "obs64"),))
    assert allowed["operation"] == "input.key.press" and allowed["arguments"]["key"] == "ctrl_k"


def test_finding_4_a_key_that_brought_a_window_up_is_closed_even_with_its_title_bar_focused() -> None:
    failed = {"step": 3, "operation": "input.visible.click", "label": "Vídeo", "index": 7, "ok": False,
              "error": "visible_button_postread_unchanged"}
    view = _view("v3-52", "Ajustes tras ctrl_k")
    # Measured: nothing appeared, the keyboard on the frame: no Escape.
    frame = cu_lookup._find_step("video", view, [failed, _ruled_key(4, "ctrl_k", same=False, appeared=[])])
    assert frame != cu_acts._key("escape")
    # A key whose look brought new controls and left their window's title bar focused: that window is closed.
    opened = _view("v3-52", "Ajustes tras ctrl_k")
    opened["window"]["focused"] = {"kind": "TitleBar", "name": "Insertar vínculo", "i": 60}
    opened["controls"].append({"i": 60, "kind": "TitleBar", "name": "Insertar vínculo", "state": "focused",
                               "rect": {"x": 300, "y": 300, "w": 500, "h": 29}})
    history = [failed, _ruled_key(4, "ctrl_k", same=False, appeared=["insertar vinculo"])]
    assert cu_lookup._find_step("video", opened, history) == cu_acts._key("escape")


def test_finding_5_a_verb_that_filters_is_a_search_and_a_frame_is_no_tree() -> None:
    # A button «Filtrar» (the verb) opens a filter box: a search; the filters as a thing are not.
    assert cu_fields._is_search_field({"kind": "Button", "name": "Filtrar"})
    assert cu_fields._is_search_field({"kind": "ListItem", "name": "Filter"})
    assert not cu_fields._is_search_field({"kind": "Button", "name": "Filtros"})
    # A window drawn without a tree lists only its frame: its written «Filtrar…» is its search box.
    frame_only = {
        "window": {"title": "Notas", "process": "notas", "focused": None},
        "controls": [{"i": 0, "kind": "Button", "name": "Minimizar"}, {"i": 1, "kind": "Button", "name": "Cerrar"},
                     {"i": 2, "kind": "TitleBar", "name": "Notas"}],
        "text": {"TL": ["Notas", "Filtrar…"]},
    }
    assert not cu_lookup._exposes_a_tree(frame_only)
    assert cu_lookup._search_affordance(frame_only, []) == {"name": "Filtrar…"}
    # Contracase: OBS exposes its tree, and a written «Filtros» there is a panel's title, never its search.
    obs = _view("v3-52", "principal")
    assert cu_lookup._exposes_a_tree(obs)
    obs["text"] = {"BL": ["Filtros"]}
    assert cu_lookup._search_affordance(obs, []) is None


def test_finding_6_the_frozen_views_are_whole_and_say_where_they_come_from() -> None:
    for (case, which), entry in _VIEWS.items():
        source = entry["source"]
        assert source["journal"].endswith("journal/missions.jsonl") and source["operation"] == "input.visible.controls"
        assert len(source["lineSha256"]) == 64 and source["sequence"] > 0, (case, which)
        assert [control["i"] for control in entry["controls"]] == list(range(len(entry["controls"]))), (case, which)
        focused = entry["window"].get("focused")
        if isinstance(focused, dict) and isinstance(focused.get("i"), int):
            assert focused["i"] < len(entry["controls"]), (case, which)
