"""The vetoes of a mission final against its facts: a join never observed, a false past, a failure told as a
success, a containment, a change or a pick never made, an invented part of the day, and a word never observed.
"""

from __future__ import annotations

import re
from typing import Iterable

from . import operation_floor
from .semantic.missions import fold
from .cu_vocabulary import _BIDI_MARKS, _PARTS, _PLACE_GOAL, _WORD, _application_kinds, _language_words, _own_words


_JOIN_CLAIM = re.compile(
    r"\b(?:me\s+uni|me\s+he\s+unido|nos\s+unimos|joined|entre\s+(?:a|al)\s+(?:el\s+)?canal\s+de\s+voz|estoy\s+en\s+el\s+canal\s+de\s+voz|te\s+uni|ya\s+estoy\s+en\s+la\s+llamada|in\s+the\s+call)\b"
)
_JOIN_NEGATED = re.compile(
    r"\b(?:no|not|sin|didn't|did\s+not|without|todavia\s+no|aun\s+no|never|nunca)\s+(?:\w+\s+){0,2}(?:uni\w*|unir\w*|join\w*|entr\w*)\b"
)
_FALSE_PAST = re.compile(
    r"\b(?:ayer|anoche|antier|anteayer|antes\s+de\s+ayer|la\s+semana\s+pasada|el\s+otro\s+dia|hace\s+(?:un|unos|varios|dos|tres)\s+(?:dia|dias|semana|semanas|hora|horas)|"
    r"yesterday|last\s+night|last\s+week|the\s+other\s+day|days?\s+ago|hours?\s+ago|weeks?\s+ago)\b"
)
_SUCCESS_CLAIM = re.compile(
    r"\b(?:listo|hecho|logrado|conseguido|cumplido|done|achieved|completed|entre\s+a|llegue\s+a|ya\s+estas\s+en|ya\s+esta\s+en|quedo\s+activado|quedo\s+activo|active|activado)\b"
)


# Live 2026-10-07 (cu-r19): «Llegué al modo Oscuro.», «Llegué a la zona horaria y es …»: an arrival is told only at a
# place of the mission (a place goal, its application or its window), never at a value or an option the window shows.
_ARRIVAL = re.compile(
    r"\b(?:llegue|llegamos|i\s+reached|we\s+reached|i\s+got\s+to|i\s+made\s+it\s+to)\s+"
    r"(?:a\s+(?:la|las|los|el)\s+|al\s+|a\s+|the\s+)?([^.;:!?,]+)"
)
_ARRIVAL_FUNCTION = {"del", "los", "las", "the", "and", "seccion", "pagina", "pestana", "section", "page", "tab", "parte"}
_ARRIVAL_END = re.compile(r"\s+(?:y|e|and|donde|where|que|that|con|with|para|to)\s+.*$")


def _arrived_off_mission(folded_reply: str, seen: dict) -> bool:
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)]
    goals = goals or str(seen.get("goal") or "").split(_PARTS["chain"])
    places = {fold(found.group(1)) for goal in goals if isinstance(goal, str) and (found := _PLACE_GOAL.match(goal.strip()))}
    places |= {fold(seen.get(key)) for key in ("application", "windowTitle") if isinstance(seen.get(key), str)}
    # A place told short («la sección de Bluetooth» for «Bluetooth y dispositivos») shares a word with it.
    words = {word for place in places for word in re.findall(r"[a-z0-9]+", place) if len(word) >= 3} - _ARRIVAL_FUNCTION
    for found in _ARRIVAL.finditer(folded_reply):
        head = set(re.findall(r"[a-z0-9]+", _ARRIVAL_END.sub("", found.group(1)))) - _ARRIVAL_FUNCTION
        if head and not head & words:
            return True
    return False


