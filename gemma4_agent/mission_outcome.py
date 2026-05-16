"""Mission-level outcome computer — combines MissionGoal + per-tool verifiers.

Pipeline:
  1. MissionGoal.from_user_text(prompt) construido al inicio del turn.
  2. Cada tool call: goal.update_with_tool(name, args, ok=result.ok).
  3. Al final: compute_mission_outcome(goal, tool_records, reply_text)
     devuelve un MissionOutcome con status + summary + counters.

El status decide el footer + telemetria. Honestidad: TOOL_OK_VERIFIER_INCONCLUSIVE
es DISTINTO de UNVERIFIED y de FAILED. Reportar mal causa mas dano que no
reportar.

References:
  - Voyager NeurIPS 2023: verify mission OBJECTIVE, not action.
  - Carter v5 mission/verifier.py — 9 outcome states.
  - ContextoCarter V3/V4: honestidad por construccion.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .mission_goal import MissionGoal, MissionOutcome, OutcomeStatus
from .verify_core import VerifierOutcome


# Tools cuyo ok=True NO se puede verificar estructuralmente (dispatch
# asincronico al SO o navegacion web). Si todas las tools del turn son
# de esta lista y vinieron confirmed=None, mapeamos a
# TOOL_OK_VERIFIER_INCONCLUSIVE en vez de UNVERIFIED.
_INCONCLUSIVE_BY_NATURE = frozenset({
    # Dispatch URI (deeplink) — efecto async observable solo por window/screenshot
    "gui",        # click es dispatch ciego sin verify post
    "browser",    # GUI scripted al browser, async
    # web.open usa webbrowser.open — async, no devuelve verify del resultado
    # Sin embargo otras actions de web (research/read) sí miden read_state.
    # Lo manejamos en el caller: solo cuenta como "by nature" si el VerifierOutcome
    # vino None para ESTA llamada concreta.
})


@dataclass(frozen=True)
class _ToolCallRecord:
    """Local mirror — agent.py usa tipos distintos pero pasamos esto al outcome."""
    name: str
    args: dict[str, Any]
    ok: bool
    verifier: VerifierOutcome | None = None


def _enabled() -> bool:
    raw = (os.environ.get("GEMMA4_MISSION_OFF") or "").strip().lower()
    return raw not in {"1", "true", "yes", "on"}


def compute_mission_outcome(
    mission_goal: MissionGoal,
    tool_records: list[_ToolCallRecord],
    reply_text: str = "",
) -> MissionOutcome:
    """Decide el outcome final combinando MissionGoal + verifier counts.

    Prioridad de reglas:
      1. Sistema desactivado (GEMMA4_MISSION_OFF=1)            -> UNVERIFIED
      2. No tools + no expected outcomes (small talk)          -> UNVERIFIED
      3. No tools + expected outcomes con accion               -> INTENT_NOT_FULFILLED
      4. Mission fulfilled + cero failed                       -> COMPLETED
      5. Mission partial (algo matched, falta el resto)        -> PARTIAL
      6. Todo failed                                           -> FAILED
      7. Todo unverified + tools son "by nature" inconclusive  -> TOOL_OK_VERIFIER_INCONCLUSIVE
      8. Todo unverified + read-only legitimo                  -> UNVERIFIED
      9. Mezcla con confirmados                                -> PARTIAL
      10. Fallback                                             -> UNVERIFIED
    """
    if not _enabled():
        return MissionOutcome(
            status=OutcomeStatus.UNVERIFIED,
            summary="mission verifier disabled",
            detail={"reason": "GEMMA4_MISSION_OFF"},
        )

    n_tools = len(tool_records)
    confirmed = sum(
        1 for r in tool_records
        if r.verifier and r.verifier.confirmed is True
    )
    failed = sum(
        1 for r in tool_records
        if r.verifier and r.verifier.confirmed is False
    )
    unverified = sum(
        1 for r in tool_records
        if r.verifier and r.verifier.confirmed is None
    )

    satisfied, expected_total = mission_goal.progress()

    detail = {
        "mission_summary": mission_goal.summary(),
        "executed_tools": [r.name for r in tool_records],
    }

    # ---- No tools ran ----
    if n_tools == 0:
        action_kinds = {
            "open_target", "close_target", "filesystem_write", "navigate",
            "set_state", "destructive_delete", "destructive_install",
        }
        expects_action = any(o.kind in action_kinds for o in mission_goal.expected)
        if expects_action:
            return MissionOutcome(
                status=OutcomeStatus.INTENT_NOT_FULFILLED,
                summary="No se ejecutó ninguna acción aunque la misión la requería.",
                confirmed_count=0, failed_count=0, unverified_count=0,
                expected_total=expected_total, expected_satisfied=satisfied,
                detail=detail,
            )
        # Conversational reply legitimo (preguntas, knowledge, smalltalk)
        return MissionOutcome(
            status=OutcomeStatus.UNVERIFIED,
            summary=(reply_text or "respuesta conversacional")[:120],
            expected_total=expected_total, expected_satisfied=satisfied,
            detail=detail,
        )

    # ---- Tools ran + mission fulfilled + nothing failed ----
    if mission_goal.is_fulfilled() and failed == 0:
        return MissionOutcome(
            status=OutcomeStatus.COMPLETED,
            summary=mission_goal.summary(),
            confirmed_count=confirmed, failed_count=0,
            unverified_count=unverified,
            expected_total=expected_total, expected_satisfied=satisfied,
            detail=detail,
        )

    # ---- Mission partial (some satisfied, some not) ----
    if 0 < satisfied < expected_total:
        return MissionOutcome(
            status=OutcomeStatus.PARTIAL,
            summary=mission_goal.summary(),
            confirmed_count=confirmed, failed_count=failed,
            unverified_count=unverified,
            expected_total=expected_total, expected_satisfied=satisfied,
            detail=detail,
        )

    # ---- All tools failed verifier ----
    if failed > 0 and confirmed == 0 and unverified == 0:
        return MissionOutcome(
            status=OutcomeStatus.FAILED,
            summary="Las herramientas ejecutadas no produjeron efecto medible.",
            confirmed_count=0, failed_count=failed, unverified_count=0,
            expected_total=expected_total, expected_satisfied=satisfied,
            detail=detail,
        )

    # ---- All verifiers inconclusive ----
    if unverified == n_tools and confirmed == 0 and failed == 0:
        # Distinguish dispatch async (GUI click, deeplink) vs legitimate read-only.
        all_dispatch = all(r.name in _INCONCLUSIVE_BY_NATURE for r in tool_records)
        if all_dispatch:
            return MissionOutcome(
                status=OutcomeStatus.TOOL_OK_VERIFIER_INCONCLUSIVE,
                summary="Tool despachada al SO (efecto asincrónico no medible).",
                unverified_count=unverified,
                expected_total=expected_total, expected_satisfied=satisfied,
                detail=detail,
            )
        return MissionOutcome(
            status=OutcomeStatus.UNVERIFIED,
            summary="Tool ejecutada (read-only o sin efecto medible).",
            unverified_count=unverified,
            expected_total=expected_total, expected_satisfied=satisfied,
            detail=detail,
        )

    # ---- Mixed (some confirmed, some failed/unverified) ----
    if confirmed > 0:
        return MissionOutcome(
            status=OutcomeStatus.PARTIAL,
            summary=mission_goal.summary(),
            confirmed_count=confirmed, failed_count=failed,
            unverified_count=unverified,
            expected_total=expected_total, expected_satisfied=satisfied,
            detail=detail,
        )

    # ---- Fallback ----
    return MissionOutcome(
        status=OutcomeStatus.UNVERIFIED,
        summary=mission_goal.summary(),
        confirmed_count=confirmed, failed_count=failed,
        unverified_count=unverified,
        expected_total=expected_total, expected_satisfied=satisfied,
        detail=detail,
    )


def mission_footer(outcome: MissionOutcome) -> str:
    """Footer corto al final del reply solo si el outcome aporta informacion.

    Reglas:
      - COMPLETED + 0 unverified -> sin footer (no inflar reply).
      - PARTIAL / FAILED / INTENT_NOT_FULFILLED -> footer con razon.
      - TOOL_OK_VERIFIER_INCONCLUSIVE -> footer explicito ("dispatch async").
      - UNVERIFIED + 0 expected -> sin footer.
    """
    if outcome.status == OutcomeStatus.COMPLETED and outcome.unverified_count == 0:
        return ""
    if outcome.status == OutcomeStatus.UNVERIFIED and outcome.expected_total == 0:
        return ""
    # Otherwise emit a one-line footer
    return f"\n\n[misión: {outcome.summary}]"


def build_tool_records(
    tool_events: list,
    verifier_outcomes: list[VerifierOutcome],
) -> list[_ToolCallRecord]:
    """Empareja eventos con sus verifier outcomes en orden.

    `tool_events` es la lista que mantiene agent.py (con name/args/result).
    `verifier_outcomes` se appendea en paralelo, asi que los indices alinean
    siempre que cada tool ejecutada se haya verifyado (TIER 1 #2 lo garantiza).
    Si las longitudes difieren, recortamos al min para no crashear.
    """
    records: list[_ToolCallRecord] = []
    n = min(len(tool_events), len(verifier_outcomes))
    for i in range(n):
        ev = tool_events[i]
        v = verifier_outcomes[i]
        # Robustez: tool_events trae dataclass ToolEvent o similar; usamos getattr.
        name = getattr(ev, "name", None) or str(ev)
        args = getattr(ev, "args", None) or getattr(ev, "arguments", None) or {}
        result = getattr(ev, "result", None) or {}
        ok = bool(result.get("ok", False)) if isinstance(result, dict) else False
        records.append(_ToolCallRecord(
            name=name,
            args=args if isinstance(args, dict) else {},
            ok=ok,
            verifier=v,
        ))
    # Si quedo cola de events sin verifier (no debería con TIER 1 #2):
    for j in range(n, len(tool_events)):
        ev = tool_events[j]
        name = getattr(ev, "name", None) or str(ev)
        args = getattr(ev, "args", None) or getattr(ev, "arguments", None) or {}
        result = getattr(ev, "result", None) or {}
        ok = bool(result.get("ok", False)) if isinstance(result, dict) else False
        records.append(_ToolCallRecord(
            name=name,
            args=args if isinstance(args, dict) else {},
            ok=ok,
            verifier=None,
        ))
    return records
