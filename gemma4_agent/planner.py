"""Lightweight mission planning and dynamic tool selection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any


STEP_SPLIT_RE = re.compile(
    r"\b(?:luego|despues|después|entonces|y luego|y despues|y después|,\s*luego)\b|[;]\s*",
    re.IGNORECASE,
)
# Cap on tools offered per turn. Lowered 16->10 (2026-05-20 latency): a big
# subset bloats the LLM prefill AND pushes the agent into thinking-ON mode for
# no benefit. Measured on the curated router corpus: holdout recall is
# IDENTICAL at 10 vs 16 (0.8345) — the anti-overfit metric doesn't move — and
# dev only drops 0.840->0.826. The planner orders by priority (utility tools
# last), so the cap trims the low-value tail, not the relevant head. Over-offer
# cases like "abre Spotify" (no dedicated tool) go 16->10 tools.
MAX_SELECTED_TOOLS = 8

# Semantic-confidence override of the conversational abstention gate.
# A single tool whose cosine to the query clears _SEM_CONFIDENT_SCORE means
# the wording lands squarely on that tool's intent — a real command even if
# the intent classifier read the turn as conversational (common on one-word
# imperatives like "mutea"/"pausa"). When overriding we keep only tools
# within _SEM_CONF_BAND of the peak, not the noisy tail. Tuned on dev only.
import os as _os
_SEM_CONFIDENT_SCORE = float(_os.environ.get("GEMMA4_SEM_CONFIDENT", "0.45"))
_SEM_CONF_BAND = float(_os.environ.get("GEMMA4_SEM_CONF_BAND", "0.12"))
# Confident-peak escape from the abstention gate: a single tool whose cosine
# clears _SEM_PEAK_KEEP AND beats the runner-up by _SEM_PEAK_GAP is treated as a
# real command even if the abstain head leans no-tool (e.g. "mutea"→audio).
# Tuned for the fine-tuned encoder's higher cosine scale (dev).
_SEM_PEAK_KEEP = float(_os.environ.get("GEMMA4_SEM_PEAK_KEEP", "0.60"))
_SEM_PEAK_GAP = float(_os.environ.get("GEMMA4_SEM_PEAK_GAP", "0.15"))
# When one tool clearly dominates ("abre steam"->steam 0.74), keep only tools
# within this band of it (drops the noisy tail -> small subset). Recall-safe:
# the labeled tool IS the dominant peak in these crisp single-intent commands.
_SEM_PEAK_BAND = float(_os.environ.get("GEMMA4_SEM_PEAK_BAND", "0.20"))
# Budget for speculative related-tool deps (the gui/uia/vision/window fan-out
# that, stacked on the semantic union, produced the operator's "11 tools").
_RELATED_BUDGET = int(_os.environ.get("GEMMA4_RELATED_BUDGET", "3"))
# Per-tool head firing filters: a tool must clear its threshold by this margin
# (weak just-over-bar firings are noise), and at most this many head tools.
_HEAD_MIN_MARGIN = float(_os.environ.get("GEMMA4_HEAD_MIN_MARGIN", "0.05"))
_HEAD_TOP_N = int(_os.environ.get("GEMMA4_HEAD_TOP_N", "3"))
# Cap on the semantic fallback list (used ONLY when the tool head AND keywords
# both came up empty — a hard query we still want to take a shot at).
_SEM_TOPN = int(_os.environ.get("GEMMA4_SEM_TOPN", "5"))
# P(no_tool) above which the abstain head VETOES the per-tool head (kills a
# marginal tool firing on a clearly-conversational turn). High so it only fires
# on confident no-tool, not borderline commands.
_VETO_P = float(_os.environ.get("GEMMA4_VETO_P", "0.78"))
# Above this absolute INFO score, the keyword-protection treats the turn as a
# knowledge question (a "what is X" frame) and does NOT shield a spurious
# keyword from the abstain wipe. Below it, a fired keyword is a real command.
_KW_PROTECT_INFO_BLOCK = float(_os.environ.get("GEMMA4_KW_PROTECT_INFO_BLOCK", "0.55"))


@dataclass
class MissionStep:
    index: int
    text: str
    suggested_tools: list[str] = field(default_factory=list)
    verification_hint: str = ""


@dataclass
class MissionPlan:
    goal: str
    steps: list[MissionStep]
    cleanup_expected: bool = False
    needs_pc_action: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "cleanup_expected": self.cleanup_expected,
            "needs_pc_action": self.needs_pc_action,
            "steps": [
                {
                    "index": step.index,
                    "text": step.text,
                    "suggested_tools": step.suggested_tools,
                    "verification_hint": step.verification_hint,
                }
                for step in self.steps
            ],
        }

    def prompt_hint(self) -> str:
        if not self.steps:
            return ""
        lines = [
            "# Current Mission Draft",
            "This is a deterministic draft from the user request. Follow it when it matches the user's intent; do not expose it.",
            f"Goal: {self.goal}",
        ]
        for step in self.steps:
            tools = ", ".join(step.suggested_tools) if step.suggested_tools else "none"
            lines.append(f"{step.index}. {_short_text(step.text, 240)} | suggested_tools={tools} | verify={step.verification_hint or 'result evidence'}")
        if self.cleanup_expected:
            lines.append("Cleanup expected: use state(action='cleanup') or targeted close/delete after completing the mission.")
        return "\n".join(lines)


def plan_mission(content: str | list[dict[str, Any]]) -> MissionPlan:
    text = _content_text(content)
    parts = _split_steps(text)
    steps = [
        MissionStep(index=i + 1, text=part, suggested_tools=_suggest_tools(part), verification_hint=_verify_hint(part))
        for i, part in enumerate(parts)
    ]
    cleanup_expected = bool(re.search(r"\b(limpia|limpiar|cleanup|cierra todo lo que abriste|cerrar al final)\b", text, re.IGNORECASE))
    needs_pc_action = any(step.suggested_tools for step in steps)
    if len(steps) == 1 and not needs_pc_action:
        steps = []
    return MissionPlan(goal=text[:500], steps=steps, cleanup_expected=cleanup_expected, needs_pc_action=needs_pc_action)


def select_tool_names(
    content: str | list[dict[str, Any]],
    plan: MissionPlan,
    *,
    safety_enabled: bool = False,
    last_assistant_text: str | None = None,
    prev_user_text: str | None = None,
    pending_intent: dict[str, Any] | None = None,
) -> list[str]:
    """Return a small, ordered tool subset for the current turn.

    Strategy:
    1. Keyword match (cheap, deterministic, multi-language regex).
    2. Continuation hint: if the previous assistant message indicated
       a pending question (e.g. "¿Cuál es tu perfil en Netflix?"),
       the current user reply is likely the answer. Force the relevant
       tool into the subset even if the user just said "Ema".
    3. If keywords found nothing, fall back to semantic similarity over
       multilingual sentence embeddings (semantic_router.suggest_tools_semantic).
    4. If everything came up empty, return [] (or ["safety"] when enabled).
    """
    raw_text = _content_text(content)
    # Expand colloquial shorthand ("vol"→"volumen", "wsp"→"whatsapp") so
    # abbreviated queries route by meaning. Universal normalization, not a
    # keyword→tool map. Applied before BOTH keyword and embedding paths.
    raw_text = _expand_abbreviations(raw_text)
    text = _fold_text(raw_text)
    names: list[str] = []
    for step in plan.steps:
        names.extend(step.suggested_tools)
    if not names:
        names.extend(_suggest_tools(text))

    # Continuation hint: si el agente preguntó por perfil de streaming en
    # el turn anterior y este turn parece una respuesta corta (no es un
    # comando nuevo), forzar media en el subset. El LLM decide si llamar
    # media o no — pero sin la tool en el subset no podría.
    streaming_hint_media = False
    if last_assistant_text and "media" not in names:
        prev_low = _fold_text(last_assistant_text)
        is_streaming_question = (
            ("perfil" in prev_low or "profile" in prev_low)
            and re.search(
                r"\b(netflix|disney|hbo|max|prime|amazon|spotify)\b",
                prev_low,
            )
        )
        if is_streaming_question:
            # Solo añadir media si el user no acaba de pedir algo
            # claramente distinto (ya cubierto por _suggest_tools, names != []).
            if not names or len(raw_text.split()) <= 6:
                names.insert(0, "media")
                streaming_hint_media = True

    semantic_fallback_used = False
    if raw_text.strip():
        # Sprint 8 (2026-05-20): the semantic router runs ALWAYS now, not
        # only when keywords come up empty. Keyword matching is precise for
        # action verbs but blind to intent expressed in wording our regex
        # doesn't cover — especially informational questions in any
        # language ("quién es X", "who is X", "de qué trata X"). The
        # embedding model (paraphrase-multilingual, 50+ languages) covers
        # that universally. We UNION the semantic suggestions onto the
        # keyword names: keywords guarantee the action tools stay (no
        # regression), semantics add the knowledge/intent tools keywords
        # miss. Smalltalk/greetings still short-circuit to no tools.
        word_count = len(raw_text.split())
        casual = re.search(
            r"^\s*(hola|hello|hi|hey|hola!|buenos dias|buenas tardes|buenas noches|buen dia|"
            r"good morning|good afternoon|good evening|"
            r"ola|bom dia|boa tarde|boa noite|"
            r"bonjour|bonsoir|salut|"
            r"ciao|buongiorno|buonasera|"
            r"gracias|thanks|thank you|obrigado|merci|grazie|"
            r"que tal|how are you|como estas|como estan|tudo bem|ca va|come stai)\b",
            _fold_text(raw_text),
        )
        # Semantic abstention gate (2026-05-20 night): the semantic router
        # returns its top-k for ANY input above a low cosine floor, so on
        # conversational turns (smalltalk, "quién eres", "no entiendo") it
        # over-offers domain tools the user never requested — the dominant
        # source of NO-TOOL over-offers in the eval. is_conversational()
        # decides PURELY by intent (chitchat/selfref outrank action/info)
        # whether the turn is "talking" rather than "do X" / "tell me about
        # the world". When it is, we skip the semantic union. Keyword hits
        # (precise action verbs) and wants_knowledge (real questions) still
        # stand, so this can't silence a genuine command or question.
        conversational = False
        try:
            from .intent_router import is_conversational
            conversational = is_conversational(raw_text)
        except Exception:
            conversational = False
        # Run semantics unless it's pure smalltalk. We compute the scored
        # matches first so a CONFIDENT top-1 can override the conversational
        # gate: a one-word imperative ("mutea", "pausa", "minimiza") reads
        # as conversational by intent (chitchat edges action on contentless
        # tokens) yet lands squarely on one tool's meaning (audio 0.51,
        # media 0.45, window 0.36). True chitchat/self-reference spreads
        # thin and low (~0.27 on catch-all tools). So we abstain ONLY when
        # the turn is conversational AND no tool match is confident — both
        # signals must agree it's "just talking". Pure semantic confidence,
        # no keywords.
        if not casual and (
            word_count >= 2 or "?" in raw_text or "¿" in raw_text
            or len(raw_text.split()) == 1  # single-word imperatives count
        ):
            from .semantic_router import suggest_tools_scored
            scored = suggest_tools_scored(raw_text, k=12)
            top_score = scored[0][1] if scored else 0.0
            confident = top_score >= _SEM_CONFIDENT_SCORE

            # Step 2 (2026-05-21): CALIBRATED abstention head. All four
            # research reports converged: NO-TOOL keep (0.51) is the weak
            # spot, and the fix is a learned reject option over cheap
            # query-comparable features, not another raw-cosine threshold.
            # The head sees the 5 intent-centroid scores, the semantic-cosine
            # shape, length and a keyword-fired flag (trained on dev only;
            # weights in data/abstain_head.json). It REPLACES the old
            # "conversational AND not confident" heuristic when available.
            abstain = None
            abstain_p = 0.0  # P(no_tool) from the head, for the veto strength
            try:
                from .abstain_head import load_model, build_features, is_enabled as _ah_on
                if _ah_on():
                    _m = load_model()
                    if _m is not None:
                        _scored_intent = None
                        try:
                            from .intent_router import classify_intent
                            _scored_intent = classify_intent(raw_text)
                        except Exception:
                            _scored_intent = None
                        _feats = build_features(
                            raw_text, intent=_scored_intent, scored=scored,
                            keyword_fired=bool(names),
                        )
                        abstain = _m.should_abstain(_feats)
                        abstain_p = _m.p_no_tool(_feats)
            except Exception:
                abstain = None

            # ONE authoritative abstention decision (2026-05-21 rebuild). All
            # four research reports were unanimous: abstention must be a single
            # calibrated decision, not a residual that survives only if every
            # tool-adding path happens to miss. The CALIBRATED head decides;
            # two narrow escapes protect real commands the head over-suppresses.
            #
            # Confident-peak escape: a crisp imperative like "mutea" reads as
            # short/contentless to the head (p_no_tool ~0.70) yet lands squarely
            # on ONE tool (audio 0.65, wide gap to #2). Keep just that peak. The
            # bar is high (_SEM_PEAK_KEEP) because the FT encoder's cosines run
            # higher; true smalltalk/knowledge spreads flatter and never clears
            # it. The other escapes (pending_intent, streaming hint) are explicit
            # prior-turn continuation signals, handled at the wipe below.
            peak_gap = (scored[0][1] - scored[1][1]) if len(scored) >= 2 else top_score
            confident_peak = (top_score >= _SEM_PEAK_KEEP
                              and peak_gap >= _SEM_PEAK_GAP)

            head_available = abstain is not None
            # Effective abstain: the learned head when present, else the prior
            # conversational heuristic. Confident commands stay either way.
            do_abstain = (abstain is True) if head_available else bool(conversational)

            # Protect keyword-matched action tools from the abstain wipe UNLESS
            # the turn is informational. "reproduce daddy yankee" fires the media
            # keyword but its OOV object makes the semantic list empty, fooling
            # the head into abstaining — the keyword is the true signal there.
            # But a keyword firing on a knowledge question ("que es pytest" ->
            # developer) is a false positive that SHOULD abstain.
            _kw_protect: list[str] = []
            if names:
                _is_knowledge = False
                try:
                    from .intent_router import wants_knowledge as _wk, classify_intent as _ci2
                    _is_knowledge = _wk(raw_text)
                    if not _is_knowledge:
                        # Looser knowledge guard for the keyword-protection only:
                        # a "what is X" frame scores high INFO even when chitchat
                        # edges it ("qué es pytest": info 0.64, chitchat 0.66).
                        # wants_knowledge stays strict (used elsewhere); here we
                        # also block protection when info is high in absolute
                        # terms, so a spurious keyword on a knowledge question
                        # ("pytest"->developer) doesn't survive the abstain wipe.
                        _si = _ci2(raw_text)
                        if _si is not None and _si.info >= _KW_PROTECT_INFO_BLOCK:
                            _is_knowledge = True
                except Exception:
                    _is_knowledge = False
                if not _is_knowledge:
                    _kw_protect = list(names)

            # A genuine WORLD-KNOWLEDGE question ("de qué trata Dune", "who
            # directed Oppenheimer") must NOT be abstained — it needs web/
            # knowledge to look the answer up. wants_knowledge() already added
            # those to `names`; protect them through the abstain gate (the
            # abstain head's high p_no_tool on these is a false positive — they
            # ARE no-PC-action, but they're a web lookup, not silence).
            _is_world_q = False
            try:
                from .intent_router import wants_knowledge as _wk2
                _is_world_q = _wk2(raw_text)
            except Exception:
                _is_world_q = False
            _knowledge_keep = [n for n in names if n in {"web", "knowledge",
                               "source_manager"}] if _is_world_q else []

            if do_abstain and not pending_intent and not streaming_hint_media:
                if confident_peak or (not head_available and confident):
                    # Keep only the dominant peak (+near ties) + protected kw.
                    cut = top_score - _SEM_CONF_BAND
                    scored = [p for p in scored if p[1] >= cut]
                    _keep = ({nm for nm, _ in scored} | set(_kw_protect)
                             | set(_knowledge_keep))
                    names = [n for n in names if n in _keep]
                else:
                    scored = []
                    names = list(_kw_protect) + [n for n in _knowledge_keep
                                                 if n not in _kw_protect]
            # PER-TOOL LOGIT HEAD (2026-05-21) — the research's anti-bloat
            # architecture. Instead of taking the semantic top-k / a band (which
            # drags a flat-distribution cluster like "pausa"->media,app,study,
            # accessibility into the subset), each tool has its OWN calibrated
            # threshold; the subset is only the tools that individually clear
            # their bar. "pausa" fires {media}; "abre steam" fires {steam,app};
            # "que es pytest" fires {} — small and precise BY CONSTRUCTION.
            # We UNION the head's firings with the keyword hits (keyword is the
            # high-precision recall floor that catches OOV objects like
            # "reproduce daddy yankee" the encoder can't place), and fall back to
            # the semantic top-k only when BOTH come up empty (so we never regress
            # to nothing on a real but hard query).
            # The abstain head VETOES the tool head on a clear no-tool turn:
            # if the calibrated abstain decision says "conversational" AND no
            # precise keyword fired AND it's not a parked continuation, we do
            # not let the per-tool head pull anything. This is what keeps
            # knowledge questions / smalltalk at zero domain tools even though a
            # tool's logit might marginally clear its bar. A keyword hit
            # (_kw_protect) or a confident command bypasses the veto.
            # Veto only when the abstain head is CONFIDENT (p >= _VETO_P), so a
            # borderline real command the head is unsure about still reaches the
            # tool head. Tuned on dev to balance no-tool keep vs recall.
            _abstain_veto = (do_abstain and abstain_p >= _VETO_P
                             and not _kw_protect
                             and not _is_world_q
                             and not pending_intent and not streaming_hint_media
                             and not confident_peak)
            head_tools: list[str] = []
            if not _abstain_veto:
                try:
                    from .tool_head import load as _th_load, is_enabled as _th_on
                    if _th_on():
                        _th = _th_load()
                        if _th is not None:
                            from .semantic_router import embed as _emb
                            _qv = _emb(raw_text)
                            if _qv is not None:
                                # Keep only firings with a real margin over
                                # their threshold, and cap to the top-N: a tool
                                # barely over its bar (margin < _HEAD_MIN_MARGIN)
                                # is weak evidence and tends to be noise
                                # ("minimiza VS Code" -> media_edit @ 0.14).
                                _fired = _th.fire(_qv)
                                head_tools = [t for t, m in _fired
                                              if m >= _HEAD_MIN_MARGIN][:_HEAD_TOP_N]
                except Exception:
                    head_tools = []

            sem = [name for name, _ in scored]
            if head_tools:
                # Head fired: it is the precise primary. Union with keyword hits
                # (both high-precision); do NOT dump the semantic top-k tail.
                existing = set(names)
                for t in head_tools:
                    if t not in existing:
                        names.append(t)
                        existing.add(t)
                if not names:
                    semantic_fallback_used = True
            elif sem:
                # Head fired nothing. Keep keyword hits; only fall back to the
                # semantic list when keywords ALSO came up empty (a hard query
                # the head couldn't score but the encoder still placed).
                if not names:
                    names = list(sem[:_SEM_TOPN])
                    semantic_fallback_used = True
                # else: keyword hits stand alone (precise); no semantic flood.

    # NOTE: continuation resolution via prev_user_text was tried (night of
    # 2026-05-20) and abandoned: on this corpus the previous-user-turn rarely
    # carries the deictic's referent ("mutea" ← prev "saca pantallazo";
    # "ciérralo" ← prev "ponlo bajito"; many have prev=None). The real
    # continuation signal is the actually-executed tool of the prior turn,
    # which the AGENT inherits from real history (agent.py) — not derivable
    # from the prev user text. The param is kept for API symmetry but the
    # planner does not guess from it.

    if not names:
        # Even on a "smalltalk" turn the user can ask to cancel ("tiempo",
        # "stop", "espera"). Expose session.cancel_turn so the LLM can pick
        # it without falling back to a generic reply.
        base = ["session"]
        if safety_enabled:
            base.append("safety")
        # 2026-05-20: a parked tool (prior turn returned needs_user) must
        # survive even when THIS reply is smalltalk-shaped. The classic case:
        # media asks "what's your Disney profile?" and the user replies
        # "Mi perfil es Ema" (no keyword → names empty). Without this, the
        # pending intent was dropped here (before the injection below) and
        # the profile never reached media → infinite "need disney profile"
        # loop. Inject the parked tool at the head.
        if pending_intent:
            pi_tool = str((pending_intent or {}).get("tool") or "")
            if pi_tool and pi_tool not in base:
                base.insert(0, pi_tool)
        select_tool_names._last_fallback_used = False  # type: ignore[attr-defined]
        return base

    # Same negative anchor as in _suggest_tools: if the user mentioned "perfil"
    # / "profile" but NO email-specific keyword, semantic fallback sometimes
    # bubbles email to the top. Drop it. Keeps the rest of the subset intact.
    if "email" in names and re.search(r"\b(perfil|profile)\b", text) and not re.search(
        r"\b(mail|email|correo|courriel|posta|messaggio)\b", text,
    ):
        names = [n for n in names if n != "email"]

    # Related-tools deps, BUDGETED across the whole subset. The unconditional
    # fan-out (every app/media tool dragging in gui/uia/vision/window/browser/
    # audio) was the second bloat engine behind the "11 tools" complaint.
    # Directly-matched tools are always kept; deps fill only up to the budget.
    expanded: list[str] = []
    _rel_budget = _RELATED_BUDGET
    for name in _dedupe(names):
        expanded.append(name)
        for rel in _related_tools(name, text):
            if rel in expanded:
                continue
            if _rel_budget <= 0:
                break
            expanded.append(rel)
            _rel_budget -= 1
    if plan.cleanup_expected or re.search(r"\b(cleanup|limpia|limpiar|cierra todo lo que abriste|rollback|restaura|deshacer)\b", text):
        expanded.append("state")
    if safety_enabled:
        expanded.append("safety")
    capped = _cap_tools(_dedupe(expanded), MAX_SELECTED_TOOLS)
    # Hotfix F 2026-05-17: pending_intent injection. If a previous turn
    # left a tool waiting on user input (status='needs_user'), inject
    # the tool at the head so it survives the cap. Language-agnostic:
    # the slot is set on a STRUCTURAL tool result, never inferred from
    # user text.
    if pending_intent:
        pi_tool = str((pending_intent or {}).get("tool") or "")
        if pi_tool and pi_tool not in capped:
            capped.insert(0, pi_tool)
    # session.cancel_turn is always reachable so the LLM can interrupt the
    # current turn in any language without depending on a keyword list. We
    # append it AFTER the cap so it cannot be dropped — its description is
    # small (~330 tokens) and the LLM ignores it when not applicable.
    if "session" not in capped:
        capped.append("session")
    # Stash signal on the function so the agent can record it in traces.
    select_tool_names._last_fallback_used = semantic_fallback_used  # type: ignore[attr-defined]
    return capped


# Default attribute, overwritten on each call.
select_tool_names._last_fallback_used = False  # type: ignore[attr-defined]


def _content_text(content: str | list[dict[str, Any]]) -> str:
    if isinstance(content, str):
        return content.strip()
    chunks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            chunks.append(str(item.get("text") or ""))
    return " ".join(chunks).strip()


def _split_steps(text: str) -> list[str]:
    raw_parts = [part.strip(" ,.") for part in STEP_SPLIT_RE.split(text) if part.strip(" ,.")]
    if len(raw_parts) <= 1:
        return [text.strip()] if text.strip() else []
    merged: list[str] = []
    for part in raw_parts:
        if len(part.split()) <= 2 and merged:
            merged[-1] = f"{merged[-1]} {part}".strip()
        else:
            merged.append(part)
    return merged[:8]


def _suggest_tools(step: str) -> list[str]:
    """Keyword-based tool router. Spanish + English buckets.

    The folded text drops accents (NFKD + combining strip) so we can match
    "música" and "musica" with the same pattern. Keywords were trimmed in
    Sprint 3a to ES + EN only (CORE_PROMPT commits the agent to reply in
    Spanish; the PT/FR/IT branches were unused output paths). The embedding
    fallback in select_tool_names handles whatever this misses.
    """
    low = _fold_text(step)
    tools: list[str] = []

    # steam (proper noun, identical across langs)
    if "steam" in low or re.search(r"\b(biblioteca|tienda|library|store)\b", low):
        tools.append("steam")
    # media: song / video / play / pause. NOTE: bare "pon"/"ponme" and the app
    # name "youtube" were REMOVED from this raw trigger — "pon" is too greedy
    # ("ponme un recordatorio" -> media), and "youtube" fired media even on
    # "cierra youtube" (close). Real media-PLAY intent is covered by the explicit
    # play nouns/verbs below + the streaming-platform rule (which now gates media
    # on a play verb). "pon" only counts when followed by a media object.
    if re.search(r"\b(cancion|musica|reproduce|reproducir|pausa|reanuda|resume|"
                 r"play|siguiente|anterior|"
                 r"music|song|track|playlist|next|previous|skip|pause)\b", low) or \
       re.search(r"\b(pon|ponme|poneme)\b.*\b(cancion|musica|video|tema|playlist|"
                 r"rock|jazz|pop|reggaeton|algo de|music|song)\b", low):
        tools.append("media")
    # audio: volume / mute
    if re.search(r"\b(volumen|mute|silencio|audio|sonido|"
                 r"volume|silence|sound)\b", low):
        tools.append("audio")
    # audio_device
    if re.search(r"\b(dispositivo de audio|salida de audio|entrada de audio|altavoz|altavoces|microfono|"
                 r"focusrite|aux|realtek|hyperx|scarlett|"
                 r"audio device|audio output|audio input|speaker|speakers|microphone|mic)\b", low):
        tools.append("audio_device")

    # browser
    if re.search(r"\b(opera|chrome|edge|firefox|youtube|google|navegador|browser|web|pagina|page|url|tab|pestana|"
                 r"website|site)\b", low):
        tools.append("browser")
        if re.search(r"\b(lee|leer|investiga|investigar|extrae|extraer|contenido|fuente|noticia|actual|"
                     r"read|research|extract|content|source|news|current|latest)\b", low):
            tools.append("web")
            tools.append("browser_real")
    if re.search(r"\b(investiga|investigar|fuentes|citas|source|snapshot|referencia|guarda fuente|"
                 r"research|cite|citation|reference|save source)\b", low):
        tools.extend(["web", "source_manager"])
    # Current-facts the model can't know from training → web. Weather is the
    # big one (live repro 2026-05-20: "que temperatura hay en Madrid" /
    # "weather in London" routed to NOTHING; the embedder doesn't tie
    # clima/tiempo/weather to web search). Also live prices/rates/scores.
    if re.search(r"\b(clima|tiempo que hace|que tiempo hace|temperatura|"
                 r"va a llover|llovera|pronostico|forecast|weather|"
                 r"cotizacion|precio actual|cuanto vale|cuanto esta|"
                 r"tipo de cambio|resultado del partido|marcador|"
                 # 2026-05-20: release dates the model can't know — "cuando
                 # sale gta 6", "cuando se estrena/lanza X". Real fail logs.
                 r"cuando sale|cuando sale|cuando se estrena|cuando estrena|"
                 r"cuando se lanza|cuando lanzan|fecha de (salida|lanzamiento|estreno)|"
                 r"when does .* (release|come out)|release date)\b", low):
        tools.append("web")

    # filesystem
    if re.search(r"\b(archivo|carpeta|directorio|escribe|crea|borra|copia|mueve|renombra|zip|extrae|descomprime|"
                 r"file|folder|directory|write|create|delete|copy|move|rename|extract|unzip)\b", low):
        tools.append("filesystem")
    # A filename WITH an extension is an unambiguous file operation, whatever
    # the verb. 2026-05-20 live repro: "agrega una linea al final de notas.txt"
    # routed to notes_tasks (the word "notas") instead of filesystem. Detect a
    # name.ext token and force filesystem in. Structural signal, not a keyword.
    if re.search(r"\b[\w\-]+\.(txt|md|csv|json|log|pdf|docx?|xlsx?|pptx?|py|js|ts|"
                 r"html?|xml|yaml|yml|ini|cfg|zip|png|jpe?g)\b", low):
        tools.append("filesystem")
    # office
    # Multi-word variants ("power point", "hoja de calculo") MUST be checked
    # before the \b...\b single-word pattern, because re.search with \b on a
    # multi-word alternative requires the WHOLE compound to live between word
    # boundaries — which it does, but \bpowerpoint\b won't match "power point"
    # (two words). The Sprint 7 follow-up audit caught this: "Puedes hacerme
    # un power point?" was routed to web instead of office.
    if re.search(
        r"\b(powerpoint|presentacion|diapositiva|pptx|word|docx|excel|xlsx|"
        r"spreadsheet|hoja de calculo|pdf|"
        r"presentation|slide|slides|workbook|sheet|"
        # multi-word variants (with optional accent on presentación):
        r"power\s+point|presentaci[oó]n|hoja\s+de\s+c[aá]lculo)\b", low):
        tools.append("office")
    if re.search(r"\b(csv|tabla|grafico|estadistica|analisis de datos|limpia datos|"
                 r"table|chart|graph|statistics|data analysis|clean data)\b", low):
        tools.extend(["filesystem", "office"])

    # app
    if re.search(r"\b(abre|abrir|cierra|cerrar|app|programa|juego|"
                 r"open|close|launch|quit|exit|program|application|game)\b", low) and "steam" not in low:
        tools.append("app")
    # gui/uia/vision: click/type/screen
    if re.search(r"\b(click|clic|teclea|teclear|escribe en pantalla|pantalla|boton|"
                 r"type|screen|button)\b", low):
        tools.extend(["uia", "gui", "vision"])
    if re.search(r"\b(registro|registry|regedit)\b", low):
        tools.append("registry")
    if re.search(r"\b(variable de entorno|environment variable|env var|\benv\b)\b", low):
        tools.append("env")
    if re.search(r"\b(descarga|descargar|download|sha256|hash|firma)\b", low):
        tools.append("download")

    if re.search(r"\b(recuerda|recorda|guarda en memoria|memoria|"
                 r"remember|remind me|save to memory|memory)\b", low):
        tools.append("memory")
    if re.search(r"\b(documento|rag|conocimiento|knowledge base|base de conocimiento|"
                 r"document|knowledge)\b", low):
        tools.extend(["memory", "knowledge"])
    if re.search(r"\b(dependencia|dependency|libreria|modulo|instala dependencia|falta|missing)\b", low):
        tools.append("dependency")
    if re.search(r"\b(contacto|contactos|telefono|email de|correo de|vcard|"
                 # 2026-05-20: natural read/write phrasings were missed —
                 # "tengo el numero de X", "agrega a X con numero", "guardado
                 # el contacto de". \bnumero\b near a name = contact op.
                 r"numero de|el numero|guardado el contacto|agrega a |agregar a |"
                 r"contact|phone|email of|number of)\b", low):
        tools.append("contacts")
    if re.search(r"\b(nota|notas|tarea|tareas|lista|checklist|pendiente|"
                 # "anota"/"apunta" (verb) and plural "notas" weren't caught
                 # by \bnota\b. "que notas tengo" / "anota que ...".
                 r"anota|anotar|apunta|apuntar|"
                 r"note|notes|task|todo)\b", low):
        tools.append("notes_tasks")
    if re.search(r"\b(calendario|agenda|agendad[oa]|agendar|evento|eventos|ics|"
                 # 2026-05-20: calendar READ phrasings were missed (write was
                 # fine). "que tengo agendado para hoy" / "que reuniones tengo"
                 # routed to nothing. \bagenda\b doesn't match "agendado".
                 r"reunion|reuniones|cita medica|citas medicas|que tengo (hoy|manana|el)|"
                 r"calendar|event|meeting|appointment|schedule)\b", low):
        tools.append("local_calendar")
    if re.search(r"\b(habito|habitos|racha|streak|habit|hobby|"
                 # "registra que hoy hice X" / "lleva la cuenta de" — habit log.
                 r"registra que|llevar la cuenta|llevo \d+ dias|hice ejercicio|"
                 r"track my)\b", low):
        tools.append("habit_tracker")
    if re.search(r"\b(busca en mis archivos|encuentra archivo|buscar archivo|reciente|"
                 r"search files|find file|recent files)\b", low):
        tools.append("local_search")
    if re.search(r"\b(impresora|imprime|imprimir|cola de impresion|scanner|escaner|escanear|"
                 r"printer|print|print queue|scan)\b", low):
        tools.append("printer_scanner")
    if re.search(r"\b(monitor|pantallas|layout|ventanas|escritorio|workspace|"
                 r"screen|window|desktop)\b", low):
        tools.append("desktop_layout")
    # Window-management verbs (minimize/maximize/restore/move a window). These
    # had NO keyword, so "minimiza la de VS Code" fell entirely to the encoder,
    # which mis-fired (VS Code -> developer/media_edit). A window verb is an
    # unambiguous `window` op — anchor it so the head's noise can't dominate.
    if re.search(r"\b(minimiza|minimizar|maximiza|maximizar|restaura(r)? la ventana|"
                 r"restaura(r)? ventana|mueve la ventana|cambia de ventana|"
                 r"trae(r)? al frente|enfoca|foco a|"
                 r"minimize|maximize|restore window|move (the )?window|focus (the )?window|"
                 r"bring to front)\b", low):
        tools.append("window")
    if re.search(r"\b(backup|respaldo|copia de seguridad|restore|restaurar|dedupe|duplicados|"
                 r"deduplicate|duplicates)\b", low):
        tools.append("backup_sync")
    if re.search(r"\b(timer|temporizador|alarma|avisame|notificacion|recordatorio|"
                 r"alarm|reminder|notify|notification)\b", low):
        tools.append("notification")
    # Routine triggers including phrase-based ("cuando te diga X haz Y"
    # Alexa-style). We accept several common typos for "cuando" / "diga"
    # ("cuanto", "dija", "diega") because users mistype these often.
    if re.search(r"\b(rutina|automatiza|automatizacion|cuando pase|cada vez|"
                 r"cuando te diga|cuando te dija|cuanto te diga|cuanto te dija|"
                 # 2026-05-20: also the "te"-less Alexa phrasing the user
                 # actually says — "cuando diga buenos dias abre X" was being
                 # routed to the action/notification instead of `routine`.
                 r"cuando diga|cuando dija|cuanto diga|cuando digas|"
                 r"cuando le diga|si te digo|si digo|cada vez que diga|"
                 r"si te escribo|cuando escriba|cuando escribas|cuando ponga|"
                 r"quiero que aprietes|quiero que apriete|quiero que presiones|"
                 r"quiero que pulses|quiero que ejecutes|"
                 r"recuerda esto|recuerda lo siguiente|registra esta rutina|"
                 r"routine|automate|automation|whenever|every time|"
                 r"when i say|whenever i say|every time i say|if i say|"
                 r"remember this|save this routine)\b", low):
        tools.append("routine")
    # Bare phrase-trigger declaration: user describes a future action without
    # using "routine" verbatim. Matches sentences like "que aprietes <key>",
    # "press <key> when i say", "presiona <tecla>". These nudge the keyword
    # router toward `routine` so Gemma sees the tool in the subset.
    if re.search(r"\b(que aprietes|que apriete|que presiones|que pulses|"
                 r"press the .* key|press the .* button)\b", low):
        if "routine" not in tools:
            tools.append("routine")
        # gui covers keypress / hotkey actions the routine will probably
        # invoke as a step.
        for needed in ("gui", "uia"):
            if needed not in tools:
                tools.append(needed)
    # Direct "tecla de" / "media key" requests should also surface gui.
    if re.search(r"\btecla(s)? de\b|\bmedia key\b|\bplay.?pause\b|\bvolume up\b|\bvolume down\b", low):
        if "gui" not in tools:
            tools.append("gui")
    # WhatsApp keywords — IMPORTANTE: chequear ANTES del match de email/message
    # para que "mandale mensaje en wsp" no caiga en email.
    # Cubre variantes ES/EN + foneticas de Whisper (guasap, wasap, huatsap).
    if re.search(
        r"\b(whatsapp|wsp|wpp|wasap|guasap|guazap|huatsap|whats)\b|"
        r"\b(mandale|mandar|enviale|envia|escribile|escribir|dile|decile|"
        r"di a|message)\b[^.]{0,40}\b(whatsapp|wsp|wpp|wasap|guasap)\b|"
        r"\b(whatsapp|wsp|wpp|wasap|guasap)\b[^.]{0,40}\b(mensaje|message|texto|chat)\b",
        low,
    ):
        tools.append("whatsapp")
        # Tambien incluir contacts para el resolve_recipient si el user paso
        # un nombre en vez de un numero ("mandale a Juan").
        tools.append("contacts")
    if re.search(r"\b(mail|email|correo|enviar mensaje|"
                 r"send mail|send email|message)\b", low):
        # Si ya elegimos whatsapp, NO empujar email — son tools distintas y
        # whatsapp es el match mas especifico.
        if "whatsapp" not in tools:
            tools.append("email")
    # Negative anchor for streaming-profile replies. "Mi perfil es <X>" used
    # to misroute to email via semantic fallback (perfil ~ profile ~ account ~
    # mail). The pending-action resume in agent.py intercepts this case before
    # the router runs, but if that bypass ever breaks we still don't want the
    # router to confidently steer toward email. Drop email when "perfil" /
    # "profile" appears WITHOUT any email-specific keyword above.
    if "email" in tools and re.search(r"\b(perfil|profile)\b", low) and not re.search(
        r"\b(mail|email|correo)\b", low,
    ):
        tools = [t for t in tools if t != "email"]

    # Streaming platforms: si el user menciona una plataforma explicitamente,
    # asegurar que `media` este en el subset (donde estan los providers
    # spotify/netflix/disney/hbo_max/prime_video).
    if re.search(
        r"\b(spotify|espotifai|spoti|"
        r"netflix|netfli|neflix|"
        r"disney|disney\+|disneyplus|disney plus|"
        r"hbo|hbo max|hbomax|hbo\+|max\b|"
        r"prime video|primevideo|amazon prime|amazon video|"
        r"apple music|apple tv|"
        r"youtube|yutu|yutubi|youtu)\b",
        low,
    ):
        # `media` (playback control) + `browser` (web fallback) only matter when
        # the user wants to PLAY/WATCH content ("pon X en spotify", "reproduce
        # Y") — NOT for a bare "abre/open spotify", which just launches the app
        # (app/window cover that). Adding them on every platform mention bloated
        # "abre spotify" to 5-6 tools. Gate on a play verb; a plain open stays
        # tight (app only). A platform mentioned with NO open verb (e.g. just
        # "spotify") also gets media — it's likely a playback intent.
        # media/browser ONLY on an explicit play/watch verb. A bare "abre
        # spotify" (launch) or "cierra youtube" (close) must NOT pull playback
        # tools — app/window cover open/close. Requiring a positive play verb
        # (instead of "not an open verb") fixes "cierra youtube" wrongly getting
        # media+browser.
        _play_verb = re.search(
            r"\b(pon|poneme|ponme|reproduce|reproducir|play|escucha|escuchar|"
            r"ver|mira|mirar|mostrar|watch|siguiente|anterior|next|previous|"
            r"pausa|reanuda|resume|skip|cancion|musica|tema|playlist|"
            r"video|episodio|pelicula|serie|capitulo)\b", low)
        if _play_verb:
            if "media" not in tools:
                tools.append("media")
            if "browser" not in tools:
                tools.append("browser")
    if re.search(r"\b(recordatorio graph|microsoft todo|to do|todoist|tarea pendiente cloud)\b", low):
        tools.append("reminder")

    # system info (processes, CPU/RAM/GPU/disk/battery usage, time). But NOT
    # when it's a CONCEPT question — "qué es una GPU" / "what is a CPU" asks for
    # an explanation, not this machine's stats. A "what is / qué es" frame in
    # front of the hardware word means knowledge, not a system query.
    if re.search(r"\b(proceso|process|cpu|ram|gpu|disco|disk|bateria|battery|hora|time)\b", low) \
       and not re.search(r"\b(que es|qu[eé] es|what is|what'?s|que significa|"
                         r"what does|explica|explicame|explain)\b", low):
        tools.append("system")
    if re.search(r"\b(portapapeles|clipboard|copiar al portapapeles|pega|paste|"
                 r"area de transferencia)\b", low):
        tools.append("clipboard")
    if re.search(r"\b(terminal|powershell|cmd|comando|ejecuta|"
                 r"shell|command|run|execute)\b", low):
        tools.append("terminal")
    if re.search(r"\b(teclado|idioma|layout|language|input method|"
                 r"keyboard)\b", low):
        tools.append("input")
    if re.search(r"\b(winget|paquete|instalar app|desinstalar|"
                 # 2026-05-20: "esta instalado X" / "tengo instalado X" (the
                 # READ — is a program installed) were missed.
                 r"instalad[oa]|tengo instalad|esta instalad|version de \w+ (que tengo|instalada)|"
                 r"package|install app|uninstall|is .* installed)\b", low):
        tools.append("package")

    # ---- Tools added in phases C/D/F3 ----
    # developer: code, tests, lint, git, dev server
    if re.search(r"\b(repositorio|repo|tests|test|pytest|unitarias|lint|format|formato|prettier|black|ruff|eslint|"
                 r"git status|git diff|git log|dev server|servidor de desarrollo|"
                 r"npm run|yarn|pnpm|cargo|go test|build|compile|"
                 r"unit test|coverage)\b", low):
        tools.append("developer")
    # device_settings
    if re.search(r"\b(wifi|wi-fi|red wifi|red inalambrica|ssid|bluetooth|monitor|monitores|display|resolucion|"
                 r"plan de energia|power plan|economizador|alto rendimiento|brillo|brightness)\b", low):
        tools.append("device_settings")
    # game_launcher
    if re.search(r"\b(epic|epic games|gog|galaxy gog|xbox|xbox app|microsoft store game|riot|league of legends|valorant|battle\.net|battlenet)\b", low):
        tools.append("game_launcher")
    # media_edit
    if re.search(r"\b(recorta|recortar|cortar video|trim|convierte el video|convierte el audio|transcodifica|extrae audio|subtitulos|normaliza audio|miniatura|thumbnail|ffmpeg|"
                 r"crop video|cut video|transcode|extract audio|subtitles|normalize audio)\b", low):
        tools.append("media_edit")
    # maintenance
    if re.search(r"\b(windows update|defender|antivirus|escaneo|firewall|event log|visor de eventos|servicio|"
                 r"servicios de windows|punto de restauracion|restore point|disk cleanup|cleanmgr|limpieza de disco|"
                 r"scan|virus|service|services)\b", low):
        tools.append("maintenance")
    # watcher
    if re.search(r"\b(vigila|vigilar|monitorea|monitorear|cuando cambie|cuando se modifique|avisame cuando|watcher|"
                 r"watch|monitor|when changes|notify me when)\b", low):
        tools.append("watcher")
    # job_manager
    if re.search(r"\b(en segundo plano|background job|tarea larga|corre en paralelo|deja corriendo|job manager|"
                 r"in background|long-running|run in parallel)\b", low):
        tools.append("job_manager")
    # network
    if re.search(r"\b(ping|hacer ping|traceroute|tracert|dns|resolver dominio|abre el puerto|puerto cerrado|"
                 r"conexiones activas|ip publica|public ip|public_ip|wireshark|"
                 r"resolve domain|port check|active connections)\b", low):
        tools.append("network")
    # data_analysis
    if re.search(r"\b(csv|pandas|describe|histograma|grafica|grafico de dispersion|scatter|plot|distribucion|"
                 r"estadistica descriptiva|histogram|chart|graph|distribution|descriptive statistics)\b", low):
        tools.append("data_analysis")
    # fact_check
    if re.search(r"\b(verifica|verificar|es cierto|es verdad|fact check|fact-check|contradice|contradicen|respaldan|"
                 r"fuente lo confirma|fuente lo dice|afirmacion|"
                 r"verify|true|false|claim|contradict|support)\b", low):
        tools.append("fact_check")
    # photo_library
    if re.search(r"\b(fotos|foto|imagenes del telefono|exif|miniaturas de fotos|organiza fotos|agrupa por fecha|biblioteca de fotos|raw fotos|"
                 r"photos|photo|pictures|images|thumbnail|organize photos|group by date|photo library)\b", low):
        tools.append("photo_library")
    # container
    if re.search(r"\b(docker|contenedor|contenedores|docker-compose|compose up|compose down|imagen docker|"
                 r"container|containers|docker image)\b", low):
        tools.append("container")
    # database
    if re.search(r"\b(sqlite|base de datos|database|postgres|postgresql|mysql|mariadb|select \*|consulta sql|query sql|"
                 r"sql query)\b", low):
        tools.append("database")
    # creative_local
    if re.search(r"\b(comfyui|stable diffusion|genera imagen|generar imagen|sdxl|flux\.1|flux1|workflow de comfyui|prompt para imagen|"
                 r"generate image|create image|image prompt)\b", low):
        tools.append("creative_local")
    # form_filler
    if re.search(r"\b(rellena el formulario|llena el formulario|completa el formulario|envia formulario|submit form|form fill|"
                 r"fill form|fill the form|complete the form|submit the form)\b", low):
        tools.append("form_filler")
        tools.append("browser_real")
    # peripheral
    if re.search(r"\b(usb|controles |controles$|control xbox|gamepad|joystick|joypad|periferico|periferal|joy-con|"
                 r"dualshock|dualsense|administrador de dispositivos|device manager|hid|"
                 r"controllers|controller|peripheral|peripherals)\b", low):
        tools.append("peripheral")
    # accessibility
    if re.search(r"\b(lupa|magnifier|narrador|narrator|alto contraste|high contrast|accesibilidad|dictado|"
                 r"accessibility|dictation)\b", low):
        tools.append("accessibility")
    # study
    if re.search(r"\b(flashcard|flashcards|tarjeta de estudio|repaso espaciado|spaced repetition|anki|deck de estudio|repeticion espaciada|"
                 r"study card|spaced rep|deck)\b", low):
        tools.append("study")
    # smart_home: any (turn|switch|encender|apagar) + (light|luz) anywhere wins.
    # Plus brand keywords (home assistant, hass, mqtt, etc).
    _smart_home_action = re.search(
        r"\b(enciende|encender|enciendan|"
        r"apaga|apague|apaguen|apagar|"
        r"prende|prender|prendan|"
        r"turn on|turn off|switch on|switch off)\b",
        low,
    )
    _smart_home_target = re.search(
        r"\b(luz|luces|lampara|lamparas|light|lights|lamp|lamps)\b",
        low,
    )
    if (_smart_home_action and _smart_home_target) or re.search(
        r"\b(home assistant|domotica|escena cine|escena de luces|"
        r"termostato|sensor de temperatura|hass|mqtt|persianas|"
        r"smart home|home automation|scene|thermostat|blinds)\b",
        low,
    ):
        tools.append("smart_home")
    # document: (read|extract|summarize verb) + (pdf|docx|xlsx|pptx|html|documento) wins.
    _doc_verb = re.search(
        r"\b(lee|leer|leyendo|lea|leas|"
        r"extrae|extraer|extraigo|extrayendo|"
        r"resume|resumir|resumiendo|resumelo|"
        r"resumi|resuma|resumas|"
        r"parsea|parsear|parseando|"
        r"ocr|escaneado|escaneada|"
        r"read|reading|"
        r"extract|extracting|"
        r"summarize|summarise|summarizing|summarising|"
        r"parse|parsing)\b",
        low,
    )
    _doc_target = re.search(r"\b(pdf|docx|xlsx|pptx|html?|documento|document|documents)\b", low)
    if (_doc_verb and _doc_target) or re.search(
        r"\b(extrae tablas|extract tables|extract_text)\b",
        low,
    ):
        tools.append("document")
        # "read|extract|summarize <doc>" wins over "office" (which is for creation).
        if "office" in tools:
            tools.remove("office")

    # IDENTITY / "WHO AM I" questions: chequear memory primero.
    # "como me llamo", "cual es mi nombre", "quien soy", "what's my name",
    # "remember my name". Estos NUNCA deberian responder "no se" sin chequear.
    if re.search(
        r"\b(como me llamo|cual es mi nombre|mi nombre|"
        r"quien soy|quien soi|"
        r"what'?s my name|what is my name|my name|who am i)\b",
        low,
    ):
        if "memory" not in tools:
            tools.insert(0, "memory")

    # FACTUAL KNOWLEDGE questions ("quién es X", "de qué trata X", "who is
    # X", "wer ist X" ...). Sprint 8 (2026-05-20): replaced the
    # per-language interrogative regex with a SEMANTIC intent classifier
    # (intent_router.wants_knowledge) — universal across languages, robust
    # on short queries, no keyword maintenance. If the user's intent is
    # informational (about the world, not a PC action), ensure web +
    # knowledge are reachable so the LLM can look things up. We add them
    # even when an entity name (a game, a person) already pulled action
    # tools — asking ABOUT something is not the same as acting on it.
    try:
        from .intent_router import wants_knowledge
        # Don't pile web/knowledge onto a LOCAL-FACT query the system can answer
        # itself. "qué hora es" / "cuánta batería tengo" read as informational
        # (info>action) and used to drag web+knowledge in, but the `system` tool
        # answers them locally — no web lookup needed. When a strong local tool
        # already matched, the question is about THIS machine, not the world.
        _LOCAL_FACT = {"system", "app", "media", "audio", "audio_device",
                       "device_settings", "network", "clipboard"}
        if wants_knowledge(step) and not (set(tools) & _LOCAL_FACT):
            if "web" not in tools:
                tools.append("web")
            if "knowledge" not in tools:
                tools.append("knowledge")
    except Exception:
        # Embedding model unavailable → degrade gracefully (no crash);
        # the rest of the subset still stands.
        pass

    return _dedupe(tools)


def _verify_hint(step: str) -> str:
    low = _fold_text(step)
    if "steam" in low:
        return "steam result, window focus, screenshot if GUI state is unclear"
    if "youtube" in low or "video" in low or "musica" in low:
        return "direct URL plus screenshot; playback may remain unverified"
    if "archivo" in low or "carpeta" in low:
        return "verify(action='file_exists') or filesystem diff/list"
    if "navegador" in low or "google" in low or "web" in low:
        return "browser_real/web content for reading; browser result only for navigation"
    if "cierra" in low or "cerrar" in low:
        return "verify app/window/process no longer exists"
    return "tool status/evidence"


def _related_tools(name: str, text: str) -> list[str]:
    if name == "steam":
        return ["app", "window", "verify"]
    if name == "app":
        return ["window", "verify"]
    if name == "browser":
        related = ["browser_real"] if re.search(r"\b(click|rellena|lee|texto|tab|pestana|descarga)\b", text) else []
        return related + ["verify"]
    if name == "browser_real":
        return ["browser", "web", "state"]
    if name == "web":
        return ["source_manager"]
    if name == "media":
        return ["browser", "audio"]
    if name == "audio_device":
        return ["audio", "state", "dependency"]
    if name in {"filesystem", "registry", "env", "download", "office", "backup_sync"}:
        return ["verify", "state"]
    # GUI family: only cross-link the ACTUAL automation primitives (gui/uia/
    # vision interchange for clicking/reading the screen). A plain window op
    # ("minimiza la ventana", "restaura") needs `window`, NOT the speculative
    # vision/uia stack — that triple was a major source of 5-6 tool subsets on
    # simple window commands. The per-tool head now surfaces vision/gui when the
    # query is actually about the screen.
    if name in {"gui", "uia", "vision"}:
        return ["gui", "uia", "vision"]
    if name in {"window", "desktop_layout"}:
        return ["window"]
    if name in {"notification", "routine", "contacts", "notes_tasks", "local_calendar", "habit_tracker", "source_manager"}:
        return ["state"]
    if name == "printer_scanner":
        return ["dependency"]
    # ---- Phase C/D/F3 tools ----
    if name == "developer":
        return ["terminal", "filesystem", "verify"]
    if name == "device_settings":
        return ["state", "verify"]
    if name == "game_launcher":
        return ["app", "window", "verify"]
    if name == "media_edit":
        return ["filesystem", "dependency"]
    if name == "maintenance":
        return ["state", "verify"]
    if name == "watcher":
        return ["state"]
    if name == "job_manager":
        return ["state", "terminal"]
    if name == "network":
        return ["state"]
    if name == "data_analysis":
        return ["filesystem", "dependency"]
    if name == "fact_check":
        return ["knowledge", "web", "source_manager"]
    if name == "photo_library":
        return ["filesystem", "dependency"]
    if name == "container":
        return ["terminal", "dependency"]
    if name == "database":
        return ["filesystem"]
    if name == "creative_local":
        return ["filesystem", "dependency"]
    if name == "form_filler":
        return ["browser_real", "state", "safety"]
    if name == "peripheral":
        return ["state"]
    if name == "accessibility":
        return ["state"]
    if name == "study":
        return ["state"]
    if name == "smart_home":
        return ["state", "dependency"]
    if name == "document":
        return ["filesystem", "knowledge", "dependency"]
    return []


_PRIMARY_TOOLS = {
    # Strong domain anchors: keep these high when matched.
    "steam", "media", "browser_real", "browser", "web",
    "office", "document", "knowledge", "fact_check",
    "filesystem", "app", "window", "gui", "uia", "vision",
    "audio", "audio_device",
    "system", "terminal", "clipboard",
    "developer", "device_settings", "game_launcher", "media_edit",
    "maintenance", "network", "data_analysis", "container", "database",
    "photo_library", "creative_local", "form_filler", "peripheral",
    "accessibility", "study", "smart_home",
    "memory", "notification", "routine", "watcher", "job_manager",
    "contacts", "notes_tasks", "local_calendar", "habit_tracker",
    "local_search", "printer_scanner", "desktop_layout", "backup_sync",
    "source_manager", "email", "reminder",
    "registry", "env", "input", "download", "package",
}
_UTILITY_TOOLS = {"verify": 90, "state": 91, "dependency": 92, "safety": 99}


def _cap_tools(names: list[str], limit: int) -> list[str]:
    if len(names) <= limit:
        return names
    # Tier policy:
    # - Primary tools (those that matched a keyword or are a related dep) keep
    #   their original position (so earliest-mentioned wins).
    # - Utility tools (verify/state/dependency/safety) go to the back regardless.
    # - Anything not classified gets a mid-tier slot at 50.
    indexed = list(enumerate(names))
    def rank(pair: tuple[int, str]) -> tuple[int, int]:
        order, name = pair
        if name in _UTILITY_TOOLS:
            return (_UTILITY_TOOLS[name], order)
        if name in _PRIMARY_TOOLS:
            return (order, order)  # original mention order
        return (50, order)
    indexed.sort(key=rank)
    selected = {name for _, name in indexed[:limit]}
    return [name for name in names if name in selected]


def _dedupe(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# Colloquial abbreviations / shorthand the multilingual embedder can't map
# on its own ("vol" is not near "volumen" in embedding space). We EXPAND the
# shorthand to its full word BEFORE routing, so the query still routes by
# MEANING (universal) rather than via a brittle keyword→tool table. Each entry
# is a true synonym expansion, not a tool binding. Whole-word match only.
_ABBREV_EXPANSIONS: tuple[tuple[str, str], ...] = (
    (r"\bvol\b", "volumen"),
    (r"\bvolu\b", "volumen"),
    (r"\bporfa\b", "por favor"),
    (r"\bpls\b", "por favor"),
    (r"\bplis\b", "por favor"),
    (r"\bpc\b", "computadora"),
    (r"\bapp\b", "aplicacion"),
    (r"\bwsp\b", "whatsapp"),
    (r"\bwpp\b", "whatsapp"),
    (r"\bwtsp\b", "whatsapp"),
    (r"\bigu?\b", "instagram"),
    (r"\bfb\b", "facebook"),
    (r"\byt\b", "youtube"),
    (r"\bopera gx\b", "opera"),
    (r"\bg hub\b", "logitech g hub"),
    # Multilingual ACTION VERBS the keyword router only knows in ES/EN. We
    # normalize the verb to its Spanish equivalent so an Italian/French/German
    # command routes like the Spanish one ("apri"→"abre", "schliesse"→"cierra").
    # Live repro 2026-05-20: "apri la calcolatrice"/"ouvre la calculatrice" did
    # not pull `app`; "schliesse das Fenster" failed. The noun stays in its
    # language — only the verb is mapped, and the embedder handles the rest.
    (r"\bapri\b", "abre"),            # IT open
    (r"\bouvre\b", "abre"),           # FR open
    (r"\boeffne\b", "abre"),          # DE open (oe for ö)
    (r"\böffne\b", "abre"),      # DE öffne
    (r"\babrir\b", "abre"),           # ES infinitive → imperative form
    (r"\bchiudi\b", "cierra"),        # IT close
    (r"\bferme\b", "cierra"),         # FR close
    (r"\bschliesse\b", "cierra"),     # DE close (ss for ß)
    (r"\bschließe\b", "cierra"), # DE schließe
    (r"\bfechar\b", "cierra"),        # PT close (infinitive; "fecha" alone is
                                       # ES "date", so we only map the verb form)
)
_ABBREV_COMPILED = [(re.compile(p, re.IGNORECASE), r) for p, r in _ABBREV_EXPANSIONS]


def _expand_abbreviations(text: str) -> str:
    """Expand colloquial shorthand to full words so short/abbreviated queries
    route semantically ('baja el vol a 10' -> 'baja el volumen a 10'). This is
    universal text normalization, language-agnostic in effect: the expanded
    query is what a clear speaker would say, and the embedder routes that
    correctly. Does NOT bind any word to a tool."""
    out = text
    for pat, repl in _ABBREV_COMPILED:
        out = pat.sub(repl, out)
    return out


def _fold_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _short_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 32].rstrip() + " ...[mission text trimmed]"
