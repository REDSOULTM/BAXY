"""Form Filler domain tool — extracted from domain_tools.py.

Llenado de formularios HTML con review-gate antes de submit. Sobre una sesión
browser_real existente (pass session_id):
  - discover: escanea fields + submits via document.querySelectorAll + JS
  - plan: matchea values {label: value} contra fields
  - apply: ejecuta el plan via browser_real.fill / click
  - submit: requiere confirmed=true; sin él devuelve screenshot + confirmation

Funciones extraídas (6):
  form_filler_tool                  (entry, 5 acciones)
  _form_discover                    (JS para extraer labels/selectors/values)
  _form_plan                        (match dict-values -> selectors)
  _form_match_field                 (exact -> substring sobre label/name/id/placeholder)
  _form_apply                       (checkbox/radio/select/text)
  _form_submit                      (con review-gate via screenshot + confirmation)

Auto-contenido (json, AgentState; ningún helper de domain_tools)."""
from __future__ import annotations

import json
from typing import Any, Callable

from .._shared import _err, _ok
from ..memory_pkg.state import AgentState


Executor = Callable[[str, dict[str, Any]], dict[str, Any]]


__all__ = [
    "form_filler_tool",
    "_form_discover",
    "_form_plan",
    "_form_match_field",
    "_form_apply",
    "_form_submit",
]


def form_filler_tool(args: dict[str, Any], state: AgentState, executor: Executor) -> dict[str, Any]:
    """Compound tool to fill HTML forms with a review gate before submit.

    Actions: status, discover, plan, apply, submit. Works on top of an
    existing browser_real session (pass session_id). discover scans the
    current page for form fields and their labels. plan matches a values
    dict (field_label -> value) against discovered fields without writing.
    apply executes the plan via browser_real.fill / click. submit clicks
    the submit button only when confirmed=true; otherwise it returns
    needs_confirmation with a screenshot for the user to verify.
    """
    action = str(args.get("action") or "status").casefold()
    if action == "status":
        return _ok(
            note="Requires an existing browser_real session (use browser_real.open or attach_visible first).",
            backend="browser_real_orchestration",
            review_gate_default=True,
        )
    session_id = str(args.get("session_id") or "default")
    if action == "discover":
        return _form_discover(session_id, executor)
    if action == "plan":
        return _form_plan(session_id, args, executor)
    if action == "apply":
        return _form_apply(session_id, args, executor)
    if action == "submit":
        return _form_submit(session_id, args, executor, state)
    return _err(
        "unknown form_filler action", action=action,
        valid_actions=[
            "status", "discover", "fill", "submit", "verify",
        ],
        status="needs_user",
    )


def _form_discover(session_id: str, executor: Executor) -> dict[str, Any]:
    script = r"""
() => {
  function bestLabel(el) {
    if (el.id) {
      const lbl = document.querySelector(`label[for="${el.id}"]`);
      if (lbl) return lbl.innerText.trim();
    }
    const parentLbl = el.closest('label');
    if (parentLbl) return parentLbl.innerText.trim();
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim();
    const placeholder = el.getAttribute('placeholder');
    if (placeholder) return placeholder.trim();
    return '';
  }
  function cssPath(el) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.name) return `${el.tagName.toLowerCase()}[name="${el.name}"]`;
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 6) {
      let part = node.tagName.toLowerCase();
      if (node.className && typeof node.className === 'string') {
        const cls = node.className.trim().split(/\s+/).slice(0, 2).join('.');
        if (cls) part += '.' + cls;
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(' > ');
  }
  const fields = [];
  const inputs = document.querySelectorAll('input, select, textarea');
  for (const el of inputs) {
    if (el.type === 'hidden') continue;
    fields.push({
      selector: cssPath(el),
      tag: el.tagName.toLowerCase(),
      type: el.type || el.tagName.toLowerCase(),
      name: el.name || '',
      id: el.id || '',
      label: bestLabel(el),
      placeholder: el.getAttribute('placeholder') || '',
      required: el.required || false,
      value: (el.type === 'password') ? '<hidden>' : (el.value || ''),
    });
  }
  const submits = [];
  document.querySelectorAll('button[type="submit"], input[type="submit"], button:not([type])').forEach(b => {
    submits.push({ selector: cssPath(b), text: (b.innerText || b.value || '').trim() });
  });
  return { fields, submits };
}
"""
    result = executor("browser_real", {"action": "evaluate", "session_id": session_id, "script": script})
    if not result.get("ok"):
        return result
    value = result.get("value") or {}
    return _ok(
        session_id=session_id,
        fields=value.get("fields") or [],
        field_count=len(value.get("fields") or []),
        submits=value.get("submits") or [],
        url=result.get("url"),
        title=result.get("title"),
    )


