"""Figures and names a talk answer states from memory that nothing in the conversation stated.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Iterable

from .semantic.normalize import fold
from .semantic import listing as semantic_listing
from .semantic import quantities as semantic_quantities
from .semantic import web as semantic_web
from .search_report import _draft_clauses


# M95 (D52; DEV-D v3l, v3r, v3u D-p28-t3 «Hustlers is perfect.» → «That's a great choice, but *Hustlers* is a 2019 film,
# not a 1980 movie.»): a talk turn reads nothing, so a figure of its answer that the conversation does not state comes
# from the model's memory, said with no notice. D52 (owner): a quantity, distance, duration, date, year or count is
# looked up before it is stated, and memory answers only what is not a figure. A hexadecimal colour is a value written,
# not a fact remembered.
_HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _is_a_year(value: Fraction) -> bool:
    return value.denominator == 1 and 1000 <= value <= 2099


def talk_memory_figures(reply: str, request: str, dialogue: Iterable[str] = (), person: Iterable[str] = ()) -> list[str]:
    """M95: the figures of a talk answer that nothing in the conversation states (see above), as written.

    ``dialogue`` is every earlier message of the conversation (the person's and BAXY's: a figure BAXY already said is
    the conversation's), ``person`` the person's own earlier messages. When the conversation writes numbers, a figure
    may be computed from them (a tip, a division, a unit conversion of a figure read before), so only a year is judged
    then, and none when the person wrote a year themselves («nací en 1995, ¿en qué año cumplo 30?»).

    M104 (reserve v3z): a number is said in digits or in words, on both sides. The person's «square root of nine» or
    «dividir doscientos por cuatro» gives numbers (``semantic.quantities.spoken_numbers_in``), so the answer computed
    from them is not memory; and the answer's own figure spelled out with its unit («seven to eight minutes», «eight
    thousand meters», which the M95 retry wrote to get past a veto that read only digits) is a figure like «7 minutes».

    M154 (D52; DEV-H v4u H-s087 «Son aproximadamente 320 euros.» for «¿cuánto son 350 dólares en euros…?», H-w05-t4
    «Today Bitcoin is at 1,850,000 Chilean pesos.» after «85.000 dólares»): an amount in another currency is not
    computed from the conversation's numbers unless a rate between the two was said; when the person asks a currency
    conversion and none was, the amounts in a currency the conversation did not say are memory's too."""

    dialogue, person = [str(item or "") for item in dialogue], [str(item or "") for item in person]
    said = [str(request or ""), *dialogue]
    text = _HEX_COLOUR.sub(" ", str(reply or ""))
    converted = _converted_from_memory(text, str(request or ""), dialogue, person)
    named = set(re.findall(r"\w+", fold(" ".join(said))))
    said_numbers = [*semantic_quantities.numbers_in(said), *semantic_quantities.spoken_numbers_in(said)]
    unsaid = [
        figure for figure in semantic_quantities.unsaid_figures(text, said)
        if (
            any(character.isdigit() for character in figure)
            # «Windows 11 trae…» after «¿qué tiene de nuevo windows?»: a number after a name the conversation said,
            # even when that name opens the sentence, is part of the name.
            and not any(
                fold(found.group(1)) in named
                for found in re.finditer(rf"\b([A-Z][\w'’-]*)[ \t]+{re.escape(figure)}(?![\w]|[.,]\d)", text)
            )
        )
        or (
            # A number word with its unit, whose number the conversation did not say («dos tazas» after «dos tazas»).
            semantic_quantities.spelled_figure(figure)
            and not set(semantic_quantities.spoken_numbers_in([figure])) <= set(said_numbers)
        )
    ]
    if not unsaid or not said_numbers:
        judged = unsaid
    elif any(_is_a_year(value) for value in semantic_quantities.numbers_in([str(request or ""), *person])):
        judged = []
    else:
        judged = [
            figure for figure in unsaid if (value := semantic_quantities.numbers_in([figure])) and _is_a_year(value[0])
        ]
    return list(dict.fromkeys([*judged, *converted]))


def _converted_from_memory(reply: str, request: str, dialogue: list[str], person: list[str]) -> list[str]:
    """M154: the amounts of a talk answer in a currency, when a currency conversion is asked, no rate between the two
    currencies was said, and the conversation did not say that amount (see ``talk_memory_figures``)."""

    asked = semantic_web.currency_conversion_request(
        request, "", dialogue[-1] if dialogue else "", person[-1] if person else "",
    )
    if asked is None or any(semantic_web.states_the_rate(said, asked) for said in dialogue):
        return []
    said_values = set(semantic_quantities.numbers_in([request, *dialogue]))
    return [
        amount for amount in semantic_web.currency_amounts(reply)
        if not set(semantic_quantities.numbers_in([amount])) <= said_values
    ]


# M95 (DEV-D v3x D-p34-t2 «explícame cómo lo entendiste en la primera pregunta» → «En mi primera respuesta, me referí a
# las cápsulas del tiempo como … las famosas de la NASA o las de la película "Back to the Future"…», after a first answer
# that said only «No encontré ninguna página que especifique las fechas…»): what BAXY says it said is in the dialogue.
# A sentence of a talk answer that speaks of BAXY's own earlier answer names nothing the conversation does not carry.
_OWN_EARLIER_ANSWER = re.compile(
    r"\b(?:mi|my)\s+(?:primera|anterior|ultima|previa|first|previous|last|earlier|prior)\s+"
    r"(?:respuesta|pregunta|busqueda|answer|reply|response|question|search)\b"
    r"|\b(?:me\s+referi|respondi|conteste|te\s+dije|entendi|interprete|"
    r"i\s+(?:referred|meant|said|answered|replied|understood|interpreted|took\s+it))\b"
)
_NAMED_IN_REPLY = re.compile(r"[«\"“]([^»\"”\n]{2,80})[»\"”]|(?<=[\w,;] )([A-ZÁÉÍÓÚÑ][\wáéíóúñ'’-]+)")


