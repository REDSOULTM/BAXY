"""Goal v3 B3 (órdenes que viven en menús cerrados): el modelo tiene tres actos más sobre un control de la vista, todos
``input.visible.click`` con ``manner`` y por la identidad que dio la vista. «open» con índice abre sólo la flecha o la
lista del control (en un botón dividido, el clic hacía su Invoke y abría otra pestaña: v3-37), «menu» su menú
contextual (v3-40: dividir y renombrar viven en el menú de la pestaña) y «double» le da doble clic. Los atajos que la
propia UIA declara (AcceleratorKey/AccessKey) se ven junto a cada control, sin lista por aplicación. Gemelos con la
vista real de v3-38/v3-39 (Terminal) y contracasos de seguridad: un doble clic nunca ejecuta un programa ni quita algo
o cambia la cuenta sin que el objetivo lo pida, y una parte de la barra de desplazamiento nunca es un acto."""

from __future__ import annotations

import pytest

from baxy_mind import computer_use
from baxy_mind import cu_history
from baxy_mind import cu_evidence
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt
from baxy_mind import cu_projection

# The view of v3-38 (step 2, req 9), as the prompt showed it: Terminal with one PowerShell tab.
TERMINAL = {
    "window": {"title": "Windows PowerShell", "process": "WindowsTerminal", "focused": None,
               "rect": {"x": 0, "y": 0, "w": 1200, "h": 800}},
    "controls": [
        {"i": 0, "kind": "TabItem", "name": "Windows PowerShell", "state": "selected", "zone": "TL", "repeated": 1,
         "rect": {"x": 10, "y": 0, "w": 200, "h": 32}},
        {"i": 1, "kind": "Button", "name": "Cerrar pestaña", "zone": "TL", "repeated": 1},
        {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "collapsed", "zone": "T",
         "rect": {"x": 214, "y": 0, "w": 60, "h": 32}},
        {"i": 6, "kind": "MenuItem", "name": "Sistema", "state": "collapsed", "zone": "TL"},
        {"i": 7, "kind": "Button", "name": "Minimizar", "zone": "TR"},
        {"i": 8, "kind": "Button", "name": "Maximizar", "zone": "TR"},
        {"i": 9, "kind": "Button", "name": "Cerrar", "zone": "TR"},
        {"i": 10, "kind": "Text", "name": "Windows PowerShell", "zone": "TL", "repeated": 2},
        {"i": 11, "kind": "ScrollBar", "name": "Vertical", "value": "0", "zone": "R"},
        {"i": 12, "kind": "TitleBar", "name": "Windows PowerShell", "zone": "T"},
        {"i": 13, "kind": "MenuBar", "name": "Barra de menús del sistema", "zone": "TL"},
    ],
    "text": {"TL": ["PS C:\\Users\\usuario>"]},
}


def _checked(raw: dict, view: dict, goal: str, *, objective: str | None = None, last_failed: dict | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=last_failed, application_names=(), history=[], goal=goal, objective=objective,
    )


def test_the_grammar_the_prompt_and_the_repertoire_carry_the_three_acts() -> None:
    for act in ("menu", "double"):
        assert act in computer_use.ACTS
        assert f"{act} ::= " in cu_step_prompt.STEP_GRAMMAR
        assert f'"act":"{act}","i":N' in cu_step_prompt.STEP_PROMPT
    assert '"act":"open","i":N' in cu_step_prompt.STEP_PROMPT
    # «open» keeps opening an application by name, and also takes an index.
    assert '"\\"application\\""' in cu_step_prompt.STEP_GRAMMAR.split("open ::= ")[1].split("\n")[0]
    assert '"\\"i\\""' in cu_step_prompt.STEP_GRAMMAR.split("open ::= ")[1].split("\n")[0]


