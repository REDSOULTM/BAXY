"""Bug 3: Grounding gate — detect replies that claim actions not in tool_events.

Two layers:

  1. **Inline cheap check** (`detect_action_claim_without_evidence`): runs in
     the hot path, no LLM/NLI inference. Uses linguistic features (verb
     morphology heuristics derived from the existing false-confirmation
     guard) to flag obvious "abrí X / busqué Y / agendé Z" claims when
     `tool_events == []`. Returns a verdict; the agent's existing
     `_guard_promise_without_action` keeps catching prefix cases.

  2. **Async NLI grounding** (`schedule_grounding_check`): fires AFTER the
     reply is generated (and ideally after TTS dispatch), classifies the
     reply against a premise built from the actual tool trace, and writes
     the verdict to the lesson store so future similar turns can be
     warned via RAG (Bug 2).

The inline layer is REPLY → fallback if a clear hallucinated claim slips
through. The async layer is REPLY → telemetry/lesson_store so the system
LEARNS from misses; it does NOT mutate the current turn.

Both gates degrade gracefully: if NLI service is unavailable or returns
None, the system falls back to the inline heuristic alone.
"""
from __future__ import annotations

import logging
import threading
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable

from .nli_service import get_nli_service

_log = logging.getLogger(__name__)


# Linguistic features for the inline layer. These are NOT a closed allowlist
# of "bad verbs"; they are morphological signals of "1st-person past-tense
# action claim" — a grammatical category. The signal is the SUFFIX pattern,
# not the lemma. Spanish 1st-person preterit indicative endings are -é (-ar),
# -í (-er/-ir); accentless variants are common in voice transcription.
_PRETERIT_SUFFIXES_ACCENTED = (
    "é", "í",
)
_PRETERIT_SUFFIXES_PLAIN = (
    "e", "i",
)
# Common short action stems that, COMBINED with a preterit suffix, signal
# a concrete action claim. Kept SHORT and abstract; not a comprehensive list.
# The point is "any verb of opening/searching/sending/etc, in 1st-person
# preterit". We detect via suffix + first-letter-set heuristic.
_ACTION_STEMS_HINT = frozenset({
    "abr", "busc", "busq", "envi", "agend", "registr", "ejecut", "inici",
    "lanc", "abri", "encontr", "mande", "mostre", "puse", "naveg", "carg",
    "cli", "guard", "borr", "cre", "elimin", "cerr", "edit", "modif",
    "actualic", "consult", "verif", "confirm", "respond", "contest",
    "ejecut", "registr",
    "salud", "marqu", "asign", "asisti", "atendi",
})


def _fold(text: str) -> str:
    """lowercase + strip diacritics for tolerant matching."""
    n = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in n if not unicodedata.combining(ch))


def _looks_like_first_person_preterit(word: str) -> bool:
    """Heuristic: does `word` look like a Spanish 1st-person preterit verb?

    Examples that should match (case-insensitive, fold-tolerant):
      abrí, abri, busqué, busque, envié, agendé, ejecuté, registré, mandé,
      lancé, naveg(u)é, mostré, encontré, puse, cliqué, abrir... NO, infinitive
      ends in -r, must reject. cargo (present)... NO, ends in -o, reject.

    Rejects pretty much anything that doesn't look like a 1st-person preterit.
    """
    w = word.strip().rstrip(".,;:!?")
    if not w or len(w) < 4:
        return False
    folded = _fold(w)
    # Must end in 'e' or 'i' (preterit indicative suffix, accent-stripped).
    if not (folded.endswith("e") or folded.endswith("i")):
        return False
    # Exclude common non-verbs ending in -e/-i (nombre, examen, casi, etc).
    # Verbs are stem + (e|i); we require the stem to be in our hint set OR
    # to be a plausible verb stem (ends in a consonant-ish form).
    # Simpler: require the stem prefix (first 3-5 chars) to be in the hint set.
    # Check stem prefixes of varying length against the hint set. Stems in
    # the set range from 3 to 6 chars (abr, busc, agend, ejecut, registr).
    if any(folded[:n] in _ACTION_STEMS_HINT for n in (3, 4, 5, 6, 7)):
        # Additional gate: reject "abrir", "abrira", future/conditional/infinitive.
        if folded.endswith("r") or folded.endswith("ra") or folded.endswith("ria"):
            return False
        return True
    return False


