"""Post-reply guards extracted from :mod:`gemma4_agent.agent`.

The six ``_guard_*`` methods that run after Gemma 4's reply (and the
``_build_user_facing_fallback`` helper they share) all read a small
subset of Gemma4Agent state: the trace logger, ``_phrase_fires``,
``_current_user_text``, ``_last_fallback_user_text``,
``_fallback_streak``, ``_last_router_subset``, ``_explicit_plan_status``.

This module exposes each guard as a pure function that takes those
fields explicitly. The methods on ``Gemma4Agent`` are thin wrappers
that pull the fields off ``self`` and write back the mutated streak /
last-text. That keeps the agent's external API identical while letting
the guard logic live in one file.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    # NO importar `ToolEvent` desde `.agent`: este módulo no lo usa y ese
    # import crea el ciclo agent ↔ agent_guards.
    from ..infra.tracing import TraceLogger  # noqa: F401


def _fold_match(text: str) -> str:
    """Lowercase + drop combining marks for substring matching."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


# Reply phrases that signal the model CLAIMED or PROMISED an action it did not
# actually call (false confirmation = past tense "ya lo hice"; promise = future
# tense "voy a hacerlo"). Lifted to module level so the forced-tool-retry guard
# in agent.py can reuse the SAME vocabulary as guard_promise_without_action —
# one source of truth. See reply_claims_action().
_FALSE_CONFIRMATION_PATTERNS = (
    "hecho:", "hecho,", "listo,", "listo:",
    "ejecuté", "ejecute", "registré", "registre",
    "agendé", "agende", "envié", "envie", "mandé", "mande",
)
_PROMISE_PATTERNS = (
    "buscare", "buscaré", "voy a buscar", "voy a investigar",
    "buscando informacion", "buscando información",
    "estoy buscando", "estoy investigando",
    "intentando buscar", "intentando investigar",
    "voy a consultar", "voy a revisar", "voy a chequear",
    "te proporcionare", "te proporcionaré", "te dire", "te diré",
    "te respondere", "te responderé", "te informare", "te informaré",
    "te traere", "te traeré", "te dare", "te daré la informacion",
    "permiteme buscar", "permíteme buscar",
    "dame un momento", "un momento por favor",
    "te aviso", "te confirmo", "te paso", "te mando", "te muestro",
    "lo reviso", "lo verifico", "déjame ver", "dejame ver",
    "ahora te traigo", "ya te digo", "te explico", "ya mismo",
    "i'll search", "i will search", "i'm searching", "i am searching",
    "i’m searching", "searching for",
    "i'll look", "i will look", "i'm looking", "i am looking",
    "i’m looking", "let me search", "let me check",
    "i will find", "i'll find", "i'll get",
)


def reply_claims_action(content: str) -> bool:
    """True if the prose reply claims/promises an action it didn't call.

    Used to decide whether a prose-without-tool-call turn is a genuine
    skipped action (claim/promise -> the forced retry is justified) or just
    chat/clarification/decline (no claim -> forcing a tool wastes an LLM
    pass). Mirrors the detection in guard_promise_without_action.
    """
    if not content:
        return False
    low = content.lower()
    stripped_low = low.lstrip()
    if any(stripped_low.startswith(p) for p in _FALSE_CONFIRMATION_PATTERNS):
        return True
    return any(p in low for p in _PROMISE_PATTERNS)


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
    from ..safety_pkg.grounding_gate import detect_reply_language, format_fallback

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
# Tri-estado honesto (compartido por guard_unverified_final / honest_action_reply)
# ---------------------------------------------------------------------------

# Las DOS redacciones de no-éxito que emite el guard. La distinción es honestidad
# tri-estado: si NO se pudo medir el efecto, el reply debe ser honesto ("lo hice,
# no pude confirmar el efecto") — NO "Hecho." a secas, NI afirmar que falló.
# summarize_verifiers (verify_core) ya respeta el tri-estado (confirmed=None ->
# silencio; confirmed=False -> "no confirmada"); acá lo alineamos para el camino
# del guard, que de lo contrario colapsaría None y False al MISMO note "no dejó
# evidencia suficiente" (sonaría a fallo para un caso no-medible).
_NOTE_MEASURED_FAIL = (
    "\n\nNota: la ultima tool no dejo evidencia suficiente de finalizacion "
    "(status={status}, verified={verified}, evidence={evidence})."
)
_NOTE_UNMEASURED = (
    "\n\nNota: lo intente, pero no pude confirmar el efecto de la accion "
    "(no fue medible)."
)


