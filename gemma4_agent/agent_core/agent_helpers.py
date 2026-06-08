"""Helpers libres del agente — extraídos de agent.py (2026-06-07, ratchet
archivo-dios: bajar agent.py de 6970->≤6687 LOC sin engrosar el dios).

Son funciones puras/utilidades de nivel módulo (sin `self`): derivación de
outcome/args, formato de réplicas de rutinas-por-frase, gates de env-flags,
parsing de args de tool, timeout, footers, y el clasificador estructural de
pending-intent por forma de la respuesta. No tocan estado del agente; reciben
todo por parámetro. agent.py las re-exporta para no romper imports existentes.

Bonus-fix de la extracción: `_progress` referenciaba un `logger` que NUNCA se
definía en agent.py (NameError latente si la rama except disparaba). Acá el
módulo tiene su propio `logger` real.
"""
from __future__ import annotations

import json
import logging
import re as _re_footers
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Tipo del callback de progreso (espejo del de agent.py — evita import circular).
ProgressCallback = Callable[[str, dict[str, Any]], None]


def _extract_user_text(content: str | list[dict[str, Any]]) -> str:
    """Return the plain-text portion of the user content (no images/audio)."""
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return " ".join(parts).strip()


def _derive_outcome_code(mission_status: str | None,
                          events: list[Any]) -> str | None:
    """Bug 2 — map (mission_status, events) → outcome_code enum.

    The codes are finite, short, and informative for RAG policy hints:
      - PASS_VERIFIED: mission_status=PASS AND at least one tool ran.
      - PASS_UNVERIFIED: PASS but no tool ran (might be smalltalk OR a
        false confirmation — disambiguate downstream via grounding flag).
      - PARTIAL: mission_status=PARTIAL.
      - FAILED: mission_status=FAILED or grounding NLI marked contradiction.
      - NEEDS_USER: mission_status=NEEDS_USER.
      - UNVERIFIED: anything else.
    """
    if not mission_status:
        return "UNVERIFIED"
    ms = str(mission_status).upper()
    if ms == "PASS":
        return "PASS_VERIFIED" if events else "PASS_UNVERIFIED"
    if ms in {"FAILED", "PARTIAL", "NEEDS_USER", "UNVERIFIED"}:
        return ms
    return ms  # passthrough for any custom status the evaluator emits


def _derive_args_signature(events: list[Any]) -> dict[str, Any] | None:
    """Bug 2 — extract normalized tool args for the lesson store.

    Captures only the most-useful, low-cardinality fields (provider, action,
    profile) — not raw queries or PII. The signature is meant to be a
    pattern the RAG can match on (e.g. provider=disney_plus), not a full
    replay of the call.
    """
    if not events:
        return None
    sig: dict[str, Any] = {}
    for ev in events:
        try:
            args = getattr(ev, "args", None) or {}
            if not isinstance(args, dict):
                continue
            for key in ("provider", "action", "engine", "browser"):
                v = args.get(key)
                if isinstance(v, str) and v and key not in sig:
                    sig[key] = v[:40]
        except Exception:
            continue
    return sig or None


def _fold_match(text: str) -> str:
    """Lowercase + drop combining marks for substring matching."""
    import unicodedata
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _strip_for_phrase_only(text: str) -> str:
    """Núcleo comparable para decidir "el usuario dijo SOLO la frase".

    Quita puntuación de borde y colapsa espacios, sobre texto ya plegado por
    :func:`_fold_match`. Así "tiempo", "tiempo.", "  tiempo  " y "¿tiempo?"
    colapsan al mismo núcleo, pero "que tiempo hace" NO (tiene más palabras).
    """
    import re
    core = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", core).strip()


def _phrase_fire_ok(fire: dict[str, Any]) -> bool:
    """¿La rutina disparada por frase corrió TODOS sus pasos con éxito?

    Honestidad (CLAUDE.md #3 + invariante "no fingir éxito"): un paso con
    ok=False, timeout o excepción significa que la rutina NO se completó —
    el mensaje al usuario debe decirlo, no afirmar "Se ejecutó". Una rutina
    sin pasos (results vacío) se considera fallida (no hizo nada).
    """
    results = fire.get("results") or []
    if not results:
        return False
    return all(bool(r.get("ok")) for r in results)


