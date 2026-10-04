"""Knowledge that is looked up before it is said (M53, step 6 of goal v3; owner's decision D35).

R8 (``research/R8_conocimiento_honesto.md``): what the 4B model gets wrong from memory is predicted by the kind of fact
better than by its confidence (Mallen et al. 2023, Adaptive-RAG). A recipe for a named dish and the plot of a named
work were recited wrong in the development runs — banana bread without banana, pastel de choclo as a sponge cake,
The Hobbit as the theft of the One Ring. Those two kinds are read here, from the person's words and not from any
single phrase, and are looked up (``web.search`` with the class word the provider reads: «receta …», «resumen …»);
what stays talk — an open suggestion («una receta vegetariana»), code, an explanation — is not read here.

- ``reference_lookup``  the named dish or work the request asks about, with the query that looks it up; a question
  right after a work's lookup that names no other work is about that same work (F-p11-t2 «¿por qué es peligroso el
  anillo?» after the summary of *El hobbit*).
- ``servings_asked``    how many people a recipe is asked for («pa 6», «para 6 personas», «for four»).
- ``memory_answer_form`` the form of an answer said from memory: a recipe, a list or a few sentences (M87).
- ``kitchen_quantity``  M88: how much of an ingredient, or a kitchen measure of it, is asked («cuánta sal le echo al
  agua», «cuánto sería eso de harina en gramos»): a figure that depends on the thing measured, looked up with what the
  conversation carried (kind ``quantity``).
- ``asks_a_figure``     M92 (D52): what is asked is a quantity, distance, duration, date, year or count, which memory
  never answers.
- ``figure_lookup``     M104 (D52): a figure of the world asked as such («how tall is mount everest») is looked up
  with the person's words (kind ``figure``); one computed from the person's numbers, or of their own things, is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .conversation import asks_for_code, translates_what_was_said
from .normalize import fold, fold_in_place, spelled_out
from .quantities import conversion_asked, numbers_in, spoken_numbers_in

__all__ = [
    "ReferenceLookup", "asks_a_figure", "figure_lookup", "kitchen_quantity", "memory_answer_form", "reference_lookup",
    "servings_asked",
]


@dataclass(frozen=True)
class ReferenceLookup:
    """A named referent to look up: ``kind`` is ``recipe``, ``plot``, ``ranking``, ``quantity`` (M88) or ``figure``
    (M104); ``query`` is what ``web.search`` is asked."""

    kind: str
    subject: str
    query: str
    language: str


# The kitchen said in the request: without it «cómo hacer una cometa» is an explanation, not a recipe.
_CULINARY_ES = r"recetas?|ingredientes?|cocina|cocinar|cocino|cocinando|hornear|horneo|horno"
_CULINARY_EN = r"recipes?|ingredients?|kitchen|cook|cooking|bake|baking|oven"
_CULINARY = re.compile(rf"\b(?:{_CULINARY_ES}|{_CULINARY_EN})\b")
# M118 (D58 with D35, DEV-F F-w31-t1 «como se hace el pebre? lo quiero hacer pal asado…», F-w34-t1 «¿cómo se hace una
# tortilla de patatas para cuatro personas? Con cebolla…»): the public-lookup guard searched these and the contextual
# decider talks them; a meal or an ingredient said beside the dish says the kitchen too, for the recipe reader alone.
_FOOD_CUE = re.compile(
    r"\b(?:asado|parrilla|cebollas?|ajos?|huevos?|harina|patatas|papas|tomates?|aceite|mantequilla|azucar|"
    r"barbecue|onions?|garlic|eggs?|flour|butter)\b"
)
_ENGLISH_CULINARY = re.compile(rf"\b(?:{_CULINARY_EN})\b")

_ARTICLE = r"(?:(?:el|la|los|las|un|una|unos|unas|del|al|a|an|the|some|my|mi|mis|unas?\s+ricas?)\s+)"
# The dish ends where the request goes on: punctuation, how many it is for, when, or the rest of the sentence.
# M83 (DEV-D v3o D-s017 «…southern-style mac and cheese recipe» restated by the decider → the query «recipe cheese»):
# «and» joins the two halves of a dish («mac and cheese», «rice and beans») as «y» does in Spanish; it ends the dish
# only before what goes on with the request, like «y no», «y me».
_DISH_END = (
    r"(?=\s*(?:[,.;:!?¿¡()]|$)|\s+(?:para|for|que|porque|pero|y\s+(?:no|me|te|que)|"
    r"and\s+(?:i|me|you|we|then|also|tell|give|show|send|how|what|it|please|make|explain)|but|so|esta|este|hoy|manana|"
    r"tonight|today|tomorrow|paso|step|en\s+(?:la|el|casa|mi)|at\s+home|por\s+favor|please|nomas|no\s+mas|simple|"
    r"facil|rapido|rapida|casero|casera|easy|quick|sin\s+horno|como\s+(?:lo|la)|like)\b)"
)
_DISH = rf"(?P<dish>[a-zn]+(?:\s+(?:(?:de|del|con|al|a\s+la|en|y|with|and|of|a)\s+)?[a-zn]+){{0,5}}?){_DISH_END}"
_RECIPE_DISH = (
    re.compile(rf"\b(?:recetas?|recipes?)\b(?:\s+[a-z]+){{0,2}}?\s+(?:de|del|para|pa|for|of)\s+"
               rf"(?:(?:hacer|preparar|making|make)\s+)?{_ARTICLE}?{_DISH}"),
    re.compile(rf"\b(?:ingredientes?|ingredients?)\b(?:\s+[a-z]+){{0,3}}?\s+(?:de|del|para|pa|for|of|in)\s+"
               rf"(?:(?:hacer|preparar|making|make)\s+)?{_ARTICLE}?{_DISH}"),
    # M118: «¿cómo se hace el pebre?», «how do you make shepherd's pie», with the kitchen said beside it.
    re.compile(rf"\b(?:como\s+se\s+(?:hace|hacen|prepara|preparan)|how\s+(?:do\s+(?:you|i)|to)\s+(?:make|prepare))\s+"
               rf"{_ARTICLE}?{_DISH}"),
    re.compile(rf"\b(?:hacer|hago|hacemos|preparar|preparo|cocinar|cocino|hornear|horneo|make|making|cook|cooking|"
               rf"bake|baking|prepare)\s+{_ARTICLE}?{_DISH}"),
    re.compile(rf"\b(?:ingredientes?|ingredients?)\b(?:\s+[a-z]+){{0,2}}?\s+(?:lleva|llevan|tiene|tienen|necesita|"
               rf"necesitan|has|have|needs?|goes\s+into|go\s+into)\s+{_ARTICLE}?{_DISH}"),
    re.compile(rf"\b(?:recetas?|recipes?)\s+(?!de\b|del\b|para\b|pa\b|for\b|of\b){_DISH}"),
)
# M81 (DEV-D v3m D-s017 «a good southern style mac n cheese recipe» → a roux made with the drained pasta): English
# names the dish before «recipe». The dish is the run of words right before it, back to an article, a praise, a
# pronoun or a verb («I need a banana bread recipe» → «banana bread»; «my grandma recipe» is nobody's dish).
_RECIPE_AFTER_DISH = re.compile(r"\brecipes?\b")
_BEFORE_THE_DISH = frozenset({
    "a", "an", "the", "some", "any", "my", "your", "our", "his", "her", "their", "this", "that", "these", "those",
    "good", "great", "nice", "easy", "simple", "quick", "classic", "best", "tasty", "delicious", "authentic",
    "homemade", "traditional", "proper", "favorite", "favourite", "new", "old", "fashioned", "family", "grandma",
    "grandmas", "mom", "moms", "i", "me", "you", "we", "need", "want", "have", "give", "get", "find", "save", "send",
    "share", "is", "are", "what", "whats", "for", "of", "to", "do", "please", "and", "or", "with", "s",
})
_DISH_CONNECTORS = frozenset({"and", "with", "or"})


def _recipe_named_before(folded: str) -> str | None:
    found = _RECIPE_AFTER_DISH.search(folded)
    if found is None:
        return None
    words = re.findall(r"[a-z]+", folded[: found.start()])
    dish: list[str] = []
    for index in range(len(words) - 1, -1, -1):
        word = words[index]
        if len(dish) == 6:
            break
        # M83 (DEV-D v3o D-s017 «a good southern-style mac and cheese recipe» → «cheese»): a connector between two
        # words of the dish («mac and cheese», «fish and chips») is part of its name.
        joins = word in _DISH_CONNECTORS and dish and index > 0 and words[index - 1] not in _BEFORE_THE_DISH
        if word in _BEFORE_THE_DISH and not joins:
            break
        dish.insert(0, word)
    return " ".join(dish) if dish and not all(word in _NOT_A_DISH for word in dish) else None
# A category, a meal or a pronoun is no dish: «una receta vegetariana», «algo para la cena», «make it».
_NOT_A_DISH = frozenset({
    "algo", "eso", "esto", "esa", "ese", "esta", "este", "comida", "comidas", "cena", "almuerzo", "desayuno", "once",
    "merienda", "receta", "recetas", "plato", "platos", "cosas", "todo", "nada", "mas", "comer", "cenar", "almorzar",
    "vegetariana", "vegetariano", "vegana", "vegano", "facil", "rapida", "rapido", "sana", "sano", "saludable",
    "rica", "rico", "casera", "casero", "nueva", "nuevo", "tipica", "tipico", "postre", "postres", "lista", "tarea",
    "something", "food", "dinner", "lunch", "breakfast", "meal", "meals", "it", "that", "this", "one", "dish",
    "dishes", "vegetarian", "vegan", "healthy", "easy", "quick", "simple", "dessert", "desserts", "list", "sure",
    "me", "te", "le", "lo", "la", "you", "sense", "money", "time", "tiempo", "dinero", "plata", "caso", "falta",
    "faltan", "reservation", "reserva", "please", "porfa",
})

_PLOT_CUE = re.compile(
    r"\b(?:resum\w*|sinopsis|argumento|trama|summar\w*|synopsis|plot|de\s+que\s+(?:se\s+)?trata\w*|"
    r"what\s+(?:is|was|'s)\s+.{1,60}?\s+about|what\s+happens\s+in)\b"
)
_WORK_NOUN = (
    r"libro|libros|novela|pelicula|serie|obra|saga|cuento|book|novel|movie|film|series|show|play"
)
_TITLE_END = r"(?=\s*(?:[,.;:!?¿¡()]|$)|\s+(?:en\s+(?:pocas|dos|tres|una)|in\s+(?:a\s+few|one|two|three)|por\s+favor|please|para|for|y\s+(?:me|dime|luego)|and\s+(?:tell|then))\b)"
_WORK = re.compile(
    rf"\b(?P<noun>{_WORK_NOUN})\s+(?:(?:de|del|de\s+la|of|of\s+the|called|llamad[oa]|titulad[oa])\s+)?"
    rf"(?:(?:el|la|los|las|the)\s+)?(?P<title>[a-z0-9n]+(?:\s+[a-z0-9n]+){{0,6}}?){_TITLE_END}"
)
# The same, when the person names the work by its capitalized title without saying what it is («Resume El Hobbit»).
_TITLED = re.compile(
    r"\b(?i:resum\w*|summar\w*|sinopsis|synopsis|argumento|trama|plot)\s+(?:(?i:me|nos|el|la|los|las|the|of|de|del)\s+)*"
    r"(?P<title>[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'-]*(?:\s+(?:de|del|la|las|los|el|of|the|and|y|[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ'-]*)){0,6})"
)
_NOT_A_TITLE = frozenset({
    "que", "lo", "esto", "eso", "este", "esta", "it", "this", "that", "what", "our", "nuestra", "nuestro", "mi", "my",
    "tu", "your", "conversacion", "conversation", "texto", "text", "articulo", "article", "chat", "correo", "email",
    "mensaje", "message", "documento", "document", "pagina", "page", "video", "reunion", "meeting",
})
_QUESTION_HEAD = re.compile(
    r"^\W*(?:y\s+|and\s+)?(?:por\s*que|porque|que|quien|quienes|como|cuando|donde|cual|cuales|cuanto|cuantos|"
    r"why|what|who|how|when|where|which)\b"
)
# A question about BAXY or the person, asking an opinion, or inviting to imagine («¿cómo continuarías la historia?
# Suponiendo que…», F-p11-t3) is not a question about the work's story.
_ABOUT_US = re.compile(
    r"\b(?:te|tu|tus|vos|usted|opinas|piensas|crees|pensas|gusta|gusto|recomiendas|you|your|think|like|recommend|"
    r"\w+(?:arias|erias|irias)|supon\w*|imagin\w*|what\s+if|y\s+si)\b"
)


def _language(folded: str, english_cue: bool) -> str:
    english = len(re.findall(r"\b(?:the|of|how|what|do|i|to|a|is|recipe|make|summary|book|movie)\b", folded))
    spanish = len(re.findall(r"\b(?:el|la|de|del|que|como|me|para|receta|hacer|resumen|libro|un|una)\b", folded))
    if english != spanish:
        return "en" if english > spanish else "es"
    return "en" if english_cue else "es"


def _recipe(folded: str) -> ReferenceLookup | None:
    if _CULINARY.search(folded) is None and _FOOD_CUE.search(folded) is None:
        return None
    for pattern in _RECIPE_DISH:
        for found in pattern.finditer(folded):
            dish = found.group("dish").strip()
            words = dish.split()
            if (
                not words
                or words[0] in _NOT_A_DISH
                or words[-1] in {"de", "del", "con", "al", "en", "y", "with", "and", "of", "a"}
                or all(word in _NOT_A_DISH for word in words)
                or len(dish) < 3
            ):
                continue
            language = _language(folded, _ENGLISH_CULINARY.search(folded) is not None)
            return ReferenceLookup("recipe", dish, ("recipe " if language == "en" else "receta ") + dish, language)
    named = _recipe_named_before(folded)
    if named is not None and len(named) >= 3:
        return ReferenceLookup("recipe", named, "recipe " + named, "en")
    return None


def _plot(text: str, folded: str) -> ReferenceLookup | None:
    if _PLOT_CUE.search(folded) is None:
        return None
    language = _language(folded, False)
    work = _WORK.search(folded)
    if work is not None:
        title = work.group("title").strip()
        if title.split()[0] not in _NOT_A_TITLE:
            subject = f"{work.group('noun')} {title}"
            return ReferenceLookup("plot", subject, ("summary " if language == "en" else "resumen ") + subject, language)
    titled = _TITLED.search(str(text or ""))
    if titled is not None:
        title = fold(titled.group("title"))
        if title and title.split()[0] not in _NOT_A_TITLE:
            return ReferenceLookup("plot", title, ("summary " if language == "en" else "resumen ") + title, language)
    return None


# A ranking of the world asked by its superlative («¿cuáles son los 9 objetos más brillantes del cielo nocturno?»,
# «what are the tallest mountains in the world»): the order and the figures are what memory gets wrong (F-s020).
_COUNT = r"\d{1,2}|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|veinte|two|three|four|five|six|seven|eight|nine|ten|twenty"
_ASK = r"(?:cuales|cual|dime|decime|dame|nombra|nombrame|lista|listame|enumera|di|what|which|name|list|tell\s+me|give\s+me)"
_RANKING_ES = re.compile(
    rf"\b{_ASK}\b.*?\b(?:los|las)\s+(?:(?:{_COUNT})\s+)?(?P<noun>[a-z]+(?:\s+[a-z]+)?)\s+(?:mas|menos)\s+"
    r"(?P<adj>[a-z]+)(?P<rest>\s+(?:de|del|en)\s+(?:(?:la|el|los|las)\s+)?[a-z]+(?:\s+[a-z]+){0,2})?"
)
_RANKING_EN = re.compile(
    rf"\b{_ASK}\b.*?\bthe\s+(?:(?:{_COUNT})\s+)?(?P<adj>most\s+[a-z]+|[a-z]{{3,}}est)\s+(?P<noun>[a-z]+(?:\s+[a-z]+)??)"
    r"(?P<rest>\s+(?:in|of|on)\s+(?:the\s+)?[a-z]+(?:\s+[a-z]+){0,2})?"
)
# What is ranked on this PC or in the person's things is read there, never looked up.
_NOT_RANKED_HERE = frozenset({
    "que", "cosas", "things", "procesos", "proceso", "ventanas", "archivos", "carpetas", "aplicaciones", "apps",
    "programas", "pestanas", "correos", "processes", "windows", "files", "folders", "programs", "tabs", "emails",
    "notas", "tareas", "notes", "tasks", "juegos", "games", "canciones", "songs", "mensajes", "messages",
})
# M56 (v3c-final F-s017 «what's the latest song from NeYo» → «ranking latest song», trot music from Korea): a ranking
# is asked only by the superlative of an attribute the world is ordered by — size, height, brightness, population,
# age, speed, price, what is measured. «último», «latest», «newest», «recent» ask for the newest thing of someone,
# not for an order, and «best», «popular» are opinions: none of them is a ranking.
_ORDERABLE_ES_O = (
    "alt", "elevad", "baj", "larg", "profund", "extens", "pequen", "chic", "rapid", "lent", "car", "costos", "barat",
    "ric", "fri", "calid", "caluros", "pesad", "livian", "antigu", "viej", "dens", "anch", "estrech", "vendid",
    "visitad", "hablad", "poblad", "habitad", "peligros", "venenos", "contaminad", "lluvios", "poderos", "caudalos",
    "grues", "lejan", "cercan", "luminos", "masiv", "numeros", "extendid", "seguid", "premiad",
)
_ORDERABLE_ES = frozenset(
    {stem + ending for stem in _ORDERABLE_ES_O for ending in ("o", "a", "os", "as")}
    | {"grande", "grandes", "brillante", "brillantes", "pobre", "pobres", "caliente", "calientes", "potente",
       "potentes", "fuerte", "fuertes", "distante", "distantes", "comun", "comunes", "letal", "letales", "mortal",
       "mortales", "veloz", "veloces"}
)
_ORDERABLE_EN_MOST = frozenset({
    "populous", "populated", "expensive", "visited", "spoken", "dangerous", "venomous", "massive", "luminous",
    "distant", "polluted", "powerful", "valuable", "abundant", "common", "densely", "widely", "sold", "followed",
    "awarded", "decorated", "remote", "crowded",
})
_ORDERABLE_EN_EST = frozenset({
    "tallest", "highest", "largest", "biggest", "brightest", "longest", "deepest", "smallest", "fastest", "slowest",
    "heaviest", "lightest", "hottest", "coldest", "oldest", "richest", "poorest", "densest", "widest", "lowest",
    "farthest", "furthest", "wettest", "driest", "strongest", "deadliest", "busiest", "shortest", "cheapest",
    "narrowest", "thickest", "loudest", "sunniest", "rainiest", "windiest", "hardest",
})


def _orderable(adj: str, language: str) -> bool:
    if language == "es":
        return adj in _ORDERABLE_ES
    if adj.startswith("most "):
        return adj.split(None, 1)[1] in _ORDERABLE_EN_MOST
    return adj in _ORDERABLE_EN_EST


def _ranking(folded: str) -> ReferenceLookup | None:
    if re.search(r"\b(?:mi|mis|tu|tus|my|your)\b", folded):
        return None
    for pattern, language in ((_RANKING_ES, "es"), (_RANKING_EN, "en")):
        found = pattern.search(folded)
        if found is None:
            continue
        noun, adj = found.group("noun").strip(), found.group("adj").strip()
        if any(word in _NOT_RANKED_HERE for word in noun.split()) or not _orderable(adj, language):
            continue
        rest = (found.group("rest") or "").strip()
        subject = " ".join(part for part in ((noun, adj, rest) if language == "es" else (adj, noun, rest)) if part)
        return ReferenceLookup("ranking", subject, "ranking " + subject, language)
    return None


# D59.8 (owner, 2026-10-02; DEV-D D-p35-t1 «Has un análisis de FODA sobre la empresa Adidas…» written from memory): the
# analysis of a real, named organization (a SWOT/FODA/DAFO, its pros and cons, its strengths and weaknesses, a business
# or market analysis of it) is written from what is read about it first: ``web.search`` on its name with «empresa» /
# «company» (+1 search), then the analysis from those pages (figures only if read, D52). A topic that is no named
# organization («pros y contras del teletrabajo», «un FODA de mi emprendimiento», «a SWOT for a coffee shop») stays talk.
# A business framework is asked of an organization: the name in its own capitals says which one. Any other analysis,
# or the pros and cons («pros y contras de Python», «análisis de Hamlet»), is of an organization only when the person
# says it is one («de la empresa Falabella», «Acme Inc.»).
_BUSINESS_ANALYSIS = (
    r"(?:(?:analisis|estudio)\s+(?:de\s+)?)?(?P<framework>foda|dafo|swot)(?:\s+(?:analysis|analisis))?|"
    r"(?:analisis|estudio)\s+(?P<business>estrategico|empresarial|de\s+negocio|financiero|de\s+mercado|"
    r"de\s+la\s+competencia)|"
    r"(?P<business_en>business|strategic|market|competitor|competitive|financial)\s+analysis"
)
_ANALYSIS_ASKED = (
    rf"{_BUSINESS_ANALYSIS}|"
    # A PESTEL is as often of a country or a market («un análisis PESTEL de Chile»).
    r"(?:(?:analisis|estudio)\s+(?:de\s+)?)?pestel(?:\s+(?:analysis|analisis))?|"
    r"pros\s+y\s+contras|ventajas\s+y\s+desventajas|fortalezas\s+y\s+debilidades|pros\s+and\s+cons|"
    r"strengths\s+and\s+weaknesses|analisis|analysis"
)
# Who asks for it: an order or a wish, a question for the pros and cons, or the analysis named alone. A question about an
# analysis already written («¿cómo hiciste el FODA de Adidas?») asks for none.
_ANALYSIS_HEAD = (
    r"(?:(?:por\s+favor|please|oye|hey|ok)\s*,?\s*)?"
    r"(?:(?:me\s+)?(?:puedes|podrias|can\s+you|could\s+you|would\s+you)\s+)?"
    r"(?:(?:haz|hazme|has(?=\s+(?:un|una)\b)|hacer|hacerme|haceme|realiza|realizame|realizar|elabora|elaborame|"
    r"elaborar|prepara|preparame|preparar|escribe|escribeme|escribir|redacta|redactame|redactar|dame|darme|dime|"
    r"decirme|quiero|necesito|me\s+haces|genera|generar|make|do|write|draft|create|give\s+me|tell\s+me|run|generate|"
    r"i\s+(?:need|want)|i'?d\s+like)\b(?:\s+(?:me|nos|us|un|una|el|la|los|las|an?|the|breve|rapido|corto|completo|"
    r"detallado|pequeno|quick|brief|short|full|detailed|small|simple))*\s+"
    r"|(?:cuales|que)\s+son\s+(?:los|las)\s+|what\s+are\s+(?:the\s+)?|(?:los|las|the)\s+)?"
)
_ORGANIZATION_NOUN = (
    r"(?:empresa|compania|marca|corporacion|firma|startup|multinacional|banco|aerolinea|cadena|tienda|"
    r"company|brand|corporation|firm|bank|airline|retailer|chain|store)"
)
_ANALYSIS_OF = re.compile(
    rf"^{_ANALYSIS_HEAD}(?:{_ANALYSIS_ASKED})\s+(?:de|del|sobre|para|of|on|about|for)\s+"
    rf"(?:(?P<org>(?:(?:la|el|the)\s+)?{_ORGANIZATION_NOUN})\s+)?(?P<name>[\w&'.-]+(?:\s+[\w&'.-]+){{0,3}}?)"
    r"(?=\s*(?:[,;:!?¿¡()]|\.(?:\s|$)|$)|\s+(?:y|e|and|para|for|con|with|en|in|utilizando|usando|using|desde|from|"
    r"como|as|que|that|por\s+favor|please)\b)"
)
# «Nike's SWOT», «Tesla pros and cons»: the organization said first.
_ANALYSIS_OF_NAMED_FIRST = re.compile(
    rf"^{_ANALYSIS_HEAD}(?:(?:a|an|the|un|una)\s+)?(?P<name>[\w&.-]+(?:\s+[\w&.-]+){{0,2}}?)(?:'s)?\s+"
    rf"(?:{_ANALYSIS_ASKED})[\s.!?]*$"
)
_NOT_AN_ORGANIZATION = re.compile(
    r"^(?:un|una|unos|unas|mi|mis|tu|tus|su|sus|nuestr[oa]s?|vuestr[oa]s?|este|esta|ese|esa|a|an|my|our|your|their|"
    r"this|that|these|those|some|any|el|la|los|las|the|lo|eso|esto|it|them|ellos|ellas|de|del|of|for|para|donde|"
    r"where|que|which|who|quien|cual|en|in)\b"
)
_ORGANIZATION_SUFFIX = re.compile(r"\b(?:inc|corp|ltd|llc|gmbh|s\.?\s?a|s\.?\s?l|s\.?\s?a\.?\s?s|plc|co)\.?$")


def _analysis(text: str) -> ReferenceLookup | None:
    raw = " ".join(str(text or "").split())
    same = fold_in_place(raw)
    body = same.strip(" ¿?¡!.,")
    lead = len(same) - len(same.lstrip(" ¿?¡!.,"))
    found = _ANALYSIS_OF.match(body) or _ANALYSIS_OF_NAMED_FIRST.match(body)
    if found is None:
        return None
    name = raw[lead + found.start("name"):lead + found.end("name")].strip(" .'")
    folded_name = fold(name)
    if not name or _NOT_AN_ORGANIZATION.match(folded_name):
        return None
    groups = found.groupdict()
    business = any(groups.get(key) for key in ("framework", "business", "business_en"))
    named = (
        groups.get("org") is not None
        or _ORGANIZATION_SUFFIX.search(folded_name) is not None
        # Its own capital, where the person wrote it, is a proper name («SWOT of Tesla», «FODA de Coca-Cola»); not at
        # the start of the message (unless said as the owner, «Nike's SWOT») nor in a message all in capitals.
        or (
            business
            and name[:1].isupper()
            and (found.start("name") > 0 or body[found.end("name"):].startswith("'s"))
            and not raw.isupper()
        )
    )
    if not named:
        return None
    english_cue = re.search(r"\b(?:swot|analysis|pros\s+and\s+cons|strengths)\b", fold(raw)) is not None
    language = _language(fold(raw), english_cue)
    return ReferenceLookup("analysis", name, name + (" company" if language == "en" else " empresa"), language)


def _direct(text: str) -> ReferenceLookup | None:
    folded = spelled_out(fold(text))
    return _recipe(folded) or _plot(text, folded) or _ranking(folded) or _analysis(text)


# M88 (step 6 of goal v3: facts with figures and recipes are looked up before they are said; DEV-D v3r D-w01-t2 «oye y
# cuánta sal le echo al agua, más o menos, cachai» after a timer «pa los tallarines» → «Al menos un cucharón de sal.»,
# D-w01-t3 «ya y pa 3 litros cuántas cucharaditas serían» → «…equivale aproximadamente a 12 cucharaditas», D-w10-t2
# «¿Y cuánto sería eso de harina en gramos?» after «2 tazas de harina de maíz» → «…aproximadamente a 400 gramos»; about
# 10 g per litre, 5–6 teaspoons and 280–300 g): how much of an ingredient, or a kitchen measure of it, is a figure that
# depends on the thing measured, and the talk recited it wrong. It is looked up, with the ingredient, the dish and the
# quantity the conversation carried; a pure conversion between units of one kind is computed instead
# (``semantic.quantities.conversion_asked``). Folded.
_INGREDIENT = (
    r"sal|azucar|harina|harinas|arroz|agua|aceite|mantequilla|manteca|margarina|leche|crema|nata|huevos?|levadura|"
    r"polvos?\s+de\s+hornear|bicarbonato|pasta|fideos|tallarines|espaguetis?|spaghetti|macarrones|queso|maiz|maicena|"
    r"avena|cacao|chocolate|miel|vinagre|yogurt?|carne|pollo|pescado|papas|patatas|porotos|frijoles|lentejas|"
    r"garbanzos|quinoa|canela|pimienta|ajo|cebolla|tomates?|gelatina|"
    r"salt|sugar|flour|rice|water|oil|butter|milk|cream|eggs?|yeast|baking\s+(?:powder|soda)|noodles|macaroni|cheese|"
    r"cornmeal|cornstarch|corn|oats|cocoa|honey|vinegar|meat|chicken|fish|potatoes|beans|lentils|chickpeas|cinnamon|"
    r"pepper|garlic|onions?|tomato(?:es)?"
)
_KITCHEN_MEASURE = (
    r"tazas?|cucharadas?|cucharaditas?|cucharon(?:es)?|pizcas?|cups?|tablespoons?|teaspoons?|tbsp|tsp|pinch(?:es)?"
)
_INGREDIENT_WORD = re.compile(rf"\b(?:{_INGREDIENT})\b")
_KITCHEN_MEASURE_WORD = re.compile(rf"\b(?:{_KITCHEN_MEASURE})\b")
_AMOUNT_ASKED = re.compile(r"\b(?:cuant[oa]s?|how\s+(?:much|many))\b")
_UNIT_ASKED = re.compile(
    rf"\b(?:en|in|cuant[oa]s|how\s+many)\s+(?P<unit>gramos|grams|kilos|kilogramos|ml|mililitros|litros|onzas|ounces|"
    rf"{_KITCHEN_MEASURE})\b"
)
# The person's own things, and a taste asked («¿cuánto te gusta el chocolate?»), are no figure of the world.
_OWN_THINGS = re.compile(
    r"\b(?:mi|mis|tu|tus|my|your|lista|listas|list|lists|nota|notas|notes|gusta|gustan|like|love|prefer\w*|"
    r"favorit\w*)\b"
)
_KITCHEN_LEAD = re.compile(
    r"^(?:(?:oye|oiga|ya|y|e|ok|okay|bueno|entonces|pues|and|so|baxy|olly|hey|ah|mira|che|a\s+ver|vale)\b[\s,]*)+"
)
_KITCHEN_TAIL = re.compile(
    r"(?:[\s,]+(?:mas\s+o\s+menos|cachai|cachay|po|pues|porfa|por\s+favor|please|pls|approximately|roughly|"
    r"more\s+or\s+less|nomas|parce|pana|we|wey|weon|mas\s+o\s+menos\s+cachai))+$"
)
_POINTS_BACK = re.compile(r"\b(?:eso|esto|esa|esas|esos|lo|that|this|it|those)\b")
# «2 tazas de harina de maíz», «1 cucharadita de sal», «un cucharón de sal», «two cups of flour».
_MEASURED_INGREDIENT = re.compile(
    rf"(?P<phrase>(?:\d+(?:[.,/]\d+)?|un|una|medio|media|dos|tres|cuatro|cinco|one|two|three|four|five|half\s+a)\s+"
    rf"(?:{_KITCHEN_MEASURE}|gramos|grams|g|ml|litros?|liters?|kilos?)\s+(?:de|of)\s+"
    r"(?P<ingredient>[a-z]+(?:\s+(?:de|del)\s+[a-z]+)?))"
)


def _kitchen_clause(folded: str) -> str:
    clause = folded.strip(" ¿?¡!.,;")
    for _ in range(3):
        clause = _KITCHEN_TAIL.sub("", _KITCHEN_LEAD.sub("", clause).strip(" ¿?¡!.,;")).strip(" ¿?¡!.,;")
    return clause


def kitchen_quantity(
    text: str, prior_requests: Iterable[str] = (), last_reply: str = "",
) -> ReferenceLookup | None:
    """How much of an ingredient, or a kitchen measure of one, the request asks (see above), with the query that looks
    it up; None for a pure conversion, the person's own things or anything else."""

    folded = spelled_out(fold(text))
    if (
        _AMOUNT_ASKED.search(folded) is None and _UNIT_ASKED.search(folded) is None
        or _OWN_THINGS.search(folded) is not None
        or conversion_asked(text) is not None
    ):
        return None
    earlier = [spelled_out(fold(request)) for request in reversed(list(prior_requests)) if str(request or "").strip()]
    reply = spelled_out(fold(last_reply))
    named = _INGREDIENT_WORD.search(folded) is not None
    if not named and not (
        _KITCHEN_MEASURE_WORD.search(folded) is not None
        and any(_INGREDIENT_WORD.search(said) is not None for said in (reply, *earlier[:2]))
    ):
        return None
    clause = _kitchen_clause(folded)
    unit = _UNIT_ASKED.search(clause)
    measured = next(
        (
            found for found in _MEASURED_INGREDIENT.finditer(reply)
            if not named or any(word in clause.split() for word in found.group("ingredient").split() if len(word) > 3)
        ),
        None,
    )
    if measured is not None and _POINTS_BACK.search(clause) is not None and unit is not None:
        # «¿cuánto sería eso de harina en gramos?» after «2 tazas de harina de maíz»: that measure, in the unit asked.
        query = f"{measured.group('phrase')} {'in' if unit.group(0).startswith('in') else 'en'} {unit.group('unit')}"
    else:
        # What the conversation said to cook with, or for, that the request leaves out: its ingredients and dishes.
        carried = [
            word
            for said in (reply, *earlier[:2])
            for word in dict.fromkeys(found.group(0) for found in _INGREDIENT_WORD.finditer(said))
            if word not in clause
        ]
        query = " ".join([clause, *dict.fromkeys(carried)][:4])
    language = _language(folded, re.search(r"\b(?:how|much|many|salt|sugar|flour|cups?)\b", folded) is not None)
    return ReferenceLookup("quantity", clause, query, language)


