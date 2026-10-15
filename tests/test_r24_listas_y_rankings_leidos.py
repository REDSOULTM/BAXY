"""Ronda 24 «listas-y-rankings-leidos-de-la-pagina» (uso real v3, tandas r23).

Each failed turn with its real text, and the counter-cases that must stay as they are. The provider's half (the
page's ranking read as rows when a listing is asked) is in ExternalAdaptersTests
(AListingAskedReadsThePagesFirstRankingAsRows, AListingAskedCarriesTheRankingRowsOfTheFirstPages).
"""

from __future__ import annotations

from pathlib import Path

from baxy_mind import llm
from baxy_mind import payload_fact_checks
from baxy_mind import conversation_shape
from baxy_mind import talk_memory_figures
from baxy_mind import search_report
from baxy_mind.semantic import answer_evidence, listing
from baxy_mind import compose_facts
from baxy_mind import turn_followups

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "listing": {"type": ["boolean", "null"]},
        "nearby": {"type": ["boolean", "null"]},
        "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
    },
    "required": ["query"],
    "additionalProperties": False,
}
TOP5 = "cuales son las peliculas mas taquilleras de la historia? dame el top 5"
ANNEX = {
    "title": "Anexo:Películas con las mayores recaudaciones - Wikipedia, la ...",
    "url": "https://es.wikipedia.org/wiki/Anexo:Pel%C3%ADculas_con_las_mayores_recaudaciones",
    "snippet": (
        "La película más taquillera de la historia es Avengers: Endgame (2019) que logró recaudar 2 925 466 085 USD."
        " … 1. Avengers: Endgame · 2 926 549 214 · 2019 | 2. Avatar · 2 923 706 026 · 2009 | 3. Spider-Man: Brand"
        " New Day · 2 506 511 390 · 2026 | 4. Avatar: el sentido del agua · 2 320 250 281 · 2022 | 5. Titanic ·"
        " 2 264 750 694 · 1997"
    ),
}
GALLERY = {
    "title": "Las películas más taquilleras de la historia del cine",
    "url": "https://www.periodismo.com/2026/09/12/las-peliculas-mas-taquilleras-de-la-historia-del-cine/",
    "snippet": "En esta galería te presentamos el listado, desde 'Avengers' y 'Piratas del Caribe' hasta 'Rápidos y "
    "Furiosos' y 'Star Wars'. Bohemian Rhapsody (2018)",
}


def _payload(*results: dict) -> dict:
    return {
        "operation": "web.search",
        "askedCount": 5,
        "seen": {"query": TOP5, "count": len(results), "results": list(results), "authority": "duckduckgo_lite_https"},
    }


# --- t1-c03 #1: the listing asked travels to the provider, and a ranking's rows are a ranking -------------------------


def test_the_top_5_asks_the_provider_for_a_listing_of_five() -> None:
    assert compose_facts._with_asked_listing("web.search", {"query": TOP5}, TOP5, SEARCH_SCHEMA) == {
        "query": TOP5, "listing": True, "limit": 5,
    }


def test_counter_cases_carry_no_listing() -> None:
    # «quién ganó el mundial 2014» is no listing; «dame 3 ideas de nombre» is not searched (only web.search lists).
    asked = "quién ganó el mundial 2014"
    assert compose_facts._with_asked_listing("web.search", {"query": asked}, asked, SEARCH_SCHEMA) == {"query": asked}
    ideas = {"text": "dame 3 ideas de nombre"}
    assert compose_facts._with_asked_listing("conversation.reply", ideas, "dame 3 ideas de nombre", SEARCH_SCHEMA) is ideas


def test_the_rows_of_a_pages_ranking_are_one_ranking() -> None:
    report = "1. Avengers: Endgame\n2. Avatar\n3. Spider-Man: Brand New Day\n4. Avatar: el sentido del agua\n5. Titanic"
    assert answer_evidence.is_ranking(ANNEX)
    assert search_report._search_listing_not_from_one_ranking(report, _payload(ANNEX, GALLERY), TOP5) == []
    # Counter-case: names taken from two results (the annex's first and the gallery's) are still no one ranking.
    mixed = "1. Avengers: Endgame\n2. Piratas del Caribe\n3. Rápidos y Furiosos"
    assert search_report._search_listing_not_from_one_ranking(mixed, _payload(ANNEX, GALLERY), TOP5)


