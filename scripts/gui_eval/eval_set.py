"""Eval-set de misiones GUI — Fase 0 del roadmap computer-use (2026-05-24).

PRINCIPIO (triple-confirmado por la investigación): el éxito se mide por el
ESTADO REAL DEL SO, NUNCA por "el tool devolvió ok". Eso es justo el origen del
falso PASS que hundió a Carter (bench que medía estructura, no efecto).

Cada misión = (id, tier, utterance, goal_verifier, reset, precheck). El runner
(run_eval.py) ejecuta la utterance contra el agente real y luego llama
goal_verifier() que LEE el SO (pycaw, EnumWindows, Path, UIA) y devuelve
PASS/FAIL/INCONCLUSIVE + evidencia.

Tiers (de la investigación):
  T1 = apps con UIA rico (Notepad, Explorer, Settings, calculadora) — el subset
       donde el SOTA local SÍ es alcanzable (~40-60% objetivo).
  T2 = navegadores / CEF (Chrome, Edge) — UIA tras --force-renderer-accessibility.
  T3 = apps custom-render (Discord/Spotify/juegos) — el techo bajo (~15-25%).
  T4 = multi-app (encadenamiento).

NO hardcodes de comportamiento del agente acá: esto es el HARNESS de medición,
no el agente. Las utterances son multi-idioma a propósito (universalidad).

Cada goal_verifier devuelve dict: {"pass": bool|None, "evidence": str, "actual": ...}
  pass=True  -> el SO está en el estado esperado.
  pass=False -> el SO NO está en el estado esperado (la misión falló de verdad).
  pass=None  -> no se pudo verificar (entorno sin la app / sin la lib).
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Helpers de lectura del ESTADO REAL del SO (no del agente). Cada uno es puro.
# ---------------------------------------------------------------------------

def _endpoint_volume():
    """IAudioEndpointVolume COM pointer reusando el patrón YA PROBADO del repo
    (tools._audio_endpoint_volume): maneja el caso pycaw-nuevo donde el device
    expone .EndpointVolume directo (sin .Activate) — el bug que hacía None."""
    from ctypes import POINTER, cast
    from comtypes import CLSCTX_ALL  # type: ignore
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    try:
        from comtypes import CoInitialize  # type: ignore
        CoInitialize()  # idempotente; necesario en threads/procesos worker
    except Exception:
        pass
    device = AudioUtilities.GetSpeakers()
    if device is None:
        raise RuntimeError("no audio endpoint")
    if hasattr(device, "EndpointVolume"):       # pycaw nuevo
        return device.EndpointVolume
    iface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)  # pycaw viejo
    return cast(iface, POINTER(IAudioEndpointVolume))


def get_master_volume() -> int | None:
    """Volumen master 0-100, o None si no disponible."""
    try:
        return int(round(_endpoint_volume().GetMasterVolumeLevelScalar() * 100))
    except Exception:
        return None


def is_muted() -> bool | None:
    try:
        return bool(_endpoint_volume().GetMute())
    except Exception:
        return None


def set_master_volume(level: int) -> None:
    """Para reset/precondición — el HARNESS fija el estado base, no el agente."""
    try:
        vol = _endpoint_volume()
        vol.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level / 100.0)), None)
        try:
            vol.SetMute(False, None)
        except Exception:
            pass
    except Exception:
        pass


def visible_windows() -> list[dict[str, Any]]:
    """Lista de ventanas visibles {hwnd, title, pid} vía Win32 EnumWindows."""
    out: list[dict[str, Any]] = []
    try:
        import win32gui
        import win32process

        def _cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                pid = 0
            out.append({"hwnd": hwnd, "title": title, "pid": pid})
            return True
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass
    return out


def foreground_title() -> str | None:
    try:
        import win32gui
        h = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(h) if h else None
    except Exception:
        return None


def process_running(name_substr: str) -> bool | None:
    """¿Hay un proceso cuyo nombre contiene name_substr? vía tasklist."""
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        low = (out.stdout or "").lower()
        return name_substr.lower() in low
    except Exception:
        return None


def window_title_contains(substr: str) -> bool:
    """¿Alguna ventana visible tiene substr (case-insensitive) en el título?"""
    s = substr.lower()
    return any(s in w["title"].lower() for w in visible_windows())


def _kill_process(exe_name: str) -> bool:
    """Cierra un proceso por nombre (para reset del HARNESS, no del agente).
    Devuelve True siempre (best-effort) para encadenar con `or`."""
    try:
        subprocess.run(["taskkill", "/IM", exe_name, "/F"],
                       capture_output=True, timeout=8,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass
    return True


def uia_window_has_text(window_substr: str, text_substr: str) -> bool | None:
    """¿La ventana cuyo título contiene window_substr tiene un control/edit cuyo
    valor o Name contiene text_substr? Lee el árbol UIA real. None si no se pudo."""
    try:
        import uiautomation as auto
        s_win, s_txt = window_substr.lower(), text_substr.lower()
        for w in auto.GetRootControl().GetChildren():
            try:
                if s_win in (w.Name or "").lower():
                    # buscar en descendientes (acotado)
                    for el in w.GetChildren():
                        for sub in [el] + el.GetChildren():
                            val = ""
                            try:
                                vp = sub.GetValuePattern()
                                val = vp.Value or ""
                            except Exception:
                                val = sub.Name or ""
                            if s_txt in val.lower():
                                return True
            except Exception:
                continue
        return False
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Estructura de una misión
# ---------------------------------------------------------------------------

@dataclass
class GuiMission:
    id: str
    tier: int                      # 1=UIA-rico, 2=CEF, 3=custom, 4=multi-app
    utterance: str                 # lo que diría el usuario (multi-idioma)
    goal_verifier: Callable[[], dict[str, Any]]  # LEE estado del SO
    reset: Callable[[], None] = lambda: None      # fija la precondición
    precheck: Callable[[], bool] = lambda: True    # ¿el entorno permite el test?
    note: str = ""
    max_steps_hint: int = 5


# ---------------------------------------------------------------------------
# Las misiones. Cada goal_verifier LEE el SO. Empezamos por las que NO requieren
# apps de terceros instaladas (volumen, Notepad, calculadora — siempre presentes
# en Windows), para que el eval corra en cualquier máquina.
# ---------------------------------------------------------------------------

def _v_volume(target: int, tol: int = 4) -> Callable[[], dict]:
    def _f() -> dict:
        actual = get_master_volume()
        if actual is None:
            return {"pass": None, "evidence": "pycaw no disponible", "actual": None}
        ok = abs(actual - target) <= tol
        return {"pass": ok, "evidence": f"volumen={actual} (target {target}±{tol})",
                "actual": actual}
    return _f


def _v_muted(expect: bool) -> Callable[[], dict]:
    def _f() -> dict:
        m = is_muted()
        if m is None:
            return {"pass": None, "evidence": "pycaw no disponible", "actual": None}
        return {"pass": m == expect, "evidence": f"muted={m} (esperado {expect})",
                "actual": m}
    return _f


def _v_window_open(title_substr: str) -> Callable[[], dict]:
    def _f() -> dict:
        ok = window_title_contains(title_substr)
        return {"pass": ok, "evidence": f"ventana '{title_substr}' visible={ok}",
                "actual": [w["title"] for w in visible_windows()][:8]}
    return _f


def _v_notepad_text(text: str) -> Callable[[], dict]:
    def _f() -> dict:
        # Notepad moderno: el título suele ser "*Sin título: Bloc de notas" o
        # contiene el texto en el edit. Leemos el edit por UIA.
        got = uia_window_has_text("notas", text) or uia_window_has_text("notepad", text)
        if got is None:
            return {"pass": None, "evidence": "UIA no disponible", "actual": None}
        return {"pass": got, "evidence": f"Notepad contiene '{text}'={got}", "actual": got}
    return _f


MISSIONS: list[GuiMission] = [
    # ---------- TIER 1: estado del SO directo, sin apps de terceros ----------
    GuiMission(
        id="t1_vol_30", tier=1, utterance="subí el volumen al 30",
        goal_verifier=_v_volume(30), reset=lambda: set_master_volume(70),
        note="volumen leído por pycaw — el verificador más limpio (sin GUI ambigua)"),
    GuiMission(
        id="t1_vol_50_en", tier=1, utterance="set the volume to 50",
        goal_verifier=_v_volume(50), reset=lambda: set_master_volume(20),
        note="multi-idioma (inglés)"),
    GuiMission(
        id="t1_vol_10_pt", tier=1, utterance="coloca o volume em 10",
        goal_verifier=_v_volume(10), reset=lambda: set_master_volume(80),
        note="multi-idioma (portugués)"),
    GuiMission(
        id="t1_mute", tier=1, utterance="silenciá el sonido",
        goal_verifier=_v_muted(True), reset=lambda: set_master_volume(50),
        note="mute via pycaw GetMute"),
    GuiMission(
        id="t1_open_notepad", tier=1, utterance="abrí el bloc de notas",
        goal_verifier=_v_window_open("notas"),
        precheck=lambda: True,
        note="Notepad siempre está en Windows; ventana via EnumWindows"),
    GuiMission(
        id="t1_open_calc", tier=1, utterance="abrí la calculadora",
        goal_verifier=lambda: (lambda ok: {"pass": ok, "evidence": f"calc proc={ok}",
                                            "actual": ok})(process_running("calc")),
        reset=lambda: _kill_process("CalculatorApp.exe") or _kill_process("Calculator.exe"),
        note="reset CIERRA calc primero -> el baseline da False, así el PASS exige "
             "que el agente la abra (no que ya estuviera abierta). Detectado por dry-baseline."),
    GuiMission(
        id="t1_notepad_write", tier=1,
        utterance="abrí el bloc de notas y escribí hola mundo",
        goal_verifier=_v_notepad_text("hola mundo"),
        reset=lambda: _kill_process("notepad.exe"),
        max_steps_hint=3,
        note="2 pasos: abrir + escribir. reset cierra Notepad. Verifica el TEXTO real "
             "por UIA, no 'tool ok'"),
    # t1_open_explorer ELIMINADA: explorer.exe es el shell de Windows y casi
    # siempre corre, así que 'proceso existe' daba PASS sin que el agente hiciera
    # nada (falso PASS estructural del propio harness, detectado por el
    # dry-baseline). Medir 'abrir explorer' bien requiere detectar una VENTANA de
    # carpeta nueva, no el proceso — se hará en una iteración posterior del set.
]


def missions_for_tier(tier: int | None = None) -> list[GuiMission]:
    if tier is None:
        return list(MISSIONS)
    return [m for m in MISSIONS if m.tier == tier]
