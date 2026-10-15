"""The report of a verified web search measured against the pages read and the request: each sentence, word,
number and name it states is checked against them.
"""

from __future__ import annotations

import os
import re
import threading
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import NamedTuple
from urllib.parse import urlparse

from .semantic.normalize import _accent_folded_with_punctuation
from .semantic import answer_evidence as semantic_answer_evidence
from .semantic import listing as semantic_listing
from .semantic import quantities as semantic_quantities
from .semantic.web import (
    words_asked, place_containers, ASKED_UNCONFIRMED_WORDS, asked_dimension_words, carried_subjects, names_subject,
    PLACE_KIND_WORDS, request_common_words, asks_this_year, undefined_asked_phrases, question_names,
    asks_where_to_find, asks_upcoming,
)
from .semantic.temporal import spoken_clocks
from .effect_intent import _entity_lookup_query, curiosity_request
from .semantic.request import fold as _reading_fold, read_request
from .semantic.network import _CALENDAR_MONTH_NUMBERS, _WEEKDAY_NAMES, _WEEKDAY_NUMBERS, _WEEKDAY_WORD
from .clock_facts import _CALENDAR_DATE_PATTERNS
from .compose_situation import _CAUSE_FACT, _merged_observed
from .failure_wording import _asserts_failure


_SEARCH_WEATHER_CLAIM = re.compile(
    r"(?:hace\s+(?:buen|mal|mucho|poco)\s+(?:tiempo|frio|calor)|"
    r"temperaturas?\s+(?:agradables?|moderadas?|altas?|bajas?|frescas?|calidas?|elevadas?|templadas?)|"
    r"\d{1,3}\s*(?:°|º|grados|degrees)|"
    r"(?:poco|mucho|fuerte|sin)\s+viento|"
    r"(?:baja|alta|poca|mucha|sin)\s+probabilidad\s+de\s+(?:lluvias?|precipitaciones?)|"
    r"(?:no\s+)?(?:va|van)\s+a\s+llover|(?:si|no)\s+llueve|llovera|"
    r"(?:esta|estara|amanece|amanecera)\s+(?:soleado|nublado|lluvioso|despejado|ventoso|cubierto)|"
    r"\b(?:soleado|nublado|lluvioso|despejado|cubierto)\b|"
    r"(?:it\s+)?(?:is|will\s+be|won't\s+be)\s+(?:sunny|cloudy|rainy|clear|windy|hot|cold|warm)|"
    r"(?:it\s+)?(?:will|won't|will\s+not)\s+rain|(?:low|high)\s+chance\s+of\s+rain)",
)


# The search is BAXY's own act: its not-found is said in his first person («No lo encontré»), never the
# person's («No lo encontraste»), which is how the hint addresses him. «si no lo encontraste…» advises.
_SECOND_PERSON_LOOKUP = re.compile(
    r"\b(?:encontraste|buscaste|hallaste)\b"
    r"|\byou\s+(?:didn't|did\s+not|couldn't|could\s+not|haven't|have\s+not)\s+(?:been\s+able\s+to\s+)?find\b"
)


def _search_report_names_the_person_as_finder(text: str) -> bool:
    folded = _accent_folded_with_punctuation(text).casefold()
    return any(
        re.search(r"\b(?:si|if)\b[^.,;:!?]*$", folded[: found.start()]) is None
        for found in _SECOND_PERSON_LOOKUP.finditer(folded)
    )


def _search_results_text(payload: dict) -> str | None:
    """Titles, hosts and snippets of a verified web.search, joined; None otherwise."""

    if payload.get("operation") != "web.search":
        return None
    seen = payload.get("seen")
    results = seen.get("results") if isinstance(seen, dict) else None
    if not isinstance(results, list) or not results:
        return None
    parts: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        for key in ("title", "snippet", "url"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(re.sub(r"[/._?=&%:-]+", " ", value) if key == "url" else value)
        meters = item.get("distanceMeters")
        if isinstance(meters, int) and not isinstance(meters, bool):
            # M62: how far a place read is, in metres and in kilometres, is a figure of the read too.
            parts.append(f"{meters} m {meters / 1000:g} km {round(meters / 1000, 1):g} km")
    return "\n".join(parts) if parts else None


def _search_results_of(situation: dict) -> list:
    """Los resultados de una busqueda, venga la situacion entera o el payload visible."""

    results = _merged_observed(situation).get("results")
    if not isinstance(results, list):
        seen = situation.get("seen") if isinstance(situation, dict) else None
        results = seen.get("results") if isinstance(seen, dict) else None
    return results if isinstance(results, list) else []


def _places_inside_named_place(situation: dict) -> list:
    """M56 (v3c-final F-p06-t2): the OpenStreetMap places whose address lies in every place the query named the
    searched one to be in («…en la Plaza de las Salesas en Madrid»: the ones in Madrid). With no such place named,
    all of them: they were read around the one named place."""

    places = [item for item in _search_results_of(situation) if isinstance(item, dict)]
    seen = situation.get("seen") if isinstance(situation.get("seen"), dict) else {}
    containers = place_containers(str(seen.get("query") or ""))
    if not containers:
        return places
    return [item for item in places if all(
        any(words <= part for part in _address_places(str(item.get("snippet") or ""))) for words in containers
    )]


# M58 (v3d-final F-p06-t3): «Calle Príncipe de Asturias, Villa del Prado, Comunidad de Madrid, …» is not in Madrid; the
# region carries the city's name. A place of an address is one of its parts that is not a region.
_ADDRESS_REGION = re.compile(
    r"^(?:comunidad|region|provincia|estado|departamento|condado|canton|state|province|county|department|"
    r"prefecture|prefectura|oblast)\b"
)


def _address_places(address: str) -> list[set[str]]:
    """The words of each part of an address that names a place (the street, the district, the town), regions left
    out."""

    parts = (_reading_fold(part).strip() for part in address.split(","))
    return [set(re.findall(r"[a-z0-9]+", part)) for part in parts if part and not _ADDRESS_REGION.match(part)]


def _search_result_hosts(situation: dict, limit: int = 3) -> list[str]:
    """Los sitios distintos que esta búsqueda devolvió, en orden."""

    results = _search_results_of(situation)
    hosts: list[str] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        host = (urlparse(url.strip()).hostname or "").casefold()
        host = host[4:] if host.startswith("www.") else host
        if host and host not in hosts:
            hosts.append(host)
        if len(hosts) >= limit:
            break
    return hosts


# The words a report may bring of its own: it says that it searched, what it
# found and which page says what. Everything else has to come from a result or
# from the request. WEB1879 H0060: «problemas técnicos generales del servicio»
# and «fallos en la conexión» were the model's own summary of causes; no title
# or snippet of the five results carried either.
_SEARCH_REPORT_OWN_WORDS = frozenset(
    {
        "encontre", "encontro", "encontraron", "encontrada", "encontradas",
        "encontrado", "encontrados", "varios", "varias", "articulo", "articulos",
        "pagina", "paginas", "resultado", "resultados", "busqueda", "menciona",
        "mencionan", "mencionado", "indica", "indican", "senala", "senalan",
        "sitio", "sitios", "fuente", "fuentes", "segun", "describe", "describen",
        "reporta", "reportan", "reportado", "explica", "explican", "afirma",
        "afirman", "dicen", "recomienda", "recomiendan", "ademas", "tambien",
        "otras", "otros", "general", "generales", "primera", "segunda", "tercera",
        "found", "page", "pages", "result", "results", "search", "mention",
        "mentions", "state", "states", "report", "reports", "another", "third",
        "titled", "according", "several", "article", "articles", "site", "sites",
        "source", "sources", "list", "lists", "note", "notes", "recommend",
        "recommends", "recommended",
        # H0463: «la página … indica que el App ID es 1098290; otra página menciona
        # el juego pero no especifica el App ID»: verbs that report what a page
        # does or does not carry, and the word for what Steam lists, are the
        # report's own voice, not a claim about the world.
        "especifica", "especifican", "proporciona", "proporcionan", "indico",
        "muestra", "muestran", "incluye", "incluyen", "contiene", "contienen",
        "aparece", "aparecen", "corresponde", "corresponden", "pertenece",
        "perteneciente", "titulada", "titulado", "juego", "juegos", "game", "games",
        "entrada", "entradas", "entry", "entries", "registro", "record", "listed",
        "listada", "listado", "shows", "specifies", "provides", "includes", "contains",
        "appears", "belongs", "corresponds", "titulo", "title", "lleva", "llevan",
        "carries", "carry", "datos",
        # SEARCH2015 H0098: counting the results, ordering the pages and the
        # verbs that say what a page offers are the report's own voice too.
        "cinco", "cuatro", "seis", "siete", "ocho", "nueve", "sobre", "acerca",
        "ofrece", "ofrecen", "destaca", "destacan", "presenta", "presentan",
        "finalmente", "distintas", "distintos", "diferentes", "ultima", "ultimo",
        "cuarta", "quinta", "reune", "reunen", "recoge", "recogen", "trata", "tratan",
        "three", "four", "five", "six", "seven", "eight", "nine", "about", "offers",
        "highlights", "presents", "finally", "different", "various", "fourth", "fifth",
        "gathers", "covers", "deals",
        # Uso real 2026-09-23 (tipo de cambio, pastel de choclo, chistes): «se
        # encuentra», «una lista de», «define», «está disponible en», «se puede
        # consultar en» say where a page is and what it does, not a fact of the world.
        "encuentra", "encuentran", "lista", "listas", "define", "definen",
        "disponible", "disponibles", "available", "consulta", "consultar",
        "sugiere", "sugieren", "suggests", "repite", "repiten", "enlace", "enlaces",
        "links", "texto", "textos", "fragmento", "fragmentos", "snippet", "snippets",
        "website", "websites", "webpage", "portal", "portales",
        # tanda-02: a question about what to wear tonight came back with pages
        # about ties and flashcards; «the pages I found are about something
        # else» is the honest report of results that do not answer it.
        "something",
        # Uso real tanda 4f «¿el sábado podremos comer en una terraza?»: «ninguna de estas páginas
        # lo dice explícitamente sobre terrazas» says how far the pages go, and «se puede encontrar» where.
        "explicitamente", "explicitly", "especificamente", "specifically", "encontrar",
    }
)

# Uso real 2026-09-23: the closed classes of the language (determiners,
# pronouns, auxiliaries, quantifiers, connectives) carry no fact of their own.
# «Exchange-Rates.org también tiene un conversor», «Calculaya permite convertir
# pesos chilenos a diversas divisas» died because «tiene» and «diversas» were in
# no snippet. Content words (nouns, adjectives, full verbs) are still grounded.
_SEARCH_REPORT_GRAMMAR_WORDS = frozenset(
    {
        "tiene", "tienen", "tenia", "tener", "puede", "pueden", "podria", "podrian",
        "poder", "deben", "hacer", "estar", "estan", "estaba", "estaban", "siendo",
        "haber", "habia", "habian", "seria", "serian", "permite", "permiten",
        "todos", "todas", "alguno", "alguna", "algunos", "algunas", "alguien",
        "ninguno", "ninguna", "nadie", "mismo", "misma", "mismos", "mismas",
        "cuando", "donde", "mientras", "aunque", "porque", "entre", "hasta", "desde",
        "hacia", "durante", "cuales", "quien", "quienes", "cuanto", "cuanta",
        "cuantos", "cuantas", "tanto", "tanta", "tantos", "tantas", "mucho", "mucha",
        "muchos", "muchas", "pocos", "pocas", "diversos", "diversas", "estos", "esos",
        "esas", "aquel", "aquella", "aquellos", "aquellas", "ellos", "ellas", "usted",
        "ustedes", "siempre", "nunca", "luego", "despues", "antes", "ahora",
        "todavia", "solamente", "incluso", "asimismo", "entonces", "cualquier",
        "cualquiera", "demas", "ambos", "ambas", "llamado", "llamada", "llamados",
        "llamadas", "dicho", "dicha", "respecto", "mediante",
        # Uso real tanda 4f «existen varios podcasts», «puedes escuchar»: that a thing exists, or that the
        # person can do it, is said with «hay» and «puede» too.
        "existe", "existen", "puedes", "podemos",
        "which", "where", "there", "their", "those", "after", "before", "being",
        "would", "could", "should", "might", "other", "others", "every", "while",
        "since", "until", "through", "within", "without", "among", "because",
        "again", "still", "whose", "either", "neither", "called", "named", "having",
    }
)


def _text_language(text: str) -> str | None:
    """es or en when the words of a text say so clearly; None for a name or a mix."""

    spanish, english = read_request(text).evidence
    if spanish >= 2 and spanish > english:
        return "es"
    if english >= 2 and english > spanish:
        return "en"
    return None


# The words of a number up to twelve: a page that writes «tres naciones» states
# the 3 a report may write in digits, and the other way round.
_SMALL_NUMBER_WORDS = {
    "0": ("cero", "zero"), "1": ("uno", "una", "one"), "2": ("dos", "two"),
    "3": ("tres", "three"), "4": ("cuatro", "four"), "5": ("cinco", "five"),
    "6": ("seis", "six"), "7": ("siete", "seven"), "8": ("ocho", "eight"),
    "9": ("nueve", "nine"), "10": ("diez", "ten"), "11": ("once", "eleven"),
    "12": ("doce", "twelve"),
}


# A number of a report; one glued to letters is part of a name («24timezones.com», «PM2.5»).
_REPORT_NUMBER = re.compile(r"(?<![\w.,:+-])\d+(?:[.,:]\d+)*(?!\w)")


# M88 (DEV-D v3r D-p12-t2 «Bring up 24/7 stores near me» → «There are five 24/7 stores near Curico, including a
# concierge delivery service, a verified store finder…, luggage storage…»): five was how many pages the search read,
# none of them a list of five stores. A count said in words is a number of the report like one said in digits: the
# pages or the request write it, or it counts the items the sentence itself lists after a colon. «los dos», «the two»
# point back at things already named and count nothing new; «once» is also English («once a week»).
_REPORT_COUNT_WORDS = {
    word: digit for digit, words in _SMALL_NUMBER_WORDS.items() if int(digit) >= 2 for word in words if word != "once"
}
_REPORT_COUNT = re.compile(
    r"(?<!\blos\s)(?<!\blas\s)(?<!\bthe\s)(?<!\bestos\s)(?<!\bestas\s)(?<!\bthese\s)(?<!\bthose\s)(?<!\bboth\s)"
    r"\b(?P<count>" + "|".join(sorted(_REPORT_COUNT_WORDS, key=len, reverse=True)) + r")\s+(?=[\w/])"
)


def _listed_items(rest: str) -> int:
    """How many items a sentence lists after its colon («: A, B y C» → 3); 0 without a colon."""

    _, colon, listed = rest.partition(":")
    if not colon:
        return 0
    return len([item for item in re.split(r",|\s(?:y|e|and|or|o)\s", listed) if item.strip(" .;")])


# SEARCH2015 H0098: counting the results or pages read («Se encontraron cinco resultados…») is the report's voice
# (tests/test_c03_search2005_query.py); what they are about is what a count of the world must ground.
_READ_PAGE_NOUNS = re.compile(
    r"(?:resultados?|paginas?|sitios?|enlaces?|fuentes?|articulos?|results?|pages?|sites?|links?|sources?|articles?)\b"
)


def _search_report_unsourced_counts(sentence: str, grounds: str) -> list[str]:
    """M88: the counts said in words (two to twelve) of a report sentence that the pages, the request or the
    sentence's own list do not give (see above); a count of the results or pages read is not judged."""

    folded = _reading_fold(sentence)
    folded_grounds = _reading_fold(grounds)
    missing: list[str] = []
    for found in _REPORT_COUNT.finditer(folded):
        word = found.group("count")
        digit = _REPORT_COUNT_WORDS[word]
        if re.search(r"(?<![\d.,])" + digit + r"(?![\d]|[.,]\d)", folded_grounds) or any(
            re.search(r"\b" + form + r"\b", folded_grounds) for form in _SMALL_NUMBER_WORDS[digit]
        ):
            continue
        if _listed_items(folded[found.end():]) == int(digit):
            continue
        if _READ_PAGE_NOUNS.match(folded, found.end()) is not None:
            continue
        missing.append(word)
    return missing


def _search_report_unsourced_numbers(sentence: str, grounds: str) -> list[str]:
    """The numbers of a report sentence that neither the pages it cites nor the request write.

    Ronda 22 (r18 t1-c03): the pages' figures are compared with their separators of thousands dropped too
    («2.925.466.085» is «2 925 466 085»), and a figure the sentence marks as rounded («casi 3 mil millones») is the
    pages' when it is within a tenth of one they write (semantic.quantities.marked_roundings)."""

    folded_grounds = _reading_fold(grounds)
    folded_grounds += "\n" + semantic_quantities.without_digit_groups(folded_grounds)
    rounded = semantic_quantities.marked_roundings(sentence, grounds)
    missing: list[str] = []
    for number in _REPORT_NUMBER.findall(sentence):
        if number in rounded:
            continue
        forms = {number, number.replace(",", "."), number.replace(".", ","), re.sub(r"[.,]", "", number)}
        if any(
            re.search(r"(?<![\d.,])" + re.escape(form) + r"(?![\d]|[.,]\d)", folded_grounds)
            for form in forms
        ) or any(
            re.search(r"\b" + word + r"\b", folded_grounds)
            for word in _SMALL_NUMBER_WORDS.get(number.lstrip("0") or "0", ())
        ):
            continue
        missing.append(number)
    return missing


# A sentence that says the asked thing was not found or cannot be told (folded). «No hay …» or «there is no …» state
# an absence in the world, not in the pages, and stay judged. «No se menciona/indica…» is the pages narrated
# (_SEARCH_NARRATED_ABSENCE), not a not-found.
_SEARCH_NOT_FOUND = re.compile(
    # M58 (v3d-final F-p05-t1): «No he encontrado aparcamiento en …» over the car parks OpenStreetMap read is the
    # same «no lo encontré».
    r"^\W*(?:no\s+(?:(?:lo|la|los|las|le)\s+)?(?:encontre|halle|(?:he|hemos)\s+(?:podido\s+)?(?:encontrar|encontrado|"
    r"hallado)|pude\s+(?:encontrar|hallar|determinar|confirmar|saber|"
    r"precisar|ver)|puedo\s+(?:confirmar|determinar|saber|precisar|decir(?:te)?)|se\s+(?:"
    r"encontro|pudo\s+(?:encontrar|determinar|confirmar)|puede\s+(?:determinar|saber|confirmar|precisar)))|"
    r"(?:i\s+)?(?:couldn'?t|could\s+not|can'?t|cannot|didn'?t|did\s+not|wasn'?t\s+able\s+to|was\s+not\s+able\s+to)\s+"
    r"(?:find|determine|confirm|tell|say|see))\b"
)
# M83: the same, said in English (the language a not-found report was told in).
_SEARCH_NOT_FOUND_EN = re.compile(
    r"^\W*(?:i\s+)?(?:couldn'?t|could\s+not|can'?t|cannot|didn'?t|did\s+not|wasn'?t\s+able\s+to|was\s+not\s+able\s+to)"
    r"\s+(?:find|determine|confirm|tell|say|see)\b"
)


_CURRENCY_SIGN_NAMES = {
    "$": frozenset({"peso", "pesos", "dolar", "dolares", "dollar", "dollars"}),
    "€": frozenset({"euro", "euros"}),
    "£": frozenset({"libra", "libras", "pound", "pounds"}),
}
# M146 (DEV-H v4o H-s001 «oye, ¿me podrias decir a como anda el dolar hoy?» over the reference rate «1 USD = 981.19
# CLP»): «Hoy el dólar está a 981.19 pesos chilenos.» died as search_report_unsourced_claim on «pesos» and «chilenos»,
# the turn ended in ⚠ (v4o) or in a false «No encontré…» (v4p, v4q). A currency code the pages write is said with its
# name, as a sign is; its figures are still the pages' own. Folded; the codes the rate source serves (Frankfurter).
_CURRENCY_CODE_NAMES = {
    "USD": frozenset({"dolar", "dolares", "dollar", "dollars", "estadounidense", "estadounidenses"}),
    "EUR": frozenset({"euro", "euros"}),
    "GBP": frozenset({"libra", "libras", "esterlina", "esterlinas", "pound", "pounds", "sterling"}),
    "JPY": frozenset({"yen", "yenes", "japones", "japoneses", "japanese"}),
    "CAD": frozenset({"dolar", "dolares", "dollar", "dollars", "canadiense", "canadienses", "canadian"}),
    "AUD": frozenset({"dolar", "dolares", "dollar", "dollars", "australiano", "australianos", "australian"}),
    "NZD": frozenset({"dolar", "dolares", "dollar", "dollars", "neozelandes", "neozelandeses"}),
    "CHF": frozenset({"franco", "francos", "suizo", "suizos", "franc", "francs", "swiss"}),
    "CNY": frozenset({"yuan", "yuanes", "renminbi", "chino", "chinos", "chinese"}),
    "INR": frozenset({"rupia", "rupias", "rupee", "rupees", "india", "indian"}),
    "MXN": frozenset({"peso", "pesos", "mexicano", "mexicanos", "mexican"}),
    "CLP": frozenset({"peso", "pesos", "chileno", "chilenos", "chilean"}),
    "ARS": frozenset({"peso", "pesos", "argentino", "argentinos", "argentine"}),
    "COP": frozenset({"peso", "pesos", "colombiano", "colombianos", "colombian"}),
    "UYU": frozenset({"peso", "pesos", "uruguayo", "uruguayos", "uruguayan"}),
    "DOP": frozenset({"peso", "pesos", "dominicano", "dominicanos", "dominican"}),
    "PHP": frozenset({"peso", "pesos", "filipino", "filipinos", "philippine"}),
    "BRL": frozenset({"real", "reales", "reais", "brasileno", "brasilenos", "brazilian"}),
    "PEN": frozenset({"sol", "soles", "peruano", "peruanos", "peruvian"}),
}


# M70 (held-out v3h t14 «averiguá qué dijo la crítica»): «Otra menciona que John Carpenter no se subió a los elogios» over
# the title «John Carpenter no se sube a los elogios de Oppenheimer» died on «subio»: a stem whose tense changes at its
# fourth letter («sub-ió», «sub-e») escaped the four-letter rule. The endings a word takes when conjugated or declined.
_INFLECTION_ENDINGS = frozenset(
    {
        "", "a", "e", "o", "i", "s", "as", "es", "os", "an", "en", "io", "ia", "ias", "ian", "aba", "aban", "ado",
        "ada", "ados", "adas", "ido", "ida", "idos", "idas", "aron", "ieron", "amos", "emos", "imos", "ed", "ing",
    }
)


def _shares_inflected_stem(word: str, seen_word: str) -> bool:
    """«subio» and «sube», «lamento» and «lamenta»: two folded words of four letters or more that share their first
    three letters and all but one letter of the shorter, and differ only by an ending of conjugation or declension
    («ganso» and «gana», «casino» and «casa», «salto» and «salsa» do not)."""

    if min(len(word), len(seen_word)) < 4:
        return False
    common = len(os.path.commonprefix((word, seen_word)))
    return (
        common >= max(3, min(len(word), len(seen_word)) - 1)
        and word[common:] in _INFLECTION_ENDINGS
        and seen_word[common:] in _INFLECTION_ENDINGS
    )


_REPORT_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12, "january": 1, "february": 2,
    "march": 3, "april": 4, "may": 5, "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}
_REPORT_MONTH = "(?:" + "|".join(_REPORT_MONTHS) + ")"
# A person's birth as an encyclopedia writes it (folded): «(Hillerslev, 10 de diciembre de 1996)», «(born 10 December
# 1996)», «(born December 10, 1996)», «nació el 10 de diciembre de 1996». A parenthesis that closes with a second date
# («13 de septiembre de 1932-27 de febrero de 2020») is a life that ended, not an age.
_BIRTH_DATE = re.compile(
    r"(?:\((?:[^()\d]{0,80},\s*)?|\bborn\s+(?:on\s+)?|\bnaci(?:o|da|do)\s+(?:el\s+)?)"
    r"(?:(?P<day>\d{1,2})\s+(?:de\s+)?(?P<month>" + _REPORT_MONTH + r")|(?P<month2>" + _REPORT_MONTH
    + r")\s+(?P<day2>\d{1,2}),?)\s+(?:de\s+|del\s+)?(?P<year>\d{4})(?!\s*[-–—]\s*\d)(?=\s*[)\s,.;])"
)


def _report_today() -> date:
    """Today, for what a report computes from a date it read (M77)."""

    return datetime.now().date()


def _birth_ages(results_text: str, today: date) -> str:
    """M77 (DEV-D v3l D-w14-t2 «¿y cuántos años tiene el chaval?» over «Jonas Vingegaard Rasmussen (Hillerslev, 10 de
    diciembre de 1996)»): «nació el 10 de diciembre de 1996» died on «nació» and the age was «not found». The birth an
    encyclopedia writes is a birth read, and the age it gives today is a figure of the read: the words that say it and
    the age computed, in both languages; empty when no birth is written."""

    grounds: list[str] = []
    for found in _BIRTH_DATE.finditer(_reading_fold(results_text)):
        day = int(found.group("day") or found.group("day2"))
        month = _REPORT_MONTHS[found.group("month") or found.group("month2")]
        year = int(found.group("year"))
        if not 1 <= day <= 31 or year > today.year:
            continue
        age = today.year - year - ((today.month, today.day) < (month, day))
        grounds.append(f"nacio nacido nacida nacimiento born birth edad age {age} anos años years old")
    return " ".join(grounds)


class _ReportSentence(NamedTuple):
    """One sentence of a search report, measured against the pages and the request."""

    not_found: bool
    numbers: list[str]  # its numbers that neither the pages nor the request write
    lettered: list[str]  # its content words that no page and no request shares
    content: int  # how many content words it has
    named: bool  # a content word or a number of it is the pages' or the request's
    translated: bool  # it says in its language what pages in the other language say
    titles: list[str] = []  # the words of a title it writes that no page and no request writes (M77)
    listed: int = 0  # how many names the pages write it lists (M105)


# M77 (DEV-D v3l D-p27-t3 «Eugene Dynarski appeared in two movies directed by Steven Spielberg: The Biker and Close
# Encounters of the Third Kind» over «dos películas de Steven Spielberg: El diablo sobre ruedas y Encuentros en la
# tercera fase»): a translated sentence is not judged word by word, and the model gave the Spanish titles English names
# of its own («The Biker» is no film of Spielberg's). A title is a run of capitalised words inside the sentence that
# opens with a capitalised article or joins its words with «of», «the», «de»…; its words must be read.
_TITLE_ARTICLES = frozenset({"the", "a", "an", "el", "la", "los", "las", "un", "una"})
_TITLE_JOINERS = frozenset({"of", "the", "a", "an", "and", "in", "on", "to", "at", "de", "del", "la", "las", "los", "el",
                            "y", "en", "un", "una"})


def _unread_title_words(sentence: str, observed: set[str], written: set[str]) -> list[str]:
    """The capitalised words of the titles a sentence writes, when most of a title's words no page nor request
    writes (folded)."""

    unread: list[str] = []
    run: list[tuple[str, bool]] = []  # (folded word, capitalised)
    joiners: list[str] = []

    def close() -> None:
        capitalised = [word for word, upper in run if upper and word not in _TITLE_ARTICLES]
        shaped = len([1 for _, upper in run if upper]) >= 2 and (
            any(not upper for _, upper in run) or run[0][0] in _TITLE_ARTICLES
        )
        missing = [
            word for word in capitalised
            if word not in observed and not any(_shares_inflected_stem(word, seen) for seen in written)
        ]
        if shaped and capitalised and len(missing) * 2 > len(capitalised):
            unread.extend(word for word in missing if word not in unread)
        run.clear()
        joiners.clear()

    for index, raw in enumerate(str(sentence).split()):
        bare = raw.strip("¿¡\"'«(“‘").rstrip(".,;:!?»\")”’…")
        folded = _reading_fold(bare)
        if not bare or not re.fullmatch(r"[a-z0-9'-]+", folded):
            if run:
                close()
            continue
        if bare[:1].isupper() and index > 0 and bare != "I":
            run.extend((joiner, False) for joiner in joiners)
            joiners.clear()
            run.append((folded, True))
        elif run and folded in _TITLE_JOINERS:
            joiners.append(folded)
        elif run:
            close()
        if run and raw.rstrip(".,;:!?»\")”’…") != raw:
            close()
    if run:
        close()
    return unread


_LISTED_NAME = re.compile(
    r"(?<![\w'’])[A-Z][\w'’:-]*(?:\s+(?:(?:of|the|a|an|and|in|on|to|de|del|la|el|los|las|y|en)\s+)?[A-Z0-9][\w'’:-]*)*"
)


def _listed_page_names(sentence: str, pages: str) -> int:
    """M105: how many names a report sentence writes, past its first word, that the pages write as they stand."""

    read = _reading_fold(pages)
    # A quoted title is the page named, not a list of what it holds.
    unquoted = re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " | ", str(sentence))
    names = {
        _reading_fold(found.group(0)).strip(" :")
        for found in _LISTED_NAME.finditer(unquoted)
        if found.start() > 0 and len(found.group(0)) >= 4
    }
    return sum(1 for name in names if name and name in read)