def test_the_retry_hint_no_longer_invites_a_first_from_a_snippet() -> None:
    # llm.py was split by responsibility: the retry hints now sit in its sibling modules.
    source = "".join(path.read_text(encoding="utf-8") for path in sorted(Path(llm.__file__).parent.glob("*.py")))
    assert "(por ejemplo cuál es la primera, si alguno lo dice)" not in source
    assert "which one is first, if a result says so" not in source
    assert "no nombres un primero a partir de una frase suelta" in source


# --- t1-c03 #2: «Lo único que afirma los resultados…» narrates the search ---------------------------------------------


def test_the_results_said_as_the_subject_that_states_are_the_search_shown() -> None:
    draft = "Lo único que afirma los resultados es que Avengers: Endgame (2019) es la más taquillera de la historia."
    assert answer_evidence.results_narrated(draft, "no wey te pedi 5 nomas")
    assert answer_evidence.results_narrated("The results say Avatar is first.")
    assert answer_evidence.results_narrated("Los resultados no muestran el top 5.")
    assert search_report._search_report_shows_the_search(draft, _payload(ANNEX), "no wey te pedi 5 nomas")


def test_counter_cases_of_the_narrated_results() -> None:
    # An answer that names no search stays; the person who asks about results (an election's) owns the word.
    assert not answer_evidence.results_narrated("Avengers: Endgame es la más taquillera de la historia.")
    assert not answer_evidence.results_narrated(
        "Los resultados muestran que ganó la lista A.", "cuáles fueron los resultados de las elecciones",
    )
    assert not search_report._search_report_shows_the_search(
        "1. Avengers: Endgame\n2. Avatar\n3. Spider-Man: Brand New Day", _payload(ANNEX), TOP5,
    )


# --- t3-c17 t1: the item keeps itself without the year from memory ----------------------------------------------------


def test_only_the_phrase_with_the_figure_goes() -> None:
    assert listing.without_figure_phrase(
        "2. El asesinato del archiduque Francisco Fernando en Sarajevo en 1914.", "1914",
    ) == "2. El asesinato del archiduque Francisco Fernando en Sarajevo."
    assert listing.without_figure_phrase("1. La Triple Alianza (1882) entre potencias.", "1882") == (
        "1. La Triple Alianza entre potencias."
    )
    assert listing.without_figure_phrase("3. The assassination in Sarajevo on 28 June 1914.", "1914") == (
        "3. The assassination in Sarajevo."
    )
    # Counter-case: a figure that is what the item says is no phrase of time or place; the item stays as it was.
    assert listing.without_figure_phrase("4. Murieron 17 millones de personas.", "17") == (
        "4. Murieron 17 millones de personas."
    )


def test_t3_c17_four_causes_stay_four_without_the_year() -> None:
    draft = (
        "1. El nacionalismo de las potencias europeas.\n"
        "2. El asesinato del archiduque Francisco Fernando en Sarajevo en 1914.\n"
        "3. El sistema de alianzas militares.\n"
        "4. El imperialismo y la carrera colonial."
    )
    kept = talk_memory_figures._without_memory_figures(draft, ["1914"])
    assert kept == (
        "1. El nacionalismo de las potencias europeas.\n"
        "2. El asesinato del archiduque Francisco Fernando en Sarajevo.\n"
        "3. El sistema de alianzas militares.\n"
        "4. El imperialismo y la carrera colonial."
    )
    four = listing.enumeration_asked("dame 4 causas de la primera guerra mundial")
    assert four is not None and four.count == 4
    assert not conversation_shape._enumeration_count_defect(kept, four)
    # Contracaso: the year itself stays vetoed.
    assert "1914" not in kept