def mission_defect(folded_reply: str, seen: dict) -> str | None:
    """Vetos of a mission final: a join never observed, a false past time, a
    failed mission told as a success (contract §4.5)."""

    if _FALSE_PAST.search(folded_reply):
        return "extra_claim"
    claims_join = _JOIN_CLAIM.search(folded_reply) is not None and _JOIN_NEGATED.search(folded_reply) is None
    if claims_join and seen.get("joined") is not True:
        return "joined_claimed"
    if seen.get("joined") is True and _JOIN_NEGATED.search(folded_reply) is not None:
        return "joined_claimed"
    if seen.get("reached") is not True and _SUCCESS_CLAIM.search(folded_reply) and not re.search(r"\b(?:no|not)\b", folded_reply):
        return "reversed_polarity"
    if _invented_meridiem(folded_reply, seen):
        return "extra_claim"
    if _arrived_off_mission(folded_reply, seen):
        return "extra_claim"
    shade = seen.get("chosenShade")
    if isinstance(shade, dict) and fold(shade.get("chosen")) not in folded_reply:
        # «Listo, elegí el azul» when the palette had no «Azul» and «Añil» was clicked: the swatch is named.
        return "shade_unnamed"
    if _only_went_somewhere(seen) and _claims_a_change(folded_reply, seen):
        return "extra_claim"
    if _claims_a_containment(folded_reply, seen):
        return "extra_claim"
    if _NEW_STATE_CLAIM.search(folded_reply) and not _toggles_something(seen):
        return "extra_claim"
    if _cause_omitted(folded_reply, seen):
        return "cause_omitted"
    return None


def _cause_omitted(folded_reply: str, seen: dict) -> bool:
    """v3 limits (live v3-72: «el Administrador de tareas no me dejó entrar»): a stop whose cause is a limit of the
    PC the person can act on (an administrator's window, a gate screen) is said with that cause. The words that name
    it are data (operation_floor.v1.json «computerUse.causeWords», prefixes); a gate also counts by a word of the text
    it showed."""

    stopped = str(seen.get("stoppedBy") or "")
    prefixes = operation_floor.floor_data()["computerUse"]["causeWords"].get(stopped)
    if seen.get("reached") is True or not prefixes:
        return False
    # The application's own name says no cause («Administrador de tareas» names Task Manager, not its rights).
    told = folded_reply
    for name in (seen.get("application"), seen.get("windowTitle")):
        if isinstance(name, str) and fold(name).strip():
            told = told.replace(fold(name).strip(), " ")
    words = set(_WORD.findall(told))
    gate_words = {word for word in _WORD.findall(fold(seen.get("gate"))) if len(word) >= 5}
    return not (words & gate_words) and not any(word.startswith(tuple(prefixes)) for word in words)


def _kinds_of(seen: dict) -> set[str]:
    """The words that name what the mission's applications hold («juegos» in Steam, «disco» in the File Explorer)."""

    kinds = _application_kinds()
    subgoals = [item for item in seen.get("subgoals") or () if isinstance(item, dict)]
    names = [seen.get("application"), *(item.get("application") for item in subgoals)]
    return {word for name in names if isinstance(name, str) for word in kinds.get(fold(name).strip(), ())}


# cu-r17 (voice audit 2026-10-07: «Pegué el texto» from «pegalo», «Cerré la ventana» from «cerrala»): the stem match
# cannot reach a short preterite from the request's imperative, so each imperative or infinitive of the request also
# grounds its own first-person preterite: «copiá» → «copié», «pegalo» → «pegué», «buscá» → «busqué», «abrí» → «abrí»,
# «mové» → «moví», «guardar» → «guardé».
_ENCLITIC = re.compile(r"(?:selos|selas|selo|sela|los|las|les|lo|la|le|me|nos)$")


