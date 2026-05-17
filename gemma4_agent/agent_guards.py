"""Post-reply guards extracted from :mod:`gemma4_agent.agent`.

The six ``_guard_*`` methods that run after Gemma 4's reply (and the
``_build_user_facing_fallback`` helper they share) all read a small
subset of Gemma4Agent state: the trace logger, ``_phrase_fires``,
``_current_user_text``, ``_last_fallback_user_text``,
``_fallback_streak``, ``_last_router_subset``, ``_explicit_plan_status``.

This module exposes each guard as a pure function that takes those
fields explicitly. The methods on ``Gemma4Agent`` are now 5-line
wrappers that pull the fields off ``self`` and write back the
mutated streak / last-text. That keeps the agent's external API
identical while letting the guard logic live in one file.

No behavior change vs the inline implementations they replace.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import ToolEvent  # noqa: F401  (only used in annotations)
    from .tracing import TraceLogger  # noqa: F401


def _fold_match(text: str) -> str:
    """Lowercase + drop combining marks for substring matching."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


# ---------------------------------------------------------------------------
# Shared fallback builder
# ---------------------------------------------------------------------------

def build_user_facing_fallback(
    *,
    reason: str,
    rejected_reply: str,
    trace_label: str,
    missing: str = "",
    current_user_text: str = "",
    last_fallback_user_text: str = "",
    fallback_streak: int = 0,
    last_router_subset: list[str] | tuple[str, ...] = (),
    trace: Any | None = None,
) -> tuple[str, int, str]:
    """Pick a fallback string in the user's language with streak-aware retry hints.

    Returns ``(text, new_streak, new_last_fallback_user_text)`` so the
    caller can persist the updated streak/last-text on its own state.

    On the 2nd consecutive call with the same ``current_user_text``, the
    reason is upgraded to ``"retry"`` and up to 3 hints are pulled from
    ``last_router_subset`` (skipping the always-present ``"session"``
    entry).
    """
    from .grounding_gate import detect_reply_language, format_fallback

    lang_hint = detect_reply_language(rejected_reply)
    current = current_user_text or ""
    if last_fallback_user_text and last_fallback_user_text == current and current:
        new_streak = fallback_streak + 1
    else:
        new_streak = 1

    effective_reason = reason
    hints = ""
    if new_streak >= 2:
        effective_reason = "retry"
        subset = list(last_router_subset) if last_router_subset else []
        top = [n for n in subset if n != "session"][:3]
        hints = ", ".join(top) if top else ""

    out = format_fallback(
        reason=effective_reason,
        reply_lang_hint=lang_hint,
        rejected_reply=rejected_reply,
        missing=missing,
        hints=hints,
    )

    if trace is not None:
        try:
            trace.event(
                trace.new_turn_id(), "fallback_emitted",
                label=trace_label, reason=effective_reason,
                streak=new_streak, lang=lang_hint,
            )
        except Exception:
            pass

    return out, new_streak, current


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def guard_unverified_final(content: str, events: list[Any]) -> str:
    """See :meth:`gemma4_agent.agent.Gemma4Agent._guard_unverified_final`."""
    if not events:
        return content
    last = events[-1].result
    status = str(last.get("status") or "")
    verified = last.get("verified")

    if verified is True:
        return content
    if status == "dispatched":
        return content
    if status in {"needs_user", "needs_dependency", "needs_permission",
                  "needs_confirmation", "needs_verification_async"}:
        return content
    if verified is None and status not in {"attempted", "needs_verification", "failed"}:
        return content
    if verified is not False and status not in {"attempted", "needs_verification", "failed"}:
        return content

    completion = str(last.get("completion_status") or "").casefold()
    from .tools import _DISPATCH_OK_COMPLETIONS
    if completion in _DISPATCH_OK_COMPLETIONS:
        return content

    if last.get("opened") is True and (last.get("url") or last.get("deeplink") or last.get("uri")):
        return content

    if status == "failed" and not last.get("ok"):
        return content

    low = content.casefold()
    already_honest = any(
        token in low
        for token in ("intent", "verifi", "no pude", "no se pudo", "error", "fall")
    )
    if already_honest:
        return content
    evidence = last.get("evidence") or last.get("completion_status") or status or "sin evidencia"
    note = (
        "\n\nNota: la ultima tool no dejo evidencia suficiente de finalizacion "
        f"(status={status or 'desconocido'}, verified={verified}, evidence={evidence})."
    )
    return content.rstrip() + note


