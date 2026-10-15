"""Encargo TZ-WA2: WhatsApp «ir a Abuela» en el banco final reducido zu1–zu3 (notebook, fable/estab-fase3 e61a9ed41).

Medido por caso (journal-caso.json y model_calls.jsonl de cu-v3/evidencia_zu<N>/v2-imp-wa-*):
- zu1 leer: WhatsApp tapado por VS Code (el OCR de la vista leyó VS Code). El chat estaba en la lista («Abuela 19:25»),
  pero la regla lo buscó por nombre fuera de la vista («abuela», no encontrado), escribió «abuela» en la búsqueda y pulsó
  la fila con la vista previa «Abuela 19:25 prueba BAXY imp»: su acción por defecto no abrió nada.
- zu2 enviar / zu2 leer / zu3 enviar / zu3 leer: la búsqueda conservaba «abuela» del caso anterior. La regla pulsó el eco
  «abuela» del propio cuadro por OCR; el modelo pulsó «Nuevo chat» y la regla de pestañas eligió «No leídos», que quedó
  puesto en WhatsApp y ocultó el chat a la búsqueda en los casos siguientes.
- zu3 abrir: con «No leídos» y «abuela» heredados, «Nuevo chat» y después «Favoritos»; final «No pude llegar».
- zu2 abrir llegó en el quinto paso: la fila no abrió y la celda de título «Abuela 19:25» pulsada en la superficie sí.

Ahora ir a un chat de una aplicación cuyos datos dicen cómo se busca su lista de chats (app_places «chatSearch») lo
decide cu_chats.chat_search_step: la entrada propia del chat, el filtro de todos los chats, el buscador por su valor y el
resultado exacto; nunca el modelo, otro filtro ni «Nuevo chat». Las vistas son las del journal por sus nombres (los
«destacados»), con el cuadro de búsqueda que la vista del modelo lista en el mismo paso cuando el journal no lo destaca.
"""

from __future__ import annotations

from baxy_mind import computer_use as cu
from baxy_mind import cu_model_calls
from baxy_mind.cu_chats import chat_search_step
from baxy_mind.cu_lookup import SEARCH_PENDING
from baxy_mind.semantic import app_places

NAMES = ["WhatsApp", "Discord"]
CHECK = "control:abuela:current|title:abuela|page:abuela|mark:abuela"
OPEN = "en WhatsApp abrí el chat con Abuela"
SEND = 'en WhatsApp mandale a Abuela "prueba BAXY imp"'
READ = "en WhatsApp leé lo último que me escribió Abuela"
_SIDE = [("Button", "Llamadas", "off"), ("Button", "Estados", "off"), ("Button", "Archivado", "off")]


def _view(title: str, focused: dict, controls: list[tuple], text: dict | None = None) -> dict:
    listed = []
    for i, (kind, name, *rest) in enumerate(controls):
        state, value = (*rest, "", "")[:2]
        listed.append({"i": i, "kind": kind, "name": name, **({"state": state} if state else {}),
                       **({"value": value} if value else {})})
    return {"window": {"title": title, "process": "msedgewebview2", "requested": True, "foreground": False,
                       "focused": focused}, "controls": listed, "text": text or {}}


def _zu1_leer() -> dict:
    # zu1 imp-wa-leer, first look (22:26:48.763 UTC): the chat list, «Abuela» third; the screen copy read VS Code.
    return _view("(3) WhatsApp", {"kind": "Document", "name": "(3) WhatsApp"}, [
        ("Document", "(3) WhatsApp", "readonly focused"),
        ("Button", "Chats", "on"),
        ("Button", "Nuevo chat"),
        ("Edit", "Buscar un chat o iniciar uno nuevo"),
        ("TabItem", "Todos", "selected"),
        ("TabItem", "No leídos 6"),
        ("DataItem", "Ver estado Contacto A 💕 19:26 0:11 Se fijó el chat. Chat destacado"),
        ("DataItem", "Contacto A 💕 19:26"),
        ("DataItem", "5 mensajes no leídos Contacto B 19:26 texto de ejemplo"),
        ("DataItem", "5 mensajes no leídos Contacto B 19:26"),
        ("DataItem", "Abuela 19:25 prueba BAXY imp"),
        ("DataItem", "Abuela 19:25 prueba BAXY imp"),
        ("DataItem", "Abuela 19:25"),
        ("DataItem", "1 mensaje no leído Contacto C 👹 19:25 0:13"),
        ("DataItem", "1 mensaje no leído Contacto C 👹 19:25"),
        ("DataItem", "Contacto D 19:06"),
        *_SIDE,
    ], {"TL": ["File Edit Selection View Go Run Terminal", "Help", "/goal"], "L": ["Thought for Is", "Bash"]})