def _preterites(word: str) -> set[str]:
    forms: set[str] = set()
    bare = word[:-1] if word.endswith("r") and len(word) > 3 else word
    stripped = _ENCLITIC.sub("", bare)
    for base in {bare, stripped}:
        if len(base) < 3:
            continue
        if base.endswith("a"):
            stem = base[:-1]
            if stem.endswith("c"):
                stem = stem[:-1] + "qu"
            elif stem.endswith("g"):
                stem = stem[:-1] + "gu"
            elif stem.endswith("z"):
                stem = stem[:-1] + "c"
            forms.add(stem + "e")
        elif base.endswith(("e", "i")):
            forms.add(base[:-1] + "i")
    return forms


def _reply_is_english(words: list[str]) -> bool:
    spanish, english, _ = _language_words()
    return sum(word in english for word in words) > sum(word in spanish for word in words)


def _fact_strings(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _fact_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _fact_strings(item)


def _folded_words(value: object) -> list[str]:
    return _WORD.findall(fold(value))


def ungrounded_word(folded_reply: str, seen: dict, said: str = "") -> str | None:
    """The first word of a mission final that neither the facts (seen, the person's words) nor BAXY's own vocabulary
    hold; a word sharing its first ``stemLength`` letters with a fact word is the same word in another form
    («calculé» from «calculá»), the preterite of a request verb is BAXY's own act («pegué» from «pegalo»), and an
    English reply may name a Spanish screen state in English («paired» for «Emparejado»). None when every word is
    grounded."""

    own, stem_length = _own_words()
    facts: set[str] = set()
    for text in (*_fact_strings(seen), said):
        facts.update(_folded_words(text))
    stems = {word[:stem_length] for word in facts if len(word) >= stem_length}
    # cu-r18 (live v2-c6: a confirmed send answered «sí», so «Envié «prueba BAXY C6» a Ron92.» had no «mandalo» to come
    # from): the mission's own goal and each subgoal's goal («…; luego enviar») ground their preterites as well.
    goals = [seen.get("goal"), *(item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict))]
    verbs = [word for text in (said, *(goal for goal in goals if isinstance(goal, str))) for word in _folded_words(text)]
    derived = {form for word in verbs for form in _preterites(word)} | _kinds_of(seen)
    reply = _folded_words(folded_reply)
    if _reply_is_english(reply):
        # cu-r17 (x4 «Windows (light)» from «Windows (claro)»): an English reply names a Spanish screen state in English.
        states = _language_words()[2]
        derived.update(said_en for word in facts for said_en in states.get(word, ()))
    for word in reply:
        if word in own or word in facts or word in derived:
            continue
        if len(word) >= stem_length and word[:stem_length] in stems:
            continue
        return word
    return None


# Live 2026-10-07 (v2-a2 «en el Reloj andá a Temporizador y después en Configuración andá a Aplicaciones» → «Estoy en
# Configuración de Aplicaciones dentro de la app Reloj.»; v2-a4 «… andá a Documentos y después a Descargas» → «Estoy en
# la carpeta de Descargas dentro de Documentos»): «X dentro de Y» puts a place of the mission inside another place or
# another application. The facts only say which application each place was reached in: X inside its own application
# passes, X inside anything else of the mission was never observed.
_CONTAINER = re.compile(r"\s+(?:dentro\s+del?|adentro\s+del?|inside(?:\s+of)?|within|in|en)\s+")
_CONTAINER_FILLER = re.compile(
    r"^(?:(?:el|la|los|las|the)\s+)?(?:(?:app|aplicacion|carpeta|ventana|seccion|pestana|pagina|folder|application|"
    r"window|section|tab|page)\s+(?:(?:de|del|of)\s+)?(?:(?:el|la|los|las|the)\s+)?)?"
)


