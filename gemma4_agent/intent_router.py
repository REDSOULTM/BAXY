"""Semantic intent classification — universal, multilingual, keyword-free.

Sprint 8 (2026-05-20): the keyword/regex router missed informational
questions ("quién es X", "who is X", "de qué trata X") because the
intent lives in the *wording*, not in any single keyword, and varies by
language. Measured info-recall over 367 real queries was 0.48.

Instead of more keywords (fragile, per-language), we classify the user's
INTENT semantically: compare the query embedding against two anchor
centroids — "is this asking for INFORMATION about the world?" vs "is
this asking to DO something on the computer?". The anchors are short
phrases in several languages; their mean is a robust centroid. This is a
2-class semantic classifier, not a 65-way tool match, so it stays sharp
even on short queries ("quién es batman") where matching against tool
descriptions is too noisy.

Reuses the already-loaded multilingual embedding model from
semantic_router (paraphrase-multilingual-MiniLM-L12-v2, 50+ languages),
so there's no extra model load.

Public API:
    classify_intent(text) -> IntentScores(info, action, margin)
    wants_knowledge(text) -> bool   # info intent with clear margin
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

# Anchor phrases per intent, in several languages. The MEAN of each
# group's embeddings is the centroid we compare against. More languages
# here = better coverage; these cover the romance/germanic/english core
# and the model generalizes to the rest via its multilingual training.
_INFO_ANCHORS = [
    # English — people, things, concepts, how/why
    "who is this person", "what is this thing", "tell me about this",
    "what is this movie or game about", "how did this happen",
    "general knowledge question about the world",
    "what is this concept", "what does this word mean",
    "how does this technology work", "explain this topic to me",
    # Spanish
    "quien es esta persona", "que es esto", "de que trata esto",
    "hablame sobre algo", "de que murio alguien",
    "informacion sobre una pelicula juego o persona",
    "que es este concepto", "como funciona esta tecnologia",
    "explicame este tema", "que significa esta palabra",
    # Portuguese / French / German / Italian
    "quem e essa pessoa", "qui est cette personne",
    "wer ist diese person", "chi e questa persona",
    "de quoi parle ce film", "worum geht es",
    "was bedeutet das", "che cosa significa",
]

_ACTION_ANCHORS = [
    # English
    "open an application", "close a window", "play music",
    "take a screenshot", "send a message", "install something",
    "do something on my computer", "control the pc",
    # Spanish
    "abre una aplicacion", "cierra una ventana", "pon musica",
    "manda un mensaje", "instala algo", "saca una captura de pantalla",
    # Portuguese / French / German / Italian
    "abrir um aplicativo", "ouvrir une application",
    "eine anwendung offnen", "apri unapplicazione",
    "envoyer un message", "eine nachricht senden",
]

# Chitchat / contentless utterances. Critical third class: short
# acknowledgements, greetings and filler ("jajaja", "nada", "ok", "oye",
# "que?") embed close to the info centroid by accident (they're not
# action-like) and would otherwise be misread as informational and pull
# a web lookup. An explicit chitchat centroid lets us require info to
# beat chitchat too, so only genuine questions about the world qualify.
_CHITCHAT_ANCHORS = [
    # English
    "hello", "hi", "thanks", "ok", "yeah", "lol", "haha", "umm", "hmm",
    "never mind", "i dont understand", "wait", "sorry", "bye",
    # Spanish
    "hola", "gracias", "si", "no", "bueno", "dale", "aja", "oye", "ya",
    "nada", "que tal", "como estas", "no entiendo", "repite", "espera",
    "perdon", "adios", "chau", "listo", "jaja",
    # Portuguese / French / German / Italian
    "obrigado", "merci", "danke", "grazie", "ciao", "salut",
]

# Questions about the ASSISTANT ITSELF or its policy ("quién eres", "qué
# puedes hacer", "cuál es tu prioridad", "qué?"). These are interrogative
# but the answer comes from the agent's own identity/system prompt, NOT a
# web lookup — so they must not pull web/knowledge. A dedicated centroid
# separates them from genuine world questions, which the chitchat/info
# margins alone can't (they sit close to info).
_SELF_ANCHORS = [
    # English
    "who are you", "what are you", "what can you do", "what is your name",
    "what is your purpose", "what is your priority", "are you an ai",
    "do you have feelings", "what?", "what do you mean",
    # Spanish
    "quien eres", "que eres", "que puedes hacer", "como te llamas",
    "cual es tu proposito", "cual es tu prioridad", "eres una ia",
    "tienes sentimientos", "que?", "que quieres decir", "quien sos",
    # Portuguese / French / German / Italian
    "quem es voce", "qui es tu", "wer bist du", "chi sei",
    "que peux tu faire", "was kannst du",
]

# wants_knowledge fires only when INFO is the dominant class — it must
# beat BOTH action and chitchat by a margin. Tuned on the full historical
# corpus (863 queries): genuine world questions clear both margins;
# smalltalk loses to chitchat; commands lose to action. No absolute-score
# cutoff (that dropped low-signal-but-real queries like "what is quantum
# computing"); the relative margins do the work.
_VS_ACTION_MARGIN = float(os.environ.get("GEMMA4_INTENT_VS_ACTION", "0.05"))
_VS_CHITCHAT_MARGIN = float(os.environ.get("GEMMA4_INTENT_VS_CHITCHAT", "0.00"))


@dataclass(frozen=True)
class IntentScores:
    info: float
    action: float
    chitchat: float = 0.0
    selfref: float = 0.0

    @property
    def margin(self) -> float:
        """Info margin over the strongest competing class."""
        return self.info - max(self.action, self.chitchat, self.selfref)


class _Centroids:
    info: Any = None
    action: Any = None
    chitchat: Any = None
    selfref: Any = None
    ready: bool = False


_C = _Centroids()


def _ensure_centroids() -> bool:
    if _C.ready:
        return _C.info is not None
    try:
        from . import semantic_router as sr
        if not sr._ensure_loaded():
            _C.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors: list[str]) -> Any:
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _C.info = _centroid(_INFO_ANCHORS)
        _C.action = _centroid(_ACTION_ANCHORS)
        _C.chitchat = _centroid(_CHITCHAT_ANCHORS)
        _C.selfref = _centroid(_SELF_ANCHORS)
        _C.ready = True
        return True
    except Exception:
        _C.ready = True
        return False


def classify_intent(text: str) -> IntentScores | None:
    """Return IntentScores or None if the embedding model is unavailable."""
    if not text or not text.strip():
        return None
    if not _ensure_centroids() or _C.info is None:
        return None
    try:
        from . import semantic_router as sr
        import numpy as np
        qe = sr._STATE.model.encode([text], normalize_embeddings=True)[0]
        qe = np.asarray(qe, dtype="float32")
        return IntentScores(
            info=float(qe @ _C.info),
            action=float(qe @ _C.action),
            chitchat=float(qe @ _C.chitchat),
            selfref=float(qe @ _C.selfref),
        )
    except Exception:
        return None


def wants_knowledge(text: str) -> bool:
    """True when the query is an informational question about the WORLD
    (any language): info intent must be the dominant class, beating
    action, chitchat AND self-reference. This keeps web/knowledge out of:
      - smalltalk ("jajaja", "nada")             → chitchat wins
      - PC commands ("abre Steam")               → action wins
      - questions about the agent ("quién eres")  → selfref wins
    while still firing for "quién es X", "what is X about", "de qué murió
    X" in any language. Used by the planner so the LLM can look things up
    even when no keyword fired."""
    s = classify_intent(text)
    if s is None:
        return False
    return (
        (s.info - s.action) >= _VS_ACTION_MARGIN
        and (s.info - s.chitchat) >= _VS_CHITCHAT_MARGIN
        and s.info >= s.selfref
    )
