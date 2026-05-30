"""Structural per-tool verifier registry.

Filosofia (heredada de ContextoCarter V3/V4): una tool retornando ok=True NO
es suficiente. El agente debe LEER el estado real del sistema y declarar si
el efecto se materializo. Si no se puede medir, decir "no verificable"
explicitamente — no fingir.

Diseño:
  - Decorator `@register_verifier(tool_name)` asocia una funcion al nombre
    de la tool. La funcion recibe (args, result) y devuelve VerifierOutcome.
  - Tristate honest: confirmed=True (efecto medido), False (medido pero
    distinto al esperado), None (no medible).
  - `verify(tool_name, args, result)` lookups el verifier registrado; si no
    hay, devuelve confirmed=None con reason explicito.
  - `summarize_verifiers(outcomes)` produce el footer que se concatena al
    reply del LLM para que el usuario vea cuantas tools se verificaron.
  - `record_evidence_for_loop` extrae los evidence_keys del outcome y los
    inyecta al LoopState para resetear el warning_count en progreso real
    (TIER 1 #1 + #2 integration).

NO usa LLM para verificar (eso fue un bug historico de generaciones previas).
Cada verifier es una funcion pura sobre el estado del SO.

Opt-out: GEMMA4_VERIFIER_OFF=1 desactiva todo el sistema; verify() siempre
devuelve confirmed=None con reason="disabled_by_env".
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class VerifierOutcome:
    """Resultado de la verificacion estructural de una tool ejecutada.

    confirmed:
      - True:  efecto medido y confirmado por estado del SO
      - False: efecto medido pero distinto al esperado (failure)
      - None:  no medible (no_verifier_registered, async dispatch, dep faltante)

    reason: texto corto explicando el outcome (para el footer + logs).

    detail: dict opcional con metadata estructurada (e.g. {"expected": 50,
    "actual": 48} en volume verification).

    evidence_keys: lista de strings tipo "app:Steam" / "file:/tmp/x" /
    "window:Notepad". Si confirmed=True, el agent llamara
    loop_state.record_evidence(key) para resetear el warning_count del
    loop detector (TIER 1 #1).
    """
    tool_name: str
    confirmed: bool | None
    reason: str
    detail: dict | None = None
    evidence_keys: list[str] = field(default_factory=list)
    # B1 (competidores, 2026-05-29): clasificación del fallo para recuperación
    # por TIPO (replan/amend/skip). None hasta que un verifier lo setee o
    # classify_failure() lo infiera. Ver ERR_* abajo.
    error_type: str | None = None


# --- B1: tipos de error para recuperación (replan/amend/skip) --------------
# missing_precondition: el efecto requiere algo que no existe aún (ventana/app
#   no abierta, archivo inexistente) -> REPLAN (hacer el prerequisito primero).
# param_mismatch: faltó/erró un argumento (sin target, ruta mala) -> AMEND
#   (reintentar la misma tool con args corregidos).
# transient: timeout/red/recurso ocupado -> SKIP/retry-1 (no culpa de la tool).
# tool_not_found: la tool/acción no existe (unknown tool, action fuera del enum)
#   -> IRRECUPERABLE por reintento: la MISMA call siempre falla igual. budget=0.
# unknown: no clasificable -> SKIP conservador (sin recuperación).
ERR_MISSING_PRECONDITION = "missing_precondition"
ERR_PARAM_MISMATCH = "param_mismatch"
ERR_TRANSIENT = "transient"
ERR_TOOL_NOT_FOUND = "tool_not_found"
ERR_UNKNOWN = "unknown"
RECOVERABLE_ERROR_TYPES = frozenset(
    {ERR_MISSING_PRECONDITION, ERR_PARAM_MISMATCH, ERR_TRANSIENT})


# --- H2 (perfection roadmap 2026-05-29): presupuesto de retry POR CLASE ------
# El research midió "466 de 513 retries desperdiciados en errores que NINGÚN
# retry arregla". El límite global de max_agent_turns no distingue: un
# TOOL_NOT_FOUND irrecuperable quemaba los 8 turnos reintentando, mientras un
# TRANSIENT legítimo competía por los mismos turnos. El budget por-clase corta
# el desperdicio en la raíz: cuando una clase agota su budget, el hint pasa de
# "reintentá" a "no reintentes más esta acción, escalá honestamente al usuario".
#
# Valores (conservadores, basados en la semántica del tipo, no en magia):
#   tool_not_found      = 0  -> la misma call SIEMPRE falla; reintentar es inútil.
#   unknown             = 0  -> no sabemos qué arreglar; reintentar a ciegas = ruido.
#   param_mismatch      = 1  -> 1 corrección de args (el caso típico se arregla en 1).
#   missing_precondition= 1  -> 1 replan (hacer el prerequisito y reintentar).
#   transient           = 2  -> red/timeout puede ceder; 2 reintentos con backoff.
_RETRY_BUDGET: dict[str, int] = {
    ERR_TOOL_NOT_FOUND: 0,
    ERR_UNKNOWN: 0,
    ERR_PARAM_MISMATCH: 1,
    ERR_MISSING_PRECONDITION: 1,
    ERR_TRANSIENT: 2,
}


def retry_budget_for(error_type: str | None) -> int:
    """Presupuesto de reintentos para una clase de error (H2). 0 = no reintentar.

    Pura: no toca estado. El agente lleva el contador `spent[err_class]` por turno
    y, al agotarlo, deja de pedir reintentos para esa clase. Un tipo desconocido
    cae a 0 (conservador: nunca reintentar a ciegas)."""
    if not error_type:
        return 0
    return _RETRY_BUDGET.get(error_type, 0)


# Registry global de verifiers. Una entrada por tool_name. Si una tool tiene
# multiples actions (ej. "app" con open/close/search), el verifier recibe
# args y switchea internamente.
VerifierFn = Callable[[dict, dict], VerifierOutcome]
_VERIFIERS: dict[str, VerifierFn] = {}


def register_verifier(tool_name: str) -> Callable[[VerifierFn], VerifierFn]:
    """Decorator para registrar el verifier de una tool.

    Uso tipico (en verifiers.py):

        @register_verifier("app")
        def verify_app(args: dict, result: dict) -> VerifierOutcome:
            action = args.get("action", "")
            if action == "open":
                ...
            return VerifierOutcome("app", None, "unknown action")

    Si dos modulos registran la misma tool, el ultimo gana — usar con
    cuidado en imports condicionales.
    """
    def decorator(fn: VerifierFn) -> VerifierFn:
        if tool_name in _VERIFIERS:
            logger.debug("verifier override for %s: %s -> %s",
                         tool_name, _VERIFIERS[tool_name].__name__, fn.__name__)
        _VERIFIERS[tool_name] = fn
        return fn
    return decorator


def _enabled() -> bool:
    raw = (os.environ.get("GEMMA4_VERIFIER_OFF") or "").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


def verify(tool_name: str, args: dict, result: dict) -> VerifierOutcome:
    """Ejecuta el verifier registrado para esta tool.

    Si no hay verifier, retorna confirmed=None (honest about not measuring).
    Si el verifier crashea, retorna confirmed=False con la excepcion.
    """
    if not _enabled():
        return VerifierOutcome(
            tool_name=tool_name,
            confirmed=None,
            reason="disabled_by_env",
        )

    fn = _VERIFIERS.get(tool_name)
    if fn is None:
        return VerifierOutcome(
            tool_name=tool_name,
            confirmed=None,
            reason="no_verifier_registered",
        )
    try:
        outcome = fn(args or {}, result or {})
        # Normalizacion defensiva: si el verifier devolvio algo raro,
        # convertirlo a un outcome valido sin crashear el turn.
        if not isinstance(outcome, VerifierOutcome):
            return VerifierOutcome(
                tool_name=tool_name,
                confirmed=False,
                reason=f"verifier returned non-VerifierOutcome: {type(outcome).__name__}",
            )
        return outcome
    except Exception as exc:  # noqa: BLE001
        return VerifierOutcome(
            tool_name=tool_name,
            confirmed=False,
            reason=f"verifier crashed: {type(exc).__name__}: {exc}",
        )


def summarize_verifiers(outcomes: list[VerifierOutcome]) -> str:
    """Footer honesto que se concatena al reply del LLM.

    Solo aparece si hay algo NEGATIVO concreto que reportar:
      - failed > 0  ->  emite footer (importante para el user)
      - todos confirmed=True / None / mix -> NO emite (sin failure no aporta).

    2026-05-15 post-audit: el "N no verificable(s)" generaba ruido visual
    en el user cuando una tool dispatch async legitima (URL abierta,
    deeplink, media key) reportaba confirmed=None. El user lo interpretaba
    como fallo de la accion. Ahora solo emitimos cuando hay un failed real.
    """
    if not outcomes:
        return ""
    failed = sum(1 for o in outcomes if o.confirmed is False)
    if failed == 0:
        return ""
    # Solo cuando hay un failed real, surfaceamos el conteo con contexto.
    confirmed = sum(1 for o in outcomes if o.confirmed is True)
    unverifiable = sum(1 for o in outcomes if o.confirmed is None)
    parts = [f"{failed} no confirmada(s)"]
    if confirmed:
        parts.insert(0, f"{confirmed} verificada(s)")
    if unverifiable:
        parts.append(f"{unverifiable} no verificable(s)")
    return f"\n\n[{', '.join(parts)}]"


def collect_evidence_keys(outcomes: list[VerifierOutcome]) -> list[str]:
    """Aplana los evidence_keys de outcomes confirmed=True.

    El caller (agent.run_content) los usa para inyectar al LoopState:

        for ek in collect_evidence_keys(outcomes):
            loop_state.record_evidence(ek)

    Solo se incluyen keys de outcomes con confirmed=True — un False/None
    NO es evidencia de progreso real.
    """
    keys: list[str] = []
    for o in outcomes:
        if o.confirmed is True and o.evidence_keys:
            keys.extend(o.evidence_keys)
    return keys


def classify_failure(result: dict | None, reason: str = "", *, given: str | None = None) -> str:
    """Clasifica un fallo (confirmed=False) en un ERR_* para decidir la recuperación.

    PREFIERE señales ESTRUCTURADAS (status codes, campos del result). Si el verifier
    ya seteó `error_type` (given), eso gana. Ante la duda devolvemos ERR_UNKNOWN
    (-> SKIP, sin recuperación) — nunca recuperamos a ciegas.

    NB: el fallback de texto usa subcadenas multi-idioma como heurística best-effort
    (no autoritativa, erra a UNKNOWN). La señal primaria es estructural; lo ideal es
    que cada verifier setee error_type. Una mis-clasificación a un tipo recuperable
    sólo dispara un HINT de reintento (daño bajo); a unknown/transient -> skip (seguro).
    """
    if given in {ERR_MISSING_PRECONDITION, ERR_PARAM_MISMATCH, ERR_TRANSIENT,
                 ERR_TOOL_NOT_FOUND, ERR_UNKNOWN}:
        return given
    r = result or {}
    status = str(r.get("status") or "").casefold()
    # ESTRUCTURAL primero (autoritativo, no depende de idioma):
    # tool/acción inexistente -> IRRECUPERABLE (budget=0). El dispatcher marca
    # "unknown tool: X" o devuelve validation_errors para una acción fuera del
    # enum. Reintentar la MISMA call siempre da el mismo error -> tool_not_found.
    err_blob = str(r.get("error") or "").casefold()
    if err_blob.startswith("unknown tool") or "unknown tool:" in err_blob:
        return ERR_TOOL_NOT_FOUND
    if r.get("validation_errors") or err_blob.startswith("invalid tool arguments"):
        # acción/arg fuera del enum: el 4B inventó una acción que no existe.
        # Corregible reintentando con la acción válida -> param_mismatch (budget 1).
        return ERR_PARAM_MISMATCH
    if status in {"needs_dependency", "needs_resource"}:
        return ERR_MISSING_PRECONDITION
    if r.get("missing"):  # algunos tools declaran qué argumento faltó (estructural)
        return ERR_PARAM_MISMATCH
    blob = f"{reason} {r.get('error') or ''} {r.get('completion_status') or ''}".casefold()
    if any(k in blob for k in ("not found", "no encontr", "no existe", "doesn't exist",
                               "introuvable", "nicht gefunden", "inexistent", "no such")):
        return ERR_MISSING_PRECONDITION
    if any(k in blob for k in ("no se especific", "no se proporcion", "missing", "required",
                               "requiere", "falta", "not specified", "sin destinatario",
                               "qué ventana", "which window", "no target")):
        return ERR_PARAM_MISMATCH
    if any(k in blob for k in ("timeout", "timed out", "network", "connection", "conexión",
                               "temporal", "busy", "ocupad", "rate limit", "try again")):
        return ERR_TRANSIENT
    return ERR_UNKNOWN


def registered_tool_names() -> list[str]:
    """Para tests/debug: nombres de tools con verifier registrado."""
    return sorted(_VERIFIERS.keys())


def _clear_registry_for_tests() -> None:
    """Solo para tests aislados que necesiten un registry limpio."""
    _VERIFIERS.clear()