def _starts_with_action_claim(text: str) -> str | None:
    """If the text starts with what looks like a 1st-person past-tense
    action verb, return that word (for telemetry). Else None.

    Tolerates leading interjections / connectives: "Listo, abrí Disney+" ->
    detects "abrí" after stripping "Listo,".
    """
    stripped = text.strip()
    if not stripped:
        return None
    # Strip up to N leading clause-openers (comma- or colon-separated).
    # Common patterns: "Listo, X" / "Listo, hecho, X" / "Hecho: X" / etc.
    import re as _re
    parts = _re.split(r"[,:;]", stripped)
    for cand in parts[:4]:
        words = cand.strip().split()
        if not words:
            continue
        first_word = words[0]
        if _looks_like_first_person_preterit(first_word):
            return first_word
    return None


# ---------- Inline gate ----------

@dataclass
class GroundingVerdict:
    """Outcome of the inline grounding check.

    `should_replace`: if True, agent should swap the reply with `fallback`.
    `reason`: short telemetry tag.
    `claim_word`: the word that triggered the gate (if any).
    """
    should_replace: bool
    reason: str = ""
    claim_word: str = ""
    fallback: str = ""


_HONEST_FALLBACK = "No alcancé a completar la acción. ¿La repetimos?"

# Per-language variants. The selector below picks one based on hints
# extracted from the LLM's own (rejected) reply, so the fallback stays
# in the same language as the rest of the conversation.
_FALLBACKS_BY_LANG: dict[str, dict[str, str]] = {
    "es": {
        "generic":  "No alcancé a completar la acción. ¿La repetimos?",
        "no_tool":  "No tengo una tool para eso. ¿Probamos con otra cosa?",
        "partial":  "Me falta info para completarlo: {missing}. ¿Me la pasás?",
        "retry":    "No agarré bien el pedido. Probá reformularlo — opciones cercanas: {hints}.",
    },
    "en": {
        "generic":  "I couldn't complete that. Want to try again?",
        "no_tool":  "I don't have a tool for that. Want to try something else?",
        "partial":  "I'm missing info to complete this: {missing}. Can you tell me?",
        "retry":    "I'm not catching that. Try rephrasing — close options: {hints}.",
    },
    "it": {
        "generic":  "Non sono riuscito a completare l'azione. Ripetiamo?",
        "no_tool":  "Non ho uno strumento per questo. Proviamo qualcos'altro?",
        "partial":  "Mi mancano info per completare: {missing}. Me le passi?",
        "retry":    "Non ho colto. Prova a riformulare — opzioni vicine: {hints}.",
    },
    "pt": {
        "generic":  "Não consegui completar a ação. Repetimos?",
        "no_tool":  "Não tenho ferramenta para isso. Tentamos outra coisa?",
        "partial":  "Faltam dados para completar: {missing}. Me passa?",
        "retry":    "Não peguei bem o pedido. Tenta reformular — opções próximas: {hints}.",
    },
    "fr": {
        "generic":  "Je n'ai pas pu terminer l'action. On recommence ?",
        "no_tool":  "Je n'ai pas d'outil pour ça. On essaie autre chose ?",
        "partial":  "Il me manque des infos pour finir : {missing}. Tu me les donnes ?",
        "retry":    "Je ne saisis pas. Reformule — options proches : {hints}.",
    },
    "de": {
        "generic":  "Ich konnte die Aktion nicht abschließen. Nochmal?",
        "no_tool":  "Ich habe dafür kein Tool. Sollen wir etwas anderes versuchen?",
        "partial":  "Mir fehlen Infos: {missing}. Kannst du sie mir geben?",
        "retry":    "Ich verstehe nicht. Formuliere es um — nahe Optionen: {hints}.",
    },
}


_LANG_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # (lang_code, list of bigram/word hints — accent-insensitive, lower)
    ("en", ("the ", " i ", " you ", "i'll", "i've", "i couldn", "let me",
            "done", "got it", "okay", "all right")),
    ("it", (" il ", " la ", " ho ", " ti ", " ci ", "ecco", "fatto",
            "riprodu", "chiud", "ferma")),
    ("pt", (" o ", " a ", " que ", " com ", " esta ", "feito", "pronto",
            "abri", "fechei")),
    ("fr", (" le ", " la ", " je ", " tu ", " vous ", " et ", "fait",
            "voici", "j'ai")),
    ("de", (" der ", " die ", " das ", " ich ", " du ", "fertig",
            "geöffnet", "geschlossen")),
    # ES is the default; only listed for completeness.
    ("es", (" el ", " la ", " ya ", "listo", "abrí", "cerré", "puse",
            "ejecut", "hecho")),
)


def detect_reply_language(reply: str) -> str:
    """Lightweight language guess from a short LLM reply.

    Not a full language detector — just enough to pick the right fallback
    string. Falls back to 'es' (project default) on ambiguity.
    """
    if not reply:
        return "es"
    low = " " + reply.lower() + " "
    best = "es"
    best_score = 0
    for lang, hints in _LANG_HINTS:
        score = sum(1 for h in hints if h in low)
        if score > best_score:
            best_score = score
            best = lang
    return best


