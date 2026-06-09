"""UIA in-process con el paquete `uiautomation` (wrapper de UIAutomationCore.dll —
la MISMA API COM que usa System.Windows.Automation de .NET, verificado en fuentes
oficiales: la calidad/precisión de GetClickablePoint/patterns/bounds es idéntica).

LATENCIA (MEDIDO 2026-06-09): la ruta PowerShell pagaba spawn (~243ms) + Add-Type
C# (~385ms) en CADA llamada. Esto lo evita (import una vez). Replica FIELMENTE el
comportamiento del script PS: tree/find (lectura), click (Invoke -> clickable
point), set_value (con guarda de password), focus; matching multilingüe token-
aware; scoring de click; SafeInt para bounds offscreen.

Devuelve un dict listo para _ok(**)/_err(**) o None si uiautomation no está/falla
(-> el caller cae a la ruta PowerShell). Kill-switch GEMMA4_UIA_PYTHON=0.
"""
from __future__ import annotations

from typing import Any, Optional

# Tipos botón priorizados para el click (mismo orden que el PS). ControlType es
# inglés -> estable cross-locale.
_BTN_TYPES = ("Button", "SplitButton", "MenuItem", "TabItem", "ListItem",
              "Hyperlink", "CheckBox", "RadioButton")

# Stop-words de UI multilingües (idénticas al PS): "botón tres" -> el Name real es
# "Tres". NO es hardcode por-app; el match sigue siendo por el Name real.
_STOP = frozenset({
    "boton", "botón", "button", "bouton", "schaltflache", "schaltfläche",
    "pulsante", "botao", "botão", "el", "la", "the", "le", "les", "der", "die",
    "das", "il", "en", "in", "de", "del", "of",
})

_INT32_MAX = 2147483647
_INT32_MIN = -2147483648


def _safe_int(v: Any) -> int:
    """Cast double->int seguro: los elementos OFFSCREEN devuelven bounds enormes/
    Inf/NaN (±1.79e308); un int directo overflowea. Clamp a int32 (igual que el PS)."""
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):  # NaN o Inf
            return 0
        if f > _INT32_MAX:
            return _INT32_MAX
        if f < _INT32_MIN:
            return _INT32_MIN
        return int(round(f))
    except Exception:
        return 0


def _elem_obj(auto, e) -> dict[str, Any]:
    """Serializa un control a dict (mismas claves que ElemObj del PS)."""
    try:
        rect = e.BoundingRectangle
        bx, by = _safe_int(rect.left), _safe_int(rect.top)
        bw = _safe_int(rect.right - rect.left)
        bh = _safe_int(rect.bottom - rect.top)
    except Exception:
        bx = by = bw = bh = 0
    click = None
    try:
        ok, pt = e.GetClickablePoint()
        if ok:
            click = {"x": _safe_int(pt.x), "y": _safe_int(pt.y)}
    except Exception:
        pass
    patterns: list[str] = []
    toggle_state = None
    try:
        if e.GetPattern(auto.PatternId.InvokePattern) is not None:
            patterns.append("Invoke")
    except Exception:
        pass
    try:
        tp = e.GetPattern(auto.PatternId.TogglePattern)
        if tp is not None:
            patterns.append("Toggle")
            try:
                toggle_state = str(tp.ToggleState)
            except Exception:
                toggle_state = None
    except Exception:
        pass
    try:
        if e.GetPattern(auto.PatternId.ValuePattern) is not None:
            patterns.append("Value")
    except Exception:
        pass
    is_password = False
    try:
        is_password = bool(e.IsPassword)
    except Exception:
        is_password = False
    return {
        "name": _safe_str(getattr(e, "Name", "")),
        "control_type": _control_type(e),
        "automation_id": _safe_str(getattr(e, "AutomationId", "")),
        "class_name": _safe_str(getattr(e, "ClassName", "")),
        "framework_id": _safe_str(getattr(e, "FrameworkId", "")),
        "enabled": bool(getattr(e, "IsEnabled", True)),
        "is_password": is_password,
        "offscreen": bool(getattr(e, "IsOffscreen", False)),
        "bounds": {"x": bx, "y": by, "width": bw, "height": bh},
        "clickable_point": click,
        "patterns": patterns,
        "toggle_state": toggle_state,
    }


