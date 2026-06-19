"""Reparación y observación del reply: detección de info-followup, query
contextual, instrucción de idioma por turno, mismatch de idioma, selección de
eventos relevantes para el summary, y los pases LLM de observación / reescritura
de idioma. Extraído de agent.py (2026-06-08, ratchet archivo-dios: bajar agent.py
bajo su techo tras la tanda de fixes de idioma/media de Codex).

Las funciones que necesitan estado del agente reciben `agent` como primer
parámetro (antes eran métodos de Gemma4Agent); agent.py deja wrappers delgados que
delegan acá, así los call-sites internos (`self._repair_*`, `self._event_*`) no
cambian. Las constantes y helpers de idioma (`_LANG_NAMES`, `_reply_lang`,
`_detect_lang`, `sanitize_text`) viven en agent.py / módulos hermanos y se importan
a nivel de función para no crear un ciclo de import en tiempo de carga.
"""
from __future__ import annotations

from typing import Any


# ----------------------------------------------------------------------------
# Funciones puras (antes module-level en agent.py)
# ----------------------------------------------------------------------------

def turn_language_instruction(user_text: str | None) -> str:
    from .agent import _reply_lang, _LANG_NAMES
    text = (user_text or "").strip()
    if not text:
        return ""
    lang = _reply_lang(text)
    name = _LANG_NAMES.get(lang)
    if not name:
        return ""
    return (
        "\n\n# Reply language for this turn\n"
        f"Selected conversation language: {name} ({lang}). "
        f"Reply ONLY in {name} for this turn. "
        "Interpret the user's message under this language unless the selector "
        "or a strong language signal says otherwise. "
        "This turn-level instruction overrides examples, tool schemas, "
        "retrieved snippets, memory, prior assistant replies, and persona text."
    )


# Fórmulas de CIERRE/CORTESÍA cortas → set de idiomas al que pertenecen.
# Identificación de idioma por la FORMA de la fórmula (mismo precedente que
# _IMPERATIVE_VERBS en agent.py: desambiguación ortográfica, NO una tabla de
# respuestas — el reply lo generó el LLM; acá solo decidimos si su idioma
# contradice el del usuario). MEDIDO (2026-06-11): py3langid es inservible en
# acks de <12 chars alfabéticos ("Listo."→en, "Con gusto."→de, "De rien."→en),
# por eso el gate corto NO puede usar _detect_lang sin falsos repairs en el
# hot-path. Formas compartidas entre idiomas llevan el set completo ("de nada"
# es es Y pt): solo hay mismatch si el idioma del usuario NO está en el set.
_SHORT_CLOSURE_LANGS: dict[str, frozenset[str]] = {
    "de nada": frozenset({"es", "pt"}),
    "por nada": frozenset({"es", "pt"}),
    "con gusto": frozenset({"es"}),
    "a la orden": frozenset({"es"}),
    "listo": frozenset({"es"}),
    "hecho": frozenset({"es"}),
    "vale": frozenset({"es"}),
    "claro": frozenset({"es", "pt"}),
    "you're welcome": frozenset({"en"}),
    "youre welcome": frozenset({"en"}),
    "no problem": frozenset({"en"}),
    "my pleasure": frozenset({"en"}),
    "anytime": frozenset({"en"}),
    "all set": frozenset({"en"}),
    "done": frozenset({"en"}),
    "sure": frozenset({"en"}),
    "de rien": frozenset({"fr"}),
    "je t'en prie": frozenset({"fr"}),
    "avec plaisir": frozenset({"fr"}),
    "d'accord": frozenset({"fr"}),
    "bitte": frozenset({"de"}),
    "gern geschehen": frozenset({"de"}),
    "gerne": frozenset({"de"}),
    "erledigt": frozenset({"de"}),
    "prego": frozenset({"it"}),
    "di niente": frozenset({"it"}),
    "figurati": frozenset({"it"}),
    "fatto": frozenset({"it"}),
    "pronto": frozenset({"pt", "it"}),
    "feito": frozenset({"pt"}),
}


