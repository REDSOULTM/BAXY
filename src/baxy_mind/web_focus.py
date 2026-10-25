"""Goal h-web (2026-10-25): what the 4B model reads of a web page, behind BAXY_WEB_FOCUS=1 (unset: the page as today).

Measured in the e2e traces (renew_v1/runs c3-*-e2e and ho6-*-e2e-e2e, 47 runs): web.fetch results were 30 % of every
result's characters (208 pages of ~4,500 characters, all completed), and the model paged a long page 8 to 14 times
looking for one line (V6E008/V6E014 «el río más largo de Europa»: 4-10 pages of a Wikipedia list, 14 context_shrunk;
V5E008 «en qué año se inauguró el Metro de Santiago»: 14 pages, 2 context_shrunk; E022 RFC 2324: 5 pages each run).

With the switch on, a web.fetch the model wrote without a size reads a wider part of the page (WINDOW characters), and
the model is shown, of that part, the lead and the paragraphs that share the most words with what the person asked
(and the web.search queries of the turn), in the page's order, up to CAP characters, with a note of how much was left
out and the call that reads it whole. A web.fetch that names maximumCharacters is the model asking for the text as it
is: it is shown whole. Every other field of the result (title, requestedUrl, finalUrl, offsets, error, verification)
stays as the App gave it."""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from typing import Any

WINDOW = 8_000
CAP = 2_000
LEAD = 400

_STOP = set("""
a al algo algun alguna alguno ante asi aun cada como con cual cuales cuyo de del desde donde el ella ellas ello ellos
en entre era es esa ese eso esta este esto fue ha hay la las le les lo los mas me mi mis muy no nos o para pero por que
quien se segun ser si sin sobre su sus te tu tus un una uno unos unas y ya yo
busca buscame buscar busques internet web pagina paginas lee leeme leer dime decir dices di sabes saber quiero quisiera
puedes podrias favor porfa hola oye baxy dame mira mirar revisa consulta google wikipedia sitio link enlace url
the of and or to in on at for with from by is are was were be it this that what which who when how does do did
""".split())

_NUMERIC = re.compile(r"\b(?:ano|anos|cuando|cuanto|cuantos|cuantas|fecha|year|when|how many|how much|codigo|numero|"
                      r"cifra|precio|mide|edad|siglo|dia)\b")
_REFERENCE = re.compile(r"\s?\[ ?(?:\d{1,3}|nota \d{1,3}|cita requerida) ?\]")
_BOILER = {"ir al contenido", "saltar al contenido", "ver galeria", "editar", "[ editar ]", "compartir", "aceptar",
           "rechazar", "leer mas", "ver mas", "volver arriba", "menu", "buscar", "cerrar", "skip to content",
           "share", "accept", "read more"}


def on() -> bool:
    return os.environ.get("BAXY_WEB_FOCUS", "").strip() == "1"


def widen(arguments: dict[str, Any]) -> dict[str, Any]:
    """The arguments sent to the App: a web.fetch without a size reads WINDOW characters."""
    if on() and "maximumCharacters" not in arguments:
        return {**arguments, "maximumCharacters": WINDOW}
    return arguments


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).casefold()
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", _fold(text))
    return {w[:4] if not w.isdigit() else w for w in words if w not in _STOP and (len(w) >= 3 or w.isdigit())}


def _blocks(text: str) -> list[str]:
    """The text's lines without boilerplate, joined into blocks of about a paragraph (a table's cells go together)."""
    lines = [_REFERENCE.sub("", line).strip() for line in text.split("\n")]
    counts: dict[str, int] = {}
    for line in lines:
        counts[line] = counts.get(line, 0) + 1
    kept = [line for line in lines if line and _fold(line) not in _BOILER and not (counts[line] >= 3 and len(line) < 40)]
    blocks: list[str] = []
    current = ""
    for line in kept:
        current = f"{current}\n{line}" if current else line
        if len(current) >= 160:
            blocks.append(current)
            current = ""
    if current:
        blocks.append(current)
    return blocks


