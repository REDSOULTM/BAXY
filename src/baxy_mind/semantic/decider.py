"""The contextual decider: the model reads the whole conversation and the catalog and decides the turn.

Fase 3.5b «comprensión natural» (F2–F3, 2026-09-25): the model deciding alone, with the conversation as it is,
the catalog of every operation and the owner's rules, decided better than the readers, the shortlist, the native
selector and the gates put together (DEV-B 204/253 against 182/253; follow-ups that depend on the previous turn
61/66 against 40/66). It first restates the last message as a complete request (what the arguments step reads),
then decides: operations of the catalog, one short question, conversation, or a limit said plainly. It proposes;
the kernel still authorizes and the provider executes (invariant 1).

This module is the reading: the policy, the catalog as the decider sees it and the closed output. The model call
is ``llm.LlmRuntime.decide_in_context``.
"""

from __future__ import annotations

import functools
import json
import pathlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
from typing import Any, Iterable

from .grammar import _CARDINAL_WORDS, spoken_cardinal
from .normalize import fold, fold_in_place, spelled_out
from .quantities import _UNITS, measures
from .temporal import _SPOKEN_DATE, _TOMORROW, _WEEKDAYS, MONTH_NUMBERS, spoken_clocks, taken_back_time

DECISIONS = ("action", "clarify", "talk", "limit")

# The owner's rules (00_IDENTIDAD, REGLAS_ORO of the comprensión sets): what is public is looked up, what is the
# person's is never looked up, a complete request is not asked again, a relative amount without a number is asked,
# a limit is said plainly, a missing personal datum is asked.
POLICY = (
    "Eres el decisor de BAXY, un asistente tipo Jarvis que vive en un PC con Windows. Lees la conversación y "
    "decides qué hacer con el ÚLTIMO mensaje de la persona. No ejecutas nada: sólo decides.\n\n"
    "Decisiones posibles:\n"
    "- \"action\": ejecutar una o varias operaciones del catálogo (lista abajo) que cubren lo pedido.\n"
    "- \"clarify\": hacer UNA pregunta corta porque falta de verdad algo que cambia el resultado.\n"
    "- \"talk\": contestar hablando, sin tocar el PC: conocimiento estable, charla, escribir contenido (código, "
    "recetas, listas, cuentos, traducciones), cálculos y conversiones, consejos, hablar de ti mismo, agradecer.\n"
    "- \"limit\": decir en llano que eso no lo haces (no está en el catálogo).\n\n"
    "Reglas:\n"
    "1. Lo público se busca: lo que cambia o no se sabe de memoria con seguridad (clima, noticias, deportes, "
    "precios, dólar, horarios, estrenos, datos de una persona, empresa o lugar concretos, opiniones sobre una obra) "
    "→ action con web.search (o weather.current para el clima, web.news.headlines para titulares). Lo estable "
    "(definiciones, cómo se hace algo, matemáticas, traducir, convertir unidades) → talk. Si la persona pide "
    "buscar o investigar algo público, es action con web.search.\n"
    "2. Lo propio no se busca en la web: datos de la persona (sus notas, recordatorios, alarmas, tareas, agenda, "
    "archivos, lo que suena en su PC), preguntas sobre ti o sobre lo que acabas de decir → la operación que lo lee, "
    "o talk, o clarify.\n"
    "3. Lo completo no se repregunta: si el mensaje trae lo necesario, action. Un valor por defecto razonable (el "
    "clima de aquí, algo de música) no es una duda.\n"
    "4. Cantidad relativa sin número («súbele un poco», «baja el brillo», «más fuerte») → clarify (cuánto). Con "
    "número o nivel → action.\n"
    "5. Vives en un PC: no controlas luces ni aparatos de la casa, no haces llamadas telefónicas ni SMS, no pides "
    "comida, taxis, compras ni reservas, no manejas el móvil ni relojes → limit. Lo que una operación del catálogo "
    "sí hace (por ejemplo mensajes por una app del PC, reproducir en un servicio de streaming, abrir una app) se "
    "hace con esa operación.\n"
    "6. Si falta un dato de la persona («¿llueve donde vive mi hermana?») → clarify.\n"
    "7. Erratas, sin tildes, dictado sin puntuación y spanglish se entienden como la persona quiso decir.\n"
    "8. Un mensaje que depende de lo anterior («¿y en Santiago?», «ahora en javascript», «20 minutos antes de "
    "eso», «súbele otro poco», «esa no, otra», «sí, dale», «10») se decide con la conversación: la misma operación "
    "con el valor nuevo, o talk que reusa lo que respondiste. Si acabas de preguntar algo y la persona contesta, "
    "completa ese pedido.\n"
    "9. Charla, gracias, quejas y reacciones → talk.\n\n"
    "Catálogo (operación: qué hace):\n"
)