def test_a_list_short_of_its_count_after_the_cut_is_a_defect() -> None:
    four = listing.enumeration_asked("dame 4 causas de la primera guerra mundial")
    short = talk_memory_figures._without_memory_figures(
        "1. El nacionalismo.\n2. Murieron 17 millones de personas.\n3. El imperialismo.\n4. Las alianzas.", ["17"],
    )
    assert short == "1. El nacionalismo.\n2. El imperialismo.\n3. Las alianzas."
    assert conversation_shape._figure_cut_left_the_list_short(
        "1. El nacionalismo.\n2. Murieron 17 millones de personas.\n3. El imperialismo.\n4. Las alianzas.", short, four,
    )


# --- Revisión 1, bloqueante 1: only a whole phrase of time or place goes, and no broken item is left ------------------


def test_a_figure_with_a_word_of_its_own_is_no_phrase_and_the_item_stays_as_it_was() -> None:
    # «En 1914, el archiduque…» would leave «2., el archiduque…»: the item stays as it was (it goes whole).
    assert listing.without_figure_phrase(
        "2. En 1914, el archiduque Francisco Fernando fue asesinado en Sarajevo.", "1914",
    ) == "2. En 1914, el archiduque Francisco Fernando fue asesinado en Sarajevo."
    assert listing.without_figure_phrase("1. Desde 1871, Francia buscaba revancha.", "1871") == (
        "1. Desde 1871, Francia buscaba revancha."
    )
    # «El año 1914 trajo…», «de 17 millones de personas»: the figure is followed by a word of its own.
    assert listing.without_figure_phrase("2. El año 1914 trajo el asesinato del archiduque.", "1914") == (
        "2. El año 1914 trajo el asesinato del archiduque."
    )
    assert listing.without_figure_phrase("2. La muerte de 17 millones de personas en el frente.", "17") == (
        "2. La muerte de 17 millones de personas en el frente."
    )
    # Counter-cases: a whole phrase before a mark or a joining word still goes.
    assert listing.without_figure_phrase("3. La crisis de los Balcanes en 1912 y la guerra.", "1912") == (
        "3. La crisis de los Balcanes y la guerra."
    )
    assert listing.without_figure_phrase("4. El tratado firmado en 1882, que unió a tres potencias.", "1882") == (
        "4. El tratado firmado, que unió a tres potencias."
    )


def test_the_reviewers_list_is_published_without_a_broken_marker_or_a_repeated_number() -> None:
    draft = (
        "1. El nacionalismo.\n2. En 1914, el archiduque Francisco Fernando fue asesinado en Sarajevo.\n"
        "3. El imperialismo.\n4. El sistema de alianzas."
    )
    kept = talk_memory_figures._without_memory_figures(draft, ["1914"])
    assert kept == "1. El nacionalismo.\n2. El imperialismo.\n3. El sistema de alianzas."
    four = listing.enumeration_asked("dame 4 causas de la primera guerra mundial")
    # Three left of the four the draft had: the cut is BAXY's, so it is not published (the reply is written again).
    assert conversation_shape._figure_cut_left_the_list_short(draft, kept, four)
    # Without a count asked, the item with «17 millones» goes whole; no «La muerte millones» is left.
    counted = "1. El nacionalismo.\n2. La muerte de 17 millones de personas en el frente.\n3. El imperialismo."
    assert talk_memory_figures._without_memory_figures(counted, ["17"]) == "1. El nacionalismo.\n2. El imperialismo."


# --- Revisión 1, bloqueante 2: an honest numbered list of a closed class is no defect ---------------------------------


def test_an_honest_numbered_list_of_a_closed_class_is_no_defect() -> None:
    four = listing.enumeration_asked("dame 4 paises de sudamerica que no tengan salida al mar")
    assert four is not None and not four.open
    assert not conversation_shape._enumeration_count_defect("1. Bolivia\n2. Paraguay", four)
    assert not conversation_shape._enumeration_count_defect(
        "Los países de Sudamérica sin salida al mar son:\n1. Bolivia\n2. Paraguay", four,
    )
    # Nor is it a list the figure cut left short: the draft itself listed two.
    assert not conversation_shape._figure_cut_left_the_list_short("1. Bolivia\n2. Paraguay", "1. Bolivia\n2. Paraguay", four)
    # Counter-case: four with one repeated is still a defect.
    assert conversation_shape._enumeration_count_defect("1. Bolivia\n2. Paraguay\n3. Bolivia\n4. Uruguay", four)


