"""Integración de la ronda 20b: dos ramas definieron ``_names_the_window`` con firmas distintas en computer_use.py
(r20 P1: nombre y título; r20b-6: vista y nombre). La segunda tapaba a la primera y el documento llamado como su
archivo («Proyecto de título - Word») volvía a ser una parte. Ninguna función del motor se define dos veces."""

import ast
import collections
from pathlib import Path

from baxy_mind import cu_text_place
from baxy_mind import cu_lookup

ROOT = Path(__file__).resolve().parents[1]


def test_no_function_of_the_engine_is_defined_twice() -> None:
    # The engine is computer_use.py and its sibling modules cu_*.py: a function is defined once among all of them.
    mind = ROOT / "src/baxy_mind"
    names = collections.Counter(
        node.name
        for path in (mind / "computer_use.py", *sorted(mind.glob("cu_*.py")))
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    assert [name for name, count in names.items() if count > 1] == []


def test_both_readings_of_the_window_title_stand() -> None:
    # r20 P1: the document the title names is the document itself.
    assert cu_text_place._names_the_window("Proyecto de título", "Proyecto de título - Word")
    assert not cu_text_place._names_the_window("Título 1", "Proyecto de título - Word")
    # r20b-6: a line or a pane that repeats the window's title is its frame, never a search's result.
    panel = {"window": {"title": "iconos grandes - Panel de control"}}
    assert cu_lookup._is_the_window_title(panel, "iconos grandes - Panel de control")
    assert cu_lookup._frame_of_the_window(panel, {"kind": "Pane", "name": "iconos grandes - Panel de control"})
    assert not cu_lookup._is_the_window_title(panel, "iconos grandes")
