"""Dataclasses para las 3 fases de Gemma4Agent.run_content (R1 sprint
2026-05-28).

run_content históricamente era una función de 2193 LOC que mezclaba 3
responsabilidades:
  - decidir qué tools ofrecer (router + abstain + planner + subset +
    pending_intent + splitter + multi-intent carry);
  - ejecutar el LLM y dispatchear tool calls (con retries, fallback nets);
  - finalizar (verifiers + accessibility nudges + reply formateado).

R1 parte el método en `_decide_turn` → `_execute_turn` (con `_finalize_turn`
llamado al final de execute). `TurnDecision` y `ExecutionResult` son los
contratos de paso entre fases; el `early_reply` modela los caminos cortos
que omiten las fases siguientes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent import AgentReply, ToolEvent
    from .modes import AgentMode


@dataclass
class TurnDecision:
    """Resultado de Gemma4Agent._decide_turn.

    early_reply: si está seteado, run_content lo devuelve y NO ejecuta
    _execute_turn. Casos: jarvis-pending handshake, multi-intent re-dispatch,
    a11y short-circuit, phrase-only routine fire.

    Si early_reply es None, los demás campos son el estado decidido para
    el LLM call. Todos OPTIONAL para que el camino early-return solo tenga
    que setear early_reply.
    """
    early_reply: "AgentReply | None" = None
    turn_id: str = ""
    mode: "AgentMode | None" = None
    plan: dict[str, Any] | None = None
    raw_text_early: str = ""
    pending_intent: dict[str, Any] | None = None
    selected_tool_names: list[str] = field(default_factory=list)
    semantic_fallback: bool = False
    selected_schemas: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Resultado de Gemma4Agent._execute_turn.

    El execute lo hace TODO: LLM loop iterativo, tool dispatch, retries,
    fallback nets, Y el cierre del turno (max_turns, loop_aborted, success).
    Por eso ExecutionResult contiene SIEMPRE un AgentReply terminal — el
    early_reply solo distingue caminos de error (chat exception) vs los
    caminos normales (assistant terminó sin tool call, max_turns, loop).

    R1.2 deja toda la lógica del finalize dentro de _execute_turn; R1.3 la
    extrae a _finalize_turn como sub-fase llamada al final del execute.
    """
    reply: "AgentReply" = None  # type: ignore[assignment]