# --- t2-c09 #1: a closed class is told with what really meets it ------------------------------------------------------


def test_counter_cases_of_closed_and_full_lists() -> None:
    four = listing.enumeration_asked("dame 4 paises de sudamerica que no tengan salida al mar")
    assert four is not None and not four.open
    # «Solo hay 2: Bolivia y Paraguay» stays the honest answer.
    assert not conversation_shape._enumeration_count_defect("Solo hay 2: Bolivia y Paraguay.", four)
    three = listing.enumeration_asked("dame 3 paises de sudamerica con costa")
    assert three is not None
    assert not conversation_shape._enumeration_count_defect("1. Chile\n2. Perú\n3. Ecuador", three)


# --- Revisión 1, bloqueante 4 (3): a first is the first row of the ranking a result numbers ---------------------------


AVATAR_LOOSE = {
    "title": "Avatar, la película más taquillera de la historia",
    "url": "https://cine.example.org/avatar",
    "snippet": "Avatar es la película más taquillera de la historia, según la revista.",
}
LISTICLE = {
    "title": "Las 5 películas más taquilleras",
    "url": "https://otro.example.org/top",
    "snippet": "Repasamos el ranking. … 1. Avatar · 2009 | 2. Avengers: Endgame · 2019 | 3. Titanic · 1997",
}


def test_a_first_from_a_loose_sentence_is_vetoed() -> None:
    assert answer_evidence.ranking_firsts([ANNEX, AVATAR_LOOSE]) == ["avengers: endgame"]
    assert answer_evidence.first_claimed_unranked("La más taquillera es Avatar.", [ANNEX, AVATAR_LOOSE])
    assert search_report._search_listing_not_from_one_ranking(
        "La más taquillera es Avatar.", _payload(ANNEX, AVATAR_LOOSE), TOP5,
    )


def test_two_rankings_with_different_firsts_name_no_first() -> None:
    assert answer_evidence.first_claimed_unranked("La más taquillera es Avengers: Endgame.", [ANNEX, LISTICLE])


def test_counter_cases_of_the_first_claimed() -> None:
    # The ranking's own first, and a list's own lines, stay.
    assert not answer_evidence.first_claimed_unranked(
        "La más taquillera es Avengers: Endgame.", [ANNEX, AVATAR_LOOSE],
    )
    report = "1. Avengers: Endgame\n2. Avatar\n3. Spider-Man: Brand New Day\n4. Avatar: el sentido del agua\n5. Titanic"
    assert not answer_evidence.first_claimed_unranked(report, [ANNEX, AVATAR_LOOSE])
    assert search_report._search_listing_not_from_one_ranking(report, _payload(ANNEX, GALLERY), TOP5) == []
    # With no numbered ranking among the results, nothing is judged here.
    assert not answer_evidence.first_claimed_unranked("La más taquillera es Avatar.", [AVATAR_LOOSE, GALLERY])


# --- Revisión 2, bloqueante 1: a cut that leaves the items said again is no list ------------------------------------


