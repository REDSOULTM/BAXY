"""Deterministic steps of computer use (cu-z-mind): the navigation item among two names, Enter only on a folder,
the failed-click retry, Enter after typing where the focus cannot be read, the menu's default entry and switches."""

from baxy_mind import cu_goals
from baxy_mind import cu_fields
from baxy_mind import cu_navigation
from baxy_mind import cu_menus
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate


def _ok(step: int, operation: str, **fields: object) -> dict:
    return {"step": step, "operation": operation, "ok": True, **fields}


def _rect(x: int, y: int, w: int, h: int) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


# ------------------------------------------------------------------ 1. the single navigation item among two names

def test_two_controls_named_like_the_place_go_to_the_single_navigation_item() -> None:
    # Explorer: «Descargas» is the side list's item and a tile of the Home view.
    explorer = {
        "window": {"title": "Inicio - Explorador de archivos", "process": "explorer", "focused": None},
        "controls": [
            {"i": 0, "kind": "TreeItem", "name": "Descargas", "zone": "L", "rect": _rect(10, 300, 160, 30)},
            {"i": 1, "kind": "ListItem", "name": "Descargas", "zone": "C", "rect": _rect(500, 200, 120, 100)},
            {"i": 2, "kind": "Edit", "name": "Buscar en Inicio", "zone": "TR"},
        ],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="ir a descargas", view=explorer, history=[])
    assert step is not None and step["arguments"] == {"label": "Descargas", "index": 0}
    # Discord: the server in the left column, not the activity card.
    discord = {
        "window": {"title": "Amigos - Discord", "process": "Discord", "focused": None},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Buscar o iniciar una conversación", "zone": "TL"},
            {"i": 3, "kind": "TreeItem", "name": "Cotele", "zone": "L"},
            {"i": 7, "kind": "ListItem", "name": "Cotele (jugando)", "zone": "R"},
        ],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="ir a cotele", view=discord, history=[])
    assert step is not None and step["arguments"] == {"label": "Cotele", "index": 3}


def test_without_a_single_navigation_item_the_place_is_still_looked_up() -> None:
    discord = {
        "window": {"title": "Amigos - Discord", "process": "Discord", "focused": None},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Buscar o iniciar una conversación", "zone": "TL"},
            {"i": 3, "kind": "TreeItem", "name": "Cotele", "zone": "L"},
            {"i": 4, "kind": "ListItem", "name": "Cotele", "zone": "BL"},
            {"i": 7, "kind": "ListItem", "name": "Cotele", "zone": "R"},
        ],
        "text": {},
    }
    step = cu_rules.deterministic_step(goal="ir a cotele", view=discord, history=[])
    assert step is not None and step["arguments"].get("label") == "Buscar o iniciar una conversación"
    # The navigation item already clicked and the place not reached: looked up, never clicked again.
    single = {**discord, "controls": [discord["controls"][0], discord["controls"][1], discord["controls"][3]]}
    clicked = [_ok(1, "input.visible.click", label="Cotele", index=3)]
    step = cu_rules.deterministic_step(goal="ir a cotele", view=single, history=clicked)
    assert step is None or step["arguments"].get("index") != 3


# ------------------------------------------------------------------ 2. Enter only on a folder or a drive

def _chosen(item: dict, *, extra: list[dict] | None = None) -> dict:
    return {
        "window": {"title": "Inicio - Explorador de archivos", "process": "explorer", "focused": None},
        "controls": [
            {"i": 0, "kind": "ListItem", "state": "selected", "zone": "C", "rect": _rect(400, 300, 300, 24), **item},
            *(extra or []),
        ],
        "text": {},
    }