# v3-38 / v3-39: «ir a configuración» in Terminal. The order lives in the split button's list: its arrow is opened, never
# its action (the click on it stays refused, it would open another tab).
def test_twin_v3_38_the_split_buttons_arrow_is_opened_never_pressed() -> None:
    goal = "ir a configuracion"
    opened = _checked({"act": "open", "i": 2}, TERMINAL, goal)
    assert opened["operation"] == "input.visible.click"
    assert opened["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}
    pressed = _checked({"act": "click", "i": 2}, TERMINAL, goal)
    # Ronda 20b, palanca 6: the press its guard refuses is sent as the opening of its arrow, never its action.
    assert pressed["operation"] == "input.visible.click" and pressed["arguments"] == {"label": "Nueva pestaña", "index": 2, "manner": "open"}


# v3-40: «split the pane» and «renombra la tab a pruebas»: both live in the tab's context menu.
def test_twin_v3_40_the_tabs_context_menu_and_its_double_click() -> None:
    menu = _checked({"act": "menu", "i": 0}, TERMINAL, "dividir el panel en vertical")
    assert menu["operation"] == "input.visible.click"
    assert menu["arguments"] == {"label": "Windows PowerShell", "index": 0, "manner": "menu"}
    twice = _checked({"act": "double", "i": 0}, TERMINAL, "renombrar la pestana a pruebas")
    assert twice["arguments"] == {"label": "Windows PowerShell", "index": 0, "manner": "double"}


def test_open_is_only_for_what_has_an_arrow_or_a_list() -> None:
    refused = _checked({"act": "open", "i": 7}, TERMINAL, "ir a configuracion")
    assert refused["operation"] == "none" and refused["code"] == "cannot_open"
    assert "cannot_open" in computer_use._RETRIED
    missing = _checked({"act": "menu", "i": 40}, TERMINAL, "ir a configuracion")
    assert missing["operation"] == "none" and missing["code"] == "label_not_visible"


# A click that failed on the split button does not forbid opening its arrow: another act on the same control.
def test_a_failed_click_does_not_forbid_opening_the_same_control() -> None:
    failed = {"operation": "input.visible.click", "label": "Nueva pestaña", "index": 2, "ok": False}
    opened = _checked({"act": "open", "i": 2}, TERMINAL, "ir a configuracion", last_failed=failed)
    assert opened["operation"] == "input.visible.click" and opened["arguments"]["manner"] == "open"
    again = {"operation": "input.visible.click", "label": "Nueva pestaña", "index": 2, "manner": "open", "ok": False}
    repeated = _checked({"act": "open", "i": 2}, TERMINAL, "ir a configuracion", last_failed=again)
    assert repeated["operation"] == "none"


# ------------------------------------------------------------------------------------------- safety counter-cases

FILES = {
    "window": {"title": "Descargas", "process": "explorer", "focused": None, "rect": {"x": 0, "y": 0, "w": 1000, "h": 700}},
    "controls": [
        {"i": 0, "kind": "ListItem", "name": "setup.exe", "itemType": "Aplicación", "rect": {"x": 10, "y": 100, "w": 300, "h": 20}},
        {"i": 1, "kind": "ListItem", "name": "Fotos", "itemType": "Carpeta de archivos", "rect": {"x": 10, "y": 120, "w": 300, "h": 20}},
        {"i": 2, "kind": "Button", "name": "Eliminar", "rect": {"x": 400, "y": 10, "w": 60, "h": 20}},
        {"i": 3, "kind": "Button", "name": "Seguir", "rect": {"x": 470, "y": 10, "w": 60, "h": 20}},
        {"i": 4, "kind": "ListItem", "name": "informe.docx", "rect": {"x": 10, "y": 140, "w": 300, "h": 20}},
        {"i": 5, "kind": "Button", "name": "Línea arriba", "rect": {"x": 980, "y": 60, "w": 16, "h": 16}},
        {"i": 6, "kind": "ScrollBar", "name": "Vertical", "rect": {"x": 980, "y": 60, "w": 16, "h": 600}},
    ],
    "text": {},
}


@pytest.mark.parametrize(
    ("index", "code"),
    [
        (0, "runs_when_opened"),       # a program runs when opened
        (2, "removes_unasked"),        # removes, and the goal does not ask for it
        (3, "changes_the_account"),    # follows someone in the person's account
    ],
)
def test_a_double_click_never_runs_removes_or_changes_the_account_unasked(index: int, code: str) -> None:
    refused = _checked({"act": "double", "i": index}, FILES, "ir a fotos")
    assert refused["operation"] == "none"
    assert refused["code"] == code


def test_a_double_click_opens_a_folder_or_a_document() -> None:
    folder = _checked({"act": "double", "i": 1}, FILES, "ir a fotos")
    assert folder["arguments"] == {"label": "Fotos", "index": 1, "manner": "double"}
    document = _checked({"act": "double", "i": 4}, FILES, "abrir informe.docx")
    assert document["arguments"]["manner"] == "double"


def test_a_scroll_bars_part_is_never_opened_nor_double_clicked() -> None:
    for act in ("menu", "double"):
        refused = _checked({"act": act, "i": 5}, FILES, "ir a fotos")
        assert refused["operation"] == "none" and refused["code"] == "scroll_part"


# A context menu presses nothing: what is chosen in it is a click, checked as one (the Kernel asks before a removal).
def test_the_context_menu_of_an_item_opens_but_its_removal_is_a_checked_click() -> None:
    menu = _checked({"act": "menu", "i": 4}, FILES, "eliminar informe.docx")
    assert menu["arguments"] == {"label": "informe.docx", "index": 4, "manner": "menu"}


# ------------------------------------------------------------------------------------------------ the shortcuts

def test_the_view_shows_the_shortcut_the_application_declares() -> None:
    view = {
        "window": {"title": "Configuración", "process": "WindowsTerminal"},
        "controls": [
            {"i": 0, "kind": "MenuItem", "name": "Configuración", "shortcut": "Ctrl+,"},
            {"i": 1, "kind": "MenuItem", "name": "Paleta de comandos", "shortcut": "Ctrl+Mayús+P"},
            {"i": 2, "kind": "MenuItem", "name": "Acerca de"},
        ],
        "text": {},
    }
    text = cu_step_prompt.compact_view_text(view, goal="ir a configuracion")
    assert "0 · MenuItem · «Configuración» · atajo=Ctrl+," in text
    assert "1 · MenuItem · «Paleta de comandos» · atajo=Ctrl+Mayús+P" in text
    assert "2 · MenuItem · «Acerca de»" in text and "«Acerca de» · atajo" not in text
    assert "atajo=" in cu_step_prompt.STEP_PROMPT


def test_the_final_says_the_act_as_it_was() -> None:
    step = {"operation": "input.visible.click", "label": "Nueva pestaña", "manner": "open"}
    assert cu_projection.describe_step(step, "es") == "abrió «Nueva pestaña»"
    assert cu_projection.describe_step({**step, "manner": "menu"}, "en") == "opened the menu of «Nueva pestaña»"
    assert cu_projection.describe_step({**step, "manner": None}, "es") == "clic en «Nueva pestaña»"


# ------------------------------------------------------------------------- review of fable/cu-v3-menus-actos (B3)

FORM = {
    "window": {"title": "Pedido", "process": "app", "focused": None, "rect": {"x": 0, "y": 0, "w": 1000, "h": 700}},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Siguiente", "rect": {"x": 10, "y": 10, "w": 80, "h": 24}},
        {"i": 1, "kind": "Button", "name": "Agregar al carrito", "rect": {"x": 100, "y": 10, "w": 120, "h": 24}},
        {"i": 2, "kind": "Hyperlink", "name": "Ver términos", "rect": {"x": 230, "y": 10, "w": 90, "h": 24}},
        {"i": 3, "kind": "Button", "name": "Enviar", "rect": {"x": 330, "y": 10, "w": 60, "h": 24}},
        {"i": 4, "kind": "MenuItem", "name": "Archivo", "state": "collapsed", "rect": {"x": 0, "y": 0, "w": 50, "h": 20}},
        {"i": 5, "kind": "SplitButton", "name": "Pegar", "state": "collapsed", "rect": {"x": 400, "y": 10, "w": 60, "h": 24}},
        {"i": 6, "kind": "Text", "name": "Ver más", "rect": {"x": 500, "y": 10, "w": 90, "h": 24}},
    ],
    "text": {},
}