def _mission_places(seen: dict) -> dict[str, str]:
    """Each place a goal «ir a X» reached, folded, with the folded application it was reached in."""

    app = fold(seen.get("application")) if isinstance(seen.get("application"), str) else ""
    parts = [
        (item.get("goal"), item.get("application")) for item in seen.get("subgoals") or () if isinstance(item, dict)
    ] or [(part, None) for part in str(seen.get("goal") or "").split(";")]
    places: dict[str, str] = {}
    for goal, where in parts:
        found = _PLACE_GOAL.match(re.sub(r"^\s*luego\s+", "", goal.strip())) if isinstance(goal, str) else None
        name = fold(_BIDI_MARKS.sub("", found.group(1))).strip(" .") if found is not None else ""
        if name:
            places[name] = fold(where) if isinstance(where, str) and where.strip() else app
    return places


def _claims_a_containment(folded_reply: str, seen: dict) -> bool:
    places = _mission_places(seen)
    apps = {
        fold(name) for name in (seen.get("application"), *(
            item.get("application") for item in seen.get("subgoals") or () if isinstance(item, dict)
        )) if isinstance(name, str) and name.strip()
    }
    names = sorted({*places, *apps} - {""}, key=len, reverse=True)
    if len(names) < 2:
        return False
    for found in _CONTAINER.finditer(folded_reply):
        before, after = folded_reply[:found.start()], _CONTAINER_FILLER.sub("", folded_reply[found.end():])
        outer = next((name for name in names if re.match(rf"{re.escape(name)}\b", after)), None)
        inner = next((name for name in names if re.search(rf"\b{re.escape(name)}$", before)), None)
        if outer is None or inner is None or inner == outer:
            continue
        if outer in apps and places.get(inner) == outer:
            continue
        return True
    return False


# Live 2026-10-07 (v2-a12 «en Configuración buscá Bluetooth» → «Ya busqué Bluetooth en Configuración y ahora está
# activado.»): a state said as the result of «ahora» tells a switch the mission never flipped. «Bluetooth está activado»
# describing the window stays allowed; only a mission whose goals switch something may say what it is «ahora».
_STATE_WORD = r"(?:activad[oa]s?|desactivad[oa]s?|encendid[oa]s?|apagad[oa]s?|prendid[oa]s?|activ[oa]s?|inactiv[oa]s?)"
_NEW_STATE_CLAIM = re.compile(
    rf"\bahora\s+(?:\w+\s+){{0,3}}?(?:ya\s+)?(?:esta|estan|queda|quedan|quedo|quedaron|sigue)\s+(?:ahora\s+)?{_STATE_WORD}\b|"
    rf"\b(?:esta|estan|queda|quedan|quedo|quedaron)\s+ahora\s+{_STATE_WORD}\b|"
    r"\bnow\s+(?:\w+\s+){0,3}?(?:is|it's|are|they're)\s+(?:now\s+)?(?:on|off|enabled|disabled|active|inactive)\b|"
    r"\b(?:is|it's|are|they're)\s+now\s+(?:on|off|enabled|disabled|active|inactive)\b"
)
_TOGGLE_GOAL = re.compile(
    r"^(?:activar|desactivar|encender|apagar|prender|alternar|cambiar|poner|hacer\s+clic|turn|enable|disable|toggle|"
    r"switch|click)\b"
)


def _toggles_something(seen: dict) -> bool:
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] + [seen.get("goal")]
    return any(
        _TOGGLE_GOAL.match(re.sub(r"^\s*luego\s+", "", fold(part).strip()))
        for goal in goals if isinstance(goal, str) for part in goal.split(";")
    )


_CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
_MERIDIEM = re.compile(
    r"(?<!\d)\d{1,2}:\d{2}(?!\d)\s*(?:hs?\s+)?(?:de\s+la\s+|del\s+|en\s+la\s+|por\s+la\s+|in\s+the\s+)?"
    r"(manana|tarde|noche|madrugada|mediodia|morning|afternoon|evening|night|a\.?\s?m\b\.?|p\.?\s?m\b\.?)"
)