def _zu2_enviar() -> dict:
    # zu2 imp-wa-enviar, first look (22:40:37.012 UTC): the search kept «abuela» from zu2 abrir; its results.
    return _view("(1) WhatsApp", {"kind": "Document", "name": "(1) WhatsApp"}, [
        ("Document", "(1) WhatsApp", "readonly focused"),
        ("Button", "Chats", "on"),
        ("Button", "Nuevo chat"),
        ("Edit", "WhatsApp", "", "abuela"),
        ("TabItem", "Todos", "selected"),
        ("TabItem", "No leídos 4"),
        ("TabItem", "Favoritos"),
        ("DataGrid", "Resultados de la búsqueda."),
        ("DataItem", "Abuela 19:25 prueba BAXY imp"),
        ("DataItem", "Abuela 19:25"),
        ("DataItem", "4 mensajes no leídos Grupo Familia Ejemplo 😍 😍 😍 15:41 Ab ... texto de ejemplo."),
        ("DataItem", "4 mensajes no leídos Grupo Familia Ejemplo 😍 😍 😍 15:41"),
        ("DataItem", "Contacto A 💕 15/9/2026 ¿Viene la abuela?"),
        ("DataItem", "Contacto A 💕 15/9/2026"),
        ("DataItem", "Contacto E 😎 17/5/2026 texto de ejemplo con mi abuela"),
        ("DataItem", "Contacto E 😎 4/4/2026 donde mi abuela"),
        *_SIDE,
    ], {"TL": ["s", "WhatsApp", "Chats", "abuela", "x", "Todos", "No leídos 4", "Favoritos"],
        "L": ["Abuela", "19:25", "v' prueba BAXY imp", "Grupos en común", "Grupo Familia Ejemplo"]})


def _zu3_abrir() -> dict:
    # zu3 imp-wa-abrir, first look (22:54:28.268 UTC; the model's view of step 3 lists «Todos» and the search's value):
    # «No leídos» left on by zu2 enviar, «abuela» in the search, no chat named so among the filtered results; the
    # screen copy read Discord, on top.
    return _view("(2) WhatsApp", {"kind": "Document", "name": "(2) WhatsApp"}, [
        ("Document", "(2) WhatsApp", "readonly focused"),
        ("Button", "Chats", "on"),
        ("Button", "Menú", "collapsed"),
        ("Button", "Nuevo chat"),
        ("Edit", "WhatsApp", "", "abuela"),
        ("TabItem", "Todos"),
        ("TabItem", "No leídos 5", "selected"),
        ("TabItem", "Favoritos 1"),
        ("TabItem", "additional filters"),
        ("Tab", "chat-list-filters"),
        ("DataGrid", "Resultados de la búsqueda."),
        ("DataItem", "Grupo Familia Ejemplo 😍 😍 😍 8/3/2026 Persona X : Feliz día abuela"),
        ("DataItem", "Grupo Familia Ejemplo 😍 😍 😍 8/3/2026"),
        ("DataItem", "Grupo Familia Ejemplo 😍 😍 😍 7/3/2026 Persona X : Gracias ab ... texto de ejemplo"),
        ("DataItem", "Grupo Ejemplo 🦞 22/12/2025"),
        *_SIDE,
    ], {"TR": ["x", "Buscar .wolfsoult", "Buscar .wolfsoultl"], "T": ["Mensajes directos", "Ron92"]})


