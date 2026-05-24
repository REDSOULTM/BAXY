"""Guardas de seguridad para acciones GUI (Fase 5 computer-use).

Dos protecciones estructurales, deterministas, que miden la FORMA/el ESTADO del
SO (no el contenido) — alineadas con CLAUDE.md (#6 respetar recursos del usuario;
guardas estructurales permitidas):

1. USER-ACTIVITY (GetLastInputInfo): no pelear el mouse/teclado con el usuario.
   Si el usuario tocó input hace muy poco (idle < umbral) cuando el agente va a
   mover el mouse / teclear, el agente está compitiendo por el control físico —
   un click del agente mientras el usuario escribe puede ir a la ventana
   equivocada y, peor, robarle el foco. Devolvemos un bloqueo suave para que el
   agente espere/avise en vez de forzar.

2. PASSWORD-FIELD (UIA IsPasswordPropertyId = 30019): NUNCA teclear en un campo
   de contraseña. Si el elemento en foco es un campo password, el agente cede el
   control (secret handoff): no teclea, no lee, no loguea el valor. Best-effort:
   en campos NATIVOS (Win32/WinUI, diálogos de credenciales, instaladores) la
   propiedad UIA es fiable; en contenido web Chromium el árbol AX es disperso y
   puede NO exponerla — ahí esta guarda no garantiza detección (limitación
   documentada), pero cuando detecta, bloquea.

Gates por env:
  GEMMA4_GUI_USER_ACTIVITY_GUARD=0  -> desactiva la guarda de actividad.
  GEMMA4_GUI_USER_IDLE_MIN_MS (default 1500) -> umbral de idle para considerar
     que el usuario está ACTIVO (idle menor = activo = bloquear).
  GEMMA4_GUI_PASSWORD_GUARD=0 -> desactiva la guarda de password.

Todo best-effort: cualquier fallo de medición -> no bloquea (no romper la acción
por un fallo de la guarda; el costo de un falso bloqueo es peor que el de medir).
"""
from __future__ import annotations

import ctypes
import os
import subprocess
from ctypes import wintypes
from typing import Any


def _env_off(name: str) -> bool:
    return os.environ.get(name, "1").strip().lower() in {"0", "false", "no", "off"}


# --- 3. activity-budget por turno (R8: anti pop-up / visual injection) -------
# Cap duro de ACCIONES FÍSICAS (click/type/drag/...) por turno de voz. Acota el
# blast-radius de un pop-up adversarial: un pop-up solo puede capturar N clicks
# antes de que el agente se detenga y pida confirmación, en vez de "distraerse"
# indefinidamente (Visual Confused Deputy, ACL 2025 ASR 86%). Estructural: mide
# CUÁNTAS acciones, no su contenido. Reset por turno (reset_action_budget).
_GUI_ACTIONS_THIS_TURN: int = 0


def _action_budget() -> int:
    try:
        return max(1, int(os.environ.get("GEMMA4_GUI_ACTION_BUDGET", "6")))
    except ValueError:
        return 6


def reset_action_budget() -> None:
    """Resetear el contador de acciones físicas (llamar al empezar cada turno)."""
    global _GUI_ACTIONS_THIS_TURN
    _GUI_ACTIONS_THIS_TURN = 0


def check_action_budget() -> dict[str, Any] | None:
    """Devuelve un dict de bloqueo si ya se agotó el presupuesto de acciones
    físicas del turno, o None si se puede proceder. NO consume (eso lo hace
    note_action). Gate GEMMA4_GUI_ACTION_BUDGET_GUARD."""
    if _env_off("GEMMA4_GUI_ACTION_BUDGET_GUARD"):
        return None
    budget = _action_budget()
    if _GUI_ACTIONS_THIS_TURN < budget:
        return None
    return {
        "ok": False,
        "blocked": "action_budget_exhausted",
        "status": "needs_user",
        "actions_this_turn": _GUI_ACTIONS_THIS_TURN,
        "budget": budget,
        "reason": (f"ya hice {_GUI_ACTIONS_THIS_TURN} acciones físicas en este "
                   f"turno (tope {budget}); me detengo para no encadenar clicks a "
                   "ciegas (posible pop-up/desvío). Confirmá si seguís."),
        "completion_status": "action_budget_exhausted",
    }