def _format_phrase_only_reply(fires: list[dict[str, Any]]) -> str:
    """Mensaje de confirmación para rutinas disparadas por frase-sola.

    Determinista, en español, breve para voz. Usa el label visible (cae a la
    frase). Es HONESTO: separa las rutinas que corrieron OK de las que
    fallaron, para no decir "Se ejecutó" cuando un paso falló (p. ej. una
    rutina que apunta a una acción inexistente).
    """
    def _name(f):
        return str(f.get("label") or f.get("phrase") or "").strip()

    ok = [_name(f) for f in fires if _phrase_fire_ok(f) and _name(f)]
    failed = [_name(f) for f in fires if not _phrase_fire_ok(f) and _name(f)]

    parts: list[str] = []
    if ok:
        if len(ok) == 1:
            parts.append(f'Se ejecutó tu rutina "{ok[0]}".')
        else:
            parts.append("Se ejecutaron tus rutinas "
                         + ", ".join(f'"{n}"' for n in ok) + ".")
    if failed:
        if len(failed) == 1:
            parts.append(f'No pude completar tu rutina "{failed[0]}" '
                         "(revisá sus pasos en Triggers).")
        else:
            parts.append("No pude completar las rutinas "
                         + ", ".join(f'"{n}"' for n in failed)
                         + " (revisá sus pasos en Triggers).")
    if not parts:
        return "Intenté ejecutar tu rutina, pero no pude completarla."
    return " ".join(parts)


def _is_unverified_result(result: dict[str, Any]) -> bool:
    """Return True if a tool result is failed, unverified, or needs follow-up.

    Mirrors the signals the SYSTEM_PROMPT tells Gemma to treat as 'not done':
    ok=False, verified=False, or status in {failed, needs_verification,
    attempted, needs_confirmation}. needs_user / needs_dependency are NOT
    flagged here because those require user action, not retry, and the
    failure_log filter handles them separately for replan triggering.
    """
    if not isinstance(result, dict):
        return False
    if result.get("ok") is False:
        return True
    if result.get("verified") is False:
        return True
    status = str(result.get("status") or "").casefold()
    return status in {"failed", "needs_verification", "attempted", "needs_confirmation"}


# Hotfix I. Module-level set of "meta" tools — these
# manage agent state / safety / verification rather than perform
# domain actions, so they do not count when deciding whether the
# LLM "should have called something".
_META_TOOLS: frozenset[str] = frozenset({
    "session", "state", "verify", "safety", "skill_load", "subagent",
})

# Info-retrieval tools: OPTIONAL grounding aids the router offers on a question
# ("¿quién es X?"), NOT user-requested ACTIONS. A model that answers such a turn
# from parametric knowledge (prose, no tool call) is behaving CORRECTLY — it must
# NOT trigger the forced-tool-retry (which exists for ACTION turns where the
# model promised "voy a abrir Steam" but skipped the call). Forcing a tool here
# wastes a full second LLM pass on an info turn (measured E2E: 11.8s wasted on
# "¿cuál es la capital de Francia?" — the model already answered "París" and the
# forced web/knowledge retry burned 512 tokens to return nothing).
_INFO_RETRIEVAL_TOOLS: frozenset[str] = frozenset({
    "web", "knowledge", "memory", "source_manager", "fact_check", "local_search",
})

# Question-mark family: ASCII, Spanish inverted, Arabic, CJK
# fullwidth. Single-char comparison; never a keyword list, so the
# detection stays language-agnostic.
_QUESTION_CHARS: frozenset[str] = frozenset({"?", "¿", "؟", "？"})


def _domain_subset(selected_tool_names: list[str]) -> list[str]:
    """Return only the non-meta tools from a router subset.

    Hotfix I. Lifted to module-level for testability —
    used by both I1 (reply-shape pending_intent) and I5
    (tool_call_skipped_when_expected telemetry).
    """
    return [t for t in selected_tool_names if t not in _META_TOOLS]