_ONE_RECIPE = re.compile(r"\b(?:receta|recipe)\b")


def asks_one_recipe(text: str) -> bool:
    """M102 (DEV-D v3z D-s017 «a good southern style mac n cheese recipe», D-w10-t1 «¿me regalas una receta sencilla de
    arepas de queso?»): the request asks for a named dish's recipe, one, whose quantities and steps are the answer.
    Recipes searched for (SEARCH2005 «search for pizza recipes») are the pages that have them, not one recipe."""

    lookup = reference_lookup(text)
    return lookup is not None and lookup.kind == "recipe" and _ONE_RECIPE.search(fold(text)) is not None


def reference_lookup(text: str, prior_requests: Iterable[str] = (), last_reply: str = "") -> ReferenceLookup | None:
    """The named dish or work this request asks about, to be looked up before anything is said about it.

    ``prior_requests`` are the person's earlier messages, oldest first: a question about the story right after a
    work's lookup, naming no other work, looks that same work up again (its plot answers the question). M88: how much
    of an ingredient is asked (``kitchen_quantity``), with ``last_reply``, BAXY's last answer, as a referent.
    """

    # M56 (v3c-final F-w14-t1 «escribeme un query de sql q me saque los users activos del ultimo mes»): code asked
    # for is written by the model; nothing in it is a dish, a work or a ranking to look up. M157 (DEV-I v4v I-w41-t3
    # «tradúceme eso al inglés» → «Traduce al inglés «¿Cuántas onzas son 3 tazas de harina de trigo?»».): nor in words
    # already said that are asked in another language (``translates_what_was_said``).
    if asks_for_code(text) or translates_what_was_said(text):
        return None
    direct = _direct(text) or kitchen_quantity(text, prior_requests, last_reply) or figure_lookup(text, last_reply)
    if direct is not None:
        return direct
    earlier = [str(request) for request in prior_requests if str(request or "").strip()]
    if not earlier:
        return None
    previous = _direct(earlier[-1])
    folded = spelled_out(fold(text))
    if (
        previous is None
        or previous.kind != "plot"
        or _QUESTION_HEAD.search(folded) is None
        or _ABOUT_US.search(folded) is not None
        or _WORK.search(folded) is not None
    ):
        return None
    # What the question asks about goes after «:» (the provider keeps the plot's paragraphs that name it).
    focus = [
        word
        for word in dict.fromkeys(re.findall(r"[a-z]{4,}", folded))
        if word not in _QUESTION_WORDS and word not in previous.subject.split()
    ]
    if not focus:
        return previous
    return ReferenceLookup(previous.kind, previous.subject, previous.query + ": " + " ".join(focus[:4]), previous.language)


