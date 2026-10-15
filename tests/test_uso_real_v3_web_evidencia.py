"""Uso real v3, tanda 1 (2026-10-07), causa 1 del juez: respuestas armadas con los fragmentos de búsqueda aunque no
traigan el dato.

- «quien gano el mundial del 2014» → «Brasil ganó la Copa Mundial de Fútbol de 2014.» Las páginas nombraban a Brasil
  como sede; ninguna decía quién ganó, y cada palabra del borrador estaba en algún resultado.
- «cuales son las peliculas mas taquilleras de la historia? dame el top 5» → un nombre de una enciclopedia y cuatro de
  una galería de fotos que los nombra sin orden.

Los resultados son los que la tanda guardó en compose_audit.jsonl (uso-real-v3-evidencia/t1-base, filas 20, 22 y 82),
copiados aquí: nada sale a la web. Cada regla lleva su contracaso: el dato que sí está en el fragmento se responde.
"""

from __future__ import annotations

from baxy_mind import payload_fact_checks
from baxy_mind import search_report
from baxy_mind.semantic import answer_evidence
from baxy_mind import compose_facts


MUNDIAL = "quien gano el mundial del 2014"
TOP5 = "cuales son las peliculas mas taquilleras de la historia? dame el top 5"

# compose_audit.jsonl fila 82 (t30), authority wikipedia_es_api.
MUNDIAL_RESULTS = [
    {
        "title": "Copa Mundial de Fútbol de 2014",
        "url": "https://es.wikipedia.org/wiki/Copa_Mundial_de_F%C3%BAtbol_de_2014",
        "snippet": "La Copa Mundial de la FIFA Brasil 2014 (en portugués: Copa do Mundo FIFA de 2014) fue la vigésima "
        "edición de la Copa Mundial de Fútbol. Se realizó en Brasil entre el 12 de junio y el 13 de julio de 2014, "
        "por segunda vez en dicho país, tras el campeonato de 1950. Después de que el presidente de la FIFA, Joseph "
        "Blatter, estableció en 2001 el criterio de rotación continental de la sede del torneo, América del Sur fue "
        "seleccionada en 2004 para celebrar en 2014 su primera copa desde Argentina 1978.",
    },
    {
        "title": "Clasificación de Conmebol para la Copa Mundial de Fútbol de 2014",
        "url": "https://es.wikipedia.org/wiki/Clasificaci%C3%B3n_de_Conmebol_para_la_Copa_Mundial_de_F%C3%BAtbol_de_2014",
        "snippet": "La clasificación de Conmebol para la Copa Mundial de Fútbol de 2014 contó con cuatro cupos directos y "
        "un cupo para el repechaje contra el ganador de la quinta ronda de la clasificatoria asiática. Como "
        "anfitrión, Brasil no pasó por la clasificación, por lo que en esta edición participaron las nueve "
        "selecciones restantes.",
    },
    {
        "title": "Clasificación para la Copa Mundial de Fútbol de 2014",
        "url": "https://es.wikipedia.org/wiki/Clasificaci%C3%B3n_para_la_Copa_Mundial_de_F%C3%BAtbol_de_2014",
        "snippet": "Fueron 32 equipos los que compitieron en la Copa Mundial de Fútbol de 2014, con una plaza destinada al "
        "país organizador, Brasil. En el programa publicado inicialmente se preveían 824 partidos para decidir las "
        "31 plazas en disputa para el Mundial de Brasil 2014, pero con el retiro de Bahamas y Mauricio, solo se "
        "necesitaron 816.",
    },
    {
        "title": "Copa Mundial de Baloncesto de 2014",
        "url": "https://es.wikipedia.org/wiki/Copa_Mundial_de_Baloncesto_de_2014",
        "snippet": "Fue la segunda vez que se celebró un mundial de baloncesto en España (el anterior, en 1986), entrando "
        "así en el grupo de países con más de un mundial organizado, en el que están Brasil (1954 y 1963) y "
        "Argentina (1950 y 1990). Con un equipo NBA, Estados Unidos derrotó ampliamente a todos sus rivales y logró "
        "defender de manera invicta y exitosa el título de 2010.",
    },
]