def _decide(objective: str, view: dict, history: list[dict] | None = None, goal: str = "ir a abuela",
            application: str = "WhatsApp") -> dict:
    return cu._decide_step(
        None, objective=objective, goal=goal, application=application, success_check=CHECK, view=view,
        history=history or [], budget_left=10, application_names=NAMES, subgoal=0, subgoal_count=1,
        translator=cu_model_calls.LabelTranslator(None, enabled=False),
    )


def _click(label: str, **extra: object) -> dict:
    return {"step": 1, "operation": "input.visible.click", "label": label, "ok": True, **extra}


# ------------------------------------------------------------------------------------------------ the chat's entry

def test_zu1_the_chats_own_entry_in_the_list_is_pressed_never_looked_up_by_name() -> None:
    for objective in (OPEN, READ, SEND):
        decision = _decide(objective, _zu1_leer())
        assert decision["operation"] == "input.visible.click"
        assert decision["arguments"] == {"label": "Abuela 19:25", "index": 12}


def test_zu2_a_search_kept_from_before_has_its_chats_entry_pressed_never_its_echo_nor_a_new_chat() -> None:
    decision = _decide(SEND, _zu2_enviar())
    assert decision["operation"] == "input.visible.click"
    # The title cell, pressed on the surface (zu2 abrir: it opened the chat); never the row with the preview, whose
    # default action opened nothing (zu1 leer, zu2 abrir), the field's echo «abuela» or a message naming her.
    assert decision["arguments"] == {"label": "Abuela 19:25", "index": 9}


def test_zu3_a_filter_that_hides_the_chat_gives_way_to_every_chat_and_nothing_else() -> None:
    decision = _decide(OPEN, _zu3_abrir())
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Todos", "index": 5}
    # Chosen, the results draw a moment later: looked at once more, never another filter or «Nuevo chat».
    chosen = [_click("Todos", index=5)]
    waited = _decide(OPEN, _zu3_abrir(), chosen)
    assert waited["operation"] == "none" and waited["code"] == SEARCH_PENDING
    # With every chat shown, the search's own result.
    after = _zu2_enviar()
    assert _decide(OPEN, after, [{**chosen[0], "awaited": True}])["arguments"]["label"] == "Abuela 19:25"


def test_zu3_after_the_wait_with_no_entry_the_mission_stops_without_wandering() -> None:
    # Every chat shown and still no entry named so: the chat is not there; nothing else is pressed.
    view = _zu3_abrir()
    for control in view["controls"]:
        if control["kind"] == "TabItem":
            control["state"] = "selected" if control["name"] == "Todos" else ""
    decision = _decide(OPEN, view, [_click("Todos", index=5, awaited=True)])
    assert decision["operation"] == "none" and decision["code"] == "no_step_visible"


def test_an_entry_pressed_is_given_a_moment_then_the_search_is_tried_once() -> None:
    pressed = [_click("Abuela 19:25", index=12)]
    waited = _decide(OPEN, _zu1_leer(), pressed)
    assert waited["operation"] == "none" and waited["code"] == SEARCH_PENDING
    # Not opened after the moment: the entry may be stale; the chat search, clicked first and then given the name by
    # its value (the field replaced whole by its index), never the same entry once more.
    pressed[0]["awaited"] = True
    clicked = _decide(OPEN, _zu1_leer(), pressed)
    assert clicked["arguments"] == {"label": "Buscar un chat o iniciar uno nuevo", "index": 3}
    typed = _decide(OPEN, _zu1_leer(), [*pressed, _click("Buscar un chat o iniciar uno nuevo", index=3)])
    assert typed["operation"] == "input.text.type"
    assert typed["arguments"] == {"text": "abuela", "index": 3, "replace": True}