def test_enter_on_a_chosen_item_only_with_evidence_it_is_a_folder() -> None:
    clicked = [_ok(1, "input.visible.click", label="Hades", index=0)]
    for item_type in ("Carpeta de archivos", "File folder", "Unidad local", "CD Drive"):
        step = cu_rules.deterministic_step(goal="ir a hades", view=_chosen({"name": "Hades", "itemType": item_type}), history=clicked)
        assert step is not None and step["arguments"] == {"key": "enter"}, item_type
    # An application, a shortcut or an item of unknown type: nothing tells it from something that starts.
    for item in ({"name": "Hades", "itemType": "Aplicación"}, {"name": "Hades", "itemType": "Acceso directo"},
                 {"name": "Hades"}):
        assert cu_rules.deterministic_step(goal="ir a hades", view=_chosen(item), history=clicked) is None, item
    # The type cell of its row in a details view says folder.
    cell = [{"i": 1, "kind": "Edit", "name": "Tipo", "value": "Carpeta de archivos", "rect": _rect(800, 302, 120, 20)}]
    # A details-view row spans the whole width: its type cell lies inside the item.
    step = cu_rules.deterministic_step(goal="ir a hades", view=_chosen({"name": "Hades", "rect": _rect(100, 300, 900, 24)}, extra=cell), history=clicked)
    assert step is not None and step["arguments"] == {"key": "enter"}
    # A cell of another row says nothing of this item.
    other_row = [{"i": 1, "kind": "Text", "name": "File folder", "rect": _rect(800, 360, 120, 20)}]
    assert cu_rules.deterministic_step(goal="ir a hades", view=_chosen({"name": "Hades"}, extra=other_row), history=clicked) is None


def test_files_that_run_when_opened_include_registry_scripts_and_screensavers() -> None:
    for name in ("ajustes.reg", "app.hta", "fondo.scr", "panel.cpl", "juego.jar", "viejo.com", "dos.pif"):
        assert cu_navigation._runs_when_opened({"name": name}), name
        clicked = [_ok(1, "input.visible.click", label=name, index=0)]
        view = _chosen({"name": name, "itemType": "Carpeta de archivos"})
        assert cu_rules.deterministic_step(goal=f"ir a {name}", view=view, history=clicked) is None, name
    assert not cu_navigation._runs_when_opened({"name": "Comunidad"})


# ------------------------------------------------------------------ 3. the failed-click retry looks up only a name

def test_a_failed_click_on_a_named_kind_is_not_searched_as_words() -> None:
    view = {
        "window": {"title": "Opera", "process": "opera", "focused": None},
        "controls": [
            {"i": 1, "kind": "Button", "name": "Buscar pestañas"},
            {"i": 2, "kind": "TabItem", "name": "Gmail"},
        ],
        "text": {},
    }
    failed = [{"step": 1, "operation": "input.visible.click", "label": "Gmail", "index": 2, "ok": False}]
    step = cu_rules.deterministic_step(goal="ir a la pestaña de Gmail", view=view, history=failed)
    assert step is None or step["operation"] != "input.text.type"
    assert step is None or step["arguments"].get("label") != "Buscar pestañas"


def test_a_failed_click_on_a_bare_name_is_looked_up_by_that_name() -> None:
    view = {
        "window": {"title": "Discord", "process": "Discord", "focused": None},
        "controls": [
            {"i": 2, "kind": "TreeItem", "name": "Cotele"},
            {"i": 3, "kind": "Button", "name": "Buscar o iniciar una conversación"},
        ],
        "text": {},
    }
    failed = [{"step": 1, "operation": "input.visible.click", "label": "Cotele", "index": 2, "ok": False}]
    step = cu_rules.deterministic_step(goal="hacer clic en Cotele", view=view, history=failed)
    assert step is not None and step["arguments"].get("label") == "Buscar o iniciar una conversación"
    # The search box then takes the name itself, never words of the goal.
    clicked = [_ok(1, "input.visible.click", label="Buscar o iniciar una conversación", index=3, surfaceChanged=True)]
    typed = cu_lookup._find_step("Cotele", {**view, "newText": ["Buscar"]}, clicked, navigate=False)
    assert typed is not None and typed["arguments"] == {"text": "Cotele"}


# ------------------------------------------------------------------ 4. Enter after typing where focus is unreadable

def _whatsapp(focused: dict | None) -> dict:
    return {
        "window": {"title": "WhatsApp", "process": "WhatsApp", "focused": focused},
        "controls": [],
        "text": {"L": ["Buscar un chat o iniciar uno nuevo", "Ana", "Beto"], "C": ["Ana", "Escribe un mensaje"]},
    }