def screen_texts(seen: dict) -> list[str]:
    """Every text the window showed at the end (title, fields, numbers, lines) and the evidence, without bidi marks."""

    screen = seen.get("screen") if isinstance(seen.get("screen"), dict) else {}
    texts: list[object] = [screen.get("title"), seen.get("evidence"), seen.get("windowTitle")]
    for key in ("numbers", "lines"):
        texts.extend(screen.get(key) if isinstance(screen.get(key), list) else ())
    for item in screen.get("values") if isinstance(screen.get("values"), list) else ():
        if isinstance(item, dict):
            texts.extend((item.get("name"), item.get("value")))
    return [_BIDI_MARKS.sub("", text) for text in texts if isinstance(text, str) and text.strip()]


def screen_clocks(seen: dict) -> frozenset[str]:
    """The «HH:MM» clocks the window wrote: a clock app's time, an alarm's, a call's length."""

    return frozenset(
        f"{int(hour):02d}:{minute}" for text in screen_texts(seen) for hour, minute in _CLOCK.findall(text)
    )


def _invented_meridiem(folded_reply: str, seen: dict) -> bool:
    """«las 7:58 de la tarde» over a window that writes only «7:58»: the part of the day is a guess."""

    shown = fold(" ".join(screen_texts(seen)))
    for found in _MERIDIEM.finditer(folded_reply):
        word = re.sub(r"[\s.]", "", found.group(1))
        if not re.search(rf"\b{word[0]}\.?\s?{word[1:]}\b" if word in {"am", "pm"} else rf"\b{word}\b", shown):
            return True
    return False


# A goal «ir a X» only went to X (_NO_META): a first-person change said beside it was never done nor observed.
_GO_GOAL = re.compile(r"^ir\s+a\b")
_CHANGE_CLAIM = re.compile(
    r"\b(?:puse|configure|cree|programe|cambie|ajuste|encendi|apague|inicie|borre|elimine|agregue|anadi|guarde|"
    r"(?:des)?active\s+(?:el|la|los|las|lo|un|una)|"
    r"pondre|configurare|creare|programare|cambiare|ajustare|encendere|apagare|borrare|eliminare|agregare|anadire|"
    r"guardare|(?:des)?activare|"
    r"voy\s+a\s+(?:poner|configurar|crear|programar|cambiar|ajustar|encender|apagar|borrar|eliminar|agregar|anadir|"
    r"guardar|(?:des)?activar)|"
    r"ahora\s+(?:pongo|configuro|programo|cambio|ajusto|enciendo|apago|borro|elimino|agrego|anado|guardo|(?:des)?activo)|"
    r"i(?:\s+will|'ll|\s+am|'m)\s+(?:set|create|start|turn|change|schedule|enable|disable|delete|add|save|setting|"
    r"creating|starting|turning|changing|scheduling|enabling|disabling|deleting|adding|saving)|"
    r"i(?:\s+have|'ve)?\s+(?:set|created|started|turned|changed|scheduled|enabled|disabled|deleted|added|saved))\b"
)
_CHANGE_DENIED = re.compile(r"\b(?:no|nunca|ni|not|never|didn'?t)\s+(?:\w+\s+)?$")


def _only_went_somewhere(seen: dict) -> bool:
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] or [seen.get("goal")]
    return all(isinstance(goal, str) and _GO_GOAL.match(fold(goal)) for goal in goals)


def _claims_a_change(folded_reply: str, seen: dict) -> bool:
    return any(
        _CHANGE_DENIED.search(folded_reply[max(0, found.start() - 20):found.start()]) is None
        and _PICK_OFFERED.search(folded_reply[max(0, found.start() - 40):found.start()]) is None
        for found in _CHANGE_CLAIM.finditer(folded_reply)
    ) or _claims_a_pick(folded_reply, seen)


