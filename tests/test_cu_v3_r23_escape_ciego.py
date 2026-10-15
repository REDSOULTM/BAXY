"""Ronda 23 (g1, comprobación en vivo r21): after a search shortcut, a look read behind the person's window of a window
drawn without an accessible tree tells neither where the keyboard is nor what the key brought up. No Escape and no
next shortcut is pressed blind on it; a written proof (a search line that appeared) is still followed, and a look in
front or a window whose tree reads behind keeps the old way."""

from __future__ import annotations

from baxy_mind import cu_lookup
from baxy_mind import cu_rules


def _ok(step: int, operation: str, **fields: object) -> dict:
    return {"step": step, "operation": operation, "ok": True, **fields}


# A library drawn by a web view: one pane, no focus, the search box only a magnifier.
WEB_VIEW = {
    "window": {"title": "Biblioteca", "process": "webhelper", "focused": None, "foreground": True},
    "controls": [{"i": 0, "kind": "Pane", "name": "Chrome Legacy Window", "state": ""}],
    "text": {
        "TL": ["TIENDA BIBLIOTECA COMUNIDAD", "Página principal", "Juegos y Software"],
        "L": ["A Story About My Uncle", "Alan Wake"],
    },
}


def _behind(view: dict) -> dict:
    return {**view, "window": {**view["window"], "foreground": False}}


def _step(view: dict, key: str) -> dict | None:
    return cu_rules.deterministic_step(goal="buscar Cuphead", view=view, history=[_ok(1, "input.key.press", key=key)])


def test_g1_a_blind_look_behind_gets_no_escape_after_a_search_key() -> None:
    for key in ("ctrl_k", "ctrl_f"):
        # No «newText» at all: «!= []» no longer makes it an Escape.
        assert _step(_behind(WEB_VIEW), key) is None, key
        # Something read on the screen behind it is no proof of what the key brought up either.
        assert _step({**_behind(WEB_VIEW), "newText": ["Descargas"]}, key) is None, key


def test_g1_a_blind_look_behind_gets_no_next_shortcut_either() -> None:
    # Nothing appeared: in front the next shortcut follows; behind it would be pressed blind, so the model decides.
    assert _step({**_behind(WEB_VIEW), "newText": []}, "ctrl_k") is None


def test_counter_case_the_same_look_in_front_keeps_the_old_way() -> None:
    assert _step(WEB_VIEW, "ctrl_k")["arguments"] == {"key": "escape"}
    assert _step({**WEB_VIEW, "newText": []}, "ctrl_k")["arguments"] == {"key": "ctrl_f"}
    assert _step({**WEB_VIEW, "newText": ["Descargas"]}, "ctrl_f")["arguments"] == {"key": "escape"}


def test_counter_case_a_written_search_line_behind_is_still_typed_into() -> None:
    opened = {**_behind(WEB_VIEW), "text": {**WEB_VIEW["text"], "TL": [*WEB_VIEW["text"]["TL"], "Q Buscar por nombre"]},
              "newText": ["Q Buscar por nombre"]}
    step = _step(opened, "ctrl_f")
    assert step["operation"] == "input.text.type" and step["arguments"] == {"text": "Cuphead"}


def test_counter_case_a_window_whose_tree_reads_behind_keeps_its_escape() -> None:
    # A native window lists its own controls even behind the person's window: what the key opened is in its tree.
    native = {
        "window": {"title": "Sin título: Bloc de notas", "process": "editor", "focused": None, "foreground": False},
        "controls": [
            {"i": 0, "kind": "MenuItem", "name": "Archivo"},
            {"i": 1, "kind": "MenuItem", "name": "Editar"},
            {"i": 2, "kind": "MenuItem", "name": "Ver"},
            {"i": 3, "kind": "Document", "name": "Editor de texto"},
        ],
        "text": {},
    }
    assert cu_lookup._exposes_a_tree(native) and not cu_lookup._exposes_a_tree(_behind(WEB_VIEW))
    assert _step(native, "ctrl_k")["arguments"] == {"key": "escape"}