# compose_audit.jsonl filas 20 y 22 (t9), authority duckduckgo_lite_https.
TOP5_RESULTS = [
    {
        "title": "Anexo:Películas con las mayores recaudaciones - Wikipedia, la ...",
        "url": "https://es.wikipedia.org/wiki/Anexo:Pel%C3%ADculas_con_las_mayores_recaudaciones",
        "snippet": "Películas con las mayores recaudaciones La película más taquillera de la historia es Avengers: "
        "Endgame (2019) que logró recaudar 2 925 466 085 USD.",
    },
    {
        "title": "Las películas más taquilleras de la historia",
        "url": "https://www.lacartelera.com/es/mas-taquilleras/",
        "snippet": "Ranking de las películas que más dinero han recaudado en taquilla mundial, en total y por década.",
    },
    {
        "title": "¿Cuáles son las 5 películas más taquilleras de la historia?",
        "url": "https://www.clarin.com/internacional/5-peliculas-taquilleras-historia_0_aEHtullgYq.html",
        "snippet": "Muchas fueron y serán inolvidables, pero no todas resultaron un éxito de taquilla.Aquí, las películas "
        "que más millones recaudaron en la historia del cine. … En ese sentido, es probable que en más de una "
        "ocasión te hayas preguntado cuáles son las películas más taquilleras de la historia , un tema que siempre "
        "despierta curiosidad entre los espectadores. Según los datos de Box Office Mojo , una plataforma en línea "
        "que proporciona información detallada sobre las ventas de entradas de cine y las cifras de taquilla de "
        "películas en todo el mundo, esta es la lista de las 5 películas con más recaudación de la historia del cine.",
    },
    {
        "title": "Las películas más taquilleras de la historia del cine",
        "url": "https://www.periodismo.com/2026/09/12/las-peliculas-mas-taquilleras-de-la-historia-del-cine/",
        "snippet": "La historia del cine está llena de películas que marcaron una época y vendieron millones de entradas "
        "en todo el planeta. En esta galería te presentamos el listado de los filmes que más millones de dólares "
        "recaudaron, que incluye desde 'Avengers' y 'Piratas del Caribe' hasta 'Rápidos y Furiosos' y 'Star Wars'. "
        "Bohemian Rhapsody (2018) […]",
    },
    {
        "title": "Estas son las 5 películas más taquilleras de la historia",
        "url": "https://www.ambito.com/espectaculos/estas-son-las-5-peliculas-mas-taquilleras-la-historia-n5977813",
        "snippet": "Estas películas dejaron una huella imborrable en la industria del cine. Enterate cuales son y si las "
        "viste.",
    },
]


def _payload(query: str, results: list[dict], authority: str) -> dict:
    return {
        "operation": "web.search",
        "seen": {"query": query, "count": len(results), "results": results, "authority": authority},
    }


def _defect(text: str, question: str, results: list[dict], authority: str = "duckduckgo_lite_https") -> str:
    return payload_fact_checks._payload_fact_defect(text, _payload(question, results, authority), question)


# --- quién ganó: el dato con su relación, no las palabras sueltas ------------------------------------------------


def test_tanda1_brasil_gano_el_mundial_2014_no_lo_dice_ningun_resultado() -> None:
    # Borrador publicado en la tanda (fila 82): pasaba porque «Brasil», «Copa Mundial», «Fútbol» y «2014» están.
    draft = "Brasil ganó la Copa Mundial de Fútbol de 2014."
    assert _defect(draft, MUNDIAL, MUNDIAL_RESULTS, "wikipedia_es_api") == "search_report_answer_unstated"
    assert search_report._search_report_answer_unstated(draft, _payload(MUNDIAL, MUNDIAL_RESULTS, "x"), MUNDIAL) == ["Brasil"]


def test_campeonato_es_el_torneo_no_quien_lo_gano() -> None:
    # «tras el campeonato de 1950» está en la misma oración que «Brasil»: nombra el torneo, no al campeón.
    assert not answer_evidence.states_relation("Se realizó en Brasil, tras el campeonato de 1950.", "win")
    assert answer_evidence.states_relation("Alemania se consagró campeona del mundo.", "win")


