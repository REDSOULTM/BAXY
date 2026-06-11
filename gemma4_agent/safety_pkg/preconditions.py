"""Catálogo declarativo de PRECONDICIONES.

Ley del proyecto #5: "el código garantiza sus precondiciones". La verificación
de precondiciones vive ad-hoc por tool (whatsapp verifica instalación). Este
módulo centraliza el patrón en un catálogo reusable + testeable:

    tool -> [Precondition(name, check, repair)]

evaluado ANTES de actuar. `check()` lee ESTADO DEL SO (registry, tasklist, UIA)
— NUNCA listas de keywords por idioma. `repair()` es idempotente; si no puede,
devuelve needs_user honesto (que encaja con ERR_MISSING_PRECONDITION del
recovery, budget=1). Fuente research: InferAct arXiv:2407.11843.

DISEÑO HONESTO: si un check no puede medir de forma fiable (UIA inconsistente),
devuelve None ("no sé") en vez de adivinar — el llamador NO bloquea ante None
(fail-open: mejor intentar que rechazar sin evidencia). Solo un False MEDIDO
bloquea con un mensaje accionable.

GATING: GEMMA4_PRECONDITIONS (DEFAULT ON: validado en vivo que no agrega latencia
ni falsos bloqueos — ver nota en preconditions_enabled()).
Kill-switch GEMMA4_PRECONDITIONS=0. Sin servidores/tools configurados -> no-op.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable


# Resultado de chequear/reparar una precondición.
#   ok        : la precondición se cumple -> seguir.
#   repaired  : no se cumplía pero repair() la resolvió -> seguir.
#   needs_user: no se cumple y no se puede reparar sin el usuario -> bloquear honesto.
#   unknown   : no medible de forma fiable -> NO bloquear (fail-open).
RESULT_OK = "ok"
RESULT_REPAIRED = "repaired"
RESULT_NEEDS_USER = "needs_user"
RESULT_UNKNOWN = "unknown"


@dataclass
class PreconditionResult:
    status: str               # uno de RESULT_*
    name: str                 # qué precondición
    detail: str = ""          # mensaje accionable (para needs_user)


# check(args) -> bool | None  (True=cumple, False=no, None=no medible)
# repair(args) -> bool        (True si la reparó)
# OJO si se agrega un check nuevo: NO construir recursos caros por chequeo
# (un AppResolver() fresco acá costó ~10s por execute, medido 2026-06-10) y
# NO bloquear un caso que la tool resuelve mejor aguas abajo (el check de app
# mataba el site-fallback de t_app).
@dataclass
class Precondition:
    name: str
    check: Callable[[dict[str, Any]], bool | None]
    repair: Callable[[dict[str, Any]], bool] | None = None
    fail_message: str = "precondición no cumplida"


def preconditions_enabled() -> bool:
    # DEFAULT ON: validado en vivo (3/4 fraseos bloquearon honesto una app
    # inexistente, 0 mentiras; en el caso restante el 4B no ruteó a app y el
    # grounding gate igual fue honesto). Fail-open (None no bloquea) + checks
    # estructurales -> bajo riesgo. Kill-switch GEMMA4_PRECONDITIONS=0.
    return (os.environ.get("GEMMA4_PRECONDITIONS", "1") or "1").strip().lower() not in {
        "0", "false", "no", "off"}


# --- Checks estructurales concretos (leen estado del SO, no keywords) --------

# NOTA (2026-06-10): la precondición `app_resolvable` se RETIRÓ del catálogo.
# Bloqueaba execute(app.open) con needs_user cuando find() no resolvía — y eso
# corre ANTES de t_app, así que MATABA el fallback a sitio web de t_app
# ("abrí pivigames" -> app not found -> resolver el sitio -> abrirlo, fix
# medido 47e6c14). MEDIDO: find("pivigames")=[] -> bloqueo, el sitio nunca se
# resolvía por la ruta app. Su valor de honestidad hoy lo cubren capas mejor
# ubicadas: el piso de apertura de app_open (GEMMA4_APP_OPEN_MIN_SCORE, no
# abre matches débiles) + el guard de claims con tools-fallidas (el reply no
# puede afirmar la acción) — ambos DESPUÉS del web-divert y el site-fallback,
# que es el orden correcto. Además el chequeo construía un AppResolver()
# fresco (~10s por execute, 2x por turno) — causa raíz del turno de 20-31s.


def _whatsapp_installed(args: dict[str, Any]) -> bool | None:
    """¿WhatsApp Desktop está instalado? Reusa _find_whatsapp_app (Get-AppxPackage).
    None si la detección falla (no bloquear)."""
    try:
        from ..domain_tools import _find_whatsapp_app
        info = _find_whatsapp_app()
        return bool(info.get("kind"))
    except Exception:
        return None


# --- Catálogo. whatsapp: si no está instalado, el envío fallaría (o peor,
#   actuaría a medias) -> needs_user honesto ANTES de actuar. repair=None (NO
#   instalamos a ciegas: sería acción no pedida). app_resolvable se retiró —
#   ver la nota de arriba (mataba el site-fallback de t_app).
PRECONDITIONS_CATALOG: dict[str, list[Precondition]] = {
    "whatsapp": [
        Precondition(
            name="whatsapp_installed",
            check=_whatsapp_installed,
            repair=None,
            fail_message="WhatsApp Desktop no está instalado. Instalalo desde Microsoft Store, o pasame el teléfono para usar wa.me.",
        ),
    ],
}


# Qué acciones de cada tool requieren el check (no chequear en status/list/etc).
_ACTIONS_THAT_ACT: dict[str, frozenset[str]] = {
    "whatsapp": frozenset({"send_message", "send", "open_chat"}),
}


def ensure_preconditions(tool_name: str, args: dict[str, Any]) -> PreconditionResult | None:
    """Evalúa las precondiciones de una tool ANTES de ejecutarla.

    Devuelve:
      - None  -> no hay precondiciones, o todas OK/unknown -> SEGUIR (fail-open).
      - PreconditionResult(needs_user) -> bloquear con mensaje accionable.

    Gated por GEMMA4_PRECONDITIONS. Best-effort: cualquier excepción -> None (seguir)."""
    if not preconditions_enabled():
        return None
    try:
        precs = PRECONDITIONS_CATALOG.get(tool_name)
        if not precs:
            return None
        action = str(args.get("action") or "").strip().casefold()
        gate = _ACTIONS_THAT_ACT.get(tool_name)
        if gate is not None and action and action not in gate:
            return None  # acción de solo-lectura: no chequear
        for prec in precs:
            verdict = prec.check(args)
            if verdict is True or verdict is None:
                continue  # cumple, o no medible (fail-open: no bloquear)
            # verdict is False -> intentar reparar
            if prec.repair is not None:
                try:
                    if prec.repair(args):
                        continue  # reparada
                except Exception:
                    pass
            return PreconditionResult(
                status=RESULT_NEEDS_USER, name=prec.name, detail=prec.fail_message)
        return None
    except Exception:
        return None  # nunca romper el dispatch por el chequeo de precondiciones
