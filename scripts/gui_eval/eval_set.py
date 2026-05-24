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


def process_running(name_substr: str, *, exact: bool = False) -> bool | None:
    """¿Hay un proceso cuyo nombre coincide? vía tasklist.
    exact=True compara el NOMBRE EXACTO del .exe (evita que 'notepad' matchee
    'notepad++.exe'). exact=False = substring en toda la salida (laxo)."""
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = out.stdout or ""
        if not exact:
            return name_substr.lower() in text.lower()
        target = name_substr.lower()
        if not target.endswith(".exe"):
            target += ".exe"
        for line in text.splitlines():
            # CSV: "imagename.exe","pid",...
            first = line.split(",")[0].strip().strip('"').lower()
            if first == target:
                return True
        return False
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
    valor o Name contiene text_substr? Lee el árbol UIA real. None si no se pudo.
    Camina descendientes en PROFUNDIDAD acotada (BFS) — el display de algunas apps
    (Calculadora: 'CalculatorResults') está más abajo que 2 niveles; un walk chato
    daba FALSO NEGATIVO aunque el texto SÍ estaba (bug 2026-05-25)."""
    try:
        import uiautomation as auto
        s_win, s_txt = window_substr.lower(), text_substr.lower()
        for w in auto.GetRootControl().GetChildren():
            try:
                if s_win not in (w.Name or "").lower():
                    continue
                # BFS acotado: hasta ~600 nodos, cualquier profundidad razonable.
                queue = list(w.GetChildren())
                seen = 0
                while queue and seen < 600:
                    sub = queue.pop(0)
                    seen += 1
                    val = ""
                    try:
                        vp = sub.GetValuePattern()
                        val = vp.Value or ""
                    except Exception:
                        val = sub.Name or ""
                    if s_txt in (val or "").lower():
                        return True
                    try:
                        queue.extend(sub.GetChildren())
                    except Exception:
                        pass
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


def _v_no_window(*title_substrs: str) -> Callable[[], dict]:
    """Verifica que NO quede ninguna ventana visible cuyo título contenga alguno
    de los substrings. Es el oráculo CORRECTO para 'cerrar' apps UWP modernas
    (Win11 Notepad) cuyo PROCESO queda residente/caliente aunque la última
    ventana se cierre — process_running daría un FALSO FAIL aunque la ventana
    (lo que el usuario pidió cerrar) sí desapareció. Para apps clásicas
    (mspaint, CalculatorApp) el proceso sí termina, así que esas siguen usando
    _v_proc. Medir 'ventana ausente' es MÁS estricto para el intent real del
    usuario, no un atajo. (2026-05-24: descubierto que Win11 Notepad no muere
    al cerrar su ventana.)"""
    subs = [s.lower() for s in title_substrs]
    def _f() -> dict:
        titles = [w["title"] for w in visible_windows()]
        remaining = [t for t in titles if any(s in t.lower() for s in subs)]
        gone = len(remaining) == 0
        return {"pass": gone,
                "evidence": f"ventanas {subs} visibles={len(remaining)} (esperado 0)",
                "actual": remaining[:6]}
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


# ===========================================================================
# EVAL-SET AMPLIADO (>=100 comandos) — Tier 1/2/3, multi-idioma, verificado por SO
# RED pidió >=100 para verificar de verdad. Generación combinatoria honesta:
# cada misión sigue midiendo por estado del SO; las de apps de terceros llevan
# precheck (skip si no está instalada -> no es FAIL falso).
# ===========================================================================

def _app_installed(start_app_substr: str) -> bool:
    """¿La app aparece en Get-StartApps (instalada)? Cacheado por proceso."""
    try:
        import functools
        return _start_apps_contains(start_app_substr)
    except Exception:
        return False


_START_APPS_CACHE: list[str] | None = None


def _start_apps_contains(substr: str) -> bool:
    global _START_APPS_CACHE
    if _START_APPS_CACHE is None:
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
                 "Get-StartApps | Select-Object -ExpandProperty Name"],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            _START_APPS_CACHE = [l.strip().lower() for l in (out.stdout or "").splitlines() if l.strip()]
        except Exception:
            _START_APPS_CACHE = []
    s = substr.lower()
    return any(s in a for a in _START_APPS_CACHE)


def _v_proc(name_substr: str, *, exact: bool = False) -> Callable[[], dict]:
    def _f() -> dict:
        ok = process_running(name_substr, exact=exact)
        if ok is None:
            return {"pass": None, "evidence": "tasklist no disponible", "actual": None}
        return {"pass": ok, "evidence": f"proceso '{name_substr}'{'(exact)' if exact else ''} corriendo={ok}", "actual": ok}
    return _f


def _v_window(title_substr: str) -> Callable[[], dict]:
    return _v_window_open(title_substr)


def _v_unmuted() -> Callable[[], dict]:
    return _v_muted(False)


def _build_extended() -> list[GuiMission]:
    """Genera >=100 misiones. Estructura: VOLUMEN (muchos niveles × idiomas) +
    MUTE/UNMUTE + APPS nativas + APPS terceros (precheck) + multi-paso."""
    out: list[GuiMission] = []

    # ---- VOLUMEN: niveles × fraseos multi-idioma. Verificable exacto por pycaw.
    # (target, utterance, reset_to)
    vol_templates = [
        ("subí el volumen al {n}", "es"), ("bajá el volumen a {n}", "es"),
        ("poné el volumen en {n}", "es"), ("volumen al {n} por ciento", "es"),
        ("set the volume to {n}", "en"), ("turn the volume to {n} percent", "en"),
        ("change volume to {n}", "en"),
        ("coloca o volume em {n}", "pt"), ("ajusta o volume para {n}", "pt"),
        ("mets le volume à {n}", "fr"), ("stell die lautstärke auf {n}", "de"),
        ("imposta il volume a {n}", "it"),
    ]
    levels = [5, 15, 25, 35, 45, 55, 65, 75, 85, 95, 20, 40, 60, 80, 10, 30, 50, 70, 90, 100]
    i = 0
    for n in levels:
        tmpl, lang = vol_templates[i % len(vol_templates)]
        i += 1
        reset_to = (n + 40) % 100  # un valor distinto al target
        out.append(GuiMission(
            id=f"t1_vol_{n}_{lang}_{i}", tier=1, utterance=tmpl.format(n=n),
            goal_verifier=_v_volume(n), reset=(lambda r=reset_to: set_master_volume(r)),
            note=f"volumen {n} ({lang})"))

    # ---- MUTE / UNMUTE × idiomas
    mute_utts = [("silenciá el sonido", "es"), ("muteá", "es"), ("mute the sound", "en"),
                 ("silencia o som", "pt"), ("coupe le son", "fr"), ("stumm schalten", "de"),
                 ("silencia el audio", "es"), ("mute", "en")]
    for k, (u, lang) in enumerate(mute_utts):
        out.append(GuiMission(
            id=f"t1_mute_{lang}_{k}", tier=1, utterance=u,
            goal_verifier=_v_muted(True), reset=(lambda: set_master_volume(50)),
            note=f"mute ({lang})"))
    unmute_utts = [("activá el sonido", "es"), ("desmuteá", "es"), ("unmute", "en"),
                   ("reactiva o som", "pt"), ("rétablis le son", "fr"), ("ton an", "de")]
    for k, (u, lang) in enumerate(unmute_utts):
        out.append(GuiMission(
            id=f"t1_unmute_{lang}_{k}", tier=1, utterance=u,
            goal_verifier=_v_unmuted(),
            reset=(lambda: (set_master_volume(50), _set_mute(True))),
            note=f"unmute ({lang})"))

    # ---- ABRIR APPS NATIVAS (siempre en Windows) × idiomas
    # (label, exe_real, proc_name_para_verify, utterances). El verifier usa el
    # NOMBRE REAL del proceso (calc -> CalculatorApp.exe), exact, para no
    # confundir (notepad != notepad++) ni fallar por mismatch (calc != calc.exe).
    native = [
        ("notepad", "notepad.exe", "notepad", ["abrí el bloc de notas", "open notepad",
         "abre o bloco de notas", "ouvre le bloc-notes", "öffne den editor"]),
        ("calc", "CalculatorApp.exe", "CalculatorApp", ["abrí la calculadora",
         "open the calculator", "abre a calculadora", "ouvre la calculatrice",
         "öffne den rechner"]),
        ("mspaint", "mspaint.exe", "mspaint", ["abrí Paint", "open Paint", "abre o Paint"]),
    ]
    for label, exe, proc_name, utts in native:
        for k, u in enumerate(utts):
            out.append(GuiMission(
                id=f"t1_open_{label}_{k}", tier=1, utterance=u,
                goal_verifier=_v_proc(proc_name, exact=True),
                reset=(lambda e=exe: _kill_process(e)),
                precheck=(lambda e=exe: _exe_exists(e)),
                note=f"abrir {label} ({u})"))

    # ---- MULTI-PASO Tier-1: abrir + escribir (verifica el TEXTO por UIA)
    write_cases = [
        ("notas", "notepad.exe", "abrí el bloc de notas y escribí {t}",
         ["hola mundo", "prueba uno dos tres", "buenos dias"]),
    ]
    for win, exe, tmpl, texts in write_cases:
        for k, t in enumerate(texts):
            out.append(GuiMission(
                id=f"t1_write_{k}", tier=1, utterance=tmpl.format(t=t),
                goal_verifier=(lambda w=win, tx=t: (lambda g: {"pass": g, "evidence":
                    f"{w} contiene '{tx}'={g}", "actual": g})(
                    uia_window_has_text(w, tx))),
                # kill + limpiar session-restore para que el write arranque sin
                # pestañas sucias previas (mismo motivo que en las misiones close).
                reset=(lambda e=exe: (_kill_process(e), _clear_notepad_session())),
                max_steps_hint=3, note=f"multi-paso abrir+escribir '{t}'"))

    # ---- TIER 2/3: APPS DE TERCEROS (precheck por instalación). Abrir la app y
    # verificar por proceso. Universal: el agente las resuelve por su nombre.
    third = [
        (2, "chrome", "chrome.exe", "Google Chrome", ["abrí Chrome", "open Chrome",
         "abre o Chrome", "lanzá Google Chrome"]),
        (2, "msedge", "msedge.exe", "Microsoft Edge", ["abrí Edge", "open Edge"]),
        (3, "Discord", "Discord.exe", "Discord", ["abrí Discord", "open Discord",
         "abre o Discord"]),
        (3, "Spotify", "Spotify.exe", "Spotify", ["abrí Spotify", "open Spotify",
         "abre o Spotify", "lanzá Spotify"]),
        (3, "steam", "steam.exe", "Steam", ["abrí Steam", "open Steam"]),
        (3, "vlc", "vlc.exe", "VLC media player", ["abrí VLC", "open VLC", "abre o VLC"]),
        (3, "Telegram", "Telegram.exe", "Telegram", ["abrí Telegram", "open Telegram"]),
        (2, "WINWORD", "WINWORD.EXE", "Word", ["abrí Word", "open Word"]),
        (2, "EXCEL", "EXCEL.EXE", "Excel", ["abrí Excel", "open Excel"]),
    ]
    for tier, proc_substr, exe, start_name, utts in third:
        for k, u in enumerate(utts):
            out.append(GuiMission(
                id=f"t{tier}_open_{proc_substr}_{k}", tier=tier, utterance=u,
                goal_verifier=_v_proc(proc_substr),
                reset=(lambda e=exe: _kill_process(e)),
                precheck=(lambda s=start_name: _start_apps_contains(s)),
                note=f"tier{tier} abrir {start_name} ({u})"))

    # ---- CERRAR APPS (verificable: el proceso YA NO corre). reset las abre.
    # verifier por target: notepad (UWP) verifica VENTANA-ausente (su proceso
    # queda residente al cerrar la última ventana); mspaint/calc (clásicas)
    # verifican PROCESO-ausente (sí terminan). Ver _v_no_window.
    close_targets = [
        ("notepad", "notepad.exe",
         _v_no_window("bloc de notas", "notepad"),
         ["cerrá el bloc de notas", "close notepad", "fecha o bloco de notas"]),
        ("mspaint", "mspaint.exe", None, ["cerrá Paint", "close Paint"]),
        ("CalculatorApp", "CalculatorApp.exe", None,
         ["cerrá la calculadora", "close calculator"]),
    ]
    for proc_substr, exe, win_verifier, utts in close_targets:
        for k, u in enumerate(utts):
            out.append(GuiMission(
                id=f"t1_close_{proc_substr}_{k}", tier=1, utterance=u,
                goal_verifier=(win_verifier or (lambda p=proc_substr: (lambda r: {"pass": (r is False),
                    "evidence": f"proceso '{p}'(exact) corriendo={r} (esperado cerrado)",
                    "actual": r})(process_running(p, exact=True)))),
                # HIGIENE DEL HARNESS: matar TODAS las instancias primero (las
                # misiones de 'escribir' dejan ventanas con cambios sin guardar
                # -> WM_CLOSE abre diálogo "¿guardar?" y la ventana sobrevive,
                # contaminando esta misión con un FALSO FAIL); para Notepad UWP
                # además limpiar TabState (si no, session-restore reabre las
                # pestañas sucias) y recién entonces abrir UNA instancia limpia.
                # Así el agente cierra exactamente una ventana sin diálogo. Sin
                # esto, el estado base no era reproducible (bug 2026-05-24).
                reset=(lambda e=exe, p=proc_substr: (
                    _kill_process(e),
                    (_clear_notepad_session() if p == "notepad" else None),
                    _launch_detached(e))),
                precheck=(lambda e=exe: _exe_exists(e)),
                note=f"cerrar {proc_substr} ({u})"))

    # ---- MÁS VOLUMEN: niveles intermedios para llegar holgado a >=100 y cubrir
    # más fraseos/idiomas. Verificable exacto.
    more_levels = [12, 22, 33, 44, 56, 66, 77, 88, 8, 18, 28, 38, 48, 58, 68, 78]
    more_templates = [
        ("poné el volumen al {n}%", "es"), ("dejá el volumen en {n}", "es"),
        ("volume to {n}", "en"), ("make it {n} percent volume", "en"),
        ("volume a {n}", "pt"), ("règle le volume sur {n}", "fr"),
        ("lautstärke {n} prozent", "de"), ("volume al {n}", "it"),
    ]
    j = 0
    for n in more_levels:
        tmpl, lang = more_templates[j % len(more_templates)]
        j += 1
        out.append(GuiMission(
            id=f"t1_vol2_{n}_{lang}", tier=1, utterance=tmpl.format(n=n),
            goal_verifier=_v_volume(n), reset=(lambda r=((n + 33) % 100): set_master_volume(r)),
            note=f"volumen {n} ({lang})"))

    # ---- CLICK_BUTTON: clickear un control por su LABEL (macro click_button +
    # uia.click button-prioritized). La Calculadora es UIA-rico y verificable: el
    # display ('CalculatorResults') refleja el resultado. Usamos utterances con
    # "clic/click en el botón X" (intención de CLICK clara — "apretá el 7" suelto
    # es realmente intención de TECLADO, va a `input`, correcto). Verificador =
    # estado del SO (display por UIA), nunca "tool ok". El reset clickea
    # 7 + <op> dejando el display en un valor conocido tras el botón objetivo.
    # Cada misión: clic en un botón NOMBRADO y el display debe mostrar el efecto.
    # (digit_label, expected_display_substr, utterances)
    # NOTA: las utterances van en el idioma del SO (Windows ES en la PC de RED)
    # porque el LABEL del control que matchea es el del UIA localizado ("Cinco",
    # no "five"). El cross-lingual label↔UI (pedir "five" en un Windows español)
    # es un TECHO documentado aparte, NO se fuerza con una tabla de traducción
    # de dígitos por idioma (sería el hardcode monolingüe vetado).
    click_named = [
        ("Nueve", "9", ["hacé clic en el botón nueve de la calculadora",
                         "clic en el botón nueve"]),
        ("Cinco", "5", ["clic en el botón cinco de la calculadora",
                        "hacé clic en el botón cinco"]),
        ("Tres", "3", ["hacé clic en el botón tres", "clic en el botón tres"]),
    ]
    for label, expect, utts in click_named:
        for k, u in enumerate(utts):
            out.append(GuiMission(
                id=f"t2_clickbtn_{expect}_{k}", tier=2, utterance=u,
                goal_verifier=(lambda e=expect: (lambda val: {
                    "pass": (val is not None and e in val),
                    "evidence": f"display Calculadora={val!r} contiene '{e}'={val is not None and e in val}",
                    "actual": val})(_calc_display_value())),
                reset=_reset_calc_clean,
                precheck=(lambda: _exe_exists("CalculatorApp.exe") or True),
                max_steps_hint=3,
                note=f"click_button '{label}' ({u})"))

    # ---- CASCADA UIA→OCR (Fase 3): clickear un botón en CONTENIDO CHROMIUM
    # (superficie de render propio, sin UIA rico) — fuerza el fallback OCR. El
    # fixture HTML abre con título "...listo-para-clickear" y al clickear
    # "Confirmar" cambia a "...OK-clickeado". Verificable por ESTADO DEL SO (el
    # título de ventana, leído por Win32), reproducible y sin depender de la UI
    # interna de apps de terceros. Mide exactamente lo que agrega Fase 3: clickear
    # algo que el árbol UIA NO expone.
    cef_clicks = [
        ("confirmar_es", "hacé clic en el botón Confirmar"),
        ("confirmar_es2", "clic en Confirmar"),
        ("confirmar_en", "click the Confirmar button"),
    ]
    for cid, u in cef_clicks:
        out.append(GuiMission(
            id=f"t3_cef_{cid}", tier=3, utterance=u,
            goal_verifier=(lambda: (lambda ok: {
                "pass": ok,
                "evidence": f"título de ventana contiene 'OK-clickeado'={ok}",
                "actual": _gemma_click_test_title()})(
                "ok-clickeado" in (_gemma_click_test_title() or "").lower())),
            reset=_reset_cef_fixture,
            precheck=(lambda: _gemma_click_test_title() is not None),
            max_steps_hint=2,
            note=f"cascada OCR sobre contenido Chromium ({u})"))

    return out


def _gemma_click_test_title() -> str | None:
    """Título de la ventana del fixture HTML (contiene 'GEMMA4 CLICK TEST').
    None si no está abierta. Es el oráculo de estado del SO para la misión CEF."""
    for w in visible_windows():
        if "gemma4 click test" in (w.get("title") or "").lower():
            return w["title"]
    return None


def _reset_cef_fixture() -> None:
    """Abre el fixture HTML en el navegador por defecto (contenido Chromium) y
    espera el render. Cierra Edge/Chrome previos para partir del estado base
    ('listo-para-clickear'). El fixture cambia su <title> al clickear, lo que da
    un oráculo limpio por título de ventana."""
    import os
    import time
    import subprocess
    # Cerrar TODOS los navegadores y ESPERAR a que no quede ninguna ventana del
    # fixture (Edge/Chrome son single-instance + session-restore: si quedan tabs
    # viejos con 'OK-clickeado', contaminan la verificación de la próxima misión —
    # mismo gotcha que Notepad UWP). Reintentar el kill hasta que el título
    # desaparezca, cap ~6s.
    _deadline_kill = time.time() + 6.0
    while time.time() < _deadline_kill:
        _kill_process("msedge.exe")
        _kill_process("chrome.exe")
        time.sleep(0.7)
        if _gemma_click_test_title() is None:
            break
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "click_target.html")
    try:
        os.startfile(fixture)  # type: ignore[attr-defined]
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", fixture])
        except Exception:
            pass
    # Poll hasta que el título base 'listo-para-clickear' esté presente (render
    # listo) — el cold start del navegador es variable; un sleep fijo daba flaky
    # en la 2da/3ra misión. Cap ~12s.
    deadline = time.time() + 12.0
    time.sleep(2.0)
    while time.time() < deadline:
        t = (_gemma_click_test_title() or "").lower()
        if "listo-para-clickear" in t:
            time.sleep(0.6)  # un respiro extra para que el botón sea clickeable
            _focus_window_substr("gemma4 click test")  # dejar Edge al frente
            time.sleep(0.4)
            return
        time.sleep(0.7)


def _focus_window_substr(substr: str) -> None:
    """Trae al frente la ventana cuyo título contiene substr (setup del harness:
    el agente clickea por coordenada/OCR sobre el FOREGROUND; si Edge no está al
    frente tras el reset, el click cae en la ventana equivocada). Usa el foco
    ROBUSTO del proyecto (win_focus: ALT+AttachThreadInput) porque el
    SetForegroundWindow directo lo bloquea el foreground-lock de Windows."""
    try:
        import win32gui
        s = substr.lower()
        target = []
        def _cb(h, _):
            if win32gui.IsWindowVisible(h) and s in (win32gui.GetWindowText(h) or "").lower():
                target.append((h, win32gui.GetWindowText(h)))
            return True
        win32gui.EnumWindows(_cb, None)
        if not target:
            return
        hwnd, title = target[0]
        try:
            from gemma4_agent.win_focus import focus_and_maximize
            focus_and_maximize(hwnd, expected_title_substr=title or None)
            return
        except Exception:
            pass
        try:
            import win32con
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
    except Exception:
        pass


def _calc_display_value() -> str | None:
    """Lee el valor del display de la Calculadora (AutomationId
    'CalculatorResults', Name tipo 'Se muestra 7' / 'Display is 7'). Devuelve el
    Name del elemento o None. Es el ESTADO real del SO — distingue el dígito
    clickeado de los botones (que también contienen dígitos en su nombre)."""
    try:
        import uiautomation as auto
        for w in auto.GetRootControl().GetChildren():
            if "calc" not in (w.Name or "").lower():
                continue
            queue = list(w.GetChildren())
            seen = 0
            while queue and seen < 600:
                el = queue.pop(0)
                seen += 1
                try:
                    if (el.AutomationId or "") == "CalculatorResults":
                        return el.Name or ""
                except Exception:
                    pass
                try:
                    queue.extend(el.GetChildren())
                except Exception:
                    pass
        return None
    except Exception:
        return None


def _reset_calc_clean() -> None:
    """Abre la Calculadora LIMPIA para las misiones click_button: mata la
    instancia previa, abre una nueva y manda Escape (limpia el display). Así el
    verificador parte de display vacío y un dígito clickeado se distingue."""
    _kill_process("CalculatorApp.exe")
    import time
    time.sleep(0.4)
    _launch_detached("calc.exe")
    time.sleep(1.4)
    try:
        # Escape limpia el display de la Calculadora si quedó algo.
        import subprocess
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "$w=New-Object -ComObject WScript.Shell; $w.AppActivate('Calculadora') | Out-Null; Start-Sleep -Milliseconds 300; $w.SendKeys('{ESC}')"],
                       capture_output=True, timeout=8)
    except Exception:
        pass


def _launch_detached(exe: str) -> bool:
    """Abre un exe (para reset de misiones de 'cerrar'). best-effort."""
    try:
        subprocess.Popen([exe], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                         | getattr(subprocess, "DETACHED_PROCESS", 0))
        import time
        time.sleep(1.2)  # dar tiempo a que arranque
    except Exception:
        pass
    return True


def _clear_notepad_session() -> bool:
    """Borra el TabState del Notepad UWP (Win11) para que abra LIMPIO sin
    session-restore. Sin esto, Notepad reabre las pestañas sucias que quedaron
    de misiones anteriores (texto '*hola mundo' sin guardar) -> la misión de
    'cerrar' ve 2-3 ventanas zombies y da FALSO FAIL irreproducible.
    Es limpieza de FIXTURE de test (pestañas SIN guardar generadas por el propio
    eval), no toca documentos guardados. best-effort. Hay que matar Notepad
    ANTES o el proceso reescribe el TabState al salir. Descubierto 2026-05-24:
    Notepad moderno es proceso ÚNICO + residente + session-restore."""
    import os
    import glob
    base = os.environ.get("LOCALAPPDATA", "")
    ts = os.path.join(base, "Packages",
                      "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
                      "LocalState", "TabState")
    try:
        if os.path.isdir(ts):
            for f in glob.glob(os.path.join(ts, "*")):
                try:
                    os.remove(f)
                except OSError:
                    pass
    except Exception:
        pass
    return True


def _set_mute(on: bool) -> None:
    try:
        v = _endpoint_volume()
        v.SetMute(bool(on), None)
    except Exception:
        pass


def _exe_exists(exe: str) -> bool:
    """¿El exe está en PATH o es una app nativa de Windows conocida?
    WordPad NO va acá: Microsoft lo deprecó/quitó en Windows 11 24H2+ (2024),
    así que no es 'siempre presente'. Si está en PATH, which lo encuentra."""
    import shutil, os as _os
    if shutil.which(exe):
        return True
    # nativas que no están en PATH pero existen siempre en Windows
    if exe.lower() in {"calculatorapp.exe", "notepad.exe", "mspaint.exe"}:
        return True
    # wordpad: solo si realmente existe el binario (deprecado en 24H2)
    if exe.lower() == "wordpad.exe":
        for base in (_os.environ.get("ProgramFiles", r"C:\Program Files"),
                     _os.environ.get("ProgramW6432", r"C:\Program Files")):
            if _os.path.isfile(_os.path.join(base, "Windows NT", "Accessories", "wordpad.exe")):
                return True
        return False
    return False


# Construir el set ampliado una vez al importar.
MISSIONS_EXT: list[GuiMission] = MISSIONS + _build_extended()


def missions_for_tier(tier: int | None = None, extended: bool = True) -> list[GuiMission]:
    src = MISSIONS_EXT if extended else MISSIONS
    if tier is None:
        return list(src)
    return [m for m in src if m.tier == tier]
