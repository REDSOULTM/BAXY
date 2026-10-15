"""Paro y campo (pasada r15b: v3-27, v3-28, v3-17, v3-08) con las vistas reales congeladas de model_calls.jsonl.

Medido: en el Mapa de caracteres (v3-27) el modelo pulsó la etiqueta Text «Caracteres para copiar:» en vez de su Edit;
el clic no hizo nada y, con otro clic sin efecto, la misión paró por «la pantalla dejó de cambiar» antes de escribir.
En v3-28 el paro llegó sin que el modelo viera nunca por qué. En Fotos (v3-17) «guárdala como copia» no reconoció el
enclítico, el «Guardar» se rechazó como acto de cuenta y ese rechazo no daba reintento. En OneNote (v3-08) el foco ya
estaba en el «Título de página» vacío de la página nueva y el modelo pulsó «Nuevo cuaderno».

Contracasos de seguridad: una etiqueta sin campo, o la de una contraseña, sigue siendo la etiqueta; un documento que ya
tiene texto (el trabajo de la persona), un buscador o una parte que el objetivo no nombra nunca reciben el texto; un
«Guardar» que el objetivo no pide sigue rechazado; un «no la guardes» no pide guardar.
"""

from __future__ import annotations

import copy

from baxy_mind import computer_use as cu
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt
from baxy_mind.semantic.account_acts import goal_asks_for
from baxy_mind.semantic.cu_buscar import slot_text

_APPS = ("Mapa de caracteres", "Fotos", "OneNote")


def _control(i: int, kind: str, name: str, state: str = "", zone: str = "C", value: str = "") -> dict:
    control: dict = {"i": i, "kind": kind, "name": name, "state": state, "zone": zone}
    if value:
        control["value"] = value
    return control


def _listed(*controls: dict) -> list[dict]:
    """The view's controls with each one at its own index, as the App lists them (the model's «i» is the position):
    the ones the prompt left out are unnamed groups."""

    by_index = {control["i"]: control for control in controls}
    return [by_index.get(n, {"i": n, "kind": "Group", "name": "", "state": "", "zone": "C"}) for n in range(max(by_index) + 1)]


class _Model:
    """A local model that answers the step with the given acts, in order, and records what it was asked."""

    def __init__(self, *acts: dict) -> None:
        self.acts = list(acts)
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, label: str) -> object:
        if payload["messages"][0]["content"] != cu_step_prompt.STEP_PROMPT:
            return {"es": [], "en": []}
        self.payloads.append(copy.deepcopy(payload))
        return self.acts.pop(0) if self.acts else {"act": "none"}


def _opened(app: str) -> dict:
    return {"step": 1, "operation": "app.open", "appId": app, "ok": True, "changed": True}


# ------------------------------------------------------------------ v3-27: la etiqueta de un campo es el campo
# The view of request 8 (charmap), as the model saw it.
_CHARMAP = {
    "window": {"title": "Mapa de caracteres", "process": "charmap", "requested": True},
    "controls": _listed(
        _control(0, "Edit", "Caracteres para copiar:"),
        _control(1, "Button", "Seleccionar", zone="R"),
        _control(2, "CheckBox", "Vista avanzada", "on", "BL"),
        _control(3, "ComboBox", "Juego de caracteres:", "collapsed", "B"),
        _control(5, "Edit", "Ir a Unicode:", zone="BR"),
        _control(6, "ComboBox", "Agrupar por:", "collapsed", "B"),
        _control(7, "Document", "Buscar:", zone="B"),
        _control(8, "ComboBox", "Fuente:", "collapsed", "T"),
        _control(9, "Button", "Ayuda", zone="TR"),
        _control(10, "Edit", "Carácter seleccionado", "readonly", "B"),
        _control(11, "MenuItem", "Sistema", "collapsed", "TL"),
        _control(14, "Pane", "Cuadrícula de caracteres"),
        _control(15, "Text", "Caracteres para copiar:", zone="L"),
        _control(16, "Text", "Juego de caracteres:", zone="BL"),
        _control(17, "Text", "Ir a Unicode:", zone="BR"),
        _control(18, "Text", "Agrupar por:", zone="BL"),
        _control(19, "Text", "Buscar:", zone="BL"),
        _control(20, "Text", "Carácter seleccionado:", zone="BL"),
        _control(21, "Text", "U+0021: Exclamación de cierre", zone="B"),
        _control(22, "Text", "Fuente:", zone="TL"),
        _control(23, "TitleBar", "Mapa de caracteres", zone="T"),
    ),
    "text": {"T": ["< = > ? @ABCDEFGH"], "C": ["qrstuvwxyz{l}—"]},
}
_V327 = "copia el simbolo del euro"