def guard_phrase_confirm(
    content: str,
    *,
    phrase_fires: list[dict[str, Any]],
    trace: Any | None = None,
) -> str:
    """See :meth:`gemma4_agent.agent.Gemma4Agent._guard_phrase_confirm`."""
    if not phrase_fires:
        return content
    folded = _fold_match(content)
    ack_tokens = ("hecho", "listo", "done", "ejecut", "completed", "fini", " ya ")
    already_ack = any(tok in folded for tok in ack_tokens)
    mentions_any = False
    for fire in phrase_fires:
        label = _fold_match(str(fire.get("label") or ""))
        phrase = _fold_match(str(fire.get("phrase") or ""))
        if (label and label in folded) or (phrase and phrase in folded):
            mentions_any = True
            break
    if already_ack or mentions_any:
        return content
    summaries: list[str] = []
    for fire in phrase_fires:
        label = fire.get("label") or "rutina"
        results = fire.get("results") or []
        ok = sum(1 for r in results if r.get("ok"))
        total = len(results)
        timed_out = sum(1 for r in results if r.get("timed_out"))
        suffix = ""
        if timed_out:
            suffix = f" ({timed_out} con timeout)"
        elif ok < total:
            suffix = f" ({total - ok} con error)"
        summaries.append(f"{label} {ok}/{total} pasos{suffix}")
    prefix = "Ejecute tu rutina: " + "; ".join(summaries) + ".\n\n"
    if trace is not None:
        try:
            trace.event(trace.new_turn_id(), "phrase_confirm_injected",
                         fires=len(phrase_fires))
        except Exception:
            pass
    return prefix + content


def guard_promise_without_action(
    content: str,
    events: list[Any],
    *,
    phrase_fires: list[dict[str, Any]] | None,
    trace: Any | None,
    current_user_text: str = "",
    last_fallback_user_text: str = "",
    fallback_streak: int = 0,
    last_router_subset: list[str] | tuple[str, ...] = (),
) -> tuple[str, int, str]:
    """See :meth:`gemma4_agent.agent.Gemma4Agent._guard_promise_without_action`.

    Returns ``(content, new_streak, new_last_fallback_text)`` so the
    caller can persist the streak update.
    """
    if events:
        return content, fallback_streak, last_fallback_user_text
    if not content:
        return content, fallback_streak, last_fallback_user_text
    if phrase_fires:
        return content, fallback_streak, last_fallback_user_text

    low = content.lower()
    false_confirmation_patterns = (
        "hecho:", "hecho,", "listo,", "listo:",
        "ejecuté", "ejecute", "registré", "registre",
        "agendé", "agende", "envié", "envie", "mandé", "mande",
    )
    stripped_low = low.lstrip()
    confirm_match = next(
        (p for p in false_confirmation_patterns if stripped_low.startswith(p)),
        None,
    )
    if confirm_match:
        if trace is not None:
            try:
                trace.event(
                    trace.new_turn_id(), "false_confirmation_caught",
                    phrase=confirm_match, original=content[:160],
                )
            except Exception:
                pass
        replacement, new_streak, new_last = build_user_facing_fallback(
            reason="generic",
            rejected_reply=content,
            trace_label="false_confirmation_caught",
            current_user_text=current_user_text,
            last_fallback_user_text=last_fallback_user_text,
            fallback_streak=fallback_streak,
            last_router_subset=last_router_subset,
            trace=trace,
        )
        return replacement, new_streak, new_last

    promise_patterns = (
        "buscare", "buscaré", "voy a buscar", "voy a investigar",
        "voy a consultar", "voy a revisar", "voy a chequear",
        "te proporcionare", "te proporcionaré", "te dire", "te diré",
        "te respondere", "te responderé", "te informare", "te informaré",
        "te traere", "te traeré", "te dare", "te daré la informacion",
        "permiteme buscar", "permíteme buscar",
        "dame un momento", "un momento por favor",
        "te aviso", "te confirmo", "te paso", "te mando", "te muestro",
        "lo reviso", "lo verifico", "déjame ver", "dejame ver",
        "ahora te traigo", "ya te digo", "te explico", "ya mismo",
        "i'll search", "i'll look", "let me search", "let me check",
        "i will find", "i'll find", "i'll get",
    )
    matched = next((p for p in promise_patterns if p in low), None)
    if not matched:
        return content, fallback_streak, last_fallback_user_text

    if trace is not None:
        try:
            trace.event(
                trace.new_turn_id(), "promise_without_action_caught",
                phrase=matched, original=content[:160],
            )
        except Exception:
            pass
    replacement, new_streak, new_last = build_user_facing_fallback(
        reason="retry",
        rejected_reply=content,
        trace_label="promise_without_action_replacement",
        current_user_text=current_user_text,
        last_fallback_user_text=last_fallback_user_text,
        fallback_streak=fallback_streak,
        last_router_subset=last_router_subset,
        trace=trace,
    )
    if len(content.strip()) <= 100:
        return replacement, new_streak, new_last
    sentences = re.split(r"(?<=[.!?])\s+", content)
    kept = [s for s in sentences if matched not in s.lower()]
    stripped_content = " ".join(kept).strip()
    if len(stripped_content) < 20:
        return replacement, new_streak, new_last
    return stripped_content, new_streak, new_last