def test_enter_after_a_search_typed_where_the_focus_cannot_be_read_asks_first() -> None:
    history = [_ok(1, "input.visible.click", label="Buscar un chat o iniciar uno nuevo"), _ok(2, "input.text.type", text="Ana")]
    for focused in (None, {"kind": "Pane", "name": ""}, {"kind": "Custom", "name": "WhatsApp"}):
        step = cu_rules.deterministic_step(goal="buscar Ana", view=_whatsapp(focused), history=history)
        assert step is not None and step["arguments"] == {"key": "enter", "target": "message_composer"}, focused
    # A search field with the keyboard (Settings): the Enter submits the search, unmarked.
    settings = {
        "window": {"title": "Configuración", "process": "SystemSettings",
                   "focused": {"kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "value": "colores"}},
        "controls": [{"i": 0, "kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "state": "focused"}],
        "text": {},
    }
    typed = [_ok(1, "input.visible.click", label="Cuadro de búsqueda, Buscar una opción", index=0), _ok(2, "input.text.type", text="colores")]
    step = cu_rules.deterministic_step(goal="buscar colores", view=settings, history=typed)
    assert step is not None and step["arguments"] == {"key": "enter"}


def test_a_models_enter_right_after_typing_where_the_focus_cannot_be_read_asks_first() -> None:
    typed = [_ok(1, "input.text.type", text="hola")]
    act = {"act": "key", "key": "enter"}
    step = cu_validate.validate_decision(act, view=_whatsapp(None), last_failed=None, application_names=(), history=typed, goal="escribir hola")
    assert step["arguments"] == {"key": "enter", "target": "message_composer"}
    # Nothing typed last (a click after it), or a calculation: free.
    clicked = [*typed, _ok(2, "input.visible.click", label="Ana")]
    step = cu_validate.validate_decision(act, view=_whatsapp(None), last_failed=None, application_names=(), history=clicked, goal="ir a ana")
    assert step["arguments"] == {"key": "enter"}
    calc = {"window": {"title": "Calculadora", "process": "CalculatorApp", "focused": None}, "controls": [], "text": {}}
    step = cu_validate.validate_decision(act, view=calc, last_failed=None, application_names=(),
                                          history=[_ok(1, "input.text.type", text="2+2")], goal="calcular 2+2")
    assert step["arguments"] == {"key": "enter"}
    assert cu_fields.key_arguments("enter", _whatsapp(None), typed) == {"key": "enter", "target": "message_composer"}
    assert cu_fields.key_arguments("enter", _whatsapp(None)) == {"key": "enter"}


def _chat_behind(*, foreground: bool, composer_value: str | None = None, extra: list[dict] | None = None) -> dict:
    composer = {"i": 3, "kind": "Edit", "name": "Escribe un mensaje"}
    if composer_value is not None:
        composer["value"] = composer_value
    focused = None if not foreground else {**composer, "value": composer_value}
    return {
        "window": {"title": "Chat", "process": "app", "foreground": foreground, "focused": focused},
        "controls": [{"i": 0, "kind": "Edit", "name": "Buscar"}, {"i": 1, "kind": "ListItem", "name": "@Ron"}, composer, *(extra or [])],
        "text": {},
    }


def test_enter_on_a_chat_read_behind_asks_whatever_the_last_step_was() -> None:
    # Safety review r10a, reproduced: «@Ron hola» typed, the mention suggestion clicked, then Enter. Read behind the
    # person's window, the focus is not reported, so the message box with text cannot be seen as focused.
    history = [_ok(1, "input.text.type", text="@Ron hola"), _ok(2, "input.visible.click", label="@Ron")]
    for value in (None, "@Ron hola"):
        view = _chat_behind(foreground=False, composer_value=value)
        assert cu_fields.key_arguments("enter", view, history) == {"key": "enter", "target": "message_composer"}, value
        assert cu_fields.key_arguments("space", view, history)["target"] == "message_composer"
        # A draft of the person's, with nothing typed by this sub-goal.
        assert cu_fields.key_arguments("enter", view) == {"key": "enter", "target": "message_composer"}
    # The same view read in front keeps asking through the focused box.
    assert cu_fields.key_arguments("enter", _chat_behind(foreground=True, composer_value="@Ron hola"), history) == {
        "key": "enter", "target": "message_composer"}


def test_enter_read_behind_stays_free_on_a_search_and_on_an_empty_message_box() -> None:
    # Counter-case: a search read behind (no message box in the view) submits unmarked.
    search = {
        "window": {"title": "Configuración", "process": "SystemSettings", "foreground": False, "focused": None},
        "controls": [{"i": 0, "kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "value": "colores"},
                     {"i": 1, "kind": "ListItem", "name": "Colores"}],
        "text": {},
    }
    clicked = [_ok(1, "input.text.type", text="colores"), _ok(2, "input.visible.click", label="Colores")]
    assert cu_fields.key_arguments("enter", search, clicked) == {"key": "enter"}
    # A message box whose value is shown empty holds nothing to send; a button named «Enviar» is not a box.
    empty = _chat_behind(foreground=False, composer_value=" ", extra=[{"i": 4, "kind": "Button", "name": "Enviar"}])
    assert cu_fields.key_arguments("enter", empty, clicked) == {"key": "enter"}
    # Read in front with the focus on another control (not the message box): the focused rule decides, unchanged.
    front = _chat_behind(foreground=True, composer_value="borrador")
    front["window"]["focused"] = {"kind": "ListItem", "name": "@Ron"}
    assert cu_fields.key_arguments("enter", front, clicked) == {"key": "enter"}



def _field_view(focused: dict) -> dict:
    return {"window": {"title": "Chat", "process": "app", "focused": focused},
            "controls": [{"i": 0, **focused, "state": "focused"}], "text": {}}


def test_a_fallback_name_never_frees_enter_in_a_field_without_a_name_of_its_own() -> None:
    # A text field with no Name, named by its AutomationId or its help text, is still a field without a name of its
    # own: after typing, Enter there may send a message, so RiskPolicy asks.
    typed = [_ok(1, "input.text.type", text="hola")]
    for name, source in (("main Input", "automationId"), ("text Box", "automationId"),
                         ("Buscar o escribir aquí", "helpText"), ("Dirección", "labeledBy")):
        focused = {"kind": "Edit", "name": name, "nameSource": source, "value": None}
        assert cu_fields.key_arguments("enter", _field_view(focused), typed) == {"key": "enter", "target": "message_composer"}, name
    # Counter-case: the same names as the field's own Name keep their meaning (a plain unnamed-looking name that is
    # the field's own is not a message box; an own search name frees the Enter).
    own = {"kind": "Edit", "name": "main Input", "value": None}
    assert cu_fields.key_arguments("enter", _field_view(own), typed) == {"key": "enter"}
    search = {"kind": "Edit", "name": "Buscar o escribir aquí", "value": None}
    assert cu_fields.key_arguments("enter", _field_view(search), typed) == {"key": "enter"}
    # A fallback name that reads as a message box still asks (it only makes the step ask more).
    chat = {"kind": "Edit", "name": "message Input", "nameSource": "automationId", "value": None}
    assert cu_fields.key_arguments("enter", _field_view(chat), typed) == {"key": "enter", "target": "message_composer"}


def test_a_fallback_search_name_does_not_make_a_field_a_search() -> None:
    # «buscá Ana» typed into a field named «Buscar» only by its help text: the Enter asks first.
    history = [_ok(1, "input.text.type", text="Ana")]
    focused = {"kind": "Edit", "name": "Buscar", "nameSource": "helpText", "value": "Ana"}
    step = cu_rules.deterministic_step(goal="buscar Ana", view=_field_view(focused), history=history)
    assert step is not None and step["arguments"] == {"key": "enter", "target": "message_composer"}
    # Counter-case: «Buscar» as the field's own Name is a search; its Enter submits unmarked.
    own = {"kind": "Edit", "name": "Buscar", "value": "Ana"}
    step = cu_rules.deterministic_step(goal="buscar Ana", view=_field_view(own), history=history)
    assert step is not None and step["arguments"] == {"key": "enter"}


def test_delete_after_an_address_needs_a_field_named_address_by_its_own_name() -> None:
    fallback = {"kind": "Edit", "name": "address Bar", "nameSource": "automationId", "value": "es.wikipedia.org"}
    own = {"kind": "Edit", "name": "Barra de direcciones", "value": "es.wikipedia.org"}
    assert cu_fields._keyboard_on_address_field(_field_view(fallback)) is False
    assert cu_fields._keyboard_on_address_field(_field_view(own)) is True


# ------------------------------------------------------------------ 5. the menu's default entry is never blind

def _menu(entries: list[str], *, controls: list[dict] | None = None) -> dict:
    return {
        "window": {"title": "Steam", "process": "steamwebhelper", "focused": None},
        "controls": controls or [],
        "newText": entries,
        "text": {"TL": ["BIBLIOTECA", *entries]},
    }


def test_a_menu_read_only_from_written_lines_gets_no_blind_first_entry() -> None:
    clicked = [_ok(1, "input.visible.click", label="Hades")]
    assert cu_menus._menu_opened_by(_menu(["Propiedades", "Administrar"]), clicked, "hades", "ir a hades") is None
    # The same entries as menu items of the tree that appeared together: the first one.
    tree = [{"i": 1, "kind": "MenuItem", "name": "Propiedades"}, {"i": 2, "kind": "MenuItem", "name": "Administrar"}]
    assert cu_menus._menu_opened_by(_menu(["Propiedades", "Administrar"], controls=tree), clicked, "hades", "ir a hades") == "Propiedades"
    # The place's own page is the measured default even without a tree (Steam «BIBLIOTECA» → «Página principal»).
    library = [_ok(1, "input.visible.click", label="BIBLIOTECA")]
    assert cu_menus._menu_opened_by(_menu(["Colecciones", "Página principal"]), library, "biblioteca", "ir a biblioteca") == "Página principal"


def test_a_menu_entry_that_does_something_is_never_the_default() -> None:
    clicked = [_ok(1, "input.visible.click", label="Hades")]
    tree = [{"i": 1, "kind": "MenuItem", "name": "Jugar"}, {"i": 2, "kind": "MenuItem", "name": "Propiedades"}]
    assert cu_menus._menu_opened_by(_menu(["Jugar", "Propiedades"], controls=tree), clicked, "hades", "ir a hades") is None
    # Not even when the goal's words name it.
    library = [_ok(1, "input.visible.click", label="BIBLIOTECA")]
    for act in ("Instalar", "Desinstalar", "Enviar", "Unirse"):
        picked = cu_menus._menu_opened_by(_menu([act, "Colecciones"]), library, "biblioteca", f"ir a {act} de la biblioteca")
        assert picked != act, act


# ------------------------------------------------------------------ 6. no switch for any placing goal

def test_a_placing_goal_never_presses_a_switch_the_model_chose() -> None:
    view = {
        "window": {"title": "Configuración", "process": "SystemSettings", "focused": None},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Bluetooth", "state": "on"},
            {"i": 1, "kind": "CheckBox", "name": "Recordarme", "state": "unchecked"},
        ],
        "text": {},
    }
    act = {"act": "click", "label": "Bluetooth", "i": 0}
    for goal in ("buscar bluetooth", "ir a bluetooth"):
        refused = cu_validate.validate_decision(act, view=view, last_failed=None, application_names=(), goal=goal)
        assert refused["operation"] == "none" and refused.get("code") == "changes_a_setting", goal
    # «hacé clic en Bluetooth» names that switch: pressing it is the person's own order.
    named = cu_validate.validate_decision(act, view=view, last_failed=None, application_names=(), goal="hacer clic en Bluetooth")
    assert named["operation"] == "input.visible.click"
    for goal in ("activar bluetooth", "desactivar bluetooth"):
        allowed = cu_validate.validate_decision(act, view=view, last_failed=None, application_names=(), goal=goal)
        assert allowed["operation"] == "input.visible.click", goal
    # A click that names the switch's kind wants the switch.
    box = {"act": "click", "label": "Recordarme", "i": 1}
    allowed = cu_validate.validate_decision(box, view=view, last_failed=None, application_names=(), goal="hacer clic en la casilla Recordarme")
    assert allowed["operation"] == "input.visible.click"
    assert cu_goals._placing_goal("buscar hades") and cu_goals._placing_goal("hacer clic en Guardar")
    assert not cu_goals._placing_goal("activar wifi") and not cu_goals._placing_goal("hacer clic en la casilla Recordarme")