# M168 (D77; DEV-G v4y G-w42-t1, DEV-I I-w12-t3, I-w26-t1): ESPN's public calendar (EspnScheduleSource) answers when a
# team plays, or how its last match went, in one English sentence: «Next game: Los Angeles Lakers play away against
# Sacramento Kings on Monday 2026-10-05 at 23:00 local time (UTC-03:00), NBA Preseason, at Golden 1 Center.». The report
# says it in the person's language («Los Lakers juegan el lunes a las 23:00 contra los Kings.»): the weekday, the month
# and the clock in either language and either dial, «tonight» for today's date, «de visitante» for «away», are figures
# and words of that read; a weekday, a clock or a name it does not give is not, whatever the language of the sentence
# (a translated sentence is otherwise judged only by its numbers and titles). A start time ESPN has not confirmed
# («TBD») has no clock at all.
_MATCH_AUTHORITY = "espn_public_schedule"
_MATCH_MOMENT = re.compile(
    r"\bon (?P<weekday>monday|tuesday|wednesday|thursday|friday|saturday|sunday) (?P<year>\d{4})-(?P<month>\d{2})-"
    r"(?P<day>\d{2})(?: at (?P<hour>\d{2}):(?P<minute>\d{2}) local time)?"
)
# The score read: «beat Unión (Santa Fe) 3-0 at home», «Playing now: Boca Juniors 1, Instituto (Córdoba) 0 (…)».
_MATCH_SCORES = (
    re.compile(r"\b(?P<own>\d{1,3})-(?P<other>\d{1,3}) (?:at home|away)\b"),
    re.compile(r"\bplaying now: [^,]*?(?P<own>\d{1,3}), [^,(]*?(?P<other>\d{1,3})\b"),
)
# A score said: «3 a 0», «3-0», «112 to 108».
_MATCH_SAID_SCORE = re.compile(r"(?<![\d:])\b(\d{1,3})\s*(?:-|–|a|to|por)\s*(\d{1,3})\b(?![\d:])")
_MATCH_SIDE_WORDS = {
    "at home": "local casa recibe reciben recibira host hosts hosting home",
    "away": "visitante visita visitan visitara fuera afuera road visit visits visiting away",
    "beat": "gano ganaron vencio vencieron derroto derrotaron victoria triunfo won win beat beating",
    "lost to": "perdio perdieron cayo cayeron derrota lost loss losing",
    "drew": "empato empataron empate igualo igualaron drew draw tied tie",
}
# A national side ESPN names in English and a Spanish report names in Spanish.
_MATCH_SIDE_NAMES_ES = {
    "brazil": "brasil", "germany": "alemania", "england": "inglaterra", "france": "francia", "spain": "espana",
    "italy": "italia", "netherlands": "paises bajos holanda", "united states": "estados unidos eeuu",
    "belgium": "belgica", "morocco": "marruecos", "japan": "japon", "switzerland": "suiza", "croatia": "croacia",
    "denmark": "dinamarca", "sweden": "suecia", "norway": "noruega", "poland": "polonia", "scotland": "escocia",
    "wales": "gales", "ireland": "irlanda", "turkey": "turquia", "south korea": "corea del sur",
    "saudi arabia": "arabia saudita", "egypt": "egipto", "canada": "canada", "new zealand": "nueva zelanda",
}


