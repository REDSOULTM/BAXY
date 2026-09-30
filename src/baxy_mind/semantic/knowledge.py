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
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .conversation import asks_for_code
from .normalize import fold, spelled_out

__all__ = ["ReferenceLookup", "memory_answer_form", "reference_lookup", "servings_asked"]


@dataclass(frozen=True)
class ReferenceLookup:
    """A named referent to look up: ``kind`` is ``recipe`` or ``plot``; ``query`` is what ``web.search`` is asked."""

    kind: str
    subject: str
    query: str
    language: str


# The kitchen said in the request: without it «cómo hacer una cometa» is an explanation, not a recipe.
_CULINARY_ES = r"recetas?|ingredientes?|cocina|cocinar|cocino|cocinando|hornear|horneo|horno"
_CULINARY_EN = r"recipes?|ingredients?|kitchen|cook|cooking|bake|baking|oven"
_CULINARY = re.compile(rf"\b(?:{_CULINARY_ES}|{_CULINARY_EN})\b")
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
    if _CULINARY.search(folded) is None:
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


def _direct(text: str) -> ReferenceLookup | None:
    folded = spelled_out(fold(text))
    return _recipe(folded) or _plot(text, folded) or _ranking(folded)


def reference_lookup(text: str, prior_requests: Iterable[str] = ()) -> ReferenceLookup | None:
    """The named dish or work this request asks about, to be looked up before anything is said about it.

    ``prior_requests`` are the person's earlier messages, oldest first: a question about the story right after a
    work's lookup, naming no other work, looks that same work up again (its plot answers the question).
    """

    # M56 (v3c-final F-w14-t1 «escribeme un query de sql q me saque los users activos del ultimo mes»): code asked
    # for is written by the model; nothing in it is a dish, a work or a ranking to look up.
    if asks_for_code(text):
        return None
    direct = _direct(text)
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