def note_action() -> None:
    """Consume una unidad del presupuesto de acciones físicas del turno."""
    global _GUI_ACTIONS_THIS_TURN
    _GUI_ACTIONS_THIS_TURN += 1


# --- 4. anchor-binding (R8.2: clic a bait de pop-up no relacionado al objetivo)
# CALIBRADO (2026-05-25): un umbral de cosine(goal,label) solo NO separa (legit
# 'Guardar'=0.156 se solapa con inject 0.267). La señal robusta es COMBINADA: un
# control real es CORTO (<=3 palabras); el bait de pop-up es una FRASE imperativa
# LARGA y NO relacionada al objetivo del turno. Flag SOLO si (label >=4 palabras)
# Y (cosine con el goal < 0.30). Medido: 0/12 fricción (no bloquea labels cortos
# legítimos) y 5/10 protección (frena el bait obvio; el resto lo acota el
# activity-budget). NO es hard-abort: es un soft-flag para que el agente confirme.
_TURN_GOAL: str = ""
_ANCHOR_COS_MAX = 0.30
_ANCHOR_MIN_WORDS = 4


def set_turn_goal(goal: str) -> None:
    """Fijar el objetivo (utterance del usuario) del turno top-level actual, para
    el anchor-binding. Llamar al empezar el turno."""
    global _TURN_GOAL
    _TURN_GOAL = (goal or "").strip()


def check_anchor(label: str) -> dict[str, Any] | None:
    """Devuelve un dict de bloqueo si el `label` del click parece BAIT de pop-up
    (frase larga NO relacionada al objetivo del turno), o None si se puede
    clickear. Conservador por diseño: solo frena el caso claro. Gate
    GEMMA4_GUI_ANCHOR_GUARD."""
    if _env_off("GEMMA4_GUI_ANCHOR_GUARD"):
        return None
    lbl = (label or "").strip()
    if not lbl or not _TURN_GOAL:
        return None
    if len(lbl.split()) < _ANCHOR_MIN_WORDS:
        return None  # control corto -> legítimo, no se evalúa (evita fricción)
    try:
        from .semantic_router import embed
        gv = embed(_TURN_GOAL)
        lv = embed(lbl)
        if gv is None or lv is None:
            return None  # sin encoder -> fallback seguro (no bloquear)
        sim = float(sum(a * b for a, b in zip(gv, lv)))
    except Exception:
        return None
    if sim >= _ANCHOR_COS_MAX:
        return None  # relacionado al objetivo -> pasa
    return {
        "ok": False,
        "blocked": "anchor_mismatch",
        "status": "needs_user",
        "label": lbl,
        "goal": _TURN_GOAL[:80],
        "similarity": round(sim, 3),
        "reason": (f"el control «{lbl[:50]}» no se relaciona con lo que pediste "
                   f"(«{_TURN_GOAL[:50]}»); parece un pop-up/desvío. No lo clickeo "
                   "sin que confirmes."),
        "completion_status": "anchor_mismatch",
    }


# El agente también genera input sintético (mouse_event/SendKeys) que resetea
# GetLastInputInfo. Para no auto-bloquearse en acciones multi-paso, registramos
# cuándo el AGENTE tocó input por última vez; si la actividad reciente cae dentro
# de la ventana del propio agente, NO la contamos como actividad del usuario.
import time as _time
_last_agent_input_ts: float = 0.0


def note_agent_input() -> None:
    """Llamar JUSTO DESPUÉS de que el agente envía input sintético (click/type).
    Marca que la actividad inmediatamente previa fue NUESTRA, no del usuario."""
    global _last_agent_input_ts
    _last_agent_input_ts = _time.monotonic()


# --- 1. user-activity (GetLastInputInfo) -----------------------------------

class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def user_idle_ms() -> int | None:
    """Milisegundos desde el último input (mouse O teclado) del USUARIO,
    system-wide. None si no se pudo medir. Nota: el propio input sintético del
    agente (mouse_event/SendKeys) también resetea esto — por eso la guarda se
    consulta ANTES de actuar, no después."""
    try:
        li = _LASTINPUTINFO()
        li.cbSize = ctypes.sizeof(li)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            return None
        return int(ctypes.windll.kernel32.GetTickCount()) - int(li.dwTime)
    except Exception:
        return None