def _has_measured_failure(last: dict[str, Any]) -> bool:
    """True si la acción se MIDIÓ y NO cambió/falló (señal de fallo DURA).

    Estructural (mide la FORMA del result, no frases por idioma). El tri-estado
    REAL vive en ``last["steps"][*]["verified"]`` y ``["state_changed"]`` (lo
    preserva PlanExecutor; nace en gui_verify.verify_after). El top-level colapsa
    None->False (PlanExecutor.execute / t_computer_use), por eso NO alcanza con
    leer ``last["verified"]``: hay que mirar los steps para distinguir
    "medido-y-falló" (False) de "no-medible" (None).

    Señales de fallo DURA, en orden de prioridad:
      - cualquier step con ``verified is False`` o ``state_changed is False``
        (el SO confirmó que NO cambió nada -> false-PASS atrapado);
      - cualquier step con ``found is False`` o ``content_verified is False``
        (no se halló el target / el contenido no coincidió);
      - sin steps: las mismas señales a nivel top-level (p.ej. gui.click_text
        con found=False -> needs_verification, verified=False genuino);
      - ``ok`` es False (la tool reportó fallo explícito).

    Si NINGUNA de estas dispara pero el top-level está colapsado a
    verified=False/None, es NO-MEDIBLE (None), no un fallo.
    """
    if last.get("ok") is False:
        return True
    steps = last.get("steps")
    if isinstance(steps, list) and steps:
        for s in steps:
            if not isinstance(s, dict):
                continue
            if s.get("verified") is False:
                return True
            if s.get("state_changed") is False:
                return True
            if s.get("found") is False:
                return True
            if s.get("content_verified") is False:
                return True
        # Hubo steps y NINGUNO falló-medido -> el colapso del top-level a
        # verified=False/None es por steps no-medibles (None): NO es fallo.
        return False
    # Sin steps: leemos las señales de fallo duras directo del top-level.
    if last.get("found") is False:
        return True
    if last.get("content_verified") is False:
        return True
    if last.get("state_changed") is False:
        return True
    if last.get("verified") is False:
        return True
    return False


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
    # Hueco adversarial: una tool READ-ONLY (verified=None: ej. source_manager
    # status, que devuelve ok=True sin cambiar nada) NO debe sustentar un reply que
    # AFIRMA un EFECTO FÍSICO. Ej: "bajá el termostato" → el 4B rutea a
    # source_manager (ok=True, verified=None) y fabrica "Listo, bajé la temperatura"
    # — MENTIRA. La rama de abajo eximía TODO verified=None. Por eso: si el result
    # no cambió estado del mundo (no state_changed, no opened/deeplink, no count de
    # efecto) Y el reply afirma semánticamente un efecto externo, NO eximimos → cae a
    # la nota honesta. Mide la FORMA (embeddings de claim-de-efecto), no listas de
    # frases. Fallback seguro: sin encoder _reply_asserts_effect devuelve False →
    # comportamiento previo intacto.
    _changed_world = (
        last.get("state_changed") is True
        or last.get("opened") is True
        or bool(last.get("url") or last.get("deeplink") or last.get("uri"))
        or last.get("verified") is True
    )
    _asserts_physical_effect = False
    if not _changed_world:
        try:
            from ..safety_pkg.reply_validator import _reply_asserts_effect
            _asserts_physical_effect = _reply_asserts_effect(content)
        except Exception:
            _asserts_physical_effect = False
    if verified is None and status not in {"attempted", "needs_verification", "failed"}:
        if not _asserts_physical_effect:
            return content
        # afirma efecto físico sobre una tool que no cambió el mundo → no eximir.
    elif verified is not False and status not in {"attempted", "needs_verification", "failed"}:
        return content

    completion = str(last.get("completion_status") or "").casefold()
    from ..tools_pkg.tools import _DISPATCH_OK_COMPLETIONS
    if completion in _DISPATCH_OK_COMPLETIONS:
        return content

    if last.get("opened") is True and (last.get("url") or last.get("deeplink") or last.get("uri")):
        return content

    # Hueco adversarial: NO eximir ciegamente todo result con ok=False. Eximir por
    # ok=False asume "el flujo de error upstream ya lo manejó honesto", lo cual vale
    # en `_finalize_turn` pero NO en los short-circuits de acción de `_decide_turn`
    # (calc/app_action/app_open): cuando t_computer_use devuelve ok=False/
    # status=failed SIN clave "reply" (tools.py:2429/2438), el short-circuit cae al
    # texto de ÉXITO HARDCODEADO ("Listo, lo hice en la calculadora." / "Hecho.") y
    # este guard es su ÚLTIMA defensa — eximirlo intacto haría que el reply AFIRMARA
    # ÉXITO en un fallo DURO, o sea mentir.
    # Estructural (mide la FORMA): no hay exención ciega por ok=False. El
    # `already_honest` de abajo SÍ exime el ok=False cuyo content YA es honesto;
    # pero si el content afirma éxito, cae a la lógica tri-estado, donde
    # _has_measured_failure (True para ok is False) emite la nota DURA de
    # no-confirmación. Sin listas de frases de éxito.
    low = content.casefold()
    already_honest = any(
        token in low
        for token in ("intent", "verifi", "no pude", "no se pudo", "error", "fall")
    )
    if already_honest:
        return content
    # TRI-ESTADO honesto. Hasta acá llegan SOLO los casos no-éxito (verified
    # no-True, no-dispatched, ...). Pero "no-éxito" se parte en dos verdades
    # distintas que de lo contrario compartirían el MISMO note (que sonaría a
    # fallo):
    #   (a) MEDIDO-y-falló  -> nota dura "no dejó evidencia" (la conserva
    #       test_dispatch_status::test_nota_still_emitted_for_genuine_failure).
    #   (b) NO-MEDIBLE (None) -> nota SUAVE "lo intenté, no pude confirmar el
    #       efecto" — NUNCA afirma que se hizo, NUNCA se disculpa como si fallara.
    # La señal tri-estado real vive en steps[*]; _has_measured_failure la lee.
    if _has_measured_failure(last):
        evidence = last.get("evidence") or last.get("completion_status") or status or "sin evidencia"
        base = content.rstrip()
        if _asserts_physical_effect:
            base = "No pude completar esa accion con evidencia suficiente."
        return base + _NOTE_MEASURED_FAIL.format(
            status=status or "desconocido", verified=verified, evidence=evidence)
    return content.rstrip() + _NOTE_UNMEASURED


