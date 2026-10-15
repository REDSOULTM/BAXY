"""Whether the answer a search report gives is in the evidence, not only its words.

Uso real v3 tanda 1 (2026-10-07):

- «quien gano el mundial del 2014» → «Brasil ganó la Copa Mundial de Fútbol de 2014.» Every word of it was in the
  results («Copa Mundial de la FIFA Brasil 2014», «Se realizó en Brasil…»), so the word-by-word filter let it pass;
  no result said that anyone won. The datum of a relation asked («who won», «quién dirigió») is a name, and a result
  states it only when ONE of its sentences carries that name together with the relation (``answer_unstated``).
- «cuales son las peliculas mas taquilleras de la historia? dame el top 5» → «Avengers: Endgame… y la lista incluye
  también Rápidos y Furiosos, Piratas del Caribe, Star Wars y Bohemian Rhapsody.»: one name from an encyclopedia's
  sentence, four from a photo gallery that names them in no order. A listing is told only with things that ONE
  result names and that result is a ranking (``listing_not_from_one_ranking``).

The relation words, function words and ordinal words are data (``data/answer_evidence_words.v1.json``).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .listing import listing_asked
from .quantities import unit_of_a_figure
from .normalize import fold

_WORD = re.compile(r"[^\W_][\w'’+]*")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\s+…\s+|\n+")


@lru_cache(maxsize=1)
def _words() -> dict:
    path = Path(__file__).resolve().parent.parent / "data" / "answer_evidence_words.v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def relation_asked(question: str) -> str | None:
    """The relation a question asks of someone or something («quién ganó…» → «win»), None when it asks none."""

    words = set(fold(question).replace("¿", " ").split())
    words = {re.sub(r"[^\w]", "", word) for word in words}
    for name, relation in _words()["relations"].items():
        if words & set(relation["asked"]):
            return name
    return None


def answerWords(question: str) -> list[str]:
    """The word beginnings with which a page states the relation the question asks; empty when it asks none. They go
    to the search provider (web.search ``answerWords``), which reads words of no language of its own."""

    relation = relation_asked(question)
    return list(_words()["relations"][relation]["stated"]) if relation is not None else []


def answer_words_not(question: str) -> list[str]:
    """The whole words that begin as the relation is stated but name something else («campeonato», «championship»);
    they go to the provider with the answer words (web.search ``answerWordsNot``), so that it judges a fragment as
    ``states_relation`` does here."""

    relation = relation_asked(question)
    return list(_words()["relations"][relation].get("not_stated", ())) if relation is not None else []


def states_relation(sentence: str, relation: str) -> bool:
    """A sentence of a page says the relation: one of its words begins as the relation is stated."""

    words = _words()["relations"][relation]
    stems = tuple(words["stated"])
    other = set(words.get("not_stated", ()))
    return any(word.startswith(stems) and word not in other for word in _WORD.findall(fold(sentence)))


def evidence_sentences(results: Iterable[object]) -> list[list[str]]:
    """Each result's title and the sentences of its snippet, folded, one list per result."""

    units: list[list[str]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        sentences = [fold(str(item.get("title") or ""))]
        sentences += [fold(part) for part in _SENTENCE_END.split(str(item.get("snippet") or "")) if part.strip()]
        units.append([sentence for sentence in sentences if sentence.strip()])
    return units


def _capitalised(word: str) -> bool:
    return word[:1].isupper()


def _written_inside(word: str, evidence: str) -> bool:
    """The evidence writes the word, capitalised as given, somewhere other than at a sentence's opening."""

    for found in re.finditer(r"\b" + re.escape(word) + r"\b", evidence):
        before = evidence[: found.start()].rstrip(" \t«\"“(¿¡")
        if before and before[-1] not in ".!?\n:":
            return True
    return False


def name_spans(text: str, evidence: str = "") -> list[str]:
    """The names a text says: runs of capitalised words, joined by connectors («Copa Mundial de Fútbol de 2014»,
    «Avengers: Endgame»), each as written. A sentence's first word starts a name only when the evidence writes it
    capitalised inside a sentence (a name, not just an opening): «Brasil ganó…» yes, «Las cinco…» no."""

    words = _words()
    connectors = set(words["span_connectors"])
    function = set(words["function_words"])
    spans: list[str] = []
    for sentence in re.split(r"(?<=[.!?;])\s+", str(text or "")):
        current: list[str] = []
        pending: list[str] = []
        previous_end = 0
        for index, found in enumerate(_WORD.finditer(sentence)):
            word = found.group()
            gap = sentence[previous_end:found.start()]
            previous_end = found.end()
            joined = current and re.fullmatch(r"\s*[:'’]?\s*", gap) is not None
            folded = fold(word)
            opening = index == 0
            named = _capitalised(word) and not (
                opening and (folded in function or not _written_inside(word, evidence))
            )
            if named or (joined and word.isdigit()):
                if joined and current:
                    current += pending
                elif current:
                    spans.append(" ".join(current))
                    current = []
                pending = []
                current.append(word)
                continue
            if joined and folded in connectors:
                pending.append(word)
                continue
            if current:
                spans.append(" ".join(current))
            current, pending = [], []
        if current:
            spans.append(" ".join(current))
    return [span for span in spans if any(fold(part) not in function for part in span.split())]


def _span_words(span: str) -> list[str]:
    connectors = set(_words()["span_connectors"])
    return [word for word in (fold(part) for part in _WORD.findall(span)) if word not in connectors]


def answer_spans(report: str, question: str, evidence: str) -> list[str]:
    """The names the report gives as its answer: those that share no word with the question (the question's own
    topic, «Copa Mundial de Fútbol de 2014» for «el mundial del 2014», is not the answer), and that are not the unit or
    currency of a figure (semantic.quantities.unit_of_a_figure)."""

    asked = {re.sub(r"[^\w]", "", word) for word in fold(question).split()}
    return [
        span for span in name_spans(report, evidence)
        # Ronda 22 (r18 t1-c03): the currency or unit of a figure («2 925 466 085 USD») names nothing answered.
        if not unit_of_a_figure(report, span)
        and not any(word in asked or (len(word) >= 5 and any(seen[:5] == word[:5] for seen in asked if len(seen) >= 5))
                   for word in _span_words(span))
    ]


def _says(sentence: str, span: str) -> bool:
    return all(re.search(r"\b" + re.escape(word) + r"\b", sentence) is not None for word in _span_words(span))


def counted_words(question: str) -> list[str]:
    """What a question of how many counts, folded: the first content word after the words that ask it, and the next
    one when it follows at once or through a connector («cuántos discos de estudio tienen…» → discos, estudio; «how
    many studio albums» → studio, albums); empty when it asks no count (data ``count_asked``)."""

    words = _words()
    folded = " ".join(_WORD.findall(fold(question)))
    function, connectors = set(words["function_words"]), set(words["span_connectors"])
    for asked in words["count_asked"]:
        found = re.search(rf"\b{re.escape(asked)}\b", folded)
        if found is None:
            continue
        counted: list[str] = []
        for word in folded[found.end():].split():
            if counted and word in connectors:
                continue
            if len(word) < _ROOT_HEAD or word in function:
                if counted:
                    break
                continue
            counted.append(word)
            if len(counted) == 2:
                break
        return counted
    return []


def counts_of_one(sentence: str, counted: list[str]) -> list[str]:
    """Where a sentence says one of the thing counted: a word of one (data ``count_one_words``) followed, within
    ``count_reach`` words and no punctuation, by a word of one root with a counted word («un disco», «su único disco de
    estudio», «one studio album»); «una de las canciones» is one among others (``count_partitives``)."""

    words = _words()
    ones, partitives = set(words["count_one_words"]), set(words["count_partitives"])
    # «una canción del disco» counts songs: the thing counted follows the word of one before any function word.
    breaks = set(words["function_words"]) | set(words["span_connectors"])
    found: list[str] = []
    for part in re.split(r"[^\w\s'’]+", fold(sentence)):
        tokens = part.split()
        for index, token in enumerate(tokens):
            following = tokens[index + 1: index + 1 + int(words["count_reach"])]
            if token not in ones or not following or following[0] in partitives:
                continue
            for reach, word in enumerate(following, start=1):
                if any(shares_root(word, wanted) for wanted in counted):
                    found.append(" ".join(tokens[index: index + 1 + reach]))
                    break
                if word in breaks:
                    break
    return found


def answer_unstated(report: str, question: str, results: Iterable[object], not_found: re.Pattern[str]) -> list[str]:
    """The answer names of a report to a relation question that no result's sentence states with that relation, and
    the counts of one it gives to a question of how many that no result's sentence says.

    Empty when the question asks no relation and no count, or every name a report sentence gives with that relation
    sits in one sentence of a result that says the relation too («dirigida por James Cameron» for «quién dirigió
    Titanic»). Estabilización TZ-VETO (z1 t2-c01 t4): «Un disco de estudio: Vida de perros.» answered «cuántos discos
    de estudio tienen los bunkers» from a page that only names the album of a song; a count of one is the answer
    only when a result says one of that thing («su único disco de estudio»). Larger counts are judged by the report's
    figures (search_report._search_report_unsourced_counts)."""

    relation = relation_asked(question)
    counted = counted_words(question)
    if relation is None and not counted:
        return []
    results = list(results)
    evidence = "\n".join(str(item.get(key) or "") for item in results if isinstance(item, dict)
                         for key in ("title", "snippet"))
    units = evidence_sentences(results)
    counted_in_evidence = bool(counted) and any(counts_of_one(said, counted) for unit in units for said in unit)
    missing: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", str(report or "").strip()):
        if not sentence.strip() or not_found.match(fold(sentence)) is not None:
            continue
        if counted and not counted_in_evidence:
            missing += counts_of_one(sentence, counted)
        # Only a sentence that says the relation claims it: «se jugó en Brasil» tells where, not who won.
        if relation is None or not states_relation(sentence, relation):
            continue
        for span in answer_spans(sentence, question, evidence):
            if not any(_says(said, span) and states_relation(said, relation) for unit in units for said in unit):
                missing.append(span)
    return list(dict.fromkeys(missing))


def _clauses(report: str) -> list[str]:
    """The report's sentences, each cut where a clause opposed to the one before it opens (``contrast_words``)."""

    contrast = "|".join(re.escape(word).replace(r"\ ", r"\s+") for word in _words()["contrast_words"])
    clauses: list[str] = []
    for sentence in re.split(r"(?<=[.!?;])\s+", str(report or "").strip()):
        clauses += [part for part in re.split(rf"[,;]?\s+(?=(?:{contrast})\b)", sentence, flags=re.IGNORECASE)
                    if part.strip()]
    return clauses


def _phrases(key: str) -> str:
    return "|".join(
        r"\s+".join(re.escape(part) for part in fold(item).split())
        for item in sorted(_words()[key], key=len, reverse=True)
    )


def _denied_names(clause: str, evidence: str) -> tuple[set[str], set[str]]:
    """The name words a clause denies (``denial_purpose``): after an existence denial (or before it, when none follows)
    or after a possession denial; with them, the thing denied whole: the stems of every word of content the clause says
    besides its denial («No hay tercera temporada de Arcane» → tercera, temporada, arcane). Both empty when it denies
    neither."""

    folded = fold(clause)
    spans = [(len(_WORD.findall(clause[:max(clause.find(span), 0)])), span) for span in name_spans(clause, evidence)]
    for key, before_too in (("existence_denials", True), ("possession_denials", False)):
        found = re.search(rf"\b(?:{_phrases(key)})\b", folded)
        if found is None:
            continue
        start = len(_WORD.findall(folded[:found.start()]))
        end = start + len(_WORD.findall(found.group()))
        named = [span for index, span in spans if index >= end] or (
            [span for index, span in spans if index < start] if before_too else []
        )
        names = {word for word in _span_words(" ".join(named)) if not word.isdigit()}
        if not names:
            return set(), set()
        rest = folded[:found.start()] + " " + folded[found.end():]
        return names, _thing_stems(rest)
    return set(), set()


def _thing_stems(folded: str) -> set[str]:
    """The stems of the words of content of a folded text: no function, joining, negation or connector word; a figure
    whole («360» is not «One»), a word by its first ``_FACT_STEM`` letters («vuelo» and «vuelos»)."""

    words = _words()
    small = (
        set(words["function_words"]) | set(words["clause_joining_words"]) | set(words["negation_words"])
        | set(words["span_connectors"])
    )
    return {
        word if word.isdigit() else word[:_FACT_STEM]
        for word in _WORD.findall(folded)
        if word not in small and (word.isdigit() or len(word) >= 3)
    }


def _affirmation_phrases(key: str) -> str:
    return "|".join(
        r"\s+".join(re.escape(part) for part in phrase.casefold().split())
        for phrase in sorted(_words()[key], key=len, reverse=True)
    )


def _affirms_existence(clause: str, things: list[set[str]]) -> bool:
    """The clause says that a denied thing exists or is had, matched on the clause in lower case with its accents.

    A thing told by its name (``called_affirmations``: «sí existe una llamada Bestiario», «there is one called…»)
    always; a thing said to exist or be had (``existence_affirmations``: «sí hay», «sí tiene», «there are indeed») only
    when the clause says nothing the denial did not, its words of content all inside one thing denied (``_thing_stems``).
    Revisión 4 de r24 (bloqueante 1): «Netflix no tiene la tercera temporada de Arcane, pero sí tiene las dos primeras
    temporadas de Arcane.», «No hay vuelos directos de Santiago a Tokio, pero sí hay vuelos de Santiago a Tokio con
    escala en Dallas.» deny one variant and affirm another one of the same name: no contradiction."""

    lowered = re.sub(r"\s+", " ", clause.casefold())
    if re.search(rf"(?<!\w)(?:{_affirmation_phrases('called_affirmations')})(?!\w)", lowered) is not None:
        return True
    plain = re.compile(rf"(?<!\w)(?:{_affirmation_phrases('existence_affirmations')})(?!\w)")
    if plain.search(lowered) is None:
        return False
    rest = fold(plain.sub(" ", lowered))
    rest = re.sub(rf"^\W*(?:{_phrases('contrast_words')})\b[\s,]*", "", rest)
    said = _thing_stems(rest)
    return any(thing and said <= thing for thing in things)


def denied_and_affirmed(report: str, evidence: str = "", not_found: re.Pattern[str] | None = None) -> list[str]:
    """The names the report denies in one clause and affirms in a later one, as the affirming clause writes them.

    Ronda 24 (r23 t4-c02 t3 «No hay película de Bestiario ni de Rayuela, pero sí existe una llamada Bestiario de
    2002.»): one thing cannot both not exist and exist; the second is another thing that shares the name, and the report
    told it as the one asked. Revisión 1 de r24 (bloqueante 2): only a denial of existence or of having something
    denies (``_denied_names``); a not-found clause (``not_found``, matched on the folded clause) denies nothing, and a
    clause that tells the thing as another one (``other_thing_words``) is the honest way out, no contradiction.

    Revisión 2 de r24 (bloqueante 1: «No hay película de Rayuela. Rayuela es una novela…», «No hay tercera temporada de
    Arcane. Arcane terminó con su segunda temporada…», «No hay vuelos directos de Santiago a Tokio; desde Santiago hay
    que hacer escala…»): naming the name again affirms nothing. A later clause affirms the denied thing only when it says
    that it exists or is had (``_affirms_existence``: «sí existe una llamada Bestiario»), or when it says the whole thing
    denied, every word of it (``_thing_stems``: «Bestiario de 2002 es una película» after «No existe una película de
    Bestiario»). Revisión 4 de r24 (bloqueante 1): a clause that says another variant of the same name exists («no hay
    vuelos directos…, pero sí hay vuelos… con escala») affirms nothing denied."""

    other = set(_words()["other_thing_words"])
    denied: set[str] = set()
    things: list[set[str]] = []
    affirmed: list[str] = []
    for clause in _clauses(report):
        folded = fold(clause)
        opened = re.sub(rf"^\W*(?:{_phrases('contrast_words')})\b[\s,]*", "", folded)
        if not_found is not None and not_found.match(opened) is not None:
            continue
        names, thing = _denied_names(clause, evidence)
        if names:
            denied |= names
            things.append(thing)
            continue
        if not denied or other & set(_WORD.findall(folded)):
            continue
        said = _thing_stems(folded)
        if _affirms_existence(clause, things) or any(thing and thing <= said for thing in things):
            affirmed += [span for span in name_spans(clause, evidence) if set(_span_words(span)) & denied]
    return list(dict.fromkeys(affirmed))


def is_ranking(item: object) -> bool:
    """A result is a ranking: it numbers its positions («1. Avatar 2. Avengers…», «#1», «primer puesto»), or its
    title announces one («las 5 películas más taquilleras», «Top 10…»)."""

    if not isinstance(item, dict):
        return False
    title = str(item.get("title") or "")
    text = title + "\n" + str(item.get("snippet") or "")
    positions = {
        found.group(1)
        for found in re.finditer(r"(?:^|[\s(#])(\d{1,2})\s*(?:[.)ºª°]\s|[-–:]\s|\.$)", text)
    }
    if len(positions) >= 2:
        return True
    ordinals = set(_words()["ordinal_words"])
    if sum(1 for word in _WORD.findall(fold(text)) if word in ordinals) >= 2:
        return True
    return listing_asked(title) is not None


def results_narrated(report: str, question: str = "") -> list[str]:
    """The phrases of a report that make the results, pages or sources the subject that says, shows or states
    («los resultados afirman», «lo único que afirma los resultados», «the results say»), folded; empty when none.
    Ronda 24 (r23 t1-c03#2): «según…» was caught and this was not. When the person asked about results themselves
    («los resultados de las elecciones»), the word is theirs and nothing is read as the search narrated."""

    words = _words()
    subjects = set(words["results_narration_subjects"])
    asked = set(_WORD.findall(fold(question or "")))
    subject = "|".join(sorted(re.escape(word) for word in subjects - asked))
    if not subject:
        return []
    determiner = "|".join(sorted(re.escape(word) for word in words["results_narration_determiners"]))
    verb = "|".join(sorted(re.escape(word) for word in words["results_narration_verbs"]))
    pattern = re.compile(
        rf"\b(?:(?:{determiner})\s+(?:{subject})\s+(?:no\s+|not\s+|do\s+not\s+|don't\s+)?(?:{verb})|"
        rf"(?:{verb})\s+(?:{determiner})\s+(?:{subject}))\b"
    )
    return [found.group(0) for found in pattern.finditer(fold(report or ""))]


_LIST_LINE = re.compile(r"\s*(?:\d{1,2}[.)]|[-•*–])\s")


_RANKING_ROW = re.compile(
    r"(?:^|(?<=[|…\n·\s]))(?P<place>\d{1,2})[.)]\s+(?P<cells>[^|…\n]+?)\s*(?=\||…|\n|\s\d{1,2}[.)]\s|$)"
)


def _ranking_rows(snippet: str) -> list[str]:
    """The names of the rows a snippet numbers 1, 2, 3… in a row, folded; empty when it numbers fewer than two.
    Revisión 2 de la ronda 24 (en.wikipedia «1. 1 · Avengers: Endgame † · $2,926,896,227 · 2019»: the column of the
    peak position comes before the title): a row's name is its first cell with letters; a cell that is only a number
    names nothing."""

    rows: list[str] = []
    for found in _RANKING_ROW.finditer(str(snippet or "")):
        place = int(found.group("place"))
        if place != len(rows) + 1:
            if rows:
                break
            continue
        name = next((cell.strip() for cell in found.group("cells").split("·") if re.search(r"[^\W\d_]", cell)), "")
        if not _span_words(name):
            break
        rows.append(fold(name))
    return rows if len(rows) >= 2 else []


def ranking_firsts(results: Iterable[object], report: str | None = None) -> list[str]:
    """The names the results put first in a ranking they number («1. Avengers: Endgame · 2 926 549 214 · 2019 | 2. …»,
    a page's rows as the provider reads them, or a numbered snippet), folded, one per result that numbers its places.
    With ``report``, only the rankings it is about count: those of which it names a row (revisión 2 de la ronda 24: the
    steps a snippet numbers, «1. Abre la app · 2. Busca», rank nothing a report on films names)."""

    said = fold(report) if report is not None else ""
    firsts: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        rows = _ranking_rows(str(item.get("snippet") or ""))
        if rows and (report is None or any(_says(said, row) for row in rows)):
            firsts.append(rows[0])
    return firsts


@lru_cache(maxsize=1)
def _first_claim() -> re.Pattern[str]:
    words = _words()
    phrases = "|".join(
        sorted((re.escape(phrase).replace(r"\ ", r"\s+") for phrase in words["first_claim_phrases"]), key=len,
               reverse=True)
    )
    return re.compile(rf"\b(?:{phrases})\b")


@lru_cache(maxsize=1)
def _superlative_claim() -> tuple[re.Pattern[str], re.Pattern[str]]:
    words = _words()
    articles = "|".join(re.escape(word) for word in words["first_claim_articles"])
    superlatives = "|".join(re.escape(word) for word in words["first_claim_superlatives"])
    between = "|".join(re.escape(word) for word in [*words["ordinal_words"], *words["first_claim_counts"]])
    copulas = "|".join(re.escape(word).replace(r"\ ", r"\s+") for word in words["first_claim_copulas"])
    return (
        re.compile(rf"\b(?:{articles})\s+(?:(?!(?:{between})\b)[^\W\d_][\w'’-]*\s+){{0,2}}(?:{superlatives})\b"),
        re.compile(rf"\b(?:{copulas})\b"),
    )


def says_first(sentence: str) -> bool:
    """A sentence says which one is first: a phrase of ``first_claim_phrases`` («la más», «encabeza», «tops»), or a
    singular article, up to two words and a superlative, with a copula («La película más taquillera de la historia es
    Avatar.», «Avatar es la película más taquillera.», «The highest-grossing film is Avatar.»). Folded or not."""

    said = fold(sentence)
    superlative, copula = _superlative_claim()
    return _first_claim().search(said) is not None or (
        superlative.search(said) is not None and copula.search(said) is not None
    )


def first_claimed_unranked(report: str, results: Iterable[object]) -> list[str]:
    """The sentences of a report that say which one is first («La más taquillera es Avatar.», «the first is…»;
    ``says_first``) when the results number a ranking and the sentence does not name its first row, or when
    two results number rankings whose firsts differ; folded, empty when none. A sentence that is a list's own line is
    not one (its place is its marker), and with no numbered ranking among the results nothing is judged here; a
    ranking counts when the report names one of its rows (``ranking_firsts``). A sentence ending in a colon that opens
    a list on the next line («El top 5 de las películas más taquilleras es:», «Here is the top 5:») names its first
    with that list's line 1, which is read with it.
    Revisión 1 de la ronda 24 (r23 t1-c03 #1: «Avengers: Endgame» named first from a loose sentence); revisión 3."""

    firsts = list(dict.fromkeys(ranking_firsts(results, str(report or ""))))
    if not firsts:
        return []
    # Revisión 4 de la ronda 24: one first written two ways («Avatar» and «Avatar (película de 2009)», «Avatar (2009)»
    # and «Avatar de James Cameron») is the same first; two rankings disagree only when neither name holds the other.
    disagree = any(not _same_entry(one, other) for index, one in enumerate(firsts) for other in firsts[index + 1:])
    claimed: list[str] = []
    lines = [line for line in str(report or "").split("\n") if line.strip()]
    for index, line in enumerate(lines):
        sentences = [sentence for sentence in _SENTENCE_END.split(line) if sentence.strip()]
        opens_list = (
            line.rstrip().endswith(":") and index + 1 < len(lines) and _LIST_LINE.match(lines[index + 1]) is not None
        )
        for position, sentence in enumerate(sentences):
            if _LIST_LINE.match(sentence):
                continue
            opens = opens_list and position == len(sentences) - 1
            if opens:
                sentence = f"{sentence} {lines[index + 1]}"
            said = fold(sentence)
            if not says_first(said):
                continue
            # Revisión 4: an introduction that only opens a list says no first of its own; its first is the list's line
            # 1, judged against the rankings (the list itself is judged by ``listing_not_from_one_ranking``), so two
            # rankings that disagree do not veto it.
            if (disagree and not opens) or not any(_names_entry(said, first) for first in firsts):
                claimed.append(said.strip())
    return claimed


def _entry_words(name: str) -> set[str]:
    """The words that name a ranking's entry, without what a parenthesis adds («Avatar (película de 2009)» → avatar);
    all its words when nothing else is left."""

    return set(_span_words(re.sub(r"\([^()]*\)", " ", name)) or _span_words(name))


def _same_entry(one: str, other: str) -> bool:
    """Two firsts name the same entry when the words of one are all in the other («Avatar» and «Avatar de James
    Cameron»); «Avengers: Endgame» and «Avengers: Infinity War» are two."""

    first, second = _entry_words(one), _entry_words(other)
    return bool(first and second) and (first <= second or second <= first)


def _names_entry(sentence: str, entry: str) -> bool:
    return all(re.search(r"\b" + re.escape(word) + r"\b", sentence) is not None for word in _entry_words(entry))


def listing_not_from_one_ranking(report: str, question: str, results: Iterable[object]) -> list[str]:
    """The things a report lists (two or more) when no single result that is a ranking names them all; empty when it
    lists fewer than two, or one ranking names them all."""

    results = [item for item in results if isinstance(item, dict)]
    evidence = "\n".join(str(item.get(key) or "") for item in results for key in ("title", "snippet"))
    items = list(dict.fromkeys(answer_spans(report, question, evidence)))
    if len(items) < 2:
        return []
    for item in results:
        said = fold(str(item.get("title") or "") + "\n" + str(item.get("snippet") or ""))
        if is_ranking(item) and all(_says(said, span) for span in items):
            return []
    return items


# Revisión 2 de la ronda 22: how much of a word two writings must share to be one fact («rumor» and «rumores»,
# «cancelado» and «cancelada»); a shorter word is compared whole.
_FACT_STEM = 5


def page_facts_dropped(clause: str, rest: str, question: str, results: Iterable[object]) -> list[str]:
    """The words of the pages a clause of a report carries that the rest of the report does not say, nor the question
    asked: what dropping the clause would take out of the answer. Revisión 2 de la ronda 22 («El vuelo LA800 a Madrid
    sale a las 10:00. En los resultados aparece que fue cancelado.» → «…sale a las 10:00.»; «…pero según los
    resultados cerró definitivamente en marzo»): a clause that narrates the search may carry the decisive fact of the
    page, and without it the answer says the opposite. A word of the narration («resultados», «aparece») is no page's
    word; a function word and the name of a page's site («Wikipedia» of es.wikipedia.org) are no fact. Empty when the
    clause brings nothing of the pages, and only then may it go."""

    results = [item for item in results if isinstance(item, dict)]
    function = set(_words()["function_words"]) | set(_words()["clause_joining_words"])
    sites = {
        label
        for item in results
        for label in re.split(r"[.\-]", fold(re.sub(r"^[a-z]+://", "", str(item.get("url") or "")).split("/", 1)[0]))
        if label
    }

    def fact(word: str) -> bool:
        # A figure of two digits or more is a fact («10:00», «2026»); a list's «3.» is no fact.
        return len(word) >= 2 if word.isdigit() else len(word) >= 4 and word not in function

    def stems(text: str) -> set[str]:
        return {word if word.isdigit() else word[:_FACT_STEM] for word in _WORD.findall(fold(text)) if fact(word)}

    pages = stems("\n".join(str(item.get(key) or "") for item in results for key in ("title", "snippet")))
    said = stems(rest) | stems(question) | {site[:_FACT_STEM] for site in sites}
    dropped: list[str] = []
    for word in _WORD.findall(fold(clause)):
        stem = word if word.isdigit() else word[:_FACT_STEM]
        if fact(word) and stem in pages and stem not in said and word not in dropped:
            dropped.append(word)
    return dropped


def clause_states_unsaid(clause: str, rest: str, question: str, results: Iterable[object]) -> list[str]:
    """What a clause of a report states that the rest of the report, the question and the narration of the search do
    not say: its words of content («funciona», «anulado», «confirman») that neither the rest nor the question write,
    that are no word of the narration (``clause_narration_words``) and no name of a page's site; and, when the clause
    denies something, that negation. Empty when dropping the clause takes nothing of what the answer means.

    Revisión 3 de la ronda 22 («…está en calle Curicó 123, Ñuñoa, aunque según los resultados ya no
    funciona.», «…sale a las 10:00. Según los resultados, fue anulado.», «Apple lanzará el iPhone 18…, aunque los
    resultados no lo confirman oficialmente.»): a clause that narrates the search may say the decisive fact with words
    no page writes, and page_facts_dropped does not see it. Only a not-found may go with its negation: the negation
    denies a finding (a word of the narration right after it, «no se menciona», «no encontré») and the clause speaks of
    another thing the question asked, one the rest does not name («…, pero no se menciona ninguna adaptación para
    Bestiario ni Octaedro en los resultados»)."""

    words = _words()
    function = set(words["function_words"]) | set(words["clause_joining_words"])
    narration = set(words["clause_narration_words"])
    negations = set(words["negation_words"])
    results = [item for item in results if isinstance(item, dict)]
    sites = {
        label
        for item in results
        for label in re.split(r"[.\-]", fold(re.sub(r"^[a-z]+://", "", str(item.get("url") or "")).split("/", 1)[0]))
        if label
    }

    def content(word: str) -> bool:
        return len(word) >= 2 if word.isdigit() else len(word) >= 4 and word not in function and word not in narration

    def stem(word: str) -> str:
        return word if word.isdigit() else word[:_FACT_STEM]

    def stems(text: str) -> set[str]:
        return {stem(word) for word in _WORD.findall(fold(text)) if content(word)}

    tokens = _WORD.findall(fold(clause))
    rest_stems = stems(rest)
    asked = stems(question)
    said = rest_stems | asked | {stem(site) for site in sites if len(site) >= 4}
    unsaid: list[str] = []
    for word in tokens:
        if content(word) and stem(word) not in said and word not in unsaid:
            unsaid.append(word)
    denied = [index for index, word in enumerate(tokens) if word in negations or word.endswith(("n't", "n’t"))]
    if not denied:
        return unsaid
    first = denied[0]
    not_found = any(word in narration for word in tokens[first + 1: first + 4]) and any(
        content(word) and stem(word) in asked and stem(word) not in rest_stems for word in tokens
    )
    if not_found:
        return []
    return unsaid or [tokens[first]]


# Ronda 23 (pregunta-lee-lo-pertinente, live r21 v3-62: «which network is active» said done citing «El firewall está
# activado.», a line the window writes once per network, while «Red privada (activa)» marked the one asked): a word of
# the question and a word of the window share a root when they begin alike for four letters or more and differ in at
# most two more letters of the longer («active»/«activa», «plan»/«planes»; never «active»/«activado»), two of them
# never a consonant's derivation («activa»/«activado», revision 2).
_ROOT_HEAD = 4
_ROOT_TAIL = 2
_VOWELS = frozenset("aeiou")


def shares_root(left: str, right: str) -> bool:
    """Two folded words of one root, also between languages that spell it alike («active»/«activa»)."""

    if len(left) < _ROOT_HEAD or len(right) < _ROOT_HEAD:
        return False
    common = 0
    for one, other in zip(left, right):
        if one != other:
            break
        common += 1
    if common < _ROOT_HEAD or common < max(len(left), len(right)) - _ROOT_TAIL:
        return False
    # Revision 2 of ronda 23: two letters more that begin with a consonant derive another word of the root (the
    # participle «activado» of «activa», «activada» of «activas»), not its inflection («planes», «activos», «memoria»).
    rest = max(left, right, key=len)[common:]
    return not (len(rest) == _ROOT_TAIL and rest[0] not in _VOWELS)


def _content_words(text: str) -> list[str]:
    function = set(_words()["function_words"])
    return [word for word in re.split(r"[^\w]+", fold(text)) if len(word) >= _ROOT_HEAD and word not in function]


def _question_words(question: str) -> list[str]:
    """The content words of a question less the words with which it asks for its answer (revision 3 of ronda 23:
    «decime» is no root of «decimal», data ``request_words``)."""

    request = set(_words()["request_words"])
    return [word for word in dict.fromkeys(_content_words(question)) if word not in request]


def _bears(word: str, wanted: str) -> bool:
    """A word of the window carries a word of the question: one root, or that root denied by a prefix (revision 1 of
    ronda 23: «Desactivado» answers «decime si el bluetooth está activado» as much as «Activado» does)."""

    if shares_root(word, wanted):
        return True
    return any(
        (word.startswith(prefix) and shares_root(word[len(prefix):], wanted))
        or (wanted.startswith(prefix) and shares_root(word, wanted[len(prefix):]))
        for prefix in _words()["negation_prefixes"]
    )


def _borne(text: str, asked: Iterable[str]) -> set[str]:
    words = _content_words(text)
    return {wanted for wanted in asked if any(_bears(word, wanted) for word in words)}


def _holds(text: str, cited: str) -> bool:
    """``cited`` is part of ``text`` (whole words, folded) or the other way round, or both share a word of four
    letters or more («Equilibrado» of «Cambiar la configuración del plan Equilibrado»)."""

    one, other = fold(text), fold(cited)
    if not one or not other:
        return False
    if re.search(rf"(?<!\w){re.escape(other)}(?!\w)", one) or re.search(rf"(?<!\w){re.escape(one)}(?!\w)", other):
        return True
    return bool(set(_content_words(text)) & set(_content_words(cited)))


def citation_misses_question(cited: str, question: str, texts: Iterable[str], said: Iterable[str] = ()) -> bool:
    """A citation that proves a question answered does not carry its datum. ``texts`` are what the window writes, each
    a label with the value the window writes beside it («Memoria física instalada (RAM) 16,0 GB», «Volumen 75»), so a
    citation that is only the value is read with its label.

    - The window writes something sharing a root with a content word of the question (less the words ``said`` already,
      the goal's place and the window's title) and neither the citation nor a text holding it carries any such word
      (live r21 v3-62: «El firewall está activado.» for «which network is active» beside «Red privada (activa)»).
    - The citation carries only words of the question it says itself («Activado») where it is written, and the window
      writes another text carrying those and more of the question («Bluetooth Desactivado»): it is another control's
      mark (revision 1: «Swift Pair Activado» for «decime si el bluetooth está activado»).

    False when the window writes nothing of the question's words: then nothing tells the datum from the rest."""

    if not str(cited or "").strip():
        return False
    texts = [str(text or "") for text in texts if str(text or "").strip()]
    words = _question_words(question)
    told = {word for text in said for word in _content_words(text)}
    asked = [word for word in words if word not in told]
    holding = [text for text in texts if _holds(text, cited)]
    own = _borne(cited, words)
    beside = set().union(*(_borne(text, words) for text in holding)) - own
    if asked and any(_borne(text, asked) for text in texts):
        if not (own | beside) & set(asked):
            return True
    if beside or not own:
        return False
    return any(_borne(text, words) > own for text in texts)