def _messages_have_image(messages: list[dict[str, Any]]) -> bool:
    """True if any message carries an image part (type=='image_url').

    Router-mode lazy-vision: a TEXT turn (mode=fast_action) can still pull
    in an image MID-turn — e.g. the `gui screenshot` tool injects its capture
    back into history for visual reasoning. The follow-up LLM call then carries
    that image, so it MUST go to the vision preset (which has the mmproj), not
    the text preset. Resolving the model once per turn from mode.name misses
    this; we re-check the actual outgoing messages on every call instead.
    Bug: 'saca un screenshot' -> 500 'image input is not supported' because the
    post-screenshot summarization call was sent to <profile>-text.
    """
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    return True
    return False


def _should_set_pending_intent_from_reply(
    reply_text: str,
    tool_calls_this_turn: list[dict[str, Any]],
    selected_tool_names: list[str],
) -> tuple[str, str] | None:
    """Decide whether to stash a pending_intent based on reply shape.

    Hotfix I. Hotfix F1 already handles the case where
    a tool returns status='needs_user'. This helper covers the
    OTHER case: the LLM asked a clarifying question on its own
    (Bug D8 part 2). 100% structural — only inspects the final
    char of the trimmed reply and the structural result of any
    tool_calls. NEVER matches user text.

    Returns (tool_name, asks_for) when:
      1. Reply text trimmed ends with a question-family char
         (? ¿ ؟ ？).
      2. ZERO successful tool_calls this turn (if a tool ran
         successfully, the turn ended in a normal action — don't
         stash a pending intent on top of it).
      3. selected_tool_names has at least one non-meta tool.
    Returns None otherwise.
    """
    if not reply_text:
        return None
    # Strip trailing whitespace and common closing punctuation
    # (quotes, parens, markdown emphasis) so the trailing-char
    # check sees the real terminal punctuation.
    stripped = reply_text.rstrip().rstrip("\"'`*_)")
    if not stripped or stripped[-1] not in _QUESTION_CHARS:
        return None
    # Accept either ToolEvent dataclasses or dicts. Production
    # callers pass ToolEvent (see agent.py turn loop); unit tests
    # pass dicts for ergonomics.
    def _result_of(c: Any) -> dict[str, Any]:
        if isinstance(c, dict):
            return c.get("result") or {}
        r = getattr(c, "result", None)
        return r if isinstance(r, dict) else {}

    successful = [
        c for c in tool_calls_this_turn
        if not _is_unverified_result(_result_of(c))
    ]
    if successful:
        return None
    candidates = _domain_subset(selected_tool_names)
    if not candidates:
        return None
    return (candidates[0], "user_clarification")


def _run_with_timeout(fn: Any, *args: Any, timeout_s: float, **kwargs: Any) -> dict[str, Any]:
    """Run a sync function in a thread with a hard wall-clock timeout.

    Returns {'result': <fn return>, '_timed_out': False} on success or
    {'result': None, '_timed_out': True} when the deadline elapses.

    Implementation detail: we do NOT use ThreadPoolExecutor's context manager
    because its __exit__ joins all workers, defeating the timeout. We submit
    on a bare executor and call shutdown(wait=False) so a hanging task is
    abandoned (the thread stays alive in the background but the caller moves
    on). The thread is daemonized so it cannot block process exit.
    """
    import concurrent.futures
    import threading
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemma4_timeout")
    # Mark spawned threads as daemons so they cannot keep the process alive.
    original_factory = threading.Thread

    try:
        future = executor.submit(fn, *args, **kwargs)
        try:
            return {"result": future.result(timeout=timeout_s), "_timed_out": False}
        except concurrent.futures.TimeoutError:
            return {"result": None, "_timed_out": True}
        except Exception as exc:
            return {"result": None, "_timed_out": False, "_error": str(exc)}
    finally:
        # Do not wait for the worker; if it's hanging, we abandon it.
        executor.shutdown(wait=False)
        _ = original_factory  # silence linters