def _match_reads(payload: dict) -> list[tuple[str, date, tuple[int, int] | None]]:
    """The moments of ESPN's calendar read in this payload: weekday (English, folded), local date, clock (None when
    ESPN has no confirmed start time)."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if payload.get("operation") != "web.search" or seen.get("authority") != _MATCH_AUTHORITY:
        return []
    reads: list[tuple[str, date, tuple[int, int] | None]] = []
    for item in _search_results_of(payload):
        if not isinstance(item, dict):
            continue
        found = _MATCH_MOMENT.search(_reading_fold(str(item.get("snippet") or "")))
        if found is None:
            continue
        try:
            day = date(int(found.group("year")), int(found.group("month")), int(found.group("day")))
        except ValueError:
            continue
        clock = (int(found.group("hour")), int(found.group("minute"))) if found.group("hour") else None
        reads.append((found.group("weekday"), day, clock))
    return reads


def _match_pages(payload: dict) -> str:
    return _reading_fold("\n".join(
        f"{item.get('title') or ''} {item.get('snippet') or ''}" for item in _search_results_of(payload)
        if isinstance(item, dict)
    ))


def _match_report_grounds(payload: dict) -> str:
    """M168: the figures and words of ESPN's read as a report in either language may say them."""

    reads = _match_reads(payload)
    if not reads:
        return ""
    months = {number: [name for name, value in _REPORT_MONTHS.items() if value == number] for number in range(1, 13)}
    today = _report_today()
    grounds: list[str] = []
    for weekday, day, clock in reads:
        index = _WEEKDAY_NUMBERS[weekday]
        grounds += [_reading_fold(_WEEKDAY_NAMES["es"][index]), weekday, str(day.day), f"{day.day:02d}",
                    str(day.year), *months[day.month]]
        if day == today:
            grounds.append("hoy today tonight noche")
        elif day == today + timedelta(days=1):
            grounds.append("manana tomorrow")
        if clock is not None:
            hour, minute = clock
            dial = hour % 12 or 12
            part = "pm p m noche tarde evening night" if hour >= 12 else "am a m manana morning"
            grounds += [f"{hour}:{minute:02d}", f"{hour:02d}:{minute:02d}", f"{dial}:{minute:02d}", str(hour),
                        str(dial), part, "hora local horas local time"]
    pages = _match_pages(payload)
    grounds += [words for said, words in _MATCH_SIDE_WORDS.items() if re.search(rf"\b{said}\b", pages)]
    grounds += [words for name, words in _MATCH_SIDE_NAMES_ES.items() if re.search(rf"\b{name}\b", pages)]
    return " ".join(grounds)


def _match_report_unread(draft: str, payload: dict, user_text: str) -> list[str]:
    """M168: what a report of ESPN's read says of the match that the read does not give: a weekday that is not the
    match's, a clock that is not its start (or any clock when ESPN has none), a name no result, no request and no
    Spanish name of a side writes. A weekday or clock the person said themselves is theirs to repeat."""

    reads = _match_reads(payload)
    if not reads:
        return []
    said = _reading_fold(user_text or "")
    folded = _reading_fold(draft)
    unread: list[str] = []
    weekdays = {_WEEKDAY_NUMBERS[weekday] for weekday, _, _ in reads}
    for found in re.finditer(rf"\b{_WEEKDAY_WORD}\b", folded):
        if _WEEKDAY_NUMBERS[found.group(0)] not in weekdays and not re.search(rf"\b{found.group(0)}\b", said):
            unread.append(found.group(0))
    starts = {clock for _, _, clock in reads if clock is not None}
    told = {(clock.hour, clock.minute) for clock in spoken_clocks(said)}
    for clock in spoken_clocks(folded):
        matches = any(
            (clock.hour, clock.minute) == start if clock.resolved
            else (clock.hour % 12, clock.minute) == (start[0] % 12, start[1])
            for start in starts
        )
        if not matches and (clock.hour, clock.minute) not in told:
            unread.append(clock.literal.strip(" .,;:!?"))
    # The score of the match read, either side first; the day of the month is no score.
    pages = _match_pages(payload)
    scores = {
        pair
        for pattern in _MATCH_SCORES
        for found in pattern.finditer(pages)
        for pair in ((found.group("own"), found.group("other")), (found.group("other"), found.group("own")))
    }
    if scores:
        for found in _MATCH_SAID_SCORE.finditer(folded):
            if (found.group(1), found.group(2)) not in scores and found.group(0) not in unread:
                unread.append(found.group(0))
    known =set(re.findall(r"[a-z0-9]+", f"{_match_pages(payload)} {said} {_match_report_grounds(payload)}"))
    for sentence in re.split(r"(?<=[.!?])\s+", str(draft).strip()):
        for raw in re.findall(r"[^\W\d_][\w'’-]*", sentence)[1:]:
            if not raw[:1].isupper():
                continue
            for word in re.findall(r"[a-z0-9]+", _reading_fold(raw)):
                if (
                    len(word) >= 3
                    and word not in _WEEKDAY_NUMBERS
                    and word not in _REPORT_MONTHS
                    and not any(seen.startswith(word[:4]) for seen in known)
                    and word not in unread
                ):
                    unread.append(word)
    return unread


def _search_report_unsourced_words(text: str, payload: dict, user_text: str) -> list[str]:
    """The words of the report that no result and no request shares.

    Judged sentence by sentence, the same for a named page as for an unnamed
    one (WEB1889: naming the page vouched for «problemas de conexion», which no
    result carried). The SEARCH2019 hint names these words back to the model.

    Uso real tanda 4 «Whats the air quality hoy?»: the pages were English and
    the report Spanish, so every translated word («calidad», «pronóstico»,
    «contaminantes») was «unsourced», the three drafts fell and the turn ended
    in the bare list of titles. A sentence that cites only pages written in the
    other language cannot be checked word by word; its numbers still must be
    the pages' own. And one paraphrased word («abarcan», «explanation»,
    «opción») among many that the pages do write is the report's wording, not a
    claim: a claim brings words of its own, and every number of a sentence is
    checked whatever its words.
    """

    words: list[str] = []
    for sentence in _search_report_sentences(text, payload, user_text):
        if sentence.not_found:
            # Uso real tanda 6 «…¿qué hora será?»: «No se indica la hora exacta de la salida del sol» died on
            # «exacta» and the turn ended in ⚠. Saying what was not found claims nothing of the world; its numbers
            # are still the pages' or the person's.
            words.extend(number for number in sentence.numbers if number not in words)
            continue
        lettered = sentence.lettered
        if sentence.translated:
            # M77 (D-p27-t3): a translated sentence keeps the titles the pages write.
            lettered = sentence.titles
        elif len(lettered) == 1 and (sentence.content >= 8 or sentence.listed >= 2):
            # M105 (DEV-D v4a D-p27-t1 «You can watch popular films like Spider-Man: No Way Home, The Matrix
            # Resurrections, and Don't Look Up.» died on «films» over pages that write «movies», and the turn said
            # «I couldn't find it.»): one paraphrased common word in a sentence that lists names the pages write is
            # the report's wording around what was read.
            lettered = []
        words.extend(word for word in sentence.numbers + lettered if word not in words)
    # M168: what a report of ESPN's calendar says of the match that the calendar does not give.
    words.extend(word for word in _match_report_unread(text, payload, user_text) if word not in words)
    return words


def _search_report_names_nothing(text: str, payload: dict, user_text: str) -> bool:
    """M70 (held-out v3h t14 «averiguá qué dijo la crítica»): over five pages about the critics of Oppenheimer the
    third draft «Nadie lo dijo.» was published. A report of a search that found pages, none of whose sentences names a
    word or a number of the pages or of the request, says nothing of what was looked up; when no draft can say it, the
    turn ends in the not-found that names it. Saying it was not found, and a translation, are judged elsewhere."""

    sentences = _search_report_sentences(text, payload, user_text)
    return bool(sentences) and not any(
        sentence.not_found or sentence.named or sentence.translated for sentence in sentences
    )


def _search_report_leaves_out_subject(text: str, payload: dict, user_text: str, said: str | None) -> list[str]:
    """M71 (held-out v3j t14 «averiguá qué dijo la crítica» after «anoche vi Oppenheimer…»): the subjects, as the
    understood request or the query writes them, that the report must name and does not.

    The search was about a name the conversation carried, not the person's own message (``said``;
    semantic.web.carried_subjects), and «Una crítica de un científico de Infobae se menciona y John Carpenter no se
    subió a los elogios de la película.» was published without saying which film. A report that states something
    names at least one such subject that the results write. Without the person's message (``said`` None) nothing is
    required; saying it was not found is left to the not-found, which names what was looked up (M64, M70)."""

    if said is None or _search_results_text(payload) is None:
        return []
    if all(
        _SEARCH_NOT_FOUND.match(_reading_fold(sentence)) is not None
        for sentence in re.split(r"(?<=[.!?])\s+", str(text).strip())
        if sentence.strip()
    ):
        return []
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    pages = "\n".join(
        f"{item.get('title') or ''} {item.get('snippet') or ''}"
        for item in _search_results_of(payload)
        if isinstance(item, dict)
    )
    subjects = [
        subject
        for subject in carried_subjects(user_text or "", str(seen.get("query") or ""), said, pages)
        if names_subject(pages, subject)
    ]
    if any(names_subject(text, subject) for subject in subjects):
        return []
    return subjects


# Ronda 22 (r18 t1-c03 «La película más taquillera es Avengers: Endgame y no encontré el listado completo.»): a
# sentence that states what was found and then, joined by «y», «pero» or «but», what was not, is two: the not-found
# clause claims nothing of the world and is judged as one (_SEARCH_NOT_FOUND), the rest as any statement.
_NOT_FOUND_JOIN = re.compile(
    r"\s*[,;]?\s+(?:pero|y|aunque|mas|but|and|although|though)\s+"
    r"(?=no\s|i\s+couldn|couldn|i\s+could\s+not|could\s+not|i\s+didn|didn|i\s+wasn|wasn|i\s+can|can'?t|cannot)",
    re.IGNORECASE,
)


def _report_clauses(text: str) -> list[str]:
    """The sentences of a report, a not-found clause joined to a statement taken apart from it (above)."""

    clauses: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", str(text).strip()):
        joint = next(
            (
                found for found in _NOT_FOUND_JOIN.finditer(sentence)
                if _SEARCH_NOT_FOUND.match(_reading_fold(sentence[found.end():])) is not None
            ),
            None,
        )
        if joint is not None and sentence[: joint.start()].strip():
            clauses += [sentence[: joint.start()].strip() + ".", sentence[joint.end():].strip()]
        else:
            clauses.append(sentence)
    return clauses


def _search_report_sentences(text: str, payload: dict, user_text: str) -> list[_ReportSentence]:
    """The sentences of the report of a verified search, each measured against the pages and the request; empty
    without results."""

    results_text = _search_results_text(payload)
    if results_text is None:
        return []
    seen = payload.get("seen")
    # Tanda 4c: the city this PC's search was made near, and saying it was near, are observed too.
    near = seen.get("near") if isinstance(seen, dict) and isinstance(seen.get("near"), str) else ""
    near_voice = f"{near} cerca near" if near.strip() else ""
    query = str(seen.get("query") or "") if isinstance(seen, dict) else ""
    # M70 (held-out v3h t16): what a question of when, where or how much asks for is part of what was asked.
    asked = asked_dimension_words(f"{user_text or ''}\n{query}")
    # M77 (D-w14-t2): a birth read gives the age today and the words that say it.
    births = _birth_ages(results_text, _report_today())
    observed = set(re.findall(r"[a-z]+", _reading_fold(results_text))) | set(
        re.findall(r"[a-z]+", _reading_fold(f"{user_text} {near_voice} {births}"))
    ) | asked
    # M54 (v3b-final F-w13-t2 «40 litros de nafta súper cuestan 82.360 pesos» over «$82.360»): a currency sign the
    # pages write is said with its name.
    for sign, names in _CURRENCY_SIGN_NAMES.items():
        if sign in results_text:
            observed |= names
    for code, names in _CURRENCY_CODE_NAMES.items():
        # M146: the code as the pages write it, a whole upper-case word («981.19 CLP»).
        if re.search(rf"(?<![A-Za-z]){code}(?![A-Za-z])", results_text):
            observed |= names
    results = [item for item in _search_results_of(payload) if isinstance(item, dict)]

    def page_text(items: list[dict]) -> str:
        return "\n".join(
            [str(item.get(key) or "") for item in items for key in ("title", "snippet")]
            # M62: how far a place read is (metres and kilometres).
            + [
                f"{item['distanceMeters']} m {item['distanceMeters'] / 1000:g} km "
                f"{round(item['distanceMeters'] / 1000, 1):g} km"
                for item in items
                if isinstance(item.get("distanceMeters"), int) and not isinstance(item.get("distanceMeters"), bool)
            ]
        )

    # M62 (F-w13-t2): the total BAXY computed from a unit price read is a figure of the read too.
    computed = " ".join(item.sentence for item in semantic_quantities.priced_totals(user_text or "", results_text))
    # M92 (D-w01-t3): so is what a per-unit rule read gives for the quantity asked.
    computed += " " + " ".join(item.sentence for item in semantic_quantities.rated_totals(user_text or "", results_text))
    computed += " " + births
    # M168: the moment of a match ESPN's calendar gave, as either language says it.
    matched = _match_report_grounds(payload)
    computed += " " + matched
    observed |= set(re.findall(r"[a-z]+", matched))
    # M70: the words the pages and the request write (no link, and not the query the mind sent), for the inflection
    # of a changing stem.
    written = set(re.findall(r"[a-z]+", _reading_fold(f"{page_text(results)}\n{user_text or ''}")))
    sentences: list[_ReportSentence] = []
    for sentence in _report_clauses(text):
        grounds = page_text(results) + "\n" + (user_text or "") + "\n" + computed
        numbers = _search_report_unsourced_numbers(sentence, grounds)
        grounded = len(_REPORT_NUMBER.findall(sentence)) > len(numbers)
        # M88 (DEV-D v3r D-p12-t2 «There are five 24/7 stores…»): a count said in words is judged like one in digits.
        numbers += _search_report_unsourced_counts(sentence, grounds)
        folded = _reading_fold(sentence)
        if _SEARCH_NOT_FOUND.match(folded) is not None:
            sentences.append(_ReportSentence(True, numbers, [], 0, grounded, False))
            continue
        said = re.findall(r"[a-z]+", folded)
        # M70 (held-out v3h t16): «No hay fecha de estreno confirmada», «sin confirmar una fecha»: that the asked date,
        # place or amount is not confirmed yet says what was not found.
        unconfirmed = bool(asked & set(said)) and re.search(_SEARCH_RESULT_NEGATION, folded) is not None
        content = 0
        shared = 0
        lettered: list[str] = []
        for word in said:
            if (
                len(word) < 5
                or word in _SEARCH_REPORT_GRAMMAR_WORDS
                or (unconfirmed and word in ASKED_UNCONFIRMED_WORDS)
                # The report's own voice, conjugated: «incluyendo», «explicando».
                or any(
                    word.startswith(own) and len(word) - len(own) <= 4
                    for own in _SEARCH_REPORT_OWN_WORDS
                    if len(own) >= 5
                )
            ):
                continue
            content += 1
            # Inflection is tolerated by the first four letters («enviar» for
            # «envío»), and a short observed word may take its plural
            # («yenes» for «yen»); a word no result shares that much is the
            # model's.
            if word in lettered:
                continue
            if any(
                seen_word.startswith(word[:4])
                or (len(seen_word) >= 3 and word.startswith(seen_word) and len(word) - len(seen_word) <= 2)
                for seen_word in observed
            ) or any(_shares_inflected_stem(word, seen_word) for seen_word in written):
                shared += 1
                continue
            lettered.append(word)
        language = _text_language(sentence)
        translated = (
            language is not None
            # A translation says what the page says; a bare verdict («está
            # prohibido») is no translation of a page and is judged by its words.
            and content >= 4
            and all(_text_language(page_text([item])) not in (None, language) for item in results)
        )
        sentences.append(
            _ReportSentence(
                False, numbers, lettered, content, grounded or shared > 0, translated,
                _unread_title_words(sentence, observed, written) if translated else [],
                # A name of its own («Disney+» beside «Netflix, HBO Max») is never the report's wording.
                0 if any(
                    word[:1].isupper() and _reading_fold(word) in lettered
                    for word in re.findall(r"[^\W\d_][\w'’-]*", sentence)[1:]
                ) else _listed_page_names(sentence, page_text(results)),
            )
        )
    return sentences


def _search_report_answer_unstated(text: str, payload: dict, user_text: str) -> list[str]:
    """Uso real v3 tanda 1 «quien gano el mundial del 2014» → «Brasil ganó la Copa Mundial de Fútbol de 2014.»: the
    names a report answers a relation question with («quién ganó», «who directed») that no sentence of a result says
    together with that relation. Every word was in the pages; the answer was not (semantic.answer_evidence)."""

    if _search_results_text(payload) is None:
        return []
    return semantic_answer_evidence.answer_unstated(
        text, user_text or "", _search_results_of(payload), _SEARCH_NOT_FOUND,
    )


def _search_listing_not_from_one_ranking(text: str, payload: dict, user_text: str) -> list[str]:
    """Uso real v3 tanda 1 «dame el top 5» → one name from an encyclopedia and four from a photo gallery: a listing
    asked is told only with things one result names, and that result is a ranking (semantic.answer_evidence)."""

    if _search_results_text(payload) is None:
        return []
    # A structured source (places, rates, a match) gives one thing per result, and its order is the source's own
    # (distance for places): no result of it lists the others, and naming each one found is what was asked.
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if seen.get("authority") in _SEARCH_STRUCTURED_AUTHORITIES:
        return []
    asked = payload.get("askedCount")
    if not (type(asked) is int or semantic_listing.listing_asked(user_text or "") is not None):
        return []
    results = _search_results_of(payload)
    # Revisión 1 de la ronda 24 (r23 t1-c03 #1): a sentence that says which one is first names the first row of the
    # ranking a result numbers, and none is said first when two numbered rankings disagree.
    return [
        *semantic_answer_evidence.listing_not_from_one_ranking(text, user_text or "", results),
        *semantic_answer_evidence.first_claimed_unranked(text, results),
    ]


