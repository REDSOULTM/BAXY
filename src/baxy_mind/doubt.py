"""The model's doubt about its own decision, read from the decision call itself (token logprobs; no other pass).

System One, layer 0 (scripts/renew/system_one): on the 1,839 labelled real requests, this confidence told right decisions
from wrong ones with AUROC 0.902, and below 0.5 it held 145 of 309 wrong decisions while 1.9 % of the right ones fell
there; on decision2, AUROC 0.818. Only read and traced here: nothing decides on it yet.
"""
from __future__ import annotations

import math
import re
from typing import Any

CALL = "<tool_call>"
NAME_OPEN = "<function="
PARAMETER = re.compile(r"<parameter=([^>]+)>")
PARAMETER_CLOSE = "</parameter>"


def _p(logprob: float | None) -> float:
    return math.exp(logprob) if logprob is not None else 0.0


def read(reply: dict[str, Any] | None) -> dict[str, Any] | None:
    """Confidence of the decision in a chat reply with `logprobs`: for a call, p(open a call) × p(this tool's name); for
    words, 1 − p(open a call). Also the weakest name token's rivals (what else the model nearly called) and, by argument,
    the probability of its value's least sure token (values). None without logprobs."""
    try:
        content = (reply or {})["choices"][0]["logprobs"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if not content:
        return None
    # Review 2026-10-22: words written before the call («Claro,» then <tool_call>) are not the decision; the call is
    # measured from its own opening token, and a call whose opening is not in the logprobs gets no judgment.
    opening = next((i for i, token in enumerate(content) if token.get("token") == CALL), None)
    if opening is None and ((reply or {})["choices"][0].get("message") or {}).get("tool_calls"):
        return None
    first = content[opening or 0]
    alternatives = {a["token"]: _p(a.get("logprob")) for a in first.get("top_logprobs") or []}
    p_call = _p(first.get("logprob")) if first.get("token") == CALL else alternatives.get(CALL, 0.0)
    starts, text = [], ""
    for token in content:
        starts.append(len(text))
        text += token.get("token", "")
    at = text.find(NAME_OPEN, starts[opening or 0])
    if opening is None or at < 0:
        return {"confidence": round(1.0 - p_call, 4), "p_call": round(p_call, 4)}
    name_from = at + len(NAME_OPEN)
    name_to = text.find(">", name_from)
    name_to = len(text) if name_to < 0 else name_to
    name = [i for i, s in enumerate(starts) if s + len(content[i].get("token", "")) > name_from and s < name_to]
    p_name = math.prod(_p(content[i].get("logprob")) for i in name) if name else 0.0
    weakest = min(name, key=lambda i: content[i].get("logprob", 0.0)) if name else None
    # The token chosen is not its own rival (review 2026-10-22: it was the first, completed again for nothing).
    rivals = ([(a["token"], round(_p(a.get("logprob")), 3)) for a in content[weakest].get("top_logprobs") or []
               if a["token"] != content[weakest].get("token")][:4] if weakest is not None else [])
    values = {}
    for parameter in PARAMETER.finditer(text, name_to):
        end = text.find(PARAMETER_CLOSE, parameter.end())
        value = text[parameter.end():len(text) if end < 0 else end]
        begin = parameter.end() + len(value) - len(value.lstrip())
        finish = begin + len(value.strip())
        shown = [_p(t.get("logprob")) for t, s in zip(content, starts)
                 if s < finish and s + len(t.get("token", "")) > begin and t.get("token", "").strip()]
        if shown:
            values[parameter.group(1).strip()] = round(min(shown), 4)
    return {"confidence": round(p_call * p_name, 4), "p_call": round(p_call, 4), "p_name": round(p_name, 4),
            "rivals": rivals, "written": text[:starts[weakest]] if weakest is not None else "", "values": values}
