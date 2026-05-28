"""Dataclasses para las 3 fases de Gemma4Agent.run_content (R1 sprint
2026-05-28).

run_content históricamente era una función de 2193 LOC que mezclaba 3
responsabilidades:
  - decidir qué tools ofrecer (router + abstain + planner + subset +
    pending_intent + splitter + multi-intent carry);
  - ejecutar el LLM y dispatchear tool calls (con retries, fallback nets);
  - finalizar (verifiers + accessibility nudges + reply formateado).

R1 (esta sesión: solo F1) parte la fase decide a `_decide_turn` que devuelve
un `TurnDecision`. F2 (execute) y F3 (finalize) van en sesiones futuras.

`TurnDecision.early_reply` modela los caminos cortos del decide (jarvis
pending handshake, multi-intent re-entry, phrase-only routine fire, etc):
si está seteado, run_content lo devuelve sin ejecutar las fases siguientes.

Si `early_reply` es None, los demás campos son las locales del decide que
el execute consume. Identificadas por AST: SOLO 10 variables cruzan la
frontera decide→execute en el código original (turn_id, mode, plan,
raw_text_early, raw_text, pending_intent, selected_tool_names,
semantic_fallback, selected_schemas, _rc).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent import AgentReply
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