_QUESTION_WORDS = frozenset({
    "porque", "cual", "cuales", "cuando", "donde", "como", "quien", "quienes", "cuanto", "cuantos", "esta", "este",
    "estos", "estas", "eso", "esto", "hace", "hizo", "tiene", "tienen", "puede", "pasa", "paso", "what", "which",
    "when", "where", "does", "that", "this", "with", "have", "there", "about",
})


_NUMBER_WORDS = {
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "una": 1, "uno": 1, "one": 1,
}
_SERVINGS = re.compile(
    r"\b(?:para|pa|for|de)\s+(?P<count>\d{1,3}|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"
    r"(?:\s+(?:personas?|porciones?|comensales|people|persons|servings?|portions?|guests|invitados))?(?=\W|$)"
)


def servings_asked(text: str, prior_requests: Iterable[str] = ()) -> int | None:
    """How many people a recipe is asked for, in this request or the earlier one it continues («pa 6» → 6)."""

    for candidate in (text, *reversed([str(request) for request in prior_requests])):
        folded = fold(candidate)
        if _CULINARY.search(folded) is None and candidate is not text:
            continue
        found = _SERVINGS.search(folded)
        if found is None:
            continue
        raw = found.group("count")
        count = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
        # «de 1 kilo», «para una cena»: a count of people is said with its noun, or as digits after «para/for».
        explicit_noun = found.group(0).rstrip().split()[-1] != raw
        if 1 <= count <= 100 and (explicit_noun or (raw.isdigit() and found.group(0).split()[0] in {"para", "pa", "for"})):
            return count
    return None