def _search_report_unsourced_claim(text: str, payload: dict, user_text: str) -> bool:
    """A sentence of the report states something that is neither in a result nor asked."""

    if _match_reads(payload):
        # M168 (DEV-H H-w23-t4 «ok who are the lakers playing tonight»): a match's moment is judged whoever asks it.
        return bool(_search_report_unsourced_words(text, payload, user_text))
    if (
        _entity_lookup_query(user_text or "") is not None
        # WEB1889: la pregunta de investigacion SI es un informe, y esta
        # exencion era lo que dejaba pasar un final sin una sola pagina
        # nombrada. Quien-o-que-es y la curiosidad siguen fuera: esas
        # contestan con el fragmento, no informan de paginas.
        or curiosity_request(user_text or "")
    ):
        return False
    return bool(_search_report_unsourced_words(text, payload, user_text))


# Uso real 2026-09-23 «cuál es la tasa de cambio entre el peso chileno y el yen»:
# «Nuestro conversor de moneda le permite conocer el cambio…» pasted a snippet
# and made the page's «we» BAXY's own; «le decimos en cuánto está el dólar»
# the same. BAXY reports pages in its own voice; a quoted title may keep theirs.
# A bare «we» stays out: «AI as we know it today» is the generic we, not a page.
_PAGE_FIRST_PERSON_PLURAL = re.compile(
    r"\b(?:nuestr[oa]s?|nosotr[oa]s|hemos|(?:le|les|te|os)\s+[a-z]+mos|our|ours)\b"
)
# Uso real tanda 6 «sería genial cenar en este nuevo restaurante…» → «Descubre los mejores restaurantes abiertos cerca
# de ti. Consulta menús, reseñas, fotos…»: a sentence that opens by telling the reader to discover, check or browse is
# the page's call to its visitor, not an answer. Read with its accents: «consulté», «busqué» are BAXY's own past,
# «consulte», «busca» the page's order.
_PAGE_CALL_TO_READER = re.compile(
    r"(?:^|(?<=[.!?;:]))\s*[¿¡]?\s*(?:descubr[ea]|consult[ae]|explor[ae]|encuentr[ae]|conoc[ea]|conozca|"
    r"compar[ae]|reserv[ae]|elige|elija|busca|visit[ae]|acced[ea]|disfrut[ae]|suscríbete|regístrate|"
    r"descarga|descargue|check|discover|explore|find|view|browse|read|watch|learn|compare|book|visit|enjoy|"
    r"subscribe|sign\s+up|download|get)\b(?!\s*,)"
    # Tanda 6c «Se pueden consultar menús, reseñas y fotos de restaurantes abiertos cerca de ti…»: the same call said
    # as what the reader may do on the page, anywhere in the sentence. Only the verbs of using a page: «se puede ver la
    # aurora en Noruega», «you can visit the Louvre» answer.
    r"|\b(?:se\s+pueden?|puedes|pod[eé]s|podr[aá]s|puede\s+usted|you\s+can|you\s+may|you'?ll\s+be\s+able\s+to)\s+"
    r"(?:consultar|reservar|comparar|descubrir|explorar|suscribirte|suscribirse|registrarte|registrarse|descargar|"
    r"check\s+out|browse|book|compare|discover|explore|subscribe|sign\s+up|download)\b"
)
# Tanda 6c «Los expertos de TU han preparado para ti una lista…»: the page addressing its visitor («para ti», «for
# you») is its voice; BAXY says the answer without the page's dedication.
_PAGE_ADDRESS_TO_READER = re.compile(r"\b(?:para\s+ti|for\s+you)\b")
# Tanda 9 «dime el tiempo de Madrid» → «El Tiempo en Madrid… previsión actualizada del tiempo. Temperaturas,
# probabilidad de lluvias…», «what traffic will be like in Tempe» → «Tempe traffic flow and incidents map provides live
# traffic, road conditions…»: the page describing itself (what its map or site offers, how fresh or live its data
# is) is its advertisement, not the answer. When no page states the answer, it was not found.
_PAGE_SELF_DESCRIPTION = re.compile(
    r"\b(?:map|maps|mapa|mapas|site|website|sitio|pagina|page|portal)\b(?:\s+\w+){0,2}\s+"
    r"(?:provides?|offers?|shows?|features?|includes?|lets|allows|gives|brings|"
    r"ofrece|muestra|incluye|permite|brinda|proporciona|entrega|trae)\b|"
    r"\b(?:prevision|pronostico|forecast|informacion|information|info|datos|data|noticias|news|trafico|traffic|"
    r"mapa|map)\s+(?:\w+\s+)?(?:actualizad[oa]s?|al\s+dia|en\s+(?:tiempo\s+real|vivo|directo)|updated|"
    r"up[-\s]to[-\s]date|in\s+real[-\s]time)\b|"
    r"\b(?:live|real[-\s]time|up[-\s]to[-\s]date|interactive)\s+(?:traffic|maps?|updates|forecasts?|data|weather)\b|"
    r"\bmapas?\s+interactivos?\b"
)
# M102 (DEV-D v3z D-p12-t2 «Bring up 24/7 stores near me» → «There are 24/7 delivery services and verified store maps
# available near Curico.»): a page's finder, locator or map said to be there is the page describing itself, and no
# store was named. Judged after the unsourced words, whose hint names them (M88 D-p12-t2 «five 24/7 stores»).
_PAGE_FINDER = re.compile(
    r"\b(?:finders?|locators?|buscadores?\s+de\s+(?:tiendas|locales|lugares|negocios))\b|"
    r"\b(?:maps?|mapas?|listings?|listados?|directory|directories|directorios?)\b(?:\s+\w+){0,2}\s+"
    r"(?:available|disponibles?)\b"
)


def _search_report_offers_a_finder(text: str, payload: dict, user_text: str) -> bool:
    """M102: the report of a verified search names a page's finder, locator or available map as what was found."""

    if _search_results_text(payload) is None:
        return False
    asked = _reading_fold(user_text or "")
    return any(
        re.search(r"\b" + re.escape(found.group().strip()) + r"\b", asked) is None
        for found in _PAGE_FINDER.finditer(_reading_fold(re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(text))))
    )
# Tanda 7 «Bob Dean afirma que … nunca lo hemos estado»: a first person plural inside what a named person says or
# believes is theirs, reported, not the page speaking.
_REPORTED_SPEECH = re.compile(
    r"\b(?:afirm|dic|dij|sostien|sostuv|asegur|cre[eiy]|explic|mencion|declar|cuent|cont[oó]|opin|"
    r"say|said|claim|believ|state|argu|told|insist)\w*\s+(?:\w+\s+){0,3}(?:que|that)\b"
)


def _search_report_speaks_as_a_page(text: str, payload: dict, user_text: str) -> bool:
    """The report of a verified search speaks as a page: its first person plural, its call to the reader, its
    address to the reader or its description of itself."""

    if _search_results_text(payload) is None:
        return False
    unquoted = re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(text))
    asked = _reading_fold(user_text or "")
    folded = _reading_fold(unquoted)

    # Only a result's title: a headline reported is news, a snippet pasted in its first person is the page speaking
    # (test_c03_uso_real_compose «Nuestro conversor de moneda le permite…» stays vetoed).
    read = _reading_fold("\n".join(
        str(item.get("title") or "") for item in _search_results_of(payload) if isinstance(item, dict)
    ))

    def reported(said: str, found: re.Match[str]) -> bool:
        sentence = re.split(r"[.!?;]", said[: found.start()])[-1]
        return _REPORTED_SPEECH.search(sentence) is not None

    def quoted(said: str, found: re.Match[str]) -> bool:
        # M81 (DEV-D v3m D-s021 «…cómo el gris conquistó nuestra vida»): the headline's own «nuestra vida», said
        # with the word that follows it in the result, is the headline reported, not the page speaking to BAXY's
        # listener.
        following = re.match(r"\s+([a-z0-9]+)", said[found.end():])
        return following is not None and re.search(
            r"\b" + re.escape(found.group()) + r"\s+" + re.escape(following.group(1)) + r"\b", read
        ) is not None

    return any(
        re.search(r"\b" + re.escape(_reading_fold(found.group()).strip(" ¿¡")) + r"\b", asked) is None
        and not (pattern is _PAGE_FIRST_PERSON_PLURAL and (reported(said, found) or quoted(said, found)))
        for pattern, said in (
            (_PAGE_FIRST_PERSON_PLURAL, folded),
            (_PAGE_CALL_TO_READER, unquoted.casefold()),
            (_PAGE_ADDRESS_TO_READER, folded),
            (_PAGE_SELF_DESCRIPTION, folded),
        )
        for found in pattern.finditer(said)
    )


# Owner rule 2026-09-24: a web lookup is invisible. «¿Qué son las Tortugas
# Ninja?» is answered «Las Tortugas Ninja son cuatro tortugas mutantes…»,
# never «Según ejemplo.com…», «Busqué en internet y encontré…» or a list of
# pages: the person must not notice that BAXY looked it up. What the answer
# says is still only what the pages say (_search_report_unsourced_words).
_SEARCH_ATTRIBUTION = re.compile(
    r"\b(?:segun|according\s+to|de\s+acuerdo\s+con|citing|cita\s+a)\s+(?:(?:el|la|los|las|un|una|the|an?)\s+)?"
    r"(?:[\w-]+\.(?:com|org|net|es|cl|mx|ar|co|info|gov|edu|io|uk|de|fr|cat|pe|us)\b|"
    r"(?:pagina|paginas|sitio|sitios|web|articulo|articulos|fuente|fuentes|wikipedia|page|pages|site|sites|"
    r"website|article|articles|source|sources|result|results|resultado|resultados|"
    # Uso real tanda 6 «…puede ser alto según la lista de las acciones más caras del mundo»: a page's list,
    # ranking, guide or reviews cited is the page cited.
    r"lista|listas|list|lists|ranking|rankings|guia|guias|guide|guides|resenas|reviews)\b)"
)
_SEARCH_MECHANICS = re.compile(
    r"\b(?:busque|he\s+buscado|estuve\s+buscando|hice\s+una\s+busqueda|la\s+busqueda|mi\s+busqueda|"
    r"(?:encontre|halle|vi)\s+(?:estas|esta|varias|algunas|unas|tres|dos|cinco)\s+(?:paginas?|resultados?|fuentes?|sitios?)|"
    r"(?:estas|esas|las|varias|algunas)\s+(?:paginas|fuentes|sitios\s+web)|"
    r"(?:en|de)\s+(?:ese|este|un|otro)\s+sitio|(?:en|de)\s+(?:esa|esta|una|otra)\s+pagina|"
    r"ninguna\s+de\s+(?:estas|las)\s+paginas|resultados\s+de\s+(?:la\s+)?busqueda|"
    # Uso real tanda 6 «No se indica la hora exacta … en los resultados».
    r"(?:en|de|entre)\s+(?:los|estos|mis)\s+resultados|(?:in|from|among)\s+(?:the|these|my)\s+results|"
    r"i\s+searched|i\s+looked\s+(?:it\s+)?up|my\s+search|the\s+search|search\s+results?|"
    r"i\s+found\s+(?:these|this|some|several|a\s+few|three|two|five)\s+(?:pages?|results?|sources?|sites?)|"
    r"(?:these|those|the|several|some)\s+(?:pages|sources|websites)|(?:on|from)\s+(?:that|this|one|another)\s+(?:site|page)|"
    r"none\s+of\s+(?:these|the)\s+pages|"
    # Guion t35 (28-09) «Un resultado dice que la primera obra … mientras que otro afirma …»: results compared aloud
    # are the search shown.
    # M115 (DEV-F v4e2 F-w26-t2 «…con un resultado de 2-1 frente a Junior»): a match's score is no search result.
    r"(?:un|otro|el\s+primer|el\s+segundo)\s+resultado(?!\s+(?:de\s+|of\s+)?\d+\s*(?:-|–|a|to)\s*\d+)|"
    r"otro\s+(?:dice|afirma|indica|sostiene)|"
    r"(?:one|another|the\s+first|the\s+second)\s+result(?!\s+(?:of\s+)?\d+\s*(?:-|–|to)\s*\d+)|"
    r"another\s+(?:says|states|claims)|"
    # M70 (held-out v3h t14/t16): once «subió» and «fecha» stopped vetoing them, «Cierta página señala que el nieto…
    # Otra menciona que John Carpenter…» and «Un artículo de La Vanguardia indica que…» would have been published: a
    # page, article or source that speaks, or «otra» that says, is the search shown the same.
    r"(?:un|una|otro|otra|cierto|cierta|algun|alguna|el|la|este|esta|ese|esa)\s+"
    # M92 (DEV-D v3u D-w10-t2 «Un conversor de cocina menciona que la harina es más ligera…»): a tool, a table or a
    # guide that speaks is a page that speaks.
    r"(?:pagina|articulo|nota|fuente|sitio|medio|publicacion|reportaje|conversor|convertidor|calculadora|tabla|guia|"
    r"blog|foro|herramienta|web)(?:\s+(?:de|del)(?:\s+[a-z0-9]+){1,3}?)?\s+"
    r"(?:dice|indica|senala|menciona|afirma|sostiene|asegura|informa|explica|cuenta|reporta|comenta)|"
    r"otra\s+(?:dice|afirma|indica|sostiene|menciona|senala|asegura|cuenta)|"
    r"(?:one|another|an?|the|this|that)\s+(?:(?:kitchen|cooking|online|recipe|news|web)\s+)?"
    r"(?:page|article|source|site|outlet|piece|converter|calculator|table|chart|"
    r"guide|blog|forum|tool|website)(?:\s+(?:from|by|on)(?:\s+[a-z0-9]+)"
    r"{1,3}?)?\s+(?:says|states|claims|mentions|notes|reports|explains|indicates)|"
    r"another\s+(?:mentions|notes|reports|indicates)|"
    # M93 (DEV-D v3u D-s061 «…cientos de miles de empleados, como se menciona en el artículo revisado por Nicholas
    # Ferraro…»): the page said in the passive («se menciona en el artículo», «as stated in the article») or by who
    # wrote or reviewed it is the page named the same.
    r"(?:como\s+)?se\s+(?:menciona|indica|dice|senala|afirma|explica|informa|cuenta|detalla)\s+en\s+"
    r"(?:el|la|un|una|este|esta|ese|esa)\s+(?:pagina|articulo|nota|fuente|sitio|publicacion|reportaje|post|web)|"
    r"(?:el|un|este|ese)\s+articulo\s+(?:revisado|publicado|escrito|firmado)\s+(?:por|en)|"
    r"(?:as\s+)?(?:mentioned|stated|noted|explained|reported|said)\s+(?:in|on)\s+(?:the|an?|this|that)\s+"
    r"(?:page|article|source|site|post|piece)|(?:the|an?|this|that)\s+article\s+(?:reviewed|published|written)\s+by|"
    # M77 (DEV-D v3l D-p27-t2 «None of the results state which genre…», D-s063 «…in the provided results», D-p34-t1
    # «Los fragmentos mencionan…», D-p31-t1 «La información visible solo confirma…», «Los resultados no mencionan…»):
    # the results, fragments or visible information named as what speaks, or qualified as the ones given, are the
    # search shown the same.
    r"none\s+of\s+(?:the|these|my)\s+(?:\w+\s+)?results|ninguno\s+de\s+(?:los|estos)\s+(?:\w+\s+)?resultados|"
    # M102 (DEV-D v3z D-p26-t2 «Santa Rosa Cinemas, Roxy Stadium 14 … are the places mentioned for movies in Santa
    # Rosa.»): what was found called the places, names or options «mentioned» or «listed» tells the pages that named them.
    r"(?:the|these|those)\s+(?:places|ones|options|names|venues|spots|locations|titles|items)\s+"
    r"(?:mentioned|listed|cited)|(?:los|las|estos|estas|esos|esas)\s+(?:lugares|sitios|opciones|nombres|locales|"
    r"titulos)\s+(?:mencionad[oa]s|citad[oa]s|listad[oa]s)|"
    r"(?:the|these|my)\s+(?:provided|returned|available|given|retrieved|visible)\s+(?:search\s+)?(?:results|information|"
    # M105 (DEV-D v4a D-p23-t2 «I could not find specific drama films mentioned in the provided text.»).
    r"snippets|texts?|data|sources|pages|content|passages?|documents?)|"
    r"(?:el|los|este|estos)\s+textos?\s+(?:proporcionad|dad|suministrad|facilitad|disponible)[oa]?s?|(?:los|estos|mis)\s+resultados\s+(?:disponibles|proporcionados|obtenidos|encontrados|mostrados|"
    r"visibles)|(?:los|estos|esos)\s+(?:fragmentos|extractos|snippets)|(?:the|these|those)\s+(?:snippets|excerpts)|"
    # «The snippet describes a drama movie called Hustlers…», «El fragmento dice…».
    r"(?:the|this|that)\s+(?:snippet|excerpt)|(?:el|este|ese)\s+(?:snippet|extracto|fragmento)\s+(?:no\s+)?"
    r"(?:dice|menciona|describe|indica|muestra|habla|senala|nombra|incluye)|"
    r"la\s+informacion\s+(?:visible|disponible|proporcionada|encontrada|obtenida)|"
    r"(?:los|estos|esos)\s+resultados\s+(?:(?:solo|solamente|unicamente|tampoco)\s+)?(?:no\s+)?(?:mencionan|muestran|"
    r"indican|dicen|detallan|especifican|incluyen|hablan|confirman|senalan|nombran|analizan|describen)|"
    r"(?:the|these|those)\s+results\s+(?:only\s+)?(?:(?:do\s+not|don'?t|did\s+not|didn'?t)\s+)?(?:show|mention|state|"
    r"say|specify|include|indicate|confirm|name|list|describe))\b"
)
# Tanda 7 «No se menciona ningún famoso…», «No se indica cuánto tiempo queda…»: an absence told as what a text does
# not say narrates the pages that were read. The owner's not-found is «No lo encontré».
_SEARCH_NARRATED_ABSENCE = re.compile(
    r"\bno\s+se\s+(?:menciona|mencionan|indica|indican|especifica|especifican|dice|detalla|detallan|precisa|nombra|"
    r"nombran|informa|aclara)\b|"
    r"\b(?:(?:is|are|was|were)\s+not|isn'?t|aren'?t|wasn'?t|weren'?t)\s+(?:mentioned|stated|specified|listed|"
    r"indicated|named|given)\b|\bno\s+mention\s+of\b|\b(?:doesn'?t|does\s+not)\s+(?:mention|specify|state|indicate)\b"
)
# Fase 3.5b held-out «¿la serie The Last of Us vale la pena?» with nothing found → «No encontré la serie The Last of
# Us porque no existe; solo hay el videojuego.»: a lookup that answered nothing carries no cause, so a reason the
# reply gives for it (the thing does not exist, only something else does, anything but not finding it) is invented.
_NOT_FOUND_EXISTENCE_DENIAL = re.compile(
    r"\bno\s+existen?\b|\b(?:doesn'?t|does\s+not|don'?t|do\s+not)\s+exist\b|\b(?:isn'?t|is\s+not)\s+real\b|"
    r"\bno\s+es\s+real\b|\bsolo\s+(?:hay|existe|existen)\b|\bthere\s+is\s+only\b|\bonly\s+exists?\b"
)
_NOT_FOUND_REASON = re.compile(
    r"\b(?:porque|ya\s+que|debido\s+a|puesto\s+que|because)\b(?P<after>[^.;]{0,160})|"
    r"(?P<before>[^.;]{0,160}?)\b(?:por\s+lo\s+que|asi\s+que|therefore)\b"
)
_NOT_FOUND_ITSELF = re.compile(
    r"encontr|hall[eoa]|\bfound\b|\bfind\b|informacion|information|\bdatos\b|\bdata\b|resultado|\bresults?\b"
)
# A7 B (FINAL t151/t233, DEV-A3 t274): a verified search that holds nothing that answers is reported «I couldn't
# find it» / «no lo encontré» by the owner's rule, and the last resort says exactly that; the success branch read it
# as a failure asserted and vetoed it, so the turn ended in ⚠. Only the not-found clause is exempt.
_SEARCH_NOT_FOUND_CLAUSE = re.compile(
    r"\b(?:i\s+)?(?:couldn'?t|could\s+not|didn'?t|did\s+not|was\s+not\s+able\s+to|wasn'?t\s+able\s+to)\s+find\b"
    r"|\bno\s+(?:(?:lo|la|los|las)\s+)?(?:pude\s+encontrar|encontre|halle)\b|\bnot\s+found\b|\bno\s+results\b"
    r"|\bsin\s+resultados\b"
)
_SEARCH_OPERATIONS = frozenset({"web.search", "web.news.headlines"})