def _format_phrase_fires(fires: list[dict[str, Any]]) -> str:
    """Render fired phrase-triggered routines for the system prompt.

    Each entry has {label, phrase, steps_run, results}. We tell Gemma the
    routine already executed and ask it to confirm briefly to the user in
    natural language. When some steps failed or timed out we add an
    explicit honesty instruction so Gemma cannot say 'done' for a step that
    actually broke.
    """
    if not fires:
        return ""
    total_steps = 0
    failed_steps = 0
    timed_out_steps = 0
    lines = ["# Phrase-triggered routines already executed this turn"]
    lines.append("These routines fired BEFORE you got the message because the user's text matched their saved phrase. Do NOT re-run their steps.")
    for fire in fires:
        label = fire.get("label") or "routine"
        phrase = fire.get("phrase") or ""
        results = fire.get("results") or []
        oks = sum(1 for r in results if r.get("ok"))
        total = len(results)
        total_steps += total
        failed_steps += total - oks
        timed_out_steps += sum(1 for r in results if r.get("timed_out"))
        lines.append(f"- {label} (phrase='{phrase}') -> {oks}/{total} steps ok")
        for r in results[:6]:
            tool = r.get("tool", "?")
            ok = r.get("ok")
            err = r.get("error") if not ok else ""
            timed_out = " (TIMED OUT)" if r.get("timed_out") else ""
            extra = f" error={err}" if err else ""
            lines.append(f"   step: tool={tool} ok={ok}{timed_out}{extra}")
    # Behavior contract.
    if failed_steps == 0:
        lines.append("All steps succeeded. Acknowledge briefly to the user in natural language what was done, then handle the rest of the message normally.")
    else:
        msg = (f"WARNING: {failed_steps} of {total_steps} steps did NOT complete"
               + (f" ({timed_out_steps} timed out)" if timed_out_steps else "")
               + ". You MUST tell the user honestly which actions did not run. "
               "Do not say 'listo', 'hecho' or 'done' for the failed steps. "
               "Either suggest a retry, ask the user to investigate, or report the error verbatim.")
        lines.append(msg)
    return "\n".join(lines)


def _summarization_enabled() -> bool:
    """Compaction by LLM summarization. Default on; disable with GEMMA4_AGENT_SUMMARIZATION=false."""
    import os
    raw = (os.environ.get("GEMMA4_AGENT_SUMMARIZATION") or "").strip().casefold()
    if raw in {"0", "false", "no", "off"}:
        return False
    return True


def _summarization_cooldown_turns() -> int:
    """Minimum number of turns between two LLM-summarization calls.

    Default 6. Override via env GEMMA4_AGENT_SUMMARIZATION_COOLDOWN.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_SUMMARIZATION_COOLDOWN") or "").strip()
    try:
        n = int(raw)
        return n if n >= 0 else 6
    except ValueError:
        return 6


def _fact_extraction_enabled() -> bool:
    """Auto fact extraction. OFF by default (privacy).

    Enable with GEMMA4_AGENT_FACT_EXTRACTION=true. When on, after each
    completed turn the agent asks Gemma to extract 0-3 small facts about
    the user (preferences, identifiers, recurring context) and saves them
    to memory with `auto:` prefix.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_FACT_EXTRACTION") or "").strip().casefold()
    return raw in {"1", "true", "yes", "on", "si"}