def guard_grounded_action_claim(
    content: str,
    events: list[Any],
    turn_id: str,
    *,
    phrase_fires: list[dict[str, Any]] | None,
    trace: Any | None,
    current_user_text: str = "",
    last_fallback_user_text: str = "",
    fallback_streak: int = 0,
    last_router_subset: list[str] | tuple[str, ...] = (),
) -> tuple[str, int, str]:
    """See :meth:`gemma4_agent.agent.Gemma4Agent._guard_grounded_action_claim`.

    Returns ``(content, new_streak, new_last_fallback_text)``.
    """
    if not content:
        return content, fallback_streak, last_fallback_user_text
    if phrase_fires:
        return content, fallback_streak, last_fallback_user_text
    from .grounding_gate import detect_action_claim_without_evidence

    verdict = detect_action_claim_without_evidence(content, events)
    if not verdict.should_replace:
        return content, fallback_streak, last_fallback_user_text
    if trace is not None:
        try:
            trace.event(
                turn_id, "grounded_action_claim_caught",
                claim_word=verdict.claim_word,
                reason=verdict.reason,
                original=content[:160],
            )
        except Exception:
            pass
    new_content, new_streak, new_last = build_user_facing_fallback(
        reason="generic",
        rejected_reply=content,
        trace_label="grounded_action_claim_caught",
        current_user_text=current_user_text,
        last_fallback_user_text=last_fallback_user_text,
        fallback_streak=fallback_streak,
        last_router_subset=last_router_subset,
        trace=trace,
    )
    return new_content, new_streak, new_last


def guard_plan_status(
    content: str,
    *,
    explicit_plan_status: dict[str, Any] | None,
    trace: Any | None = None,
) -> str:
    """See :meth:`gemma4_agent.agent.Gemma4Agent._guard_plan_status`."""
    status = explicit_plan_status or {}
    state = str(status.get("state") or "")
    if state not in {"failed", "error"}:
        return content
    if len(content.strip()) >= 30:
        return content
    err = str(status.get("error") or "unknown error")
    note = f"\n\nNota: intente generar un plan explicito para tu pedido pero fallo ({err[:120]}). Si quieres, repiteme la peticion o pasame el detalle paso a paso."
    if trace is not None:
        try:
            trace.event(trace.new_turn_id(), "plan_status_surfaced", state=state)
        except Exception:
            pass
    return content.rstrip() + note


__all__ = [
    "build_user_facing_fallback",
    "guard_unverified_final",
    "guard_phrase_confirm",
    "guard_promise_without_action",
    "guard_grounded_action_claim",
    "guard_plan_status",
]