def _search_not_found_report(text: str, situation: dict) -> bool:
    if (
        str(situation.get("operation") or "") not in _SEARCH_OPERATIONS
        or situation.get("verified") is not True
        or situation.get("succeeded") is not True
    ):
        return False
    folded = _accent_folded_with_punctuation(text)
    clauses = re.split(r"[.;:!?\n]+|,\s*(?:but|pero|and|y)\b", folded)
    # M70 (held-out v3h t16 «¿Cuándo sale la próxima temporada…?» → «…sin confirmar una fecha de estreno»): that the
    # date, place or amount asked is not confirmed yet is the not-found of that search, not a failure of BAXY's.
    asked = asked_dimension_words(str(_merged_observed(situation).get("query") or ""))

    def not_found(clause: str) -> bool:
        return _SEARCH_NOT_FOUND_CLAUSE.search(clause) is not None or (
            bool(asked & set(re.findall(r"[a-z]+", _reading_fold(clause))))
            and re.search(_SEARCH_RESULT_NEGATION, _reading_fold(clause)) is not None
        )

    found = [clause for clause in clauses if not_found(clause)]
    if not found:
        return False
    rest = " . ".join(clause for clause in clauses if not not_found(clause))
    return not _asserts_failure(rest)


# M54 (v3b-final F-p03-t1 «can you find the note called grocery?» over a verified note list that holds only «Llego
# tarde hoy»): «I cannot find a note called "grocery"» was vetoed as a failure asserted, and the retry published «No
# found a note titled grocery». A verified listing that does not hold the named item is told as not found; the item
# the clause names (quoted, or after called/named/titled/llamada/titulada) must be in no listed entry.
_LISTING_NOT_FOUND_CLAUSE = re.compile(
    r"\b(?:i\s+)?(?:can'?t|cannot|couldn'?t|could\s+not|didn'?t|did\s+not|don'?t|do\s+not)\s+(?:find|see)\b"
    r"|\bno\s+(?:(?:lo|la|los|las)\s+)?(?:encuentro|encontre|veo|pude\s+encontrar|hay\s+ningun[oa]?)\b"
    r"|\bthere\s+(?:is|are)\s+no\b|\bnot\s+found\b"
)
_LISTING_NAMED_ITEM = re.compile(
    r"[«\"“]([^»\"”]{1,120})[»\"”]|\b(?:called|named|titled|llamad[oa]s?|titulad[oa]s?)\s+([^\s,;.]+(?:\s+[^\s,;.]+)?)"
)
_LISTING_KEYS = ("notes", "items", "files", "entries", "names", "tasks", "events", "reminders", "notifications")


def _listing_not_found_report(text: str, situation: dict) -> bool:
    if situation.get("verified") is not True or situation.get("succeeded") is not True:
        return False
    observed = _merged_observed(situation)
    listed = [observed[key] for key in _LISTING_KEYS if isinstance(observed.get(key), list)]
    if not listed:
        return False
    entries = " \n ".join(
        _reading_fold(" ".join(str(value) for value in entry.values() if isinstance(value, str)))
        if isinstance(entry, dict) else _reading_fold(str(entry))
        for group in listed for entry in group
    )
    folded = _accent_folded_with_punctuation(text)
    clauses = re.split(r"[.;:!?\n]+|,\s*(?:but|pero|and|y)\b", folded)
    found = [clause for clause in clauses if _LISTING_NOT_FOUND_CLAUSE.search(clause)]
    if not found:
        return False
    items = [
        item
        for clause in found for match in _LISTING_NAMED_ITEM.finditer(clause)
        if (item := _reading_fold(match.group(1) or match.group(2)).strip(" «»\"'“”"))
    ]
    if not items or any(item in entries for item in items):
        return False
    rest = " . ".join(clause for clause in clauses if not _LISTING_NOT_FOUND_CLAUSE.search(clause))
    return not _asserts_failure(rest)


# «según Tripadvisor», «according to BBC Mundo»: a source named by its proper name.
_SEARCH_NAMED_SOURCE = re.compile(
    r"\b(?:[Ss]eg[uú]n|[Aa]ccording\s+to|[Dd]e\s+acuerdo\s+con)\s+(?:(?:el|la|los|las|the)\s+)?[A-ZÁÉÍÓÚÑ][\w.-]*"
)


def _not_found_invents_a_cause(text: str, payload: dict) -> bool:
    """A lookup that answered nothing is told as not found; a reason given for it that is not the not-finding itself
    («porque no existe», «solo hay el videojuego», «no es un videojuego, por lo que…») is a fact nobody observed."""

    reason = payload.get("reason")
    if _search_results_text(payload) is not None or not (
        isinstance(reason, dict) and reason.get("operation") == "web.search"
    ):
        return False
    folded = _reading_fold(re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(text)))
    if _NOT_FOUND_EXISTENCE_DENIAL.search(folded) is not None:
        return True
    return any(
        _NOT_FOUND_ITSELF.search(found.group("after") or found.group("before") or "") is None
        for found in _NOT_FOUND_REASON.finditer(folded)
    )


# M77 (DEV-D v3l D-s087 «What's the weather este fin de semana en Abingdon Virginia?» → «No hay pronóstico disponible
# porque no existe un lugar llamado Abingdon en Virginia.»): the weather service did not recognise the name; that the
# place does not exist is a fact nobody read. Folded.
_PLACE_EXISTENCE_DENIAL = re.compile(
    _NOT_FOUND_EXISTENCE_DENIAL.pattern
    + r"|\bno\s+hay\s+(?:ningun[oa]?\s+)?(?:lugar|ciudad|pueblo|localidad|sitio|poblacion)\b"
    r"|\bthere\s+(?:is|are)\s+no\s+(?:such\s+)?(?:place|city|town|location)\b|\bno\s+such\s+(?:place|city|town|location)\b"
    r"|\b(?:place|city|town|location)\s+(?:does\s+not|doesn'?t)\s+exist\b"
)


def _place_existence_denied(text: str, payload: dict) -> bool:
    """The weather service knew no place by the name asked, and the reply says the place does not exist."""

    reason = payload.get("reason")
    if not isinstance(reason, dict) or reason.get("cause") != _CAUSE_FACT["weather_place_not_found"]:
        return False
    folded = _reading_fold(re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(text)))
    return _PLACE_EXISTENCE_DENIAL.search(folded) is not None


# M41 (official-window DEV-A 2026-09-28 «what's your recommendation for dining out tonight», «best parking
# manhattan»): «I did not find a specific recommendation in the search results» was vetoed three times for naming
# the search, and the turn failed. That closing phrase is form, not content: it is clipped before costing a retry.
# Ronda 22 «vetos que reparan sin rehacer» (pasada r18 t4-c02 t3 «Sí, hay una película llamada "Andábamos sin
# buscarnos" basada en Rayuela, pero no se menciona ninguna adaptación para Bestiario ni Octaedro en los resultados.»,
# t1-c03 «Según la Wikipedia, la película más taquillera es…»): a veto that a clause of the draft earns took the whole
# draft and the next one was worse. The clauses a draft can lose and stay whole are its sentences, its list lines, a
# short lead before its first comma («Según la Wikipedia,») and a tail joined by a contrast («, pero …», «; …»).
# Ronda 22: set by a composition whose not-found was reached because the time ran out after a refused draft, so that
# no answer after the not-found is asked of the model (per thread: each turn composes on its own).
_COMPOSE_TIME_SPENT = threading.local()
_CLAUSE_TAIL = re.compile(r"\s*(?:;|,\s+(?:pero|aunque|sino|mientras\s+que|but|although|though|while|whereas)\b)")
_CLAUSE_LEAD_WORDS = 5


def _draft_clauses(text: str, *, sentences_only: bool = False) -> list[tuple[int, int]]:
    """The spans of ``text`` that ``_without_clause`` may drop (above); a list line is one whole. ``sentences_only``:
    its sentences alone, a list marker kept with its item («1. El asalto…»)."""

    value = str(text or "")
    lines = [found for found in re.finditer(r"[^\n]+", value) if found.group().strip()]
    if len(lines) >= 2:
        return [(found.start(), found.end()) for found in lines]
    spans: list[tuple[int, int]] = []
    starts = [0] + [
        found.end() for found in re.finditer(r"(?<=[.!?…])\s+", value)
        # «1. El asalto…»: a list marker opens its item, it ends no sentence.
        if re.search(r"(?:^|\s)\d{1,2}[.)]$", value[: found.start()]) is None
    ]
    ends = starts[1:] + [len(value)]
    for start, end in zip(starts, ends):
        sentence = value[start:end]
        if not sentence.strip():
            continue
        spans.append((start, end))
        if sentences_only:
            continue
        body_end = start + len(sentence.rstrip().rstrip(".!?…"))
        lead = re.match(r"\s*([^,.!?;:]+),\s+", sentence)
        if lead is not None and len(lead.group(1).split()) <= _CLAUSE_LEAD_WORDS and start + lead.end() < body_end:
            spans.append((start, start + lead.end()))
        tail = next((found for found in _CLAUSE_TAIL.finditer(value, start, body_end)), None)
        if tail is not None and tail.start() > start:
            spans.append((tail.start(), body_end))
    return spans


def _without_clause(text: str, span: tuple[int, int]) -> str:
    """``text`` without the clause at ``span``: spaces and closing mark tidied, a capital opening, a list renumbered."""

    value = str(text or "")
    start, end = span
    multiline = "\n" in value.strip()
    rest = value[:start] + value[end:]
    if multiline:
        rest = semantic_listing.renumbered("\n".join(line for line in rest.split("\n") if line.strip()))
        return rest.strip()
    rest = re.sub(r"[ \t]{2,}", " ", rest).strip()
    rest = re.sub(r"\s+([.!?,;])", r"\1", rest)
    rest = semantic_listing.renumbered(rest)
    if not rest:
        return ""
    opening = len(rest) - len(rest.lstrip("¿¡\"'«“"))
    if opening < len(rest) and rest[opening].islower():
        rest = rest[:opening] + rest[opening].upper() + rest[opening + 1:]
    return rest if rest.endswith((".", "!", "?", "…")) else rest + "."


# The vetoes a clause of a draft earns by itself, which ``_draft_clauses`` repair instead of a new draft. A listing,
# a missing fact or a wrong act is the draft's whole and is written again.
_CLAUSE_REPAIRABLE_DEFECTS = frozenset({
    "search_report_shows_the_search", "search_report_unsourced_claim", "search_report_names_a_page",
    "search_report_page_voice", "search_report_offers_a_finder", "search_report_pasted_urls", "wrong_language",
})


_SEARCH_RESULTS_TAIL = re.compile(
    # M77 (DEV-D v3l D-s063 «…in the provided results.», D-s012 «…en los resultados disponibles.»): the results
    # qualified as the ones given are the same closing phrase.
    # M105 (DEV-D v4a D-p23-t2 «…mentioned in the provided text.»): the text given, and what it «mentions», too.
    r"(?:\s+(?:mentioned|listed|named|mencionad[oa]s?|listad[oa]s?|nombrad[oa]s?))?"
    r"\s*,?\s+(?:in|from|among|within|en|entre|de)\s+(?:the|these|my|this|los|estos|mis|las|estas|el|este)\s+"
    r"(?:(?:provided|returned|available|given|retrieved)\s+)?(?:search\s+)?(?:results|resultados|fuentes|p[aá]ginas|"
    r"pages|sources|texts?|textos?)(?:\s+(?:disponibles?|proporcionad[oa]s?|obtenid[oa]s?|encontrad[oa]s?|dad[oa]s?))?"
    r"(?:\s+de\s+(?:la\s+)?b[uú]squeda)?"
    r"(?:\s+(?:that\s+i\s+found|que\s+encontr[eé]))?(?=\s*[.!]?\s*$)",
    re.IGNORECASE,
)


# M81 (DEV-D v3m D-p31-t1 «No encontré en los resultados una lista de los últimos 10 presidentes…», D-p34-t1 «No
# encontré en los resultados nombres específicos de cápsulas…»): the same closing phrase said right after the
# not-found verb; clipped, the not-found report is whole.
_SEARCH_RESULTS_AFTER_NOT_FOUND = re.compile(
    r"\b(no\s+(?:lo\s+|la\s+)?(?:encontr[eé]|hall[eé])|i\s+(?:couldn'?t|could\s+not|didn'?t|did\s+not)\s+find)\s+"
    r"(?:en|in|entre|among)\s+(?:los|las|estos|estas|mis|the|these|my)\s+(?:(?:provided|available)\s+)?"
    r"(?:search\s+)?(?:resultados|results|p[aá]ginas|pages|fuentes|sources)"
    r"(?:\s+(?:disponibles|proporcionad[oa]s|de\s+(?:la\s+)?b[uú]squeda))?\s+",
    re.IGNORECASE,
)


