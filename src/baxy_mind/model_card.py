"""MODX2: how the decision is sampled, whether the model reasons first and where its doubt holds a call, for the model
BAXY runs, read from what the model file declares of itself (gguf_shape.declared), never from code that names a model.

MOD2 (§5, point 3): the harness was tuned to its stock model (Qwen3.5-4B: temperature 0.2 with Qwen3's top_p 0.8 and
top_k 20, no reasoning, the doubt's 0.4), and another model got those numbers or none. Each entry of the table
(data/model_cards.v1.json) matches the keys a GGUF declares (general.architecture, general.size_label, …) and says what
its maker's card recommends for it, or what was measured better with BAXY, with its source: the first entry that
matches is the model's card. A person extends it with a file of their own (BAXY_MODEL_CARDS: a JSON list of entries, read
before the shipped ones). A model no entry matches, or one whose file is not read (a server reached by the translator),
keeps what the mind always sent (Card.decide empty: Mind._decide_sampling).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TABLE = Path(__file__).with_name("data") / "model_cards.v1.json"
# The sampling fields a card may set for the decision (llama-server's /v1/chat/completions names: tools/server/README.md
# at b11609).
SAMPLING = ("temperature", "top_p", "top_k", "min_p", "presence_penalty", "frequency_penalty", "repeat_penalty")


@dataclass(frozen=True)
class Card:
    """The card the model got: ``decide``, the decision's sampling (empty: the mind's own); ``thinking_budget``, the
    tokens it may reason before deciding (0: it does not); ``doubt``, the confidence under which its call is held
    (None: the mind's own threshold)."""

    name: str | None = None
    decide: dict[str, int | float] = field(default_factory=dict)
    thinking_budget: int = 0
    doubt: float | None = None
    source: str = ""


NONE = Card()


def _entries() -> list[dict[str, Any]]:
    own: list[dict[str, Any]] = []
    path = os.environ.get("BAXY_MODEL_CARDS", "").strip()
    if path:
        try:
            read = json.loads(Path(path).read_text(encoding="utf-8"))
            own = [e for e in (read.get("cards", []) if isinstance(read, dict) else read) if isinstance(e, dict)]
        except (OSError, ValueError):
            own = []
    shipped = json.loads(TABLE.read_text(encoding="utf-8"))["cards"]
    return [*own, *shipped]


def _fits(said: object, value: object) -> bool:
    """A declared value fits an entry's: equal, or, for an entry's text ending in «*», beginning with what precedes it
    (a family's name: «Llama-3*» fits «Llama-3.2-3B-Instruct»)."""
    if isinstance(value, str) and value.endswith("*"):
        return isinstance(said, str) and said.startswith(value[:-1])
    return said == value


def _matches(match: dict[str, Any], declared: dict[str, object]) -> bool:
    """Every key of ``match`` is declared with that value, or one of those values (a list)."""
    return bool(match) and all(any(_fits(declared.get(key), v) for v in (value if isinstance(value, list) else [value]))
                               for key, value in match.items())


def card_for(declared: dict[str, object]) -> Card:
    """The first entry whose ``match`` the declared keys fit; NONE when none does or nothing is declared."""
    if not declared:
        return NONE
    for entry in _entries():
        if not _matches(entry.get("match") or {}, declared):
            continue
        decide = {key: value for key, value in (entry.get("decide") or {}).items()
                  if key in SAMPLING and isinstance(value, (int, float)) and not isinstance(value, bool)}
        doubt = entry.get("doubt")
        return Card(name=str(entry.get("name") or ""), decide=decide,
                    thinking_budget=max(0, int(entry.get("thinking_budget") or 0)),
                    doubt=float(doubt) if isinstance(doubt, (int, float)) else None,
                    source=str(entry.get("source") or ""))
    return NONE