def honest_action_reply(reply: Any) -> Any:
    """Honestidad para los early_reply de ACCIÓN de ``_decide_turn``.

    Los short-circuits de acción (calc_action / app_action / app_open) devuelven
    ``TurnDecision(early_reply=AgentReply(content=...))`` SALTÁNDOSE todo
    ``_finalize_turn`` — y con él ``guard_unverified_final``. Sin este helper el
    tool reporta honesto (``verified=False/None``, ``status=attempted/
    needs_verification``) pero el reply al usuario MENTIRÍA ("Hecho." / "Listo,
    abrí X") porque el guard final nunca corre por ese camino.

    Este helper aplica el MISMO ``guard_unverified_final`` (única fuente de
    verdad — no duplica su lógica de exenciones: dispatched / needs_user /
    deeplink / launch_requested siguen pasando) sobre el ``content`` del reply
    usando sus propios ``tool_events`` como evidencia. Estructural: mide la
    FORMA del result (verified/status), no listas de frases por idioma. Si el
    reply no tiene tool_events (no es de acción) o ya es honesto, lo devuelve
    intacto -> el camino feliz (verified=True) NO se toca.

    Devuelve el mismo objeto reply (con ``content`` reescrito si hizo falta)
    para que el caller pueda seguir usándolo tal cual.
    """
    events = getattr(reply, "tool_events", None)
    if not events:
        return reply
    content = getattr(reply, "content", None)
    if not isinstance(content, str) or not content:
        return reply
    new_content = guard_unverified_final(content, events)
    if new_content != content:
        reply.content = new_content
    return reply


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
    # EXENCIÓN DE TURNO SIN-ACCIÓN: si el router solo ofreció tools META
    # (`session`: cancelaciones/negaciones como "No.", "no lo envíes"), NO hubo
    # acción de SO posible, así que un ack ("cancelé eso" / "listo, lo dejo") NO es
    # una FALSA confirmación de acción — es la verdad (no se hizo nada). Dejamos
    # pasar el reply del LLM en vez del genérico "No alcancé a completar la acción".
    # No debilita la honestidad: con CUALQUIER tool de acción en el subset, el guard
    # dispara como siempre (ver guard_grounded_action_claim, misma exención).
    _subset = {str(t) for t in (last_router_subset or ())}
    if _subset and _subset.issubset({"session"}):
        return content, fallback_streak, last_fallback_user_text

    low = content.lower()
    stripped_low = low.lstrip()
    confirm_match = next(
        (p for p in _FALSE_CONFIRMATION_PATTERNS if stripped_low.startswith(p)),
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

    matched = next((p for p in _PROMISE_PATTERNS if p in low), None)
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
    from ..safety_pkg.grounding_gate import detect_action_claim_without_evidence

    verdict = detect_action_claim_without_evidence(content, events)
    if not verdict.should_replace:
        return content, fallback_streak, last_fallback_user_text
    # EXENCIÓN DE TURNO SIN-ACCIÓN: si el router solo ofreció tools META (p. ej.
    # `session` para una cancelación/negación: "No.", "no lo envíes", "cancelá
    # eso"), NO hubo ninguna acción de SO posible este turno. Entonces un "claim"
    # como "cancelé eso" NO puede ser una mentira sobre una acción de SO — es un ack
    # de INACCIÓN, que es lo verdadero. Dejamos pasar el reply del LLM en vez del
    # genérico "No alcancé a completar la acción" (que implicaría falsamente que
    # había una acción fallida y confundiría al usuario).
    # NO debilita la honestidad: si se ofreció CUALQUIER tool de acción (app/media/
    # web/gui/...), el subset NO es meta-only -> el gate dispara como siempre.
    # EXCEPCIÓN A LA EXENCIÓN (bug routing 2026-06-06): una pregunta HOW-TO ("cómo
    # cierro Spotify?") deja el subset meta-only (el planner retira app/steam para
    # que el LLM EXPLIQUE, no actúe) — pero ahí "Listo, cerré Spotify" SÍ es mentira
    # (el user preguntó CÓMO, no pidió cerrar). La exención meta-only es solo para
    # cancelaciones/negaciones ("cancelé eso"=ack de inacción verdadero), NO para
    # how-to. Detecta la FORMA (interrogador how-to), no listas.
    _is_howto = False
    if current_user_text:
        try:
            from ..routing.planner import _is_howto_or_info_question as _ishw
            _is_howto = _ishw(current_user_text)
        except Exception:
            _is_howto = False
    _META_ONLY = {"session"}
    _subset = {str(t) for t in (last_router_subset or ())}
    if _subset and _subset.issubset(_META_ONLY) and not _is_howto:
        if trace is not None:
            try:
                trace.event(
                    turn_id, "grounded_action_claim_exempt_nonaction",
                    subset=sorted(_subset), original=content[:120],
                )
            except Exception:
                pass
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


def repair_media_fabricated_inline(
    content: str,
    user_text: str,
    events: list[Any],
    turn_id: str,
    *,
    trace: Any | None = None,
) -> str:
    """Reparación INLINE del media-fabricado (cacería tanda 2-5, ~25-30 casos/tanda).

    El 4B tiene un prior degenerado fortísimo a emitir "Stranger Things está
    reproduciéndose en Netflix" ante CUALQUIER pedido de media sin título (o ante
    ruido). El guard deferido (``media_fabricated_claim`` → hint) corrige el PRÓXIMO
    turno, pero el 4B reincide turno a turno, así que el usuario igual ve la mentira
    ESTE turno. Como es alta frecuencia y bajo riesgo (el título NO viene de ninguna
    tool), reemplazamos el reply EN EL ACTO por un acuse honesto y genérico.

    Estructural: solo actúa cuando ``media_fabricated_claim`` confirma la fabricación.
    Gate por env (mismo que el hint deferido): ``GEMMA4_MEDIA_FABRICATED_GUARD=0`` apaga
    ambos. Falla-segura: cualquier excepción deja el reply intacto.
    """
    import os
    if os.environ.get("GEMMA4_MEDIA_FABRICATED_GUARD", "1").strip().lower() \
            in {"0", "false", "no", "off"}:
        return content
    try:
        from ..safety_pkg.reply_validator import (
            media_fabricated_claim, repair_media_fabricated)
        if not media_fabricated_claim(user_text or "", content or "", list(events)):
            return content
        repaired = repair_media_fabricated(content or "")
        if trace is not None and repaired != content:
            try:
                trace.event(turn_id, "reply_repaired_inline", pattern="media_fabricated")
            except Exception:
                pass
        return repaired
    except Exception:
        return content


__all__ = [
    "build_user_facing_fallback",
    "guard_unverified_final",
    "honest_action_reply",
    "guard_phrase_confirm",
    "guard_promise_without_action",
    "guard_grounded_action_claim",
    "guard_plan_status",
    "repair_media_fabricated_inline",
]