def select(text: str, queries: list[str], cap: int = CAP, lead: bool = True) -> tuple[str, int]:
    """The lead and the blocks most related to the queries, in the page's order, up to ``cap`` characters, «…» where
    text was left out; and how many characters of ``text`` are not shown. Text within the cap comes back as it is."""
    if len(text) <= cap:
        return text, 0
    blocks = _blocks(text)
    wanted = set().union(*(_terms(q) for q in queries)) if queries else set()
    numeric = any(_NUMERIC.search(_fold(q)) for q in queries)
    present = [_terms(b) for b in blocks]
    count = len(blocks)
    scores = []
    for block, terms in zip(blocks, present):
        score = sum(math.log((count + 1) / (0.5 + sum(t in p for p in present))) for t in wanted & terms)
        if score and numeric and re.search(r"\d", block):
            score += 0.5
        scores.append(score)
    chosen: set[int] = set()
    used = 0
    if lead and blocks:
        chosen.add(0)
        blocks[0] = blocks[0] if len(blocks[0]) <= LEAD else blocks[0][:LEAD].rsplit(" ", 1)[0] + " …"
        used = len(blocks[0])
    for index in sorted(range(count), key=lambda i: (-scores[i], i)):
        if scores[index] <= 0:
            break
        if index in chosen or used + len(blocks[index]) + 2 > cap:
            continue
        chosen.add(index)
        used += len(blocks[index]) + 2
    if len(chosen) <= (1 if lead else 0):
        # Nothing shares a word with the question: the start of the text, as it comes.
        shown = text[:cap].rsplit("\n", 1)[0] if "\n" in text[:cap] else text[:cap]
        return shown, len(text) - len(shown)
    # The room left goes to what follows each chosen block (a heading's paragraph, a sentence's end), then to the
    # blocks nearest to them.
    best = sorted((i for i in chosen if scores[i] > 0), key=lambda i: (-scores[i], i))
    for distance in (1, -1, 2, -2):
        for index in best:
            near = index + distance
            if 0 <= near < count and near not in chosen and used + len(blocks[near]) + 2 <= cap:
                chosen.add(near)
                used += len(blocks[near]) + 2
    parts: list[str] = []
    last = -1
    for index in sorted(chosen):
        if index != last + 1:
            parts.append("…")
        parts.append(blocks[index])
        last = index
    if last != count - 1:
        parts.append("…")
    shown = "\n".join(parts)
    return shown, max(0, len(text) - sum(len(blocks[i]) for i in chosen))


def focus(observation: str, queries: list[str], arguments: dict[str, Any]) -> str:
    """A web.fetch result as the model reads it (see the module). Not a completed page with text, or the model asked a
    size (maximumCharacters), or the switch is off: the result as it came."""
    if not on() or "maximumCharacters" in arguments:
        return observation
    try:
        result = json.loads(observation)
    except json.JSONDecodeError:
        return observation
    page = result.get("observed") if isinstance(result, dict) else None
    text = page.get("text") if isinstance(page, dict) else None
    if not isinstance(text, str) or len(text) <= CAP:
        return observation
    start = page.get("offset") if isinstance(page.get("offset"), int) else 0
    shown, left_out = select(text, queries, lead=start == 0)
    if not left_out:
        return observation
    end = start + len(text)
    total = page.get("totalCharacters")
    url = page.get("finalUrl") or page.get("requestedUrl") or arguments.get("url") or ""
    of_total = f" de {total}" if isinstance(total, int) else ""
    note = (f"\n[recortado: {left_out} caracteres más de esta parte (caracteres {start + 1}–{end}{of_total}) sin "
            f"mostrar; se muestran los párrafos más relacionados con lo pedido. Para leer esta parte entera: web_fetch "
            f"con url {url}, offset {start} y maximumCharacters {len(text)}.")
    if page.get("hasMore") is True and isinstance(page.get("nextOffset"), int):
        note += f" Para seguir con el resto de la página: offset {page['nextOffset']}."
    note += "]"
    page = {**page, "text": shown + note, "readInPart": True, "shownCharacters": len(shown),
            "omittedCharacters": left_out}
    return json.dumps({**result, "observed": page}, ensure_ascii=False, separators=(",", ":"))