def test_no_encontrado_y_la_sede_sin_relacion_se_dicen() -> None:
    # Contracasos: decir que no lo encontró, o lo que el resultado sí dice (la sede) sin afirmar quién ganó.
    for said in ("No encontré quién ganó el mundial del 2014.", "La Copa Mundial de Fútbol de 2014 se jugó en Brasil."):
        assert not search_report._search_report_answer_unstated(said, _payload(MUNDIAL, MUNDIAL_RESULTS, "x"), MUNDIAL)


def test_el_dato_en_el_fragmento_se_responde() -> None:
    # Contracaso: cuando el fragmento leído (la página, tras « … ») dice quién ganó, la respuesta pasa.
    read = [dict(MUNDIAL_RESULTS[0])] + MUNDIAL_RESULTS[1:]
    read[0]["snippet"] += (
        " … Alemania se consagró campeona por cuarta vez tras vencer a Argentina por 1-0 en la final."
    )
    assert _defect("Alemania ganó el Mundial de 2014.", MUNDIAL, read, "wikipedia_es_api") == ""


def test_quien_dirigio_con_el_director_en_el_fragmento() -> None:
    results = [{
        "title": "Titanic (película de 1997)",
        "url": "https://es.wikipedia.org/wiki/Titanic_(pel%C3%ADcula_de_1997)",
        "snippet": "Titanic es una película estadounidense de 1997 escrita y dirigida por James Cameron.",
    }]
    question = "quien dirigio titanic"
    assert answer_evidence.relation_asked(question) == "direct"
    assert _defect("James Cameron dirigió Titanic.", question, results, "wikipedia_es_api") == ""
    # Y el mismo informe con otro nombre no está en la evidencia.
    assert search_report._search_report_answer_unstated(
        "Steven Spielberg dirigió Titanic.", _payload(question, results, "x"), question
    )


def test_quien_perdio_dice_quien_gano() -> None:
    # Revisión adversarial: el resultado de un partido que el equipo leído perdió dice «lost to» (EspnScheduleSource),
    # y el ganador está en esa oración. «Barcelona ganó» se responde; antes caía en «No encontré» tras tres borradores.
    question = "who won the last real madrid match"
    results = [{
        "title": "Real Madrid",
        "url": "https://www.espn.com/soccer/match/_/gameId/1",
        "snippet": "Last match: Real Madrid lost to Barcelona 1-2 away, on Sunday 2026-10-04 at 16:00 local time "
        "(UTC-03:00).",
    }]
    for draft in ("Barcelona beat Real Madrid 2-1.", "Barcelona ganó 2-1 al Real Madrid."):
        assert _defect(draft, question, results, "espn_public_schedule") == ""
    assert answer_evidence.states_relation("Argentina perdió la final ante Alemania.", "win")
    # Contracasos: un ganador que ningún resultado nombra sigue sin estar en la evidencia, y la pérdida de dinero no
    # dice quién ganó.
    assert search_report._search_report_answer_unstated(
        "Ganó el Atlético, 2-1 al Real Madrid.", _payload(question, results, "espn_public_schedule"), question
    ) == ["Atlético"]
    assert not answer_evidence.states_relation("El club registró pérdidas en 2014.", "win")


def test_una_pregunta_sin_relacion_no_se_juzga_aqui() -> None:
    assert answer_evidence.relation_asked("quien es Keanu Reeves") is None
    assert answer_evidence.relation_asked(TOP5) is None
    assert answer_evidence.relation_asked("who won the 2014 world cup") == "win"


# --- un listado pedido: de una misma fuente que es un ranking ----------------------------------------------------


