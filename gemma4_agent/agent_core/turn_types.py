"""Dataclasses para las fases de Gemma4Agent.run_content.

run_content está partido en 3 fases, cada una con una sola responsabilidad:
  - decidir qué tools ofrecer (router + abstain + planner + subset +
    pending_intent + splitter + multi-intent carry);
  - ejecutar el LLM y dispatchear tool calls (con retries, fallback nets);
  - finalizar (verifiers + accessibility nudges + reply formateado).

El método se divide en `_decide_turn` → `_execute_turn` (con `_finalize_turn`
llamado al final de execute). `TurnDecision` es el contrato de paso de
decide → execute; el `early_reply` modela los caminos cortos que omiten
las fases siguientes.

Nota: no existe un dataclass `ExecutionResult` envoltorio porque no hace
falta: `_execute_turn` devuelve `AgentReply` directo (el resultado terminal
del turno), sin envoltorio. Si en el futuro se necesita pasar estado entre
execute y finalize, se puede añadir acá.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

# NO importamos `.agent` — eso crearía el ciclo agent → turn_types → agent
# en el analizador estático. Los type hints a AgentReply/AgentMode son
# STRINGS (forward refs) para que Python no evalúe el nombre en runtime y el
# analizador no vea la dependencia. Si agregás un campo que necesite
# AgentReply en runtime (constructor, isinstance check), mové AgentReply
# acá en vez de importarlo.
if TYPE_CHECKING:
    from ..support.modes import AgentMode  # solo modes — no agent
    from .agent import AgentReply  # solo type-check; no corre en runtime (sin ciclo)


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