FORMAT = (
    "\nResponde sólo con JSON: {\"request\": el último pedido reescrito como pedido completo y autónomo con lo que "
    "aporta la conversación, en el idioma de la persona, \"decision\": ..., \"operations\": [...] (vacía si no es "
    "action), \"question\": la pregunta corta si es clarify, si no \"\"}."
)

# Fase 3.5b M42 (D33): the decision and the values the person already gave travel in one output. Each catalog line
# names the operation's fields (identifiers left out: the kernel resolves them), so the arguments step no longer asks
# for a time, a name or a folder the message or the conversation gave (spent FINAL: 12 actions asked again).
FORMAT_WITH_ARGUMENTS = (
    "\nResponde sólo con JSON: {\"request\": el último pedido reescrito como pedido completo y autónomo con lo que "
    "aporta la conversación, en el idioma de la persona, \"decision\": ..., \"operations\": [...] (vacía si no es "
    "action), \"arguments\": {operación: {campo: valor}} con los valores que el mensaje o la conversación YA dan "
    "para los campos entre paréntesis (horas, duraciones, nombres, carpetas, títulos, textos; nunca inventes uno; "
    "{} si no hay), \"question\": la pregunta corta si es clarify, si no \"\"}."
)

FAMILY_TITLES = {
    "app": "aplicaciones", "audio": "sonido", "backup": "copias", "bluetooth": "bluetooth", "browser": "navegador",
    "calculator": "calculadora", "calendar": "agenda", "capture": "capturas", "clipboard": "portapapeles",
    "display": "pantalla", "email": "correo", "filesystem": "archivos", "game": "juegos", "input": "teclado y clics",
    "media": "música y video", "memory": "memoria privada", "message": "mensajes", "network": "red", "note": "notas",
    "notification": "alarmas y recordatorios", "ocr": "leer texto en pantalla", "office": "documentos",
    "package": "programas", "peripheral": "periféricos", "reminder": "recordatorios", "routine": "rutinas",
    "streaming": "streaming", "system": "sistema", "task": "tareas y listas", "vision": "describir la pantalla",
    "weather": "clima", "web": "web", "wifi": "wifi", "window": "ventanas",
}

# Model turns kept from the conversation, and characters per turn: the prompt stays inside one server slot.
HISTORY_TURNS = 4
HISTORY_CHARACTERS = 1500
# M49: each value the decider writes is bounded; one that reaches the bound was cut by the grammar (M67).
ARGUMENT_VALUE_CHARACTERS = 120


@dataclass(frozen=True, slots=True)
class ContextDecision:
    request: str
    decision: str
    operations: tuple[str, ...]
    question: str
    arguments: tuple[tuple[str, Any], ...] = ()


_PLAIN_CATALOG = pathlib.Path(__file__).resolve().parents[1] / "data" / "decider_catalog.es.v1.json"


