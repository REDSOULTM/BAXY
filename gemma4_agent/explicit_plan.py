"""Explicit Planner -> Executor pattern (Goose-style) on top of Gemma 4.

The deterministic planner in planner.py only emits a regex-based draft. This
module asks Gemma 4 itself to produce a concrete numbered plan before the
tool-calling loop starts. The plan is injected into the system prompt as a
mission contract; the executor follows it step by step. If 2+ steps fail or
the executor stalls, we ask Gemma to revise the plan in light of the failure.

Disable with GEMMA4_AGENT_EXPLICIT_PLAN=false.

Design notes:
- We do NOT use it for casual / single-step requests. Heuristic: only invoke
  for requests with >=2 sequencing markers or >=3 actions, or when the
  deterministic planner found >=2 steps. This keeps cost bounded.
- The plan is plain text, max 8 numbered steps. Each step is one short
  imperative line. We do not force a JSON schema because Gemma 4 with no
  tools follows prose much more reliably.
- We do NOT enforce 1 LLM call == 1 step. The executor reuses the existing
  tool-calling loop; the plan is a HINT, not a script. This matches Goose's
  Planner -> Executor pattern.
"""
from __future__ import annotations

import os
from typing import Any, Callable

PlanFn = Callable[[list[dict[str, Any]]], dict[str, Any]]


def is_enabled() -> bool:
    raw = (os.environ.get("GEMMA4_AGENT_EXPLICIT_PLAN") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def should_plan(user_text: str, deterministic_steps: int) -> bool:
    """Decide whether to spend an LLM call on explicit planning.

    Cheap heuristic: trigger when the deterministic planner already split into
    2+ steps, OR the user wrote >=3 imperative verbs, OR the request mentions
    'plan'/'planea'/'plan it' explicitly.
    """
    if not is_enabled():
        return False
    if deterministic_steps >= 2:
        return True
    low = user_text.casefold()
    if any(token in low for token in ("plan it", "haz un plan", "planea", "step by step", "paso a paso")):
        return True
    # Count imperative verbs (rough ES+EN, single-word match).
    verbs = ("abre", "abrir", "open", "cierra", "close", "busca", "search", "pon", "play",
             "lee", "read", "escribe", "write", "crea", "create", "instala", "install",
             "mueve", "move", "copia", "copy", "borra", "delete", "manda", "send",
             "verifica", "verify", "descarga", "download")
    hits = sum(1 for v in verbs if f" {v} " in f" {low} ")
    return hits >= 3


def generate_plan(user_text: str, chat_fn: PlanFn, *, max_tokens: int = 350) -> dict[str, Any]:
    """Ask Gemma to produce a numbered plan for the request.

    Returns {"plan": str, "steps": [str, ...], "ok": bool, "error": str|None}.
    """
    prompt = (
        "Eres un planificador. Lee el pedido del usuario y devuelve un plan "
        "numerado de maximo 8 pasos para cumplirlo. Cada paso debe ser una "
        "linea corta en imperativo, mencionando que tool aproximada se usara "
        "y que evidencia verificara que se cumplio. No ejecutes nada, solo "
        "planifica. Si el pedido es trivial (saludo, conocimiento general, "
        "una sola accion clara), responde literalmente 'NO_PLAN_NEEDED'.\n\n"
        f"Pedido del usuario:\n{user_text.strip()[:2000]}\n\nPLAN:"
    )
    try:
        resp = chat_fn([{"role": "user", "content": prompt}])
    except Exception as exc:
        return {"ok": False, "plan": "", "steps": [], "error": f"chat_failed: {exc}"}
    if not isinstance(resp, dict):
        return {"ok": False, "plan": "", "steps": [], "error": "invalid_response_shape"}
    choices = resp.get("choices") or []
    if not choices:
        return {"ok": False, "plan": "", "steps": [], "error": "no_choices"}
    msg = choices[0].get("message") or {}
    raw = str(msg.get("content") or "").strip()
    from .reasoning import sanitize_text
    plan = sanitize_text(raw)
    if not plan or plan.upper().startswith("NO_PLAN_NEEDED"):
        return {"ok": True, "plan": "", "steps": [], "skipped": True}
    steps = _parse_numbered_steps(plan)
    return {"ok": True, "plan": plan, "steps": steps}


def replan(user_text: str, original_plan: str, failures: list[dict[str, Any]], chat_fn: PlanFn, *, max_tokens: int = 350) -> dict[str, Any]:
    """Ask Gemma to revise the plan after step failures."""
    failure_block = "\n".join(
        f"- step={f.get('step', '?')} tool={f.get('tool', '?')} error={str(f.get('error', ''))[:200]}"
        for f in failures[-4:]
    ) or "(none recorded)"
    prompt = (
        "El plan original fallo. Lee el pedido del usuario, el plan original y "
        "las ultimas fallas. Devuelve un plan revisado de maximo 6 pasos, "
        "evitando los enfoques que ya fallaron. Si el pedido ya no es alcanzable, "
        "responde literalmente 'GIVE_UP: <razon corta>'.\n\n"
        f"Pedido del usuario:\n{user_text.strip()[:1500]}\n\n"
        f"Plan original:\n{original_plan.strip()[:1500]}\n\n"
        f"Fallas recientes:\n{failure_block}\n\nPLAN REVISADO:"
    )
    try:
        resp = chat_fn([{"role": "user", "content": prompt}])
    except Exception as exc:
        return {"ok": False, "plan": "", "steps": [], "error": f"chat_failed: {exc}"}
    if not isinstance(resp, dict):
        return {"ok": False, "plan": "", "steps": [], "error": "invalid_response_shape"}
    choices = resp.get("choices") or []
    if not choices:
        return {"ok": False, "plan": "", "steps": [], "error": "no_choices"}
    msg = choices[0].get("message") or {}
    raw = str(msg.get("content") or "").strip()
    from .reasoning import sanitize_text
    plan = sanitize_text(raw)
    if plan.upper().startswith("GIVE_UP"):
        return {"ok": True, "plan": plan, "steps": [], "give_up": True}
    steps = _parse_numbered_steps(plan)
    return {"ok": True, "plan": plan, "steps": steps}


def _parse_numbered_steps(text: str) -> list[str]:
    """Pull out the numbered lines from a free-form plan reply."""
    import re
    steps: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"^\s*(?:\(?(\d{1,2})\)?[\.\)\-]\s+|[*\-]\s+)(.+)$", line)
        if match:
            steps.append(match.group(2).strip())
        if len(steps) >= 8:
            break
    return steps


def format_for_prompt(plan_text: str) -> str:
    """Render an explicit plan as a system-prompt hint block."""
    if not plan_text.strip():
        return ""
    return (
        "# Explicit Plan (follow these steps in order)\n"
        f"{plan_text.strip()}\n"
        "Treat the plan as a contract. If a step blocks, attempt a verify "
        "and then continue or report it honestly. Do not skip ahead silently."
    )
