"""Ronda 24 de uso real, palanca «orden completa se ejecuta sin pregunta ni charla» (tandas r23): a yes/no question that
only says a complete order back is the order (t2-c03#2, t4-c03 t4); a clause opened by a verb of putting something back
is an order, not feedback (t2-c04#4). Each rule with its counter-cases. Every phrasing here is our own or the reviewed
turn's. Revisión 1: the said-back order becomes the decider's action before every guard that judges an action (a pointer
is never the window in front, M19/M118), only when the readers prove an order in the person's words and see it whole;
the dial-hour change (t4-c03 t3) was withdrawn (it moved «de las 8:00 a las 9:00» to 21:00, M58 s019). Revisión 2:
the target turn itself goes through the route (a reason after the order said back), every operation done is one the
question says back, verbs said back in another mood are compared as order heads (never by prefix).
"""

from __future__ import annotations

import pytest

from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue, reading
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.grammar import _COVERAGE_ACTION_HEAD, _head_is
from baxy_mind.semantic.normalize import fold
from baxy_mind import engine_handoff
from baxy_mind import turn_decide
from baxy_mind import direct_arguments
from baxy_mind import argument_payload


# (1) The question that only says the order back.

@pytest.mark.parametrize(
    ("question", "said"),
    [
        ("¿Te gustaría que cierre la configuración ahora mismo?", "ya cierra configuracion que me esta laggeando el valorant"),
        ("¿Quieres que cierre Discord ahora mismo?", "ya cierra discord"),
        ("Do you want me to close Discord now?", "close discord already"),
    ],
)
def test_a_yes_no_question_that_says_the_order_back_asks_nothing(question: str, said: str) -> None:
    assert dialogue.question_only_says_the_order_back(question, said)


@pytest.mark.parametrize(
    ("question", "said"),
    [
        # Two candidate windows: the question names the options.
        ("¿Quieres que cierre Chrome o Word?", "cierra eso"),
        ("¿Quieres que cierre Discord?", "cierra eso"),
        # «súbele un poco» asks how much (owner rule).
        ("¿Cuánto quieres que lo suba?", "súbele un poco"),
        ("¿Cuál es la URL exacta que deseas visitar?", "ábrelo"),
        ("¿Qué quieres que busque?", "busca eso"),
        # Revisión 1: a pointer asks about a referent still unresolved.
        ("¿Quieres que lo cierre?", "ciérralo"),
        ("Do you want me to close it?", "close it"),
        ("¿Quieres que cierre eso?", "cierra eso"),
    ],
)
def test_a_question_that_asks_for_something_stays_a_question(question: str, said: str) -> None:
    assert not dialogue.question_only_says_the_order_back(question, said)