@functools.cache
def plain_descriptions() -> dict[str, str]:
    """One line per operation in the words a person uses (F4 M2).

    The technical description confused siblings («sesión SMTC» for pause and next, absolute and relative
    volume, opening an app and playing inside it). Written in a clean room from the technical catalog only;
    an operation it lacks keeps its own first sentence.
    """

    try:
        data = json.loads(_PLAIN_CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    operations = data.get("operations") if isinstance(data, dict) else None
    return {str(k): str(v) for k, v in operations.items()} if isinstance(operations, dict) else {}


def catalog_line(name: str, description: str) -> str:
    """What the decider reads of one operation: its line in the person's words, or its description's first sentence."""

    return plain_descriptions().get(name) or description.split(". ")[0].rstrip(".")


def catalog_prompt(
    tools: Iterable[tuple[str, str]],
    signatures: dict[str, tuple[str, ...]] | None = None,
) -> str:
    """The system prompt for ``(name, description)`` operations, the same bytes for the same catalog.

    With ``signatures`` (M42) each line names the operation's argument fields and the output asks for their values.
    """

    families: dict[str, list[str]] = {}
    for name, description in sorted(tools):
        first = catalog_line(name, description)
        fields = (signatures or {}).get(name) or ()
        signature = f"({', '.join(fields)})" if fields else ""
        families.setdefault(name.split(".", 1)[0], []).append(f"- {name}{signature}: {first[:140]}")
    catalog = "\n".join(f"[{FAMILY_TITLES.get(f, f)}]\n" + "\n".join(lines) for f, lines in families.items())
    return POLICY + catalog + (FORMAT if signatures is None else FORMAT_WITH_ARGUMENTS)


def argument_signature(schema: dict[str, Any]) -> tuple[str, ...]:
    """The fields the decider may fill for one operation: optional ones marked «?», identifiers left out."""

    properties = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(properties, dict):
        return ()
    required = set(schema.get("required") or ())
    return tuple(
        name + ("" if name in required else "?")
        for name in properties
        if isinstance(name, str) and not (name.endswith("Id") and name != "appId")
    )


def response_schema(operations: Iterable[str], *, with_arguments: bool = False) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "request": {"type": "string", "maxLength": 300},
        "decision": {"type": "string", "enum": list(DECISIONS)},
        "operations": {"type": "array", "items": {"type": "string", "enum": sorted(operations)}, "maxItems": 3},
        "question": {"type": "string", "maxLength": 200},
    }
    closed = {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}
    if not with_arguments:
        return closed
    # M49 (lat49): the values are decoded only when the decision is an action, each one bounded; a talk, a question
    # or a limit writes no arguments at all (M42 as first shipped cost +0.8 s p50 on every turn in the app).
    other = {
        **closed,
        "properties": {
            **properties,
            "decision": {"type": "string", "enum": [d for d in DECISIONS if d != "action"]},
            "operations": {"type": "array", "items": {"type": "string"}, "maxItems": 0},
        },
    }
    action_properties = {
        "request": properties["request"],
        "decision": {"type": "string", "enum": ["action"]},
        "operations": properties["operations"],
        "arguments": {
            "type": "object",
            "additionalProperties": {"type": ["string", "number", "boolean"], "maxLength": ARGUMENT_VALUE_CHARACTERS},
        },
        "question": properties["question"],
    }
    action = {**closed, "properties": action_properties, "required": list(action_properties)}
    return {"anyOf": [action, other]}


