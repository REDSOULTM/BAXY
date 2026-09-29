"""M51 (2026-09-28): a search report states only what a result about the query says.

The payloads and drafts are the real ones of the official-window run v3a-final
(%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3a-final/compose-audit.jsonl, traces t26, t37, t113), the
development set reviewed by hand: F-s026, F-s037 and F-p05-t1 were published although no result said them.
"""

from __future__ import annotations

import copy

from baxy_mind.llm import (
    _payload_fact_defect,
    _search_report_from_no_pertinent_result,
    _search_report_proposal_as_fact,
)

S026_PAYLOAD = {
    "seen": {
        "query": "el artículo más leído de Wikipedia",
        "count": 3,
        "results": [
            {
                "title": "Artículo II de la Constitución de los Estados Unidos",
                "url": "https://es.wikipedia.org/wiki/Art%C3%ADculo_II_de_la_Constituci%C3%B3n_de_los_Estados_Unidos",
                "snippet": "El Artículo II de la Constitución de los Estados Unidos crea el poder ejecutivo del Gobierno estadounidense, el cual está formado por el presidente y otros funcionarios principales."
            },
            {
                "title": "Cómo hablar de los libros que no se han leído",
                "url": "https://es.wikipedia.org/wiki/C%C3%B3mo_hablar_de_los_libros_que_no_se_han_le%C3%ADdo",
                "snippet": "Cómo hablar de los libros que no se han leído (en francés: Comment parler des livres que l'on n'a pas lus ?) es un ensayo del psicoanalista, profesor de literatura, crítico literario y escritor francés Pierre Bayard, publicado originalmente por Éditions de Minuit en 2007 y, en español, por la editorial Anagrama, en 2008. En tono provocativo, reflexiona sobre qué significa la lectura y el condicionamiento social del hecho de que en algún momento de la vida todos hayan fingido haber leído un libro que no fue leído. Según Bayard, «tal como se demostrará a lo largo de este ensayo, a veces, para hablar con rigor de un libro, es deseable no haberlo leído del todo, e incluso no haberlo abierto nunca». Cuando se publicó en Francia, atrajo a un gran número de lectores y se convirtió rápidamente en un superventas. Sus derechos de traducción se vendieron a más de 30 países."
            },
            {
                "title": "Las fuentes del comportamiento soviético",
                "url": "https://es.wikipedia.org/wiki/Las_fuentes_del_comportamiento_sovi%C3%A9tico",
                "snippet": "El Artículo X es un artículo, formalmente titulado Las fuentes de la conducta soviética, escrito por George F. Kennan y publicado bajo el seudónimo \"X\" en el número de julio de 1947 de la revista Foreign Affairs. El artículo introdujo ampliamente el término \"contención\" y abogó por su uso estratégico contra la Unión Soviética. El artículo amplió las ideas expresadas por Kennan en un telegrama confidencial de febrero de 1946, identificado formalmente por el número del Departamento de Estado de Kennan, 511, pero apodado informalmente el telegrama largo por su tamaño."
            }
        ],
        "authority": "wikipedia_es_api"
    },
    "operation": "web.search"
}

S037_PAYLOAD = {
    "seen": {
        "query": "¿Cuáles son los números ganadores del loto?",
        "count": 1,
        "results": [
            {
                "title": "Baloto",
                "url": "https://es.wikipedia.org/wiki/Baloto",
                "snippet": "Baloto es un juego de tipo loto en línea de suerte y azar en Colombia, donde el jugador por $9.000 apuesta por un acumulado multimillonario inicial de $4.000 millones de pesos colombianos, que se irá acumulando en cada sorteo, si no se tiene un ganador. Dado que Baloto es un juego paramutual, las cifras exactas de cuánto se gana en el Baloto son difíciles de determinar. Sin embargo, aquí hay un desglose aproximado de la tabla de premios Baloto: Superbalota Única: 5.700 pesos (reembolso del costo del boleto)."
            }
        ],
        "authority": "wikipedia_es_api"
    },
    "operation": "web.search"
}