def _safe_str(v: Any) -> str:
    try:
        return str(v) if v is not None else ""
    except Exception:
        return ""


def _control_type(e) -> str:
    # uiautomation expone ControlTypeName tipo 'ButtonControl' -> 'Button'.
    try:
        ct = str(getattr(e, "ControlTypeName", "") or "")
        if ct.endswith("Control"):
            ct = ct[: -len("Control")]
        return ct
    except Exception:
        return ""


def _matches(e, q: str) -> bool:
    """Match multilingüe token-aware — idéntico al PS."""
    if not q or not q.strip():
        return True
    needle = q.lower()
    name = _safe_str(getattr(e, "Name", "")).lower()
    hay = " ".join([
        _safe_str(getattr(e, "Name", "")),
        _safe_str(getattr(e, "AutomationId", "")),
        _safe_str(getattr(e, "ClassName", "")),
        _control_type(e),
    ]).lower()
    if needle in hay:
        return True
    if len(name) >= 2 and name in needle:
        return True
    for tok in needle.split():
        if len(tok) < 3 or tok in _STOP:
            continue
        if name == tok or tok in name or name in tok:
            return True
    return False


def _root_element(auto, window_query: str):
    """Ventana raíz: por título (si se pidió), si no la del foreground, si no el
    desktop. Mismo orden que RootElement del PS."""
    wq = (window_query or "").strip().lower()
    if wq:
        try:
            for w in auto.GetRootControl().GetChildren():
                title = _safe_str(getattr(w, "Name", "")).lower()
                if title and wq in title:
                    return w
        except Exception:
            pass
    try:
        fg = auto.GetForegroundControl()
        if fg is not None:
            return fg
    except Exception:
        pass
    return auto.GetRootControl()


def _descendants(root, limit: int) -> list:
    """Aplana los descendientes (BFS acotado por limit*4 para no caminar árboles
    gigantes). FindAll(Descendants) del PS puede ser lento; acotamos."""
    out = []
    stack = list(root.GetChildren())
    budget = max(limit * 6, 200)
    while stack and budget > 0:
        e = stack.pop(0)
        budget -= 1
        out.append(e)
        try:
            stack.extend(e.GetChildren())
        except Exception:
            pass
    return out