# M60 (DEV-D p16-t1 v3c, web_search_unavailable): the cause asks to offer opening it in the person's browser, and
# «I can open the search page in your web browser» / «open the search in your web browser?» is that offer, a search
# the person would run, not BAXY's lookup shown. Folded text.
_BROWSER_SEARCH_OFFER = re.compile(
    r"\b(open|abrir|abro|abra|abrirte|abrirla|abrirlo)\s+(?:the|a|that|la|una|esa)\s+(?:search|busqueda)"
    r"(?:\s+(?:page|pagina))?(?=\s+(?:for\s+you\s+)?(?:in|on|en)\s+(?:your|the|tu|su|el)\s+(?:web\s+)?"
    r"(?:browser|navegador))"
)


# FINAL v1 F-p08-t2 «You can find theatre, dance, and stage shows in Cape Town through sites like What's on in Cape
# Town and Cape Tourism» (reviewed right): sites offered as sites, where to look, are not counted among what was found.
_OFFERED_AS_SITES = re.compile(r"\b(?:sites?|websites?|sitios?(?:\s+web)?|paginas?(?:\s+web)?|apps?)\s+(?:like|such\s+as|como)\b")


def _search_result_site_brands(payload: dict) -> set[str]:
    """M102: the names of the sites the results belong to (folded): the last part of a result's title («… | Fandango»,
    «… - Southern Cravings») when it is its host's name («fandango.com», «southerncravings.com»)."""

    brands: set[str] = set()
    for item in _search_results_of(payload):
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        labels = [label for label in (urlparse(item["url"].strip()).hostname or "").casefold().split(".") if label]
        if len(labels) < 2:
            continue
        # «fandango.com» → fandango; «elpais.com.uy», «bbc.co.uk» → elpais, bbc.
        label = labels[-3] if len(labels) >= 3 and len(labels[-2]) <= 3 and len(labels[-1]) == 2 else labels[-2]
        parts = re.split(r"\s+[|\-–—:]\s+", str(item.get("title") or "").strip())
        if len(parts) < 2:
            continue
        brand = _reading_fold(parts[-1]).strip(" .")
        if len(label) < 4 or re.sub(r"[^a-z0-9]", "", brand) != label:
            continue
        # «Model Y | Tesla»: a name the title also gives as its subject, or that another site's result carries, is
        # what the pages are about, not only where they were read.
        elsewhere = " ".join(parts[:-1]) + " " + " ".join(
            f"{other.get('title') or ''} {other.get('snippet') or ''}"
            for other in _search_results_of(payload)
            if isinstance(other, dict) and isinstance(other.get("url"), str)
            and label not in (urlparse(other["url"].strip()).hostname or "").casefold()
        )
        if re.search(r"\b" + re.escape(brand) + r"\b", _reading_fold(elsewhere)) is None:
            brands.add(brand)
    return brands


def _search_report_shows_the_search(text: str, payload: dict, user_text: str) -> bool:
    """The answer to a verified search tells the search: a source cited, a result's site named, or how it was
    found. The person's own words and a snippet's own words are not the search showing."""

    results_text = _search_results_text(payload)
    folded = _reading_fold(re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(text)))
    folded = _BROWSER_SEARCH_OFFER.sub(r"\1 it", folded)
    reason = payload.get("reason")
    if results_text is None:
        # Tanda 7 «quién ganó el game de los Lakers anoche» → «…debido a que los resultados de búsqueda son
        # irrelevantes»: a lookup that answered nothing is told as not found, never as a search that failed.
        return (
            isinstance(reason, dict)
            and reason.get("operation") == "web.search"
            and (
                any(
                    pattern.search(folded) is not None
                    for pattern in (_SEARCH_MECHANICS, _SEARCH_ATTRIBUTION, _SEARCH_NARRATED_ABSENCE)
                )
                or bool(semantic_answer_evidence.results_narrated(folded, user_text or ""))
            )
        )
    grounds = _reading_fold(f"{user_text or ''}\n" + "\n".join(
        str(item.get(key) or "") for item in _search_results_of(payload) if isinstance(item, dict)
        for key in ("title", "snippet")
    ))
    # M81 (DEV-D v3m D-p34-t3): where the person could find something is answered by naming the site or page that
    # holds it; that is the answer, not the lookup shown. How BAXY searched stays invisible.
    where_asked = asks_where_to_find(user_text)
    named_source = (
        _reading_fold(found.group(0))
        for found in _SEARCH_NAMED_SOURCE.finditer(re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(text)))
    )
    if not where_asked and not _OFFERED_AS_SITES.search(folded) and any(
        re.search(r"\b" + re.escape(brand) + r"\b", folded) is not None
        and re.search(r"\b" + re.escape(brand) + r"\b", _reading_fold(user_text or "")) is None
        for brand in _search_result_site_brands(payload)
    ):
        # M102 (DEV-D v3z D-p26-t2 «Santa Rosa Cinemas, Roxy Stadium 14, Airport Stadium 12, and Fandango are the places
        # …»): «Movie Showtimes and Theaters near Santa Rosa, CA | Fandango» is Fandango's page; the site a result
        # belongs to is where it was read, never one of the things found.
        return True
    for found in (
        *(match.group(0) for match in _SEARCH_ATTRIBUTION.finditer(folded) if not where_asked),
        *(match.group(0) for match in _SEARCH_MECHANICS.finditer(folded)),
        # Ronda 24 (r23 t1-c03#2 «Lo único que afirma los resultados es que…»): the results as the subject that says.
        *semantic_answer_evidence.results_narrated(folded, user_text or ""),
        *(match.group(0) for match in _SEARCH_NARRATED_ABSENCE.finditer(folded)),
        *(() if where_asked else named_source),
    ):
        # A snippet that itself says «según la OMS» may be repeated with its words.
        if found not in grounds:
            return True
    if where_asked:
        return False
    for host in _search_result_hosts(payload, limit=len(_search_results_of(payload))):
        if host in folded:
            return True
        for label in host.split("."):
            # «tripadvisor»: a site said by its name. A label the person or the pages use as a word
            # («curico» of curico.cl in a snippet about Curicó) is that word, not the site.
            word = r"\b" + re.escape(label) + r"\b"
            if (
                len(label) >= 5
                and re.search(word, folded) is not None
                and re.search(word, grounds) is None
            ):
                return True
    return False


def _search_report_names_a_page(text: str, payload: dict, user_text: str) -> bool:
    """The whole answer is a result's title, or the heading its snippet opens with before a colon.

    Uso real tanda 5e «dónde está el restaurante italiano mas cercano» → «Los mejores restaurantes italianos en
    Curico, región de Curicó.»: the snippet «Los mejores restaurantes italianos en Curico, Región de
    Curicó: Consulta en Tripadvisor opiniones…» named a listing page and no restaurant, and its heading was
    published as the answer. A page's name states nothing the person asked."""

    if _search_results_text(payload) is None:
        return False
    said = re.findall(r"[a-z0-9]+", _reading_fold(text))
    if len(said) < 3:
        return False
    for item in _search_results_of(payload):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        headed = re.split(r"\s*:\s+", str(item.get("snippet") or ""), maxsplit=1)
        headings = (title, *re.split(r"\s+[-|–—]\s+|\s*:\s+", title), *(headed[:1] if len(headed) == 2 else ()))
        if any(re.findall(r"[a-z0-9]+", _reading_fold(heading)) == said for heading in headings):
            return True
    return False


def _search_report_repeats_a_quote(text: str, payload: dict) -> bool:
    """M81 (DEV-D v3m D-p27-t3 «What movies are there with Eugene Dynarski?» → «…two movies directed by Steven
    Spielberg: "Eugene Dynarski" (the title itself implies the film), "Eugene Dynarski" (…), and "Eugene
    Dynarski" (…)»): a report of a verified search that quotes the same thing twice lists nothing it read; the
    titles the page gave («El diablo sobre ruedas», «Encuentros en la tercera fase») were replaced by the name asked."""

    if _search_results_text(payload) is None:
        return False
    quoted = [_reading_fold(found).strip() for found in re.findall(r"[«\"“]([^»\"”]{1,200})[»\"”]", str(text))]
    quoted = [item for item in quoted if item]
    return len(quoted) != len(set(quoted))


def _search_report_off_subject(text: str, payload: dict, user_text: str) -> bool:
    """The search did not answer and the report says something anyway.

    Tanda 7 «¿y quién fue el top scorer?» after the Lakers game was reported as «Raphinha fue el top scorer con 12
    goles en la LaLiga»: the question names its subject («Lakers») and no result mentions it, so none answers it.
    Then only «no lo encontré» may be said, never a fact of another subject. A subject is a name the question
    writes with a capital after its first word; a question without one is not judged here.
    """

    results_text = _search_results_text(payload)
    if results_text is None:
        return False
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if seen.get("authority") == "openstreetmap_nominatim":
        # M58 (v3d-final F-p05-t1 «Encuentra aparcamiento en Plaza del Polvorista» ended with no answer): the places
        # OpenStreetMap returns lie around the named place by construction, and their addresses do not repeat its
        # name. Only a town the query names them to be in judges them (M56).
        if _places_inside_named_place(payload):
            return False
    else:
        names = question_names(str(user_text or "")) - {
            "google", "bing", "duckduckgo", "internet", "web", "wikipedia", "youtube",  # where to look, not what
        }
        if not names:
            return False
        found = _reading_fold(results_text)
        if any(re.search(r"\b" + re.escape(name) + r"\b", found) for name in names):
            return False
    return any(
        _SEARCH_NOT_FOUND.match(_reading_fold(sentence)) is None
        for sentence in re.split(r"(?<=[.!?])\s+", str(text).strip())
        if sentence.strip()
    )


# M51 (review of the official-window run v3a-final, 2026-09-28): «el artículo más leído es Cómo hablar de los libros que
# no se han leído», «no hay números ganadores del loto porque Baloto…»: the reply took a fact from a result that is not
# about what was searched. A result is about the query by the same rule the providers gate Wikipedia and the news feed
# with (src/Baxy.Providers.Windows/External/SearchPertinence.cs): the query's proper names are all in its title or
# snippet, or without names one of its content words is in the title; and the title and snippet repeat its content
# words (both when there are one or two, a strict majority when more). A general engine's result is judged as that
# engine's own gate judges it (half of the words, no title needed). The structured sources (a place read from
# OpenStreetMap, a reference exchange rate) answer by construction and are not judged here.
_SEARCH_QUERY_FRAME_WORDS = frozenset(
    {
        # IsSearchStopWord (WebBrowserAdapter.cs)
        "a", "an", "and", "the", "to", "for", "from", "in", "of", "on", "search", "find", "de", "del", "el", "en",
        "la", "las", "los", "para", "por", "un", "una", "y", "busca", "buscar", "hoy", "today", "ahora", "now",
        "todays", "que", "porque", "como", "cual", "cuales", "cuando", "donde", "quien", "quienes", "es", "son",
        "esta", "estan", "hay", "se", "me", "mi", "mis", "tu", "su", "sus", "lo", "le", "les", "al", "con", "sin",
        "sobre", "si", "no", "ya", "muy", "mas", "why", "how", "what", "which", "when", "where", "who", "whom", "is",
        "are", "was", "were", "do", "does", "did", "can", "could", "should", "would", "will", "it", "its", "my",
        "your", "this", "that", "with", "without", "about", "at", "by", "or", "not", "so", "very", "more", "please",
        # SearchPertinence.FrameWords
        "show", "tell", "give", "get", "got", "look", "lookup", "list", "us", "something", "anything", "any",
        "some", "there", "new", "info", "information", "want", "need", "know", "like", "let", "only", "just", "also",
        "much", "many", "have", "has", "had", "wrote", "written", "write", "writes", "invented", "discovered",
        "founded", "directed", "painted", "composed", "won", "played", "starred", "starring", "muestra",
        "muestrame", "mostrar", "ensename", "dime", "decime", "dame", "pasame", "pasa", "encuentra", "encuentrame",
        "encontrar", "buscame", "buscarme", "informacion", "algo", "alguna", "alguno", "algun", "quiero", "quisiera",
        "necesito", "saber", "puedes", "podrias", "puede", "solo", "solamente", "tambien", "cuanto", "cuanta",
        "cuantos", "cuantas", "tiene", "tienen", "tener", "sale", "vale", "valen", "cuesta", "cuestan", "escribio",
        "escribe", "escrito", "invento", "descubrio", "fundo", "dirigio", "pinto", "compuso", "gano", "ganaron",
        "internet", "web", "google", "bing", "duckduckgo", "wikipedia", "online", "net", "latest", "news", "recent",
        "noticia", "noticias", "ultima", "ultimas", "ultimo", "ultimos", "actualidad", "precio", "precios", "price",
        "prices", "cost", "costs", "cotizacion",
        # M77 (DEV-D v3l D-w10-t2 «¿Y cuánto sería eso de harina en gramos, por favor?»): the person's whole sentence
        # reached the general engine; its courtesy and its pointing back («eso», «sería», «por favor») ask nothing.
        "eso", "esto", "seria", "serian", "favor", "porfa", "please", "gracias", "thanks",
        # M81 (DEV-D v3m D-p34-t3 «¿Cómo podría encontrar un listado…?»): the modal of the question asks nothing.
        "podria", "podrias", "podriamos", "puedo", "podemos", "pudiera", "might", "may",
    }
)
_SEARCH_TERM_SYNONYMS = (
    frozenset({"clima", "tiempo", "weather", "meteo", "meteorologico", "meteorologica", "pronostico", "forecast"}),
    frozenset({"lluvia", "lluvias", "llueve", "llover", "llovera", "rain", "raining"}),
    frozenset({"manana", "tomorrow"}),
    frozenset({"temperatura", "temperature", "temperaturas", "temperatures"}),
    frozenset({"movie", "movies", "film", "films", "pelicula", "peliculas", "filme"}),
    # M95 (DEV-D v3x D-w01-t2 «cuánta sal le echo al agua … para los tallarines» → «No encontré una cifra exacta.» over
    # «La regla del 1, 100 y 10: cuánta sal hay que echarle a la [pasta]»): tallarines are pasta.
    frozenset({"pasta", "pastas", "tallarines", "tallarin", "fideos", "espaguetis", "spaghetti", "macarrones",
               "noodles"}),
)
# M168: a match read from ESPN's calendar answers by construction too.
_SEARCH_STRUCTURED_AUTHORITIES = frozenset({"openstreetmap_nominatim", "frankfurter_reference_rates", _MATCH_AUTHORITY})


def _search_query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for word in re.findall(r"[a-z0-9]+", _reading_fold(query)):
        if len(word) >= 2 and word not in _SEARCH_QUERY_FRAME_WORDS and word not in terms:
            terms.append(word)
    return terms


def _search_query_names(query: str) -> list[str]:
    names: list[str] = []
    opening = True
    for raw in str(query).split():
        word = raw.lstrip("¿¡\"'«(“")
        if word and not opening and word[0].isupper():
            for token in _search_query_terms(word):
                if token not in names:
                    names.append(token)
        if word:
            opening = word[-1] in ".?!:"
    return names


def _search_term_found(term: str, observed: set[str]) -> bool:
    if term in observed or any(term in family and family & observed for family in _SEARCH_TERM_SYNONYMS):
        return True
    stem = term[:-2]
    return len(term) >= 5 and len(stem) >= 4 and any(len(word) >= 4 and word.startswith(stem) for word in observed)