# M83 (DEV-D v3o D-p27-t1 «Any good movies for me to watch?»): the decider answered it by talking in v3l and v3o and
# looked it up in v3m, with the same code (its LoRA, full3, flips on this request); the talk recommended «the latest
# sci-fi flick about time travel», a film that does not exist. Works to watch, read or hear, asked for with no title
# named, are recommended from what is looked up (or, with nothing pertinent read, from memory with its notice, D35),
# never from a recency the model cannot know.
_WORK_KIND = (
    r"(?:movies?|films?|series|shows?|tv\s+shows?|books?|novels?|songs?|albums?|podcasts?|documentar(?:y|ies)|"
    r"peliculas?|pelis?|libros?|novelas?|canciones|cancion|discos?|documentales?)"
)
_WORKS_RECOMMENDATION = re.compile(
    rf"\b(?:(?:any|some)\s+(?:good|nice|great|fun)\s+{_WORK_KIND}|"
    rf"recommend(?:\s+me)?\s+(?:(?:a|an|some|any)\s+)?(?:(?:good|nice|great|fun)\s+)?{_WORK_KIND}|"
    rf"(?:what|which)\s+{_WORK_KIND}\s+(?:should|could|can)\s+i\s+(?:watch|read|see|listen\s+to)|"
    rf"(?:recomiend\w*|recomendarme|recomendame)\s+(?:(?:un|una|unos|unas|algun|alguna|algunos|algunas)\s+)?"
    rf"(?:(?:buen|buena|buenos|buenas)\s+)?{_WORK_KIND}|"
    rf"(?:alguna?s?|unas?)\s+(?:buen[oa]s?\s+)?{_WORK_KIND}\s+(?:para|que)\s+(?:ver|leer|escuchar))\b"
)
# A work, a person or a service named («like Elijah Wood», «como Titanic», «on Netflix», a quoted title) or the person's
# own list make another request.
_WORK_NAMED = re.compile(
    r"\b(?:like|como|similar|parecid[oa]s?|with|con|by|de|del|starring|featuring|on|en|my|mi|mis)\s+\S|[\"«“]"
)