def _check(raw: dict, view: dict, goal: str, history: list | None = None, application: str = "Mapa de caracteres") -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=_APPS, history=history or [_opened(application)], goal=goal,
        objective=goal, application=application,
    )


def test_v3_27_a_click_on_a_fields_label_goes_to_the_field() -> None:
    decision = _check({"act": "click", "i": 15}, copy.deepcopy(_CHARMAP), _V327)
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Caracteres para copiar:", "index": 0}


def test_a_click_on_a_combo_boxs_label_goes_to_the_combo_box() -> None:
    decision = _check({"act": "click", "i": 22}, copy.deepcopy(_CHARMAP), "pon la fuente Wingdings")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Fuente:", "index": 8}


def test_a_label_without_a_field_of_its_name_stays_the_label() -> None:
    # «Carácter seleccionado:» labels a read-only Edit, «U+0021…» labels nothing: neither click moves.
    for index, name in ((20, "Carácter seleccionado:"), (21, "U+0021: Exclamación de cierre")):
        decision = _check({"act": "click", "i": index}, copy.deepcopy(_CHARMAP), _V327)
        assert decision["operation"] == "input.visible.click"
        assert decision["arguments"] == {"label": name, "index": index}


def test_a_label_of_a_document_is_never_moved_to_it() -> None:
    # Only a field or a list box is a label's field: «Buscar:» stays the label beside the Document of that name.
    decision = _check({"act": "click", "i": 19}, copy.deepcopy(_CHARMAP), _V327)
    assert decision["arguments"] == {"label": "Buscar:", "index": 19}


def test_a_label_of_a_password_field_is_never_moved_to_it() -> None:
    view = {
        "window": {"title": "Iniciar sesión", "process": "app"},
        "controls": [_control(0, "Edit", "Contraseña:", "password"), _control(1, "Text", "Contraseña:", zone="L")],
    }
    decision = _check({"act": "click", "i": 1}, view, "escribí la contraseña")
    assert decision["arguments"] == {"label": "Contraseña:", "index": 1}


def test_two_fields_of_the_labels_name_leave_the_label_as_it_was() -> None:
    view = copy.deepcopy(_CHARMAP)
    view["controls"][4] = _control(4, "Edit", "Caracteres para copiar:", zone="R")
    decision = _check({"act": "click", "i": 15}, view, _V327)
    assert decision["arguments"] == {"label": "Caracteres para copiar:", "index": 15}


# ------------------------------------------------------------------ v3-17: «guárdala» pide guardar, y el rechazo reintenta
# The view of request 31 (Fotos, the resize dialog with its file type list open).
_PHOTOS = {
    "window": {"title": "prueba.png", "process": "Photos", "requested": True,
               "focused": {"kind": "ListItem", "name": "PNG", "i": 3}},
    "controls": _listed(
        _control(1, "ComboBox", "Tipo de archivo", "expanded"),
        _control(2, "ListItem", "JPG"),
        _control(3, "ListItem", "PNG", "selected focused"),
        _control(4, "ListItem", "TIF"),
        _control(6, "Button", "Guardar", zone="B"),
        _control(7, "Button", "Cancelar", zone="B"),
        _control(13, "Edit", "Ancho", zone="C", value="100"),
        _control(14, "Edit", "Altura", zone="C", value="100"),
        _control(17, "Button", "Información del archivo", zone="B"),
        _control(25, "Button", "Editar", zone="TL"),
        _control(26, "Button", "Girar", zone="TL"),
        _control(27, "Button", "Eliminar", zone="TL"),
        _control(30, "Button", "Más opciones para Editar barra de herramientas", zone="TL"),
        _control(32, "MenuItem", "Sistema", "collapsed", "TL"),
    ),
    "text": {"T": ["prueba.png", "Cambiar tamaño"], "B": ["Nuevo:", "1 KB", "Guardar", "Cancelar"]},
}
_V317_SAVE = "guárdala como copia en esa misma carpeta"


def test_v3_17_saving_it_said_with_its_pronoun_asks_for_the_save() -> None:
    decision = _check({"act": "click", "i": 6}, copy.deepcopy(_PHOTOS), _V317_SAVE, application="Fotos")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Guardar", "index": 6}


def test_a_save_the_goal_does_not_ask_for_is_still_refused() -> None:
    decision = _check({"act": "click", "i": 6}, copy.deepcopy(_PHOTOS), "recórtala en proporción cuadrada", application="Fotos")
    assert decision["operation"] == "none"
    assert decision["code"] == "changes_the_account"