def _form_plan(session_id: str, args: dict[str, Any], executor: Executor) -> dict[str, Any]:
    values = args.get("values") if isinstance(args.get("values"), dict) else {}
    if not values:
        return _err("plan requires values={'field label or name': value}")
    discover = _form_discover(session_id, executor)
    if not discover.get("ok"):
        return discover
    fields = discover.get("fields", [])
    plan: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for key, val in values.items():
        match = _form_match_field(key, fields)
        if not match:
            unmatched.append(str(key))
            continue
        plan.append({"selector": match["selector"], "label": match.get("label") or match.get("name") or match.get("placeholder"), "tag": match["tag"], "type": match["type"], "value": val})
    return _ok(
        session_id=session_id,
        plan=plan, plan_size=len(plan),
        unmatched=unmatched, unmatched_count=len(unmatched),
        submits=discover.get("submits", []),
        url=discover.get("url"), title=discover.get("title"),
    )


def _form_match_field(query: str, fields: list[dict[str, Any]]) -> dict[str, Any] | None:
    q = query.casefold().strip()
    if not q:
        return None
    # 1. Exact match on label / name / id / placeholder.
    for f in fields:
        for key in ("label", "name", "id", "placeholder"):
            if str(f.get(key) or "").casefold() == q:
                return f
    # 2. Substring.
    for f in fields:
        for key in ("label", "name", "id", "placeholder"):
            if q in str(f.get(key) or "").casefold():
                return f
    return None


def _form_apply(session_id: str, args: dict[str, Any], executor: Executor) -> dict[str, Any]:
    plan = args.get("plan") if isinstance(args.get("plan"), list) else None
    if plan is None:
        # If only values were passed, build the plan first.
        if args.get("values"):
            built = _form_plan(session_id, args, executor)
            if not built.get("ok"):
                return built
            plan = built.get("plan", [])
        else:
            return _err("apply requires plan (list) or values (dict)")
    if not plan:
        return _err("plan is empty; nothing to apply")
    applied: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for step in plan:
        selector = str(step.get("selector") or "").strip()
        value = step.get("value")
        tag = str(step.get("type") or step.get("tag") or "").casefold()
        if not selector:
            failed.append({"step": step, "error": "missing selector"})
            continue
        if tag in {"checkbox", "radio"}:
            should_check = bool(value)
            current = executor("browser_real", {"action": "evaluate", "session_id": session_id, "script": f"() => {{ const el = document.querySelector({json.dumps(selector)}); return el ? el.checked : null; }}"})
            if current.get("ok") and bool(current.get("value")) != should_check:
                result = executor("browser_real", {"action": "click", "session_id": session_id, "selector": selector})
            else:
                result = {"ok": True, "noop": True}
        elif tag == "select" or step.get("tag") == "select":
            # For <select>, use JS to set the value option.
            script = f"""() => {{ const el = document.querySelector({json.dumps(selector)}); if (!el) return false; el.value = {json.dumps(str(value))}; el.dispatchEvent(new Event('change', {{bubbles: true}})); return true; }}"""
            result = executor("browser_real", {"action": "evaluate", "session_id": session_id, "script": script})
        else:
            result = executor("browser_real", {"action": "fill", "session_id": session_id, "selector": selector, "value": str(value)})
        (applied if result.get("ok") else failed).append({"step": step, "result": {"ok": result.get("ok"), "error": result.get("error")}})
    return _ok(
        session_id=session_id,
        applied=len(applied), failed=len(failed),
        applied_details=applied, failed_details=failed,
        verified=not failed,
    )


def _form_submit(session_id: str, args: dict[str, Any], executor: Executor, state: AgentState) -> dict[str, Any]:
    confirmed = bool(args.get("confirmed", False))
    selector = str(args.get("selector") or "").strip()
    if not confirmed:
        # Capture a screenshot + summary so the user can verify before submit.
        screenshot = executor("browser_real", {"action": "screenshot", "session_id": session_id})
        discover = _form_discover(session_id, executor)
        pending = state.create_confirmation(
            "form_filler",
            {"action": "submit", "session_id": session_id, "selector": selector, "confirmed": True},
            reason="Submitting a form to the live website. Verify the values are correct.",
            risk="medium",
        )
        return _err(
            "form submission requires confirmation; review the screenshot then call safety(confirm,...) or re-call submit with confirmed=true",
            status="needs_confirmation", verified=False,
            completion_status="needs_user_confirmation",
            screenshot=screenshot.get("image_path"),
            current_fields=[{"label": f.get("label") or f.get("name"), "value": f.get("value")} for f in discover.get("fields", [])],
            url=screenshot.get("url"),
            confirmation=pending.get("confirmation"),
        )
    if selector:
        result = executor("browser_real", {"action": "click", "session_id": session_id, "selector": selector})
    else:
        # Try to find a submit button automatically.
        discover = _form_discover(session_id, executor)
        submits = discover.get("submits", [])
        if not submits:
            return _err("no submit button found; pass selector explicitly")
        result = executor("browser_real", {"action": "click", "session_id": session_id, "selector": submits[0]["selector"]})
    return _ok(session_id=session_id, submit_result=result, verified=result.get("ok"))
