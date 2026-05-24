"""Post-reply structural validators.

These run after the LLM emits its turn's final reply. If a
structural anti-pattern is detected, the agent injects a
corrective system message into self.history so the NEXT turn's
LLM sees both its previous mistake and the correction note in
the same context window — the deferred-correction path
(Gemma4Agent has no _regen_reply method, building one is out of
scope for this hotfix).

The validators NEVER match user text — only the shape of the
LLM's own reply and the structural tool_call activity this turn.

Hotfix I 2026-05-17.
"""
from __future__ import annotations

import re
from typing import Any


# 'Listo' is the Spanish marker the fast_action prompt teaches
# the LLM to use as a POST-TOOL ack template. The structural
# anti-pattern is "ack template emitted on a turn where no tool
# ran" — the model defaulted to the template even though it
# shouldn't have. We detect the specific phrase the prompt
# teaches, NOT a generic ack across all languages.
_LISTO_PATTERN = re.compile(
    r"^\s*listo(\b|[,.!])",
    re.IGNORECASE,
)


def _result_of(call: Any) -> dict[str, Any]:
    """Read .result from a ToolEvent or a dict — tests use dicts,
    production code uses dataclasses."""
    if isinstance(call, dict):
        return call.get("result") or {}
    r = getattr(call, "result", None)
    return r if isinstance(r, dict) else {}


def _is_successful_call(call: Any) -> bool:
    """Mirror of agent._is_unverified_result inverted; duplicated
    here so reply_validator can stay decoupled from agent.py."""
    r = _result_of(call)
    if r.get("ok") is False:
        return False
    if r.get("verified") is False:
        return False
    status = str(r.get("status") or "").casefold()
    if status in {"failed", "needs_verification", "attempted", "needs_confirmation"}:
        return False
    return True


def is_listo_on_no_tool_turn(
    reply_text: str,
    tool_calls_this_turn: list[Any],
) -> bool:
    """True iff the reply starts with 'Listo' AND no tool ran
    successfully this turn.

    'Listo' is the template the fast_action prompt teaches for
    POST-TOOL acks. Emitting it without a tool is the anti-pattern
    Bug B caught. The fix in B was prompt-level; this is the
    structural backstop.
    """
    if not reply_text or not _LISTO_PATTERN.match(reply_text):
        return False
    successful = [c for c in tool_calls_this_turn if _is_successful_call(c)]
    return not successful


LISTO_REGEN_HINT = (
    "Your previous reply started with 'Listo' but no tool ran "
    "in this turn. 'Listo' is reserved for post-tool acks. "
    "Rewrite your reply naturally — for social acks like a "
    "thank-you, use 'de nada', 'no hay de qué', or the equivalent "
    "in the user's language."
)


# ---------------------------------------------------------------------------
# Anti-unverified-claim (guarda estructural, candidato Tier-1 de la auditoría
# Carter OS). Detecta cuando el reply AFIRMA que una acción/estado externo
# ocurrió ("ya lo abrí", "the window is open", "el volumen quedó en 50") SIN que
# este turno haya corrido una tool VERIFICADA que sustente esa afirmación.
#
# CUMPLE las reglas del proyecto:
#  - NO lista de keywords por idioma: la detección de "afirma efecto" es por
#    SIMILITUD SEMÁNTICA contra anclas multi-idioma (mismo encoder del router).
#  - Mide la FORMA + la actividad de tools del turno, nunca inventa contenido.
#  - FALLBACK SEGURO: sin encoder o margen ambiguo -> NO flaggea (jamás molesta
#    en un reply legítimo). Conservador a propósito.
#  - Determinista permitido (CLAUDE.md): embeddings + guarda estructural.
# ---------------------------------------------------------------------------

# Margen mínimo (claim - conv) para considerar que el reply AFIRMA un efecto.
# Medido (2026-05-23, 9 casos / 4 idiomas): afirmaciones reales caen en +0.25..
# +0.39; preguntas/conversación en <=+0.16. 0.20 separa limpio con margen.
_CLAIM_MARGIN = 0.20