def works_recommendation(text: str) -> bool:
    """«Any good movies for me to watch?», «recomiéndame un buen libro»: works of a kind asked for, none named."""

    raw = str(text or "")
    folded = spelled_out(fold(raw))
    if _WORKS_RECOMMENDATION.search(folded) is None or _WORK_NAMED.search(folded) is not None:
        return False
    # A capitalized word past the first is a name (a title, an actor, a service).
    return not any(word[:1].isupper() for word in re.findall(r"[^\W\d_]+", raw)[1:] if word not in {"I", "TV"})


# M87 (DEV-D v3r D-p23-t2 «Look for a drama film.», D-p29-t2 «Search for scary movies.»): the answer from memory was
# asked for in the three forms at once (a recipe, a list, a work) and the model wrote all three — «Ingredients:» of a
# drama film, «A recipe for a spooky atmosphere» after ten horror films. The form is read here from what was asked.
_SEVERAL = re.compile(
    r"\b(?:movies|films|series|shows|books|novels|songs|albums|podcasts|documentaries|games|"
    r"peliculas|pelis|libros|novelas|canciones|discos|documentales|juegos|"
    r"list|lista|listado|top|examples|ejemplos|options|opciones|ideas|recommendations|recomendaciones)\b"
    r"|(?<![\d.,])\d{1,2}\s+(?:[a-z]+\s+)?[a-z]+s\b"
)