def _fact_extraction_cooldown_turns() -> int:
    """Min turns between two fact-extraction LLM calls.

    Default 5. Override via env GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_FACT_EXTRACTION_COOLDOWN") or "").strip()
    try:
        n = int(raw)
        return n if n >= 0 else 5
    except ValueError:
        return 5


def _parallel_tools_enabled() -> bool:
    """Run multiple tool calls in the same batch concurrently.

    OFF by default: most local tools share state (filesystem, registry,
    apps_index, MCP clients) and ordering can matter for the model. Enable
    explicitly with GEMMA4_AGENT_PARALLEL_TOOLS=true. When on AND the model
    emitted >=2 valid tool calls in one assistant message, they run on a
    small ThreadPoolExecutor (max_workers=4). Order is preserved when the
    results are stitched back into history.
    """
    import os
    raw = (os.environ.get("GEMMA4_AGENT_PARALLEL_TOOLS") or "").strip().casefold()
    return raw in {"1", "true", "yes", "on", "si"}


def _looks_like_context_overflow(message: str) -> bool:
    low = message.casefold()
    # Phrasing varies across llama-server builds: explicit "exceeds the available
    # context size" or the JSON error type "exceed_context_size_error", plus a
    # generic fallback that pairs "context size" with any "exceed*" variant.
    if "exceeds the available context size" in low:
        return True
    if "exceed_context_size_error" in low:
        return True
    return ("context size" in low) and ("exceed" in low)


# Footers added by the agent (TIER 1 #2 verifier + TIER 2 #5 mission). Si el
# LLM ve uno en el historial, lo va a reproducir en proximos turns, infando
# context + duplicando texto en pantalla. Strippeamos antes de guardar al
# history Y antes de devolver al display.
#
# User explicitly asked for "[misión: ...]" to NEVER appear. El
# patron es case-insensitive y captura variantes con / sin acento. Tambien
# detecta "Mision" (sin acento, Capitalizado) que el LLM podria emitir.
_FOOTER_PATTERNS = [
    # "[misión: ...]" / "[Mision: ...]" — del mission_outcome
    _re_footers.compile(r"\n*\[\s*[Mm]isi[óo]n\s*:[^\]]*\]\s*$"),
    # "[N verificada(s), N no confirmada(s), N no verificable(s)]" — verifier
    _re_footers.compile(r"\n*\[\d+\s*verificada\(s\)[^\]]*\]\s*$"),
    _re_footers.compile(r"\n*\[\d+\s*no\s+confirmada\(s\)[^\]]*\]\s*$"),
    _re_footers.compile(r"\n*\[\d+\s*no\s+verificable\(s\)[^\]]*\]\s*$"),
]


def _strip_trailing_footers(text: str) -> str:
    """Remueve cualquier footer agregado por el agent del final del texto.

    Hace varias pasadas: si hay multiples footers stackeados (verifier +
    mission), los strippea todos. Idempotente (correr 2 veces da lo mismo).
    """
    if not text:
        return text
    prev = None
    cur = text.rstrip()
    while cur != prev:
        prev = cur
        for pat in _FOOTER_PATTERNS:
            cur = pat.sub("", cur).rstrip()
    return cur


def _parse_args(raw: Any) -> tuple[dict[str, Any], str | None]:
    """Parse a tool-call arguments field.

    Returns (args_dict, parse_error). parse_error is None on success; otherwise
    it's a short human-readable string suitable for surfacing to the LLM. The
    args_dict always returns something callable so the caller can still log a
    placeholder, but in the error case the caller MUST short-circuit and not
    invoke the tool with sucky data.
    """
    if isinstance(raw, dict):
        return raw, None
    if raw is None:
        return {}, None
    if isinstance(raw, str):
        raw_trim = raw.strip()
        if not raw_trim:
            return {}, None
        try:
            parsed = json.loads(raw_trim)
            if isinstance(parsed, dict):
                return parsed, None
            return {"value": parsed}, None
        except json.JSONDecodeError as exc:
            # Surface the column so Gemma can see what it sent wrong.
            preview = raw_trim if len(raw_trim) <= 200 else raw_trim[:200] + "..."
            return {"_raw_invalid_json": preview}, f"invalid_json: {exc.msg} at pos {exc.pos}"
    return {"value": raw}, f"unsupported_args_type: {type(raw).__name__}"


def _progress(callback: ProgressCallback | None, event: str, **payload: Any) -> None:
    """Forward a progress event. Errors in the user callback are swallowed
    but logged to stderr so they don't go fully silent."""
    if callback is None:
        return
    try:
        callback(event, payload)
    except Exception as exc:
        try:
            logger.warning("progress callback error in event=%s: %s", event, exc)
        except Exception:
            pass
