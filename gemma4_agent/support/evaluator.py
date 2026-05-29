"""Mission status evaluator for tool-using turns."""

from __future__ import annotations

from typing import Any


MISSION_STATES = {"PASS", "PARTIAL", "FAILED", "UNVERIFIED", "NEEDS_USER"}


def evaluate_mission(events: list[Any], final_content: str = "", plan: Any | None = None) -> dict[str, Any]:
    expected_steps = _plan_steps(plan)
    if not events:
        if _looks_like_user_needed(final_content):
            return {"mission_status": "NEEDS_USER", "reason": "assistant requested missing context"}
        if expected_steps:
            return {"mission_status": "FAILED", "reason": "mission expected tool actions but no tool ran", "expected_steps": len(expected_steps)}
        return {"mission_status": "PASS", "reason": "no tool action required"}

    results = [event.result if hasattr(event, "result") else event.get("result", {}) for event in events]
    any_ok = any(bool(result.get("ok")) for result in results)
    any_failed = any(not bool(result.get("ok")) or result.get("status") == "failed" for result in results)
    any_needs_user = any(
        result.get("status") == "needs_user"
        or result.get("status") == "needs_confirmation"
        or result.get("completion_status") in {"needs_user", "needs_user_auth", "needs_dependency", "needs_confirmation"}
        for result in results
    )
    any_unverified = any(result.get("verified") is False or result.get("status") in {"attempted", "needs_verification"} for result in results)
    last = results[-1]
    tool_names = [event.name if hasattr(event, "name") else event.get("name") for event in events]
    covered_steps = _covered_steps(expected_steps, tool_names)

    if any_needs_user:
        return {"mission_status": "NEEDS_USER", "reason": "a tool needs user-provided auth/dependency/argument/confirmation", "last_status": last.get("status"), "covered_steps": covered_steps}
    if _looks_like_user_needed(final_content):
        return {"mission_status": "NEEDS_USER", "reason": "assistant requested user input", "last_status": last.get("status"), "covered_steps": covered_steps}
    if expected_steps and covered_steps["missing"]:
        state = "PARTIAL" if any_ok else "FAILED"
        return {
            "mission_status": state,
            "reason": "not all planned mission steps had matching tool evidence",
            "last_status": last.get("status"),
            "covered_steps": covered_steps,
        }
    if any_failed and not any_ok:
        return {"mission_status": "FAILED", "reason": "all tool actions failed", "last_status": last.get("status"), "covered_steps": covered_steps}
    if any_unverified:
        state = "PARTIAL" if any_ok else "UNVERIFIED"
        return {"mission_status": state, "reason": "one or more tool results lack verification", "last_status": last.get("status"), "covered_steps": covered_steps}
    if any_failed:
        return {"mission_status": "PARTIAL", "reason": "some tool actions failed", "last_status": last.get("status"), "covered_steps": covered_steps}
    return {"mission_status": "PASS", "reason": "all tool results completed with verification", "last_status": last.get("status"), "covered_steps": covered_steps}


def _plan_steps(plan: Any | None) -> list[dict[str, Any]]:
    if plan is None:
        return []
    if hasattr(plan, "as_dict"):
        plan = plan.as_dict()
    if not isinstance(plan, dict):
        return []
    steps = plan.get("steps") or []
    return [step for step in steps if isinstance(step, dict) and step.get("suggested_tools")]


def _covered_steps(steps: list[dict[str, Any]], tool_names: list[str | None]) -> dict[str, Any]:
    covered: list[int] = []
    missing: list[int] = []
    names = {name for name in tool_names if name}
    for step in steps:
        index = int(step.get("index") or 0)
        suggested = set(step.get("suggested_tools") or [])
        if suggested & names:
            covered.append(index)
        else:
            missing.append(index)
    return {"covered": covered, "missing": missing, "tool_names": list(tool_names)}


def _looks_like_user_needed(text: str) -> bool:
    low = text.casefold()
    return any(
        token in low
        for token in (
            "necesito que me digas",
            "podrias especificar",
            "podrías especificar",
            "confirmame",
            "confírmame",
            "dime la ruta",
            "falta",
            "necesito una ruta",
            "necesito el destinatario",
        )
    )