_CLAIM_ANCHORS = [
    # es
    "ya abrí Spotify", "la ventana está abierta", "el volumen quedó en 50",
    "listo, lo cerré", "ya está reproduciendo", "el archivo fue creado",
    # en
    "Spotify is now open", "the file was created", "done, I opened it",
    "I set the volume to 50", "the window is now maximized",
    # pt / fr / de / it
    "pronto, abri o app", "a janela está aberta", "c'est ouvert",
    "fertig, ich habe es geöffnet", "fatto, l'ho aperto",
]
_CONV_ANCHORS = [
    # es
    "¿qué querés que haga?", "no estoy seguro", "¿a cuál te referís?",
    "hola, en qué ayudo", "no tengo esa función", "de nada", "no puedo hacer eso",
    # en
    "what do you want me to do", "I am not sure", "which one did you mean",
    "I don't have that tool",
    # pt / fr / de
    "o que você quer", "je ne suis pas sûr", "ich bin nicht sicher",
]


class _ClaimCentroids:
    __slots__ = ("ready", "claim", "conv")

    def __init__(self) -> None:
        self.ready = False
        self.claim = None
        self.conv = None


_CC = _ClaimCentroids()


def _ensure_claim_centroids() -> bool:
    if _CC.ready:
        return _CC.claim is not None
    try:
        from . import semantic_router as sr
        if not sr._ensure_loaded():
            _CC.ready = True
            return False
        import numpy as np
        model = sr._STATE.model

        def _centroid(anchors):
            e = model.encode(anchors, normalize_embeddings=True).mean(0)
            return np.asarray(e / (np.linalg.norm(e) or 1.0), dtype="float32")

        _CC.claim = _centroid(_CLAIM_ANCHORS)
        _CC.conv = _centroid(_CONV_ANCHORS)
        _CC.ready = True
        return True
    except Exception:
        _CC.ready = True
        return False


def _reply_asserts_effect(reply_text: str) -> bool:
    """True si el reply AFIRMA semánticamente que un efecto externo ocurrió.
    False si no hay encoder (fallback seguro) o si es conversacional/pregunta."""
    txt = (reply_text or "").strip()
    if len(txt) < 4:
        return False
    if not _ensure_claim_centroids() or _CC.claim is None:
        return False  # sin encoder -> no flaggear
    try:
        from . import semantic_router as sr
        import numpy as np
        q = sr.embed(txt)
        if q is None:
            q = sr._STATE.model.encode([txt], normalize_embeddings=True)[0]
        q = np.asarray(q, dtype="float32")
        return (float(q @ _CC.claim) - float(q @ _CC.conv)) >= _CLAIM_MARGIN
    except Exception:
        return False


def is_unverified_claim(reply_text: str, tool_calls_this_turn: list[Any]) -> bool:
    """True iff el reply AFIRMA un efecto externo PERO ninguna tool verificada
    corrió este turno para sustentarlo. Anti-alucinación de estado.

    Estructural: combina la FORMA del reply (afirma efecto, por embeddings) con
    la actividad real de tools (¿hubo una call exitosa?). Si hubo tool exitosa,
    la afirmación está sustentada -> NO flaggea. Conservador."""
    successful = [c for c in tool_calls_this_turn if _is_successful_call(c)]
    if successful:
        return False  # hubo efecto real -> la afirmación está OK
    return _reply_asserts_effect(reply_text)


UNVERIFIED_CLAIM_REGEN_HINT = (
    "Your previous reply asserted that an action or state happened "
    "(e.g. 'it's open', 'volume is set') but NO tool ran successfully "
    "this turn to make that true. Do NOT claim a side effect you did "
    "not perform. Either call the right tool, or say honestly that you "
    "did not do it / are not sure — in the user's language."
)