def test_tanda1_top5_de_una_galeria_y_otra_pagina_no_es_el_listado() -> None:
    # Borrador publicado en la tanda (fila 22, y repetido tras «no wey te pedi 5 nomas»).
    draft = (
        "Avengers: Endgame es la película más taquillera de la historia y la lista incluye también Rápidos y "
        "Furiosos, Piratas del Caribe, Star Wars y Bohemian Rhapsody."
    )
    assert _defect(draft, TOP5, TOP5_RESULTS) == "search_listing_not_one_ranking"
    again = "Entiendo, solo te daré el top 5: Avengers: Endgame, Rápidos y Furiosos, Piratas del Caribe, Star Wars y Bohemian Rhapsody."
    assert search_report._search_listing_not_from_one_ranking(again, _payload(TOP5, TOP5_RESULTS, "x"), TOP5)


def test_la_galeria_sola_tampoco_es_un_ranking() -> None:
    gallery = TOP5_RESULTS[3]
    assert not answer_evidence.is_ranking(gallery)
    draft = "Entre las más taquilleras están Piratas del Caribe, Rápidos y Furiosos y Star Wars."
    assert search_report._search_listing_not_from_one_ranking(draft, _payload(TOP5, [gallery], "x"), TOP5)


def test_lo_que_un_resultado_si_afirma_se_dice() -> None:
    # Contracaso: el primero, que un fragmento sí dice, más el aviso de que no está el listado completo.
    draft = "La película más taquillera de la historia es Avengers: Endgame. No encontré el top 5 completo."
    assert _defect(draft, TOP5, TOP5_RESULTS) == ""


def test_un_ranking_numerado_en_un_fragmento_se_lista() -> None:
    results = [{
        "title": "Top 3: las películas más taquilleras de todos los tiempos",
        "url": "https://example.org/top",
        "snippet": "1. Avatar (2009) 2. Avengers: Endgame (2019) 3. Titanic (1997)",
    }]
    question = "dame el top 3 de peliculas mas taquilleras"
    assert answer_evidence.is_ranking(results[0])
    assert not search_report._search_listing_not_from_one_ranking(
        "Las tres más taquilleras son Avatar, Avengers: Endgame y Titanic.", _payload(question, results, "x"), question
    )


def test_un_titulo_que_anuncia_el_ranking_lo_es() -> None:
    assert answer_evidence.is_ranking(TOP5_RESULTS[2])  # «¿Cuáles son las 5 películas más taquilleras…?»
    assert not answer_evidence.is_ranking(TOP5_RESULTS[0])  # un anexo cuyo fragmento nombra una sola


def test_sin_listado_pedido_no_se_exige_ranking() -> None:
    question = "que peliculas de piratas hay"
    draft = "Están Piratas del Caribe y La isla de las cabezas cortadas."
    results = [{"title": "Películas de piratas", "url": "https://example.org/p",
                "snippet": "Entre ellas, Piratas del Caribe y La isla de las cabezas cortadas."}]
    assert not search_report._search_listing_not_from_one_ranking(draft, _payload(question, results, "x"), question)


def test_lugares_de_una_fuente_estructurada_se_nombran_cada_uno() -> None:
    # Revisión adversarial: con OpenStreetMap cada resultado es un lugar y su orden es la distancia; ningún resultado
    # nombra a los demás. «los mejores restaurantes cerca de mí» pide un listado y la instrucción del listado dice
    # nombrar cada uno encontrado: no es un ranking inventado.
    question = "dime los mejores restaurantes cerca de mi"
    places = [
        {"title": "Café Brasil", "url": "https://www.openstreetmap.org/node/1",
         "snippet": "Avenida Libertad 100, Ñuñoa, Curicó, Chile", "distanceMeters": 300},
        {"title": "Restaurante Delicias del Mar", "url": "https://www.openstreetmap.org/node/2",
         "snippet": "Avenida San Martín 459, Ñuñoa, Curicó, Chile", "distanceMeters": 500},
        {"title": "Fuente Alemana", "url": "https://www.openstreetmap.org/node/3",
         "snippet": "Calle Curicó 520, Ñuñoa, Curicó, Chile", "distanceMeters": 700},
    ]
    for draft in (
        "Café Brasil, Restaurante Delicias del Mar y Fuente Alemana.",
        "Café Brasil está en Avenida Libertad 100 y Fuente Alemana en Calle Curicó 520.",
    ):
        payload = _payload(question, places, "openstreetmap_nominatim")
        assert not search_report._search_listing_not_from_one_ranking(draft, payload, question)
    # Contracaso: los mismos nombres sacados de páginas (buscador general), sin un ranking que los nombre a todos.
    pages = [{**place, "url": "https://example.org/" + str(index)} for index, place in enumerate(places)]
    assert search_report._search_listing_not_from_one_ranking(
        "Café Brasil, Restaurante Delicias del Mar y Fuente Alemana.",
        _payload(question, pages, "duckduckgo_lite_https"), question,
    )