def test_v3_17_an_account_refusal_gets_one_more_try_with_the_refusal_in_front() -> None:
    model = _Model({"act": "click", "i": 6}, {"act": "click", "i": 25})
    decision = cu.decide_step(
        model, objective="recórtala en proporción cuadrada", goal="recórtala en proporción cuadrada", application="Fotos",
        success_check=None, view=copy.deepcopy(_PHOTOS), history=[_opened("Fotos")], budget_left=8,
        application_names=_APPS,
    )
    assert "changes_the_account" in cu._RETRIED
    assert len(model.payloads) == 2
    assert "cambia tu cuenta" in model.payloads[1]["messages"][-1]["content"]
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"]["label"] == "Editar"


def test_enclitic_verbs_ask_for_their_act_and_negations_do_not() -> None:
    assert goal_asks_for("guárdala como copia en esa misma carpeta", "save")
    assert goal_asks_for("save it as a copy", "save")
    assert goal_asks_for("instálalo", "install")
    assert goal_asks_for("seguilo", "follow")
    assert goal_asks_for("agrégala a favoritos", "save")
    assert goal_asks_for("tenés que guardarla", "save")
    assert not goal_asks_for("ábrelo", "save")
    assert not goal_asks_for("recórtala", "save")
    assert not goal_asks_for("no la guardes", "save")
    assert not goal_asks_for("creá una nota sin guardarla", "save")
    assert not goal_asks_for("abrí la lista de guardados", "save")
    assert goal_asks_for("guárdamela", "save")


def test_an_indirect_pronoun_alone_never_asks_for_an_account_act() -> None:
    """Review of paro-campo, finding 1: «agrégale X a la foto» gives something to the photo, never asks to save it;
    «únete», «unile las celdas» never ask to join, «seguile la pista» never asks to follow."""

    for goal in ("agregale un filtro a la foto", "añadile un borde a la imagen", "agrégale un título a la diapositiva",
                 "agregale una columna", "agrégame un filtro"):
        assert not goal_asks_for(goal, "save"), goal
    assert not goal_asks_for("unite al canal", "subscribe")
    assert not goal_asks_for("unile las dos celdas", "subscribe")
    assert not goal_asks_for("seguile la pista al pedido", "follow")


def test_save_is_refused_when_the_goal_adds_something_to_the_photo() -> None:
    decision = _check({"act": "click", "i": 6}, copy.deepcopy(_PHOTOS), "agregale un filtro a la foto",
                      application="Fotos")
    assert decision["operation"] == "none"
    assert decision["code"] == "changes_the_account"


# ------------------------------------------------------------------ v3-08: el título va al foco que lo nombra
# The view of request 10 (OneNote, the new page «Sin título» with the keyboard in its empty title).
_NEW_PAGE = {
    "window": {"title": "Sin título - OneNote", "process": "ONENOTE", "requested": True,
               "focused": {"kind": "Document", "name": "Título de página", "i": 46}},
    "controls": _listed(
        _control(0, "Button", "Atrás", zone="TL"),
        _control(4, "Edit", "Búsqueda de Microsoft", zone="T", value="Buscar"),
        _control(9, "Button", "Pestaña Archivo", zone="TL"),
        _control(10, "TabItem", "Inicio", zone="TL"),
        _control(11, "TabItem", "Insertar", zone="TL"),
        _control(21, "Button", "Nuevo bloc de notas de Copilot", zone="TL"),
        _control(22, "Button", "Cuadernos", "expanded", "TL"),
        _control(23, "Button", "Nuevo cuaderno", zone="TL"),
        _control(24, "TreeItem", "PERSONA en INSTITUTO EJEMPLO", "selected expanded", "L"),
        _control(36, "TreeItem", "Nueva sección 10", "selected", "BL"),
        _control(42, "ListItem", "Sin título", zone="T"),
        _control(44, "Button", "Buscar", zone="TR"),
        _control(46, "Document", "Título de página", "focused", "TR"),
        _control(59, "Pane", "Buscar", zone="TR"),
    ),
    "text": {"TL": ["Sin título", "- OneNote", "Archivo", "Inicio"], "T": ["Agregar página"]},
}
_V308 = "ponele de título Lista del super"
_V308_REQUEST = "abrí onenote, creá una página nueva y ponele de título Lista del super"