def _tool(name: str, risk: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": risk, "parameters": schema}}


# The risks are the real catalog's (src/Baxy.Kernel/Operations/ProductCatalog.cs).
_CATALOG = PlannerCatalog([
    _tool("app.close", "work_loss"),
    _tool("message.send", "external_communication"),
    _tool("filesystem.path.ensure.absent", "recoverable_delete"),
    _tool("system.power", "work_loss"),
])


def test_the_order_said_back_is_done() -> None:
    assert engine_handoff._operations_the_question_only_says_back(
        "¿Quieres que cierre Discord ahora mismo?", "ya cierra discord", _CATALOG, ("Discord",),
    ) == ("app.close",)


@pytest.mark.parametrize(
    ("question", "said", "operations"),
    [
        # What reaches a person keeps asking.
        ("¿Quieres que le mande a Ron92 que ya llegué?", "mandale a Ron92 que ya llegué", ("message.send",)),
        # What deletes keeps asking.
        ("¿Quieres que borre la carpeta fotos?", "borra la carpeta fotos", ("filesystem.path.ensure.absent",)),
        # Kept on its own route (data: operation_surface.v1.json).
        ("¿Quieres que apague el computador?", "apaga el computador", ("system.power",)),
        # A real question stays one.
        ("¿Quieres que cierre Chrome o Word?", "cierra eso", ("app.close",)),
    ],
)
def test_what_confirms_or_asks_keeps_its_question(question: str, said: str, operations: tuple[str, ...]) -> None:
    assert engine_handoff._operations_the_question_only_says_back(question, said, _CATALOG, ("Discord",)) is None


# (2) Putting something back is an order.

@pytest.mark.parametrize("verb", ["regresa", "devuelve", "devuelvelo", "restablece", "revert", "regresala"])
def test_restore_verbs_are_order_heads(verb: str) -> None:
    assert _head_is(verb, _COVERAGE_ACTION_HEAD)


def test_a_restore_clause_is_not_feedback() -> None:
    assert reading.plain_talk(
        "te dije la escala no el brillo, regresa la escala a 100", effects=None, clarification=None,
    ) is None


@pytest.mark.parametrize(
    "text",
    ["te dije que regresaba mañana", "ya devolvió el paquete el cartero", "el reset de ayer salió bien"],
)
def test_a_restore_word_inside_talk_opens_no_clause(text: str) -> None:
    assert not reading._clause_opens_with_restore(fold(text))


# Revisión 4: «regresa», «devuelve», «restablece» are also the indicative and «reset» a noun; with no thing of the PC
# and no level the clause is talk, as it was before the restore verbs became order heads.
@pytest.mark.parametrize(
    ("text", "act"),
    [
        ("estoy feliz, regresa mi hermano mañana", "statement"),
        ("qué bueno, regresa el sol", "reaction"),
        ("jaja y regresa el profe con la prueba", "reaction"),
        ("me encanta, reset total de mi vida", "statement"),
        ("jaja y regresa en 5 minutos el profe", "reaction"),
    ],
)
def test_a_restore_verb_in_the_indicative_is_still_talk(text: str, act: str) -> None:
    assert not reading._clause_opens_with_restore(fold(text))
    assert reading.plain_talk(text, effects=None, clarification=None) == act


@pytest.mark.parametrize(
    "text",
    ["te dije la escala no el brillo, regresa la escala a 100", "uf, regresa el volumen como estaba",
     "ok, restablece el brillo", "devuelve la ventana a su tamaño", "reset the volume to 50"],
)
def test_a_restore_clause_on_the_pc_or_with_a_level_is_an_order(text: str) -> None:
    assert reading._clause_opens_with_restore(fold(text))


# Revisión 1: the route, with the decider's clarify scripted (harness of test_context_decider_route).

_HISTORY = [{"role": "user", "content": "¿qué hora es?"}, {"role": "assistant", "content": "Son las 17:26."}]


class _Decider:
    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        return self.decision

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        return "", []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return "¿Qué quieres que cierre?"

    def formulate_explicit_clarification_question(self, *_args: object, **_kwargs: object) -> str:
        return "¿Cuánto lo subo?"

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


def _route_tool(name: str, risk: str, properties: dict | None = None, required: list | None = None) -> dict:
    schema = {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": risk, "parameters": schema}}


# Risks and the volume schema are the real catalog's (src/Baxy.Kernel/Operations/ProductCatalog.cs).
_ROUTE_TOOLS = {
    "app.close": _route_tool("app.close", "work_loss"),
    "window.active": _route_tool("window.active", "read_only"),
    "system.time": _route_tool("system.time", "read_only"),
    "audio.volume.adjust": _route_tool(
        "audio.volume.adjust", "low_reversible",
        {"amount": {"type": "integer", "minimum": 1, "maximum": 100},
         "direction": {"type": "string", "enum": ["down", "up"]}},
        ["amount", "direction"],
    ),
}


def _route(text: str, decision: ContextDecision) -> dict:
    return turn_decide._prepare_turn_result(
        {"id": "turn-r24u", "text": text, "history": [*_HISTORY, {"role": "user", "content": text}]},
        llm=_Decider(decision),
        planner_catalog=PlannerCatalog(list(_ROUTE_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=_ROUTE_TOOLS,
        application_names=("Discord",),
    )


@pytest.mark.parametrize(
    ("text", "restated", "question"),
    [
        ("ciérralo", "Cierra la ventana activa.", "¿Quieres que lo cierre?"),
        ("cierra aquello", "Cierra la ventana activa.", "¿Quieres que lo cierre?"),
        ("close it", "Close the active window.", "Do you want me to close it?"),
        # The pointer guard judges the said-back order as it judges the decider's action.
        ("close it", "Close the active window.", "Do you want me to close?"),
        ("ciérralo", "Cierra la ventana activa.", "¿Quieres que cierre?"),
    ],
)
def test_a_pointer_said_back_is_never_the_window_in_front(text: str, restated: str, question: str) -> None:
    result = _route(text, ContextDecision(restated, "clarify", ("app.close",), question))

    assert result["kind"] == "clarify"
    assert result.get("operation") is None


@pytest.mark.parametrize(
    ("text", "question"),
    [
        # Asks for advice, thinks it over, takes it back: no order, whatever the decider's operations.
        ("should I close discord?", "Do you want me to close Discord?"),
        ("¿y si cierro discord?", "¿Quieres que cierre Discord?"),
        ("ya cierra discord, bueno no, mejor no", "¿Quieres que cierre Discord?"),
    ],
)
def test_what_is_no_order_keeps_the_question(text: str, question: str) -> None:
    result = _route(text, ContextDecision("Cierra Discord.", "clarify", ("app.close",), question))

    assert result["kind"] == "clarify"
    assert result.get("operation") is None


def test_an_order_missing_a_required_value_keeps_the_question() -> None:
    # Owner rule H0027: a relative volume change without its amount asks how much.
    result = _route(
        "aumenta el volumen",
        ContextDecision("Aumenta el volumen.", "clarify", ("audio.volume.adjust",), "¿Quieres que aumente el volumen?"),
    )

    assert result["kind"] == "clarify"
    assert result.get("operation") is None


def test_the_complete_order_said_back_is_the_action() -> None:
    result = _route(
        "ya cierra discord",
        ContextDecision("Cierra Discord.", "clarify", ("app.close",), "¿Quieres que cierre Discord ahora mismo?"),
    )

    assert result["kind"] == "action"
    assert result["operation"] == "app.close"


def test_a_bare_said_back_verb_reads_no_order_of_its_own() -> None:
    # Revisión 2: the words said back are read alone; «close» without its object («close it» → «Do you want me to
    # close?») reads no order, so the question stays before the pointer guard (M19/M118, test above) is reached.
    catalog = PlannerCatalog(list(_ROUTE_TOOLS.values()))
    assert engine_handoff._operations_the_question_only_says_back(
        "Do you want me to close?", "close it", catalog, ("Discord",),
    ) is None


class _RecoveringDecider(_Decider):
    def __init__(self, decision: ContextDecision, recovered: str) -> None:
        super().__init__(decision)
        self.recovered = recovered
        self.recoveries = 0

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        self.recoveries += 1
        return self.recovered


def _recovered_route(text: str, recovered: str) -> tuple[dict, _RecoveringDecider]:
    llm = _RecoveringDecider(ContextDecision("Cierra Discord.", "clarify", ("app.close",), ""), recovered)
    result = turn_decide._prepare_turn_result(
        {"id": "turn-r24u-recovered", "text": text, "history": [*_HISTORY, {"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(_ROUTE_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=_ROUTE_TOOLS,
        application_names=("Discord",),
    )
    return result, llm


@pytest.mark.parametrize(
    "recovered",
    # Estabilización T (tandas estab 1 y 2, t4-c03 t4): what the recovery wrote in each run. The recovered question is
    # no reading of the order (it varied run to run and two of three said nothing back); the complete order the decider
    # asked nothing about is done, and the recovery is not consulted (was: done only when the recovery said it back).
    ["¿Quieres que cierre Discord?", "¿Quieres que te avise cuando Discord se cierre?",
     "¿Quieres que te ayude a cerrar Discord ahora mismo?"],
)
def test_the_complete_order_the_decider_asked_nothing_about_is_the_action(recovered: str) -> None:
    result, llm = _recovered_route("ya cierra discord", recovered)

    assert result["kind"] == "action"
    assert result["operation"] == "app.close"
    assert llm.recoveries == 0


def test_the_recovered_question_is_asked_once_when_it_asks_something() -> None:
    result, llm = _recovered_route("¿y si cierro discord?", "¿Quieres que cierre Discord?")

    assert result["kind"] == "clarify"
    assert result["question"] == "¿Quieres que cierre Discord?"
    assert llm.recoveries == 1


# Revisión 2: the target turns through the route, with the decider's operation; verbs compared as order heads.

_FULL_TOOLS = {
    **_ROUTE_TOOLS,
    "app.open": _route_tool("app.open", "low_reversible"),
    "audio.volume": _route_tool(
        "audio.volume", "low_reversible", {"level": {"type": "integer", "minimum": 0, "maximum": 100}}, ["level"],
    ),
}
_APPLICATIONS = ("Discord", "Spotify", "Configuración")


def _full_route(text: str, question: str, operations: tuple[str, ...]) -> dict:
    return turn_decide._prepare_turn_result(
        {"id": "turn-r24u-2", "text": text, "history": [*_HISTORY, {"role": "user", "content": text}]},
        llm=_Decider(ContextDecision(text, "clarify", operations, question)),
        planner_catalog=PlannerCatalog(list(_FULL_TOOLS.values())),
        encoder=lambda _texts: (),
        tool_by_name=_FULL_TOOLS,
        application_names=_APPLICATIONS,
    )


@pytest.mark.parametrize(
    ("text", "question", "operation"),
    [
        # r23 t2-c03#2: the reason after the order is no part of it.
        ("ya cierra configuracion que me esta laggeando el valorant",
         "¿Te gustaría que cierre la configuración ahora mismo?", "app.close"),
        ("ya cierra discord que me esta laggeando el valorant", "¿Quieres que cierre Discord ahora mismo?", "app.close"),
        ("cierra discord porque me laggea", "¿Quieres que cierre Discord?", "app.close"),
        # Revisión 3, contracasos: the «no» of the reason opener is the reason's own, and a reason in English.
        ("cierra discord que ya no lo uso", "¿Quieres que cierre Discord?", "app.close"),
        ("close discord because it lags", "Do you want me to close Discord?", "app.close"),
        # Another mood of the same verb (abre/abra, sube/suba, baja/baje, pon/ponga).
        ("abre spotify", "¿Quieres que abra Spotify?", "app.open"),
        ("sube el volumen al 50", "¿Quieres que suba el volumen al 50?", "audio.volume"),
        ("baja el volumen al 20", "¿Quieres que baje el volumen al 20?", "audio.volume"),
        ("pon el volumen al 50", "¿Quieres que ponga el volumen al 50?", "audio.volume"),
    ],
)
def test_the_order_said_back_is_done_through_the_route(text: str, question: str, operation: str) -> None:
    result = _full_route(text, question, (operation,))

    assert result["kind"] == "action"
    assert result["operation"] == operation
    assert result["effectOperations"] == [operation]


@pytest.mark.parametrize(
    ("text", "question", "operations"),
    [
        # The readers read one more order than the question says back («y spotify»): nothing is done unasked.
        ("cierra discord y spotify", "¿Quieres que cierre Discord?", ("app.close",)),
        # What follows says which window, not why.
        ("cierra la ventana que dice error", "¿Quieres que cierre la ventana?", ("app.close",)),
        # Taken back after the order.
        ("ya cierra discord que me laggea, bueno no, mejor no", "¿Quieres que cierre Discord?", ("app.close",)),
        # Revisión 3: taken back without a pause, as voice says it.
        ("ya cierra discord que me esta laggeando el valorant bueno no mejor no", "¿Quieres que cierre Discord?",
         ("app.close",)),
        ("cierra discord que me esta laggeando o mejor no", "¿Quieres que cierre Discord?", ("app.close",)),
        ("cierra discord que me lo pidio mi mama pero no lo cierres todavia", "¿Quieres que cierre Discord?",
         ("app.close",)),
        ("close discord because it lags but not yet", "Do you want me to close Discord?", ("app.close",)),
        ("close discord because it lags but don't do it yet", "Do you want me to close Discord?", ("app.close",)),
        # The decider's operation is not the one the words said back read.
        ("ya cierra discord que me esta laggeando el valorant", "¿Quieres que cierre Discord?", ("app.open",)),
    ],
)
def test_what_the_question_does_not_say_back_keeps_it(text: str, question: str, operations: tuple[str, ...]) -> None:
    result = _full_route(text, question, operations)

    assert result["kind"] == "clarify"
    assert result.get("operation") is None
    assert not result.get("effectOperations")


@pytest.mark.parametrize(
    ("question", "said"),
    [
        # Same first letters, another verb: the prefix rule took «descarte» for «descarga», «cierro» for «cierra».
        ("¿Quieres que descarte el archivo?", "descarga el archivo"),
        ("¿Quieres que cierre Discord?", "¿y si cierro discord?"),
        ("¿Quieres que configure la pantalla?", "cierra la configuracion de pantalla"),
    ],
)
def test_another_verb_with_the_same_start_is_not_said_back(question: str, said: str) -> None:
    assert not dialogue.question_only_says_the_order_back(question, said)


@pytest.mark.parametrize(
    "rest",
    [" y spotify", ", bueno no, mejor no", " que dice error", " en la otra pantalla", " que me laggea, bueno no, mejor no"],
)
def test_only_a_reason_may_follow_the_order_said_back(rest: str) -> None:
    assert not dialogue.only_gives_a_reason(rest)


@pytest.mark.parametrize(
    "rest",
    [
        " que me esta laggeando el valorant bueno no mejor no",
        " que me esta laggeando o mejor no",
        " que me lo pidio mi mama pero no lo cierres todavia",
        " because it lags but not yet",
        " porque me laggea mejor dejalo",
        " because it lags or don't",
    ],
)
def test_a_reason_that_takes_the_order_back_without_a_pause_is_no_reason(rest: str) -> None:
    assert dialogue.takes_the_order_back(rest)
    assert not dialogue.only_gives_a_reason(rest)


@pytest.mark.parametrize(
    "rest",
    ["", "?", " que me esta laggeando el valorant", " porque me laggea", " because it lags", " que ya no lo uso",
     " porque nomas me laggea", " because it's slowing down my game"],
)
def test_a_reason_after_the_order_said_back(rest: str) -> None:
    # Contracasos de la revisión 3: «que ya no» opens the reason, and words that only contain «no» or «o» («nomás»,
    # «slowing», «down») take nothing back.
    assert not dialogue.takes_the_order_back(rest)
    assert dialogue.only_gives_a_reason(rest)


@pytest.mark.parametrize("rest", [" por favor", " ahora", ""])
def test_what_takes_nothing_back_after_the_whole_order(rest: str) -> None:
    assert not dialogue.takes_the_order_back(rest)


# Revisión 2, punto 3 (r23 t3-c17 t4): a search that points back is filled with the subject of the last answer, and a
# search verb never asks for an address.

_BELGIUM = (
    "La invasión de Bélgica por Alemania fue la violación directa de la neutralidad belga que obligó a Francia a entrar "
    "en guerra, cumpliendo así el Plan Schlieffen."
)


def test_the_subject_of_an_answer_is_what_it_says_something_is() -> None:
    assert dialogue.answer_subject(_BELGIUM) == "La invasión de Bélgica por Alemania"
    assert dialogue.answer_subject("The Treaty of Versailles was signed in 1919.") == "The Treaty of Versailles"


# Revisión 3: an answer that says BAXY does not know, or speaks of the question, names no thing to look up.
_SAYS_NOTHING = (
    "No estoy seguro de quién fue el autor de ese libro.",
    "No lo sé con certeza, pero creo que fue en 1914.",
    "Eso que preguntas es complicado de responder.",
    "Creo que la guerra fue en 1914.",
    "Lo que tienes abierto es Discord.",
    "Estoy casi seguro de la fecha: fue en 1914.",
    "Not sure who the author was.",
)


@pytest.mark.parametrize("reply", _SAYS_NOTHING)
def test_an_answer_that_says_it_does_not_know_has_no_subject(reply: str) -> None:
    assert dialogue.answer_subject(reply) is None


@pytest.mark.parametrize(
    ("reply", "subject"),
    [
        # The opening interjection is no part of the subject.
        ("Claro, la Primera Guerra Mundial fue un conflicto global.", "la Primera Guerra Mundial"),
        ("¡Claro! La Primera Guerra Mundial fue un conflicto global.", "La Primera Guerra Mundial"),
        ("Sure, the Treaty of Versailles was signed in 1919.", "the Treaty of Versailles"),
        # Contracasos: the opener without a mark is a word of the name; «noche» holds no refusal; a plural in «-as» is
        # no second person.
        ("Claro de Luna de Debussy es una pieza para piano.", "Claro de Luna de Debussy"),
        ("La Noche de los Cristales Rotos fue un pogromo.", "La Noche de los Cristales Rotos"),
        ("La batalla de las Termópilas fue en el 480 a. C.", "La batalla de las Termópilas"),
    ],
)
def test_the_subject_without_what_opens_the_answer(reply: str, subject: str) -> None:
    assert dialogue.answer_subject(reply) == subject


@pytest.mark.parametrize("reply", _SAYS_NOTHING)
def test_a_search_that_points_back_at_an_answer_that_does_not_know_asks_what(reply: str) -> None:
    assert _answered("quien escribio ese libro", reply).searched_in_place("buscalo en google") is None


def test_a_search_that_points_back_past_the_opener() -> None:
    state = _answered("cuando fue la primera guerra", "Claro, la Primera Guerra Mundial fue entre 1914 y 1918.")

    assert state.searched_in_place("buscalo en google") == "busca en google la Primera Guerra Mundial"


@pytest.mark.parametrize(
    "reply",
    [
        "Son las 17:26.",
        "1. El bloqueo naval alemán. 2. La invasión de Bélgica por Alemania.",
        "Te di 3 elementos, no 7 ni 4.",
        "La respuesta es 42.",
        "Tu alarma es a las 7:00.",
        "Abrí Discord.",
        "",
    ],
)
def test_an_answer_with_no_thing_it_is_about_has_no_subject(reply: str) -> None:
    assert dialogue.answer_subject(reply) is None


# Revisión 4: a subject that values, ranks or comments instead of naming is no thing to look up.
_VALUES_INSTEAD_OF_NAMING = (
    "La causa más común es la falta de memoria RAM, que obliga al juego a usar el disco.",
    "La solución más rápida es cerrar los programas en segundo plano.",
    "Una buena opción es reinstalar los drivers.",
    "Lo más importante es mantener los drivers al día.",
    "El problema más probable es tu conexión.",
    "The best option is to restart the router.",
    "Lamentablemente esa información es privada.",
    "Ninguna aplicación es perfecta.",
    "La causa común es la memoria.",
    "Probably the router is the problem.",
)


@pytest.mark.parametrize("reply", _VALUES_INSTEAD_OF_NAMING)
def test_an_answer_whose_subject_values_instead_of_naming_has_no_subject(reply: str) -> None:
    assert dialogue.answer_subject(reply) is None


@pytest.mark.parametrize("reply", _VALUES_INSTEAD_OF_NAMING)
def test_a_search_that_points_back_at_a_valuation_asks_what(reply: str) -> None:
    state = _answered("por que me laggea el valorant", reply)

    assert state.searched_in_place("búscalo en google") is None


@pytest.mark.parametrize(
    ("reply", "subject"),
    [
        # Contracasos: a generic head with what names it, and words of a proper name.
        ("La causa de la Primera Guerra Mundial fue el asesinato de Francisco Fernando.",
         "La causa de la Primera Guerra Mundial"),
        ("Buenos Aires es la capital de Argentina.", "Buenos Aires"),
        ("La ciudad de Buenos Aires es la capital de Argentina.", "La ciudad de Buenos Aires"),
        ("El Día de Todos los Santos es el 1 de noviembre.", "El Día de Todos los Santos"),
    ],
)
def test_a_named_subject_survives_the_valuation_check(reply: str, subject: str | None) -> None:
    assert dialogue.answer_subject(reply) == subject


def _answered(request: str, reply: str, operations: tuple[str, ...] = ()) -> dialogue.DialogueState:
    state = dialogue.DialogueState()
    state.expect(request, operations)
    state.said(reply)
    return state


def test_a_search_that_points_back_looks_up_the_subject_of_the_last_answer() -> None:
    state = _answered("explicame mejor la segunda", _BELGIUM)

    assert state.searched_in_place("buscalo en google pa poder citarlo") == (
        "busca en google La invasión de Bélgica por Alemania"
    )


@pytest.mark.parametrize(
    ("request_text", "reply", "operations", "said"),
    [
        # It names its own thing to look up.
        ("explicame mejor la segunda", _BELGIUM, (), "busca en google recetas de arepas"),
        # Forbids the search.
        ("explicame mejor la segunda", _BELGIUM, (), "no lo busques en google"),
        # The last answer is about no thing.
        ("qué hora es", "Son las 17:26.", (), "buscalo en google"),
        # The last turn was an operation, not an answer in conversation (and nothing was searched).
        ("abre discord", "La ventana de Discord es la que está al frente.", ("app.open",), "buscalo en google"),
    ],
)
def test_no_subject_fills_a_search_that_does_not_point_at_an_answer(
    request_text: str, reply: str, operations: tuple[str, ...], said: str,
) -> None:
    assert _answered(request_text, reply, operations).searched_in_place(said) is None


@pytest.mark.parametrize(
    "text",
    ["buscalo en google pa poder citarlo", "busca recetas de arepas", "search for it on google", "googlea eso"],
)
def test_a_search_verb_asks_to_search(text: str) -> None:
    assert dialogue.asks_to_search(text)


@pytest.mark.parametrize("text", ["abre la página del banco", "ve a youtube.com", "open my bank's website"])
def test_going_to_a_page_is_no_search(text: str) -> None:
    assert not dialogue.asks_to_search(text)


class _AskingForTheUrl:
    def __init__(self) -> None:
        self.asked: list[dict] = []

    def extract_direct_arguments(self, *_args: object, **_kwargs: object) -> object:
        return argument_payload.DirectArgumentExtraction(
            arguments=None, evidence=(), fallback_question="¿Cuál es la URL exacta?",
        )

    def formulate_missing_argument_question(self, *_args: object, **kwargs: object) -> str:
        self.asked.append(dict(kwargs))
        return "¿Qué quieres que busque?" if kwargs.get("ask_as") else "¿Cuál es la URL exacta que deseas visitar?"


_NAVIGATE = _route_tool(
    "browser.navigate", "external_communication",
    {"url": {"type": "string", "x-maxUtf8Bytes": 2048, "x-nonWhitespace": True}}, ["url"],
)


def _navigate_arguments(text: str) -> tuple[dict | None, str, _AskingForTheUrl]:
    llm = _AskingForTheUrl()
    arguments, question = direct_arguments._direct_arguments_result(
        {"operation": "browser.navigate", "text": text, "history": [{"role": "user", "content": text}]},
        llm=llm,
        tool=_NAVIGATE,
        dialogue_state=dialogue.DialogueState(),
    )
    return arguments, question, llm


def test_a_search_verb_never_asks_for_an_address() -> None:
    arguments, question, llm = _navigate_arguments("buscalo en google pa poder citarlo")

    assert arguments is None
    assert question == "¿Qué quieres que busque?"
    assert "url" in llm.asked[-1]["ask_as"]


def test_going_to_a_page_still_asks_for_its_address() -> None:
    arguments, question, llm = _navigate_arguments("abre la página del banco")

    assert arguments is None
    assert not any(asked.get("ask_as") for asked in llm.asked)


def test_the_search_that_points_back_goes_through_the_route_with_the_subject() -> None:
    text = "buscalo en google pa poder citarlo"
    tools = {**_ROUTE_TOOLS, "browser.navigate": _NAVIGATE}
    result = turn_decide._prepare_turn_result(
        {"id": "turn-r24u-c17", "text": text, "history": [
            {"role": "user", "content": "explicame mejor la segunda"},
            {"role": "assistant", "content": _BELGIUM},
            {"role": "user", "content": text},
        ]},
        llm=_Decider(ContextDecision("Buscalo en Google para poder citarlo.", "action", ("browser.navigate",), "")),
        planner_catalog=PlannerCatalog(list(tools.values())),
        encoder=lambda _texts: (),
        tool_by_name=tools,
        application_names=("Discord",),
        dialogue_state=_answered("explicame mejor la segunda", _BELGIUM),
    )

    assert result["kind"] == "action"
    assert result["operation"] == "browser.navigate"
    assert result["objective"] == "busca en google La invasión de Bélgica por Alemania"
    arguments, question, _llm = _navigate_arguments(result["objective"])
    assert question == ""
    assert arguments is not None and arguments["url"].startswith("https://www.google.com/search?q=")
    assert "B%C3%A9lgica" in arguments["url"] or "Belgica" in arguments["url"]