P05_T1_PAYLOAD = {
    "seen": {
        "query": "aparcamiento en Plaza del Polvorista",
        "count": 5,
        "results": [
            {
                "title": "Plaza del Polvorista - Wikipedia, la enciclopedia libre",
                "url": "https://es.wikipedia.org/wiki/Plaza_del_Polvorista",
                "snippet": "La plaza del Polvorista es una plaza de la ciudad andaluza de El Puerto de Santa María, creada en 1884 y yace cerca al destacado conjunto urbano del Campo de Guía. De forma cuadrada, esta plaza alberga notables edificios como el palacio de Vizarrón (Casa de las Cadenas), el de Aguado -Conde de Montelirios-, Reinoso Mendoza -donde se encuentra el actual ayuntamiento- o el Cuartel de ..."
            },
            {
                "title": "VOX El Puerto plantea un aparcamiento subterráneo en la Plaza del ...",
                "url": "https://www.voxespana.es/noticias/vox-el-puerto-plantea-un-aparcamiento-subterraneo-en-la-plaza-del-polvorista-20260304?provincia=cadiz",
                "snippet": "En ese contexto, VOX defiende que la Plaza del Polvorista reúne condiciones para albergar un aparcamiento subterráneo de gran capacidad \"con menos obstáculos y más control municipal\"."
            },
            {
                "title": "Mantenimiento urbano remodela los estacionamientos de la Plaza del ...",
                "url": "https://www.diariodecadiz.es/elpuerto/Mantenimiento-remodela-estacionamientos-Plaza-Polvorista_0_1404759712.html",
                "snippet": "El área de Mantenimiento Urbano está acometiendo la remodelación de los estacionamientos de la plaza del Polvorista , para mejorarlos de cara a las necesidades de los ciudadanos."
            },
            {
                "title": "El Puerto: La plaza de El Polvorista, la guinda del 'Pasillo Amable'",
                "url": "https://www.diariodecadiz.es/elpuerto/Puerto-Polvorista-guinda-Pasillo-Amable-plaza-casco-historico_0_1901511859.html",
                "snippet": "Una imagen panorámica de la Plaza del Polvorista , con la fuente en el centro y al fondo el antiguo Ayuntamiento (Palacio de Imblusqueta) y el edificio de Correos, a la izquierda. / Manuel Aragón ..."
            },
            {
                "title": "Plaza del Polvorista - Mapa - Parque - El Puerto de Santa María ...",
                "url": "https://mapcarta.com/es/W29451697",
                "snippet": "La plaza del Polvorista es una plaza de la ciudad andaluza de El Puerto de Santa María, creada en 1884 y yace cerca al destacado conjunto urbano del Campo de Guía."
            }
        ],
        "authority": "duckduckgo_lite_https"
    },
    "operation": "web.search"
}



def test_s026_the_most_read_article_is_not_in_any_result_about_it():
    draft = "El artículo más leído es Cómo hablar de los libros que no se han leído."
    user = "pásame el artículo más leído de la wikipedia"
    assert _search_report_from_no_pertinent_result(draft, S026_PAYLOAD, user)
    assert _payload_fact_defect(draft, S026_PAYLOAD, user) == "search_report_off_subject"
    assert _payload_fact_defect("No lo encontré.", S026_PAYLOAD, user) == ""


def test_s037_baloto_does_not_answer_the_winning_numbers_of_the_loto():
    draft = (
        "No hay números ganadores del loto porque Baloto es un juego de suerte y azar donde los premios son "
        "difíciles de determinar."
    )
    user = "Cuáles son los números ganadores del loto"
    assert _search_report_from_no_pertinent_result(draft, S037_PAYLOAD, user)
    assert _payload_fact_defect(draft, S037_PAYLOAD, user) == "search_report_off_subject"
    assert _payload_fact_defect("No lo encontré.", S037_PAYLOAD, user) == ""


def test_p05_t1_a_proposed_car_park_is_not_said_to_exist():
    draft = "Hay aparcamiento subterráneo en la Plaza del Polvorista y se está remodelando el área de estacionamientos."
    user = "Encuentra aparcamiento en Plaza del Polvorista"
    # The results are about the query (the square and its parking); the claim is what fails.
    assert not _search_report_from_no_pertinent_result(draft, P05_T1_PAYLOAD, user)
    assert _search_report_proposal_as_fact(draft, P05_T1_PAYLOAD, user)
    assert _payload_fact_defect(draft, P05_T1_PAYLOAD, user) == "search_report_proposal_as_fact"
    assert not _search_report_proposal_as_fact(
        "Se propone un aparcamiento subterráneo en la Plaza del Polvorista.", P05_T1_PAYLOAD, user
    )


def test_a_result_about_the_query_still_answers():
    payload = {
        "operation": "web.search",
        "seen": {
            "query": "who wrote Dracula",
            "count": 1,
            "results": [
                {
                    "title": "Dracula",
                    "url": "https://en.wikipedia.org/wiki/Dracula",
                    "snippet": "Dracula is an 1897 Gothic horror novel by Irish author Bram Stoker.",
                }
            ],
            "authority": "wikipedia_en_api",
        },
    }
    assert not _search_report_from_no_pertinent_result("Bram Stoker wrote Dracula.", payload, "who wrote Dracula")
    places = copy.deepcopy(payload)
    places["seen"].update(query="aparcamiento en Plaza Mayor, Madrid", authority="openstreetmap_nominatim")
    # M56 (v3c-final F-p06-t2, car parks of Cartagena told for «…la Plaza de las Salesas en Madrid»): a place read
    # from OpenStreetMap answers by construction only inside the city the query named; one outside it (this result
    # names no Madrid) answers nothing about it.
    assert _search_report_from_no_pertinent_result("Hay un parking en la Calle Mayor.", places, "")
    places["seen"]["results"][0].update(
        title="parking", snippet="Calle Mayor, Sol, Centro, Madrid, Comunidad de Madrid, 28013, España"
    )
    assert not _search_report_from_no_pertinent_result("Hay un parking en la Calle Mayor.", places, "")
