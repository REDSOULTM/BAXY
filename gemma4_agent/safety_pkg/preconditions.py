"""Catálogo declarativo de PRECONDICIONES.

Ley del proyecto #5: "el código garantiza sus precondiciones". La verificación
de precondiciones vive ad-hoc por tool (app_open verifica `apps.find`; whatsapp
verifica instalación). Este módulo centraliza el patrón en un catálogo reusable
+ testeable:

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


# check(args, ctx=None) -> bool | None  (True=cumple, False=no, None=no medible)
#   ctx: recursos COMPARTIDOS del llamador (p.ej. ctx["app_resolver"] = la
#   instancia warm de la registry) — evita reconstruir estado caro por chequeo.
# repair(args) -> bool        (True si la reparó)
@dataclass
class Precondition:
    name: str
    check: Callable[..., bool | None]
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

def _app_is_resolvable(args: dict[str, Any], ctx: dict[str, Any] | None = None) -> bool | None:
    """¿La app pedida existe en el sistema (PATH/StartMenu/registry/Steam)?

    Reusa el AppResolver COMPARTIDO de la registry si el llamador lo pasa por
    ctx["app_resolver"] — la MISMA instancia (fuentes warm + memo del deep scan)
    que usaría app.open. CAUSA RAÍZ medida (2026-06-10): construir acá un
    AppResolver() fresco recargaba TODAS las fuentes (~5s, 2 spawns PowerShell)
    + deep scan sin memo (~4s) EN CADA chequeo -> ~10s por execute(app.open),
    pagados DOS VECES por turno (open-net en decide + re-llamada del 4B) = el
    grueso de los 20-31s del turno "abrí <app inexistente>". Sin ctx (tests,
    llamadores viejos) cae al fresco; si nada se puede construir, None
    (no bloquear sin evidencia)."""
    name = str(args.get("name") or "").strip()
    if not name:
        return None
    try:
        resolver = (ctx or {}).get("app_resolver")
        if resolver is None:
            from ..tools_pkg.app_resolver import AppResolver
            resolver = AppResolver()
        return bool(resolver.find(name))
    except Exception:
        return None


def _whatsapp_installed(args: dict[str, Any], ctx: dict[str, Any] | None = None) -> bool | None:
    """¿WhatsApp Desktop está instalado? Reusa _find_whatsapp_app (Get-AppxPackage).
    None si la detección falla (no bloquear)."""
    try:
        from ..domain_tools import _find_whatsapp_app
        info = _find_whatsapp_app()
        return bool(info.get("kind"))
    except Exception:
        return None


# --- Catálogo: solo las 2 tools de mayor flake (Fase A) ----------------------
# app_open: si la app no resuelve, app.open igual fallaría -> atrapar antes con un
#   mensaje claro. repair=None (NO instalamos winget a ciegas: sería acción no pedida).
# whatsapp: si no está instalado, el envío fallaría -> needs_user honesto.
PRECONDITIONS_CATALOG: dict[str, list[Precondition]] = {
    "app": [
        Precondition(
            name="app_resolvable",
            check=_app_is_resolvable,
            repair=None,
            fail_message="No encuentro esa aplicación en el sistema. ¿Está instalada y escrita igual?",
        ),
    ],
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
    "app": frozenset({"open"}),
    "whatsapp": frozenset({"send_message", "send", "open_chat"}),
}


def ensure_preconditions(tool_name: str, args: dict[str, Any],
                         ctx: dict[str, Any] | None = None) -> PreconditionResult | None:
    """Evalúa las precondiciones de una tool ANTES de ejecutarla.

    Devuelve:
      - None  -> no hay precondiciones, o todas OK/unknown -> SEGUIR (fail-open).
      - PreconditionResult(needs_user) -> bloquear con mensaje accionable.

    `ctx`: recursos compartidos del llamador para los checks (ver Precondition).
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
            verdict = prec.check(args, ctx)
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
