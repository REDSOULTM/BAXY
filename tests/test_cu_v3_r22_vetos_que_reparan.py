"""Ronda 22, palanca «vetos que reparan sin rehacer» (pasada r18, cu-v3/tandas_r20/analisis_todas.md M1 y nº 5).

Un veto que gana una cláusula ya no tira el borrador entero: se quita esa cláusula y se vuelve a juzgar (``_draft_clauses``
/ ``_without_clause``); las cifras se comparan sin separadores de miles y con el redondeo marcado; la moneda de una
cifra no es un nombre de la lista; lo dicho dos veces seguidas se veta en toda etapa del compose (revisión 2: la charla
no se poda; un rótulo por sección, un paso o un hablante repetido no son repetición; la cláusula que se quita no puede
traer un hecho de las páginas); una línea que es sólo un título no tiene idioma; con un borrador ya rechazado el último recurso es el
no-encontrado y no «se me acabó el tiempo»; «No encontré si de Bestiario…» en minúscula.

Borradores y resultados de los compose_audit / raw_replies reales de tandas_r20 (t1-c03, t3-c03, t3-c17, t4-c02)."""

from __future__ import annotations

import json

import pytest

from baxy_mind import llm, operation_floor
from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect
from baxy_mind import talk_memory_figures
from baxy_mind import search_report
from baxy_mind.semantic import answer_evidence, listing, quantities, web

# ---------------------------------------------------------------- t1-c03 «dame el top 5» (compose_audit t1, t9)
TOP5_SAID = "cuales son las peliculas mas taquilleras de la historia? dame el top 5"
TOP5_RESULTS = [
    {"title": "Anexo:Películas con las mayores recaudaciones - Wikipedia, la ...",
     "url": "https://es.wikipedia.org/wiki/Anexo:Pel%C3%ADculas_con_las_mayores_recaudaciones",
     "snippet": "Películas con las mayores recaudaciones La película más taquillera de la historia es Avengers: Endgame "
                "(2019) que logró recaudar 2 925 466 085 USD. … Otro dato relevante es que las recaudaciones de la "
                "mayoría de las películas del chequeo que aparece a continuación provienen principalmente de su "
                "exhibición internacional; solo existen 6 casos en que la recaudación en Estados Unidos y Canadá superó "
                "a la internacional: E.T., el extraterrestre (1982), The Dark Knight (2008), Rogue One: una historia de "
                "Star Wars (2016), Wonder Woman (2017), Black Panther (2018) y Black Panther: Wakanda Forever (2022)."},
    {"title": "Las películas más taquilleras de la historia", "url": "https://www.lacartelera.com/es/mas-taquilleras/",
     "snippet": "Ranking de las películas que más dinero han recaudado en taquilla mundial, en total y por década."},
    {"title": "¿Cuáles son las 5 películas más taquilleras de la historia?",
     "url": "https://www.clarin.com/internacional/5-peliculas-taquilleras-historia_0_aEHtullgYq.html",
     "snippet": "Muchas fueron y serán inolvidables, pero no todas resultaron un éxito de taquilla.Aquí, las películas que "
                "más millones recaudaron en la historia del cine."},
    {"title": "Las películas más taquilleras de la historia del cine", "url": "https://www.infobae.com/galeria",
     "snippet": "En esta galería te presentamos el listado de los filmes que más millones de dólares recaudaron, que "
                "incluye desde 'Avengers' y 'Piratas del Caribe' hasta 'Rápidos y Furiosos' y 'Star Wars'. Bohemian "
                "Rhapsody (2018) […]"},
]
TOP5_PAYLOAD = {
    "operation": "web.search", "askedCount": 5,
    "seen": {"query": TOP5_SAID, "count": len(TOP5_RESULTS), "authority": "duckduckgo_lite_https",
             "results": TOP5_RESULTS},
}


def _top5_defect(draft: str) -> str:
    return payload_fact_checks._payload_fact_defect(draft, TOP5_PAYLOAD, TOP5_SAID)


@pytest.mark.parametrize(
    "draft",
    [
        # third: one film with its currency was read as a listing of two («Avengers Endgame», «USD»).
        "La película más taquillera de la historia es Avengers: Endgame, con una recaudación de 2 925 466 085 USD.",
        # the same figure with another separator of thousands.
        "La película más taquillera de la historia es Avengers: Endgame, con una recaudación de 2.925.466.085 USD.",
        # retry: a rounding the report marks as one.
        "Avengers: Endgame es la película más taquillera de la historia con casi 3 mil millones de dólares.",
        # t10 third: BAXY's own not-found clause claims nothing of the pages.
        "La película más taquillera es Avengers: Endgame y no encontré el listado completo.",
    ],
)
def test_t1_c03_the_grounded_drafts_now_pass(draft):
    assert _top5_defect(draft) == "", draft