# Live 2026-10-07 (cu-r8, «en el Reloj andá a Alarma» → «Ya elegí la alarma de las 7:00»): a navigation selects the
# place it goes to (the tab «Alarma»), nothing inside it. A first-person pick is what the mission went to or nothing:
# its object must be a place the goals named, a name the steps clicked or a value the window marked, optionally «en»
# the application; «elegí el lápiz» on a mission that picked it is not a navigation and is not judged here.
# Live v6 («en Word andá a la pestaña Diseño» → «Ya estoy en la pestaña Diseño y ahora selecciono Títulos.»): an act
# said in the present or the future beside the arrival is as invented as one in the past.
_PICK_CLAIM = re.compile(
    r"\b(?:elegi|escogi|seleccione|marque|opte\s+por|elijo|escojo|selecciono|elegire|escogere|seleccionare|marcare|"
    r"voy\s+a\s+(?:elegir|escoger|seleccionar|marcar)|"
    r"i(?:\s+have|'ve|\s+will|'ll|\s+am|'m)?\s+(?:chose|chosen|selected|picked|ticked|choose|select|pick|"
    r"choosing|selecting|picking))\s+"
    r"(?P<object>[^.,;:!?\n]+?)(?=\s+(?:y|e|pero|and|but|que|that|which)\b|[.,;:!?\n]|$)"
)
# «Si quieres, selecciono Títulos» offers the act; it does not claim it.
_PICK_OFFERED = re.compile(r"\b(?:si\s+quieres|si\s+deseas|puedo|if\s+you\s+(?:want|like)|i\s+can|want\s+me\s+to)\b[^.;]{0,20}$")
_PICK_HEAD = re.compile(
    r"^(?:(?:el|la|los|las|lo|the|a|an)\s+)?(?:(?:pestana|seccion|opcion|pagina|vista|apartado|tab|section|option|"
    r"page|view)\s+(?:(?:de|del|of)\s+)?(?:(?:el|la|los|las|the)\s+)?)?"
)
_PICK_WHERE = re.compile(
    r"^(?:en|in|on|de|del|of)\s+(?:(?:el|la|the)\s+)?(?:(?:aplicacion|app|ventana|window)\s+(?:(?:de|del|of)\s+)?)?(?P<app>.+)$"
)
_QUOTED = re.compile(r"«([^«»]+)»")


def _picked_places(seen: dict) -> set[str]:
    # What the goals named and what the steps clicked; a value the window marks without this mission clicking it is
    # not its pick (live v6: Word's «Títulos» style, selected by default, said as «ahora selecciono Títulos»).
    goals = [item.get("goal") for item in seen.get("subgoals") or () if isinstance(item, dict)] + [seen.get("goal")]
    names = [
        *(found.group(1) for goal in goals if isinstance(goal, str) for part in goal.split(";")
          if (found := _PLACE_GOAL.match(re.sub(r"^\s*luego\s+", "", part.strip()))) is not None),
        *(quoted for step in seen.get("stepsDone") or () if isinstance(step, str) for quoted in _QUOTED.findall(step)),
    ]
    return {fold(_BIDI_MARKS.sub("", name)).strip(" .") for name in names if isinstance(name, str) and name.strip()}


def _claims_a_pick(folded_reply: str, seen: dict) -> bool:
    places = _picked_places(seen)
    apps = {fold(name) for name in (seen.get("application"), seen.get("windowTitle")) if isinstance(name, str)}
    for found in _PICK_CLAIM.finditer(folded_reply):
        before = folded_reply[max(0, found.start() - 40):found.start()]
        if _CHANGE_DENIED.search(before[-20:]) is not None or _PICK_OFFERED.search(before) is not None:
            continue
        picked = _PICK_HEAD.sub("", fold(found.group("object").replace("«", " ").replace("»", " "))).strip()
        if picked in places:
            continue
        place = next((name for name in places if name and picked.startswith(name + " ")), None)
        where = _PICK_WHERE.match(picked[len(place) + 1:]) if place is not None else None
        if where is None or fold(where.group("app")) not in apps:
            return True
    return False