def talk_misquotes_itself(reply: str, dialogue: Iterable[str] = ()) -> list[str]:
    """M95: the names (quoted titles, capitalized words past a sentence's start) that a sentence of a talk answer about
    BAXY's own earlier answer gives and no message of the conversation carries (see above)."""

    said = fold(" ".join(str(item or "") for item in dialogue))
    unsaid: list[str] = []
    for sentence in re.split(r"(?<=[.!?…])\s+", str(reply or "").strip()):
        if _OWN_EARLIER_ANSWER.search(fold(sentence)) is None:
            continue
        for found in _NAMED_IN_REPLY.finditer(sentence):
            name = (found.group(1) or found.group(2) or "").strip()
            # A quoted phrase is a title or a name when a word of it is capitalized; «"time capsules"» (v3l D-p34-t2,
            # the other meaning offered) is a phrase.
            if found.group(1) and not re.search(r"(?:^|\s)[A-ZÁÉÍÓÚÑ]", name):
                continue
            if name and fold(name) not in said and name not in unsaid:
                unsaid.append(name)
    return unsaid


def _without_memory_figures(reply: str, figures: Iterable[str]) -> str:
    """M95: the talk answer without the sentences that carry a figure from memory (or a name of BAXY's earlier answer
    it never gave); "" when every sentence does."""

    marked = [str(item) for item in figures if str(item)]

    def carries(sentence: str) -> bool:
        return any(
            re.search(rf"(?<![\w.,]){re.escape(figure)}(?![\w]|[.,]\d)", sentence)
            # M104: a figure in words is found folded («Ocho minutos» → «ocho minutos»).
            or re.search(rf"(?<![\w.,]){re.escape(fold(figure))}(?![\w]|[.,]\d)", fold(sentence))
            for figure in marked
        )

    # Ronda 22 (r18 t3-c17 t1 «1. El asalto de Bosnia por Serbia en 1914. 2. El bloqueo naval alemán…» → «1. 2. El
    # bloqueo…»): a list marker opens its item, it is not a sentence of its own; the item goes whole with its figure and
    # the list is numbered again. A list in lines keeps its lines.
    # Ronda 24 (r23 t3-c17 t1 «dame 4 causas…» → three): an item whose figure is only its time or place phrase («…en
    # Sarajevo en 1914», «(1914)», «in 1914») keeps the item without that phrase (semantic.listing.without_figure_phrase);
    # only an item whose figure is what it says goes whole.
    def trimmed(line: str) -> str:
        kept = line
        for figure in marked:
            kept = semantic_listing.without_figure_phrase(kept, figure)
        return kept if kept != line and not carries(kept) else line
    def item_trimmed(clause: str) -> str:
        return trimmed(clause) if re.match(r"\s*\d{1,2}[.)]\s", clause) else clause

    # Revisión 2 de la ronda 24 («1. El Mundial de 1954.\n2. El Mundial de 1974.\n3. El Mundial de 2014.» → «1. El
    # Mundial.» three times): when the figure is all that told the items apart, the cut leaves one item said again; an
    # item whose cut repeats another item goes whole with its figure, as it always did.
    def item_key(item: str) -> str:
        return " ".join(re.findall(r"\w+", fold(re.sub(r"^\s*(?:\d{1,2}[.)]|[-•*–])\s+", "", item))))

    def unrepeated(items: list[str], cut: list[str]) -> list[str]:
        keys = [item_key(item) for item in cut]
        return [trim if trim == item or keys.count(item_key(trim)) == 1 else item for item, trim in zip(items, cut)]

    def sentences_kept(value: str) -> str:
        clauses = [value[start:end] for start, end in _draft_clauses(value, sentences_only=True)]
        listed = [index for index, clause in enumerate(clauses) if re.match(r"\s*\d{1,2}[.)]\s", clause)]
        cut = dict(zip(listed, unrepeated([clauses[i] for i in listed], [item_trimmed(clauses[i]) for i in listed])))
        return " ".join(
            cut.get(index, clause).strip() for index, clause in enumerate(clauses)
            if not carries(cut.get(index, clause))
        ).strip()

    value = str(reply or "").strip()
    if not any(re.match(r"\s*(?:\d{1,2}[.)]|[-•*–])\s", line) for line in value.split("\n")[1:]):
        # No list in lines: its sentences, as they always were, one paragraph.
        return semantic_listing.renumbered(sentences_kept(re.sub(r"\s*\n\s*", " ", value)))
    lines = value.split("\n")
    listed = [index for index, line in enumerate(lines) if re.match(r"\s*(?:\d{1,2}[.)]|[-•*–])\s", line)]
    for index, line in zip(listed, unrepeated([lines[i] for i in listed], [trimmed(lines[i]) for i in listed])):
        lines[index] = line
    kept_lines: list[str] = []
    for line in lines:
        if re.match(r"\s*(?:\d{1,2}[.)]|[-•*–])\s", line):
            if not carries(line):
                kept_lines.append(line)
        elif sentences_kept(line):
            kept_lines.append(sentences_kept(line))
    kept = semantic_listing.renumbered("\n".join(kept_lines)).strip()
    return kept if re.search(r"\w", kept) else ""