def test_items_told_apart_only_by_their_year_go_whole_and_are_not_published_repeated() -> None:
    for draft, figures in (
        ("1. El Mundial de 1954.\n2. El Mundial de 1974.\n3. El Mundial de 2014.", ["1954", "1974", "2014"]),
        ("1. La Revolución de 1789.\n2. La Revolución de 1830.\n3. La Revolución de 1848.", ["1789", "1830", "1848"]),
        ("1. Los Juegos Olímpicos de 1908. 2. Los Juegos Olímpicos de 1948. 3. Los Juegos Olímpicos de 2012.",
         ["1908", "1948", "2012"]),
    ):
        kept = talk_memory_figures._without_memory_figures(draft, figures)
        # Each item goes whole with its figure (nothing is left, and the recovery takes the turn), as before the branch.
        assert kept == "", (draft, kept)
    three = listing.enumeration_asked("dame 3 mundiales que ganó Alemania")
    assert three is not None
    # Two told apart by their year and one by its words: the two go whole, the third keeps itself without its year.
    mixed = "1. El Mundial de 1954.\n2. El Mundial de 1974.\n3. La Eurocopa de Inglaterra en 1996."
    kept = talk_memory_figures._without_memory_figures(mixed, ["1954", "1974", "1996"])
    assert kept == "1. La Eurocopa de Inglaterra."
    assert conversation_shape._figure_cut_left_the_list_short(mixed, kept, three)
    # The belt: a cut that leaves an item said twice that the draft said once is not published.
    assert conversation_shape._figure_cut_repeated_items(mixed, "1. El Mundial.\n2. El Mundial.\n3. La Eurocopa.")
    # Counter-cases: items that stay distinct keep themselves without the year; a draft that already repeated is no cut.
    distinct = "1. El nacionalismo en 1914.\n2. El imperialismo.\n3. Las alianzas."
    assert talk_memory_figures._without_memory_figures(distinct, ["1914"]) == "1. El nacionalismo.\n2. El imperialismo.\n3. Las alianzas."
    assert not conversation_shape._figure_cut_repeated_items(distinct, "1. El nacionalismo.\n2. El imperialismo.\n3. Las alianzas.")
    assert not conversation_shape._figure_cut_repeated_items("1. A.\n2. A.\n3. B.", "1. A.\n2. A.\n3. B.")


# --- Revisión 2, bloqueante 2: a first said with a noun between its article and its superlative ----------------------


def test_a_first_said_the_natural_way_is_judged_too() -> None:
    for sentence in (
        "La película más taquillera de la historia es Avatar.",
        "Avatar es la película más taquillera.",
        "The highest-grossing film is Avatar.",
        "Avatar is the best-selling film of all time.",
    ):
        assert answer_evidence.says_first(sentence), sentence
        assert answer_evidence.first_claimed_unranked(sentence, [ANNEX, AVATAR_LOOSE]), sentence
        assert search_report._search_listing_not_from_one_ranking(sentence, _payload(ANNEX, AVATAR_LOOSE), TOP5), sentence
    # Counter-cases: the ranking's own first said the same ways, a second place, a plural that opens a list.
    assert not answer_evidence.first_claimed_unranked(
        "La película más taquillera de la historia es Avengers: Endgame.", [ANNEX, AVATAR_LOOSE],
    )
    assert not answer_evidence.first_claimed_unranked("Avengers: Endgame es la película más taquillera.", [ANNEX])
    assert not answer_evidence.says_first("Avatar es la segunda película más taquillera.")
    assert not answer_evidence.says_first("Las películas más taquilleras son estas:")
    assert not answer_evidence.says_first("Here are the five highest-grossing films:")
    assert not answer_evidence.says_first("La película tiene una trama más oscura.")


# --- Revisión 3, bloqueante 2: the line ending in a colon that opens the list names its first with line 1 ------------


ROWS = "1. Avengers: Endgame\n2. Avatar\n3. Spider-Man: Brand New Day\n4. Avatar: el sentido del agua\n5. Titanic"


def test_t1_c03_an_introduction_that_opens_the_right_list_is_no_veto() -> None:
    for intro in (
        "El top 5 de las películas más taquilleras es:",
        "Este es el top 5:",
        "El top 5 es este:",
        "The top 5 is:",
        "Here is the top 5:",
        "La lista más reciente es esta:",
        "La mejor forma de verlo es esta lista:",
    ):
        report = f"{intro}\n{ROWS}"
        assert not answer_evidence.first_claimed_unranked(report, [ANNEX, GALLERY]), intro
        assert search_report._search_listing_not_from_one_ranking(report, _payload(ANNEX, GALLERY), TOP5) == [], intro
    # Counter-cases: the introduction is read with the list's line 1, so a first other than the ranking's is still
    # judged; a loose sentence before the introduction is judged as before; a colon not followed by a list is no
    # introduction.
    wrong = "La más taquillera es:\n1. Avatar\n2. Avengers: Endgame\n3. Titanic"
    assert answer_evidence.first_claimed_unranked(wrong, [ANNEX, AVATAR_LOOSE])
    loose = f"La más taquillera es Avatar. Este es el top 5:\n{ROWS}"
    assert answer_evidence.first_claimed_unranked(loose, [ANNEX, AVATAR_LOOSE])
    assert answer_evidence.first_claimed_unranked("La más taquillera es:\nAvatar.", [ANNEX, AVATAR_LOOSE])


