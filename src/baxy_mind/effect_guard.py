"""The semantic effect guard: the request text it classifies and the state its reply reduces to (its prompt is in
``llm_prompts``).
"""

from __future__ import annotations

from .effect_intent import _strip_request_envelope


def _guard_request_text(text: str) -> str:
    """The request the effect guard G classifies: its words without their envelope.

    Tanda-06b (2026-09-24): G read the turn's routing text («Cuál es…?») beside
    the selector, and the conversation presentation then read the same request
    with its envelope («¿Cuál es…?»): a second, serial G of 0.4–1.1 s on every
    such question before the reply could be published. The envelope (``¿``, «hola
    baxy,», «por favor», a closing «gracias») is not part of the request by the
    grammar every reader shares, so one reading serves every consumer of G.
    """

    return _strip_request_envelope(text).strip() or text


# Uso real 2026-09-23: one «external_read» mixed a public fact to look up with the
# person's own data and this PC's state, so nothing could tell «busca el tipo de
# cambio» from «qué grupos hay en mis contactos». Both still count as a complete
# effect; only a public lookup may become a web search (the line of 00_IDENTIDAD:
# information may come in, the person's content does not go out).
SEMANTIC_REQUEST_TYPES = (
    "stable_conversation",
    "public_lookup",
    "own_data_read",
    "environment_change",
    "incomplete_effect",
)


def derive_semantic_effect_state(raw: object) -> str:
    """Reduce a candidate-free guard response to a one-sided state.

    ``effect_count`` is authenticated separately from this state. It may detect
    a disagreement and force independent replanning, but it is never allowed
    to rewrite the primary operation list or cardinality. The guard may
    preserve or remove direct authority; it can never select an operation.
    """

    if not isinstance(raw, dict) or set(raw) != {
        "request_type",
        "effect_count",
    }:
        return "invalid"
    request_type = raw.get("request_type")
    effect_count = raw.get("effect_count")
    if request_type not in SEMANTIC_REQUEST_TYPES or effect_count not in {"zero", "one", "multiple"}:
        return "invalid"
    if request_type == "stable_conversation":
        return "no_effect"
    if request_type == "incomplete_effect":
        return "not_complete"
    return "complete"