def memory_answer_form(text: str, prior_requests: Iterable[str] = ()) -> str:
    """The form of an answer said from memory: ``recipe`` for a dish, ``list`` for several things asked for (works of
    a kind in plural, a list, «los últimos 10 presidentes»), ``prose`` otherwise."""

    lookup = reference_lookup(text, prior_requests)
    folded = spelled_out(fold(text))
    if (lookup is not None and lookup.kind == "recipe") or _CULINARY.search(folded) is not None:
        return "recipe"
    if (lookup is not None and lookup.kind == "ranking") or _SEVERAL.search(folded) is not None:
        return "list"
    return "prose"


# M92 (D52; DEV-D v3u D-s111 «¿Cuál es la distancia de Barcelona a París?» → «de memoria… unos 1.100 kilómetros… 2 horas
# y media… entre 8 y 9 horas», D-w01-t3 «ya y pa 3 litros cuántas cucharaditas serían» → «de memoria… unas 600
# cucharaditas»): the answer from memory (D35) is kept for what is not a figure. When what is asked is a quantity, a
# distance, a duration, a date, a year or a count, memory does not say it (step 6 of goal v3: figures are looked up; if
# that is impossible, it is said). Folded, with the short forms spelled out.
_FIGURE_NOUN = (
    r"distancia|altura|poblacion|superficie|extension|longitud|peso|velocidad|temperatura|duracion|fecha|ano|edad|"
    r"precio|distance|height|population|area|length|weight|speed|temperature|duration|date|year|age|price"
)
_FIGURE_ASKED = re.compile(
    # «cuánto», «cuánta sal», «cuántas cucharaditas» (not «en cuanto», «cuanto antes», «unos cuantos»).
    r"(?<!\ben )(?<!\bpor )(?<!\bunos )(?<!\bunas )\bcuant[oa]s?\b(?!\s+(?:antes|mas|menos)\b)"
    r"|\bhow\s+(?:much|many|far|long|old|tall|big|high|deep|heavy|often|fast|large)\b"
    r"|\b(?:que|cual\s+es\s+(?:la|el)|cuales\s+son\s+(?:las|los)|a\s+que|what(?:'?s|\s+is|\s+are|\s+was)?\s+the|what)"
    rf"\s+(?:{_FIGURE_NOUN})\b"
    r"|\b(?:la|the)\s+(?:distancia|distance)\s+(?:de|entre|from|between)\b"
    r"|\ben\s+que\s+ano\b|\bin\s+(?:what|which)\s+year\b"
    r"|\bque\s+tan\s+(?:lejos|alt[oa]|grande|larg[oa]|profund[oa]|rapid[oa]|car[oa]|cerca|viej[oa])\b"
    r"|(?:^|[¿,;]\s*|\by\s+)cuando\s+(?:nacio|murio|fue|se\s+[a-z]+|ocurrio|empezo|comenzo|termino|salio|llego|paso)\b"
    r"|^\s*when\s+(?:was|were|did)\b|\bnumero\s+de\b|\bnumber\s+of\b"
)
# A taste or a wish is no figure of the world («¿cuánto te gusta?»).
_FIGURE_NOT_ASKED = re.compile(r"\bcuant[oa]s?\s+(?:te|me|le|nos|les)\s+(?:gusta|gustan|quiere|quieres|importa)\b")


