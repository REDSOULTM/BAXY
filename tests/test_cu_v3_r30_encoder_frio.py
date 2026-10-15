"""r30: el encoder frío no mata el paso (banco y9, «en Configuración buscá mouse»: 5 de 6 corridas fallidas).

El hecho (evidencia_r28/v2-y9 lograda; cu-universal-evidencia/v2-y9 y evidencia_b3tb/v2-y9 fallidas): la regla pulsa el
cuadro de búsqueda, detrás de la ventana de la persona ese clic no se puede probar
(``visible_button_postread_unchanged``) y el paso 3 quedaba al modelo. En las dos corridas el modelo repitió el clic
y el validador lo vetó igual (``repeated_step``): el veto no depende del encoder. Lo que dependía de E5 era el
reintento: con E5 cargado nombraba «[4] Cuadro de búsqueda…» y no ofrecía ``none`` (el modelo escribió «mouse» en el
campo); con E5 cargando ofrecía ``none`` y el modelo lo tomó. Desde que el primer turno llega antes (paso 3 a ~21 s
del arranque; E5 queda listo a ~27–30 s) eso pasa casi siempre.

Arreglo en el origen: tras ese clic sin efecto, la regla «buscar» escribe en el campo de búsqueda por su rótulo (el
mismo paso que daba el modelo, ``_form_field_arguments``): ni modelo ni encoder. La tecla que sigue la decide v3 sin
tocar. Las vistas son las del paso 3 de y9 como llegan a la mente (reconstruidas del prompt de la corrida fallida).
"""

from __future__ import annotations

import copy
import math

import numpy as np
import pytest

from baxy_mind import computer_use as cu
from baxy_mind import cu_view
from baxy_mind import cu_meaning
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt
from baxy_mind.semantic import cu_semejanza

_BOX = "Cuadro de búsqueda, Buscar una opción"
_OBJECTIVE = "en Configuración buscá mouse"
_CHECK = ("title:mouse&stepDone:input.key.press:enter|title:mouse&stepDone:input.visible.click:mouse|"
          "stepDone:input.text.type&stepDone:input.key.press:enter&text:mouse")


def _control(i: int, kind: str, name: str, state: str = "", zone: str = "C", **more: object) -> dict:
    return {"i": i, "kind": kind, "name": name, "state": state, "zone": zone, **more}


# Step 3 of y9 (cu-universal-evidencia/v2-y9, request 10): Settings behind the person's window, no focus read.
_SETTINGS = {
    "window": {"title": "Configuración", "process": "SystemSettings", "requested": True},
    "controls": [
        _control(0, "Button", "Atrás", "disabled", "TL"),
        _control(1, "Button", "Minimizar Configuración", zone="TR"),
        _control(2, "Button", "Maximizar Configuración", zone="TR"),
        _control(3, "Button", "Cerrar Configuración", zone="TR"),
        _control(4, "Edit", _BOX, zone="T"),
        _control(5, "Button", "Persona Ejemplo persona@ejemplo.com", zone="TL"),
        _control(6, "ListItem", "Inicio", "selected", "TL"),
        _control(7, "ListItem", "Sistema", zone="TL"),
        _control(8, "ListItem", "Bluetooth y dispositivos", zone="TL"),
        _control(9, "ListItem", "Red e Internet", zone="L"),
        _control(10, "ListItem", "Personalización", zone="L"),
        _control(11, "ListItem", "Aplicaciones", zone="L"),
        _control(12, "ListItem", "Cuentas", zone="L"),
        _control(13, "ListItem", "Hora e idioma", zone="L"),
        _control(14, "ListItem", "Juegos", zone="L"),
        _control(15, "ListItem", "Accesibilidad", zone="L"),
        _control(16, "ListItem", "Privacidad y seguridad", zone="BL"),
        _control(17, "ListItem", "Windows Update", zone="BL"),
        _control(18, "Button", "Inicio", zone="T"),
        _control(19, "Hyperlink", "Cambiar nombre", zone="T"),
        _control(20, "Button", "Ethernet Conectado", zone="TR"),
        _control(21, "Button", "Windows Update Última comprobación: hace 1 hora", zone="TR"),
        _control(22, "ListItem", "Puntero del mouse y entrada táctil", zone="B"),
        _control(23, "Text", "Configuración recomendada", zone="C"),
    ],
    "text": {"T": ["Buscar una opción de configuración", "REDNOTE", "Cambiar nombre"],
             "B": ["Puntero del mouse y entrada táctil", "Dispositivos Bluetooth"]},
}
_OPENED = {"step": 1, "operation": "app.open", "appId": "Configuración", "ok": True}
_CLICK_FAILED = {"step": 2, "operation": "input.visible.click", "label": _BOX, "index": 4, "ok": False,
                 "error": "visible_button_postread_unchanged"}
