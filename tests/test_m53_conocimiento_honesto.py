"""M53 (step 6 of goal v3; owner's decision D35; study R8): dated facts, figures and recipes are consulted first.

Design A — a named dish's recipe and a named work's plot are looked up (``semantic.knowledge``), without touching the
decider: its «talk» becomes ``web.search`` with the query the reader writes, and the answer is written from the page
read, in its form (ingredients and numbered steps). Nothing consulted → from memory, saying so briefly.
Design B — figures derived from the person's quantities are computed by BAXY (``semantic.quantities``) and a talk
reply whose derived figure matches nothing is vetoed and retried.

The texts are the development cases of the official window (``window/v3a-final``, ``window/final-once``); the drafts
are the replies those runs published.
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import LlmRuntime, _shaped_conversation_answer_violates_contract
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import knowledge, quantities
from baxy_mind.semantic.decider import ContextDecision

S002 = "¿Qué ingredientes hacen faltan para el pan de banana"
W01_T1 = (
    "oye baxy, esta noche vienen unos amigos a comer y quiero hacer pastel de choclo, ¿me dai la receta pa 6? "
    "algo simple nomás, no soy muy de cocinar po"
)
W02_T1 = "oye baxy, onda, explícame paso a paso cómo hacer sopaipillas, que estoy en la cocina y no cacho nada"
P11_T1 = "Podrías resumirme el libro del Hobbit?"
P11_T2 = "¿Porque es peligroso el anillo?"
P11_T3 = "¿Cómo continuarías la historia? Suponiendo que el final propuesto debe ser trágico y asombroso a la vez."
S097 = "He recorrido 5 kilómetros en 1 hora, en realidad 1 hora 10 minutos."
W12 = (
    "Che, mirá, estoy armando un scriptcito en Python para ordenar los gastos del mes, ¿viste? ¿Me escribís una "
    "función que reciba una lista de montos y devuelva el total y el promedio?",
    "Buenísimo. ¿Y me la pasás a JavaScript? Es para una paginita",
)
W12_T3 = "Re bien. Ahora que el promedio salga redondeado a dos decimales, dale"
GUARD = (
    "how do i make chicken alfredo",  # F-s036: answered well from memory; no culinary word says «recipe»
    "¿Qué diferencia a un animal de compañía de uno salvaje?",  # F-s057
    "¿Podrías sugerirme una receta vegetariana para cenar esta noche?",  # F-s068: an open suggestion
    "Cuantos numeros primos existen entre el numero 1 y el numero 5000",  # F-s069
    "i need to know what timezone ireland is in",  # F-s073
    "¿Qué me recomiendas que lleve para el viaje? ¿puedes generar una lista de los elementos considerando que voy a "
    "estar entre 3 y 4 días allí?",  # F-p12-t3
)


# ------------------------------------------------------------------ design A: what is looked up


@pytest.mark.parametrize(
    ("text", "prior", "kind", "query"),
    [
        (S002, (), "recipe", "receta pan de banana"),
        (W01_T1, (), "recipe", "receta pastel de choclo"),
        ("Dame una receta simple de pastel de choclo para 6 personas.", (), "recipe", "receta pastel de choclo"),
        (W02_T1, (), "recipe", "receta sopaipillas"),
        ("what are the ingredients for banana bread", (), "recipe", "recipe banana bread"),
        (P11_T1, (), "plot", "resumen libro hobbit"),
        # The follow-up names no other work: it is about the work just looked up; after «:», what it asks about.
        (P11_T2, (P11_T1,), "plot", "resumen libro hobbit: peligroso anillo"),
        ("¿Por qué es peligroso el Anillo Único en El Hobbit?", (P11_T1,), "plot", "resumen libro hobbit: peligroso anillo unico"),
        ("Resumime El Señor de los Anillos", (), "plot", "resumen senor de los anillos"),
        # F-s020: a ranking of the world, asked by its superlative.
        ("¿Cuáles son los 9 objetos mas brillantes del cielo nocturno?", (), "ranking",
         "ranking objetos brillantes del cielo nocturno"),
        ("what are the tallest mountains in the world", (), "ranking", "ranking tallest mountains in the world"),
    ],
)
def test_a_named_dish_or_work_is_looked_up(text: str, prior: tuple[str, ...], kind: str, query: str) -> None:
    lookup = knowledge.reference_lookup(text, prior)

    assert lookup is not None
    assert (lookup.kind, lookup.query) == (kind, query)


@pytest.mark.parametrize("text", GUARD)
def test_the_guard_set_stays_talk(text: str) -> None:
    assert knowledge.reference_lookup(text) is None


@pytest.mark.parametrize(
    ("text", "prior"),
    [
        (P11_T3, (P11_T1,)),  # imagining an ending is written, not looked up
        ("¿Te gustó el libro?", (P11_T1,)),  # an opinion
        ("ya, hazme la lista de compras con eso", (W01_T1,)),
        ("resume este texto: hola mundo", ()),
        ("cómo hago la tarea en la cocina", ()),
        # What is ranked on this PC or among the person's things is read there, not looked up.
        ("¿cuáles son los procesos que más memoria consumen?", ()),
        ("dime las canciones que más escucho", ()),
    ],
)
def test_what_is_not_a_named_dish_or_work_is_not_looked_up(text: str, prior: tuple[str, ...]) -> None:
    assert knowledge.reference_lookup(text, prior) is None


def test_the_servings_asked_are_read_from_the_request_or_the_one_it_continues() -> None:
    assert knowledge.servings_asked(W01_T1) == 6
    assert knowledge.servings_asked("Dame una receta de sopaipillas para 6 personas.") == 6
    assert knowledge.servings_asked("¿y para cuatro personas?", (W02_T1,)) == 4
    assert knowledge.servings_asked("receta para una cena rica") is None
    assert knowledge.servings_asked(S002) is None


OPERATIONS = ("web.search", "system.time", "media.control")


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.",
            "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


class _Talk:
    """The decider answers «talk», as it did for every development case."""

    def __init__(self, request: str) -> None:
        self.request = request
        self.chats = 0

    def decide_in_context(self, text: str, history: object, tools: object, **_kwargs: object) -> ContextDecision:
        return ContextDecision(self.request, "talk", (), "")

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Una respuesta de memoria.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"

    @staticmethod
    def consume_deferred_response_language(_text: str) -> tuple[bool, str | None]:
        return True, "es"

    @staticmethod
    def retire_deferred_response_language(_text: str) -> None:
        return None

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def _verify_semantic_effect_shape(_text: str) -> tuple[str, str]:
        return "no_effect", "zero"


def _turn(text: str, llm: _Talk, history: list[dict[str, str]] | None = None) -> dict[str, object]:
    tools = {name: _tool(name) for name in OPERATIONS}
    return sidecar._prepare_turn_result(
        {"id": "m53", "text": text, "history": [*(history or []), {"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


@pytest.mark.parametrize(
    ("text", "restated"),
    [
        (S002, "¿Qué ingredientes faltan para hacer pan de banana?"),
        (W01_T1, "Dame una receta simple de pastel de choclo para 6 personas."),
        (W02_T1, "Explícame paso a paso cómo hacer sopaipillas."),
        (P11_T1, "Resume el libro El Hobbit."),
    ],
)
def test_the_deciders_talk_about_a_named_dish_or_work_is_a_lookup(text: str, restated: str) -> None:
    llm = _Talk(restated)

    result = _turn(text, llm)

    assert result["kind"] == "action"
    assert result["operation"] == "web.search"
    assert llm.chats == 0


@pytest.mark.parametrize("text", GUARD)
def test_the_deciders_talk_on_the_guard_set_is_still_answered(text: str) -> None:
    llm = _Talk(text)

    result = _turn(text, llm)

    assert result["kind"] == "conversation"
    assert llm.chats == 1


WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "minimum": 1, "maximum": 20},
        "nearby": {"type": ["boolean", "null"]},
        "query": {"type": "string", "minLength": 1},
    },
    "required": ["query"],
    "additionalProperties": False,
}


def test_the_arguments_step_reads_the_same_query_back() -> None:
    assert sidecar._ground_explicit_arguments(
        "web.search", "Dame una receta simple de pastel de choclo para 6 personas.", WEB_SEARCH_SCHEMA,
    ) == {"query": "receta pastel de choclo"}
    # The follow-up reads the work from the conversation the App sends back.
    history = [
        {"role": "user", "content": P11_T1},
        {"role": "assistant", "content": "Bilbo acompaña a trece enanos a recuperar el tesoro de Smaug."},
        {"role": "user", "content": P11_T2},
    ]
    assert sidecar._ground_explicit_arguments("web.search", P11_T2, WEB_SEARCH_SCHEMA, history=history) == {
        "query": "resumen libro hobbit: peligroso anillo"
    }


# ------------------------------------------------------------------ design A: the answer from the page


SOPAIPILLA_PAGE = (
    "Ingredientes (para 4 personas):\n- 3 tazas de harina\n- 2 huevos\n- 1 barrita de mantequilla o poquito menos\n"
    "- 1 cucharadita de polvo de hornear\n- 1 pizca de sal\n- Leche para amasar\n- Aceite (el suficiente para freír)\n"
    "Preparación:\n1. Se coloca la harina con el polvo de hornear, se agrega la mantequilla desintegrándola.\n"
    "2. Se hacen tortillas y se cortan en cuatro.\n3. Se fríen en aceite hasta que tomen un aspecto dorado."
)


def _recipe_situation(servings: int | None = 4) -> dict:
    observed = {
        "version": 1,
        "query": "receta sopaipillas",
        "count": 1,
        "results": [{
            "title": "Sopaipilla",
            "url": "https://es.wikibooks.org/wiki/Artes_culinarias/Recetas/Sopaipilla",
            "snippet": SOPAIPILLA_PAGE,
        }],
        "reference": "recipe",
        "authority": "wikibooks_es_api",
    }
    if servings is not None:
        observed["servings"] = servings
    return {
        "kind": "operation", "operation": "web.search", "polarity": "success",
        "verified": True, "succeeded": True, "observed": observed,
    }


class _Writer(LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


SCALED = (
    "La sopaipilla es una masa frita; esta receta es para 6.\nIngredientes:\n- 4 1/2 tazas de harina\n- 3 huevos\n"
    "- 1 1/2 barritas de mantequilla\n- 1 1/2 cucharaditas de polvo de hornear\n- 1 pizca de sal\n- Leche para amasar\n"
    "- Aceite para freír\nPreparación:\n1. Mezcla la harina con el polvo de hornear y la mantequilla.\n"
    "2. Forma tortillas y córtalas en cuatro.\n3. Fríelas en aceite hasta que estén doradas."
)


def test_a_recipe_is_written_from_its_page_with_its_form_and_the_declared_scaling() -> None:
    writer = _Writer([SCALED])

    reply = writer.compose_user_message(
        "Dame una receta de sopaipillas para 6 personas.", "status", {"situation": _recipe_situation()},
    )

    assert reply == SCALED
    system = writer.requests[0]["messages"][0]["content"]
    assert "multiplica cada cantidad por 1,5" in system
    assert json.loads(writer.requests[0]["messages"][1]["content"])["evidence"]["text"] == SOPAIPILLA_PAGE
    assert writer.requests[0]["max_tokens"] >= 400


def test_a_quantity_the_page_does_not_carry_is_written_again() -> None:
    invented = SCALED.replace("- 3 huevos", "- 3 huevos\n- 200 gramos de azúcar")
    writer = _Writer([invented, SCALED])

    reply = writer.compose_user_message(
        "Dame una receta de sopaipillas para 6 personas.", "status", {"situation": _recipe_situation()},
    )

    assert reply == SCALED
    assert "200" in writer.requests[1]["messages"][-1]["content"]


def test_a_recipe_in_one_sentence_is_written_again_in_its_form() -> None:
    sentence = "Para hacer sopaipillas mezcla 3 tazas de harina con 2 huevos y fríelas en aceite."
    unscaled = SCALED.replace("4 1/2", "3").replace("3 huevos", "2 huevos").replace("1 1/2 barritas", "1 barrita")
    unscaled = unscaled.replace("1 1/2 cucharaditas", "1 cucharadita").replace("es para 6", "es para 4")
    writer = _Writer([sentence, unscaled])

    assert writer.compose_user_message(W02_T1, "status", {"situation": _recipe_situation()}) == unscaled


def test_a_named_page_or_link_is_not_published() -> None:
    writer = _Writer([SCALED + "\nFuente: https://es.wikibooks.org", SCALED])

    assert writer.compose_user_message(
        "Dame una receta de sopaipillas para 6 personas.", "status", {"situation": _recipe_situation()},
    ) == SCALED


def test_when_nothing_could_be_consulted_the_answer_is_from_memory_and_says_so() -> None:
    # M92 (D52): a recipe from memory is a whole one, each ingredient with its quantity.
    silent = "Ingredientes:\n- 2 tazas de harina\n- 500 g de zapallo\nPreparación:\n1. Amasa.\n2. Fríe."
    honest = "No pude comprobarlo; de memoria, puede no ser exacto:\n" + silent
    writer = _Writer([silent, honest])
    situation = {
        "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
        "reason": {"kind": "operation", "operation": "web.search", "polarity": "failure", "verified": False,
                   "succeeded": False, "error": "web_search_unavailable"},
    }

    assert writer.compose_user_message(W02_T1, "error", {"situation": situation}) == honest


def test_a_ranking_is_listed_from_its_table_with_its_figures_only() -> None:
    table = (
        "Estrellas más brillantes\nMagnitud V — Denominación de Bayer — Nombre propio\n0 — −26.73 — Sol\n"
        "1 — −1,47 — α Canis Majoris — Sirio\n2 — −0.72 — α Carinae — Canopus\n3 — −0.05 — α Bootes — Arturo"
    )
    situation = _recipe_situation()
    situation["observed"].update(
        reference="ranking", authority="wikipedia_es_api",
        results=[{"title": "Estrellas más brillantes", "url": "https://es.wikipedia.org/wiki/Anexo:X", "snippet": table}],
    )
    del situation["observed"]["servings"]
    invented = "1. Sirio (−1,47)\n2. Canopus (−0,72)\n3. Betelgeuse (0,42)"
    listed = "1. Sirio (−1,47)\n2. Canopus (−0,72)\n3. Arturo (−0,05)"
    writer = _Writer([invented, listed])

    assert writer.compose_user_message(
        "¿Cuáles son las 3 estrellas más brillantes?", "status", {"situation": situation},
    ) == listed
    assert "0,42" in writer.requests[1]["messages"][-1]["content"]


def test_an_ordinary_search_keeps_its_ordinary_composition() -> None:
    writer = _Writer([])
    situation = _recipe_situation()
    del situation["observed"]["reference"]

    assert writer._compose_consulted_answer(
        "receta de sopaipillas", {}, situation, "es", writer._post, None, "t",
    ) is None
    failure = {"kind": "failure", "reason": {"operation": "web.search", "error": "web_search_unavailable"}}
    # A failed lookup of something that is not a named dish or work is told as usual (not from memory).
    assert writer._compose_consulted_answer(
        "noticias de hoy en Chile", {}, failure, "es", writer._post, None, "t",
    ) is None
    assert writer.requests == []


# ------------------------------------------------------------------ design B: figures


def test_quantities_are_read_with_their_units_and_computed_exactly() -> None:
    stated = quantities.measures(S097)
    # «en realidad» corrects the hour; «1 hora 10 minutos» is one duration of 70 minutes.
    assert [(item.value, item.dimension) for item in stated] == [(Fraction(5000), (1, 0, 0, 0)), (Fraction(4200), (0, 1, 0, 0))]
    value, dimension = quantities.evaluate("5 km / (1 h + 10 min)")
    assert dimension == (1, -1, 0, 0) and round(float(value) * 3.6, 2) == 4.29
    assert quantities.evaluate("round(mean(2, 3, 5), 2)") == (Fraction(333, 100), (0, 0, 0, 0))
    with pytest.raises(ValueError):
        quantities.evaluate("__import__('os')")
    with pytest.raises(ValueError):
        quantities.evaluate("5 km + 3 h")
    facts = quantities.derived_facts(S097)
    assert facts[0][0] == "5 km en 70 min = 4,29 km/h"


@pytest.mark.parametrize(
    ("draft", "request_text", "prior", "vetoed"),
    [
        # F-s097: 4,54 = 5 / 1,1 — the duration misread; the computed speed is 4,29.
        ("Has recorrido 5 kilómetros en 1 hora y 10 minutos, lo que significa que tu velocidad media fue de 4,54 km/h.",
         S097, (), True),
        ("Recorriste 5 km en 1 h 10 min, unos 4,29 km/h.", S097, (), False),
        # F-w12-t3: an average with no numbers to average.
        ("El promedio redondeado a dos decimales es 3,14.", W12_T3, W12, True),
        ("El promedio de 4, 8 y 9 es 7.", "¿cuál es el promedio de 4, 8 y 9?", (), False),
        # Guard: figures that are not derived from the person's quantities are not judged.
        ("Hay 669 números primos entre 1 y 5000.", GUARD[3], (), False),
        ("Un 500 gramos de harina equivalen aproximadamente a 3 1/3 tazas.",
         "cuánto son los 500 gramos de harina en tazas más o menos", (), False),
        ("Para un viaje de 3 a 4 días, lleva ropa cómoda y un cargador.", GUARD[5], (), False),
        ("6 por 7 es 42.", "¿cuánto es 6 por 7?", (), False),
    ],
)
def test_a_talk_reply_with_an_underived_figure_is_vetoed(
    draft: str, request_text: str, prior: tuple[str, ...], vetoed: bool,
) -> None:
    assert bool(quantities.underived_figure(draft, request_text, prior)) is vetoed
    assert _shaped_conversation_answer_violates_contract(draft, request_text, None, prior_requests=prior) is vetoed


class _Chat(LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def test_the_writer_gets_the_calculation_and_a_wrong_figure_is_written_again() -> None:
    wrong = "Has recorrido 5 kilómetros en 1 hora y 10 minutos, a 4,54 km/h."
    right = "Recorriste 5 km en 70 minutos, a unos 4,29 km/h."
    chat = _Chat([wrong, json.dumps({"answer": right}, ensure_ascii=False)])

    reply, _ = chat.chat(S097, conversation_kind="knowledge", response_language="es", temperature=0.0)

    assert reply == right
    first = "\n".join(str(message["content"]) for message in chat.requests[0]["messages"])
    assert "5 km en 70 min = 4,29 km/h" in first
    repair = "\n".join(str(message["content"]) for message in chat.requests[1]["messages"])
    assert "4,54 km/h" in repair and "4,29 km/h" in repair