# Finding 2: a double click on a button, a link, a menu's item, a split button or a written text is two activations
# («Enviar» sent twice under one confirmation); only an item, a tab or a document takes it.
@pytest.mark.parametrize("index", [0, 1, 2, 3, 4, 5, 6])
def test_a_double_click_is_never_two_activations_of_a_button_a_link_or_a_text(index: int) -> None:
    refused = _checked({"act": "double", "i": index}, FORM, "ir a opciones")
    assert refused["operation"] == "none"
    assert refused["code"] == "cannot_double"
    assert "cannot_double" in computer_use._RETRIED


# Finding 3: the App now sends «manner» in the history (HistoryForMind); the repetition guard reads it as sent.
def test_the_repeat_guard_tells_an_opening_from_a_click_as_the_app_sends_them() -> None:
    menu_failed = {"step": 3, "operation": "input.visible.click", "label": "Archivo", "index": 4, "manner": "menu", "ok": False}
    again = _checked({"act": "menu", "i": 4}, FORM, "ir a opciones", last_failed=menu_failed)
    assert again["operation"] == "none" and again["code"] == "repeated_step"
    open_failed = {"step": 3, "operation": "input.visible.click", "label": "Archivo", "index": 4, "manner": "open", "ok": False}
    clicked = _checked({"act": "click", "i": 4}, FORM, "ir a opciones", last_failed=open_failed)
    assert clicked.get("code") != "repeated_step"
    assert clicked["operation"] == "input.visible.click" and "manner" not in clicked["arguments"]
    # The model reads the opening as an opening, never as a press.
    assert "manner=open" in cu_step_prompt._history_line({**open_failed, "ok": True})


# Finding 4 (twin of the App's checks): opening an arrow or a menu is no act done on the control.
def test_an_opened_arrow_or_menu_is_no_act_with_effect_nor_a_click_on_it() -> None:
    opened = {"step": 2, "operation": "input.visible.click", "label": "Nueva pestaña", "manner": "open", "ok": True,
              "changed": True}
    assert cu_history.only_opened(opened)
    assert not cu_history.only_opened({**opened, "manner": "double"})
    assert not cu_evidence.acted_with_effect([opened], "hacer clic en nueva pestaña")
    assert not cu_evidence.acted_with_effect([{**opened, "manner": "menu"}], "hacer clic en nueva pestaña")
    pressed = {k: v for k, v in opened.items() if k != "manner"}
    assert cu_evidence.acted_with_effect([pressed], "hacer clic en nueva pestaña")
    assert cu_history._clicks_on([opened], "Nueva pestaña") == []
    assert cu_history._clicks_on([pressed], "Nueva pestaña") == [pressed]
