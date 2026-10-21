"""The model's doubt about its own decision, read from the decision call itself (token logprobs; no other pass).

System One, layer 0 (scripts/renew/system_one): on the 1,839 labelled real requests, this confidence told right decisions
from wrong ones with AUROC 0.902, and below 0.5 it held 145 of 309 wrong decisions while 1.9 % of the right ones fell
there; on decision2, AUROC 0.818. Only read and traced here: nothing decides on it yet.
"""
from __future__ import annotations

import math
from typing import Any

CALL = "<tool_call>"
NAME_OPEN = "<function="


def _p(logprob: float | None) -> float:
    return math.exp(logprob) if logprob is not None else 0.0


def read(reply: dict[str, Any] | None) -> dict[str, Any] | None:
    """Confidence of the decision in a chat reply with `logprobs`: for a call, p(open a call) × p(this tool's name); for
    words, 1 − p(open a call). Also the weakest name token's rivals (what else the model nearly called). None without
    logprobs."""
    try:
        content = (reply or {})["choices"][0]["logprobs"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not content:
        return None
    first = content[0]
    alternatives = {a["token"]: _p(a.get("logprob")) for a in first.get("top_logprobs") or []}
    p_call = _p(first.get("logprob")) if first.get("token") == CALL else alternatives.get(CALL, 0.0)
    starts, text = [], ""
    for token in content:
        starts.append(len(text))
        text += token.get("token", "")
    at = text.find(NAME_OPEN)
    if first.get("token") != CALL or at < 0:
        return {"confidence": round(1.0 - p_call, 4), "p_call": round(p_call, 4)}
    name_from = at + len(NAME_OPEN)
    name_to = text.find(">", name_from)
    name_to = len(text) if name_to < 0 else name_to
    name = [i for i, s in enumerate(starts) if s + len(content[i].get("token", "")) > name_from and s < name_to]
    p_name = math.prod(_p(content[i].get("logprob")) for i in name) if name else 0.0
    weakest = min(name, key=lambda i: content[i].get("logprob", 0.0)) if name else None
    rivals = ([(a["token"], round(_p(a.get("logprob")), 3)) for a in content[weakest].get("top_logprobs") or []][:4]
              if weakest is not None else [])
    return {"confidence": round(p_call * p_name, 4), "p_call": round(p_call, 4), "p_name": round(p_name, 4),
            "rivals": rivals}