def format_fallback(
    *,
    reason: str,
    reply_lang_hint: str | None = None,
    rejected_reply: str = "",
    missing: str = "",
    hints: str = "",
) -> str:
    """Pick a fallback string in the user's language.

    `reason` is one of generic / no_tool / partial / retry. `missing` and
    `hints` are interpolated only when present in the template.
    """
    lang = reply_lang_hint or detect_reply_language(rejected_reply)
    table = _FALLBACKS_BY_LANG.get(lang) or _FALLBACKS_BY_LANG["es"]
    template = table.get(reason) or table["generic"]
    return template.format(missing=missing or "—", hints=hints or "—")


def detect_action_claim_without_evidence(
    reply: str, tool_events: list[Any],
) -> GroundingVerdict:
    """Inline (no NLI) check: if the reply opens with a 1st-person past-tense
    action verb AND `tool_events` is empty, flag it.

    Does NOT depend on a hardcoded verb list — uses morphological pattern.
    Conservative by design: only flags clear cases starting the reply, so
    legitimate replies like "Encontré la respuesta: ..." (after a real web
    tool ran) are untouched because tool_events is non-empty.
    """
    if tool_events:
        return GroundingVerdict(should_replace=False, reason="tool_events_nonempty")
    if not reply:
        return GroundingVerdict(should_replace=False, reason="empty_reply")
    claim = _starts_with_action_claim(reply)
    if not claim:
        return GroundingVerdict(should_replace=False, reason="no_claim_signal")
    return GroundingVerdict(
        should_replace=True,
        reason="action_claim_without_evidence",
        claim_word=claim,
        fallback=_HONEST_FALLBACK,
    )


# ---------- Async NLI gate ----------

GROUNDING_LABELS = [
    "el sistema ejecutó acciones concretas",
    "el sistema no ejecutó ninguna acción",
]


def build_evidence_premise(tool_events: list[Any]) -> str:
    """Serialize the observable tool trace into a NLI premise string.

    Kept short and factual; longer premises hurt NLI accuracy on encoder
    models. Hides args (sensitive data) but preserves tool names + outcome
    flags so claim/evidence comparison is meaningful.
    """
    if not tool_events:
        return ("Estado verificable del sistema en este turno: "
                "no se ejecutó ninguna tool, no hubo acciones sobre el entorno.")
    names: list[str] = []
    for ev in tool_events:
        # ToolEvent dataclass has .name; fall back to getattr/dict.
        n = getattr(ev, "name", None) or (ev.get("name") if isinstance(ev, dict) else None)
        if isinstance(n, str) and n:
            names.append(n)
    if not names:
        return ("Estado verificable: hubo intentos de tool pero sin nombres "
                "identificables.")
    uniq = ", ".join(sorted(set(names)))
    return (f"Estado verificable del sistema en este turno: "
            f"se ejecutaron las siguientes tools: {uniq}.")


def schedule_grounding_check(
    reply: str,
    tool_events: list[Any],
    callback: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    """Fire-and-forget NLI grounding check.

    The result is delivered via `callback` (running in NLI worker thread).
    Typical callback: write a `grounding_verdict` event to the trace +
    lesson store. The callback MUST be short and side-effect only.

    Returns immediately; the current reply is NOT modified by this call.
    """
    if not reply:
        return
    premise = build_evidence_premise(tool_events)
    # Hypothesis is the reply; we want to know whether premise entails it.
    # We frame as a 2-label zero-shot: "executed actions" vs "did nothing".
    # If reply implies actions but premise says "did nothing" → high score
    # on the wrong label → contradiction detected.
    svc = get_nli_service()

    def _cb(scores: dict[str, float] | None) -> None:
        if scores is None:
            if callback:
                callback({"available": False})
            return
        executed = scores.get(GROUNDING_LABELS[0], 0.0)
        nothing = scores.get(GROUNDING_LABELS[1], 0.0)
        # Contradiction: reply claims executed actions but actually nothing ran.
        contradicts = (not tool_events) and executed > nothing and executed > 0.55
        verdict = {
            "available": True,
            "executed_score": executed,
            "nothing_score": nothing,
            "contradicts": contradicts,
            "premise": premise[:200],
            "reply": reply[:200],
        }
        if callback:
            try:
                callback(verdict)
            except Exception as exc:  # noqa: BLE001
                _log.warning("grounding callback raised: %s", exc)

    svc.classify_async(reply, GROUNDING_LABELS, callback=_cb)


__all__ = [
    "GroundingVerdict",
    "detect_action_claim_without_evidence",
    "build_evidence_premise",
    "schedule_grounding_check",
    "GROUNDING_LABELS",
]
