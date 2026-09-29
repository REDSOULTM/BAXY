"""M77 (2026-09-29, independent review of the DEV-D real-app run v3l-devD): a search report says what was read, only
what was read, and never shows the search. Each case is a real turn of that run, with the payload the composer judged
(%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3l-devD/: compose-audit.jsonl, run.map.json, REVIEW.reviewed.jsonl;
result URLs left out).

Causes, grouped:
1. The search shown: «None of the results state…» (D-p27-t2), «…in the provided results» (D-s063), «Los fragmentos
   mencionan…» (D-p34-t1), «La información visible…», «Los resultados no mencionan…» (D-p31-t1).
2. A verdict the read does not hold: «No valet parking is available at the Kenzi Rose Garden» over public car parks
   (D-p16-t3); and the honest «I could not find valet parking…» denied as if the car parks were valet (D-p16-t1/t2).
3. «No lo encontré» with the datum read: the age from a birth date read (D-w14-t2); results judged off subject by a
   narrower-article rule meant for places (D-p24-t2), by half of a long request's words (D-p34-t1) and by courtesy
   words (D-w10-t2).
4. Another time given as the answer: the 2025 winner for «este año» (D-w14-t1); a headline's «mañana» of five days
   before (D-p05-t2, then repeated in D-p05-t3).
5. A fact the read does not state: «Por qué el mundo ha perdido sus colores» said as «El mundo ha perdido sus colores»
   (D-s021); Spanish titles given English names of the model's own, «The Biker» (D-p27-t3); «the cozy mystery that's
   been trending this week» with nothing read (D-p27-t1).
6. The word asked with, defined: «Genre is any style…» (D-p19-t3), «A drama film is…» (D-p23-t2), «The second headline
   refers to the text…» (D-w17-t5).
7. Failures told wrong: «no existe un lugar llamado Abingdon en Virginia» when the weather service only did not
   recognise it (D-s087); three headlines quoted died on the headline's own «¿…?» (D-s032).
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from baxy_mind import llm
from baxy_mind.llm import (
    _SEARCH_RESULTS_TAIL,
    _birth_ages,
    _payload_fact_defect,
    _places_unread_qualifiers,
    _search_report_defines_the_ask,
    _search_report_other_year,
    _search_report_stale_day,
    _search_report_unsourced_words,
    _search_report_why_title_as_fact,
    compose_visible_defect,
)
from baxy_mind.semantic.web import asks_this_year, request_common_words, undefined_asked_phrases


@pytest.fixture
def run_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """The run was on 2026-09-29."""

    monkeypatch.setattr(llm, "_report_today", lambda: date(2026, 9, 29))


def _search(query: str, results: list[dict], authority: str) -> dict:
    return {"seen": {"query": query, "count": len(results), "results": results, "authority": authority},
            "operation": "web.search"}


P16_T3 = _search(
    "Is there valet parking at the Kenzi Rose Garden in Marrakech?",
    [
        {"title": "parking", "snippet": "Boulevard Mohammed VI شارع محمد السادس, L'Hivernage, Guéliz ⴳⵉⵍⵉⵣ گليز, "
         "Arrondissement de Gueliz مقاطعة كليز, Marrakesh, Pachalik de Marrakech, Marrakesh Prefecture, Marrakech-Safi, "
         "40020, Morocco", "distanceMeters": 460},
        {"title": "parking", "snippet": "Avenue Houman El Fetouaki, Medina, Arrondissement de Marrakech-Medina مقاطعة "
         "مراكش المدينة, Marrakesh, Pachalik de Marrakech, Marrakesh Prefecture, Marrakech-Safi, 40034, Morocco",
         "distanceMeters": 880},
        {"title": "parking", "snippet": "Annexe Bab Doukkala, Bab Doukkala, Medina, Arrondissement de Marrakech-Medina "
         "مقاطعة مراكش المدينة, Marrakesh, Pachalik de Marrakech, Marrakesh Prefecture, Marrakech-Safi, 40034, Morocco",
         "distanceMeters": 940},
        {"title": "parking", "snippet": "Rue Khalid Ben El Oualid, El Hara, Arrondissement de Gueliz مقاطعة كليز, "
         "Marrakesh, Pachalik de Marrakech, Marrakesh Prefecture, Marrakech-Safi, 40000, Morocco",
         "distanceMeters": 960},
        {"title": "Parking place", "snippet": "Parking place, Place El Harti, Guéliz ⴳⵉⵍⵉⵣ گليز, Arrondissement de "
         "Gueliz مقاطعة كليز, Marrakesh, Pachalik de Marrakech, Marrakesh Prefecture, Marrakech-Safi, 40025, Morocco",
         "distanceMeters": 970},
    ],
    "openstreetmap_nominatim",
)
P16_T1 = {**P16_T3, "seen": {**P16_T3["seen"], "query": "valet parking at the Kenzi Rose Garden"}}

P05_T2 = _search(
    "Necesito aparcamiento para mañana.",
    [
        {"title": "EL NUEVO APARCAMIENTO JUNTO A LA ESTACIÓN DE FERROCARRIL ABRIRÁ MAÑANA CON MÁS DE 400 PLAZAS",
         "snippet": "Ayuntamiento del Real Sitio y Villa de Aranjuez, Thu, 24 Sep 2026 12:12:35 GMT"},
        {"title": "El aparcamiento disuasorio de la calle Bálago abre mañana viernes con 172 plazas",
         "snippet": "Ayuntamiento de Valladolid, Thu, 03 Sep 2026 07:00:00 GMT"},
        {"title": "El Civil cierra mañana día 27 el aparcamiento por el avance de las obras del futuro hospital",
         "snippet": "Cadena SER, Tue, 26 May 2026 07:00:00 GMT"},
        {"title": "Mañana se inaugura el EcoParking Seguro Arnedo, un referente europeo en áreas de aparcamiento para "
         "camiones", "snippet": "Transporte 3, Thu, 25 Jun 2026 07:00:00 GMT"},
        {"title": "El aparcamiento disuasorio de la avenida de la Estación abrirá al público mañana viernes",
         "snippet": "Ayuntamiento de Torrevieja, Thu, 30 Jul 2026 07:00:00 GMT"},
    ],
    "google_news_rss_search",
)

S021 = _search(
    "noticias por el mundo",
    [
        {"title": "Por qué el mundo ha perdido sus colores: Los estudios que muestran cómo el gris conquistó nuestra "
         "vida", "snippet": "BioBioChile, Tue, 29 Sep 2026 19:29:43 GMT"},
        {"title": "Por qué la IA más potente del mundo está obsesionada con Mark Fisher, el filósofo anticapitalista más "
         "influyente del siglo", "snippet": "EL PAÍS, Tue, 29 Sep 2026 03:30:00 GMT"},
        {"title": 'La familia de Ranulph Fiennes, "el explorador vivo más importante del mundo", dice desconocer su '
         "paradero", "snippet": "BBC, Tue, 29 Sep 2026 17:01:34 GMT"},
        {"title": "El nuevo mapa del fin del mundo: 22,3 millones de hectáreas para Cabo de Hornos",
         "snippet": "El Mostrador, Tue, 29 Sep 2026 08:06:14 GMT"},
    ],
    "google_news_rss_search",
)

W14_T1 = _search(
    "¿Quién ha ganado la Vuelta este año?",
    [
        {"title": "El 'paquete' que perdió el miedo a caer y ha ganado la Vuelta a España ...",
         "snippet": "Mas dio el salto al ciclismo profesional en 2017 con el equipo Quick-Step Floors, y un año después "
         "ganó Vuelta al País Vasco y una etapa en la Vuelta a España."},
        {"title": "Ganadores De Etapa De La Vuelta 2026", "snippet": "Sitio oficial de La Vuelta ."},
        {"title": "Palmarés de la Vuelta a España: quién ha ganado más veces",
         "snippet": "Te contamos todos los ganadores de La Vuelta a España 2025: todos los campeones de la historia, "
         "qué ciclistas tienen más títulos..."},
        {"title": "Bostezos, Zack Snyder y Massiel en Año Nuevo: Vingegaard conquista la ...",
         "snippet": "En la Vuelta a España 2025, Jonas Vingegaard ganó sin convencer, entre recorridos anodinos, "
         "protestas legítimas y duelos descafeinados. Una crónica donde el ciclismo sobrevive entre artificios, sombras "
         "y sarcasmos."},
    ],
    "duckduckgo_lite_https",
)

W14_T2 = _search(
    "Cuántos años tiene Jonas Vingegaard",
    [{"title": "Jonas Vingegaard",
      "snippet": "Jonas Vingegaard Rasmussen (Hillerslev, 10 de diciembre de 1996) es un ciclista danés, miembro del "
      "equipo Team Visma | Lease a Bike. Ha sido el ganador del Tour de Francia 2022 y 2023, de la Vuelta a España 2025 "
      "y del Giro de Italia 2026."}],
    "wikipedia_es_api",
)

P27_T3 = _search(
    "movies with Eugene Dynarski",
    [{"title": "Eugene Dynarski",
      "snippet": "Eugene Dynarski (Estados Unidos, 13 de septiembre de 1932-27 de febrero de 2020) fue un actor "
      "estadounidense. Tres de los más importantes proyectos en los que estuvo involucrado fueron, dos películas de "
      "Steven Spielberg: El diablo sobre ruedas y Encuentros en la tercera fase, y el videojuego de Westwood Studios, "
      "Command & Conquer: Red Alert."}],
    "wikipedia_es_api",
)

P24_T2 = _search(
    "a drama movie like Lizzo",
    [{"title": "Estafadoras de Wall Street",
      "snippet": "Estafadoras de Wall Street (título original en inglés: Hustlers) es una película de drama de crimen de "
      "comedia negra estadounidense de 2019 escrita y dirigida por Lorene Scafaria, basada en el artículo de 2015 de "
      "New York Magazine The Hustlers at Scores: The Ex-Strippers Who Stole From (Mostly) Rich Men and Gave to, Well, "
      "Themselves, de Jessica Pressler. La película está protagonizada por Constance Wu, Jennifer López, Julia Stiles, "
      "Keke Palmer, Lili Reinhart, Lizzo y Cardi B."}],
    "wikipedia_es_api",
)

P24_T1 = _search(
    "a nice fantasy movie like Elijah Wood",
    [
        {"title": "Ya no me siento a gusto en este mundo",
         "snippet": "Ya no me siento a gusto en este mundo (título en inglés: I Don't Feel at Home in This World "
         "Anymore) es una película estadounidense de comedia policíaca y suspense escrita y dirigida por Macon Blair en "
         "su debut en la dirección, protagonizada por Melanie Lynskey, Elijah Wood, David Yow, Jane Levy y Devon "
         "Graye."},
        {"title": "Pawn Shop Chronicles",
         "snippet": "Pawn Shop Chronicles es una película del año 2013, protagonizada por Paul Walker, Elijah Wood, "
         "Brendan Fraser, Matt Dillon y Norman Reedus y dirigida por Wayne Kramer."},
        {"title": "Kevin (Sin City)",
         "snippet": "Kevin es un personaje ficticio de la novela gráfica Sin City de Frank Miller. En la película de "
         "2005 está interpretado por Elijah Wood."},
    ],
    "wikipedia_es_api",
)

W10_T2 = _search(
    "¿Y cuánto sería eso de harina en gramos, por favor?",
    [
        {"title": "Equivalencias de harina en gramos: guía práctica",
         "snippet": "Medir exacto Equivalencias de harina en gramos : guía práctica Conocer las equivalencias de harina "
         "en gramos permite cocinar con precisión, incluso sin balanza. En esta guía práctica te mostramos cómo medir "
         "harina sin errores."},
        {"title": "Taza de Harina a Gramos: Calculadora Precisa para Tus Recetas",
         "snippet": "Convierte tazas de harina a gramos y onzas de forma exacta. Descubre consejos, tablas de "
         "equivalencias y tips para medir correctamente y lograr recetas perfectas en repostería y panadería."},
        {"title": "Gramos a Tazas de Harina: Tabla de Conversión (1 taza = 125 g)",
         "snippet": "1 taza de harina = 125 g · 2 tazas = 250 g · 3 tazas = 375 g · 4 tazas = 500 g. Tabla de "
         "conversión en las dos direcciones para harina común y leudante."},
    ],
    "duckduckgo_lite_https",
)

P34_T1 = _search(
    "Elabora una lista con las cápsulas del tiempo más famosas de la historia, especificando las fechas en las que "
    "fueron creadas, y en el caso de que hayan sido abiertas, el contenido además de la fecha de apertura.",
    [
        {"title": "Estas son las cápsulas del tiempo más increíbles que el ser humano ha ...",
         "snippet": "Descubre las cápsulas del tiempo más famosas de la historia, qué contienen, quién las creó y cuándo "
         "está previsto que algunas se abran."},
        {"title": "8 cápsulas del tiempo que la historia ha dejado para nosotros",
         "snippet": "Desde Paul Revere hasta la pandemia, estas cápsulas del tiempo guardan objetos que conectan épocas. "
         "Descubre las más antiguas y sorprendentes de la historia ."},
        {"title": "¿Qué onda con las cápsulas del tiempo? - Algarabía",
         "snippet": "Cápsula del tiempo de Seward, Nebraska. Considerada como una de las más grandes del mundo, fue "
         "sellada en 1975. Será abierta el 4 de julio de 2025. Cápsula del tiempo Yahoo! Esta « cápsula virtual» "
         "recopila archivos e imágenes digitales aportados por usuarios de todo el mundo. Fue cerrada en 2006 y se "
         "planea abrirla en 2020."},
    ],
    "duckduckgo_lite_https",
)

P19_T3 = _search(
    "What's the genre?",
    [
        {"title": "Genre",
         "snippet": "Genre ( ZHAHN-rə; French for 'kind, sort') is any style or form of communication and art in any "
         "mode (written, spoken, digital, visual, auditory, etc.) with socially agreed-upon elements, or conventions, "
         "developed over time."},
        {"title": "Film genre",
         "snippet": "A film genre is a stylistic or thematic category for motion pictures based on similarities either "
         "in the narrative elements, aesthetic approach, or the emotional response to the film."},
    ],
    "wikipedia_en_api",
)

P23_T2 = _search(
    "a drama film online",
    [{"title": "Drama histórico (cinematografía)",
      "snippet": "Se conoce como drama histórico (también conocido como drama de época) a una obra ambientada en un "
      "período de tiempo pasado, generalmente utilizada en el contexto del cine y la televisión. El drama histórico "
      "incluye ficción histórica y romances, películas de aventuras y espadachines."}],
    "wikipedia_es_api",
)

W17_T5 = _search(
    "more about the second headline",
    [
        {"title": "Betteridge's law of headlines - Wikipedia",
         "snippet": 'Betteridge\'s law of headlines is an adage that states: "Any headline that ends in a question mark '
         'can be answered by the word no."'},
        {"title": "Headline - Wikipedia",
         "snippet": "A headline is the text indicating the content or nature of the article below it, typically a news "
         "piece, by providing a form of brief summary of its contents."},
    ],
    "duckduckgo_lite_https",
)

P27_T2 = _search(
    "What genre is the cozy mystery that's been trending this week, and who's in it?",
    [
        {"title": "K-lytics Cozy Mystery Report and Seminar",
         "snippet": "What is the latest trend in cozy mystery that takes the bestseller lists by storm right now?This "
         "market research finally brings some objectivity into what is trending and what is not in this genre ."},
        {"title": "Cozy Mystery New Book Releases 2025 | Upcoming Cozy Mystery Books ...",
         "snippet": "Genre : Cozy Mystery Escape to idyllic settings with just a hint of mischief in our newest cozy "
         "mystery releases. Unravel the top cosy mysteries in 2025."},
    ],
    "duckduckgo_lite_https",
)

S087 = {"outcome": "failed", "reason": {
    "outcome": "failed", "cause": "the weather service knows no place by that name, so no forecast was read",
    "operation": "weather.current"}}

S032_SITUATION = {
    "kind": "operation", "operation": "web.news.headlines", "polarity": "success", "verified": True,
    "succeeded": True,
    "observed": {"version": 1, "topic": "Taylor Swift", "edition": "es-419/CL", "count": 3, "headlines": [
        {"title": "Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026",
         "source": "CNN en Español", "publishedAt": "Mon, 28 Sep 2026 03:46:00 GMT"},
        {"title": "De la elegancia de Taylor Swift a Lisa y Charli XCX: la alfombra roja de los MTV VMA 2026",
         "source": "BioBioChile", "publishedAt": "Mon, 28 Sep 2026 00:31:50 GMT"},
        {"title": "La crítica se harta de Taylor Swift, pero… ¿es ‘Cleveland’ tan mala?", "source": "Jenesaispop",
         "publishedAt": "Tue, 29 Sep 2026 12:39:16 GMT"},
    ], "authority": "google_news_rss_es419_cl"},
}


# ------------------------------------------------------------------ 1. the search shown


def test_d_p27_t2_none_of_the_results_is_the_search_shown() -> None:
    user = "What genre is that, and who's in it?"
    draft = "None of the results state which genre is trending this week or who is in it."
    assert _payload_fact_defect(draft, P27_T2, user, said=user) == "search_report_shows_the_search"


@pytest.mark.parametrize(
    "draft",
    [
        "Los fragmentos mencionan la cápsula de Seward sellada en 1975 para abrirse en 2025.",
        "Los resultados no mencionan los nombres de los últimos diez presidentes.",
        "La información visible solo confirma que hubo trece presidentes.",
        "The provided results do not specify a single trending genre.",
    ],
)
def test_d_p34_t1_and_d_p31_t1_fragments_and_visible_information_are_the_search_shown(draft: str) -> None:
    assert llm._SEARCH_MECHANICS.search(llm._reading_fold(draft)) is not None


def test_d_s063_the_provided_results_tail_is_clipped() -> None:
    draft = "I could not find a specific traffic update for your trip to the grocery store in the provided results."
    assert _SEARCH_RESULTS_TAIL.sub("", draft) == (
        "I could not find a specific traffic update for your trip to the grocery store."
    )
    spanish = "No encontré información sobre el precio de la acción de Movistar en los resultados disponibles."
    assert _SEARCH_RESULTS_TAIL.sub("", spanish) == (
        "No encontré información sobre el precio de la acción de Movistar."
    )


def test_results_of_a_match_are_not_the_search() -> None:
    # «Los resultados del partido» are the match's, not the search's.
    assert llm._SEARCH_MECHANICS.search(llm._reading_fold("Los resultados del partido fueron dos a uno.")) is None


# ------------------------------------------------------------------ 2. a verdict the read does not hold


def test_d_p16_t3_no_valet_parking_available_is_a_verdict_nobody_read() -> None:
    user = "Is there valet parking at the Kenzi Rose Garden in Marrakech?"
    assert _payload_fact_defect(
        "No valet parking is available at the Kenzi Rose Garden in Marrakech.", P16_T3, user, said=user
    ) != ""
    assert _payload_fact_defect(
        "I could not find valet parking at the Kenzi Rose Garden in Marrakech.", P16_T3, user, said=user
    ) == ""
    assert _places_unread_qualifiers(P16_T3, user) == ["valet"]


def test_d_p16_t1_valet_not_found_over_public_car_parks_is_honest() -> None:
    user = "Oh, I meant to search for valet parking at the Kenzi Rose Garden."
    assert _payload_fact_defect(
        "I could not find valet parking at the Kenzi Rose Garden.", P16_T1, user, said=user
    ) == ""
    # The class read itself is still not denied (M54).
    assert _payload_fact_defect(
        "I could not find parking at the Kenzi Rose Garden.", P16_T1, user, said=user
    ) == "search_places_denied"


def test_request_common_words_leave_names_out() -> None:
    assert request_common_words("Is there valet parking at the Kenzi Rose Garden?") == frozenset(
        {"there", "valet", "parking"}
    )


# ------------------------------------------------------------------ 3. «no lo encontré» with the datum read


def test_d_w14_t2_the_age_is_computed_from_the_birth_read(run_day: None) -> None:
    user = "¿y cuántos años tiene el chaval?"
    for draft in (
        "Jonas Vingegaard tiene 29 años.",
        "Jonas Vingegaard nació el 10 de diciembre de 1996.",
        "Jonas Vingegaard tiene 29 años: nació el 10 de diciembre de 1996.",
    ):
        assert _payload_fact_defect(draft, W14_T2, user, said=user) == "", draft
    for draft in ("Jonas Vingegaard tiene 27 años.", "Jonas Vingegaard nació en 1996, por lo que tiene 27 años."):
        assert _payload_fact_defect(draft, W14_T2, user, said=user) == "search_report_unsourced_claim", draft


def test_birth_ages_count_the_birthday_and_skip_a_life_that_ended() -> None:
    assert " 29 " in _birth_ages("Jonas Vingegaard (Hillerslev, 10 de diciembre de 1996) es", date(2026, 9, 29))
    assert " 30 " in _birth_ages("Jonas Vingegaard (Hillerslev, 10 de diciembre de 1996) es", date(2026, 12, 10))
    assert " 29 " in _birth_ages("Jonas Vingegaard (born 10 December 1996) is a Danish cyclist", date(2026, 9, 29))
    assert _birth_ages(P27_T3["seen"]["results"][0]["snippet"], date(2026, 9, 29)) == ""


def test_d_p24_t2_an_article_tied_to_the_name_by_its_extract_answers() -> None:
    user = "Search for something else and I change my mind. Now I want to watch Drama movies like Lizzo."
    assert _payload_fact_defect("The drama movie like Lizzo is Hustlers.", P24_T2, user, said=user) == ""


def test_d_p24_t1_an_article_without_the_kind_asked_still_does_not_answer() -> None:
    user = (
        "I am in a mood to watch movie online and I need your help to search for a nice Fantasy Movie like Elijah "
        "Wood."
    )
    draft = "I don't feel at home in this world anymore. Pawn Shop Chronicles."
    assert _payload_fact_defect(draft, P24_T1, user, said=user) == "search_report_off_subject"


def test_d_p34_t1_a_long_request_is_answered_by_the_page_that_shares_its_subject() -> None:
    user = P34_T1["seen"]["query"]
    draft = (
        "Las cápsulas más famosas incluyen la de Seward, Nebraska, sellada en 1975 para abrirse en 2025, y la cápsula "
        "virtual de Yahoo!, cerrada en 2006 con planes de apertura en 2020."
    )
    assert _payload_fact_defect(draft, P34_T1, user, said=user) == ""


def test_d_w10_t2_courtesy_words_are_not_what_was_searched() -> None:
    user = W10_T2["seen"]["query"]
    assert _payload_fact_defect("Una taza de harina equivale a 125 gramos.", W10_T2, user, said=user) == ""
    # A total nobody read is still the model's.
    assert _payload_fact_defect(
        "Cinco tazas equivalen a 625 gramos de harina.", W10_T2, user, said=user
    ) == "search_report_unsourced_claim"


# ------------------------------------------------------------------ 4. another time given as the answer


def test_d_w14_t1_another_year_does_not_answer_this_year(run_day: None) -> None:
    user = "tío, ¿quién ha ganado la Vuelta este año?"
    draft = "Jonas Vingegaard conquistó la Vuelta a España 2025."
    assert _payload_fact_defect(draft, W14_T1, user, said=user) == "search_report_other_year"
    assert _search_report_other_year("Jonas Vingegaard ganó la Vuelta a España 2026.", W14_T1, user) == ""
    asked_2025 = {**W14_T1, "seen": {**W14_T1["seen"], "query": "¿Quién ganó la Vuelta a España 2025?"}}
    assert _search_report_other_year(draft, asked_2025, "¿Quién ganó la Vuelta a España 2025?") == ""
    assert asks_this_year("¿quién ganó la liga esta temporada?")
    assert not asks_this_year("¿quién ganó la liga en 2025?")


def test_d_p05_t2_a_headline_tomorrow_is_the_day_after_it_was_published(
    run_day: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = "Necesito aparcamiento para mañana"
    draft = "El aparcamiento junto a la estación de ferrocarril abrirá mañana con más de 400 plazas."
    assert _payload_fact_defect(draft, P05_T2, user, said=user) == "search_report_stale_day"
    assert _search_report_stale_day(draft, P05_T2) == ("manana", date(2026, 9, 24))
    # On the day it was published, its «mañana» is the person's.
    monkeypatch.setattr(llm, "_report_today", lambda: date(2026, 9, 24))
    assert _search_report_stale_day(draft, P05_T2) is None
    # Saying it was not found carries no day of a headline.
    monkeypatch.setattr(llm, "_report_today", lambda: date(2026, 9, 29))
    assert _search_report_stale_day("No encontré aparcamiento para mañana.", P05_T2) is None


# ------------------------------------------------------------------ 5. a fact the read does not state


def test_d_s021_a_why_headline_does_not_state_its_clause() -> None:
    user = "me gustaría saber qué está pasando por el mundo"
    draft = (
        "El mundo ha perdido sus colores y la IA más potente está obsesionada con Mark Fisher, mientras la familia de "
        "Ranulph Fiennes desconoce su paradero y se ha asignado un nuevo mapa para Cabo de Hornos."
    )
    assert _payload_fact_defect(draft, S021, user, said=user) == "search_report_why_title_as_fact"
    assert not _search_report_why_title_as_fact("Un titular: «Por qué el mundo ha perdido sus colores».", S021)
    assert not _search_report_why_title_as_fact(
        "La familia de Ranulph Fiennes dice desconocer su paradero.", S021
    )


def test_d_p27_t3_titles_a_translation_names_must_be_the_pages() -> None:
    user = "Anything else, preferably something with Eugene Dynarski?"
    draft = (
        "Eugene Dynarski appeared in two movies directed by Steven Spielberg: The Biker and Close Encounters of the "
        "Third Kind."
    )
    assert _payload_fact_defect(draft, P27_T3, user, said=user) == "search_report_unsourced_claim"
    assert "biker" in _search_report_unsourced_words(draft, P27_T3, user)
    assert _payload_fact_defect(
        "Eugene Dynarski was an American actor who appeared in two Steven Spielberg films.", P27_T3, user, said=user
    ) == ""


def test_d_p27_t1_what_is_trending_is_not_known_without_a_read() -> None:
    user = "Any good movies for me to watch?"
    facts = {"situation": json.dumps({"kind": "conversation"})}
    draft = "If you need a break, try the new space opera or the cozy mystery that's been trending this week."
    assert compose_visible_defect(draft, "conversation", user, facts) == "unverified_present_fact"
    assert compose_visible_defect(
        "If you like mysteries, Knives Out is a fun one.", "conversation", user, facts
    ) != "unverified_present_fact"


# ------------------------------------------------------------------ 6. the word asked with, defined


def test_d_p19_t3_d_p23_t2_d_w17_t5_the_word_asked_with_is_not_defined() -> None:
    cases = (
        (P19_T3, "What's the genre?", "Genre is any style or form of communication and art in any mode with "
         "socially agreed-upon elements or conventions developed over time."),
        (P23_T2, "Look for a drama film.", "A drama film is a work set in a past period, often including historical "
         "fiction, romances, adventures, and sword-and-sandal films."),
        (W17_T5, "tell me more about the second one", "The second headline refers to the text indicating the content "
         "or nature of the article below it, typically a news piece, by providing a form of brief summary of its "
         "contents."),
    )
    for payload, user, draft in cases:
        assert _payload_fact_defect(draft, payload, user, said=user) == "search_report_defines_the_ask", user


def test_a_definition_asked_is_answered_with_the_definition() -> None:
    what_is = {**P19_T3, "seen": {**P19_T3["seen"], "query": "What is a genre?"}}
    assert _search_report_defines_the_ask(
        "Genre is any style or form of communication and art.", what_is, "What is a genre?"
    ) == ""
    assert undefined_asked_phrases("What's the genre?") == ("genre",)
    assert undefined_asked_phrases("Look for a drama film.") == ("drama film",)
    assert undefined_asked_phrases("What is the internet?") == ()
    # The attribute of a particular one, over that one's own article, answers.
    film = _search("After the Wedding genre", [{
        "title": "After the Wedding (2006 film)",
        "snippet": "After the Wedding is a 2006 Danish drama film directed by Susanne Bier, starring Mads Mikkelsen.",
    }], "wikipedia_en_api")
    assert _search_report_defines_the_ask("The genre is drama.", film, "What's the genre?") == ""
    # A title said with its capitals names a work, not the word.
    scary = {**P23_T2, "seen": {**P23_T2["seen"], "query": "scary movies"}}
    assert _search_report_defines_the_ask(
        "Scary Movie is a 2000 American black comedy.", scary, "Search for scary movies."
    ) == ""


# ------------------------------------------------------------------ 7. failures told wrong


def test_d_s087_a_place_the_weather_service_did_not_recognise_is_not_said_not_to_exist() -> None:
    user = "What's the weather este fin de semana en Abingdon Virginia?"
    assert _payload_fact_defect(
        "No hay pronóstico disponible porque no existe un lugar llamado Abingdon en Virginia.", S087, user, said=user
    ) == "place_existence_denied"
    assert _payload_fact_defect(
        "There is no such place as Abingdon, Virginia.", S087, user, said=user
    ) == "place_existence_denied"
    assert _payload_fact_defect(
        "El servicio del tiempo no reconoce Abingdon, Virginia, así que no tengo el pronóstico.", S087, user, said=user
    ) == ""


def test_d_s032_a_headline_question_quoted_is_the_headlines() -> None:
    user = "Noticias sobre Taylor Swift."
    facts = {"situation": json.dumps(S032_SITUATION, ensure_ascii=False)}
    draft = (
        "Taylor Swift supera a Beyoncé como la artista más premiada de los MTV VMA 2026; De la elegancia de Taylor "
        "Swift a Lisa y Charli XCX: la alfombra roja de los MTV VMA 2026; La crítica se harta de Taylor Swift, pero… "
        "¿es 'Cleveland' tan mala?"
    )
    assert compose_visible_defect(draft, "status", user, facts) == ""
    # BAXY asking stays BAXY's question.
    assert compose_visible_defect(draft + " ¿Quieres que te lea otra?", "status", user, facts) == "extra_claim"
