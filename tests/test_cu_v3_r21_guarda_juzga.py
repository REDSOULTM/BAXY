"""Ronda 21, palanca «guarda-juzga-lo-que-el-acto-altera» (pasada r18: v3-36, v3-59, t-scroll-4, t-form-3).

Gemelos con las vistas de la evidencia (journal y model_calls de cu-universal-evidencia/v2-<caso>) y sus contracasos:
sobre el contenido de un documento el atajo ciego es ctrl_f y nunca ctrl_k; una página de sólo lectura no es contenido;
la tecla de una regla que la guarda del App rechazó pasa al modelo; una meta que es ruta nunca cae al buscador; un paso
de regla nunca repite el que acaba de fallar. La negativa search_box_not_target sin parte nombrada (t-form-3) se retiró
en la revisión 3: el buscador de otra aplicación es el único camino a un contacto, una imagen, un correo o un archivo
que no está a la vista, y una lista de palabras de la meta no distingue eso de un valor.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind.semantic.missions import fold as missions_fold
from baxy_mind import computer_use as cu
from baxy_mind import cu_vocabulary
from baxy_mind import cu_history
from baxy_mind import cu_meaning
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_diagnosis
from baxy_mind import cu_validate

_DIRECCION = json.loads((Path(__file__).parent / "data" / "cu_v3_vistas_direccion.json").read_text(encoding="utf-8"))


def _rect(x: int, y: int, w: int, h: int) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


# ------------------------------------------------------------------ v3-36: la nota de la persona, ctrl_f y nunca ctrl_k

def _note() -> dict:
    # Journal seq 1584: Microsoft.Notes, others [], the Edit «Editor de notas» of 382×350 in a window of 384×392, with
    # no «Menú» and no search.
    return {
        "window": {"title": "Notas rápidas", "process": "Microsoft.Notes", "rect": _rect(0, 0, 384, 392), "focused": None},
        "controls": [
            {"i": 0, "kind": "Edit", "name": "Editor de notas", "state": "", "value": "baxy prueba",
             "rect": _rect(1, 40, 382, 350), "zone": "C"},
        ],
        "text": {},
    }


def test_v3_36_over_a_notes_editor_the_blind_shortcut_is_the_find() -> None:
    view = _note()
    assert cu_lookup.document_content(view)
    step = cu_rules.deterministic_step(goal="buscar dentista", view=view, history=[])
    assert step is not None and step["operation"] == "input.key.press" and step["arguments"] == {"key": "ctrl_f"}
    # ctrl_f did nothing there: no ctrl_k after it, never on an editor.
    tried = [{"step": 1, "operation": "input.key.press", "key": "ctrl_f", "ok": True, "changed": False, "sameView": True}]
    after = cu_rules.deterministic_step(goal="buscar dentista", view=view, history=tried)
    assert after is None or after.get("arguments", {}).get("key") != "ctrl_k"


def test_contracase_a_chat_without_a_document_covering_it_keeps_ctrl_k_first() -> None:
    # Discord or Slack: the web root read-only, the composer a small field: the quick switcher (ctrl_k) first.
    chat = {
        "window": {"title": "#general | Servidor - Discord", "process": "Discord", "rect": _rect(0, 0, 1400, 900), "focused": None},
        "controls": [
            {"i": 0, "kind": "Document", "name": "Discord", "state": "readonly", "rect": _rect(0, 30, 1400, 870)},
            {"i": 1, "kind": "Edit", "name": "Enviar mensaje a #general", "state": "", "rect": _rect(300, 820, 1000, 40)},
        ],
        "text": {},
    }
    assert not cu_lookup.document_content(chat)
    step = cu_rules.deterministic_step(goal="ir a anuncios", view=chat, history=[])
    assert step is not None and step["arguments"] == {"key": "ctrl_k"}


def test_v3_59_a_read_only_page_is_no_document_content_and_a_draft_is() -> None:
    page = {
        "window": {"title": "Microsoft Support - Microsoft Edge", "process": "msedge", "rect": _rect(0, 0, 1600, 900),
                   "focused": {"kind": "Document", "name": "Microsoft Support", "state": "readonly focused"}},
        "controls": [
            {"i": 2, "kind": "Document", "name": "Microsoft Support", "state": "readonly focused", "rect": _rect(0, 80, 1600, 820)},
        ],
        "text": {},
    }
    assert not cu_lookup.document_content(page)
    draft = copy.deepcopy(page)
    draft["controls"].append({"i": 3, "kind": "Edit", "name": "Cuerpo del mensaje", "state": "focused",
                              "value": "Hola", "rect": _rect(300, 200, 1000, 600)})
    assert cu_lookup.document_content(draft)


def test_the_shared_key_classes_say_what_alters_the_content() -> None:
    assert "ctrl_f" in cu_vocabulary.CONTENT_KEEPING_KEYS and "ctrl_k" not in cu_vocabulary.CONTENT_KEEPING_KEYS
    for key in ("ctrl_a", "delete", "backspace", "ctrl_v", "enter"):
        assert key not in cu_vocabulary.CONTENT_KEEPING_KEYS


# ------------------------------------------------------------------ v3-36: la tecla rechazada por la guarda pasa al modelo

class _Model:
    """A model that answers one fixed act and counts the calls."""

    def __init__(self, act: dict) -> None:
        self.act = act
        self.calls = 0

    def _post_schema_object(self, payload: dict, what: str) -> dict:
        self.calls += 1
        return dict(self.act)


def _decide(model: _Model, view: dict, history: list[dict], goal: str = "buscar dentista") -> dict:
    return cu.decide_step(
        model, objective=f"en notas rápidas {goal}", goal=goal, application="Notas rápidas", success_check=None,
        view=view, history=history, budget_left=10, application_names=("Notas rápidas",),
    )


_REFUSED = {"step": 1, "operation": "input.key.press", "key": "ctrl_k", "ok": False, "error": "document_not_named",
            "source": "rule", "refused": True}


def test_v3_36_a_refused_rule_key_hands_the_next_step_to_the_model() -> None:
    model = _Model({"act": "none", "why": "no hay buscador en la nota"})
    step = _decide(model, _note(), [_REFUSED])
    assert model.calls >= 1, "the model was not asked"
    assert step.get("source") == cu_meaning.SOURCE_MODEL
    assert cu_diagnosis.refused_by_the_guard([_REFUSED])


def test_contracase_a_failed_step_that_was_no_refusal_keeps_the_rule() -> None:
    # A rule whose last step was another act that failed dictates as before (the find), the model not asked.
    failed = {"step": 1, "operation": "input.visible.click", "label": "Inicio", "ok": False, "error": "visible_button_not_found"}
    assert not cu_diagnosis.refused_by_the_guard([failed])
    assert not cu_diagnosis.refused_by_the_guard([{**_REFUSED, "refused": None}])
    model = _Model({"act": "none"})
    step = _decide(model, _note(), [failed])
    assert model.calls == 0 and step.get("source") == cu_meaning.SOURCE_RULE


# ------------------------------------------------------------------ t-scroll-4: una ruta nunca cae al buscador

GOAL_EXPLORER = "ir a c:\\windows\\system32"


def _explorer() -> dict:
    return copy.deepcopy(_DIRECCION["explorador_este_equipo"]["vista"])


def test_t_scroll_4_a_path_whose_address_field_left_the_view_is_the_models() -> None:
    # Seq 46 ctrl_l, seq 57-61 the click on «Barra de direcciones» landed on a crumb and navigated; the field is gone.
    history = [
        {"step": 1, "operation": "input.key.press", "key": "ctrl_l", "ok": True, "changed": True},
        {"step": 2, "operation": "input.visible.click", "label": "Barra de direcciones", "index": 59, "ok": True, "changed": True},
    ]
    step = cu_rules.deterministic_step(goal=GOAL_EXPLORER, view=_explorer(), history=history)
    assert step is None


def test_contracase_a_search_in_a_folder_keeps_the_search_box() -> None:
    step = cu_rules.deterministic_step(goal="buscar calc.exe", view=_explorer(), history=[])
    assert step is not None and step["operation"] == "input.visible.click"
    assert "buscar" in missions_fold(step["arguments"].get("label"))


def test_t_scroll_4_a_rule_never_repeats_the_step_that_just_failed() -> None:
    click = {"operation": "input.visible.click", "arguments": {"label": "Buscar en usuario", "index": 7}, "reason": "x"}
    failed = {"step": 3, "operation": "input.visible.click", "label": "Buscar en usuario", "index": 7, "ok": False,
              "error": "visible_click_postread_invalid"}
    assert cu_diagnosis.repeats_the_failed_step(click, [failed])
    # Contracases: the last step was another act that failed, or the same act that did not fail.
    other = {**failed, "label": "Descargas", "index": 9}
    assert not cu_diagnosis.repeats_the_failed_step(click, [other])
    assert not cu_diagnosis.repeats_the_failed_step(click, [{**failed, "ok": True}])
    assert not cu_diagnosis.repeats_the_failed_step(None, [failed])


def _search_view(kind: str) -> dict:
    return {
        "window": {"title": "usuario - Explorador de archivos", "process": "explorer", "rect": _rect(0, 0, 1200, 800), "focused": None},
        "controls": [
            {"i": 7, "kind": kind, "name": "Buscar en usuario", "state": "", "rect": _rect(900, 60, 280, 30), "zone": "TR"},
            {"i": 9, "kind": "ListItem", "name": "Descargas", "state": "", "rect": _rect(200, 200, 200, 30), "zone": "C"},
        ],
        "text": {},
    }


def _after_the_failed_search_click(kind: str) -> tuple[dict, "_Model"]:
    view = _search_view(kind)
    dictated = cu_rules.deterministic_step(goal="buscar informe", view=view, history=[])
    assert dictated is not None and dictated["operation"] == "input.visible.click"
    failed = {"step": 1, "operation": "input.visible.click", "label": dictated["arguments"]["label"],
              "index": dictated["arguments"].get("index"), "ok": False, "error": "visible_click_postread_invalid"}
    model = _Model({"act": "none", "why": "no veo otro camino"})
    step = cu.decide_step(
        model, objective="en el explorador buscá informe", goal="buscar informe", application="Explorador de archivos",
        success_check=None, view=view, history=[failed], budget_left=10, application_names=("Explorador de archivos",),
    )
    return step, model


def test_t_scroll_4_decide_asks_the_model_instead_of_repeating_a_failed_rule_click() -> None:
    # A search button that did nothing: the rule has no other step of its own, the model decides.
    step, model = _after_the_failed_search_click("Button")
    assert model.calls >= 1 and step.get("source") == cu_meaning.SOURCE_MODEL


def test_r30_a_failed_click_on_the_search_field_is_followed_by_the_typing_into_it_never_by_the_same_click() -> None:
    # Rewritten in r30 (it asked the model here too). Banco y9, five of six runs: the model repeated the click, was
    # refused, and its retry typed into the field only when a loaded E5 named it; while E5 loaded it said «none».
    # The field is on the view and takes the search by its label: the rule's step, never the same click again.
    step, model = _after_the_failed_search_click("Edit")
    assert step["operation"] == "input.text.type" and step.get("source") == cu_meaning.SOURCE_RULE and model.calls == 0
    assert step["arguments"] == {"text": "informe", "field": "Buscar en usuario", "replace": True}


# ------------------------------------------------------------------ t-form-3: el buscador del documento no es el campo

_WORD = {
    "window": {"title": "Documento1 - Word", "process": "WINWORD", "focused": None},
    "controls": [
        {"i": 3, "kind": "Edit", "name": "Buscar en documento", "state": "", "zone": "T"},
        {"i": 12, "kind": "TabItem", "name": "Insertar", "state": "selected", "zone": "T"},
    ],
    "text": {},
}


def _check(raw: dict, goal: str) -> dict:
    return cu_validate.validate_decision(
        raw, view=copy.deepcopy(_WORD), last_failed=None, application_names=("Word",), history=[], goal=goal,
        objective=f"en word {goal}", application="Word",
    )


def test_contracase_a_search_in_the_document_still_types_into_its_search_box() -> None:
    decision = _check({"act": "type", "text": "Informe", "field": "Buscar en documento"}, "buscar Informe en el documento")
    assert decision["operation"] == "input.text.type"
    assert decision["arguments"]["text"] == "Informe"


# ------------------------------------------------------------------ revisión 1: hallazgos d, e y b

class _Cold:
    """An E5 worker still loading."""

    def try_ready(self, timeout: float = 0.0) -> bool:
        return False

    def __call__(self, texts, *, prefix="query"):
        raise TimeoutError("router worker response timed out")


def _failed_encoder(texts, *, prefix="query"):
    raise TimeoutError("interactive encoder budget expired")


def _ready_encoder(texts, *, prefix="query"):
    return [[1.0] + [0.0] * 7 for _ in texts]


_GOAL_REPORT = "ir a informe"


def _report_history() -> list[dict]:
    # The rule clicked «informe» by its name (it failed), then the window's search «Buscar en Este», whose click failed.
    return [
        {"step": 1, "operation": "input.visible.click", "label": "informe", "ok": False,
         "error": "visible_click_postread_invalid"},
        {"step": 2, "operation": "input.visible.click", "label": "Buscar en Este", "ok": False,
         "error": "visible_click_postread_invalid"},
    ]


def _decide_explorer(model: _Model, history: list[dict], encoder) -> dict:
    return cu.decide_step(
        model, objective=f"en el explorador {_GOAL_REPORT}", goal=_GOAL_REPORT, application="Explorador de archivos",
        success_check=None, view=_explorer(), history=history, budget_left=10,
        application_names=("Explorador de archivos",), encoder=encoder,
    )


@pytest.mark.parametrize("encoder", [_ready_encoder, _Cold(), _failed_encoder], ids=["ready", "cold", "failed"])
def test_finding_d_the_fallback_after_the_models_none_never_repeats_the_failed_rule_click(encoder) -> None:
    history = _report_history()
    # The rule would repeat the failed click: the case the fallback hid.
    literal = cu_rules.deterministic_step(goal=_GOAL_REPORT, view=_explorer(), history=history)
    assert literal is not None and cu_diagnosis.repeats_the_failed_step(literal, history)
    model = _Model({"act": "none", "why": "no veo otro camino"})
    step = _decide_explorer(model, history, encoder)
    assert model.calls >= 1
    assert not cu_diagnosis.repeats_the_failed_step(step, history), step


@pytest.mark.parametrize("encoder", [_ready_encoder, _Cold()], ids=["ready", "cold"])
def test_contracase_finding_d_the_fallback_still_takes_the_rule_after_another_failed_act(encoder) -> None:
    # The last failure was the click on «informe»: the window's search is the fallback as before.
    history = _report_history()[:1]
    model = _Model({"act": "none", "why": "no veo otro camino"})
    step = _decide_explorer(model, history, encoder)
    assert step["operation"] == "input.visible.click" and step["arguments"].get("label") == "Buscar en Este", step
    assert step.get("source") == cu_meaning.SOURCE_RULE


def test_finding_d_after_a_refused_key_the_fallback_takes_no_rule_step() -> None:
    model = _Model({"act": "none", "why": "no hay buscador en la nota"})
    step = cu.decide_step(
        model, objective="en notas rápidas buscar dentista", goal="buscar dentista", application="Notas rápidas",
        success_check=None, view=_note(), history=[_REFUSED], budget_left=10, application_names=("Notas rápidas",),
        encoder=_ready_encoder,
    )
    assert model.calls >= 1 and step["operation"] == "none" and step.get("source") == cu_meaning.SOURCE_MODEL, step


def _settings() -> dict:
    return {
        "window": {"title": "Configuración", "process": "SystemSettings", "rect": _rect(0, 0, 1200, 800), "focused": None},
        "controls": [
            {"i": 2, "kind": "Edit", "name": "Buscar una configuración", "state": "", "rect": _rect(20, 100, 300, 32),
             "zone": "TL"},
            {"i": 5, "kind": "ListItem", "name": "Personalización", "state": "", "rect": _rect(20, 300, 300, 32),
             "zone": "L"},
        ],
        "text": {},
    }


def _typed_in_settings(goal: str, text: str) -> dict:
    return cu_validate.validate_decision(
        {"act": "type", "text": text, "field": "Buscar una configuración"}, view=_settings(), last_failed=None,
        application_names=("Configuración",), history=[], goal=goal, objective=f"en configuración {goal}",
        application="Configuración",
    )


@pytest.mark.parametrize("goal,text", [
    ("ir a fuentes", "fuentes"), ("go to fonts", "fonts"),
    ("activar modo oscuro", "modo oscuro"), ("turn on dark mode", "dark mode"),
    ("escribir hola en el buscador", "hola"), ("type hello in the search box", "hello"),
    ("escribir hola en buscar una configuración", "hola"),
    ("consultar sonido", "sonido"), ("averiguar la versión", "versión"), ("look up sound", "sound"),
    ("look for sound", "sound"),
])
def test_finding_e_the_search_box_takes_a_place_a_lookup_or_a_goal_naming_it_in_both_languages(goal, text) -> None:
    decision = _typed_in_settings(goal, text)
    assert decision["operation"] == "input.text.type", (goal, decision)


def test_finding_e_go_to_fonts_types_into_the_settings_search_through_decide_step() -> None:
    model = _Model({"act": "type", "text": "fonts", "field": "Buscar una configuración"})
    step = cu.decide_step(
        model, objective="in settings go to fonts", goal="go to fonts", application="Configuración", success_check=None,
        view=_settings(), history=[{"step": 1, "operation": "input.visible.click", "label": "fonts", "ok": False,
                                    "error": "visible_button_not_found"}],
        budget_left=10, application_names=("Configuración",),
    )
    assert step.get("code") != "search_box_not_target", step


def test_finding_b_a_refused_key_is_spent_for_the_rule_and_the_model() -> None:
    own, spent = cu_history.spent_steps([_REFUSED])
    assert own == [_REFUSED] and spent == (("ctrl_k", ""),)
    # After another step the rule never presses ctrl_k again on that application.
    later = [_REFUSED, {"step": 2, "operation": "input.visible.click", "label": "Editor de notas", "ok": True,
                        "changed": False}]
    model = _Model({"act": "key", "key": "ctrl_k", "why": "buscar"})
    step = _decide(model, _note(), later)
    assert not (step["operation"] == "input.key.press" and step["arguments"].get("key") == "ctrl_k"), step
    # Nor the model: its ctrl_k is refused as spent.
    token = cu_history._SPENT_KEYS.set(cu_history.spent_steps(later)[1])
    try:
        decision = cu_validate.validate_decision(
            {"act": "key", "key": "ctrl_k"}, view=_note(), last_failed=None, application_names=("Notas rápidas",),
            history=later, goal="buscar dentista", objective="en notas rápidas buscar dentista",
            application="Notas rápidas",
        )
        assert cu_diagnosis.presses_a_spent_key({"operation": "input.key.press", "arguments": {"key": "ctrl_k"}}, _note())
    finally:
        cu_history._SPENT_KEYS.reset(token)
    assert decision["operation"] == "none" and decision["code"] == "key_spent"


def test_contracase_finding_b_a_key_spent_on_another_application_is_pressed_here() -> None:
    elsewhere = {"step": 1, "operation": "input.key.press", "key": "ctrl_k", "ok": False, "spent": True, "process": "WINWORD"}
    own, spent = cu_history.spent_steps([elsewhere])
    assert own == [] and spent == (("ctrl_k", "winword"),)
    token = cu_history._SPENT_KEYS.set(spent)
    try:
        assert "ctrl_k" not in cu_history._spent_keys(_note())
        assert not cu_diagnosis.presses_a_spent_key({"operation": "input.key.press", "arguments": {"key": "ctrl_k"}}, _note())
    finally:
        cu_history._SPENT_KEYS.reset(token)


# ------------------------------------------------------------------ revisión 2: el buscador juzga lo que se escribe

# Revisión 2 (hallazgo e): a free goal of opening, changing, showing, seeing, setting or uninstalling a setting looks its
# place up in the settings search, whatever verb the goal starts with (in fable/cu-universal-v3 the same step was
# input.text.type in one call; the verb list of revisión 1 refused it and the mission stopped).
_FREE_GOALS = [
    ("abrir fuentes", "fuentes"), ("open fonts", "fonts"), ("cambiar el fondo de pantalla", "fondo de pantalla"),
    ("mostrar la configuración de pantalla", "pantalla"), ("show display settings", "display"),
    ("cambiar a modo oscuro", "modo oscuro"), ("poner el tema oscuro", "tema oscuro"),
    ("ver el almacenamiento", "almacenamiento"), ("abrir la sección de sonido", "sonido"),
    ("configurar el mouse", "mouse"), ("ajustar el brillo", "brillo"), ("elegir modo oscuro", "modo oscuro"),
    ("desinstalar Reproductor multimedia", "Reproductor multimedia"), ("uninstall Media Player", "Media Player"),
    ("cambiar el nombre del equipo", "nombre del equipo"), ("rename this pc", "rename"),
]


@pytest.mark.parametrize("goal,text", _FREE_GOALS)
def test_finding_e_rev2_a_free_goal_looks_its_place_up_in_the_settings_search(goal, text) -> None:
    decision = _typed_in_settings(goal, text)
    assert decision["operation"] == "input.text.type" and decision["arguments"]["text"] == text, (goal, decision)


@pytest.mark.parametrize("goal,text", _FREE_GOALS[:13])
def test_finding_e_rev2_the_free_goal_is_never_stopped_through_decide_step(goal, text) -> None:
    # As in fable/cu-universal-v3 (measured: the same step there): the model's lookup is typed, or a rule's step comes
    # first (a scroll toward «la configuración de pantalla»); never a none that stops the mission.
    model = _Model({"act": "type", "text": text, "field": "Buscar una configuración"})
    step = cu.decide_step(
        model, objective=f"en configuración {goal}", goal=goal, application="Configuración", success_check=None,
        view=_settings(), history=[], budget_left=10, application_names=("Configuración",),
    )
    assert step["operation"] != "none" and step.get("code") != "search_box_not_target", (goal, step)
    if step.get("source") == cu_meaning.SOURCE_MODEL:
        assert step["operation"] == "input.text.type" and step["arguments"]["text"] == text, (goal, step)


def test_contracase_finding_e_rev2_a_search_or_the_named_box_still_takes_a_value() -> None:
    # The value rule never overrides a search, a lookup or the box named as where the text goes.
    for goal, text in (("buscar 4", "4"), ("escribir hola en el buscador", "hola"), ("type 4 in the search box", "4")):
        decision = _typed_in_settings(goal, text)
        assert decision["operation"] == "input.text.type", (goal, decision)


# ------------------------------------------------------------------ revisión 3: el buscador de selección no se corta

# Revisión 3 (regresión de la revisión 2, hallazgo e): en el buscador de otras aplicaciones el texto es el contacto, la
# imagen, el correo o el archivo que la meta busca para elegirlo, aunque la meta lo diga tras «escribir», «llamar»,
# «insertar», «asunto» o «nombre». En fable/cu-universal-v3 (9a042bdf5) cada uno era input.text.type; la negativa sin
# parte nombrada se retiró y cada uno vuelve a escribirse, por validate_decision y por decide_step.
_SELECTION_SEARCHES = [
    ("Chat", "Buscar o empezar un chat nuevo", "escribirle a Juan que llego tarde", "Juan"),
    ("Chat", "Buscar o empezar un chat nuevo", "escribir a Juan: llego tarde", "Juan"),
    ("Chat", "Buscar o empezar un chat nuevo", "write to John that I'm late", "John"),
    ("Chat", "Buscar o empezar un chat nuevo", "llamar a Juan", "Juan"),
    ("Chat", "Buscar", "llamar a Ana por videollamada", "Ana"),
    ("Documento1", "Buscar en Bing", "insertar una imagen de gatos", "gatos"),
    ("Documento1", "Buscar iconos", "insert an icon of a cat", "cat"),
    ("Servidor", "Buscar en Tenor", "insertar un gif de gato", "gato"),
    ("Correo", "Buscar", "abrir el correo con asunto Factura", "Factura"),
    ("Mail", "Buscar", "open the email with subject Invoice", "Invoice"),
    ("Descargas", "Buscar en Descargas", "abrir el archivo de nombre informe", "informe"),
    ("Descargas", "Buscar en Descargas", "abrir el archivo con nombre factura", "factura"),
]


def _selection_view(title: str, box: str) -> dict:
    return {
        "window": {"title": title, "process": "app", "rect": _rect(0, 0, 1200, 800), "focused": None},
        "controls": [
            {"i": 2, "kind": "Edit", "name": box, "state": "", "rect": _rect(20, 60, 400, 32), "zone": "TL"},
            {"i": 5, "kind": "ListItem", "name": "Inicio", "state": "", "rect": _rect(20, 300, 300, 32), "zone": "L"},
        ],
        "text": {},
    }


@pytest.mark.parametrize("title,box,goal,text", _SELECTION_SEARCHES)
def test_review_3_the_search_box_of_a_selection_takes_what_the_goal_seeks(title, box, goal, text) -> None:
    decision = cu_validate.validate_decision(
        {"act": "type", "text": text, "field": box}, view=_selection_view(title, box), last_failed=None,
        application_names=(title,), history=[], goal=goal, objective=goal, application=title,
    )
    assert decision["operation"] == "input.text.type" and decision["arguments"]["text"] == text, (goal, decision)


@pytest.mark.parametrize("title,box,goal,text", _SELECTION_SEARCHES)
def test_review_3_the_selection_search_never_stops_the_mission_through_decide_step(title, box, goal, text) -> None:
    model = _Model({"act": "type", "text": text, "field": box})
    step = cu.decide_step(
        model, objective=goal, goal=goal, application=title, success_check=None, view=_selection_view(title, box),
        history=[], budget_left=10, application_names=(title,),
    )
    assert step["operation"] != "none" and step.get("code") != "search_box_not_target", (goal, step)
    if step.get("source") == cu_meaning.SOURCE_MODEL:
        assert step["operation"] == "input.text.type" and step["arguments"]["text"] == text, (goal, step)