def run(action: str, query: str, window: str, value: str, limit: int) -> Optional[dict[str, Any]]:
    try:
        import uiautomation as auto
    except Exception:
        return None
    try:
        limit = max(1, min(200, int(limit)))
    except Exception:
        limit = 60
    try:
        root = _root_element(auto, window)
        if root is None:
            return {"ok": False, "error": "uia root not found", "window": window}

        all_elems = _descendants(root, limit)
        matches = [e for e in all_elems if _matches(e, query)][:limit]

        # FALLBACK ALL-WINDOWS (no para tree): el control puede estar en otra
        # ventana sin foco. Reescaneamos top-level visibles. Igual que el PS.
        if len(matches) < 1 and not (window or "").strip() and action != "tree":
            try:
                desktop = auto.GetRootControl()
                for top in desktop.GetChildren():
                    if len(matches) >= limit:
                        break
                    for e in _descendants(top, limit):
                        if _matches(e, query):
                            matches.append(e)
                            if len(matches) >= limit:
                                break
                if matches:
                    all_elems = matches
            except Exception:
                pass

        if action == "tree":
            items = []
            for e in all_elems:
                o = _elem_obj(auto, e)
                if o["name"] or o["automation_id"] or o["control_type"] in ("Edit", "Button"):
                    items.append(o)
                    if len(items) >= limit:
                        break
            return {"ok": True, "action": action, "window": window,
                    "root": _elem_obj(auto, root), "elements": items,
                    "count": len(items), "source": "uia_python"}

        if action == "find":
            return {"ok": True, "action": action, "query": query, "window": window,
                    "matches": [_elem_obj(auto, e) for e in matches],
                    "count": len(matches), "source": "uia_python"}

        if len(matches) < 1:
            return {"ok": False, "action": action, "error": "uia element not found",
                    "query": query, "window": window}

        el = matches[0]
        # CLICK: reordenar al control MÁS clickeable (scoring idéntico al PS).
        if action == "click" and len(matches) > 1:
            best, best_score = None, float("inf")
            ql = (query or "").lower()
            for m in matches:
                ct = _control_type(m)
                nml = _safe_str(getattr(m, "Name", "")).lower()
                ct_rank = _BTN_TYPES.index(ct) if ct in _BTN_TYPES else 99
                has_invoke = False
                try:
                    has_invoke = m.GetPattern(auto.PatternId.InvokePattern) is not None
                except Exception:
                    has_invoke = False
                exact = 0 if nml == ql else 1
                name_has = 0 if ql in nml else 1
                enabled = 0 if getattr(m, "IsEnabled", True) else 1
                offs = 1 if getattr(m, "IsOffscreen", False) else 0
                score = (offs * 100000 + enabled * 10000 + (0 if has_invoke else 1) * 1000
                         + ct_rank * 10 + exact * 4 + name_has * 2)
                if score < best_score:
                    best_score, best = score, m
            if best is not None:
                el = best

        if action == "focus":
            try:
                el.SetFocus()
            except Exception as exc:
                return {"ok": False, "action": action, "error": f"set_focus failed: {exc}",
                        "element": _elem_obj(auto, el)}
            return {"ok": True, "action": action, "query": query,
                    "element": _elem_obj(auto, el), "method": "uia_set_focus",
                    "source": "uia_python"}

        if action == "click":
            try:
                inv = el.GetPattern(auto.PatternId.InvokePattern)
            except Exception:
                inv = None
            if inv is not None:
                try:
                    inv.Invoke()
                    return {"ok": True, "action": action, "query": query,
                            "element": _elem_obj(auto, el), "method": "invoke_pattern",
                            "source": "uia_python"}
                except Exception:
                    pass  # cae al clickable point
            try:
                ok, pt = el.GetClickablePoint()
                if not ok:
                    raise RuntimeError("no clickable point")
                import ctypes
                ctypes.windll.user32.SetCursorPos(int(pt.x), int(pt.y))
                ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
                ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
                return {"ok": True, "action": action, "query": query,
                        "element": _elem_obj(auto, el), "method": "clickable_point",
                        "source": "uia_python"}
            except Exception as exc:
                return {"ok": False, "action": action, "error": str(exc),
                        "element": _elem_obj(auto, el)}

        if action == "set_value":
            try:
                if bool(getattr(el, "IsPassword", False)):
                    return {"ok": False, "action": action, "query": query,
                            "element": _elem_obj(auto, el),
                            "error": "refusing to set value on a password/protected field",
                            "status": "needs_user", "verified": False,
                            "completion_status": "needs_secret_handoff"}
            except Exception:
                pass
            try:
                vp = el.GetPattern(auto.PatternId.ValuePattern)
            except Exception:
                vp = None
            if vp is not None:
                try:
                    vp.SetValue(value)
                    return {"ok": True, "action": action, "query": query,
                            "value_chars": len(value or ""), "element": _elem_obj(auto, el),
                            "method": "value_pattern", "source": "uia_python"}
                except Exception as exc:
                    return {"ok": False, "action": action, "error": f"set_value failed: {exc}",
                            "element": _elem_obj(auto, el)}
            return {"ok": False, "action": action, "query": query,
                    "value_chars": len(value or ""), "element": _elem_obj(auto, el),
                    "method": "value_pattern_unavailable", "verified": False,
                    "completion_status": "uia_value_pattern_unavailable",
                    "error": "element does not expose ValuePattern"}

        return {"ok": False, "action": action, "error": "unknown uia action"}
    except Exception:
        return None  # cualquier fallo -> caller cae al PowerShell


__all__ = ["run"]
