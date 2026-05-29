"""Bug 3: Grounding gate — detect replies that claim actions not in tool_events.

Inline cheap check (`detect_action_claim_without_evidence`): runs in the
hot path, no LLM/NLI inference. Uses linguistic features (verb
morphology heuristics derived from the existing false-confirmation
guard) to flag obvious "abrí X / busqué Y / agendé Z" claims when
`tool_events == []`. Returns a verdict; the agent's existing
`_guard_promise_without_action` keeps catching prefix cases.

The async NLI grounding layer (`schedule_grounding_check`) was removed
in Sprint 3a — its cache hit rate over 5 days of use was 3.2 %, below
the 20 % keep/kill threshold from `08_findings.md §2.10`.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any


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
}


# Sprint 3a: tables trimmed from 6 langs to es+en. PT/FR/IT/DE branches
# were never observed in 5 days of traces and the CORE_PROMPT commits
# the agent to Spanish output by default.
_LANG_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # (lang_code, list of bigram/word hints — accent-insensitive, lower)
    ("en", ("the ", " i ", " you ", "i'll", "i've", "i couldn", "let me",
            "done", "got it", "okay", "all right")),
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


__all__ = [
    "GroundingVerdict",
    "detect_action_claim_without_evidence",
    "detect_reply_language",
    "format_fallback",
]