# --- Revisión 2, bloqueante 3: a cell that is only a number names no row; steps are no ranking of what is said --------


EN_WIKI = {
    "title": "List of highest-grossing films - Wikipedia",
    "url": "https://en.wikipedia.org/wiki/List_of_highest-grossing_films",
    "snippet": (
        "1. 1 · Avengers: Endgame † · $2,926,896,227 · 2019 | 2. 1 · Avatar · $2,923,706,026 · 2009 | 3. 3 · Avatar:"
        " The Way of Water · $2,320,250,281 · 2022"
    ),
}
STEPS = {
    "title": "Cómo ver las películas más taquilleras",
    "url": "https://guia.example.org/ver",
    "snippet": "Te contamos cómo verlas. … 1. Abre la app · 2. Busca la película · 3. Pulsa reproducir",
}


def test_the_peak_column_names_no_first_and_the_right_first_stays() -> None:
    assert answer_evidence.ranking_firsts([EN_WIKI]) == ["avengers: endgame †"]
    assert not answer_evidence.first_claimed_unranked("Avengers: Endgame tops the list.", [EN_WIKI])
    assert not answer_evidence.first_claimed_unranked("La más taquillera es Avengers: Endgame.", [ANNEX, EN_WIKI])
    # Counter-case: a wrong first is still vetoed against the same rows.
    assert answer_evidence.first_claimed_unranked("Avatar tops the list.", [EN_WIKI])


def test_numbered_steps_are_no_ranking_of_the_report() -> None:
    assert answer_evidence.ranking_firsts([STEPS]) == ["abre la app"]
    assert answer_evidence.ranking_firsts([STEPS], "La más taquillera es Avengers: Endgame.") == []
    assert not answer_evidence.first_claimed_unranked("La más taquillera es Avengers: Endgame.", [ANNEX, STEPS])
    assert not answer_evidence.first_claimed_unranked("La más taquillera es Avatar.", [STEPS, AVATAR_LOOSE])
    # Counter-case: the annex beside the steps still vetoes a first that is not its own.
    assert answer_evidence.first_claimed_unranked("La más taquillera es Avatar.", [ANNEX, STEPS])


# --- Revisión 2, bloqueante 5: «te pedí 5» after a turn that did not deliver them searches again ----------------------


class _Writer:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def compose_user_message(self, user_text: str, intent: str, facts: dict, *, said: str | None = None) -> str:
        self.calls += 1
        return self.reply


def _searched(told: str):
    from baxy_mind.semantic import dialogue

    situation = {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "query": "peliculas mas taquilleras de la historia", "count": 5, "results": []},
    }
    state = dialogue.DialogueState()
    state.expect(TOP5, ["web.search"])
    state.record(situation)
    state.told(situation, told)
    return state


def test_t1_c03_2_the_reproach_after_an_undelivered_listing_searches_again() -> None:
    text = "no wey te pedi 5 nomas"
    decided = {
        "type": "turn.result", "id": "t2", "kind": "action", "operation": "web.search",
        "intentOperations": ["web.search"], "effectOperations": ["web.search"], "question": "", "reply": "",
        "objective": TOP5,
    }
    for told in ("La más taquillera es Avengers: Endgame.", "No lo encontré."):
        state = _searched(told)
        assert state.repeats_the_last_plan(["web.search"], TOP5, text)
        writer = _Writer("Buscar de nuevo da lo mismo.")
        assert turn_followups._not_the_same_again(decided, {"id": "t2", "text": text}, state, writer) is decided, told
        assert writer.calls == 0
    # Counter-case: after the five told, looking again finds the same and that is said (no search again).
    state = _searched("1. Avengers: Endgame\n2. Avatar\n3. Titanic\n4. Star Wars\n5. Jurassic World")
    writer = _Writer("Son esas cinco. ¿Abro la búsqueda en tu navegador?")
    result = turn_followups._not_the_same_again(decided, {"id": "t2", "text": text}, state, writer)
    assert result["kind"] == "conversation" and writer.calls == 1


