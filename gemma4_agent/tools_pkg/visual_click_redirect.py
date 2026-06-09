"""Redirección de CLICK VISUAL a gui(click_text).

Extraído de tools.py (2026-06-08, ratchet archivo-dios). Causa raíz (capturas
2026-06-08): "apretá el icono de Mortal Kombat" (ya visible en Steam) -> el 4B
emitió steam(action='click', name='Mortal Kombat') -> 'click' no está en el enum
de steam -> error -> reintentó launch_game (juego no instalado) -> callejón sin
salida. La acción correcta SIEMPRE fue clickear el ícono visible (es GUI, no una
acción de la tool de la app).
"""
from __future__ import annotations

from typing import Any, Optional

# Verbos de CLICK VISUAL: "apretá/clickeá el icono/botón X que se ve". El 4B los
# emite como action en TODA tool de app (steam, app, window…) porque "apretar X"
# suena a operar esa app. Estos nombres de acción son el enum de `gui` (inglés,
# los emite el modelo), no contenido de idioma del usuario -> estructural.
_VISUAL_CLICK_ACTIONS = {"click", "click_text", "click_button", "double_click",
                         "right_click", "tap", "press", "locate_text"}


def maybe_redirect_visual_click(
    name: str,
    args: dict[str, Any],
    valid_actions: Optional[set[str]] = None,
) -> Optional[dict[str, Any]]:
    """Si una tool de APP recibe un verbo de CLICK VISUAL que NO es válido para
    ESA tool, con un objetivo de texto (name/label/target/text) y SIN coordenadas,
    lo reescribe a `gui(action='click_text', text=...)`: el OCR localiza el
    elemento visible y lo clickea. Devuelve los args reescritos {action,text,...}
    para `gui`, o None si no aplica. `valid_actions`: el enum de acciones válidas
    de `name` (ACTION_ENUMS) para no secuestrar acciones legítimas.

    SOLO redirige cuando el verbo NO es válido para la tool (el dead-end real). Si
    `click` SÍ es una acción legítima de esa tool (uia, browser, gui), la dejamos:
    uia(click)/browser(click) son caminos válidos (accesibilidad / DOM) y mejores
    que el OCR cuando aplican."""
    if name == "gui":
        return None  # gui ya maneja click_text nativo; no redirigir sobre sí mismo
    action = str(args.get("action") or "").strip().lower()
    if action not in _VISUAL_CLICK_ACTIONS:
        return None
    # Si el verbo ES válido para esta tool, no la secuestramos: uia(click) /
    # browser(click) son rutas legítimas. Solo rescatamos el enum INVÁLIDO.
    if valid_actions and action in valid_actions:
        return None
    # Si el 4B ya dio coordenadas explícitas, es un click posicional crudo: no es
    # "clickeá el elemento visible X" -> no redirigimos (dejamos el flujo normal).
    if args.get("x") is not None or args.get("y") is not None:
        return None
    target = str(args.get("text") or args.get("name") or args.get("label")
                 or args.get("target") or args.get("query") or "").strip()
    if not target:
        return None  # sin objetivo de texto no hay qué localizar por OCR
    redirected: dict[str, Any] = {"action": "click_text", "text": target}
    # Preservar tuning OCR si el 4B lo pasó (raro, pero no lo perdemos).
    for k in ("lang", "min_conf", "monitor"):
        if args.get(k) is not None:
            redirected[k] = args[k]
    return redirected


__all__ = ["maybe_redirect_visual_click", "_VISUAL_CLICK_ACTIONS"]