def test_a_chat_out_of_sight_is_searched_by_value_and_its_result_pressed() -> None:
    # The coordinator's hypothesis (the chat pushed down the list by new messages): zu1's look without its rows.
    view = _zu1_leer()
    view["controls"] = [control for control in view["controls"] if "Abuela" not in control["name"]]
    assert _decide(READ, view)["arguments"]["label"] == "Buscar un chat o iniciar uno nuevo"
    view["window"]["focused"] = {"kind": "Edit", "name": "Buscar un chat o iniciar uno nuevo"}
    history = [_click("Buscar un chat o iniciar uno nuevo", index=3)]
    typed = _decide(READ, view, history)
    assert typed["arguments"] == {"text": "abuela", "index": 3, "replace": True}
    history.append({"step": 2, "operation": "input.text.type", "text": "abuela", "ok": True, "query": True})
    assert _decide(READ, view, history)["code"] == SEARCH_PENDING
    history[-1]["awaited"] = True
    assert _decide(READ, _zu2_enviar(), history)["arguments"]["label"] == "Abuela 19:25"


# ------------------------------------------------------------------------------------------------------ contracases

def test_contracase_entries_that_are_not_the_chats_own_are_never_taken() -> None:
    spec, _ = app_places.chat_search("WhatsApp", "ir a abuela")
    import re

    shape = re.compile(spec["entry"].replace("{name}", "abuela"))
    for name in ("abuela 19:25 prueba baxy imp", "abuela rosa 12:00", "contacto a 💕 15/9/2026 viene la abuela?",
                 "contacto e 😎 4/4/2026 donde mi abuela", "escribir un mensaje para abuela"):
        assert shape.fullmatch(name) is None, name
    for name in ("abuela", "abuela 19:25", "1 mensaje no leido abuela 21:03", "abuela 29/9/2026", "abuela ayer"):
        assert shape.fullmatch(name) is not None, name
    emoji = re.compile(spec["entry"].replace("{name}", "contacto a"))
    assert emoji.fullmatch("contacto a 💕 19:26") is not None and emoji.fullmatch("contacto a 💕 19:26 hola?") is None


def test_contracase_other_applications_goals_and_panels_keep_the_engines_way() -> None:
    # An application whose data do not say how its chats are searched (Discord: its chats have an address).
    assert chat_search_step("ir a ron92", "Discord", _zu1_leer(), []) is None
    # A search or a typed text is no chat gone to.
    assert chat_search_step("buscar abuela", "WhatsApp", _zu1_leer(), []) is None
    assert chat_search_step("escribir prueba BAXY imp", "WhatsApp", _zu1_leer(), []) is None
    # Another panel of the application, with no chat search on screen.
    panel = _zu1_leer()
    panel["controls"] = [control for control in panel["controls"] if control["kind"] != "Edit"]
    assert chat_search_step("ir a abuela", "WhatsApp", panel, []) is None


def test_contracase_the_filter_is_never_touched_when_the_chat_is_in_sight_or_every_chat_is_shown() -> None:
    # zt2 and wac (good runs): «Todos» selected and the chat listed: only its entry.
    assert _decide(OPEN, _zu1_leer())["arguments"]["label"] == "Abuela 19:25"
    # A filter of the person's that shows the chat stays as it is.
    view = _zu1_leer()
    for control in view["controls"]:
        if control["kind"] == "TabItem":
            control["state"] = "selected" if control["name"] == "No leídos 6" else ""
    assert _decide(OPEN, view)["arguments"]["label"] == "Abuela 19:25"


def test_contracase_a_recent_search_button_named_whole_is_the_chats_entry() -> None:
    # zt1 (good): the empty search focused shows «Búsquedas recientes» with the button «Abuela»; pressed by Invoke it
    # opened the chat (zt1 abrir and enviar, zt3 four times).
    view = _zu1_leer()
    view["controls"] = [control for control in view["controls"] if "Abuela" not in control["name"]]
    view["controls"].append({"i": len(view["controls"]), "kind": "Button", "name": "Abuela"})
    view["controls"].append({"i": len(view["controls"]), "kind": "Button", "name": "Borrar todo"})
    decision = _decide(OPEN, view, [_click("Buscar un chat o iniciar uno nuevo", index=3)])
    assert decision["arguments"]["label"] == "Abuela"


