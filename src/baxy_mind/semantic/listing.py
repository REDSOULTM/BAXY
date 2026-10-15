"""A ranked listing asked for: «un top 3 películas de suspenso», «las 5 mejores series», «a list of the 10 best games».

Uso real 2026-10-07 («Podrias buscarme en google un top 3 peliculas de suspenso del 2026» → one film, three times): no
reader knew that several things were asked, so the search took an article about one work as the answer and the
writer told it as if it were the top. ``listing_asked`` gives how many (None when no number is said) and the class of
thing listed; the search carries them as ``limit`` and ``listing`` and the writer as ``askedCount``. The words are data
(``data/listing_words.v1.json``).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable, NamedTuple

from .grammar import _fold, correction_words, spoken_cardinal


class Listing(NamedTuple):
    count: int | None  # how many were asked; None when the listing says no number («los mejores restaurantes»)
    kind: str  # the class of thing listed, as said and folded («peliculas»)


@lru_cache(maxsize=1)
def _words() -> dict:
    path = Path(__file__).resolve().parent.parent / "data" / "listing_words.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _alternation(words: object) -> str:
    return "|".join(re.escape(str(word)) for word in sorted(words, key=len, reverse=True))


@lru_cache(maxsize=1)
def _patterns() -> tuple[re.Pattern[str], ...]:
    words = _words()
    number = r"(?P<n>\d{1,2}|[a-z]+)"
    ranking = _alternation(words["ranking_heads"])
    best = _alternation(words["best_words"])
    most = _alternation(words["most_words"])
    lists = _alternation(words["list_nouns"])
    rest = r"(?P<rest>[a-z0-9ñ ]*)"
    return (
        # «top 3 peliculas», «un top tres de series», «ranking 10 de juegos»
        re.compile(rf"\b(?:{ranking})[\s-]*{number}\b\s*{rest}"),
        # «las 5 mejores series», «the 10 best games», «3 top movies»
        re.compile(rf"\b{number}\s+(?:{best})\b\s*{rest}"),
        # «mejores 3 juegos», «best five movies»
        re.compile(rf"\b(?:{best})\s+{number}\b\s*{rest}"),
        # «5 canciones mas escuchadas», «3 most watched shows»
        re.compile(rf"\b{number}\s+(?P<kind>[a-zñ]{{3,}})\s+(?:{most})\s+[a-zñ]{{3,}}"),
        # «una lista de 4 libros», «a list of the 10 best games», «una lista de las mejores series»
        # (a number or a ranking word is said: «la lista de tareas» is a list the person keeps, not a ranking)
        re.compile(
            rf"\b(?:{lists}|{ranking})\s+(?:de|of)\s+(?:(?:los|las|the)\s+)?"
            rf"(?:{number}\s+(?:(?:{best})\s+)?|(?:{best})\s+){rest}"
        ),
        # «los mejores restaurantes», «the best laptops»: a plural ranking with no number
        re.compile(rf"\b(?:los|las|the)\s+(?:{best})\s+{rest}"),
    )


def _count(said: str | None) -> int | None | bool:
    """The number said, None when nothing was said, False when the word is not a number in range."""

    if said is None:
        return None
    value = int(said) if said.isdigit() else spoken_cardinal(said)
    if value is None or not 1 <= value <= int(_words()["largest"]):
        return False
    return value


def _kind(rest: str) -> str | None:
    words = _words()
    skipped = set(words["articles"]) | set(words["best_words"]) | set(words["most_words"])
    own = set(words["own_markers"])
    for token in rest.split():
        if token in own:
            return None  # «top 3 de mi lista de tareas»: what is the person's own is not a public listing
        if token in skipped or token.isdigit():
            continue
        return token if len(token) >= 3 else None
    return ""


def listing_asked(text: str) -> Listing | None:
    """How many of what the message asks to be listed, or None when it asks no ranked listing.

    «Podrias buscarme en google un top 3 peliculas de suspenso del 2026» → (3, «peliculas»); «los mejores
    restaurantes de Lima» → (None, «restaurantes»); «¿quién ganó el Óscar 2026?», «dame 3 recetas de pan» (no ranking
    said) and «top 3 de mi lista de tareas» (the person's own) → None."""

    folded = " ".join(re.sub(r"[^\w\s-]", " ", _fold(str(text or ""))).split())
    for pattern in _patterns():
        for found in pattern.finditer(folded):
            groups = found.groupdict()
            count = _count(groups.get("n"))
            if count is False:
                continue
            kind = groups.get("kind") or _kind(groups.get("rest") or "")
            if kind is None or (not kind and count is None):
                continue
            # «sí, pero quiero un top 3»: a number with no class is the count of what the conversation asked (kind «»).
            return Listing(count, kind)
    return None


class Enumeration(NamedTuple):
    count: int  # how many were asked
    kind: str  # the class of thing listed, as said and folded («paises»)
    open: bool  # an open class (ideas, recipes, names): there are always more, so how many exist is never checked


@lru_cache(maxsize=1)
def _enumeration_pattern() -> re.Pattern[str]:
    words = _words()
    verbs = _alternation(words["enumeration_verbs"])
    best = _alternation(words["best_words"])
    return re.compile(
        rf"\b(?:{verbs})\s+(?:(?:me|nos|us)\s+)?(?:(?:unos|unas|los|las|the|some|about)\s+)?"
        rf"(?P<n>\d{{1,2}}|[a-z]+)\s+(?:(?:{best})\s+)?(?P<kind>[a-zñ]{{3,}})"
    )


def enumeration_asked(text: str) -> Enumeration | None:
    """How many of what the message asks to be listed, by a counted list or a ranking.

    Uso real v3 tanda 2 «dame 4 paises de sudamerica que no tengan salida al mar» → (4, «paises», closed): the reply
    named four, two of them with a coast. «dame 5 ideas de cena…» → (5, «ideas», open); «give me 3 stretches…» → (3,
    «stretches», open); «top 3 peliculas» → (3, «peliculas», open). «dame 5 minutos», «dame un segundo» and «los
    mejores restaurantes» (no number) → None."""

    words = _words()
    ranked = listing_asked(text)
    if ranked is not None and ranked.count is not None and ranked.kind:
        return Enumeration(ranked.count, ranked.kind, ranked.kind in set(words["open_kinds"]))
    folded = " ".join(re.sub(r"[^\w\s-]", " ", _fold(str(text or ""))).split())
    for found in _enumeration_pattern().finditer(folded):
        count = _count(found.group("n"))
        kind = found.group("kind")
        # «dame 5 minutos»: a span of time or money is no list; «dame 1 idea» is one thing, not a list.
        if type(count) is not int or count < 2 or kind in set(words["not_listed_kinds"]):
            continue
        return Enumeration(count, kind, kind in set(words["open_kinds"]))
    return None


# Review 2 r19 (2026-10-09): «**1. Juego**: cooperativo, ligero y gratis.» is item 1 written in bold; the bold that opens
# the line is no reason to read its description as the list. Review 3 r19 (2026-10-09): nor is the bold that closes
# the number («**1.** Among Us: social, rápido y gratis.»), and a numbered heading («### 1. Tortilla» with its
# ingredients bulleted under it) is a marker of the outermost list, at the column of its line.
_NUMBERED_ITEM = re.compile(
    r"(?:^|(?<=\s))(?:#{1,6}[ 	]+)?(?:\*\*|__)?(\d{1,2})[.)](?:\*\*|__)?\s+(?=\S)", re.MULTILINE
)
_BULLET_ITEM = re.compile(r"^(?P<indent>[ \t]*)[-•*–]\s+(?=\S)", re.MULTILINE)


class _Series:
    """One numbered series being read: the column of its markers, its items, and whether it is a sublist."""

    def __init__(self, column: int, item: str, nested: bool) -> None:
        self.column = column
        self.items = [item]
        self.nested = nested
        self.has_nested = False


def _column(text: str, position: int) -> int:
    return position - (text.rfind("\n", 0, position) + 1)


def _marker_items(text: str, markers: list[re.Match[str]]) -> list[str]:
    """Each marker's item as written: up to the end of its line or the next marker on that line."""

    items: list[str] = []
    for index, found in enumerate(markers):
        line_end = text.find("\n", found.end())
        end = len(text) if line_end < 0 else line_end
        if index + 1 < len(markers) and markers[index + 1].start() < end:
            end = markers[index + 1].start()
        items.append(text[found.end(): end].strip())
    return items


def _item_shape(item: str) -> tuple[bool, bool]:
    """How an item is written: as a bold name, and as a heading followed by a colon («**Tortilla**: …»)."""

    return item.startswith(("**", "__")), re.match(r"[^:\n]{1,80}:(?:\s|$)", item.replace("**", "")) is not None


def _first_level_series(text: str) -> list[_Series]:
    """The first-level numbered series of an answer (its column and items), or None when it has none of two or more.

    Review r19 (2026-10-09): «Aquí tienes 3 recetas:» with three numbered recipes and numbered steps under each is
    three, not the last recipe's steps. A «1.» inside a series opens a sublist; the outer series resuming («2.» after
    the steps) closes it as a sublist, and so does a deeper indent or an earlier sibling sublist. A series the outer
    one never resumes after, at its own column, is a list of its own («Ingredientes: 1… Pasos: 1… 3»): the longest
    counts."""

    markers = list(_NUMBERED_ITEM.finditer(text))
    items = _marker_items(text, markers)
    stack: list[_Series] = []
    every: list[_Series] = []
    for found, item in zip(markers, items):
        number, column = int(found.group(1)), _column(text, found.start())
        if number == 1:
            while stack and column < stack[-1].column:
                stack.pop()
            parent = stack[-1] if stack else None
            series = _Series(column, item, parent is not None and (column > parent.column or parent.has_nested))
            stack.append(series)
            every.append(series)
            continue
        candidates = [index for index, series in enumerate(stack) if len(series.items) + 1 == number]
        if not candidates:
            continue
        # The series this number continues: the nearest column, then the one whose items it looks like («**Arroz**:
        # …» continues the recipes, «Hierve.» the steps), then the innermost.
        chosen = min(
            candidates,
            key=lambda index: (
                abs(stack[index].column - column), _item_shape(stack[index].items[0]) != _item_shape(item), -index,
            ),
        )
        for inner in stack[chosen + 1:]:
            inner.nested = True
        if len(stack) > chosen + 1:
            stack[chosen].has_nested = True
        del stack[chosen + 1:]
        stack[chosen].items.append(item)
    return [series for series in every if not series.nested]


def _top_numbered(text: str) -> tuple[int, tuple[str, ...]] | None:
    """The first-level numbered series of an answer (its column and items), or None when it has none of two or more;
    of several, the longest (``_first_level_series``)."""

    top = [series for series in _first_level_series(text) if len(series.items) >= 2]
    if not top:
        return None
    best = max(top, key=lambda series: len(series.items))
    return best.column, tuple(best.items)


def _top_level_lines(text: str) -> tuple[str, ...]:
    """The first-level items of an answer's numbered or bulleted list, each line as written; empty when it has none
    of two or more. The one counter of ``items_listed`` and ``listed_items``: a sublist (numbered steps under each
    recipe, bullets under a numbered item) is part of its item, never more items."""

    numbered = _top_numbered(text)
    bullets = [
        (len(found.group("indent")), text[found.end():].split("\n", 1)[0].strip())
        for found in _BULLET_ITEM.finditer(text)
    ]
    outer = min((column for column, _ in bullets), default=None)
    top_bullets = tuple(line for column, line in bullets if column == outer)
    if len(top_bullets) >= 2 and (numbered is None or outer is not None and outer < numbered[0]):
        return top_bullets
    if numbered is not None:
        return numbered[1]
    return top_bullets if len(top_bullets) >= 2 else ()


_QUOTED_ITEM = re.compile(r"[\"“«]([^\"“”«»\n]{1,80})[\"”»]")
# What sets two quoted items of one inline list apart: a comma, «y/e/o/and/or», or both.
_QUOTED_JOIN = re.compile(r"\s*,?\s*(?:(?:y|e|o|u|and|or)\s+)?")


def _quoted_run(text: str) -> int:
    """The longest run of quoted items set apart only by commas or a conjunction («"A", "B" y "C"» → 3)."""

    run = best = 0
    previous_end: int | None = None
    for found in _QUOTED_ITEM.finditer(text):
        joined = previous_end is not None and _QUOTED_JOIN.fullmatch(text[previous_end: found.start()]) is not None
        run = run + 1 if joined else 1
        best = max(best, run)
        previous_end = found.end()
    return best


def _discourse(segment: str) -> bool:
    """A segment of a sentence that is only a discourse word or an interjection («Claro», «¿Bueno», «Well»)."""

    folded = " ".join(re.sub(r"[^\w\s]", " ", _fold(segment.replace("'", "").replace("’", ""))).split())
    return folded in set(_words()["inline_discourse_words"])


def _inline_items(sentence: str) -> tuple[str, ...]:
    """The items of one sentence written as an inline list («A, B y C»: a comma or more, then a conjunction that
    joins the last one), each as said; empty when the sentence is no such list. The first item begins after the
    sentence's lead-in («Puedes probar con …», «Las causas fueron …»); what follows the last one after a comma («, que
    son ligeros») is a clause, not an item."""

    words = _words()
    conjunctions = set(words["inline_conjunctions"])
    leads = set(words["inline_lead_words"])
    longest = int(words["inline_item_words"])
    segments = [segment.strip() for segment in sentence.split(",")]
    # Review r19 (2026-10-09): «Claro, puedes probar con Among Us, …» — what opens a sentence as a discourse word
    # («claro», «bueno, mira», «well, honestly») is no item; the list's lead-in is read after it.
    while segments and _discourse(segments[0]):
        segments = segments[1:]

    def joined(item: str) -> bool:
        return any(_fold(token) in conjunctions for token in item.split())

    for last in range(1, len(segments)):
        tokens = segments[last].split()
        joins = [index for index, token in enumerate(tokens) if _fold(token) in conjunctions]
        if not joins or joins[0] == 0 or joins[0] == len(tokens) - 1:
            continue
        before, after = " ".join(tokens[: joins[0]]), " ".join(tokens[joins[0] + 1:])
        middle = segments[1:last]
        items = [*middle, before, re.sub(r"[.!?;:…]+$", "", after).strip()]
        if not all(item and len(item.split()) <= longest and not _discourse(item) for item in items):
            return ()
        # Review 3 r19 (2026-10-09): a list written inline is introduced — by a lead-in («Puedes probar con …», «Las
        # causas fueron …») or a colon. «Tercero, cuida la cafeína, el alcohol y las cenas pesadas» and «Third, cut
        # caffeine, alcohol and heavy dinners» are one step of the answer, «Chile, Perú y Ecuador sí tienen mar» a
        # remark after it; none is the list.
        introduced = ":" in segments[0]
        opening = segments[0].split(":")[-1].split()
        lead = max((index for index, token in enumerate(opening) if _fold(token) in leads), default=-1)
        first = " ".join(opening[lead + 1:])
        if not (introduced or lead >= 0) or not first or len(first.split()) > longest:
            return ()
        # «Puedes probar pasta o sushi, ambas son rápidas, baratas y ricas»: an item before the last that is joined
        # already («pasta o sushi») closed its list; what follows it is a clause.
        if joined(first) or any(joined(item) for item in middle):
            return ()
        return (first, *items)
    return ()


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def without_figure_phrase(item: str, figure: str) -> str:
    """The item without the phrase of time or place that carries ``figure`` («…en Sarajevo en 1914» → «…en
    Sarajevo»; «La Triple Alianza (1882)» → «La Triple Alianza»); the item as it was when the figure is not in such a
    phrase («Murieron 17 millones»: the figure is what it says). Ronda 24 (r23 t3-c17 t1).

    Revisión 1: the phrase goes only when it is whole, the figure followed by the end, a mark or a word that joins
    (``repeat_separators``), never by a word of its own («de 17 millones de personas», «El año 1914 trajo…»: the
    figure is what the item says); and when what is left after the item's marker does not open with a word («2., el
    archiduque…» from «2. En 1914, el archiduque…»), the item is left as it was (it goes whole with its figure)."""

    words = _words()
    if not figure or figure not in item:
        return item
    ranges = set(words["figure_range_heads"])
    heads = _alternation(word for word in words["figure_phrase_heads"] if word not in ranges).replace("\\ ", r"\s+")
    range_heads = _alternation(ranges)
    range_joins = _alternation(words["figure_range_joins"])
    articles = _alternation(words["figure_phrase_articles"])
    nouns = _alternation(words["figure_phrase_nouns"])
    joins = _alternation(words["repeat_separators"])
    day = r"(?:\d{1,2}\s+(?:de\s+)?[^\W\d_]+\s+(?:de\s+)?)?"
    whole = rf"(?=[ \t]*(?:[.,;:!?)\]…]|$)|[ \t]+(?:{joins})\b)"
    opening = rf"(?:(?:{articles})\s+)?(?:(?:{nouns})\s+(?:de\s+)?)?{day}"
    # Revisión 4 de la ronda 24 («…en Europa entre 1914 y 1918» → «…en Europa y 1918»): a phrase between two terms
    # («entre 1914 y 1918», «between 1914 and 1918») goes whole with its second term, a figure; otherwise it is left as
    # it was (the item then goes whole with its figure).
    phrase = re.compile(
        rf"(?:\s*,)?\s+(?:{range_heads})\s+{opening}{re.escape(figure)}(?![\w]|[.,]\d)"
        rf"[ \t]+(?:{range_joins})[ \t]+(?:(?:{articles})\s+)?{day}\d{{1,4}}(?![\w]|[.,]\d){whole}"
        rf"|(?:\s*,)?\s+(?:{heads})\s+{opening}{re.escape(figure)}(?![\w]|[.,]\d){whole}"
        rf"|\s*\((?:[^()]{{0,30}}?\s)?{re.escape(figure)}(?:\s[^()]{{0,30}}?)?\)",
        re.IGNORECASE | re.MULTILINE,
    )
    kept = phrase.sub("", item)
    if kept == item:
        return item
    kept = re.sub(r"[ \t]+([.,;:!?])", r"\1", kept)
    kept = re.sub(r"[ \t]{2,}", " ", kept).rstrip()
    # What the item says opens with a word (or a mark that opens one: «**», «"», «¿»), after its marker if it has one.
    if re.match(r"\s*(?:(?:\d{1,2}[.)]|[-•*–])\s+)?[*_«\"“'¿¡(]*[^\W\d_]", kept) is None:
        return item
    return kept


def listed_items(answer: str) -> tuple[str, ...]:
    """The items an answer lists, as written: numbered («1. **Pollo al curry**: …» → «Pollo al curry»), as bullets, or
    inline in one sentence («Bolivia, Paraguay, Perú y Uruguay»); empty when it lists fewer than two (three inline).
    Inline lists are read here for what was asked by number (``items_listed(..., counted=True)``)."""

    text = str(answer or "")
    lines = _top_level_lines(text)
    if lines:
        # «**Pollo al curry rápido**: Corta el pollo…» names «Pollo al curry rápido».
        return tuple(
            re.split(r"\s*[:—–](?:\s+|$)|\s+-\s+", line.replace("**", "").replace("__", ""), maxsplit=1)[0].strip()
            for line in lines
        )
    # Review 2 r19: an answer that numbers or bullets what it lists is read by its markers; a sentence inside one of
    # its items («cooperativo, ligero y gratis») is that item's description, never the list.
    if _NUMBERED_ITEM.search(text) or _BULLET_ITEM.search(text):
        return ()
    for sentence in _SENTENCE_SPLIT.split(text):
        items = _inline_items(sentence)
        if items:
            return items
    return ()


def counts_listed(answer: str) -> tuple[int, ...]:
    """Every count an answer's list can be read as: its items (``listed_items``) and, when it numbers them in several
    first-level series, all of them together. Review 2 r19 (2026-10-09): five games written as «**Online:** 1. 2. 3.»
    and «**En la misma PC:** 1. 2.» are five, though ``items_listed`` counts the longest series («Ingredientes: 1. 2.
    Pasos: 1. 2. 3.» is three). Empty when it lists fewer than two."""

    text = str(answer or "")
    readings = [len(listed_items(text))] if len(listed_items(text)) >= 2 else []
    series = _first_level_series(text)
    if len(series) >= 2:
        readings.append(sum(len(each.items) for each in series))
    return tuple(dict.fromkeys(readings))


def repeated_items(items: Iterable[str]) -> tuple[str, ...]:
    """The items said twice in one list, compared folded and without their articles («el nacionalismo» and
    «nacionalismo»); empty when every item is said once."""

    articles = set(_words()["articles"])
    seen: dict[str, str] = {}
    repeated: list[str] = []
    for item in items:
        key = " ".join(token for token in re.sub(r"[^\w\s]", " ", _fold(item)).split() if token not in articles)
        if key and key in seen:
            repeated.append(item)
        seen.setdefault(key, item)
    return tuple(repeated)


def items_listed(answer: str, *, counted: bool = False) -> int | None:
    """How many items an answer lists, numbered («1. …», «2) …»), as bullets or as quoted titles in one line; None when
    it lists fewer than two (three quoted). ``counted``: a number was asked (``enumeration_asked`` of this turn or the
    one before), and an inline list («A, B, C y D», three or more) is counted too (ronda 19, r17 t3-c03 «…Among Us,
    Garry's Mod, Portal 2 o Minecraft» for five asked).

    Uso real v3 tanda 2: BAXY's «1. **Pollo al curry rápido**… 5. **Pollo al horno…**» is five; the recovery that
    composed the next turn without it said «Solo te proporcioné dos recetas». Audit 2026-10-08 (t4-c02-2): «Te
    recomiendo "El Aleph", "La supermanera" y "El fin de los tiempos"» is three, each quoted; «me tiraste una lista
    enorme» got «te di más de lo que pediste». A list written inline without quotes («A, B y C») is not counted: its
    items cannot be told from a clause."""

    text = str(answer or "")
    top = _top_level_lines(text)
    if top:
        return len(top)
    # Two quoted names are as often a choice or a pair said in a sentence («¿Abro "Spotify" o "Steam"?», «Abrí «Notas» y
    # «Calculadora»», review 2026-10-08 r2): quoted, a list is three or more.
    quoted = _quoted_run(text)
    if quoted >= 3:
        return quoted
    if counted:
        inline = listed_items(text)
        if len(inline) >= 3:
            return len(inline)
    return None


def empty_items(answer: str) -> int:
    """Revisión 2 de la ronda 22 (bloqueante 3): how many first-level items of an answer's numbered or bulleted list say
    nothing («1. 2. El bloqueo naval alemán. 3. …» numbers four and tells three: item 1 is empty); 0 when every item
    says something, or the answer lists nothing."""

    return sum(1 for line in _top_level_lines(str(answer or "")) if not re.search(r"\w", line))


def opening_series(answer: str) -> int | None:
    """Ronda 22 (t4-c02 «Bestiario, Rayuela y Octaedro son libros de Julio Cortázar.» for «dame 3 libros…»): how many
    things a one-sentence answer names as the subject it opens with («A, B y C son …»), which ``listed_items`` leaves out
    (a remark like «Chile, Perú y Ecuador sí tienen mar» reads the same). Read only against a count the person disputes
    (``semantic.dialogue.correction_already_holds``), never as a list told. None when the answer is more than one
    sentence, or does not open with short items set apart by commas and joined by a conjunction."""

    text = " ".join(str(answer or "").split())
    if not text or len([part for part in _SENTENCE_SPLIT.split(text) if part.strip()]) != 1:
        return None
    words = _words()
    conjunctions = set(words["inline_conjunctions"])
    longest = int(words["inline_item_words"])
    segments = [segment.strip() for segment in text.split(",")]
    if len(segments) < 2:
        return None
    for segment in segments[:-1]:
        tokens = segment.split()
        if not tokens or len(tokens) > longest or any(_fold(token) in conjunctions for token in tokens) or _discourse(
            segment
        ):
            return None
    tokens = segments[-1].split()
    joins = [index for index, token in enumerate(tokens) if _fold(token) in conjunctions]
    if not joins or joins[0] == 0 or joins[0] > longest or joins[0] == len(tokens) - 1:
        return None
    # Revisión 1 de la ronda 22 («Lo siento, no encontré libros y no puedo seguir.» read as three): the series names
    # its items only when a copula says what they are right after the last one («… y Octaedro son libros …»;
    # data: series_copulas), and no item is a negation (series_negations).
    copulas, negations = set(words["series_copulas"]), set(words["series_negations"])
    tail = [_fold(token).strip(".,;:!?¡¿") for token in tokens[joins[0] + 1:]]
    copula = next((index for index, token in enumerate(tail) if token in copulas), None)
    if copula is None or copula == 0 or copula > longest:
        return None
    items = [_fold(token).strip(".,;:!?¡¿") for segment in segments[:-1] for token in segment.split()]
    items += [_fold(token).strip(".,;:!?¡¿") for token in tokens[: joins[0]]] + tail[:copula]
    if set(items) & negations:
        return None
    return len(segments) + 1


def counts_said(text: str) -> tuple[int, ...]:
    """Every number from two to the largest listing the message says, in figures or words, in order («no te pedí 4,
    me tiraste como siete» → (4, 7)); empty when it says none («me tiraste menos», «la segunda»)."""

    found: list[int] = []
    for token in re.sub(r"[^\w\s]", " ", _fold(str(text or ""))).split():
        count = _count(token) if token.isdigit() or token.isalpha() else None
        if type(count) is int and count >= 2:
            found.append(count)
    return tuple(found)


def given_counts(text: str) -> tuple[int, ...]:
    """The numbers a message says BAXY gave (``dispute_given`` then a number within three words: «me tiraste como 7»,
    «you gave me 5» → 7, 5), in order; empty when it says none. Review 3 r19 (2026-10-09): every other number a
    dispute says is what the person asked or what the list should have had («quería 10», «son 6»)."""

    words = _words()
    padded = " " + " ".join(re.sub(r"[^\w\s]", " ", _fold(str(text or "").replace("'", "").replace("’", ""))).split()) + " "
    found: dict[int, int] = {}
    for claim in words["dispute_given"]:
        for match in re.finditer(rf"(?<= ){re.escape(claim)}(?= )", padded):
            # «me diste 5» and «diste 5» name one number: it is keyed by where it is said.
            start = len(padded[: match.end()].split())
            for index, token in enumerate(padded[match.end():].split()[:3]):
                value = _count(token) if token.isdigit() or token.isalpha() else None
                if type(value) is int and value >= 2:
                    found[start + index] = value
                    break
    return tuple(value for _, value in sorted(found.items()))


def argues_the_count(reply: object, text: str) -> bool:
    """Revisión 2 de la ronda 24 (r23 t3-c17 t2 «no te pedi 4 po, me tiraste como 7, solo 4» → «Te di 3 elementos, no 7
    ni 4.»): a reply to a count dispute (``count_disputed``) that lists nothing and refuses a count the person asks
    (every number said but what they say BAXY gave, ``given_counts``) right after a refusal word («no 4», «ni 4», «no
    son 4»; data: correction_words.v1.json, refusals) argues with the person instead of giving what was asked.
    Contracaso: «Ya te di 4, los que pediste» says the count asked as given (the settled dispute); a reply that lists
    the items, or a message that disputes nothing («gracias, las 3 están buenas»), is never judged."""

    if not count_disputed(text) or counts_listed(str(reply or "")):
        return False
    asked = set(counts_said(text)) - set(given_counts(text))
    if not asked:
        return False
    refusals = {_fold(str(word)) for word in correction_words()["refusals"]}
    tokens = re.sub(r"[^\w\s]", " ", _fold(str(reply or ""))).split()
    for index, token in enumerate(tokens):
        if token not in refusals:
            continue
        for following in tokens[index + 1 : index + 3]:
            value = _count(following) if following.isdigit() or following.isalpha() else None
            if type(value) is int and value in asked:
                return True
    return False


def count_disputed(text: str, kind: str = "") -> bool:
    """Whether the message disputes how many things BAXY's last list had: it says what the person asked or denies
    the count, then a number («no, te pedí 5 che», «I asked for five», «eso no son 5»), or says what BAXY gave, then a
    number or more/fewer («me tiraste menos», «me tiraste como 7», «you gave me fewer»). Review r19 (2026-10-09): a
    number said about the list is no dispute by itself — «explícame la 5», «el 5 me gusta», «son 5 o 4?», «las 5
    están buenas» — and a message that asks for other or more items («dame otras 5», «quiero 5 más», «another 5») is
    a new request. Review 2 r19 (2026-10-09): what disputes the count says nothing else of the list
    (``_says_only_the_count``); «te pedí 5 vegetarianas», «me diste 5 con pollo y yo quería con carne», «no son 5
    personas, son 6» or «te dije 5 minutos» claim a condition or something else, not the count. ``kind``: the class
    the list was asked by («ideas»), which a dispute may repeat («te pedí 5 ideas»)."""

    words = _words()
    folded = " ".join(
        re.sub(r"[^\w\s]", " ", _fold(str(text or "").replace("'", "").replace("’", ""))).split()
    )
    tokens = folded.split()
    more = set(words["relative_more"])
    relative = more | set(words["relative_fewer"])

    def counted(token: str) -> bool:
        value = _count(token) if token.isdigit() or token.isalpha() else None
        return type(value) is int and value >= 2

    if any(token in set(words["dispute_new_request"]) for token in tokens) or any(
        counted(token) and following in more for token, following in zip(tokens, tokens[1:])
    ):
        return False
    padded = f" {folded} "
    for key, accepts_relative in (("dispute_said", False), ("dispute_given", True)):
        for claim in words[key]:
            for found in re.finditer(rf"(?<= ){re.escape(claim)}(?= )", padded):
                # «te pedí 5», «me tiraste como 7», «I asked you for five»: the claim's number within three words.
                following = padded[found.end():].split()[:3]
                if any(counted(token) or accepts_relative and token in relative for token in following):
                    return _says_only_the_count(padded, kind, counted)
    return False


def _says_only_the_count(padded: str, kind: str, counted) -> bool:
    """Whether a message that claims a count (``count_disputed``) says nothing but the count: once its claims
    («te pedí», «me tiraste», «de lo que pediste») are set apart, every word left is a count, more or fewer, a word
    that only carries the claim (``dispute_filler``: «che», «po», «solo», «como», «than»), a discourse word, or the
    class asked (``kind``). A word left over is a condition or another thing said («vegetarianas», «con carne»,
    «personas», «minutos», «que no tarden más de media hora»): the person corrects what the list was, not its count."""

    words = _words()
    claims = (*words["dispute_said"], *words["dispute_given"], *(_fold(said) for said in words["relative_asked"]))
    for claim in sorted(claims, key=len, reverse=True):
        padded = re.sub(rf"(?<= ){re.escape(claim)}(?= )", " ", padded)
    allowed = {
        *words["dispute_filler"],
        *words["relative_more"],
        *words["relative_fewer"],
        *(said for said in words["inline_discourse_words"] if " " not in said),
    }
    kind = _fold(str(kind or "")).strip()
    if kind:
        allowed |= {kind, kind.rstrip("s"), kind + "s", kind + "es"}
    return all(token in allowed or counted(token) for token in padded.split())


def count_said(text: str) -> int | None:
    """The first number from two to the largest listing the message says (``counts_said``); None when it says none."""

    said = counts_said(text)
    return said[0] if said else None


@lru_cache(maxsize=1)
def _given_pattern() -> re.Pattern[str]:
    words = _words()
    spanish = _alternation(words["given_verbs"])
    # «gave you», «sent you» name the person; a bare «listed», «suggested» or «named» is any clause («the recipe
    # suggested 2 cups», «a dish named…») and is read only with its «I».
    addressed = _alternation([verb for verb in words["given_verbs_en"] if verb.endswith(" you")])
    bare = _alternation([verb for verb in words["given_verbs_en"] if not verb.endswith(" you")])
    only = r"(?:(?:solo|solamente|nada\s+mas|only|just)\s+)?"
    return re.compile(
        rf"\b(?:{only}te\s+(?:{spanish})|(?:i\s+)?{only}(?:{addressed})|i\s+{only}(?:{bare}))\s+{only}(?:you\s+)?"
        rf"(?:(?:unos|unas|the)\s+)?(?P<n>\d{{1,2}}|[a-z]+)\b"
    )


@lru_cache(maxsize=1)
def _relative_given_pattern() -> re.Pattern[str]:
    words = _words()
    given = _alternation([*words["given_verbs"], *words["given_verbs_en"]])
    return re.compile(
        rf"\b(?:te\s+|i\s+)?(?:{given})\s+(?:(?:you|te)\s+)?(?:(?:muchos?|muchas?|algo|a\s+lot|a\s+bit|way)\s+)?"
        rf"(?P<side>{_alternation([*words['relative_more'], *words['relative_fewer']])})\s+"
        rf"(?:\w+\s+){{0,2}}?(?:{_alternation(words['relative_asked'])})\b"
    )


def stated_given_relation(reply: str) -> str | None:
    """Whether a reply says BAXY gave more or fewer things than were asked: «te di más de lo que pediste» → "more",
    «I gave you fewer than you asked» → "fewer"; None when it says neither."""

    folded = " ".join(re.sub(r"[^\w\s]", " ", _fold(str(reply or ""))).split())
    for found in _relative_given_pattern().finditer(folded):
        # «No te di más de lo que pediste: son las tres» denies it (review 2026-10-08 r2).
        if re.search(r"\b(?:no|nunca|jamas|not|never)\s+(?:te\s+)?$", folded[: found.start()]) is not None:
            continue
        return "more" if found.group("side") in set(_words()["relative_more"]) else "fewer"
    return None


def stated_given_count(reply: str) -> int | None:
    """How many things a reply says BAXY gave the person before: «Solo te proporcioné dos recetas» → 2, «I gave you
    five» → 5, «te di 5: …» → 5; None when it says no such count («te di la receta», «te paso los pasos»)."""

    folded = " ".join(re.sub(r"[^\w\s]", " ", _fold(str(reply or ""))).split())
    articles = set(_words()["articles"])
    for found in _given_pattern().finditer(folded):
        said = found.group("n")
        if said in articles:
            # «Te di una lista con cinco ideas», «te di un par de opciones»: an article is no count of what was given.
            continue
        count = _count(said)
        if type(count) is int:
            return count
    return None


# Ronda 22 «vetos que reparan sin rehacer» (pasada r18): one thing said twice in a row, a line that is only a title, and
# a list renumbered after an item is dropped. The joining and title words are data (``repeat_separators``,
# ``title_connectors``).
_RUN_WORD = re.compile(r"[^\W_][\w'’+-]*")
_RUN_BREAK = re.compile(r"[.!?;:\n]")
# What makes a name written again another name: a number or a Roman numeral, a colon or a dash and a subtitle, or more
# capitalised words right after it.
_NAME_GOES_ON = re.compile(r"[ \t]*(?:\d|[:–—][ \t]*\w|-[ \t]+\w)|[ \t]+(?:[IVX]{1,4}\b|[^\W\d_a-zß-ÿ])")


def _said_before(folded: list[str], start: int, run: list[str], text: str, tokens: list) -> bool:
    """Whether the run is written right before its first writing too, joined by a comma."""

    size = len(run)
    if start - size < 0 or folded[start - size: start] != run:
        return False
    return re.fullmatch(r"[ \t]*,?[ \t]*", text[tokens[start - 1].end(): tokens[start].start()]) is not None


# The head of a clause: the start of the text, of a sentence or of a quote, with only spaces after it.
_CLAUSE_HEAD = re.compile(r"(?:^|[.!?;:\n¡¿«\"“(])[ \t]*$")


def _said_again_after(folded: list[str], index: int, run: list[str], text: str, tokens: list) -> bool:
    """Whether the run is written a third time right after its second writing, joined by a comma or a joining word."""

    if index + len(run) > len(tokens) or index < 1:
        return False
    if folded[index: index + len(run)] == run:
        return re.fullmatch(r"[ \t]*,?[ \t]*", text[tokens[index - 1].end(): tokens[index].start()]) is not None
    separators = set(_words()["repeat_separators"])
    return (
        index + 1 + len(run) <= len(tokens)
        and folded[index] in separators
        and folded[index + 1: index + 1 + len(run)] == run
        and re.fullmatch(r"[ \t]*,?[ \t]*", text[tokens[index - 1].end(): tokens[index].start()]) is not None
    )


class _Repeat(NamedTuple):
    first_start: int
    first_end: int
    second_start: int
    second_end: int
    comma: bool  # the two are joined only by a comma («leche de coco, leche de coco»), not by «y», «o», «and»


def _repeats(text: str) -> list[_Repeat]:
    """Every run of words said twice in a row inside one sentence, joined by nothing, a comma or a joining word
    («Rayuela y Rayuela», «leche de coco, leche de coco», «de la historia de la historia»). One word alone counts only
    as a name written twice with a comma or a joining word between («Rayuela y Rayuela»; «muy muy», «no, no» and
    «Bora Bora» are not); a longer run needs a word of four letters or more that is not an article."""

    words = _words()
    separators = set(words["repeat_separators"])
    articles = set(words["articles"])
    tokens = list(_RUN_WORD.finditer(text))
    folded = [_fold(token.group()) for token in tokens]
    found: list[_Repeat] = []
    for size in range(6, 0, -1):
        for start in range(0, len(tokens) - 2 * size + 1):
            following = start + size
            gap = text[tokens[following - 1].end(): tokens[following].start()]
            if re.fullmatch(r"[ \t]*,?[ \t]*", gap) is None:
                continue
            second = following
            joined_by_word = False
            if folded[following] in separators and following + 1 < len(tokens):
                after = text[tokens[following].end(): tokens[following + 1].start()]
                if re.fullmatch(r"[ \t]+", after) is not None and folded[following + 1: following + 1 + size] == (
                    folded[start: start + size]
                ):
                    second, joined_by_word = following + 1, True
            if second + size > len(tokens) or folded[second: second + size] != folded[start: start + size]:
                continue
            span = text[tokens[start].start(): tokens[second + size - 1].end()]
            if _RUN_BREAK.search(span) or "," in text[tokens[start].start(): tokens[start + size - 1].end()]:
                # A run with a comma inside it is a pattern read out of step («quiero, te» in «Te quiero, te quiero, te
                # quiero»): the thing said twice is what the commas separate.
                continue
            if _NAME_GOES_ON.match(text, tokens[second + size - 1].end()) is not None and (
                tokens[second].group()[:1].isupper() or tokens[second].group()[:1].isdigit()
            ):
                # Revisión 1 de la ronda 22 («Toy Story y Toy Story 2», «Black Panther y Black Panther: Wakanda
                # Forever», «Frozen, Frozen 2 y Moana»): a name whose second writing goes on with a number, a colon or
                # more capitalised words is another name, a sequel, not the first said again.
                continue
            if "," in gap and not joined_by_word and (
                _CLAUSE_HEAD.search(text[: tokens[start].start()]) is not None
                or _said_again_after(folded, second + size, folded[start: start + size], text, tokens)
                or _said_before(folded, start, folded[start: start + size], text, tokens)
            ):
                # Revisión 1 de la ronda 22 («New York, New York es…», «La cucaracha, la cucaracha, ya no puede…»,
                # «Feliz Navidad, Feliz Navidad, Feliz Navidad…»): a run doubled with a comma at the head of its clause,
                # or said three times, is a title or a refrain written that way; a slip doubles an item inside a list
                # («arroz, leche de coco, leche de coco y curry»).
                continue
            run = folded[start: start + size]
            if size == 1:
                if not (joined_by_word or "," in gap) or len(run[0]) < 3:
                    continue
                if not (tokens[start].group()[:1].isupper() and tokens[second].group()[:1].isupper()):
                    continue
            elif not any(len(word) >= 4 and word not in articles for word in run):
                continue
            found.append(_Repeat(
                tokens[start].start(), tokens[start + size - 1].end(), tokens[second].start(),
                tokens[second + size - 1].end(), "," in gap and not joined_by_word,
            ))
    return found


def _sections(text: str) -> list[str]:
    """The sections of an answer written in lines: a line that is no list item, not indented and not blank («**Galaxy
    S24:**», «Cena:») opens the next one. An answer without a list in lines is one section."""

    sections: list[list[str]] = [[]]
    for line in text.split("\n"):
        item = _NUMBERED_ITEM.match(line.lstrip()) is not None or _BULLET_ITEM.match(line) is not None
        if line.strip() and not item and not line[:1].isspace() and sections[-1]:
            sections.append([])
        sections[-1].append(line)
    return ["\n".join(lines) for lines in sections]


def _a_name(item: str) -> bool:
    """An item that is only a name («Rayuela», «Toy Story», «Precio»), not a step or a sentence («Espera 30 segundos»,
    «leche de coco»)."""

    words = _RUN_WORD.findall(item)
    return title_only(item) or (len(words) == 1 and words[0][:1].isupper())


def _repeated_name(section: str) -> str:
    """A name one list of a section says twice; "" when it says each once. Revisión 2 de la ronda 22 («**iPhone 15:**
    - Precio: alto - Batería: buena **Galaxy S24:** - Precio: medio…», «1. Desenchúfalo 2. Espera 30 segundos 3.
    Enchúfalo 4. Espera 30 segundos»): a list of steps or of sentences may do a thing twice, and a label written again
    with another value («Precio: medio», «Ventaja: …») names nothing twice; only a list of names repeats one."""

    names = listed_items(section)
    lines = _top_level_lines(section) or names
    if len(names) < 2 or len(lines) != len(names) or not all(_a_name(name) for name in names):
        return ""
    articles = set(_words()["articles"])
    seen: dict[str, str] = {}
    for name, line in zip(names, lines):
        key = " ".join(token for token in re.sub(r"[^\w\s]", " ", _fold(name)).split() if token not in articles)
        if not key:
            continue
        if key in seen:
            told = _fold(line.replace("**", "").replace("__", "")).strip(" .;")
            if told == seen[key] or told == key or _fold(name) == told:
                return name
            continue
        seen[key] = _fold(line.replace("**", "").replace("__", "")).strip(" .;")
    return ""


def _written_as_a_title(text: str, repeat: _Repeat, evidence: str) -> bool:
    """A run doubled with a comma is a title written that way: the evidence writes it doubled, or both writings are a
    name, each word of content with a capital or a digit («New York, New York», «Que Sera, Sera», «Sugar, Sugar»).
    Revisión 2 de r24 (r23 t4-c08 t1 «añade arroz, leche de coco, leche de coco y azúcar»): an item of an enumeration
    written in lower case and doubled is a slip, not a title."""

    doubled = text[repeat.first_start: repeat.second_end]
    if evidence and re.sub(r"\s+", " ", _fold(doubled)) in re.sub(r"\s+", " ", _fold(evidence)):
        return True
    connectors = set(_words()["title_connectors"])
    for start, end in ((repeat.first_start, repeat.first_end), (repeat.second_start, repeat.second_end)):
        words = [word for word in _RUN_WORD.findall(text[start:end]) if _fold(word) not in connectors]
        if not words or not all(word[:1].isupper() or word[:1].isdigit() for word in words):
            return False
    return True


def _without_comma_doubles(text: str, evidence: str = "") -> str:
    """``text`` with the second writing of each run doubled with a comma left out when it is written as a title
    («New York, New York, grabada en 1979» → «New York, grabada en 1979»; ``_written_as_a_title``)."""

    kept = text
    taken: list[tuple[int, int]] = []
    for repeat in sorted((found for found in _repeats(text) if found.comma), key=lambda found: -found.first_end):
        if any(repeat.first_end < end and start < repeat.second_end for start, end in taken):
            continue
        if not _written_as_a_title(text, repeat, evidence):
            continue
        taken.append((repeat.first_end, repeat.second_end))
        kept = kept[: repeat.first_end] + kept[repeat.second_end:]
    return kept


def duplicated_run(answer: str, *, comma_doubled: bool = True, evidence: str = "") -> str:
    """A thing an answer says twice: a name one list of a section repeats (``_repeated_name``) or a run of words written
    twice in a row (``_repeats``); "" when it says each thing once. «Rayuela» named in two sentences is said once in
    each, and a label in two sections («Precio:» under each phone) once in each.

    ``comma_doubled=False`` (revisión 3 de la ronda 22, the veto of the compose stage): a run doubled with only a comma
    between («es New York, New York, grabada en 1979», «canta Que Sera, Sera», «Yesterday, New York, New York y
    Imagine») may be a title written that way, which no other draft can write otherwise; it is read once when it is
    written as one (``_written_as_a_title``: capitalised, or doubled so in ``evidence``). A name a list says again
    further on («Toy Story, Cars, Toy Story»), one joined by «y» («Rayuela y Rayuela») and an item of an enumeration
    doubled in lower case («arroz, leche de coco, leche de coco y azúcar», revisión 2 de r24) are still twice."""

    text = str(answer or "")
    if not comma_doubled:
        text = _without_comma_doubles(text, str(evidence or ""))
    for section in _sections(text):
        repeated = _repeated_name(section)
        if repeated:
            return repeated
    runs = _repeats(text)
    return text[runs[0].first_start: runs[0].first_end] if runs else ""


# «**…**» around any text; «__…__» only around words with a space between them, so that an identifier written in prose
# («__init__», «__name__») stays as written.
_EMPHASIS = re.compile(
    r"(?<![\w*])\*\*(?![\s*])(?P<starred>.+?)(?<![\s*])\*\*(?![\w*])"
    r"|(?<![\w_])__(?![\s_])(?P<underlined>[^_\n]*?\s[^_\n]*?)(?<![\s_])__(?![\w_])"
)
_CODE = re.compile(r"```.*?(?:```|$)|`[^`\n]*`", re.DOTALL)


def _plain(found: re.Match[str]) -> str:
    return found.group("starred") if found.group("starred") is not None else found.group("underlined")


def without_emphasis(text: str) -> str:
    """``text`` with its markdown emphasis («**Pollo al curry**:», «__nota__») written plain, outside code (a ``` block
    or an inline `span`, where «**» and «__» are code: «a**b», «__init__»). Revisión 2 de r24 (r23 t2-c02#1 / t4-c08 t1:
    «1. **Pollo al curry rápido**: …» published with its asterisks though the writer is told «sin markdown»): the
    person's window shows the marks as written."""

    value = str(text or "")
    pieces: list[str] = []
    last = 0
    for code in _CODE.finditer(value):
        pieces.append(_EMPHASIS.sub(_plain, value[last:code.start()]))
        pieces.append(code.group())
        last = code.end()
    pieces.append(_EMPHASIS.sub(_plain, value[last:]))
    return "".join(pieces)


_MARKER_LINE = re.compile(
    r"^(?P<lead>[ \t]*(?:#{1,6}[ \t]+)?(?:\*\*|__)?)(?P<n>\d{1,2})(?P<mark>[.)])(?=\s)", re.MULTILINE
)
_INLINE_MARKER = re.compile(r"(?:(?<=^)|(?<=[.!?…][ \t]))(?P<n>\d{1,2})(?P<mark>[.)])(?=[ \t]+\S)")


def renumbered(answer: str) -> str:
    """The numbered list of an answer numbered again from 1 after an item was dropped («1. A 3. C» → «1. A 2. C»);
    a list written in lines renumbers the markers at the column of its first one (a sublist under them is left as
    written), a list written in one paragraph renumbers each marker that opens a sentence."""

    text = str(answer or "")
    lines = list(_MARKER_LINE.finditer(text))
    if len(lines) >= 2 and "\n" in text.strip():
        column = len(lines[0].group("lead"))
        counter = iter(range(1, len(lines) + 1))
        return _MARKER_LINE.sub(
            lambda found: found.group("lead") + str(next(counter)) + found.group("mark")
            if len(found.group("lead")) == column else found.group(0),
            text,
        )
    if _INLINE_MARKER.match(text) is None:
        # A paragraph that does not open with a marker numbers no list («Nací en 1990. 3) …» is not one).
        return text
    counter = iter(range(1, 100))
    return _INLINE_MARKER.sub(lambda found: str(next(counter)) + found.group("mark"), text)


def title_only(line: str) -> bool:
    """A line or a list item that is only a name or a title («It Takes Two», «Garry's Mod», «El Señor de los
    Anillos»): its list marker and bold left out, every word written with a capital or a digit except the small words
    a title carries (``title_connectors``), two to eight words, and nothing after a colon or a dash."""

    text = re.sub(r"^\s*(?:[-•*–]|\d{1,2}[.)])\s*", "", str(line or "")).replace("**", "").replace("__", "").strip()
    text = text.strip(" .;,!¡¿?\"'«»“”()")
    if not text or re.search(r"[:—–]\s|\s-\s", text):
        return False
    words = _RUN_WORD.findall(text)
    if not words or len(words) > 8:
        return False
    connectors = set(_words()["title_connectors"])
    named = 0
    for word in words:
        if word[:1].isupper() or word[:1].isdigit():
            named += word[:1].isupper()
            continue
        if _fold(word) not in connectors:
            return False
    # One word alone («Sí.», «Rayuela») is judged as any short reply is; a title is two words or more.
    return named >= 1 and len(words) >= 2
