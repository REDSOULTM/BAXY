"""Rule of «answer_check» about a datum the final answer bends (encargo A5): what the answer tells about a result that
the result itself says it does not bring. Only the form is compared (the words of a search the result says it did not
match, against the answer's statements); nothing here writes a reply, chooses a tool or decides what the person meant: a
finding is a fact for the note the mind gives the model (mind.CHECK_NOTE), and the model writes again.

Sources of the method: faithfulness work separates an *extrinsic* addition (something the source never says) from an
*intrinsic* distortion (the source says another thing) (Maynez et al. 2020, arXiv 2005.00661; Ji et al. 2023, ACM
Computing Surveys 55(12), arXiv 2202.03629); verifying a claim against its evidence before saying it is what
Chain-of-Verification (Dhuliawala et al. 2023, arXiv 2309.11495) and attribution-and-revision (RARR, Gao et al. 2023,
arXiv 2210.08726) do with the model itself, which is what the note asks for. «Tool Receipts» (arXiv 2603.10060) is the
origin of the check this rule belongs to.

- ``unmatched``: a result that says, in a field named «…MatchesQuery», that what it did is not what was asked (a video
  whose title lacks words of the search), while the answer attributes to it those words (the artist of a title that
  did not name one). Not when the statement says it is not sure or denies.

Measured and left out (encargo A5 and diag-6f20, documentacion/APLAZADOS.md): ``unsourced``, a capitalised name or a
number of a statement that no result and nothing said had (the entity check of Nan et al. 2021, arXiv 2102.09130); in
the bank it gave 12 notes, 9 false (the VM's «Settings» against «Configuración», a word of a proper name), none right,
and one turned a right answer wrong. Comparing every word of a clause with a sentence of a result flagged faithful
paraphrases in 11 of 20 faithful answers.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

# The sentence says itself that it is not sure of what it tells.
_UNSURE = re.compile(r"\b(?:no (?:estoy|estaba) segur|no se si|no puedo (?:confirmar|asegurar)|no (?:esta|queda) "
                     r"confirmad|sin confirmar|no (?:lo )?(?:pude|puedo) (?:comprobar|verificar|confirmar)|"
                     r"parece|al parecer|quiza|tal vez|puede que|podria ser|no necesariamente|supongo)\b")


def fold(text: str) -> str:
    """Lower case without accents, one character for each (positions in it are positions in ``text``)."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower() if c.strip() else " " for c in text)


def _parsed(receipt: dict[str, Any]) -> Any:
    try:
        return json.loads(receipt.get("observation") or "")
    except (json.JSONDecodeError, TypeError):
        return None


def _quote(sentence: str, words: int = 22) -> str:
    cut = sentence.split()
    return " ".join(cut[:words]) + ("…" if len(cut) > words else "")


def unmatched(answer: str, statements: list[tuple[int, int]], receipts: list[dict[str, Any]]) -> list[dict]:
    """Rule ``unmatched``: see the module."""
    folded = fold(answer)
    for receipt in receipts:
        if not receipt.get("completed"):
            continue
        observed = _parsed(receipt)
        observed = observed.get("observed") if isinstance(observed, dict) and isinstance(observed.get("observed"), dict) \
            else observed
        if not isinstance(observed, dict):
            continue
        off = [k for k, v in observed.items() if k.endswith("MatchesQuery") and v is False]
        title = observed.get("title") or observed.get("requestedTitle")
        query = observed.get("query")
        if not off or not isinstance(title, str) or not isinstance(query, str):
            continue
        in_title = set(re.findall(r"[a-zñü0-9]+", fold(title)))
        lacking = [w for w in dict.fromkeys(re.findall(r"[a-zñü0-9]+", fold(query))) if len(w) >= 3 and w not in in_title]
        if not lacking:
            continue
        for start, end in statements:
            statement = folded[start:end]
            if _UNSURE.search(statement) or re.search(r"\bno\b", statement):
                continue
            said = [w for w in lacking if re.search(rf"\b{re.escape(w)}\b", statement)]
            if said:
                return [{"rule": "unmatched", "said": _quote(answer[start:end]),
                         "fact": f"{receipt.get('tool') or receipt.get('op')} dice {off[0]}: false, el título que sonó es "
                                 f"«{title}» y no trae «{' '.join(lacking)}» de lo que se buscó; que eso sea lo que sonó no "
                                 "está confirmado"}]
    return []