# --- Revisión 3, bloqueante 1: a right closed list is published as the model wrote it --------------------------------
#
# The item-by-item yes/no check of revisión 2 was taken out: asked of one item with the count in the question, the
# product model (granite-4.2-3b, llama-server b9980) answered «No» in 45 of 46 right items (one item is not «5
# planets»), so right lists ended without an answer or as a false «solo hay 2». A right closed list takes one call.


class _Writer1(llm.LlmRuntime):
    def __init__(self, replies: list[str]) -> None:  # noqa: D107
        self._gguf = "granite-4.2-3b-Q4_K_M.gguf"
        self.replies = iter(replies)
        self.payloads: list[dict] = []

    def _post(self, payload: dict, **_: object) -> dict:
        self.payloads.append(payload)
        return {"choices": [{"message": {"content": next(self.replies)}, "finish_reason": "stop"}]}


def test_a_right_closed_list_is_published_with_no_item_check() -> None:
    for asked, right, language in (
        ("dame 5 planetas del sistema solar", "1. Mercurio\n2. Venus\n3. Tierra\n4. Marte\n5. Júpiter", "es"),
        ("give me 3 planets of the solar system", "1. Mercury\n2. Venus\n3. Earth", "en"),
        ("dame 3 paises de sudamerica con costa", "1. Chile\n2. Perú\n3. Ecuador", "es"),
        ("dame 3 rios de europa", "1. Danubio\n2. Rin\n3. Sena", "es"),
    ):
        client = _Writer1([right])
        final, _ = client.chat(asked, history=[], conversation_kind="knowledge", response_language=language)
        assert final == right, asked
        assert len(client.payloads) == 1, asked
    assert not hasattr(llm, "_closed_item_question")
    # Counter-case: a closed list off its count is still written again (the count check of the ronda stays).
    four = listing.enumeration_asked("dame 4 paises de sudamerica que no tengan salida al mar")
    assert conversation_shape._enumeration_count_defect("1. Bolivia\n2. Paraguay\n3. Uruguay\n4. Surinam\n5. Chile", four)


# --- Revisión 4, bloqueante 1: the numbered top N the hint asks for is published end to end ---------------------------