_HISTORY = [_OPENED, _CLICK_FAILED]
_TYPED = {"text": "mouse", "field": _BOX, "replace": True}


class _Loading:
    """E5 still loading: never ready, encoding fails like the router's."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    def try_ready(self, timeout: float = 0.0) -> bool:
        self.waits.append(float(timeout))
        return False

    def __call__(self, texts, *, prefix: str = "query"):
        raise TimeoutError("router worker response timed out")


class _Loaded:
    """E5 loaded: the search box is the one name near «buscar mouse» (0.9), every other name far (0.5)."""

    def __init__(self) -> None:
        self.calls = 0

    def try_ready(self, timeout: float = 0.0) -> bool:
        return True

    def __call__(self, texts, *, prefix: str = "query"):
        self.calls += 1
        angles = [0.0 if prefix == "query" else math.acos(0.9 if text == _BOX else 0.5) for text in texts]
        return np.array([[math.cos(angle), math.sin(angle)] for angle in angles])


class _Model:
    """The local model as it answered live at step 3: the same click again, then what the retry got from it."""

    def __init__(self, *steps: dict) -> None:
        self.steps = list(steps)
        self.prompts: list[list[dict]] = []

    def _post_schema_object(self, payload: dict, label: str) -> object:
        if label == "la traducción de una etiqueta":
            return {"es": [], "en": []}
        if label != "el paso de computer use":
            return {}
        self.prompts.append(copy.deepcopy(payload["messages"]))
        return self.steps.pop(0) if self.steps else {"act": "none"}


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cu_meaning, "_SEMANTIC_CACHE", cu_semejanza.EmbeddingCache())
    monkeypatch.setattr(cu_meaning, "_COLD_WAIT", cu_meaning._ColdWait(cu_meaning.ENCODER_COLD_WAIT_SECONDS))


def _decide(model: _Model, encoder, view: dict = _SETTINGS, history: list[dict] | None = None,
            goal: str = "buscar mouse") -> dict:
    return cu.decide_step(
        model, objective=_OBJECTIVE, goal=goal, application="Configuración", success_check=_CHECK,
        view=copy.deepcopy(view), history=copy.deepcopy(_HISTORY if history is None else history), budget_left=10,
        application_names=["Configuración"], encoder=encoder,
    )


def _validate(raw: dict, encoder) -> dict:
    return cu_validate.validate_decision(
        raw, view=copy.deepcopy(_SETTINGS), history=copy.deepcopy(_HISTORY), last_failed=_CLICK_FAILED,
        application_names=["Configuración"], goal="buscar mouse", objective=_OBJECTIVE, success_check=_CHECK,
        application="Configuración", semantic=cu_meaning.SemanticMatcher(encoder, cu_semejanza.EmbeddingCache()),
    )


# ------------------------------------------------------------------ la causa: qué dependía del encoder


def test_the_validator_gives_the_same_verdict_with_the_encoder_loading_and_loaded() -> None:
    # No veto depends on E5: the model's first act (the same click) is refused as a repeat either way, and the
    # typing it gave on the good run is accepted either way.
    for encoder in (_Loading(), _Loaded()):
        repeated = _validate({"act": "click", "i": 4}, encoder)
        assert repeated["operation"] == "none" and repeated["code"] == "repeated_step", repeated
        typed = _validate({"act": "type", "text": "mouse", "field": _BOX}, encoder)
        assert typed["operation"] == "input.text.type" and typed["arguments"] == _TYPED, typed


def test_what_depended_on_the_encoder_was_the_retry_after_the_veto() -> None:
    # Loaded, the retry names the search box and offers no «none»; loading, it offers «none» (the live «none»).
    similar = cu_step_prompt._similar_controls("buscar mouse", _SETTINGS, ("buscar mouse",), cu_meaning.SemanticMatcher(_Loaded(), cu_semejanza.EmbeddingCache()))
    assert [control["name"] for control in similar][:1] == [_BOX]
    assert "none" not in cu_step_prompt.retry_instruction("repetiría el paso que acaba de fallar", similar)
    loading = cu_meaning.SemanticMatcher(_Loading(), cu_semejanza.EmbeddingCache())
    assert cu_step_prompt._similar_controls("buscar mouse", _SETTINGS, ("buscar mouse",), loading) == []
    assert loading.state == cu_meaning.ENCODER_COLD
    assert cu_step_prompt.retry_instruction("repetiría el paso que acaba de fallar", []).endswith("o none si no hay ninguno.")


# ------------------------------------------------------------------ el arreglo: el paso 3 ya no es del modelo


def test_y9_step_3_with_the_encoder_loading_types_the_search_into_its_field_without_the_model() -> None:
    # Live, cold: the model said «click 4» (refused) and then «none»: computer_use_no_step_visible.
    encoder, model = _Loading(), _Model({"act": "click", "i": 4}, {"act": "none"})
    decided = _decide(model, encoder)
    assert decided["operation"] == "input.text.type" and decided["arguments"] == _TYPED, decided
    assert decided["source"] == cu_meaning.SOURCE_RULE and not model.prompts
    # The step asked the encoder nothing and waited for nothing: the trace says «step.3.input.text.type.rule».
    assert "encoder" not in decided and "encoderMs" not in decided and sum(encoder.waits) == 0.0


def test_y9_step_3_is_the_same_step_with_the_encoder_loaded() -> None:
    encoder, model = _Loaded(), _Model({"act": "click", "i": 4}, {"act": "type", "text": "mouse", "field": _BOX})
    decided = _decide(model, encoder)
    assert decided["operation"] == "input.text.type" and decided["arguments"] == _TYPED
    assert decided["source"] == cu_meaning.SOURCE_RULE and not model.prompts and encoder.calls == 0


def test_the_rule_gives_the_very_step_the_validator_accepts_from_the_model() -> None:
    step = cu_rules.deterministic_step(goal="buscar mouse", view=copy.deepcopy(_SETTINGS), history=copy.deepcopy(_HISTORY),
                                 application="Configuración", objective=_OBJECTIVE, success_check=_CHECK)
    accepted = _validate({"act": "type", "text": "mouse", "field": _BOX}, _Loaded())
    assert step is not None and (step["operation"], step["arguments"]) == (accepted["operation"], accepted["arguments"])


def test_after_the_typing_the_enter_is_v3s_on_the_search_field() -> None:
    # The good run's step 4 (evidencia_r28/v2-y9): after the text the view reads the keyboard on the search box.
    view = copy.deepcopy(_SETTINGS)
    view["window"]["focused"] = {"kind": "Edit", "name": _BOX, "i": 4, "value": "mouse"}
    view["controls"][4] = {**view["controls"][4], "state": "focused", "value": "mouse"}
    history = [*_HISTORY, {"step": 3, "operation": "input.text.type", "text": "mouse", "field": _BOX, "ok": True}]
    for encoder in (_Loading(), _Loaded()):
        model = _Model()
        decided = _decide(model, encoder, view, history)
        assert decided["operation"] == "input.key.press" and decided["arguments"] == {"key": "enter"}, decided
        assert decided["source"] == cu_meaning.SOURCE_RULE and not model.prompts


# ------------------------------------------------------------------ contracasos


def _failed_on(view: dict, label: str, index: int, goal: str = "buscar mouse") -> dict | None:
    history = [_OPENED, {"step": 2, "operation": "input.visible.click", "label": label, "index": index, "ok": False,
                         "error": "visible_button_postread_unchanged"}]
    return cu_rules.deterministic_step(goal=goal, view=view, history=history, application="x", objective=goal)


def test_contracase_the_first_step_of_a_search_is_still_the_click_on_its_field() -> None:
    step = cu_rules.deterministic_step(goal="buscar mouse", view=copy.deepcopy(_SETTINGS), history=[_OPENED],
                                 application="Configuración", objective=_OBJECTIVE, success_check=_CHECK)
    assert step is not None and step["operation"] == "input.visible.click"
    assert step["arguments"] == {"label": _BOX, "index": 4}


def test_contracase_a_search_button_that_did_nothing_is_still_the_models() -> None:
    # A button opens the box: nothing to write into yet, and no blind key after it by this rule.
    view = {"window": {"title": "Tienda", "process": "x"},
            "controls": [_control(0, "Button", "Buscar"), _control(1, "ListItem", "Inicio", "selected")], "text": {}}
    assert _failed_on(view, "Buscar", 0) is None


def test_contracase_a_search_field_that_is_not_written_takes_nothing() -> None:
    for kind, name, state in (
        ("Edit", "Buscar", "readonly"), ("Edit", "Buscar", "disabled"), ("Edit", "Buscar contraseña", "password"),
        ("Document", "Buscar", ""),  # a document is the person's work, whatever its name
    ):
        view = {"window": {"title": "App", "process": "x"},
                "controls": [_control(0, kind, name, state), _control(1, "ListItem", "Inicio", "selected")], "text": {}}
        step = _failed_on(view, name, 0)
        assert step is None or step["operation"] != "input.text.type", (kind, name, state, step)


def test_contracase_the_text_names_its_field_so_it_never_goes_to_another_one_that_has_the_keyboard() -> None:
    # A chat with the keyboard on its message box: the search goes to «Buscar» by its label (the App gives it that
    # field's index and the provider writes there or refuses), never to the focus.
    view = {"window": {"title": "Chat con Juan", "process": "x",
                       "focused": {"kind": "Edit", "name": "Escribe un mensaje", "i": 1, "value": "borrador"}},
            "controls": [_control(0, "Edit", "Buscar"), _control(1, "Edit", "Escribe un mensaje", "focused", value="borrador"),
                         _control(2, "ListItem", "Juan", "selected")], "text": {}}
    step = _failed_on(view, "Buscar", 0, "buscar hades")
    assert step is not None and step["arguments"] == {"text": "hades", "field": "Buscar", "replace": True}


def test_contracase_a_field_that_is_gone_takes_no_text() -> None:
    # v3 untouched: with the field gone the lookup goes on with its next way.
    gone = {"window": {"title": "App", "process": "x"}, "controls": [_control(0, "ListItem", "Inicio", "selected")], "text": {}}
    step = _failed_on(gone, "Buscar", 0)
    assert step is None or step["operation"] != "input.text.type", step


def test_contracase_of_two_fields_of_one_name_only_the_first_is_written_by_its_label() -> None:
    # Review of r30 (H1c). The App gives a label the first field of that name (LabelledField): the text names
    # «Buscar» only when the click that failed was on that first one; after a failure on the second the rule's step
    # is the click on the first, as before, never a text.
    twice = {"window": {"title": "App", "process": "x"},
             "controls": [_control(0, "Edit", "Buscar"), _control(1, "Edit", "Buscar"), _control(2, "ListItem", "Inicio", "selected")],
             "text": {}}
    first = _failed_on(twice, "Buscar", 0)
    assert first is not None and first["arguments"] == {"text": "mouse", "field": "Buscar", "replace": True}
    second = _failed_on(twice, "Buscar", 1)
    assert second is not None and second["operation"] == "input.visible.click"
    assert second["arguments"] == {"label": "Buscar", "index": 0}


@pytest.mark.parametrize("name", ["Escribe un mensaje", "Nombre", "Barra de direcciones y de búsqueda"])
def test_contracase_a_failed_click_on_a_field_that_is_no_search_never_gets_the_text(name: str) -> None:
    # Review of r30 (H1b): the model's click on a message box, a form's field or the address bar failed under
    # «buscar X». No text names that field, with the window's search beside it or alone.
    beside = {"window": {"title": "App", "process": "x"},
              "controls": [_control(0, "Edit", "Buscar"), _control(1, "Edit", name, value="borrador"),
                           _control(2, "ListItem", "Juan", "selected")], "text": {}}
    alone = {"window": {"title": "App", "process": "x"},
             "controls": [_control(0, "ListItem", "Juan", "selected"), _control(1, "Edit", name, value="borrador")], "text": {}}
    for view in (beside, alone):
        step = _failed_on(view, name, 1, "buscar hades")
        assert step is None or step["operation"] != "input.text.type", (name, step)
    # Beside the search, the rule's step is still its click on the search, as before the branch.
    step = _failed_on(beside, name, 1, "buscar hades")
    assert step is not None and step["arguments"] == {"label": "Buscar", "index": 0}


def test_contracase_an_index_that_no_longer_holds_the_failed_control_is_never_written_by_its_label() -> None:
    # Review of r30 (H2): the view was numbered again between two looks. The click that failed was on «Filtrar lista»
    # at 4; that index now holds the window's «Buscar», and «Filtrar lista» lives at 6. ``find_control`` falls back to
    # the label and finds the one at 6: a step that WRITES takes only the control at the index that failed.
    view = {"window": {"title": "App", "process": "x"},
            "controls": [*(_control(i, "ListItem", f"Fila {i}") for i in range(4)), _control(4, "Edit", "Buscar"),
                         _control(5, "ListItem", "Fila 5", "selected"), _control(6, "Edit", "Filtrar lista")], "text": {}}
    retried = cu_rules.deterministic_step(goal="buscar mouse", view=view, history=[_OPENED], application="x", objective="buscar mouse")
    assert retried is not None and retried["arguments"] == {"label": "Buscar", "index": 4}  # the same index: the rule's retry
    assert cu_view.find_control(view, "Filtrar lista", index=4)["i"] == 6
    step = _failed_on(view, "Filtrar lista", 4)
    assert step is None or step["operation"] != "input.text.type", step


# ------------------------------------------------------------------ revisión de r30, H1a: el Enter con un compositor


def _after_the_text(view: dict) -> dict | None:
    history = [_OPENED, {"step": 2, "operation": "input.visible.click", "label": "Buscar", "index": 0, "ok": False,
                         "error": "visible_button_postread_unchanged"},
               {"step": 3, "operation": "input.text.type", "text": "hades", "field": "Buscar", "into": "Buscar", "ok": True}]
    return cu_rules.deterministic_step(goal="buscar hades", view=view, history=history, application="x", objective="buscar hades")


def test_contracase_the_enter_after_the_text_is_asked_with_the_keyboard_read_on_a_message_box() -> None:
    # In front: the keyboard is read on the message box, which holds a draft. The text went to «Buscar» by its label;
    # the Enter that follows could send the draft, so it is marked for RiskPolicy to ask. Never a bare Enter.
    view = {"window": {"title": "Chat con Juan", "process": "x",
                       "focused": {"kind": "Edit", "name": "Escribe un mensaje", "i": 1, "value": "borrador"}},
            "controls": [_control(0, "Edit", "Buscar", value="hades"),
                         _control(1, "Edit", "Escribe un mensaje", "focused", value="borrador"),
                         _control(2, "ListItem", "Juan", "selected")], "text": {}}
    step = _after_the_text(view)
    assert step is not None and step["operation"] == "input.key.press"
    assert step["arguments"] == {"key": "enter", "target": "message_composer"}


def test_contracase_the_enter_after_the_text_is_asked_behind_with_a_message_box_that_shows_no_value() -> None:
    # Behind the person's window: no focus is read and the message box exposes no value (it may hold a draft).
    view = {"window": {"title": "Chat con Ron92", "process": "x"},
            "controls": [_control(0, "Edit", "Buscar", value="hades"), _control(1, "Edit", "Mensaje @Ron92"),
                         _control(2, "ListItem", "Ron92", "selected")], "text": {}}
    step = _after_the_text(view)
    assert step is not None and step["operation"] == "input.key.press"
    assert step["arguments"] == {"key": "enter", "target": "message_composer"}


def test_contracase_a_place_looked_up_after_its_failed_click_is_as_before() -> None:
    # «ir a …» already went on from its whole history (``_find_step``); nothing of that changes.
    view = copy.deepcopy(_SETTINGS)
    step = cu_rules.deterministic_step(goal="ir a fuentes", view=view, history=[_OPENED, {**_CLICK_FAILED}],
                                 application="Configuración", objective="andá a fuentes en Configuración")
    assert step is not None and step["operation"] == "input.text.type" and "field" not in step["arguments"]


def test_contracase_a_failed_typing_into_the_field_is_the_models_next() -> None:
    # The provider refused the text (a field no value reaches without its focus): no rule insists.
    history = [*_HISTORY, {"step": 3, "operation": "input.text.type", "text": "mouse", "field": _BOX, "ok": False,
                           "error": "input_field_not_reachable"}]
    assert cu_rules.deterministic_step(goal="buscar mouse", view=copy.deepcopy(_SETTINGS), history=history,
                                 application="Configuración", objective=_OBJECTIVE, success_check=_CHECK) is None