def asks_a_figure(text: str) -> bool:
    """M92 (D52): what the request asks is a figure — a quantity, a distance, a duration, a date, a year or a count
    («¿cuál es la distancia de Barcelona a París?», «cuántas cucharaditas», «how many», «¿en qué año…?»)."""

    folded = spelled_out(fold(text))
    return _FIGURE_ASKED.search(folded) is not None and _FIGURE_NOT_ASKED.search(folded) is None


# M104 (D52, step 6 of goal v3; reserve v3z en13580 «how tall is mount everest» → «Mount Everest is 8,848.86 meters
# tall.», en13823 «how far away is the sun», en9930 «how long should i boil the egg» → «…seven to eight minutes»,
# en14316 «how large is alaska», es13823 «que tan lejos esta el sol»): a figure of the world asked of the talk was
# answered from memory, or refused twice as memory and recovered with no answer. A figure is looked up before it is
# said, so a figure of the world asked as such is a lookup, with the person's words as the query. Not a figure of the
# world: one computed from numbers the person gives (digits or words: «cuánto es doscientos por cuatro»), a conversion,
# the person's or BAXY's own things, this PC, the clock and the calendar of today, and a question that names nothing
# to look up («how much does it cost?»).
_NOT_THE_WORLDS_FIGURE = re.compile(
    r"\b(?:mi|mis|tu|tus|my|your|our|nuestr[oa]s?|you|te|contigo|conmigo|usted|baxy|olly|tengo|tenemos|"
    r"llevo|llevamos|i\s+have|i'?ve|do\s+i\s+have|have\s+i|am\s+i|"
    r"hoy|today|ahora|now|tonight|esta\s+noche|manana|tomorrow|ayer|yesterday|falta|faltan|quedan?|until|till|left|"
    r"hora|horas|time|reloj|clock|fecha|date|calendario|calendar|agenda|cumpleanos|birthday|"
    r"pc|computadora|computador|ordenador|equipo|computer|laptop|bateria|battery|ram|memoria|memory|disco|disk|cpu|"
    r"procesador|processor|gpu|almacenamiento|storage|espacio|space|volumen|volume|brillo|brightness|pantalla|screen|"
    r"archivos?|files?|carpetas?|folders?|ventanas?|windows|pestanas?|tabs?|apps?|aplicacion\w*|programas?|"
    r"procesos?|process\w*|descarga\w*|download\w*|instala\w*|install\w*|actualiza\w*|update\w*|wifi|internet|"
    r"notas?|notes?|recordatorios?|reminders?|alarmas?|alarms?|temporizador\w*|timers?|tareas?|tasks?|eventos?|"
    r"events?|reunion\w*|meetings?|citas?|appointments?|correos?|emails?|mails?|mensajes?|messages?|lista|list|"
    r"pedido|order|carrito|cart|cancion\w*|songs?|playlist|"
    # The weather has its own read («cuánto calor hace en Extremadura»).
    r"clima|weather|temperatura|temperature|lluvia|rain|calor|frio|fria|hot|cold|humedad|humidity|viento|wind|"
    # Someone's phone or address is a contact, never a figure of the world («el número de teléfono de Emilia», «el
    # número de mamá»); the person's family are their own.
    r"telefonos?|phones?|celular|movil|contactos?|contacts?|direccion|address|mama|papa|madre|padre|herman[oa]s?|"
    r"abuel[oa]s?|esposa|esposo|novi[oa]|jef[ae]|mom|dad|mother|father|sister|brother|wife|husband|boss)\b"
)
# The words of the frame that ask the figure, and what refers back without naming: none of them is what to look up.
_FIGURE_FRAME_WORDS = frozenset({
    "cuanto", "cuanta", "cuantos", "cuantas", "que", "cual", "cuales", "como", "cuando", "donde", "tan", "es", "son",
    "era", "fue", "fueron", "esta", "estan", "estamos", "hay", "habia", "tiene", "tienen", "mide", "miden", "pesa",
    "pesan", "cuesta", "cuestan", "costaria", "vale", "valen", "tarda", "tardan", "demora", "dura", "duran", "debo",
    "deberia", "puedo", "hace", "hacer", "eso", "esto", "esa", "ese", "ello", "numero", "nacio", "murio", "paso",
    "ocurrio", "empezo", "comenzo", "termino", "salio", "llego", "lejos", "alto", "alta", "grande", "largo", "larga",
    "profundo", "profunda", "rapido", "rapida", "caro", "cara", "cerca", "viejo", "vieja", "ano", "anos",
    "how", "much", "many", "far", "long", "old", "tall", "big", "high", "deep", "heavy", "often", "fast", "large",
    "what", "whats", "which", "when", "where", "who", "the", "and", "are", "was", "were", "been", "being", "does",
    "did", "should", "would", "could", "can", "will", "shall", "must", "need", "needs", "take", "takes", "cost",
    "costs", "weigh", "weighs", "measure", "get", "make", "made", "this", "that", "these", "those", "there", "away",
    "from", "with", "for", "about", "number", "year", "years", "per", "una", "uno", "unos", "unas", "los", "las",
    "del", "por", "para", "con", "sin", "entre", "desde", "hasta", "sobre", "the", "its", "it's", "one",
} | {word for word in re.findall(r"[a-z]+", _FIGURE_NOUN)})


