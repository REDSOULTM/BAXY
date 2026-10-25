"""The model's doubt about its own decision, read from the decision call itself (token logprobs; no other pass).

System One, layer 0 (scripts/renew/system_one): on the 1,839 labelled real requests, this confidence told right decisions
from wrong ones with AUROC 0.902, and below 0.5 it held 145 of 309 wrong decisions while 1.9 % of the right ones fell
there; on decision2, AUROC 0.818. Only read here; the mind decides on it (Mind._held): layer 0 (BAXY_S1_DOUBT), the
decision model's layer 2 (BAXY_S1_VETO) and the floor of a «sí» (CONFIRM_FLOOR).
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
    # Holdout v5 E023: the token that carries the end of «<function=» into the name («=input») had «=» alone as its main
    # rival, the same text cut otherwise, and that read as a doubt. A rival that only writes what is still the opening
    # chooses no name: the token is read among those that do.
    opened = {i: 1.0 - sum(_p(a.get("logprob")) for a in content[i].get("top_logprobs") or []
                           if a["token"] and a["token"] != content[i].get("token")
                           and text[starts[i]:name_from].startswith(a["token"]))
              for i in name if starts[i] < name_from}

    def p_of(i: int, logprob: float | None) -> float:
        return _p(logprob) / opened[i] if i in opened and opened[i] > 0 else _p(logprob)

    p_name = math.prod(p_of(i, content[i].get("logprob")) for i in name) if name else 0.0
    weakest = min(name, key=lambda i: p_of(i, content[i].get("logprob", 0.0))) if name else None
    # The token chosen is not its own rival (review 2026-10-22: it was the first, completed again for nothing).
    rivals = ([(a["token"], round(p_of(weakest, a.get("logprob")), 3))
               for a in content[weakest].get("top_logprobs") or []
               if a["token"] != content[weakest].get("token")
               and not (weakest in opened and text[starts[weakest]:name_from].startswith(a["token"]))][:4]
              if weakest is not None else [])
    return {"confidence": round(p_call * p_name, 4), "p_call": round(p_call, 4), "p_name": round(p_name, 4),
            "rivals": rivals, "written": text[:starts[weakest]] if weakest is not None else ""}
