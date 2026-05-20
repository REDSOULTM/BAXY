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

# Decision is driven by the MARGIN (info − action), which separates the
# two classes cleanly on the real corpus: informational queries score
# margin ≥ ~0.08 (multilingual, incl. abstract concepts), PC actions
# score margin ≤ ~0.02 (usually negative). 0.05 sits in the gap with a
# safety band on both sides — robust without an absolute-score cutoff
# that would drop low-signal-but-clearly-info queries like
# "what is quantum computing" (info 0.28, action 0.13, margin 0.15).
_INFO_MARGIN = float(os.environ.get("GEMMA4_INTENT_INFO_MARGIN", "0.05"))
# Low absolute floor: only rejects utterances with almost no info signal
# at all. The margin does the real work; this just guards against noise.
_INFO_FLOOR = float(os.environ.get("GEMMA4_INTENT_INFO_FLOOR", "0.20"))


@dataclass(frozen=True)
class IntentScores:
    info: float
    action: float

    @property
    def margin(self) -> float:
        return self.info - self.action


class _Centroids:
    info: Any = None
    action: Any = None
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
        ie = model.encode(_INFO_ANCHORS, normalize_embeddings=True).mean(0)
        ae = model.encode(_ACTION_ANCHORS, normalize_embeddings=True).mean(0)
        ie = ie / (np.linalg.norm(ie) or 1.0)
        ae = ae / (np.linalg.norm(ae) or 1.0)
        _C.info = np.asarray(ie, dtype="float32")
        _C.action = np.asarray(ae, dtype="float32")
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
        )
    except Exception:
        return None


def wants_knowledge(text: str) -> bool:
    """True when the query is an informational question about the world
    (any language) with a clear margin over action intent. Used by the
    planner to ensure web/knowledge tools are in the subset even when no
    keyword fired and even if an entity name (a game, a person) also
    pulls action tools."""
    s = classify_intent(text)
    if s is None:
        return False
    return s.info >= _INFO_FLOOR and s.margin >= _INFO_MARGIN