_POINTS_BACK = re.compile(r"\b(?:eso|esto|that|this)\b")
# A rate of it: per metre, per person, each.
_PER_UNIT = re.compile(
    r"\b(?:por|per|cada|each|a)\s+(?:(?:un|una|el|la|a|an)\s+)?"
    r"(?:metros?|m2|kilos?|kg|gramos?|litros?|personas?|unidad(?:es)?|piezas?|horas?|dias?|semanas?|mes(?:es)?|anos?|"
    r"cuotas?|meters?|metres?|square|feet|foot|pounds?|lbs?|persons?|people|heads?|units?|pieces?|hours?|days?|weeks?|"
    r"months?|years?|items?)\b"
)


def rate_of_what_was_said(text: str, last_reply: str) -> bool:
    """M118 (D58, DEV-F F-w24-t4 «y eso cuanto sale por metro?» after «Pisos laminados para 42 m²: total 4.830.000
    pesos…» → looked up as «eso cuanto sale por metro»): a rate of what BAXY just said, pointed at, is computed from
    the numbers it said (D35: calculations are worked out, not searched); the decider's answer stands."""

    folded = spelled_out(fold(text))
    return (
        asks_a_figure(text)
        and _POINTS_BACK.search(folded) is not None
        and _PER_UNIT.search(folded) is not None
        and bool(numbers_in([spelled_out(fold(last_reply or ""))]))
    )


def figure_lookup(text: str, last_reply: str = "") -> ReferenceLookup | None:
    """A figure of the world the request asks (see above), with the query that looks it up; None otherwise."""

    folded = spelled_out(fold(text))
    if (
        not asks_a_figure(text)
        or asks_for_code(text)
        or conversion_asked(text) is not None
        or numbers_in([folded])
        or spoken_numbers_in([folded])
    ):
        return None
    # The address before the question («olly, how long…») is no word of it.
    clause = _kitchen_clause(folded)
    if _NOT_THE_WORLDS_FIGURE.search(clause) is not None or not any(len(word) >= 3 and word not in _FIGURE_FRAME_WORDS for word in re.findall(r"[a-z]+", clause)):
        return None
    if rate_of_what_was_said(text, last_reply):
        return None
    language = _language(folded, re.search(r"\b(?:how|what|when|which|is|are|the)\b", folded) is not None)
    return ReferenceLookup("figure", clause, clause, language)
