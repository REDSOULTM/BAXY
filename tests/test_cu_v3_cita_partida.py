"""Ronda 20 P6, la parte de la mente (pasada r18: v3-15, v3-16).

v3-16 (model_calls request 8): el done citó «paisaJe.Jpg | Restablecer | 9», literalmente la línea «texto TL» que
``compact_view_text`` escribe uniendo las líneas de una zona con « | », y se rechazó porque ``view_contains`` une con
un espacio. Una cita partida está en la vista cuando cada trozo lo está; lo visto al empezar y el acto con efecto exigen
que al menos un trozo sea nuevo. v3-15: «Parecidos al objetivo: [7] Ocupado» propuso pulsar una ProgressBar.
La vista es la que el modelo vio (v2-v3-16, paso 3), recortada a lo que se juzga.
"""

from __future__ import annotations

from baxy_mind import cu_view
from baxy_mind import cu_first_look
from baxy_mind import cu_validate
from baxy_mind import cu_step_prompt

# v2-v3-16, paso 3: el marco con su cromo y lo que el OCR leyó del editor.
_EDITOR_SEEN = {
    "window": {"title": "paisaje.jpg", "process": "Photos"},
    "controls": [
        {"i": 0, "kind": "Button", "name": "Minimize", "zone": "TR"},
        {"i": 1, "kind": "Button", "name": "Maximize", "zone": "TR"},
        {"i": 2, "kind": "Button", "name": "Close", "zone": "TR"},
        {"i": 3, "kind": "Button", "name": "Atrás", "zone": "TL"},
        {"i": 4, "kind": "MenuItem", "name": "Sistema", "state": "collapsed", "zone": "TL"},
        {"i": 5, "kind": "Pane", "name": "Non Client Input Sink Window", "zone": "T"},
        {"i": 6, "kind": "Pane", "name": "AppWindow Custom Title Bar", "zone": "TR"},
        {"i": 7, "kind": "Text", "name": "paisaje.jpg", "zone": "TL"},
        {"i": 8, "kind": "TitleBar", "name": "paisaje.jpg", "zone": "T"},
        {"i": 9, "kind": "MenuBar", "name": "Barra de menús del sistema", "zone": "TL"},
    ],
    "text": {
        "TL": ["paisaJe.Jpg", "Restablecer", "9"],
        "TR": ["Opciones para guardar v'", "Opciones para guardar v", "Cancelar"],
        "C": ["16:9"],
        "B": ["1920x 1080", "1920 x 1080", "Libre"],
    },
}

_GOAL_PLACE = "ir a editor de la imagen que tengo abierta"
_GOAL_ACT = "girar la imagen a la derecha"


def _rotated(first_look: str | None = None) -> dict:
    view = {
        "window": {"title": "paisaje.jpg", "process": "Photos"},
        "controls": [{"i": 0, "kind": "Button", "name": "Girar en el sentido de las agujas del reloj", "zone": "T"}],
        "text": {"TL": ["paisaJe.Jpg", "Restablecer", "90°"], "TR": ["Cancelar"]},
    }
    if first_look is not None:
        view["firstLook"] = first_look
    return view


def _before_rotation() -> str:
    view = {
        "window": {"title": "paisaje.jpg", "process": "Photos"},
        "controls": [{"i": 0, "kind": "Button", "name": "Girar en el sentido de las agujas del reloj", "zone": "T"}],
        "text": {"TL": ["paisaJe.Jpg", "Restablecer", "0°"], "TR": ["Cancelar"]},
    }
    return "\n".join(cu_first_look.look_parts(view))


_ROTATE = {
    "step": 1, "operation": "input.visible.click", "ok": True, "label": "Girar en el sentido de las agujas del reloj",
    "surfaceChanged": True, "changed": True,
}


def _validate(raw: dict, view: dict, history: list[dict], goal: str) -> dict:
    return cu_validate.validate_decision(raw, view=view, last_failed=None, application_names=(), history=history, goal=goal)


