"""Uso real tanda 3 (2026-09-24, official window): five general rules, each with one owner.

A. The person's own data never leaves the PC as a web search («es cierto que el cumpleaños de antonia es
   el primero de marzo», «what do i have to do on january 1st» became web.search). Owner:
   semantic/web.names_own_data (first person possession or experience, a bare given name, relatives, this PC).
B. A time is never a place («el weather para la semana del 5 al 12 de julio» read the weather of Júlio,
   Mozambique). Owner: semantic/system._weather_location over semantic/temporal.is_window_phrase.
C. The home, the start page or the desktop after a go-to verb is the PC's desktop («Go to página de inicio»
   opened a dictionary page). Owner: semantic/windows.PC_HOME_PLACE / minimize_all_request.
D. Day, date, month, year and weekday questions read this PC's clock («what day are we in», «¿estamos a
   enero o febrero?»). Owner: semantic/network._direct_current_time_request.
E. A kind of public place near the person is looked up near this PC, never asked its name («busca un
   restaurante en mi zona»). Owner: semantic/web._location_recommendation_request.

Every list mixes Spanish, English and Spanglish, and holds phrasings never seen in a run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind import __main__ as mind_main  # noqa: E402
from baxy_mind.__main__ import _prepare_turn_result  # noqa: E402
from baxy_mind.effect_intent import operation_domain_is_grounded, resolve_explicit_effects  # noqa: E402
from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.semantic.system import _weather_location  # noqa: E402
from baxy_mind.semantic.web import _entity_lookup_query, names_own_data, person_fact_subject  # noqa: E402


def _tool(operation: str, properties: dict | None = None) -> dict:
    properties = properties or {}
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            },
        },
    }


_WEB_SEARCH = _tool("web.search", {"query": {"type": "string", "x-nonWhitespace": True}})


class _NoModel:
    """The readers must own the turn: the model is never asked to decide it."""

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("a deterministic reading owns this turn")

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


class _ChattingModel:
    """A model that answers as knowledge and admits not knowing, with a guard that reads everything as a
    public lookup: the two ways a question reaches web.search without a reader (public_lookup and
    unknown_looked_up)."""

    def __init__(self) -> None:
        self.chat_texts: list[str] = []

    @staticmethod
    def decide_turn(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "mode": "conversation", "operation": None, "question": "", "conversation_kind": "knowledge",
            "effect_count": "zero", "effect_operations": [], "effect_verification": "not_applicable",
            "response_language": "es",
        }

    def chat(self, text: str, **_kwargs: object) -> tuple[str, list[object]]:
        self.chat_texts.append(text)
        return "No lo sé.", []

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return True

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None


def _turn(text: str, operations: tuple[str, ...], llm: object) -> dict:
    tools = [_WEB_SEARCH if operation == "web.search" else _tool(operation) for operation in operations]
    return _prepare_turn_result(
        {"id": "tanda-03", "text": text, "history": []},
        llm=llm,
        planner_catalog=PlannerCatalog(tools),
        encoder=lambda _texts: (),
        tool_by_name={tool["function"]["canonical_name"]: tool for tool in tools},
    )


# --- A. The person's own data never leaves the PC as a web search ------------------------------------

_OWN_DATA = [
    # tanda 3, t4 and t35
    "es cierto que el cumpleaños de antonia es el primero de marzo",
    "what do i have to do on january 1st",
    # a private person named by a bare given name
    "cuándo es el cumpleaños de juan",
    "when is carlos's birthday",
    "qué edad tiene pedro",
    "how old is jessica",
    "dónde vive martina",
    "what is daniel's phone number",
    "cuál es el teléfono de lucía",
    "is it true that valentina got married in april",
    "es verdad que andrés se muda en mayo",
    "did antonia call yesterday",
    "qué me regaló sebastián para navidad",
    # first person possession or experience
    "what do i have going on next friday",
    "qué tengo que hacer el lunes",
    "tengo algo pendiente para el 3 de mayo",
    "did i pay the electricity bill",
    "am i free on thursday afternoon",
    "have i got anything on saturday",
    "what did i do last weekend",
    "qué hice ayer en la tarde",
    "me toca trabajar el domingo",
    "cuáles son mis planes para el finde",
    "i have to call the bank tomorrow, at what time",
    "cuántos años tengo",
    "Do I have any meetings on the 5th?",
    # relatives
    "cuándo es el cumpleaños de mi mamá",
    "how old is my wife",
    "what's grandma's birthday",
    "cuándo cumple años la abuela",
    "is mom working on monday",
    # this PC
    "how much battery does this laptop have left",
    "cuánto espacio le queda a este pc",
    "a qué hora llega el vuelo de la tía",
    "what did mike say about the party",
    "cuándo es la boda de juan y andrea",
]

_PUBLIC = [
    "cuántos años tiene jennifer lopez",
    "when is taylor swift's birthday",
    "quién fue gandhi",
    "cuándo nació gandhi",
    "how old is shakira",
    "dónde vive messi",
    "cuál es el precio del bitcoin hoy",
    "cuánto está el dólar en chile",
    "noticias de hoy en argentina",
    "quién ganó el partido de anoche",
    "qué edad tiene el papa francisco",
    "who is elon musk",
    "cuántos años tiene maría becerra",
    "how old is david beckham",
    "quién es carlos alcaraz",
    "qué edad tiene el rey felipe",
    "when did queen elizabeth die",
    "how tall is michael jordan",
    "who won the world cup in 2022",
    "what's the population of japan",
    "cuál es la capital de australia",
    "what's the exchange rate between pesos and yen",
    "quién escribió don quijote",
    "who is the president of france",
    "cuándo sale la nueva película de marvel",
    "is it true that einstein failed math",
    "what time does the louvre open",
    "how do i get to machu picchu from cusco",
    "where can i buy cheap flights to lima",
    "tengo una duda, quién pintó la mona lisa",
    "i have a question, who invented the telephone",
    "cuántos años tiene luis miguel",
    "qué edad tiene juan pablo ii al morir",
    "restaurantes cerca de mí",
    "busca un restaurante en mi zona",
    "who is kevin hart",
    "cuándo murió juan gabriel",
    "how old is prince william",
    "cuánto cuesta el iphone 16 en mi país",
    "qué edad tiene la cantante maría",
]


def _catalog() -> PlannerCatalog:
    return PlannerCatalog([_WEB_SEARCH])


class _GuardSaysPublic:
    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return True


@pytest.mark.parametrize("text", _OWN_DATA)
def test_own_data_is_never_a_public_lookup_whatever_the_guard_reads(text: str) -> None:
    assert names_own_data(text)
    assert not mind_main._public_lookup_applies(text, text, _GuardSaysPublic(), ("web.search",), _catalog())


@pytest.mark.parametrize("text", _PUBLIC)
def test_public_questions_are_still_looked_up(text: str) -> None:
    assert not names_own_data(text)
    assert mind_main._public_lookup_applies(text, text, _GuardSaysPublic(), ("web.search",), _catalog())


@pytest.mark.parametrize(
    "text", ["qué edad tiene pedro", "how old is jessica", "cuántos años tiene antonia", "quién es antonia",
             "who is martina"],
)
def test_a_private_person_is_no_person_or_entity_lookup(text: str) -> None:
    assert person_fact_subject(text) is None
    assert _entity_lookup_query(text) is None
    intent = resolve_explicit_effects(text, {"web.search"})
    assert intent is None or "web.search" not in intent.operations


@pytest.mark.parametrize(
    "text", ["cuantos años tiene jennifer lopez", "how old is Taylor Swift", "quién es gandhi", "who is Shakira"],
)
def test_public_people_keep_their_lookup(text: str) -> None:
    intent = resolve_explicit_effects(text, {"web.search"})
    assert intent is not None and intent.operations == ("web.search",)


# --- B. A time is never a place -----------------------------------------------------------------------

_TIMES_ONLY = [
    "Dime el weather para la semana del 5 al 12 de julio por favor",
    "clima para julio",
    "weather for july",
    "¿cómo estará el clima en agosto?",
    "weather in december",
    "pronóstico del 3 al 8 de mayo",
    "clima para el 15 de septiembre",
    "forecast for march 3rd",
    "qué tiempo hará el 24 de diciembre",
    "weather for the week of june 10",
    "va a llover en enero?",
    "weather for next monday please",
    "clima para el 1 de enero",
    "el clima para julho",
    "clima de la semana del 10 al 17 de octubre",
    "weather for the weekend of november 8",
    "dime el clima para febrero, porfa",
    "forecast from april 2 to april 9",
    "clima para el martes 5 de marzo",
    "weather on the 4th of july",
    "clima para el 20/07",
]

_PLACE_AND_TIME = [
    ("clima en Madrid el 5 de julio", "Madrid"),
    ("weather in London in july", "London"),
    ("clima en Buenos Aires para la semana del 5 al 12 de julio", "Buenos Aires"),
    ("qué tiempo hace en Lima en agosto", "Lima"),
    ("weather in Paris on the 4th of july", "Paris"),
    ("clima de Santiago del 1 al 3 de marzo", "Santiago"),
    ("clima en Ñuñoa en enero", "Ñuñoa"),
    ("qué tiempo hace en San José el lunes", "San José"),
    ("weather in Sydney next week", "Sydney"),
    ("clima en Puerto Montt el 18 de septiembre", "Puerto Montt"),
    ("weather in Rio de Janeiro in march", "Rio de Janeiro"),
    ("clima en Mendoza para diciembre", "Mendoza"),
]


@pytest.mark.parametrize("text", _TIMES_ONLY)
def test_a_time_is_never_the_weather_place(text: str) -> None:
    assert _weather_location(text) is None


@pytest.mark.parametrize("text, place", _PLACE_AND_TIME)
def test_the_place_is_kept_and_its_time_dropped(text: str, place: str) -> None:
    assert _weather_location(text) == place


# --- C. Home, the start page and the desktop after a go-to verb are the PC's desktop -------------------

_HOME = [
    "Go to página de inicio",
    "ve a la página de inicio",
    "llévame a la página de inicio",
    "vuelve a la página principal",
    "take me home please",
    "regresa a la página de inicio",
    "go home",
    "go back to the home screen",
    "ve al inicio",
    "vuelve al inicio",
    "regresa a la pantalla de inicio",
    "go to the start screen",
    "ir al escritorio",
    "go to desktop",
    "llévame al home",
    "ve a home",
    "vete al escritorio",
    "take me back home",
    "return to the home screen",
    "regresa al inicio por favor",
    "Go to the pantalla de inicio",
    "anda a la página de inicio",
]

_NOT_HOME = [
    "ve a la página de inicio de google",
    "go to youtube home",
    "abre la página de inicio de wikipedia",
    "ve a youtube",
    "go to amazon's home page",
    "llévame a la página principal de mercadolibre",
    "go to the homepage of the bbc",
    "ve a la página de la nasa",
]

_HOME_OPS = frozenset({"window.minimize.all", "web.search", "browser.navigate", "app.open"})


@pytest.mark.parametrize("text", _HOME)
def test_going_home_shows_the_desktop(text: str) -> None:
    intent = resolve_explicit_effects(text, _HOME_OPS)
    assert intent is not None and intent.operations == ("window.minimize.all",)
    assert operation_domain_is_grounded(text, "window.minimize.all") is True
    assert operation_domain_is_grounded(text, "browser.navigate") is not True
    assert operation_domain_is_grounded(text, "web.search") is not True


@pytest.mark.parametrize("text", _HOME)
def test_going_home_is_never_a_website_even_without_minimize_all(text: str) -> None:
    intent = resolve_explicit_effects(text, {"web.search", "browser.navigate"})
    assert intent is None or not {"web.search", "browser.navigate"} & set(intent.operations)


@pytest.mark.parametrize("text", _NOT_HOME)
def test_a_named_site_home_stays_on_the_web(text: str) -> None:
    intent = resolve_explicit_effects(text, _HOME_OPS)
    assert intent is not None and "window.minimize.all" not in intent.operations
    assert "web.search" in intent.operations


def test_the_desktop_folder_and_the_start_of_a_song_are_not_the_desktop_view() -> None:
    for text in ("abre el escritorio", "ve al inicio de la canción"):
        intent = resolve_explicit_effects(text, _HOME_OPS)
        assert intent is None or "window.minimize.all" not in intent.operations


# --- D. Day, date, month, year and weekday questions read this PC's clock -------------------------------

_CLOCK_DATE = [
    # tanda 3, t26 and t34
    "what day are we in",
    "¿estamos a enero o febrero?",
    "what day is it today",
    "what day is today",
    "what's today",
    "what's the date today",
    "what is today's date",
    "which day is it",
    "what month is it",
    "what month are we in",
    "what year is it",
    "what year are we in",
    "is it monday today?",
    "is today friday",
    "do you know what day it is",
    "can you tell me what day it is",
    "what weekday is it",
    "today is what day?",
    "¿en qué mes estamos?",
    "qué mes es",
    "¿en qué año estamos?",
    "qué año es",
    "¿hoy es lunes?",
    "¿es viernes hoy?",
    "qué fecha es hoy",
    "a cuántos estamos",
    "a cuántos estamos hoy",
    "¿a qué día estamos?",
    "sabes qué día es hoy",
    "dime qué día es hoy",
    "hoy qué día es",
    "¿estamos en marzo?",
    "¿ya es viernes?",
    "qué día de la semana es hoy",
    "¿estamos a martes o miércoles?",
    "cuál es la fecha de hoy",
    "¿hoy es monday?",
]

_NOT_CLOCK_DATE = [
    "qué día es el cumpleaños de juan",
    "what day is the meeting",
    "en qué año nació messi",
    "what month is best to visit japan",
    "qué día cae navidad este año",
    "what year did world war two end",
    "estamos listos",
    "qué día es mejor para viajar",
    "what day of the week was july 4 1776",
    "estamos a tiempo de llegar",
    "en qué mes se planta el tomate",
    "what date is easter this year",
    "is it raining today",
]

_CLOCK_OPS = frozenset({"system.time", "web.search", "calendar.event.list"})


@pytest.mark.parametrize("text", _CLOCK_DATE)
def test_date_questions_read_this_pc_clock(text: str) -> None:
    intent = resolve_explicit_effects(text, _CLOCK_OPS)
    assert intent is not None and intent.operations == ("system.time",)
    assert operation_domain_is_grounded(text, "system.time") is True


@pytest.mark.parametrize("text", _NOT_CLOCK_DATE)
def test_dates_of_other_things_are_not_the_clock(text: str) -> None:
    intent = resolve_explicit_effects(text, _CLOCK_OPS)
    assert intent is None or "system.time" not in intent.operations


@pytest.mark.parametrize("text", ["what day are we in", "¿estamos a enero o febrero?", "what year is it"])
def test_a_date_question_turn_reads_the_clock_without_the_model(text: str) -> None:
    result = _turn(text, ("system.time", "web.search"), _NoModel())
    assert result["operation"] == "system.time"
    assert "web.search" not in result["effectOperations"]


# --- E. A kind of public place near the person is looked up near this PC -------------------------------

_NEARBY_PLACES = [
    "busca un restaurante en mi zona",
    "restaurantes cerca de mí",
    "find a restaurant near me",
    "busca una pizzería cerca de aquí",
    "recomiéndame un bar en mi barrio",
    "what are the best restaurants in my area",
    "any good coffee shops nearby?",
    "busca gasolineras cercanas",
    "dónde hay una farmacia por aquí",
    "is there a supermarket around here",
    "search for a gym close to me",
    "farmacias abiertas cerca",
    "necesito un cajero cerca de donde estoy",
    "hay alguna heladería en la zona",
    "look for a bakery in my neighborhood",
    "quiero comer sushi, busca un restaurante cerca",
    "encuentra un hotel en mi ciudad",
    "where's the closest gas station",
    "busca cines en mi área",
    "top rated pizza places near me",
    "buscame una peluquería por acá",
    "find me a laundromat nearby",
    "dónde queda la farmacia más cercana",
    "any bars around me",
    "restaurantes buenos en mi zona",
    "busca un café cerca de mi casa",
    "hay tiendas abiertas cerca de aquí",
    "best tacos near me",
    "encuéntrame un supermercado en la zona",
    "recommend a restaurant around here",
]

_NOT_NEARBY_PLACES = [
    "cuánto gasté en restaurantes este mes",
    "qué restaurante me recomendó juan",
    "busca la receta de pollo en mis notas",
    "abre mis fotos del restaurante",
]


@pytest.mark.parametrize("text", _NEARBY_PLACES)
def test_a_place_near_the_person_is_a_public_search(text: str) -> None:
    intent = resolve_explicit_effects(text, {"web.search", "browser.navigate"})
    assert intent is not None and intent.operations == ("web.search",)


@pytest.mark.parametrize("text", _NOT_NEARBY_PLACES)
def test_the_persons_own_places_are_no_nearby_search(text: str) -> None:
    intent = resolve_explicit_effects(text, {"web.search", "browser.navigate"})
    assert intent is None or "web.search" not in intent.operations


def test_a_nearby_place_turn_searches_without_asking_its_name() -> None:
    result = _turn("busca un restaurante en mi zona", ("web.search",), _NoModel())
    assert result["kind"] == "action"
    assert result["operation"] == "web.search"