def test_t1_c03_the_currency_of_a_figure_is_no_listed_name():
    draft = "La película más taquillera de la historia es Avengers: Endgame, con una recaudación de 2 925 466 085 USD."
    assert answer_evidence.answer_spans(draft, TOP5_SAID, "") == ["Avengers Endgame"]
    assert quantities.unit_of_a_figure(draft, "USD")
    # A name that is no unit is never taken for one, even next to a figure.
    assert not quantities.unit_of_a_figure("Avatar 2 recaudó mucho.", "Avatar")


@pytest.mark.parametrize(
    "draft",
    [
        # Contracaso: an invented figure without «casi» is still the model's.
        "Avengers: Endgame es la película más taquillera de la historia con 3 mil millones de dólares.",
        # Contracaso: a marked rounding far from every figure of the pages is still invented.
        "Avengers: Endgame es la película más taquillera de la historia con casi 4 mil millones de dólares.",
    ],
)
def test_t1_c03_an_unmarked_or_far_figure_is_still_refused(draft):
    assert _top5_defect(draft) == "search_report_unsourced_claim", draft


def test_t1_c03_a_top3_from_two_pages_is_still_refused():
    # Contracaso: one name from the encyclopedia and two from the photo gallery, no ranking names them all.
    draft = "Las más taquilleras son Avengers: Endgame, Piratas del Caribe y Bohemian Rhapsody."
    assert _top5_defect(draft) == "search_listing_not_one_ranking"


def test_marked_roundings_read_scale_and_separators():
    assert quantities.marked_roundings("casi 3 mil millones", "2 925 466 085 USD") == ["3"]
    assert quantities.marked_roundings("about 3 billion", "2,925,466,085") == ["3"]
    assert quantities.marked_roundings("3 mil millones", "2 925 466 085") == []
    assert quantities.marked_roundings("casi 4 mil millones", "2 925 466 085") == []
    assert quantities.without_digit_groups("2 925 466 085 y 2.925.466.085 y 3,5") == "2925466085 y 2925466085 y 3,5"


def test_981_chilean_pesos_still_pass():
    # Contracaso M146: «981.19 CLP» said as «981.19 pesos chilenos».
    payload = {"operation": "web.search", "seen": {"query": "dolar hoy", "results": [
        {"title": "Tipo de cambio de referencia", "url": "https://api.frankfurter.app/latest",
         "snippet": "1 USD = 981.19 CLP"}]}}
    said = "oye, ¿me podrias decir a como anda el dolar hoy?"
    assert not search_report._search_report_unsourced_claim("Hoy el dólar está a 981.19 pesos chilenos.", payload, said)