def _short_closure_lang_set(reply_text: str) -> frozenset[str] | None:
    """Set de idiomas de un reply-fórmula corto, o None si no es una fórmula
    conocida. Normaliza: casefold + colapsa espacios + strip de puntuación de
    borde. Solo matchea el reply COMPLETO (un reply con contenido extra no es
    una fórmula de cierre y queda fuera del gate corto)."""
    t = " ".join((reply_text or "").casefold().split())
    t = t.strip(".,;:!? ¡¿\"'()")
    return _SHORT_CLOSURE_LANGS.get(t)


def reply_language_mismatch(
    user_text: str | None,
    reply_text: str | None,
    target_lang: str | None = None,
) -> tuple[bool, str, str]:
    from .agent import _reply_lang, _detect_lang, _LANG_NAMES
    utext = (user_text or "").strip()
    rtext = (reply_text or "").strip()
    if not utext or not rtext:
        return False, "", ""
    target = target_lang if target_lang in _LANG_NAMES else _reply_lang(utext)
    if target not in _LANG_NAMES:
        return False, "", ""
    # Very short acknowledgements can be language-neutral ("OK", "Done", "Si")
    # and _detect_lang is unreliable there (measured). Repair ONLY when the
    # reply is a KNOWN closure formula whose language set excludes the target
    # (bug real 2026-06-10: "I guess it." -> "De nada."). Unknown short
    # replies keep the old skip — no LLM rewrite without reliable signal.
    # es↔pt comparten imperativos cortos ("abre Spotify" detecta pt, medido):
    # el target se expande a su grupo confusable para no reescribir "Listo."
    # de un usuario hispano cuyo comando detectó pt.
    if sum(1 for ch in rtext if ch.isalpha()) < 12:
        langs = _short_closure_lang_set(rtext)
        confusable = {"es", "pt"} if target in {"es", "pt"} else {target}
        if langs and not (langs & confusable):
            return True, target, "/".join(sorted(langs))
        return False, target, ""
    reply_lang = _detect_lang(rtext)
    return reply_lang != target, target, reply_lang


def is_info_followup_question(user_text: str, previous_tools: list[str] | tuple[str, ...]) -> bool:
    """Short question continuing a previous information/research turn."""
    from .agent_helpers import _INFO_RETRIEVAL_TOOLS, _QUESTION_CHARS
    text = (user_text or "").strip()
    if not text or not (set(previous_tools or []) & _INFO_RETRIEVAL_TOOLS):
        return False
    words = text.split()
    if len(words) < 3 or len(words) > 14:
        return False
    try:
        from ..routing.intent_router import classify_intent, is_question_lexical
        is_q, conf = is_question_lexical(text)
        scores = classify_intent(text)
    except Exception:
        is_q = any(ch in text for ch in _QUESTION_CHARS)
        conf = 0.55 if is_q else 0.0
        scores = None
    if not is_q or conf < 0.55:
        return False
    if scores is None:
        return conf >= 0.80
    if scores.action - scores.info > 0.05:
        return False
    if scores.selfref >= 0.70 and (scores.selfref - scores.info) >= 0.12:
        return False
    if max(scores.action, scores.chitchat, scores.selfref, scores.meta) - scores.info > 0.10:
        return False
    return scores.info >= 0.45