def test_v3_08_the_title_goes_to_the_focused_title_without_the_model() -> None:
    model = _Model({"act": "click", "i": 23})
    decision = cu.decide_step(
        model, objective=_V308_REQUEST, goal=_V308, application="OneNote", success_check=None,
        view=copy.deepcopy(_NEW_PAGE), history=[], budget_left=10, application_names=_APPS, subgoal=1, subgoal_count=2,
    )
    assert model.payloads == []
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"] == {"text": "Lista del super", "field": "Título de página"}


def _dictated(view: dict, goal: str = _V308, history: list | None = None) -> dict | None:
    return cu_rules.deterministic_step(goal=goal, view=view, history=history or [], application="OneNote", objective=_V308_REQUEST)


def test_a_title_that_already_holds_text_is_never_written_over() -> None:
    view = copy.deepcopy(_NEW_PAGE)
    view["window"]["focused"]["value"] = "Comprar pan, leche y huevos"
    view["controls"][46]["value"] = "Comprar pan, leche y huevos"
    assert _dictated(view) is None


def test_the_search_box_with_the_keyboard_never_takes_the_title() -> None:
    view = copy.deepcopy(_NEW_PAGE)
    view["window"]["focused"] = {"kind": "Edit", "name": "Búsqueda de Microsoft", "i": 4}
    view["controls"][4]["state"] = "focused"
    view["controls"][46]["state"] = ""
    assert _dictated(view) is None


def test_a_focused_part_the_goal_does_not_name_never_takes_the_text() -> None:
    view = copy.deepcopy(_NEW_PAGE)
    view["window"]["focused"] = {"kind": "Document", "name": "Contenido de la página", "i": 46}
    view["controls"][46]["name"] = "Contenido de la página"
    step = _dictated(view)
    assert step is None or step.get("operation") != "input.text.type"


def test_the_title_is_typed_once() -> None:
    typed = {"step": 1, "operation": "input.text.type", "text": "Lista del super", "field": "Título de página", "ok": True}
    step = _dictated(copy.deepcopy(_NEW_PAGE), history=[typed])
    assert step is None or step.get("operation") != "input.text.type"


def test_the_text_a_goal_puts_in_its_part() -> None:
    assert slot_text("ponele de título Lista del super") == "Lista del super"
    assert slot_text("ponle 'Proyecto final' de título") == "Proyecto final"
    assert slot_text("escribí Hola equipo en el asunto") == "Hola equipo"
    assert slot_text("put Groceries as the title") == "Groceries"
    assert slot_text("ponle eso de título") is None
    assert slot_text("buscá Lista del super") is None
    assert slot_text("ordená la lista por nombre") is None


def test_a_described_or_negated_text_is_never_the_literal_text() -> None:
    """Review of paro-campo, finding 2: a text said as a description (an article, a determiner, a possessive, a
    preposition first) is the model's to write, and one said as what not to put is never written; quoted, it is."""

    for goal in ("ponele de título la fecha de hoy", "ponle de título algo gracioso",
                 "ponele de título el nombre del archivo", "ponle como título lo mismo que el anterior",
                 "write a summary in the title", "escribe en el cuerpo del correo que llego tarde",
                 "escribí un resumen en el cuerpo", "poné tu nombre como nombre", "escribí en el asunto lo que te dije",
                 "no le pongas de título Hola", "don't put Hello as the title", "nunca escribas Hola en el asunto"):
        assert slot_text(goal) is None, goal
    assert slot_text("ponle de título «La fecha de hoy»") == "La fecha de hoy"
    assert slot_text("no te olvides de ponerle de título Hola") == "Hola"
    assert slot_text("type Hello as the subject") == "Hello"


def test_a_described_title_is_left_to_the_model() -> None:
    for goal in ("ponele de título la fecha de hoy", "no le pongas de título Hola", "write a summary in the title"):
        assert _dictated(copy.deepcopy(_NEW_PAGE), goal=goal) is None, goal


# ------------------------------------------------------------------ v3-27/v3-28: el paro dice por qué antes de parar
# Ronda 25 (libro §4.2): la App ya no da «un paso más» tras dos pantallas iguales (0 de 4 en el banco): para con
# computer_use_surface_unchanged (ComputerUseLoopTests). Ninguna marca «stalled» cambia lo que el modelo lee del paso.
def test_no_stalled_mark_changes_what_the_model_reads_of_a_step() -> None:
    step = {"step": 3, "operation": "input.visible.click", "label": "Fuente:", "ok": True}
    line = cu_step_prompt._history_line(step)
    assert cu_step_prompt._history_line({**step, "stalled": True}) == line
    assert "no repitas ninguno" not in line and "type y field" not in line
    assert not hasattr(cu_step_prompt, "STALLED_NOTE")