# ---------------------------------------------------------------- reparación por cláusula (t4-c02 t3, t1-c03 t10)
class _Drafts(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then fails with ``error`` (time ran out by default)."""

    def __init__(self, drafts: list[str], error: OSError | None = None) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.error = error
        self.calls = 0

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.calls += 1
        if not self.drafts:
            raise self.error or TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


CORTAZAR_SAID = "y de bestiario, rayuela u octaedro hay pelicula?"
CORTAZAR_RESULTS = [
    {"title": "Andábamos sin buscarnos - película basada en Rayuela", "url": "https://es.wikipedia.org/wiki/Rayuela",
     "snippet": "Andábamos sin buscarnos es una película basada en Rayuela, la novela de Julio Cortázar."},
    {"title": "Bestiario (libro) - Wikipedia", "url": "https://es.wikipedia.org/wiki/Bestiario_(libro)",
     "snippet": "Bestiario es el primer libro de cuentos de Julio Cortázar, publicado en 1951."},
]


def _situation(results: list[dict], query: str) -> dict:
    return {"kind": "operation", "operation": "web.search", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "query": query, "count": len(results), "results": results}}


def _compose(said: str, situation: dict, drafts: list[str], error: OSError | None = None) -> tuple[str, int]:
    writer = _Drafts(drafts, error)
    final = writer.compose_user_message(
        said, "status", {"situation": json.dumps(situation, ensure_ascii=False)}, said=said,
    )
    return final, writer.calls


def test_t4_c02_the_clause_that_narrates_the_search_is_dropped_and_the_answer_kept():
    draft = ('Sí, hay una película llamada "Andábamos sin buscarnos" basada en Rayuela, pero no se menciona ninguna '
             "adaptación para Bestiario ni Octaedro en los resultados.")
    situation = _situation(CORTAZAR_RESULTS, "pelicula de bestiario rayuela octaedro")
    final, calls = _compose(CORTAZAR_SAID, situation, [draft])
    assert final == 'Sí, hay una película llamada "Andábamos sin buscarnos" basada en Rayuela.'
    assert calls == 1


def test_a_draft_that_only_narrates_the_search_is_still_refused():
    # Contracaso: nothing is left once the narration goes; the draft is written again.
    draft = "No hay información en los resultados sobre la película más taquillera de la historia."
    situation = _situation(TOP5_RESULTS, TOP5_SAID)
    final, calls = _compose("quien dirigio la pelicula mas taquillera de la historia", situation, [draft, "", ""])
    assert final != draft
    assert calls >= 3


def _news(snippet: str) -> list[dict]:
    return [{"title": "Noticia", "url": "https://www.noticias.example/nota", "snippet": snippet}]


FLIGHT_SAID = "a que hora sale el vuelo la800 a madrid"
FLIGHT_RESULTS = _news("El vuelo LA800 a Madrid, programado para las 10:00, fue cancelado.")
PLACE_SAID = "donde queda la picada de don pepe"
PLACE_RESULTS = _news("La Picada de Don Pepe, en calle Curicó 123, Ñuñoa, cerró definitivamente en marzo.")
RUMOR_SAID = "cuando sale el iphone 18"
RUMOR_RESULTS = _news("Según rumores, Apple lanzaría el iPhone 18 en septiembre de 2026.")


@pytest.mark.parametrize(
    "said, results, draft, false_answer",
    [
        (FLIGHT_SAID, FLIGHT_RESULTS,
         "El vuelo LA800 a Madrid sale a las 10:00. En los resultados aparece que fue cancelado.",
         "El vuelo LA800 a Madrid sale a las 10:00."),
        (FLIGHT_SAID, FLIGHT_RESULTS,
         "El vuelo LA800 a Madrid estaba programado para las 10:00, pero los resultados indican que fue cancelado.",
         "El vuelo LA800 a Madrid estaba programado para las 10:00."),
        (PLACE_SAID, PLACE_RESULTS,
         "La Picada de Don Pepe está en calle Curicó 123, Ñuñoa, pero según los resultados cerró "
         "definitivamente en marzo.",
         "La Picada de Don Pepe está en calle Curicó 123, Ñuñoa."),
        (RUMOR_SAID, RUMOR_RESULTS,
         "Apple lanzaría el iPhone 18 en septiembre de 2026, aunque en los resultados es sólo un rumor.",
         "Apple lanzaría el iPhone 18 en septiembre de 2026."),
    ],
)
def test_a_clause_that_narrates_the_search_and_carries_the_decisive_fact_is_not_dropped(
    said, results, draft, false_answer,
):
    # Contracaso de la revisión 2: a cancellation, a closure or a rumour told with the search narrated is the answer;
    # dropping that clause publishes the opposite. The draft is written again, as in the base (calls=2).
    final, calls = _compose(said, _situation(results, said), [draft])
    assert final != false_answer
    assert calls == 2


def test_page_facts_dropped_reads_the_pages_not_the_narration():
    assert answer_evidence.page_facts_dropped(
        "En los resultados aparece que fue cancelado.", "El vuelo LA800 a Madrid sale a las 10:00.", FLIGHT_SAID,
        FLIGHT_RESULTS,
    ) == ["cancelado"]
    # The narration alone, the site's name or what the person asked bring nothing of the pages.
    assert answer_evidence.page_facts_dropped(
        "Según la Wikipedia, ", "La más taquillera es Avengers: Endgame.", TOP5_SAID, TOP5_RESULTS,
    ) == []
    assert answer_evidence.page_facts_dropped(
        ", pero no se menciona ninguna adaptación para Bestiario ni Octaedro en los resultados",
        'Sí, hay una película llamada "Andábamos sin buscarnos" basada en Rayuela.', CORTAZAR_SAID, CORTAZAR_RESULTS,
    ) == []


def test_clauses_of_a_draft():
    text = "Según la Wikipedia, la más taquillera es Avengers: Endgame, pero no encontré el listado completo."
    spans = search_report._draft_clauses(text)
    rests = [search_report._without_clause(text, span) for span in spans]
    assert "La más taquillera es Avengers: Endgame, pero no encontré el listado completo." in rests
    assert "Según la Wikipedia, la más taquillera es Avengers: Endgame." in rests


def test_a_list_line_dropped_renumbers_the_list():
    text = "1. Among Us\n2. Brawl Stars\n3. Portal 2"
    assert search_report._without_clause(text, search_report._draft_clauses(text)[1]) == "1. Among Us\n2. Portal 2"


# ---------------------------------------------------------------- t2-c01 t4: no «se me acabó el tiempo» tras un rechazo
def test_t2_c01_after_a_refused_draft_the_time_sentence_is_not_said():
    said = "cuantos discos de estudio tienen los bunkers"
    situation = _situation(
        [{"title": "Los Bunkers - Wikipedia", "url": "https://es.wikipedia.org/wiki/Los_Bunkers",
          "snippet": "Los Bunkers es una banda chilena de rock formada en Concepción."}],
        said,
    )
    # The first draft is refused (a figure no page gives), the retry runs out of the budget.
    final, _ = _compose(said, situation, ["Los Bunkers tienen 7 discos de estudio."])
    untold = operation_floor.floor_data()["searchUntold"]["es"].values()
    assert all(final != template.format(clause="cuántos discos de estudio tienen Los Bunkers") for template in untold)
    assert "tiempo" not in final
    assert final.startswith("No encontré")


def test_without_any_draft_the_time_that_ran_out_is_still_said():
    # Contracaso r19b: no draft was ever written; the time sentence stays.
    said = "cuantos discos de estudio tienen los bunkers"
    situation = _situation(
        [{"title": "Los Bunkers - Wikipedia", "url": "https://es.wikipedia.org/wiki/Los_Bunkers",
          "snippet": "Los Bunkers es una banda chilena de rock formada en Concepción."}],
        said,
    )
    final, _ = _compose(said, situation, [])
    assert "tiempo" in final


# ---------------------------------------------------------------- lo dicho dos veces (t4-c02 t2, t2-c02, t4-c08)
@pytest.mark.parametrize(
    "text, repeated",
    [
        ("Bestiario, Rayuela y Rayuela son libros de Julio Cortázar.", "Rayuela"),
        ("Lleva arroz, leche de coco, leche de coco y curry.", "leche de coco"),
        ("La película más taquillera de la historia de la historia no se menciona.", "de la historia"),
        ("1. Rayuela\n2. Bestiario\n3. Rayuela", "Rayuela"),
    ],
)
def test_a_thing_said_twice_in_a_row_is_found(text, repeated):
    assert listing.duplicated_run(text) == repeated


@pytest.mark.parametrize(
    "text",
    [
        # Contracaso: «Rayuela» in two sentences is said once in each.
        "Rayuela es de Cortázar. Hay una película basada en Rayuela.",
        "No, no lo encontré.",
        "Es muy muy rápido.",
        "Viajé a Bora Bora.",
        "Es la historia de la historia del arte.",
    ],
)
def test_what_is_not_a_repeat(text):
    assert listing.duplicated_run(text) == ""


def test_t4_c02_the_third_draft_with_a_repeat_is_refused_at_every_stage():
    situation = _situation(
        [{"title": "Libros de Julio Cortázar", "url": "https://es.wikipedia.org/wiki/Julio_Cort%C3%A1zar",
          "snippet": "Entre sus libros están Bestiario, Rayuela y Octaedro."}],
        "libros de julio cortazar",
    )
    final, _ = _compose(
        "dame 3 libros de cortazar", situation,
        ["Bestiario, Rayuela y Rayuela son libros de Julio Cortázar."] * 3,
    )
    assert "Rayuela y Rayuela" not in final


class _Talk(llm.LlmRuntime):
    """A talk writer that answers the given drafts in order, then runs out of time."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.calls = 0

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.calls += 1
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _talk(said: str, reply: str) -> tuple[str, int]:
    writer = _Talk([reply])
    final, _ = writer.chat(said, history=[], conversation_kind="knowledge", response_language="es", temperature=0.0)
    return final, writer.calls


@pytest.mark.parametrize(
    "said, reply",
    [
        # Revisión 2: the talk is not pruned. A speaker who talks again, a step done twice, a label in two sections, a
        # food in two meals or an item doubled is published as written (base: one call, as written).
        ("escribe un dialogo corto entre ana y juan", "- Ana: Hola, ¿cómo estás?\n- Juan: Bien, ¿y tú?\n- Ana: Muy bien."),
        ("como reinicio el router", "1. Desenchúfalo.\n2. Espera 30 segundos.\n3. Enchúfalo.\n4. Espera 30 segundos."),
        ("como entro a mi cuenta", "1. Presiona Enter.\n2. Escribe tu contraseña.\n3. Presiona Enter."),
        ("compara el iphone 15 y el galaxy s24",
         "**iPhone 15:**\n- Precio: alto\n- Batería: buena\n\n**Galaxy S24:**\n- Precio: medio\n- Batería: muy buena"),
        ("dame un menu para el dia", "**Desayuno:**\n- Fruta\n- Pan\n\n**Cena:**\n- Fruta\n- Sopa"),
        ("dame una receta de curry", "Lleva arroz, leche de coco, leche de coco y curry."),
    ],
)
def test_the_talk_keeps_every_line_it_was_written_with(said, reply):
    # Revisión 2 de r24: every line is kept as written; only the markdown emphasis («**iPhone 15:**») is written plain
    # (listing.without_emphasis), as the writer is told. Lines, words and the number of calls stay as before.
    assert _talk(said, reply) == (listing.without_emphasis(reply), 1)
    assert listing.without_emphasis(reply).splitlines() == [
        line.replace("**", "") for line in reply.splitlines()
    ]


@pytest.mark.parametrize(
    "text",
    [
        # Revisión 2: a label written again in another section, or with another value, names nothing twice; a list of
        # steps or a dialogue's lines may say one twice.
        "**iPhone 15:**\n- Precio: alto\n- Batería: buena\n\n**Galaxy S24:**\n- Precio: medio\n- Batería: muy buena",
        "**Desayuno:**\n- Fruta\n- Pan\n\n**Cena:**\n- Fruta\n- Sopa",
        "- Ventaja: barato\n- Ventaja: rápido\n- Desventaja: frágil",
        "- Ana: Hola, ¿cómo estás?\n- Juan: Bien, ¿y tú?\n- Ana: Muy bien.",
        "1. Desenchúfalo\n2. Espera 30 segundos\n3. Enchúfalo\n4. Espera 30 segundos",
        "1. Pon el agua a hervir.\n2. Agrega la pasta.\n3. Pon el agua a hervir.",
    ],
)
def test_a_label_in_two_sections_a_step_or_a_speaker_said_again_is_no_repeat(text):
    assert listing.duplicated_run(text) == ""


@pytest.mark.parametrize(
    "text, repeated",
    [
        # Contracaso: a list of names that names one twice inside one section is still a repeat.
        ("- Toy Story\n- Cars\n- Toy Story", "Toy Story"),
        ("**Novelas:**\n1. Rayuela\n2. Bestiario\n3. Rayuela", "Rayuela"),
        ("1. **Rayuela**: novela\n2. **Bestiario**: cuentos\n3. **Rayuela**: novela", "Rayuela"),
    ],
)
def test_a_name_listed_twice_in_one_section_is_still_a_repeat(text, repeated):
    assert listing.duplicated_run(text) == repeated


COMPARISON_SAID = "que diferencia hay entre el iphone 15 y el galaxy s24 en precio y bateria"
COMPARISON_RESULTS = [
    {"title": "iPhone 15 vs Galaxy S24", "url": "https://www.comparativas.example/iphone-15-vs-galaxy-s24",
     "snippet": "iPhone 15: precio alto, batería buena. Galaxy S24: precio medio, batería muy buena."},
]


def test_a_comparison_with_one_label_per_section_is_published_first_time():
    # Revisión 2 (base: calls=1; the branch read «Precio» as said twice, vetoed every draft and published a false
    # «No encontré…»).
    draft = "**iPhone 15:**\n- Precio: alto\n- Batería: buena\n\n**Galaxy S24:**\n- Precio: medio\n- Batería: muy buena"
    final, calls = _compose(COMPARISON_SAID, _situation(COMPARISON_RESULTS, COMPARISON_SAID), [draft])
    assert final == draft
    assert calls == 1


# ---------------------------------------------------------------- t3-c03: un título en inglés no es una frase en inglés
GAMES = "1. Among Us\n2. Garry's Mod\n3. Deep Rock Galactic\n4. It Takes Two\n5. Portal 2"


def test_t3_c03_a_list_of_titles_is_no_english_reply():
    assert not visible_defect._reply_uses_opposite_language(GAMES, "es")
    assert listing.title_only("4. It Takes Two")
    assert listing.title_only("El Señor de los Anillos")


@pytest.mark.parametrize(
    "text",
    [
        "You can play Among Us, Portal 2 and It Takes Two with your friends.",
        "1. Among Us is a social deduction game.\n2. Portal 2 is a puzzle game.",
    ],
)
def test_an_english_answer_to_a_spanish_request_is_still_refused(text):
    assert visible_defect._reply_uses_opposite_language(text, "es")
    assert not listing.title_only(text.split("\n")[0])


# ---------------------------------------------------------------- t3-c17 t1: «1. 2. El bloqueo…»
def test_t3_c17_the_item_with_a_memory_figure_keeps_itself_without_it_and_no_marker_is_left_alone():
    # Ronda 24 (r23 t3-c17 t1, «dame 4 causas…» → three): the item no longer goes whole when its figure is only a
    # phrase of time («en 1914»); that phrase goes, the item stays, and no empty «1.» is left (the r22 fault).
    retry = ("1. El asalto de Bosnia por Serbia en 1914. 2. El bloqueo naval alemán. 3. La invasión de Bélgica por "
             "Alemania. 4. La declaración de guerra de Rusia a Alemania.")
    kept = talk_memory_figures._without_memory_figures(retry, ["1914"])
    assert kept == ("1. El asalto de Bosnia por Serbia. 2. El bloqueo naval alemán. 3. La invasión de Bélgica por "
                    "Alemania. 4. La declaración de guerra de Rusia a Alemania.")
    lines = ("1. El asalto de Bosnia por Serbia en 1914.\n2. El asesinato del archiduque Francisco Fernando.\n"
             "3. La formación de alianzas militares entre potencias.")
    assert talk_memory_figures._without_memory_figures(lines, ["1914"]) == (
        "1. El asalto de Bosnia por Serbia.\n2. El asesinato del archiduque Francisco Fernando.\n"
        "3. La formación de alianzas militares entre potencias."
    )
    # An item whose figure is what it says still goes whole, and the list is numbered again.
    counted = ("1. Murieron 17 millones de personas.\n2. El asesinato del archiduque Francisco Fernando.\n"
               "3. La formación de alianzas militares entre potencias.")
    assert talk_memory_figures._without_memory_figures(counted, ["17"]) == (
        "1. El asesinato del archiduque Francisco Fernando.\n2. La formación de alianzas militares entre potencias."
    )


def test_a_reply_whose_only_content_is_the_figure_is_still_nothing():
    # Contracaso: «Tiene 1.100 km» from memory leaves nothing.
    assert talk_memory_figures._without_memory_figures("Tiene 1.100 km.", ["1.100"]) == ""
    assert talk_memory_figures._without_memory_figures("Mide 300 metros. Es una torre de hierro.", ["300"]) == "Es una torre de hierro."


# ---------------------------------------------------------------- t4-c02 t3: «No encontré si de Bestiario…»
def test_searched_clause_lowers_the_opening_function_word():
    clause, asked = web.searched_clause("De Bestiario, Rayuela o Octaedro hay película?", "es")
    assert clause.startswith("si de Bestiario")
    assert asked
    # A name that opens the question keeps its capital.
    clause, _ = web.searched_clause("Star Wars tiene película animada?", "es")
    assert clause.startswith("si Star Wars")


# ---------------------------------------------------------------- revisión 1: secuelas, estribillos y fechas
PIXAR_SAID = "cuales fueron las dos primeras peliculas de pixar"
PIXAR_RESULTS = [
    {"title": "Anexo:Películas de Pixar - Wikipedia", "url": "https://es.wikipedia.org/wiki/Anexo:Pel%C3%ADculas_de_Pixar",
     "snippet": "Pixar estrenó Toy Story en 1995 y Toy Story 2 en 1999."},
]


def test_a_sequel_is_no_repeat_and_the_answer_is_published_first_time():
    # Contracaso del veto de lo dicho dos veces: «Toy Story y Toy Story 2» names two films (base: 1 llamada).
    draft = "Las dos primeras películas de Pixar fueron Toy Story y Toy Story 2."
    final, calls = _compose(PIXAR_SAID, _situation(PIXAR_RESULTS, "primeras peliculas de pixar"), [draft])
    assert final == draft
    assert calls == 1


@pytest.mark.parametrize(
    "text",
    [
        "Las dos primeras películas de Pixar fueron Toy Story y Toy Story 2.",
        "Avatar y Avatar 2 son de James Cameron.",
        "Shrek y Shrek 2 son de DreamWorks.",
        "Rocky y Rocky II son de Stallone.",
        "Black Panther y Black Panther: Wakanda Forever superaron la taquilla internacional.",
        "Las películas son Frozen, Frozen 2 y Moana.",
        # Estribillos y títulos escritos así a propósito.
        "Feliz Navidad, Feliz Navidad, Feliz Navidad, próspero año y felicidad.",
        "La cucaracha, la cucaracha, ya no puede caminar.",
        "Te quiero, te quiero, te quiero.",
        "New York, New York es una canción de Sinatra.",
    ],
)
def test_a_sequel_a_refrain_or_a_title_is_no_repeat_and_chat_keeps_it(text):
    assert listing.duplicated_run(text) == ""
    assert _talk("dime algo", text) == (text, 1)


def test_a_slip_inside_a_list_is_still_a_repeat():
    # Contracaso: the same name doubled inside a list, with no number or subtitle after it, is still said twice.
    assert listing.duplicated_run("Bestiario, Rayuela, Rayuela y Octaedro son de Cortázar.") == "Rayuela"
    assert listing.duplicated_run("Vimos Toy Story y Toy Story en 1995.") == "Toy Story"
    # Revisión 2: the talk is published as written; the veto is the compose stage's (publishable), never a pruning.
    for text in (
        "Mis favoritas: Yesterday, New York, New York y Imagine.",
        "Le dije adiós, que te vaya bien, que te vaya bien.",
        "Compra pan, huevos, huevos frescos, leche y sal.",
    ):
        assert _talk("dime algo", text) == (text, 1)


QUAKE_SAID = "cuantos muertos dejo el terremoto de chile 2010"
QUAKE_PAYLOAD = {
    "operation": "web.search",
    "seen": {"query": QUAKE_SAID, "count": 1, "authority": "duckduckgo_lite_https", "results": [
        {"title": "Terremoto de Chile de 2010 - Wikipedia", "url": "https://es.wikipedia.org/wiki/Terremoto_de_Chile_de_2010",
         "snippet": "El terremoto del 27 de febrero de 2010 dejó 525 muertos."}]},
}


def test_a_year_of_the_page_does_not_confirm_a_rounded_figure():
    draft = "El terremoto de 2010 dejó unos 2000 muertos."
    assert payload_fact_checks._payload_fact_defect(draft, QUAKE_PAYLOAD, QUAKE_SAID) == "search_report_unsourced_claim"
    assert quantities.marked_roundings("unos 2000 muertos", "El terremoto del 27 de febrero de 2010 dejó 525 muertos.") == []
    assert quantities.marked_roundings("unos 25 muertos", "El 27 de febrero hubo 525 muertos.") == []
    assert quantities.marked_roundings("unos 2000", "Avengers: Endgame (2019)") == []
    assert quantities.marked_roundings("unos 2000", "Se estrenó en 2019.") == []


def test_a_count_near_the_rounding_still_confirms_it():
    # Contracaso: the page's own count, rounded and marked, is still the page's.
    assert payload_fact_checks._payload_fact_defect("El terremoto de 2010 dejó unos 500 muertos.", QUAKE_PAYLOAD, QUAKE_SAID) == ""
    assert quantities.marked_roundings("unos 2000 muertos", "hubo 2010 muertos") == ["2000"]
    assert quantities.marked_roundings("casi 1500 casos", "hubo más de 1520 casos") == ["1500"]


# ---------------------------------------------------------------- revisión 3: la cláusula que dice el hecho con otras palabras
@pytest.mark.parametrize(
    "said, results, draft, false_answer",
    [
        (PLACE_SAID, PLACE_RESULTS,
         "La Picada de Don Pepe está en calle Curicó 123, Ñuñoa, aunque según los resultados ya no funciona.",
         "La Picada de Don Pepe está en calle Curicó 123, Ñuñoa."),
        (FLIGHT_SAID, _news("El vuelo LA800 a Madrid, programado para las 10:00, fue suspendido por huelga."),
         "El vuelo LA800 a Madrid sale a las 10:00. Según los resultados, fue anulado.",
         "El vuelo LA800 a Madrid sale a las 10:00."),
        (RUMOR_SAID, RUMOR_RESULTS,
         "Apple lanzará el iPhone 18 en septiembre de 2026, aunque los resultados no lo confirman oficialmente.",
         "Apple lanzará el iPhone 18 en septiembre de 2026."),
    ],
)
def test_a_clause_that_says_the_decisive_fact_in_other_words_is_not_dropped(said, results, draft, false_answer):
    # Base (merge-base 7bdc88fbd): the draft is refused and written again (2 calls); the branch published the rest.
    final, calls = _compose(said, _situation(results, said), [draft])
    assert final != false_answer
    assert calls == 2


def test_clause_states_unsaid_reads_content_and_negation():
    rest = "La Picada de Don Pepe está en calle Curicó 123, Ñuñoa."
    assert answer_evidence.clause_states_unsaid(
        ", aunque según los resultados ya no funciona", rest, PLACE_SAID, PLACE_RESULTS,
    ) == ["funciona"]
    # A denial with no word of content left is still a denial.
    assert answer_evidence.clause_states_unsaid(", aunque no lo es", rest, PLACE_SAID, PLACE_RESULTS) == ["no"]
    # The narration alone, the site's name and the not-found of another thing asked take nothing out.
    assert answer_evidence.clause_states_unsaid(
        "Según la Wikipedia, ", "La más taquillera es Avengers: Endgame.", TOP5_SAID, TOP5_RESULTS,
    ) == []
    assert answer_evidence.clause_states_unsaid(
        ", pero no se menciona ninguna adaptación para Bestiario ni Octaedro en los resultados",
        'Sí, hay una película llamada "Andábamos sin buscarnos" basada en Rayuela.', CORTAZAR_SAID, CORTAZAR_RESULTS,
    ) == []
    # Contracaso: a not-found of the very thing the rest answers is no not-found of another thing.
    assert answer_evidence.clause_states_unsaid(", pero en los resultados no aparece abierto", rest, PLACE_SAID, PLACE_RESULTS)


# ---------------------------------------------------------------- revisión 3: un título escrito con la repetición
SONG_RESULTS = [
    {"title": "Frank Sinatra - Wikipedia", "url": "https://es.wikipedia.org/wiki/Frank_Sinatra",
     "snippet": "Su canción más famosa es New York, New York, grabada en 1979. Doris Day canta Que Sera, Sera en esa "
                "película. Sugar, Sugar fue el mayor éxito de The Archies."},
]


@pytest.mark.parametrize(
    "said, draft",
    [
        ("cual es la cancion mas famosa de frank sinatra",
         "La canción más famosa de Frank Sinatra es New York, New York, grabada en 1979."),
        ("que cancion canta doris day en el hombre que sabia demasiado",
         "En esa película Doris Day canta Que Sera, Sera."),
        ("cual fue el mayor exito de the archies", "El mayor éxito de The Archies fue Sugar, Sugar."),
    ],
)
def test_a_title_written_with_its_repeat_is_published_first_time(said, draft):
    # Base: 1 call. The branch read «New York» / «Sera» / «Sugar» as said twice, vetoed every draft and published a
    # false «No encontré…».
    final, calls = _compose(said, _situation(SONG_RESULTS, said), [draft] * 3)
    assert final == draft
    assert calls == 1


@pytest.mark.parametrize(
    "text",
    [
        "La canción más famosa de Frank Sinatra es New York, New York, grabada en 1979.",
        "En esa película Doris Day canta Que Sera, Sera.",
        "Mis favoritas: Yesterday, New York, New York y Imagine.",
        "El mayor éxito de The Archies fue Sugar, Sugar.",
    ],
)
def test_a_comma_doubled_title_is_no_repeat_for_the_veto(text):
    assert listing.duplicated_run(text, comma_doubled=False) == ""


@pytest.mark.parametrize(
    "text, repeated",
    [
        # Contracaso: joined by «y», doubled with no comma, or listed again further on, it is still twice.
        ("Bestiario, Rayuela y Rayuela son libros de Julio Cortázar.", "Rayuela"),
        ("La película más taquillera de la historia de la historia no se menciona.", "de la historia"),
        ("- Toy Story\n- Cars\n- Toy Story", "Toy Story"),
    ],
)
def test_other_repeats_are_still_vetoed(text, repeated):
    assert listing.duplicated_run(text, comma_doubled=False) == repeated


# ---------------------------------------------------------------- revisión 3: fuera de web.search no se poda por cláusula
def test_an_observed_text_in_another_language_is_never_dropped_by_a_clause():
    observed_text = "Good morning everyone, see you at noon in the office"
    situation = {"kind": "operation", "operation": "clipboard.read.text", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": {"version": 1, "text": observed_text}}
    final, _ = _compose("que tengo en el portapapeles", situation, [f"Leí el portapapeles. Dice:\n{observed_text}"])
    assert final != "Leí el portapapeles. Dice:"
    assert observed_text in final
