"""Subagent execution: delegate a task to a fresh Gemma 4 agent instance.

Inspired by Goose's SubagentExecutionTool. The parent agent picks a focused
task that's bounded enough to delegate (e.g. "search my Steam library for
games tagged metroidvania") and dispatches it to a child agent with:

  - its own AgentConfig (cloned from the parent, but with constrained
    max_agent_turns)
  - a fresh chat history (no inherited context)
  - optional `tools_filter`: a subset of tool names the child is allowed to
    see (the child's schemas_for_names is restricted, the registry still
    holds everything but the schemas surfaced to the LLM are filtered).
  - timeout enforced by max_turns + the underlying request_timeout.

The child returns the same shape as Gemma4Agent.run_text: AgentReply with
content, tool_events, mission. The parent surfaces it as a tool result.

We do NOT inherit the parent's experience memory recall, semantic router
cache, or persistent memory text. The child sees a clean SYSTEM_PROMPT plus
the explicit task. That's the whole point of delegation.

Concurrency: the implementation is synchronous. Parallel subagents (asyncio
or threads) are deferred until we have a use case for them.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any


def run_subagent(
    parent_agent: Any,
    task: str,
    *,
    tools_filter: list[str] | None = None,
    max_turns: int = 4,
    enable_thinking: bool | None = None,
) -> dict[str, Any]:
    """Spawn a child Gemma4Agent, run a single text turn, return a result dict."""
    if not task.strip():
        return {"ok": False, "error": "task is required"}
    if max_turns < 1 or max_turns > 10:
        return {"ok": False, "error": "max_turns must be between 1 and 10"}

    # Build a constrained child config from the parent's.
    parent_config = parent_agent.config
    child_kwargs: dict[str, Any] = {"max_agent_turns": int(max_turns)}
    if enable_thinking is not None:
        child_kwargs["enable_thinking"] = bool(enable_thinking)
    try:
        child_config = replace(parent_config, **child_kwargs)
    except TypeError as exc:
        return {"ok": False, "error": f"cannot build child config: {exc}"}

    # Lazy import to avoid circular at module load time.
    from ..agent_core.agent import Gemma4Agent

    child = Gemma4Agent(config=child_config)

    # tools_filter is realized by patching the child's tool registry method.
    if tools_filter:
        allowed = {str(name) for name in tools_filter if isinstance(name, str)}
        if not allowed:
            return {"ok": False, "error": "tools_filter is empty"}
        # Capture original to honor downstream behavior; replace with a
        # closure that intersects with the allowed set.
        original = child.tools.schemas_for_names

        def filtered_schemas(names: list[str]) -> list[dict[str, Any]]:
            limited = [n for n in names if n in allowed]
            return original(limited)

        child.tools.schemas_for_names = filtered_schemas  # type: ignore[method-assign]

    try:
        reply = child.run_text(task)
    except Exception as exc:
        return {"ok": False, "error": f"subagent run_text failed: {exc}", "task": task}
    finally:
        # Best-effort close of child experience store (its embeddings are
        # shared with the parent through the module-level cache anyway).
        try:
            child.experience.close()
        except Exception:
            pass

    return {
        "ok": True,
        "task": task,
        "content": reply.content,
        "tool_events": [
            {"name": e.name, "args": e.args, "ok": bool(e.result.get("ok"))}
            for e in reply.tool_events[:20]
        ],
        "tool_count": len(reply.tool_events),
        "mission": reply.mission,
        "max_turns": int(max_turns),
        "tools_filter": list(tools_filter or []),
    }