# --------------------------------------------------- the good runs before (zt2, wac1): the same chat, the same way

def _zt2_abrir() -> dict:
    # zt2 imp-wa-abrir, first look (19:46:10.040 UTC): «Abuela» seventh in the list; the rule pressed «Abuela» by OCR.
    return _view("(5) WhatsApp", {"kind": "Document", "name": "(5) WhatsApp"}, [
        ("Document", "(5) WhatsApp", "readonly focused"),
        ("Button", "Chats", "on"),
        ("Edit", "Buscar un chat o iniciar uno nuevo"),
        ("TabItem", "Todos", "selected"),
        ("TabItem", "No leídos 8"),
        ("TabItem", "Favoritos 1"),
        ("DataItem", "Ver estado 1 mensaje no leído Contacto A 💕 16:00 Texto de ejemplo ... . Chat destacado"),
        ("DataItem", "1 mensaje no leído Contacto A 💕 16:00"),
        ("DataItem", "4 mensajes no leídos Contacto B 16:40 texto de ejemplo"),
        ("DataItem", "4 mensajes no leídos Contacto B 16:40"),
        ("DataItem", "Contacto C 👹 16:17"),
        ("DataItem", "Abuela 16:11 prueba BAXY imp"),
        ("DataItem", "Abuela 16:11"),
        ("DataItem", "Contacto F 15:48 Vale, texto de ejemplo"),
        ("DataItem", "Contacto F 15:48"),
        *_SIDE,
    ])


def _wac1_abrir(searching: bool) -> dict:
    # wac1 imp-wa-abrir (03:11:37.716 and 03:11:42.916 UTC): «Abuela» out of sight; the search clicked shows the recent
    # searches, «Abuela» among them, whose press opened the chat.
    controls = [
        ("Document", "(2) WhatsApp", "readonly" if searching else "readonly focused"),
        ("Button", "Chats", "on"),
        ("Edit", "Buscar un chat o iniciar uno nuevo", "focused" if searching else ""),
        ("TabItem", "Todos", "selected"),
        ("TabItem", "No leídos 4"),
        ("DataItem", "Ver estado Contacto A 💕 0:09 . Se fijó el chat. Chat destacado"),
        ("DataItem", "Contacto A 💕 0:09"),
        ("DataItem", "9 mensajes no leídos Contacto B 0:11"),
        ("DataItem", "Contacto G Ayer 0:05"),
        ("DataItem", "+00 0 0000 0000 Ayer"),
        *_SIDE,
    ]
    if searching:
        controls += [("Group", "Búsquedas recientes"), ("Button", "Borrar todo"), ("Button", "Contacto H"),
                     ("Button", "Contacto I 🍓"), ("Button", "Abuela")]
    focused = ({"kind": "Edit", "name": "Buscar un chat o iniciar uno nuevo"} if searching
               else {"kind": "Document", "name": "(2) WhatsApp"})
    return _view("(2) WhatsApp", focused, controls)


def test_contracase_zt2_the_chat_in_the_list_is_its_title_cell() -> None:
    decision = _decide(OPEN, _zt2_abrir())
    assert decision["arguments"] == {"label": "Abuela 16:11", "index": 12}


def test_contracase_wac1_out_of_sight_the_search_then_its_recent_entry() -> None:
    first = _decide(OPEN, _wac1_abrir(searching=False))
    assert first["arguments"] == {"label": "Buscar un chat o iniciar uno nuevo", "index": 2}
    clicked = [_click("Buscar un chat o iniciar uno nuevo", index=2, kind="Edit", focused=True)]
    second = _decide(OPEN, _wac1_abrir(searching=True), clicked)
    assert second["operation"] == "input.visible.click" and second["arguments"]["label"] == "Abuela"
