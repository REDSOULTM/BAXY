"""Input de teclado de bajo nivel: maquinaria SendInput (ctypes) cacheada +
traducción de especificadores de teclas a SendKeys. Extraído de tools.py (split
del archivo-dios, 2026-06-19). Solo stdlib (os + ctypes), sin dependencias del
paquete; tools.py lo re-exporta para sus handlers keypress/type.
"""
from __future__ import annotations

import os

# Maquinaria SendInput CACHEADA a nivel módulo. CAUSA RAÍZ del "anda ~6 veces
# y muere": recrear WinDLL + redeclarar argtypes + redefinir las clases
# Structure en CADA llamada acumula estado en el proceso hasta que SendInput
# deja de entregar (la cola de input se corrompe). Medido: con todo recreado
# por llamada -> 3-6 OK luego falla. Construir la maquinaria UNA sola vez
# elimina el acumulador. _SENDINPUT = None hasta el primer uso; en no-Windows
# queda None y el caller cae al path legacy.
_SENDINPUT = None


def _sendinput_machine():
    """Devuelve (user32, INPUT_factories) cacheado, o None si no aplica."""
    global _SENDINPUT
    if _SENDINPUT is not None:
        return _SENDINPUT if _SENDINPUT is not False else None
    if os.name != "nt":
        _SENDINPUT = False
        return None
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        ULONG_PTR = wintypes.WPARAM

        class _MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class _KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ULONG_PTR)]

        class _HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]

        class _INPUTUNION(ctypes.Union):
            _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT),
                        ("hi", _HARDWAREINPUT)]

        class _INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

        user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
        user32.SendInput.restype = wintypes.UINT
        user32.VkKeyScanW.argtypes = (wintypes.WCHAR,)
        user32.VkKeyScanW.restype = ctypes.c_short
        _SENDINPUT = {
            "user32": user32, "ctypes": ctypes, "INPUT": _INPUT,
            "KEYBD": _KEYBDINPUT, "size": ctypes.sizeof(_INPUT),
        }
        return _SENDINPUT
    except Exception:
        _SENDINPUT = False
        return None


# Mapeo de teclas individuales a SendKeys syntax. Source de truth:
# learn.microsoft.com/dotnet/api/system.windows.forms.sendkeys.send
# Las teclas se envuelven entre { } en SendKeys cuando son special.
_SENDKEYS_SPECIAL = {
    "ENTER": "{ENTER}", "RETURN": "{ENTER}",
    "ESC": "{ESC}", "ESCAPE": "{ESC}",
    "TAB": "{TAB}", "BACKSPACE": "{BACKSPACE}", "BS": "{BACKSPACE}",
    "DELETE": "{DELETE}", "DEL": "{DELETE}",
    "SPACE": " ", "SPACEBAR": " ",
    "UP": "{UP}", "DOWN": "{DOWN}", "LEFT": "{LEFT}", "RIGHT": "{RIGHT}",
    "HOME": "{HOME}", "END": "{END}",
    "PGUP": "{PGUP}", "PAGEUP": "{PGUP}",
    "PGDN": "{PGDN}", "PAGEDOWN": "{PGDN}",
    "INS": "{INS}", "INSERT": "{INS}",
    "F1": "{F1}", "F2": "{F2}", "F3": "{F3}", "F4": "{F4}",
    "F5": "{F5}", "F6": "{F6}", "F7": "{F7}", "F8": "{F8}",
    "F9": "{F9}", "F10": "{F10}", "F11": "{F11}", "F12": "{F12}",
    "CAPSLOCK": "{CAPSLOCK}", "NUMLOCK": "{NUMLOCK}",
    "PRINTSCREEN": "{PRTSC}", "PRTSC": "{PRTSC}", "PRINT": "{PRTSC}",
    "PLAYPAUSE": "^v",  # SendKeys no soporta media keys; usar virtual key via gui_keypress_vk
}

# Prefijos modificadores de SendKeys.
_SENDKEYS_MODIFIERS = {
    "CTRL": "^", "CONTROL": "^",
    "ALT": "%",
    "SHIFT": "+",
    "WIN": "^{ESC}",  # Win key no es directamente soportado por SendKeys; workaround limitado
}


def _translate_keys_to_sendkeys(keys: str) -> str:
    """Traduce un especificador de teclas humano-friendly a SendKeys syntax.

    Casos cubiertos:
      - "enter" -> "{ENTER}"
      - "ctrl+f" -> "^f"
      - "Ctrl+Shift+T" -> "^+t"
      - "alt+f4" -> "%{F4}"
      - "ctrl+shift+escape" -> "^+{ESC}"
      - "a" -> "a"  (letra normal)
      - "^f" -> "^f"  (passthrough si ya es SendKeys)
      - "{ENTER}" -> "{ENTER}"  (passthrough)

    Si el formato no es reconocible, devuelve la string tal cual (passthrough)
    para no romper input que ya estaba bien.
    """
    if not keys:
        return ""
    s = keys.strip()
    # Si ya parece SendKeys syntax (empieza con ^+% o tiene {...}), pass.
    if s and (s[0] in "^+%" or s.startswith("{")):
        return s
    # Mapeo exacto para nombres simples (ENTER, F5, etc).
    upper = s.upper()
    if upper in _SENDKEYS_SPECIAL:
        return _SENDKEYS_SPECIAL[upper]
    # Combo con modificadores: split por '+'.
    if "+" in s:
        parts = [p.strip() for p in s.split("+") if p.strip()]
        if not parts:
            return s
        modifier_prefix = ""
        # El ultimo token es la tecla; los anteriores son modificadores.
        for mod in parts[:-1]:
            mu = mod.upper()
            if mu in _SENDKEYS_MODIFIERS:
                # Solo agregamos el simbolo del modificador (^/%/+).
                m = _SENDKEYS_MODIFIERS[mu]
                # Filtramos el workaround inutil de WIN.
                if m in {"^", "%", "+"}:
                    modifier_prefix += m
                # Si el modificador no es estandar, retornamos passthrough.
                else:
                    return s
            else:
                return s
        last = parts[-1].upper()
        if last in _SENDKEYS_SPECIAL:
            return modifier_prefix + _SENDKEYS_SPECIAL[last]
        last_raw = parts[-1]
        if len(last_raw) == 1:
            # Letra/digito normal: lowercase para SendKeys consistency.
            return modifier_prefix + last_raw.lower()
        # Multi-char no especial: envolver en { }.
        return modifier_prefix + "{" + last_raw + "}"
    # No combo, no especial conocido. Para multichar suponemos texto literal.
    if len(s) == 1:
        return s
    # Multichar sin combo (e.g. "abc"): pasar tal cual (SendKeys lo trata como texto).
    return s