def _search_result_is_about(query: str, item: dict, titled: bool, dropped: frozenset[str] = frozenset()) -> bool:
    """«titled»: the source's pages are about their title (an encyclopedia article, a headline). A general engine's
    page title is often the site's own, so there the snippet may carry the query's words instead, and half of them
    is enough. «dropped»: names of the query that no result carries and the report does not say, left out."""

    terms = [term for term in _search_query_terms(query) if term not in dropped]
    if not terms:
        return False
    title = set(re.findall(r"[a-z0-9]+", _reading_fold(str(item.get("title") or ""))))
    observed = title | set(re.findall(r"[a-z0-9]+", _reading_fold(str(item.get("snippet") or ""))))
    names = [name for name in _search_query_names(query) if name not in dropped]
    if names:
        if not all(_search_term_found(name, observed) for name in names):
            return False
        # M54 (v3b-final F-p08-t2 «stage shows in Cape Town» → the article «Cape Town Stadium»): an article whose title
        # names something narrower than the place asked about (a word that is neither a name nor a word of the query)
        # is about that thing; it answers only if its title carries one of the other words asked.
        others = [term for term in terms if term not in names]
        narrower = [
            word for word in title
            if len(word) >= 4 and not word.isdigit() and word not in _SEARCH_QUERY_FRAME_WORDS
            and not any(_search_term_found(term, {word}) for term in terms)
        ]
        # M77 (DEV-D v3l D-p24-t2 «Drama movies like Lizzo» → the article «Estafadoras de Wall Street», whose extract
        # says «película de drama … protagonizada por … Lizzo»): an article narrower than a name is one whose title
        # carries that name. One whose title does not is about another thing the extract ties to the name, and it
        # answers when the extract carries the other words asked.
        title_names = any(_search_term_found(name, title) for name in names)
        if titled and title_names and others and narrower and not any(
            _search_term_found(term, title) for term in others
        ):
            return False
        # «a nice fantasy movie like Elijah Wood» is not answered by «Pawn Shop Chronicles», whose extract names Elijah
        # Wood and a film but no fantasy: most of the other words asked are the extract's.
        if titled and not title_names and others and sum(
            1 for term in others if _search_term_found(term, observed)
        ) < len(others) // 2 + 1:
            return False
    elif titled and not any(_search_term_found(term, title) for term in terms):
        return False
    matched = sum(1 for term in terms if _search_term_found(term, observed))
    if not titled:
        # The general engine's own gate: half of the words, rounded up («cómo llego a parquelandia» is answered by
        # «Cómo llegar a Parquelandia Resort»). M77 (DEV-D v3l D-p34-t1, D-p31-t1): the engine was given the
        # person's whole long request («Elabora una lista con las cápsulas del tiempo más famosas de la historia,
        # especificando las fechas…», eighteen words), and no page repeats half of a request's wording; four of its
        # words («cápsulas», «tiempo», «famosas», «historia») are what a page about it shares.
        return matched >= min((len(terms) + 1) // 2, 4)
    return matched >= (len(terms) if len(terms) <= 2 else len(terms) // 2 + 1)


def _search_query_unseen_names(query: str, results: list) -> frozenset[str]:
    """The names of the query (folded) that no result carries, when at least one other name is carried."""

    names = _search_query_names(query)
    observed = [
        set(re.findall(r"[a-z0-9]+", _reading_fold(f"{item.get('title') or ''} {item.get('snippet') or ''}")))
        for item in results
        if isinstance(item, dict)
    ]
    unseen = frozenset(name for name in names if not any(_search_term_found(name, words) for words in observed))
    return unseen if len(unseen) < len(names) else frozenset()


def _search_report_says_unseen_name(text: str, payload: dict, user_text: str) -> list[str]:
    """The query's names, as the query writes them, that no result carries and the report says (the retry is told to
    leave them out, not to give up: v3b-final F-w13-t2 «…cuesta $82.360 en Córdoba» over the country's price)."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    query = seen.get("query") if isinstance(seen.get("query"), str) and seen.get("query").strip() else user_text
    unseen = _search_query_unseen_names(str(query or ""), _search_results_of(payload))
    said = set(re.findall(r"[a-z0-9]+", _reading_fold(text)))
    spelled: list[str] = []
    for raw in str(query or "").split():
        word = raw.strip("¿¡?!.,;:\"'«»()“”")
        folded = _reading_fold(word)
        if folded in unseen and _search_term_found(folded, said) and word not in spelled:
            spelled.append(word)
    return spelled


def _search_result_is_a_namesake(item: dict, user_text: str) -> bool:
    """M83 (DEV-D v3o D-p29-t2 «Search for scary movies.» → the articles «Scary Movie», «Scary Movie 3»…, parodies): an
    encyclopedia article whose title is a proper name (each word capitalized) made of the very words the person wrote in
    lower case as a kind of thing, one of them in the plural the title has in the singular («movies» → «Movie»), is a
    work named like that kind, not one of the kind asked for."""

    title = re.sub(r"\([^)]*\)", " ", str(item.get("title") or ""))
    words = [word for word in re.findall(r"[^\W\d_]+", title) if len(word) >= 4]
    if not words or not all(word[0].isupper() for word in words):
        return False
    common = request_common_words(user_text or "")
    folded = [_reading_fold(word) for word in words]
    plural = [word for word in folded if word not in common and (word + "s" in common or word + "es" in common)]
    return bool(plural) and all(word in common or word + "s" in common or word + "es" in common for word in folded)


def _search_report_from_no_pertinent_result(text: str, payload: dict, user_text: str) -> bool:
    """The search answered with results none of which is about the query, and the report states something anyway."""

    if _search_results_text(payload) is None:
        return False
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if seen.get("authority") == "openstreetmap_nominatim" and not _places_inside_named_place(payload):
        # M56 (v3c-final F-p06-t2): places outside the city the person named answer nothing about it.
        return any(
            _SEARCH_NOT_FOUND.match(_reading_fold(sentence)) is None
            for sentence in re.split(r"(?<=[.!?])\s+", str(text).strip())
            if sentence.strip()
        )
    if seen.get("authority") in _SEARCH_STRUCTURED_AUTHORITIES:
        return False
    query = seen.get("query") if isinstance(seen.get("query"), str) and seen.get("query").strip() else user_text
    near = seen.get("near") if isinstance(seen.get("near"), str) else ""
    if near and str(query).endswith(" " + near):
        query = str(query)[: -len(near) - 1]
    elif near and " " + near + " " in str(query) and len(str(query).rsplit(" " + near + " ", 1)[1].split()) <= 3:
        # M81: the provider also adds this PC's country after the city («… Curico Chile»).
        query = str(query).rsplit(" " + near + " ", 1)[0]
    if not _search_query_terms(str(query or "")):
        return False
    results = [item for item in _search_results_of(payload) if isinstance(item, dict)]
    authority = str(seen.get("authority") or "")
    titled = authority.startswith("wikipedia_") or authority == "google_news_rss_search"
    # M54 (v3b-final F-w13-t2 «¿Cuánto me sale cargar 40 litros de nafta Super en Córdoba?»): the pages gave the
    # country's price for 40 litres and none named Córdoba, and every draft that said the price died, «Córdoba» or not.
    # A name of the query that no result carries is left out of the judgment when the report does not say it (then it
    # claims nothing about it) and another name still binds the results to the query.
    unseen = _search_query_unseen_names(str(query), results)
    said = set(re.findall(r"[a-z0-9]+", _reading_fold(text)))
    dropped = unseen if not any(_search_term_found(name, said) for name in unseen) else frozenset()
    if any(
        _search_result_is_about(str(query), item, titled, dropped)
        and not (titled and _search_result_is_a_namesake(item, user_text))
        for item in results
    ):
        return False
    return any(
        _SEARCH_NOT_FOUND.match(_reading_fold(sentence)) is None
        for sentence in re.split(r"(?<=[.!?])\s+", str(text).strip())
        if sentence.strip()
    )


def _places_whole_address(text: str, payload: dict, user_text: str = "") -> bool:
    """M62 (v3e2-final F-p05-t1 «Encontré aparcamiento en Calle Aurora, Valdelagrana, El Puerto de Santa María, Bahía
    de Cádiz, Cádiz, Andalucía, 11500, España y …»): a place OpenStreetMap read is said by its name or street, not by
    its whole address. Two consecutive parts of the tail of an address (province, region, postcode, country: «Cádiz,
    Andalucía», «11500, España») said together, and not said so by the person, are the whole address copied; a street
    that carries a country's name («Avenida de España») is not."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if seen.get("authority") != "openstreetmap_nominatim":
        return False
    said = _reading_fold(text)
    asked = _reading_fold(user_text or "")
    for item in _search_results_of(payload):
        if not isinstance(item, dict):
            continue
        parts = [_reading_fold(part.strip()) for part in str(item.get("snippet") or "").split(",") if part.strip()]
        tail = parts[-4:] if len(parts) >= 5 else []
        for first, second in zip(tail, tail[1:]):
            joined = r"(?<!\w)" + re.escape(first) + r"\s*,\s*" + re.escape(second) + r"(?!\w)"
            if re.search(joined, said) and not re.search(joined, asked):
                return True
    return False


def _places_unread_qualifiers(payload: dict, user_text: str) -> list[str]:
    """M77: the words the person wrote in lower case about the places asked («valet» of «valet parking») that are
    not the class OpenStreetMap read and that no place read carries, in the person's order."""

    carried = set(re.findall(r"[a-z0-9]+", _reading_fold(_search_results_text(payload) or "")))
    return sorted(
        (
            word for word in request_common_words(user_text)
            if word not in PLACE_KIND_WORDS and word not in _SEARCH_QUERY_FRAME_WORDS
            and word not in _SEARCH_REPORT_GRAMMAR_WORDS and not _search_term_found(word, carried)
        ),
        key=lambda word: _reading_fold(user_text).find(word),
    )


def _search_report_denies_found_places(text: str, payload: dict, user_text: str = "") -> bool:
    """M54 (v3b-final F-p06-t3 «Mejor en calle Génova» → «No encontré aparcamiento en la calle Génova en Madrid» over
    five car parks of Chueca, the next streets): the places OpenStreetMap returns are of the asked kind inside the asked
    place by construction, so they cannot be reported as not found nor as absent.

    M77 (DEV-D v3l D-p16-t1/t2 «valet parking at the Kenzi Rose Garden»): OpenStreetMap read the class («parking»),
    not what the person qualified it with; «I could not find valet parking at …» over public car parks says what was
    not read. A not-found that names a word the person wrote in lower case, which is not the class read and no place
    carries, is that honest not-found. Saying it does not exist stays denied."""

    if _search_results_text(payload) is None:
        return False
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if seen.get("authority") != "openstreetmap_nominatim" or not _places_inside_named_place(payload):
        # M56: places outside the city the person named are not the asked place; «no lo encontré» fits them.
        return False
    qualifiers = set(_places_unread_qualifiers(payload, user_text))

    def qualified_not_found(folded: str) -> bool:
        return _SEARCH_NOT_FOUND.match(folded) is not None and bool(qualifiers & set(re.findall(r"[a-z0-9]+", folded)))

    return any(
        (_SEARCH_NOT_FOUND.match(folded) is not None or _SEARCH_ABSENCE_CLAIM.search(folded) is not None)
        and not qualified_not_found(folded)
        for folded in (_reading_fold(sentence) for sentence in re.split(r"(?<=[.!?;])\s+", str(text).strip()))
    )


# M51 v3a-final F-p05-t1 «Encuentra aparcamiento en Plaza del Polvorista» → «Hay aparcamiento subterráneo en la Plaza del
# Polvorista»: the only result that named an underground car park said a party «plantea» one. What a result proposes or
# plans is not there yet; the report may say it is proposed, never that it exists.
_SEARCH_EXISTENCE_CLAIM = re.compile(
    r"\b(?:hay|existen?|cuenta\s+con|dispone\s+de|there\s+(?:is|are)|has|have)\s+(?:(?:un|una|unos|unas|el|la|los|las|"
    r"a|an|the|some)\s+)?(?P<thing>[a-z]{4,}(?:\s+[a-z]{4,})?)"
)
_SEARCH_PROPOSAL_WORDS = frozenset(
    {
        "plantea", "plantean", "propone", "proponen", "propuesta", "propuestas", "proyecto", "proyecta", "proyectan",
        "proyectado", "proyectada", "planea", "planean", "contara", "contaran", "construira", "construiran", "futuro",
        "futura", "proposes", "proposed", "proposal", "planned", "plans",
    }
)


def _search_report_proposal_as_fact(text: str, payload: dict, user_text: str) -> bool:
    """The report says a thing exists that the only results naming it propose or plan."""

    if _search_results_text(payload) is None:
        return False
    results = [
        set(re.findall(r"[a-z0-9]+", _reading_fold(f"{item.get('title') or ''} {item.get('snippet') or ''}")))
        for item in _search_results_of(payload)
        if isinstance(item, dict)
    ]
    for sentence in re.split(r"(?<=[.!?])\s+", str(text).strip()):
        folded = _reading_fold(sentence)
        if _SEARCH_NOT_FOUND.match(folded) is not None or re.search(r"\b(?:propuest|propon|plante|plan|propos)", folded):
            continue
        for claim in _SEARCH_EXISTENCE_CLAIM.finditer(folded):
            thing = [word for word in claim.group("thing").split() if word not in _SEARCH_QUERY_FRAME_WORDS]
            naming = [words for words in results if thing and all(_search_term_found(word, words) for word in thing)]
            if naming and all(words & _SEARCH_PROPOSAL_WORDS for words in naming):
                return True
    return False


# M54 (review of v3b-final): «No hay taquerías específicas con servicio a domicilio» over five directory pages, «No hay
# aparcamiento para motocicletas en el centro» over a list of car parks: that a thing does not exist is a fact of the
# world only a page can state. What the pages do not carry was not found. Folded.
_SEARCH_ABSENCE_CLAIM = re.compile(
    r"\bno\s+(?:hay|habra|habia|existen?|existira|tienen?|cuentan?\s+con|ofrecen?|disponen?\s+de|venden?)\b|"
    r"\bno\s+se\s+(?:venden?|ofrecen?)\b|\bningun[oa]?\s+[a-z]+\s+(?:tiene|ofrece|cuenta)\b|"
    r"\bthere\s+(?:is|are|was|were|will\s+be)\s+no\b|\bthere\s+(?:isn'?t|aren'?t|won'?t\s+be)\b|"
    r"\b(?:doesn'?t|does\s+not|don'?t|do\s+not)\s+(?:have|offer|exist)\b|\bnone\s+(?:of\s+them\s+)?(?:is|are|has|have)\b|"
    # M77 (DEV-D v3l D-p16-t3 «No valet parking is available at the Kenzi Rose Garden» over public car parks): that a
    # thing is not available or not offered is the same verdict of the world.
    r"\bno\s+[a-z]+(?:\s+[a-z]+){0,2}\s+(?:is|are|was|were)\s+(?:available|offered|provided)\b|"
    r"\b(?:is|are|was|were)\s+not\s+(?:available|offered|provided)\b|\b(?:isn'?t|aren'?t|wasn'?t|weren'?t)\s+"
    r"(?:available|offered|provided)\b|\bno\s+(?:esta|estan|estaba|estaban)\s+disponibles?\b|"
    r"\bno\s+(?:se\s+)?(?:ofrece|ofrecen|dispone|disponen|presta|prestan)\b"
)
_SEARCH_RESULT_NEGATION = r"(?:\b(?:no|not|sin|ningun[oa]?|none|never|nunca|without|nadie|nothing|nada)\b|n't\b)"


def _search_report_absence_claim(text: str, payload: dict, user_text: str = "") -> bool:
    """A sentence of the report says a thing does not exist or is not offered, and no result denies one of its words
    (a negation at most three words before it: «sin servicio a domicilio», «no hay aparcamiento»)."""

    if _search_results_text(payload) is None:
        return False
    results = [
        _reading_fold(f"{item.get('title') or ''} {item.get('snippet') or ''}")
        for item in _search_results_of(payload)
        if isinstance(item, dict)
    ]
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    asked = asked_dimension_words(f"{user_text or ''}\n{seen.get('query') or ''}")
    for sentence in re.split(r"(?<=[.!?;])\s+", str(text).strip()):
        folded = _reading_fold(sentence)
        if _SEARCH_NOT_FOUND.match(folded) is not None or _SEARCH_ABSENCE_CLAIM.search(folded) is None:
            continue
        if any(asked & set(folded[claim.end():].split()[:3]) for claim in _SEARCH_ABSENCE_CLAIM.finditer(folded)):
            # M70 (held-out v3h t16 «¿Cuándo sale la próxima temporada…?» → «No hay fecha de estreno confirmada…»):
            # the absent thing is the date, place or amount asked; that is what was not found, not a fact of the world.
            continue
        words = {
            word for word in re.findall(r"[a-z]{5,}", folded)
            if word not in _SEARCH_QUERY_FRAME_WORDS and word not in _SEARCH_REPORT_GRAMMAR_WORDS
        }
        if not any(
            re.search(_SEARCH_RESULT_NEGATION + r"(?:\W+[\w']+){0,3}?\W+" + re.escape(word[:5]), result) is not None
            for result in results
            for word in words
        ):
            return True
    return False


# M77 (DEV-D v3l D-p05-t2 «Necesito aparcamiento para mañana» → «El aparcamiento junto a la estación de ferrocarril
# abrirá mañana con más de 400 plazas»): the headline «… ABRIRÁ MAÑANA CON MÁS DE 400 PLAZAS» was published five days
# before, by the town hall of Aranjuez; its «mañana» was the day after that, not the person's. A day said relative to
# when a dated result was published (the news feed writes it: «Thu, 24 Sep 2026 12:12:35 GMT») belongs to that day.
_RELATIVE_DAY_WORDS = frozenset({"hoy", "manana", "ayer", "anoche", "today", "tomorrow", "yesterday", "tonight"})
_RESULT_PUBLISHED = re.compile(
    r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),\s+\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\s+"
    r"\d{2}:\d{2}:\d{2}\s+GMT\b"
)


def _result_published_day(item: dict) -> date | None:
    """The local day a dated result (a news item) was published; None when it carries no date."""

    for key in ("publishedAt", "snippet"):
        found = _RESULT_PUBLISHED.search(str(item.get(key) or ""))
        if found is None:
            continue
        try:
            return parsedate_to_datetime(found.group(0)).astimezone().date()
        except (TypeError, ValueError):
            return None
    return None


def _search_report_stale_day(text: str, payload: dict) -> tuple[str, date] | None:
    """The relative day a report sentence takes from a result published on another day (the word and that day)."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    items = [
        item for item in [*_search_results_of(payload), *(seen.get("headlines") or [])] if isinstance(item, dict)
    ]
    today = _report_today()
    if not any((day := _result_published_day(item)) is not None and day != today for item in items):
        return None
    for sentence in re.split(r"(?<=[.!?;])\s+", str(text).strip()):
        folded = _reading_fold(sentence)
        if _SEARCH_NOT_FOUND.match(folded) is not None:
            continue
        words = set(re.findall(r"[a-z0-9]+", folded))
        if not words & _RELATIVE_DAY_WORDS:
            continue
        # The result the sentence says: the one whose title shares most of its words.
        best: tuple[int, dict] | None = None
        for item in items:
            title = set(re.findall(r"[a-z0-9]+", _reading_fold(f"{item.get('title') or ''}")))
            shared = len({word for word in words & title if len(word) >= 5 and word not in _RELATIVE_DAY_WORDS})
            if shared >= 2 and (best is None or shared > best[0]):
                best = (shared, item)
        if best is None:
            continue
        day = _result_published_day(best[1])
        said = words & _RELATIVE_DAY_WORDS & set(re.findall(r"[a-z0-9]+", _reading_fold(str(best[1].get("title") or ""))))
        if day is not None and day != today and said:
            return sorted(said)[0], day
    return None


# M93 (DEV-D v3u D-s027 «Concierto en 6th street mañana» → «Mañana hay un evento gratuito en 6th Street & Broadway…»
# over a Facebook post of Pittsburg, Kansas, «¡Dos eventos GRATIS mañana!», with no date): the «mañana» of a page that
# carries no date is the day after it was written, which nobody knows. Said as the person's tomorrow, it is a day the
# read does not give. A date written in the page that is that day, or a news item published today, gives it.
_UNDATED_RELATIVE_DAYS = {"manana": 1, "tomorrow": 1, "ayer": -1, "yesterday": -1, "anoche": -1}


def _search_report_undated_relative_day(text: str, payload: dict) -> str:
    """The relative day («mañana», «ayer») a report sentence takes from a result that says it without a date; ""."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    items = [
        item for item in [*_search_results_of(payload), *(seen.get("headlines") or [])] if isinstance(item, dict)
    ]
    today = _report_today()
    for sentence in re.split(r"(?<=[.!?;])\s+", str(text).strip()):
        folded = _reading_fold(sentence)
        if _SEARCH_NOT_FOUND.match(folded) is not None:
            continue
        # «de la mañana», «por la mañana» are a part of the day; a capitalised «Ayer» inside the sentence is a name
        # («directed by David Ayer», replay of v3m D-p27-t1).
        words = set(re.findall(r"[a-z0-9]+", re.sub(r"\bla\s+manana\b", " ", folded)))
        lowered = {
            _reading_fold(token) for index, token in enumerate(re.findall(r"[^\W\d_]+", sentence))
            if index == 0 or not token[:1].isupper()
        }
        relative = sorted(words & lowered & set(_UNDATED_RELATIVE_DAYS))
        if not relative:
            continue
        best: tuple[int, dict] | None = None
        for item in items:
            page = set(re.findall(r"[a-z0-9]+", _reading_fold(f"{item.get('title') or ''} {item.get('snippet') or ''}")))
            shared = len({word for word in words & page if len(word) >= 5 and word not in _RELATIVE_DAY_WORDS})
            if shared >= 2 and (best is None or shared > best[0]):
                best = (shared, item)
        if best is None:
            continue
        item = best[1]
        page_text = _reading_fold(f"{item.get('title') or ''} {item.get('snippet') or ''}")
        page_words = set(re.findall(r"[a-z0-9]+", re.sub(r"\bla\s+manana\b", " ", page_text)))
        for word in relative:
            if word not in page_words:
                continue
            if _result_published_day(item) == today:
                continue
            target = today + timedelta(days=_UNDATED_RELATIVE_DAYS[word])
            dated = False
            for pattern in _CALENDAR_DATE_PATTERNS:
                for match in pattern.finditer(page_text):
                    month = match["month"]
                    number = int(month) if month.isdigit() else _CALENDAR_MONTH_NUMBERS.get(month)
                    if number == target.month and int(match["day"]) == target.day and (
                        match["year"] is None or int(match["year"]) == target.year
                    ):
                        dated = True
            if not dated:
                return word
    return ""