def test_the_listing_joins_a_zones_lines_as_the_cited_line() -> None:
    assert "texto TL: paisaJe.Jpg | Restablecer | 9" in cu_step_prompt.compact_view_text(_EDITOR_SEEN)


def test_v3_16_a_whole_listed_line_is_in_the_view() -> None:
    assert cu_view.view_contains(_EDITOR_SEEN, "paisaJe.Jpg | Restablecer | 9")
    assert cu_view.view_contains(_EDITOR_SEEN, "Restablecer | 16:9")
    assert cu_view.citation_pieces(" paisaJe.Jpg | Restablecer |9 ") == ["paisaJe.Jpg", "Restablecer", "9"]
    assert cu_view.citation_pieces("Restablecer") == ["Restablecer"]


def test_v3_16_the_done_citing_the_line_reaches_the_editor() -> None:
    history = [
        {"step": 1, "operation": "app.open", "appId": "Fotos", "ok": True},
        {"step": 2, "operation": "input.visible.click", "label": "Editar", "ok": True, "surfaceChanged": True},
    ]
    decision = _validate({"act": "done", "evidence": "paisaJe.Jpg | Restablecer | 9"}, _EDITOR_SEEN, history, _GOAL_PLACE)
    assert decision["operation"] == "done"
    assert decision["arguments"]["evidence"] == "paisaJe.Jpg | Restablecer | 9"


def test_counter_case_a_piece_the_view_lacks_is_refused() -> None:
    assert not cu_view.view_contains(_EDITOR_SEEN, "paisaJe.Jpg | Filtros")
    assert not cu_view.view_contains(_EDITOR_SEEN, "Restablecer | Monocromo | 9")
    decision = _validate({"act": "done", "evidence": "Restablecer | Monocromo"}, _EDITOR_SEEN, [], _GOAL_PLACE)
    assert decision["operation"] == "none"


def test_a_split_citation_proves_an_act_when_one_piece_is_new() -> None:
    view = _rotated(_before_rotation())
    decision = _validate({"act": "done", "evidence": "Restablecer | 90°"}, view, [_ROTATE], _GOAL_ACT)
    assert decision["operation"] == "done"


def test_counter_case_every_piece_seen_before_the_act_is_refused() -> None:
    view = _rotated(_before_rotation())
    decision = _validate({"act": "done", "evidence": "paisaJe.Jpg | Restablecer"}, view, [_ROTATE], _GOAL_ACT)
    assert decision["operation"] == "none"
    assert decision.get("code") == "evidence_not_visible"


def test_counter_case_a_new_piece_without_an_act_proves_nothing() -> None:
    view = _rotated(_before_rotation())
    decision = _validate({"act": "done", "evidence": "Restablecer | 90°"}, view, [], _GOAL_ACT)
    assert decision["operation"] == "none"


class _AnyMatcher:
    """A matcher whose scores are not read: ``similar_hints`` is replaced by the names the test hands it."""

    def scored(self, label, view, others):
        return []


def test_v3_15_a_busy_indicator_or_a_status_bar_is_never_similar(monkeypatch) -> None:
    view = {
        "window": {"title": "paisaje.jpg", "process": "Photos"},
        "controls": [
            {"i": 3, "kind": "Button", "name": "Atrás", "zone": "TL"},
            {"i": 7, "kind": "ProgressBar", "name": "Ocupado", "zone": "C"},
            {"i": 8, "kind": "StatusBar", "name": "Listo", "zone": "B"},
            {"i": 9, "kind": "Button", "name": "Girar", "zone": "T"},
        ],
        "text": {},
    }
    monkeypatch.setattr(cu_step_prompt, "similar_hints", lambda scored, usable: ["Ocupado", "Listo", "Girar"])
    names = [control["name"] for control in cu_step_prompt._similar_controls("girar la imagen a la derecha", view, (), _AnyMatcher())]
    assert names == ["Girar"]