def research_tool_fallback_enabled() -> bool:
    """Last-resort read-only web fallback for research turns."""
    import os as _os
    return (_os.environ.get("GEMMA4_RESEARCH_TOOL_FALLBACK", "1") or "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


def contextual_info_query(user_text: str, history: list[dict[str, Any]] | None) -> str:
    """Build a search query for an elliptical info follow-up.

    Uses conversation structure only: current user text plus the previous
    substantive user turn. It does not infer domain-specific entities or answer.
    """
    current = (user_text or "").strip()

    def _msg_text(msg: dict[str, Any]) -> str:
        content = msg.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
            return " ".join(parts).strip()
        return ""

    previous = ""
    for msg in reversed(history or []):
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        text = _msg_text(msg)
        if not text or text == current or text.startswith("[system note]"):
            continue
        if len(text.split()) >= 2:
            previous = text
            break
    query = " ".join(part for part in (previous, current) if part).strip()
    return query[:220] if query else current[:220]


# ----------------------------------------------------------------------------
# Selección de eventos relevantes para el reply (antes static/classmethods)
# ----------------------------------------------------------------------------

def event_args_for_reply(ev: Any) -> dict[str, Any]:
    args = getattr(ev, "args", {}) or {}
    return args if isinstance(args, dict) else {}


def event_result_for_reply(ev: Any) -> dict[str, Any]:
    result = getattr(ev, "result", {}) or {}
    return result if isinstance(result, dict) else {}


def event_successful_for_reply(ev: Any) -> bool:
    result = event_result_for_reply(ev)
    if result.get("ok") is False or result.get("verified") is False:
        return False
    status = str(result.get("status") or "").casefold()
    return status not in {
        "failed", "needs_verification", "attempted", "needs_confirmation",
    }


def event_auxiliary_for_reply(ev: Any) -> bool:
    """Read-only/status events should not dominate a post-action summary."""
    name = str(getattr(ev, "name", "") or "").casefold()
    args = event_args_for_reply(ev)
    result = event_result_for_reply(ev)
    completion = str(result.get("completion_status") or "").casefold()
    if completion in {
        "resumed_current_media",
        "current_media_already_playing",
        "app_opened",
        "message_sent",
        "uia_action_completed",
    }:
        return False
    action = str(
        result.get("action") or args.get("action") or ""
    ).replace("_", " ").strip().casefold()
    read_actions = {
        "status", "pending", "list", "read", "get", "query", "search",
        "find", "active", "active tab title", "now playing", "screenshot",
        "snapshot", "tree", "scan", "info", "devices", "processes",
        "cpu ram gpu", "disk", "battery", "get volume", "brightness get",
    }
    if name in {"verify"}:
        return True
    if name == "safety" and action in {"status", "pending"}:
        return True
    return action in read_actions


# ----------------------------------------------------------------------------
# Pases LLM de observación / reescritura de idioma (necesitan el agente)
# ----------------------------------------------------------------------------

def llm_observation_reply(agent: Any, user_text: str, evidence: dict[str, Any],
                          fallback: str, target_lang: str | None = None) -> str:
    from .agent import _LANG_NAMES, sanitize_text
    import os as _os_lor
    if _os_lor.environ.get("GEMMA4_LLM_OBSERVATION_REPLY", "1").strip().lower() \
            in {"0", "false", "no", "off"}:
        return fallback
    try:
        if target_lang and target_lang in _LANG_NAMES:
            _lang_rule = f"Reply ONLY in {_LANG_NAMES[target_lang]}. "
        else:
            _lang_rule = "Reply in the same language as the user. "
        sys_p = (
            "You are Baxy, a local Windows voice assistant. Answer the user's "
            "question from the provided tool evidence only. "
            f"{_lang_rule}One short sentence, plain text."
        )
        usr_p = (
            f"User asked: {user_text[:300]}\n"
            f"Tool evidence: {evidence}\n"
            "Answer:"
        )
        _model = agent._router_model_for([{"role": "user", "content": usr_p}])
        resp = agent.client.chat(
            [{"role": "system", "content": sys_p},
             {"role": "user", "content": usr_p}],
            tools=None, enable_thinking=False, parallel_tool_calls=False,
            max_tokens=60, timeout_s=12.0, model=_model,
        )
        choices = resp.get("choices") or []
        raw = str((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
        raw = sanitize_text(raw)
        return raw or fallback
    except Exception as _exc:
        try:
            agent.trace.event("agent", "silent_fallback",
                              component="llm_observation_reply",
                              error=f"{type(_exc).__name__}: {_exc}")
        except Exception:
            pass
        return fallback


def llm_knowledge_reply(agent: Any, user_text: str, fallback: str,
                        target_lang: str | None = None) -> str:
    """Regenera el reply como RESPUESTA DE CONOCIMIENTO honesta.

    Bug "J Balvin" live 2026-06-09: ante una pregunta CULTURAL/de conocimiento
    ("¿conocés a J Balvin?", "¿has escuchado a X?") el router NO ofrece tools y el
    4B debe responder con lo que SABE — pero a veces alucina una acción consumada
    ("ya escuché sus canciones", "he reproducido en Spotify"). El guard detecta el
    claim falso; en vez del genérico "no ejecuté nada, ¿lo intento?" (absurdo: no
    hay nada que ejecutar), regeneramos como conocimiento directo. El LLM
    responde, no inventa acciones. Gate GEMMA4_LLM_ACTION_REPLY.
    """
    from .agent import _LANG_NAMES, sanitize_text
    import os as _os_lkr
    if _os_lkr.environ.get("GEMMA4_LLM_ACTION_REPLY", "1").strip().lower() \
            in {"0", "false", "no", "off"}:
        return fallback
    try:
        if target_lang and target_lang in _LANG_NAMES:
            _lang_rule = f"Reply ONLY in {_LANG_NAMES[target_lang]} (the user's language). "
        else:
            _lang_rule = "Reply in the SAME language the user wrote their message in. "
        sys_p = (
            "You are Baxy, a local Windows voice assistant. The user asked a "
            "KNOWLEDGE question (about a person, artist, movie, topic). Answer "
            "DIRECTLY with what you know, in one or two short sentences. You are a "
            "text assistant: do NOT claim to have listened to music, watched videos, "
            "opened apps, searched, or performed ANY action — you are only answering "
            "from knowledge. If you don't know, say so honestly. "
            f"{_lang_rule}Plain text, no markdown, no emojis."
        )
        usr_p = f"User asked: {user_text[:300]}\nAnswer:"
        _model = agent._router_model_for([{"role": "user", "content": usr_p}])
        resp = agent.client.chat(
            [{"role": "system", "content": sys_p},
             {"role": "user", "content": usr_p}],
            tools=None, enable_thinking=False, parallel_tool_calls=False,
            max_tokens=120, timeout_s=12.0, model=_model,
        )
        choices = resp.get("choices") or []
        raw = str((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
        raw = sanitize_text(raw)
        return raw or fallback
    except Exception as _exc:
        try:
            agent.trace.event("agent", "silent_fallback",
                              component="llm_knowledge_reply",
                              error=f"{type(_exc).__name__}: {_exc}")
        except Exception:
            pass
        return fallback


def repair_reply_language_if_needed(agent: Any, user_text: str, assistant_text: str,
                                    turn_id: str,
                                    target_lang: str | None = None) -> tuple[str, bool]:
    from .agent import _detect_lang, sanitize_text
    needs, target, reply_lang = reply_language_mismatch(
        user_text, assistant_text, target_lang)
    if not needs:
        return assistant_text, False
    # Método del agente (no la función del módulo) para respetar monkeypatch.
    fixed = agent._llm_rewrite_reply_language(user_text, assistant_text, target)
    fixed = sanitize_text(fixed)
    # ANTI-FABRICACIÓN (medido en vivo 2026-06-11): el rewrite del 2B parafraseó
    # "It is 00:04:33 on June 11, 2026." → "The current time is 10:30 AM."
    # (inventó la hora pese al "preserve the same facts"). Un rewrite de idioma
    # NUNCA puede introducir tokens de hora que el original no tenía.
    try:
        from ..safety_pkg.reply_validator import _clock_pairs
        if fixed and (_clock_pairs(fixed) - _clock_pairs(assistant_text)):
            fixed = ""
    except Exception as _cp_exc:
        try:
            agent.trace.event("agent", "silent_fallback",
                              component="lang_rewrite_clock_check",
                              error=f"{type(_cp_exc).__name__}: {_cp_exc}")
        except Exception:
            pass
    fixed_lang = _detect_lang(fixed) if fixed else ""
    # Aceptación: _detect_lang es poco fiable en rewrites cortos ("De rien."→en,
    # medido) — si el rewrite es una fórmula de cierre conocida cuyo set incluye
    # el target, eso ES confirmación de idioma (misma tabla que el gate corto).
    _fixed_closure = _short_closure_lang_set(fixed) if fixed else None
    if _fixed_closure and target in _fixed_closure:
        fixed_lang = target
    if fixed and fixed.strip() and fixed_lang == target:
        try:
            agent.trace.event(
                turn_id, "reply_lang_repair",
                user_lang=target, reply_lang=reply_lang,
                before=(assistant_text or "")[:80], after=fixed[:80],
            )
        except Exception:
            pass
        if getattr(agent, "_tts_streamed", False):
            agent._tts_streamed = False
            agent._tts_streamed_text = ""
            agent._tts_info_stream = False
        return fixed, True
    try:
        agent.trace.event(
            turn_id, "reply_lang_repair_failed",
            user_lang=target, reply_lang=reply_lang,
            fixed_lang=fixed_lang,
        )
    except Exception:
        pass
    return assistant_text, False