# M93 (DEV-D v3u D-s021 «me gustaría saber qué está pasando por el mundo» → «Alemania, campeona del mundo, criticó a
# Jürgen Klopp…» over «Campeón del mundo con Alemania critica a Jürgen Klopp: …»): a headline retold with a name it
# writes after a preposition («con Alemania») as the one who acts turns who did it around. The sentence that opens
# with that name, retelling a headline that opens otherwise and keeps the name behind «con», «de», «en»…, is that.
_HEADLINE_PREPOSITIONS = frozenset(
    {"con", "de", "del", "en", "para", "por", "contra", "sin", "sobre", "ante", "with", "for", "of", "in", "against",
     "from", "about", "on", "at"}
)
_SENTENCE_LEAD = re.compile(r"^[\W\d_]*(?:(?:y|e|and|pero|but|ademas|also|el|la|los|las|the)\s+)*", re.IGNORECASE)


def _search_report_moves_the_subject(text: str, payload: dict) -> str:
    """The name a report sentence makes the subject of a headline that writes it as a complement; ""."""

    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if seen.get("authority") != "google_news_rss_search":
        return ""
    titles = [
        str(item.get("title") or "")
        for item in [*_search_results_of(payload), *(seen.get("headlines") or [])] if isinstance(item, dict)
    ]
    for sentence in re.split(r"(?<=[.!?;])\s+", re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(text)).strip()):
        body = sentence[_SENTENCE_LEAD.match(sentence).end():]
        head = re.match(r"([^\W\d_][\w'’-]*)", body)
        if head is None:
            continue
        name = head.group(1)
        key = _reading_fold(name)
        words = set(re.findall(r"[a-z0-9]+", _reading_fold(sentence)))
        for title in titles:
            tokens = re.findall(r"[^\W_][\w'’-]*", title)
            folded_tokens = [_reading_fold(token) for token in tokens]
            if key not in folded_tokens[1:] or folded_tokens[:1] == [key]:
                continue
            place = folded_tokens.index(key)
            if not tokens[place][:1].isupper() or folded_tokens[place - 1] not in _HEADLINE_PREPOSITIONS:
                continue
            shared = {word for word in words & set(folded_tokens) if len(word) >= 5 and word != key}
            if len(shared) >= 2:
                return name
    return ""


# M93 (DEV-D v3u D-w06-t4 «Bueno, dale, buscame las que estén abiertas cerca» → «Las pizzerías abiertas están cerca de
# Curico.» over five pages that named Giuseppe, Errázuriz 2970): a report whose every word is the request's, the
# query's or the place it was searched near says back what was asked and nothing of what was read. A yes-or-no question
# answered with its own words is an answer; a request to find something is not.
def _search_report_echoes_the_ask(text: str, payload: dict, user_text: str) -> bool:
    if _search_results_text(payload) is None or "?" in str(user_text or ""):
        return False
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    asked = words_asked(str(user_text or ""), str(seen.get("query") or ""), str(seen.get("near") or ""))
    sentences = [part for part in re.split(r"(?<=[.!?;])\s+", str(text).strip()) if part.strip()]
    if not sentences:
        return False
    for sentence in sentences:
        folded = _reading_fold(sentence)
        if _SEARCH_NOT_FOUND.match(folded) is not None or re.search(r"\d", sentence):
            return False
        content = [
            word for word in re.findall(r"[a-z0-9]+", folded)
            if len(word) >= 5 and word not in _SEARCH_REPORT_GRAMMAR_WORDS
        ]
        if not content or any(
            not any(word[:5] == said[:5] for said in asked if len(said) >= 4) for word in content
        ):
            return False
    return True


def _search_report_other_year(text: str, payload: dict, user_text: str) -> str:
    """M77 (DEV-D v3l D-w14-t1 «¿quién ha ganado la Vuelta este año?» → «Jonas Vingegaard conquistó la Vuelta a
    España 2025» in 2026): what a result states of another year does not answer a question about this one. The year
    a report sentence names when the request asks about the current year and the sentence does not name it."""

    if _search_results_text(payload) is None:
        return ""
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if not (asks_this_year(user_text or "") or asks_this_year(str(seen.get("query") or ""))):
        return ""
    current = str(_report_today().year)
    for sentence in re.split(r"(?<=[.!?;])\s+", str(text).strip()):
        if _SEARCH_NOT_FOUND.match(_reading_fold(sentence)) is not None:
            continue
        years = re.findall(r"(?<![\d.,])(?:19|20)\d{2}(?![\d.,]\d)", sentence)
        if years and current not in years:
            return years[0]
    return ""


# M83 (DEV-D v3o D-w08-t2 «y cuando juega el sigiente» on 30-09 → «América juega este 27 de septiembre de 2026 contra
# Necaxa…», read from a page written before that match): a date a report gives for what is still to come is compared
# with today. A day already gone is not the next one; a sentence that tells it as gone («ya se jugó», «el último fue»)
# says it truly. Folded report sentence.
_TOLD_AS_GONE = re.compile(
    r"\b(?:ya\s+(?:paso|se\s+jugo|fue|se\s+celebro)|pasad[oa]s?|ultim[oa]s?|anterior(?:es)?|fue|fueron|jugo|jugaron|"
    r"gano|ganaron|perdio|perdieron|empato|empataron|already|last|previous|was|were|played|won|lost|drew|ended)\b"
)


def _search_report_past_as_next(text: str, payload: dict, user_text: str) -> str:
    """The past day (ISO) a report sentence gives for an event the request asks about as still to come; ""."""

    if _search_results_text(payload) is None:
        return ""
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    if not (asks_upcoming(user_text or "") or asks_upcoming(str(seen.get("query") or ""))):
        return ""
    today = _report_today()
    for sentence in re.split(r"(?<=[.!?;])\s+", str(text).strip()):
        folded = _reading_fold(sentence)
        if _SEARCH_NOT_FOUND.match(folded) is not None or _TOLD_AS_GONE.search(folded) is not None:
            continue
        for pattern in _CALENDAR_DATE_PATTERNS:
            for match in pattern.finditer(folded):
                month = match["month"]
                month_number = int(month) if month.isdigit() else _CALENDAR_MONTH_NUMBERS.get(month)
                if month_number is None:
                    continue
                try:
                    day = date(int(match["year"]) if match["year"] else today.year, month_number, int(match["day"]))
                except ValueError:
                    continue
                if day < today:
                    return day.isoformat()
    return ""


# M77 (DEV-D v3l D-s021 «me gustaría saber qué está pasando por el mundo» → «El mundo ha perdido sus colores y la IA más
# potente está obsesionada con Mark Fisher…»): the headlines were «Por qué el mundo ha perdido sus colores: Los
# estudios…» and «Por qué la IA más potente del mundo está obsesionada con Mark Fisher…». A headline that asks why
# something is so is a piece about it; said without its «por qué», it becomes a fact the headline does not state.
_WHY_TITLE = re.compile(r"^\W*(?:por\s*que|why)\s+(?P<clause>[^:?|]+)")


def _search_report_why_title_as_fact(text: str, payload: dict) -> bool:
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    items = [
        item for item in [*_search_results_of(payload), *(seen.get("headlines") or [])] if isinstance(item, dict)
    ]
    unquoted = re.sub(r"[«\"“][^»\"”]{1,400}[»\"”]", " ", str(text))
    said = " " + " ".join(re.findall(r"[a-z0-9]+", _reading_fold(unquoted))) + " "
    for item in items:
        found = _WHY_TITLE.match(_reading_fold(str(item.get("title") or "")))
        if found is None:
            continue
        clause = re.findall(r"[a-z0-9]+", found.group("clause"))
        for start in range(len(clause) - 3):
            run = clause[start:start + 4]
            if (
                sum(1 for word in run if len(word) >= 4) >= 2
                and f" {' '.join(run)} " in said
                and not re.search(r"\b(?:por\s+que|why)\s+" + re.escape(clause[0]) + r"\b", said)
            ):
                return True
    return False


# M77 (DEV-D v3l D-p19-t3 «What's the genre?» → «Genre is any style or form of communication…», D-p23-t2 «Look for a
# drama film.» → «A drama film is a work set in a past period…», D-w17-t5 → «The second headline refers to the text
# indicating the content…»): the encyclopedia's article on the word itself was read and the reply defined the word.
_REPORT_DEFINES = re.compile(
    r"^\W*(?:(?:the|a|an|el|la|los|las|un|una)\s+)?(?P<term>[a-z]+(?:[\s-][a-z]+){0,2}?)\s+"
    r"(?:is|are|es|son|refers?\s+to|se\s+refiere\s+a|means|significa|se\s+conoce\s+como)\b"
)


def _search_report_defines_the_ask(text: str, payload: dict, user_text: str) -> str:
    """The term the report opens by defining, when the request used it for an attribute, one of a series or the kind of
    thing to find (semantic.web.undefined_asked_phrases): the person did not ask what it means."""

    if _search_results_text(payload) is None:
        return ""
    seen = payload.get("seen") if isinstance(payload.get("seen"), dict) else {}
    phrases = [
        set(phrase.split())
        for source in (user_text or "", str(seen.get("query") or ""))
        for phrase in undefined_asked_phrases(source)
    ]
    first = re.split(r"(?<=[.!?;])\s+", str(text).strip())[0]
    found = _REPORT_DEFINES.match(_reading_fold(first))
    if found is None or not phrases:
        return ""
    term = found.group("term")
    # A title said with capitals («Scary Movie is a 2000 comedy») names a work, not the word.
    written = re.search(r"\b" + r"\W+".join(re.escape(word) for word in term.split()) + r"\b", first, re.IGNORECASE)
    if written is not None and any(word[:1].isupper() for word in written.group(0).split()[1:]):
        return ""
    words = set(re.findall(r"[a-z]+", term))
    if not any(words and all(_search_term_found(word, phrase) for word in words) for phrase in phrases):
        return ""
    # It is the word defined only when a result is the article on that word («Genre», «Headline - Wikipedia», «Drama
    # histórico (cinematografía)»); «The genre is drama» over the film's own article answers.
    for item in _search_results_of(payload):
        if not isinstance(item, dict):
            continue
        heading = re.split(r"\s+[-|–—]\s+|\s*\(", str(item.get("title") or ""), maxsplit=1)[0]
        heading_words = re.findall(r"[a-z]+", _reading_fold(heading))
        if 0 < len(heading_words) <= 3 and _search_term_found(heading_words[0], words):
            return term
    return ""


def _verified_search_results(situation: dict) -> bool:
    """A completed, verified web.search whose observation carries results."""

    if (
        situation.get("kind") != "operation"
        or situation.get("operation") != "web.search"
        or situation.get("verified") is not True
        or situation.get("succeeded") is not True
    ):
        return False
    results = _merged_observed(situation).get("results")
    return isinstance(results, list) and bool(results)


def _search_unsupported_claim(text: str, results_text: str) -> str | None:
    """A weather assertion in a search report that no result states verbatim."""

    folded_results = _reading_fold(results_text)
    for match in _SEARCH_WEATHER_CLAIM.finditer(_reading_fold(text)):
        claim = re.sub(r"\s+", " ", match.group(0)).strip()
        if claim and claim not in folded_results:
            return claim
    return None


_MEANS_WORDS = (
    r"(?:python|powershell|bash|cmd|scripts?|c[oó]digo|code|terminal|consola|console|api)"
)
# «sin Python», «sin usar un script», «no usé la terminal», «without running code»:
# a negated mention is the honest disclaimer, not a claim.
_NEGATED_MEANS = re.compile(
    r"\b(?:sin(?:\s+(?:usar|ejecutar|correr|necesitar|recurrir\s+a|tener\s+que\s+usar))?|"
    r"no\s+(?:us[eé]|utilic[eé]|ejecut[eé]|corr[ií]|necesit[oé]|recurr[ií]\s+a|hace\s+falta|"
    r"necesito|uso|utilizo|ejecuto)|"
    r"without(?:\s+(?:using|running|needing))?|"
    r"(?:did\s+not|didn't|don't|do\s+not)\s+(?:use|run|need)|no\s+need\s+(?:for|of))"
    r"(?:\s+(?:el|la|un|una|ningun|ninguna|a|the|any))?\s+" + _MEANS_WORDS + r"\b",
    re.IGNORECASE,
)


def _claims_declined_means(text: str) -> bool:
    """True when the reply mentions the declined means other than to deny it."""

    folded = _NEGATED_MEANS.sub(" ", _reading_fold(text))
    return re.search(r"\b" + _MEANS_WORDS + r"\b", folded) is not None


# NETWORK1729: a network name the reply quotes, in guillemets, curly or straight quotes.
_QUOTED_NAME = re.compile("[" + chr(171) + chr(8220) + chr(34) + "]([^" + chr(187) + chr(8221) + chr(34) + "]{1,64})[" + chr(187) + chr(8221) + chr(34) + "]")