class _Drafts(llm.LlmRuntime):
    """A writer that answers the given drafts in order (the compose chain whole, every veto on)."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.calls = 0

    def _post(self, payload: dict, **_: object) -> dict:
        self.calls += 1
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _composed(said: str, results: list[dict], drafts: list[str], asked: int | None = 5) -> tuple[str, int]:
    import json

    situation = {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {"version": 1, "query": said, "count": len(results), "results": results},
    }
    if asked is not None:
        situation["askedCount"] = asked
    writer = _Drafts(drafts)
    final = writer.compose_user_message(
        said, "status", {"situation": json.dumps(situation, ensure_ascii=False)}, said=said,
    )
    return final, writer.calls


def test_r4_t1_c03_the_numbered_top_5_is_published_and_not_denied() -> None:
    for draft in (ROWS, f"El top 5 de las películas más taquilleras es:\n{ROWS}"):
        final, calls = _composed(TOP5, [ANNEX, GALLERY], [draft, draft, draft])
        assert final == draft, final
        assert calls == 1
        assert payload_fact_checks._payload_fact_defect(draft, _payload(ANNEX, GALLERY), TOP5) == ""


def test_estabilizacion_r6_a_search_report_is_judged_by_what_it_says_not_by_its_length() -> None:
    # Estabilización R6 (libro de vetos y guardas §5 R6; r23_redpc t3-c14: three recipes asked, the three drafts died
    # as «search_report_runs_long» and the final was a false «No lo encontré.»): the length of a web answer is the
    # composer's (max_tokens 120, test_uso_real_tanda05_weather_web_reports), never a veto. The listing asked and short
    # prose taken from the pages are published; prose that shows the lookup is still vetoed by its own rule.
    assert payload_fact_checks._payload_fact_defect(ROWS, _payload(ANNEX), TOP5) == ""
    assert payload_fact_checks._payload_fact_defect("Avatar. Titanic. Endgame.", _payload(ANNEX), TOP5) == ""
    assert payload_fact_checks._payload_fact_defect(
        f"Busqué el ranking. Lo encontré en Wikipedia. Este es el top 5:\n{ROWS}", _payload(ANNEX), TOP5,
    ) == "search_report_shows_the_search"


# --- Revisión 4, bloqueante 2: one first written two ways is one first; an introduction opens its list ----------------


RANK_A = {
    "title": "Ranking A", "url": "https://a.example.org/top",
    "snippet": "1. Avatar · 2009 | 2. Avengers: Endgame · 2019 | 3. Titanic",
}
RANK_B = {
    "title": "Ranking B", "url": "https://b.example.org/top",
    "snippet": "1. Avatar (película de 2009) · 2 923 | 2. Avengers: Endgame · 2 799 | 3. Titanic · 2 264",
}


def test_r4_the_same_first_written_two_ways_is_no_disagreement() -> None:
    top3 = "1. Avatar\n2. Avengers: Endgame\n3. Titanic"
    for report in (f"{top3}\nAvatar es la más taquillera de la historia.", f"Este es el top 3:\n{top3}"):
        assert not answer_evidence.first_claimed_unranked(report, [RANK_A, RANK_B]), report
    assert answer_evidence._same_entry("avatar (2009)", "avatar de james cameron")
    # Counter-cases: two films that share a word are two firsts; a first neither ranking gives is still vetoed.
    assert not answer_evidence._same_entry("avengers: endgame", "avengers: infinity war")
    assert answer_evidence.first_claimed_unranked("La más taquillera es Titanic.", [RANK_A, RANK_B])


def test_r4_an_introduction_that_opens_one_rankings_list_is_no_claim() -> None:
    for intro in ("Este es el top 5:", "El top 5 es:", "Here is the top 5:"):
        report = f"{intro}\n{ROWS}"
        assert not answer_evidence.first_claimed_unranked(report, [ANNEX, LISTICLE]), intro
        assert not answer_evidence.first_claimed_unranked(ROWS, [ANNEX, LISTICLE])
    # Counter-cases: with two rankings that disagree a loose first stays vetoed, and an introduction whose list opens
    # with no ranking's first is still judged.
    assert answer_evidence.first_claimed_unranked("La más taquillera es Avengers: Endgame.", [ANNEX, LISTICLE])
    assert answer_evidence.first_claimed_unranked(
        "La más taquillera es:\n1. Titanic\n2. Avatar", [ANNEX, LISTICLE],
    )


# --- Revisión 4, bloqueante 3: a phrase between two terms goes whole or stays -----------------------------------------


def test_r4_a_between_phrase_goes_whole_with_its_second_term() -> None:
    draft = "1. La guerra en Europa entre 1914 y 1918.\n2. El nacionalismo.\n3. El imperialismo.\n4. Las alianzas."
    assert talk_memory_figures._without_memory_figures(draft, ["1914"]) == (
        "1. La guerra en Europa.\n2. El nacionalismo.\n3. El imperialismo.\n4. Las alianzas."
    )
    assert listing.without_figure_phrase("1. La gripe se extendió entre 1914 y 1918.", "1914") == (
        "1. La gripe se extendió."
    )
    assert listing.without_figure_phrase("1. The war in Europe between 1914 and 1918.", "1914") == (
        "1. The war in Europe."
    )
    # Counter-cases: a between whose second term is no figure is left as it was (never «…entre y Rusia»); an item
    # with no between keeps its old cut; the second term alone from memory leaves the item as it was.
    for item in ("1. La guerra entre 1914 y la revolución rusa.", "1. La guerra entre 1914 y 1918."):
        figure = "1914" if "rusa" in item else "1918"
        assert listing.without_figure_phrase(item, figure) == item, item
    assert listing.without_figure_phrase("1. El nacionalismo en 1914 y el imperialismo.", "1914") == (
        "1. El nacionalismo y el imperialismo."
    )