def messages(system: str, text: str, history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """The conversation as it was, without the current message when the history already ends with it.

    M125 (D58; window v4i-devF F-s002: the app's decider read 42 prompt tokens where the isolated one read 23, the 19
    of «Hola, soy BAXY. ¿En qué puedo ayudarte hoy?»): what BAXY says before the person has said anything (the
    welcome of every new conversation, a start-up notice) is not a turn of the conversation, and the decider was
    trained and measured without it. It came first in the history of every first and second turn.
    """

    prior = [turn for turn in (history or []) if turn.get("role") in {"user", "assistant"} and turn.get("content")]
    prior = prior[next((index for index, turn in enumerate(prior) if turn.get("role") == "user"), len(prior)):]
    if prior and prior[-1].get("role") == "user" and prior[-1].get("content") == text:
        prior = prior[:-1]
    prior = prior[-HISTORY_TURNS:]
    return [
        {"role": "system", "content": system},
        *({"role": turn["role"], "content": str(turn["content"])[:HISTORY_CHARACTERS]} for turn in prior),
        {"role": "user", "content": text},
    ]


def parse(content: str, operations: Iterable[str]) -> ContextDecision:
    """The decision the model wrote; an action whose operations are not served is not an action."""

    raw = json.loads(content)
    served = set(operations)
    decision = raw.get("decision")
    if decision not in DECISIONS:
        raise ValueError(f"decisión desconocida: {decision!r}")
    chosen = tuple(dict.fromkeys(op for op in raw.get("operations") or [] if op in served))
    if decision == "action" and not chosen:
        raise ValueError("una acción sin operaciones del catálogo")
    return ContextDecision(
        request=" ".join(str(raw.get("request") or "").split()),
        decision=decision,
        operations=chosen if decision == "action" else (),
        question=" ".join(str(raw.get("question") or "").split()),
        arguments=_decided_arguments(raw.get("arguments"), chosen) if decision == "action" else (),
    )


def _decided_arguments(value: Any, operations: tuple[str, ...]) -> tuple[tuple[str, Any], ...]:
    """The scalar values the decider read, flat: the model writes them keyed by operation or not."""

    if not isinstance(value, dict):
        return ()
    flat: dict[str, Any] = {}
    for key, item in value.items():
        if key in operations and isinstance(item, dict):
            for field, inner in item.items():
                flat.setdefault(str(field), inner)
        elif isinstance(item, (str, int, float, bool)):
            flat.setdefault(str(key), item)
    return tuple((name, item) for name, item in flat.items() if isinstance(item, (str, int, float, bool)))


# --- Fidelity of the restatement (Fase 3.5b M64) ---------------------------------------------------------------------
# v3d-final and v3f-final F-w01-t4 «¿y cuánto sale más o menos ese pisco en el líder? el mistral de 35» was restated
# «¿Cuánto sale el pisco Mistral de 350 ml en el líder?», and «350 ml» travelled as the objective to the search and to
# the reply; F-s054 «Estará storming mañana» became «…mañana en Santiago?» and the weather of a city nobody named was
# read; F-w05-t3 «apúntamelo como recordatorio un mes antes» got «el 1 de octubre», a date nobody gave. The restatement
# joins the message with the conversation; a number, a unit, a date, a clock time or a proper name that neither the
# person nor BAXY said is the model's, not the person's.
#
# What counts as said: every turn of the conversation the decider read (the person's and BAXY's) and the message. A
# number is said in digits or in words («treinta y cinco» is 35, «la mitad» of a level is 50, the current year); a
# clock time or a date is said, or is one a said duration or day word puts from now or from a said clock («en 20
# minutos», «20 minutos antes de eso», «mañana»); a unit is said, or the same unit in other words («l» for «litros»);
# a name is said in any case, with or without its hyphen («NeYo» → «Ne-Yo»), as an abbreviation of a said word
# («control» → «Ctrl»), or completing a said name through «de/del» («ñuñoa» → «Ñuñoa»). What the catalog line of
# the chosen operation names is its world, not an introduction: «sonido del PC» for audio.mute, «on Netflix» for
# streaming.play.named (Netflix or Disney+, whose title reader needs the service written after the title).
_DAY_WORDS_OF_A_NAME = frozenset(
    {*MONTH_NUMBERS, *(name for names in _WEEKDAYS for name in names), "i", "i'm", "i'd", "i'll", "i've"}
)
_NAME_CONNECTOR = frozenset({"de", "del", "la", "las", "los", "of", "the"})
_LEVEL_WORDS = (
    (re.compile(r"\b(?:mitad|half)\b"), 50),
    (re.compile(r"\b(?:maxim[oa]|al\s+tope|full|max)\b"), 100),
    (re.compile(r"\bminim[oa]\b"), 0),
    (re.compile(r"\b(?:un\s+cuarto|a\s+quarter)\b"), 25),
    (re.compile(r"\b(?:tres\s+cuartos|three\s+quarters)\b"), 75),
)
_DEGREES = frozenset({"grado", "grados", "degree", "degrees"})
_NUMERAL = re.compile(
    r"(?<![\w.,])(?P<number>\d+(?:[.,]\d+)*)(?:st|nd|rd|th)?(?P<sign>\s*[°º%])?(?:\s+(?P<unit>[a-z]+)\b)?"
)
_NAME_WORD = re.compile(r"[\w'’-]+")
# M105: the nationalities that qualify a currency or a team, lower case in Spanish; ``stem`` is shared with the
# country's name («colombianos» / «Colombia», «chileno» / «Chile», «mexican» / «México»). Folded.
_DEMONYM = re.compile(
    r"\b(?P<stem>colombian|mexican|argentin|chilen|chilean|uruguay|peruan|peruvian|venezolan|ecuatorian|ecuadorian|"
    r"bolivian|paraguay|cuban|dominican|filipin|philippin|brasilen|brazilian|canadiense|canadian|australian|"
    r"estadounidense|japones|japanese)(?:o|a|os|as|es|s|e)?\b"
)
# What a removed complement leaves hanging in front of it: its preposition and its article.
_LEAD_IN = re.compile(
    r"(?:\s*,)?\s+(?:en|de|del|para|por|a|al|con|in|at|on|from|for|near|of|with)(?:\s+(?:el|la|las|los|the))?\s*$",
    re.IGNORECASE,
)
_ARTICLES_AS_ONE = frozenset({"un", "una", "uno", "one", "a", "an"})


@dataclass(frozen=True, slots=True)
class Fidelity:
    """What travels as the objective: the restatement, the restatement without what it brought, or the message."""

    request: str
    introduced: tuple[str, ...] = ()
    kind: str = "kept"  # kept | trimmed | person


def _values(token: str) -> set[Fraction]:
    """«5.000» is 5000 and 5; «3,5» is 3.5."""

    found: set[Fraction] = set()
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
        found.add(Fraction(int(re.sub(r"\D", "", token))))
    if token.count(".") + token.count(",") <= 1:
        try:
            found.add(Fraction(token.replace(",", ".")))
        except (ValueError, ZeroDivisionError):
            pass
    return found


def _spoken_values(words: list[str], *, articles: bool = True) -> set[Fraction]:
    """The numbers runs of number words say («treinta y cinco» → 35), and each number word alone; without
    ``articles`` a lone «un», «una» or «a» is an article, not a one."""

    found: set[Fraction] = set()
    run: list[str] = []
    for word in [*words, ""]:
        if word in _CARDINAL_WORDS or (run and word in {"y", "and"}):
            run.append(word)
            continue
        while run and run[-1] in {"y", "and"}:
            run.pop()
        if run and (articles or len(run) > 1 or run[0] not in _ARTICLES_AS_ONE):
            whole = spoken_cardinal(" ".join(run))
            if whole is not None:
                found.add(Fraction(whole))
            for single in run:
                value = None if single in {"y", "and"} else spoken_cardinal(single)
                if value is not None and (articles or single not in _ARTICLES_AS_ONE):
                    found.add(Fraction(value))
        run = []
    return found


def _numbers_said(folded: str, *, articles: bool = True) -> set[Fraction]:
    found = {value for token in re.findall(r"\d+(?:[.,]\d+)*", folded) for value in _values(token)}
    return found | _spoken_values(re.findall(r"[a-z0-9]+", folded), articles=articles)


def _said_days(folded: str, now: datetime) -> set[tuple[int, int]]:
    """(day, month) of the dates the words put from today: «hoy», «mañana», «ayer», a weekday, «en 3 días»."""

    offsets = set()
    if re.search(r"\b(?:hoy|today|tonight)\b", folded):
        offsets.add(0)
    if re.search(_TOMORROW, folded):
        offsets.add(1)
    if re.search(r"\bpasado\s+manana\b|\bday\s+after\s+tomorrow\b", folded):
        offsets.add(2)
    if re.search(r"\b(?:ayer|yesterday)\b", folded):
        offsets.add(-1)
    for index, names in enumerate(_WEEKDAYS):
        if re.search(rf"\b(?:{'|'.join(names)})\b", folded):
            offsets.add((index - now.weekday()) % 7)
    for measure in measures(folded):
        if measure.dimension == (0, 1, 0, 0) and measure.value % 86400 == 0:
            offsets.update({int(measure.value // 86400), -int(measure.value // 86400)})
    return {((now + timedelta(days=offset)).day, (now + timedelta(days=offset)).month) for offset in offsets}


def _dates(folded: str) -> list[tuple[int, int, int, int]]:
    """(start, end, day, month) of each date said with its month («el 1 de octubre», «november 10th»)."""

    found = []
    for match in _SPOKEN_DATE.finditer(re.sub(r"(?<=[a-z])-(?=[a-z])", " ", folded)):
        month = match.group("month") or match.group("month_first")
        digits = re.match(r"\d+", match.group("day") or match.group("day_after") or "")
        if month is None or digits is None:
            continue
        found.append((match.start(), match.end(), int(digits.group()), MONTH_NUMBERS[month]))
    return found


def _subsequence(short: str, long: str) -> bool:
    letters = iter(long)
    return all(letter in letters for letter in short)


def _introduced_spans(
    request: str, said: list[str], world: list[str], now: datetime,
) -> list[tuple[int, int, str]]:
    """(start, end, what) of each number, unit, date, clock time or proper name of ``request`` nobody said; the
    ``world`` lines count for names only (their «una hora» is no duration the person gave)."""

    folded_request = fold_in_place(request)
    said_text = spelled_out(fold("\n".join(said)))
    said_words = re.findall(r"[a-z0-9]+", said_text)
    said_set = set(said_words)
    named_words = said_words + re.findall(r"[a-z0-9]+", fold("\n".join(world)))
    named_set = set(named_words)
    stems = {word[:4] for word in named_words}
    named_by_sound = {word.replace("y", "i") for word in named_set if len(word) >= 4}
    glued = {first + second for first, second in zip(named_words, named_words[1:])}
    numbers = _numbers_said(said_text) | {Fraction(now.year)}
    numbers |= {Fraction(value) for pattern, value in _LEVEL_WORDS if pattern.search(said_text)}
    said_units = {_UNITS[word] for word in said_words if word in _UNITS}
    durations = {m.value for line in said for m in measures(fold(line)) if m.dimension == (0, 1, 0, 0)}
    said_clocks = {(c.hour % 12) * 60 + c.minute for line in said for c in spoken_clocks(fold(line))}
    said_dates = {(day, month) for line in said for _, _, day, month in _dates(fold(line))}
    said_dates |= _said_days(said_text, now)

    spans: list[tuple[int, int, str]] = []
    covered: list[tuple[int, int]] = []

    def inside(start: int) -> bool:
        return any(first <= start < last for first, last in covered)

    for start, end, day, month in _dates(folded_request):
        covered.append((start, end))
        if (day, month) not in said_dates:
            spans.append((start, end, request[start:end]))
    # «media hora antes de eso» is only earlier, «dentro de una hora» only later (v3f-devD D-w02-t3 «…antes de eso» after
    # «las 10» was restated «a las 10:30»); a message that says neither may go either way.
    message = fold(said[0]) if said else ""
    signs = tuple(
        sign for sign, word in ((-1, r"antes|before|earlier"), (1, r"despues|after|later|dentro"))
        if re.search(rf"\b(?:{word})\b", message)
    ) or (1, -1)
    bases = said_clocks | {(now.hour % 12) * 60 + now.minute}
    derived = {(base + sign * int(duration // 60)) % 720 for base in bases for duration in durations for sign in signs}
    for clock in spoken_clocks(folded_request):
        start = folded_request.find(clock.literal)
        if start < 0 or inside(start):
            continue
        end = start + len(clock.literal)
        covered.append((start, end))
        dial = (clock.hour % 12) * 60 + clock.minute
        if dial not in said_clocks and dial not in derived:
            spans.append((start, end, request[start:end]))
    for match in _NUMERAL.finditer(folded_request):
        if inside(match.start()):
            continue
        unit = match.group("unit")
        sign = (match.group("sign") or "").strip()
        if sign in {"°", "º"} or unit in _DEGREES:
            unit_said = bool(_DEGREES & said_set) or "°" in said_text or "º" in said_text
        elif unit in _UNITS:
            unit_said = unit in said_set or _UNITS[unit] in said_units
        else:
            unit_said = True
        if unit in _UNITS or unit in _DEGREES:
            end = match.end()
        else:
            end = match.end("sign") if sign else match.end("number")
        if not (_values(match.group("number")) & numbers) or not unit_said:
            spans.append((match.start(), end, request[match.start():end]))

    for match in _DEMONYM.finditer(folded_request):
        # M105 (DEV-D v4a D-w03-t4 «ya. dolar hoy?» in a Chilean conversation → «¿Cuánto vale hoy el dólar en pesos
        # colombianos?»): a nationality is a name written in lower case; the country it belongs to nobody said.
        # A capitalised one («Argentina», «Colombian») is a name, judged with the names below.
        if inside(match.start()) or match.group("stem")[:4] in stems or request[match.start()].isupper():
            continue
        spans.append((match.start(), match.end(), request[match.start():match.end()]))
    words = list(_NAME_WORD.finditer(request))
    for index, word in enumerate(words):
        text = word.group(0)
        if not text[:1].isupper():
            continue
        lead = request[:word.start()].rstrip().rstrip("¿¡\"«“'(").rstrip()
        key = fold(text)
        if not lead or lead[-1] in ".!?:;" or key in _DAY_WORDS_OF_A_NAME:
            continue
        bare = re.sub(r"[-'’]", "", key)
        if bare[:4] in stems or bare in glued or bare in named_set:
            continue
        if bare.replace("y", "i") in named_by_sound:
            # M110 (DEV-F v4d F-w03-t4 «qué hora es en Tokyo» restated «…en Tokio?», trimmed to «¿Qué hora es
            # ahora?» and the clock of here was read): a name spelled with «i» for «y» is the name said.
            continue
        if len(bare) >= 2 and any(
            len(said_word) >= len(bare) + 2 and said_word[0] == bare[0] and _subsequence(bare, said_word)
            for said_word in named_set
        ):
            continue
        if len(bare) >= 4 and any(_one_transposition(bare, said_word) for said_word in said_set):
            # M111 (DEV-F v4d F-s003 «abreme el wrod» restated «Abre Word.» → asked which application): two letters
            # swapped are the same word mistyped or misheard (owner rule 2026-09-19: BAXY fixes what was said wrong).
            continue
        # «Ñuñoa» for «ñuñoa»: the name continues a said name through «de/del».
        back = index - 1
        while back >= 0 and fold(words[back].group(0)) in _NAME_CONNECTOR:
            back -= 1
        if back < index - 1 and back >= 0 and words[back].group(0)[:1].isupper():
            if re.sub(r"[-'’]", "", fold(words[back].group(0)))[:4] in stems:
                continue
        spans.append((word.start(), word.end(), text))
    return sorted(spans)


def _one_transposition(word: str, said: str) -> bool:
    """``word`` is ``said`` with two neighbouring letters swapped («word» / «wrod»)."""

    if len(word) != len(said) or word == said:
        return False
    differ = [index for index, (first, second) in enumerate(zip(word, said)) if first != second]
    return (
        len(differ) == 2
        and differ[1] == differ[0] + 1
        and word[differ[0]] == said[differ[1]]
        and word[differ[1]] == said[differ[0]]
    )


def _trimmed(request: str, spans: list[tuple[int, int, str]]) -> str | None:
    """The request without each introduced complement and the preposition that led to it; None when one of them is
    not a complement («Abre Spotify») or too little would be left."""

    # A name of several words is one complement: «en Nueva York».
    merged: list[list[int]] = []
    for start, end, _ in spans:
        if merged and re.fullmatch(r"[\s,]*", request[merged[-1][1]:start]):
            merged[-1][1] = end
        else:
            merged.append([start, end])
    result = request
    for start, end in reversed(merged):
        if request[start:end].islower() and _DEMONYM.fullmatch(fold(request[start:end])) is not None:
            # M105 (DEV-D v4a D-w03-t4): a nationality nobody said qualifies the noun before it («en pesos
            # colombianos» → «en pesos»); the noun stays.
            result = result[:start] + result[end:]
            continue
        lead = _LEAD_IN.search(result[:start])
        if lead is None:
            # M93 (DEV-D v3u D-w08-t2 «y cuando juega el sigiente» after «el América» → «¿Cuándo juega el Club América
            # su próximo partido?»): a capitalised word the decider put in front of a name that was said («Club
            # América») is a title of that name; the name said stays and the word goes. Anything else is no complement.
            follows = re.match(r"\s+([^\W\d_][\w'’-]*)", result[end:])
            if (
                follows is None
                or not follows.group(1)[:1].isupper()
                or not re.fullmatch(r"(?:[^\W\d_][\w'’-]*\s*)+", request[start:end])
            ):
                return None
            result = result[:start] + result[end:].lstrip()
            continue
        result = result[:lead.start()] + result[end:]
    result = re.sub(r"\s+([?.!,;:])", r"\1", " ".join(result.split()))
    result = re.sub(r",([?.!])", r"\1", result).strip(" ,")
    content = [word for word in re.findall(r"[a-z0-9]+", fold(result)) if len(word) > 2]
    return result if len(content) >= 2 else None


def faithful_request(
    request: str,
    text: str,
    conversation: Iterable[str],
    *,
    world: Iterable[str] = (),
    now: datetime | None = None,
) -> Fidelity:
    """The decider's restatement as the objective, only with what was said (M64).

    ``conversation`` is every turn the decider read; ``world`` the catalog lines of the operations it chose. What the
    restatement brought is taken out when it is a complement («…mañana en Santiago?» → «…mañana?») and every number
    the message states stays in the result; otherwise the objective is the person's message, which the steps after
    the decider read with the conversation as they always do.
    """

    request = " ".join(str(request or "").split())
    if not request:
        return Fidelity(request)
    now = now or datetime.now()
    taken_back = taken_back_time(str(text or ""))
    if taken_back is not None:
        # M76 (DEV-D v3l D-s097 «… en 2 , no espera en 3 minutos» restated «Pon un temporizador de 2 minutos…»): a
        # number the person said and took back is said, but not asked for. A restatement that keeps it and loses the
        # time that stands is not the request.
        restated = _numbers_said(fold(request))
        kept = _numbers_said(fold(taken_back.kept))
        dropped = _numbers_said(fold(taken_back.taken_back)) - kept
        if dropped & restated and not kept & restated:
            return Fidelity(" ".join(str(text or "").split()), (taken_back.taken_back,), "person")
    said = [str(text or ""), *(str(line or "") for line in conversation)]
    lines = [str(line or "") for line in world]
    spans = _introduced_spans(request, said, lines, now)
    if not spans:
        return Fidelity(request)
    introduced = tuple(dict.fromkeys(what for _, _, what in spans))
    trimmed = _trimmed(request, spans)
    if (
        trimmed is not None
        and not _introduced_spans(trimmed, said, lines, now)
        and _numbers_said(fold(text), articles=False) <= _numbers_said(fold(trimmed))
    ):
        return Fidelity(trimmed, introduced, "trimmed")
    carried = _with_the_conversation_name(request, spans, str(text or ""), [str(line or "") for line in conversation])
    if (
        carried is not None
        and not _introduced_spans(carried, said, lines, now)
        and _numbers_said(fold(text), articles=False) <= _numbers_said(fold(carried))
    ):
        return Fidelity(carried, introduced, "carried")
    return Fidelity(" ".join(str(text or "").split()), introduced, "person")


# Words that carry no content of their own: a restatement may add or drop them freely.
_FUNCTION_WORDS = frozenset({
    "para", "pero", "porque", "como", "este", "esta", "esto", "estos", "estas", "ese", "esa", "eso", "unos", "unas",
    "sobre", "desde", "hasta", "donde", "cuando", "tambien", "solo", "todo", "toda", "todos", "todas", "mismo",
    "with", "that", "this", "these", "those", "from", "have", "will", "your", "about", "into", "then", "than",
    "there", "their", "they", "what", "when", "which", "would", "could", "should",
})


def said_in_other_words(value: str, said: Iterable[str], *, now: datetime | None = None) -> bool:
    """M118 (D58, DEV-F F-w28-t4 «ponme algo de lo-fi pa concentrarme» → query «lo-fi para concentrarse», F-w01-t4 the
    draft «…con 10 minutos de retraso porque tengo dentista antes», F-s022 details «…porque el viaje a Cancún…» after
    «el trip a Cancún»): a free text the decider wrote is what was said, in its own words, when it brings no number,
    unit, date, clock time or name nobody said (``_introduced_spans``, the restatement's own check) and at least three
    in four of its content words share their stem with a word said. A literal check dropped these values and the turn
    asked again for what the person had given; the decider is never overruled on words alone."""

    text = " ".join(str(value or "").split())
    lines = [str(line or "") for line in said]
    if not text or not any(line.strip() for line in lines):
        return False
    said_text = spelled_out(fold("\n".join(lines)))
    if any(
        # What is written as it was said (an address «192.168.1.64», «a las 11:30» quoted from BAXY) is said.
        " ".join(spelled_out(fold(what)).split()) not in " ".join(said_text.split())
        for _, _, what in _introduced_spans(text, lines, [], now or datetime.now())
    ):
        return False
    said_stems = {word[:5] for word in re.findall(r"[a-z0-9]+", said_text)}
    content = [
        word for word in re.findall(r"[a-z]+", spelled_out(fold(text)))
        if len(word) >= 4 and word not in _FUNCTION_WORDS
    ]
    if not content:
        return False
    return 4 * sum(word[:5] in said_stems for word in content) >= 3 * len(content)


def _conversation_names(line: str) -> list[str]:
    """The names a line writes: runs of capitalised words that do not open a sentence, joined by «de/del/of…»."""

    names: list[str] = []
    run: list[str] = []
    words = list(_NAME_WORD.finditer(line))
    for word in words:
        text = word.group(0)
        lead = line[:word.start()].rstrip().rstrip("¿¡\"«“'(").rstrip()
        opens = not lead or lead[-1] in ".!?:;"
        if text[:1].isupper() and not opens and fold(text) not in _DAY_WORDS_OF_A_NAME:
            run.append(text)
            continue
        if run and fold(text) in _NAME_CONNECTOR and text[:1].islower():
            run.append(text)
            continue
        if run:
            while run and fold(run[-1]) in _NAME_CONNECTOR:
                run.pop()
            names.append(" ".join(run))
            run = []
    while run and fold(run[-1]) in _NAME_CONNECTOR:
        run.pop()
    if run:
        names.append(" ".join(run))
    return [name for name in names if name]


def _with_the_conversation_name(
    request: str, spans: list[tuple[int, int, str]], text: str, conversation: list[str],
) -> str | None:
    """M105 (DEV-D v4a D-w08-t2 «y cuando juega el sigiente» after «cuanto qedo el america anoche» → «¿Cuándo juega el
    Atlético Nacional el próximo partido?»): the decider put another team where the conversation's own name goes, the
    fidelity check fell back to the bare message, and the search for «y cuando juega el sigiente» answered with Mexico's
    national team. In a short follow-up that names nothing itself, the one name the restatement brought stands where
    the conversation's last name goes: that name replaces it. None when the restatement brought more than one name,
    anything that is no name, or the last two lines of the conversation name nothing."""

    if len(re.findall(r"[\w'’-]+", text)) > 8 or _conversation_names(f". {text}"):
        return None
    merged: list[list[int]] = []
    for start, end, _ in spans:
        if merged and re.fullmatch(r"[\s,]*|\s+(?:de|del|la|las|los|of|the)\s+", request[merged[-1][1]:start]):
            merged[-1][1] = end
        else:
            merged.append([start, end])
    if len(merged) != 1 or not all(what[:1].isupper() for _, _, what in spans):
        return None
    start, end = merged[0]
    lines = [line for line in conversation if line.strip() and " ".join(line.split()) != " ".join(text.split())]
    for line in reversed(lines[-2:]):
        names = _conversation_names(line)
        if names:
            return " ".join((request[:start] + names[-1] + request[end:]).split())
    return None