def _idle_threshold_ms() -> int:
    try:
        return max(0, int(os.environ.get("GEMMA4_GUI_USER_IDLE_MIN_MS", "1500")))
    except ValueError:
        return 1500


def user_is_active() -> bool:
    """True si el USUARIO tocó input MÁS RECIENTE que el umbral (está usando la
    máquina ahora). Si no se puede medir -> False (no bloquear). Excluye la
    actividad sintética del propio agente: si el último input del agente fue
    hace menos que el idle medido, la actividad reciente fue NUESTRA, no del
    usuario -> no bloquear."""
    if _env_off("GEMMA4_GUI_USER_ACTIVITY_GUARD"):
        return False
    idle = user_idle_ms()
    if idle is None:
        return False
    if idle >= _idle_threshold_ms():
        return False
    # Hay actividad reciente. ¿Fue del agente? Si el agente tecleó/clickeó hace
    # ~ (idle + margen) ms, esa es la actividad detectada -> no es el usuario.
    if _last_agent_input_ts:
        since_agent_ms = (_time.monotonic() - _last_agent_input_ts) * 1000.0
        # margen: la actividad detectada (idle) es atribuible al agente si su
        # último input es de hace un poco MÁS que el idle (el input del agente
        # ocurrió y luego pasó `idle` ms).
        if since_agent_ms <= idle + 500:
            return False
    return True


def check_user_activity() -> dict[str, Any] | None:
    """Devuelve un dict de bloqueo si el usuario está activo, o None si se puede
    proceder. El caller (tool GUI) corta y devuelve este dict como resultado."""
    if not user_is_active():
        return None
    idle = user_idle_ms()
    return {
        "ok": False,
        "blocked": "user_active",
        "status": "deferred",
        "idle_ms": idle,
        "threshold_ms": _idle_threshold_ms(),
        "reason": ("el usuario está usando el mouse/teclado ahora mismo "
                   f"(idle {idle} ms); no tomo el control físico para no "
                   "pelear el foco — pedile que suelte el control o reintentá."),
        "completion_status": "deferred_user_active",
    }


# --- 2. password-field (UIA IsPasswordPropertyId) ---------------------------

# PowerShell que lee IsPassword del elemento EN FOCO. Devuelve "1"/"0"/"NA".
# Acotado y rápido (~150-300ms). Best-effort.
_PWD_PROBE_PS = r"""
$ErrorActionPreference='Stop'
try {
  Add-Type -AssemblyName UIAutomationClient
  Add-Type -AssemblyName UIAutomationTypes
  $f=[System.Windows.Automation.AutomationElement]::FocusedElement
  if($null -eq $f){ Write-Output 'NA'; exit 0 }
  $p=$f.GetCurrentPropertyValue([System.Windows.Automation.AutomationElement]::IsPasswordProperty)
  if($p -eq $true){ Write-Output '1' } else { Write-Output '0' }
} catch { Write-Output 'NA' }
"""


def focused_is_password() -> bool | None:
    """¿El elemento en foco es un campo de contraseña (UIA IsPassword)? True/
    False, o None si no se pudo determinar. Fiable en campos nativos; en web
    Chromium puede dar None/False aunque sea password (limitación AX del CEF)."""
    if _env_off("GEMMA4_GUI_PASSWORD_GUARD"):
        return None
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _PWD_PROBE_PS],
            capture_output=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
        if out == "1":
            return True
        if out == "0":
            return False
        return None
    except Exception:
        return None


def check_password_field() -> dict[str, Any] | None:
    """Devuelve un dict de bloqueo si el foco está en un campo password, o None
    si se puede teclear. SECRET HANDOFF: no tecleamos el secreto, no lo leemos,
    no lo logueamos."""
    if focused_is_password() is True:
        return {
            "ok": False,
            "blocked": "password_field",
            "status": "needs_user",
            "reason": ("el campo en foco es de CONTRASEÑA; no tecleo secretos. "
                       "Escribila vos directamente (secret handoff)."),
            "completion_status": "secret_handoff",
        }
    return None
