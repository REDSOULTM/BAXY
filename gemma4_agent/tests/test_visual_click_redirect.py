"""Bugs de las capturas 2026-06-08:

1. "apretá el icono de Mortal Kombat" (ya visible en Steam) -> el 4B emitió
   steam(action='click', name='Mortal Kombat') -> 'click' no está en el enum de
   steam -> error -> reintentó launch_game (no instalado) -> callejón sin salida.
   FIX: redirección estructural de click VISUAL a gui(click_text).

2. La descripción de visión volcaba el ancla OCR cruda ("El OCR leyó '<<<...>>>'")
   en la respuesta visible. FIX: instrucción + guarda estructural _strip_ocr_echo.
"""
from __future__ import annotations

import pytest

from gemma4_agent.tools_pkg.tools import ACTION_ENUMS
from gemma4_agent.tools_pkg.visual_click_redirect import (
    maybe_redirect_visual_click as _redirect_impl,
)
from gemma4_agent.tools_pkg.vision_describe import _strip_ocr_echo


def _maybe_redirect_visual_click(name, args):
    """Wrapper de test: inyecta el enum real de la tool (como hace execute())."""
    return _redirect_impl(name, args, ACTION_ENUMS.get(name))


# ---- BUG 1: redirección de click visual --------------------------------------

@pytest.mark.parametrize("name,action,key", [
    ("steam", "click", "name"),
    ("steam", "click", "text"),
    ("app", "click", "target"),
    ("window", "double_click", "label"),
    ("steam", "tap", "name"),
    ("steam", "press", "name"),
])
def test_app_click_verb_redirects_to_gui_click_text(name, action, key):
    out = _maybe_redirect_visual_click(name, {"action": action, key: "Mortal Kombat"})
    assert out is not None
    assert out["action"] == "click_text"
    assert out["text"] == "Mortal Kombat"


def test_gui_is_never_redirected_onto_itself():
    # gui ya maneja click_text nativo; no debe redirigirse sobre sí mismo.
    assert _maybe_redirect_visual_click("gui", {"action": "click", "text": "X"}) is None


def test_positional_click_with_coords_is_not_redirected():
    # click con x/y es posicional crudo, no "clickeá el elemento visible X".
    assert _maybe_redirect_visual_click(
        "gui", {"action": "click", "x": 100, "y": 200}) is None
    assert _maybe_redirect_visual_click(
        "steam", {"action": "click", "x": 5, "y": 5}) is None


def test_click_verb_without_target_is_not_redirected():
    # sin texto objetivo no hay nada que localizar por OCR.
    assert _maybe_redirect_visual_click("steam", {"action": "click"}) is None


def test_non_click_action_is_not_redirected():
    assert _maybe_redirect_visual_click(
        "steam", {"action": "launch_game", "query": "X"}) is None


@pytest.mark.parametrize("name", ["uia", "browser"])
def test_tools_with_valid_click_are_not_hijacked(name):
    # uia(click)/browser(click) son acciones VÁLIDAS (accesibilidad / DOM) y
    # mejores que el OCR cuando aplican: NO debemos secuestrarlas.
    assert _maybe_redirect_visual_click(
        name, {"action": "click", "query": "Mortal Kombat"}) is None


def test_redirect_preserves_ocr_tuning():
    out = _maybe_redirect_visual_click(
        "steam", {"action": "click", "name": "X", "min_conf": 40, "lang": "spa"})
    assert out is not None
    assert out["min_conf"] == 40
    assert out["lang"] == "spa"


# ---- BUG 2: no filtrar el OCR crudo al reply ---------------------------------

def test_strip_ocr_echo_removes_anchor_markers():
    txt = ('Se ve la app ChatGPT. <<<0 a_ox @ chatgpt.com BI [aM Recibidos>>> '
           'con varias pestañas.')
    out = _strip_ocr_echo(txt)
    assert "<<<" not in out
    assert ">>>" not in out
    assert "a_ox @ chatgpt.com" not in out
    assert "ChatGPT" in out


def test_strip_ocr_echo_drops_meta_ocr_sentence():
    txt = ('La pantalla muestra Steam con varios juegos. '
           'El OCR leyó "Mortal Kombat, Terraria". '
           'Hay una barra de tareas abajo.')
    out = _strip_ocr_echo(txt)
    assert "OCR" not in out
    assert "Steam" in out
    assert "barra de tareas" in out


def test_strip_ocr_echo_handles_unclosed_marker():
    txt = "Se ve el escritorio. <<<garbled ocr text sin cierre"
    out = _strip_ocr_echo(txt)
    assert "<<<" not in out
    assert "garbled" not in out
    assert "escritorio" in out


def test_strip_ocr_echo_passthrough_clean_prose():
    txt = "Se ve la ventana de Steam con los iconos de varios juegos instalados."
    assert _strip_ocr_echo(txt) == txt


def test_strip_ocr_echo_empty():
    assert _strip_ocr_echo("") == ""