def test_nombres_del_tema_de_la_pregunta_no_son_la_respuesta() -> None:
    evidence = "\n".join(item["title"] + "\n" + item["snippet"] for item in MUNDIAL_RESULTS)
    assert answer_evidence.answer_spans("Brasil ganó la Copa Mundial de Fútbol de 2014.", MUNDIAL, evidence) == [
        "Brasil"
    ]
    # La primera palabra de una oración no es un nombre si la evidencia no la escribe con mayúscula dentro de una.
    assert answer_evidence.name_spans("Las cinco son Avatar y Titanic.", "es Avatar o Titanic") == ["Avatar", "Titanic"]


# --- la mente le dice al proveedor con qué palabras una página afirma lo preguntado ------------------------------

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "answerWords": {"type": ["string", "null"], "x-maxUtf8Bytes": 512},
        "answerWordsNot": {"type": ["string", "null"], "x-maxUtf8Bytes": 256},
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "listing": {"type": ["boolean", "null"]},
        "nearby": {"type": ["boolean", "null"]},
        "query": {"type": "string", "x-maxUtf8Bytes": 2000, "x-nonWhitespace": True},
    },
    "required": ["query"],
    "additionalProperties": False,
}


def test_una_pregunta_de_relacion_lleva_sus_palabras_al_proveedor() -> None:

    arguments = compose_facts._with_asked_listing("web.search", {"query": "ganador mundial 2014"}, MUNDIAL, SEARCH_SCHEMA)
    assert arguments["query"] == "ganador mundial 2014"
    assert {"gan", "campeon", "derroto"} <= set(arguments["answerWords"].split())
    # Revisión adversarial: y las palabras que empiezan así pero nombran el torneo, para que el proveedor no tome
    # «tras el campeonato de 1950» o «the quadrennial world championship» por quién ganó.
    assert {"campeonato", "championship"} <= set(arguments["answerWordsNot"].split())


def test_sin_exclusiones_en_la_relacion_o_en_el_catalogo_no_se_mandan() -> None:

    directed = compose_facts._with_asked_listing("web.search", {"query": "titanic"}, "quien dirigio titanic", SEARCH_SCHEMA)
    assert directed["answerWords"] and "answerWordsNot" not in directed
    older = {**SEARCH_SCHEMA, "properties": {
        k: v for k, v in SEARCH_SCHEMA["properties"].items() if k != "answerWordsNot"
    }}
    won = compose_facts._with_asked_listing("web.search", {"query": "mundial 2014"}, MUNDIAL, older)
    assert won["answerWords"] and "answerWordsNot" not in won


def test_contracasos_de_las_palabras_de_respuesta() -> None:

    # Sin relación preguntada, nada; y un catálogo cuya búsqueda no acepta answerWords no lo recibe.
    plain = {"query": "keanu reeves"}
    assert compose_facts._with_asked_listing("web.search", plain, "quien es Keanu Reeves", SEARCH_SCHEMA) == plain
    old = {**SEARCH_SCHEMA, "properties": {k: v for k, v in SEARCH_SCHEMA["properties"].items() if k != "answerWords"}}
    assert compose_facts._with_asked_listing("web.search", {"query": "mundial 2014"}, MUNDIAL, old) == {"query": "mundial 2014"}
    assert compose_facts._with_asked_listing("task.list", {"x": 1}, MUNDIAL, SEARCH_SCHEMA) == {"x": 1}
