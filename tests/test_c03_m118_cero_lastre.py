"""M118 (2026-10-01, D58): BAXY helps the decider and never loses what it gets right.

Evidence: a per-rule ledger of DEV-D and DEV-F replayed offline with the isolated decider's decision (full3, product
prompt) as the model's output, attributing every change between the isolated decider and the product to the rule that
made it. Each rule with breaks was narrowed to where the model is wrong; the tests use phrasings of our own.

1. Long talk with no order verb the readers know (overheard speech) asks the overheard question before the decider
   (M123: safety exception to D58; a request said to BAXY with words of its own is not overheard).
2. The stable-knowledge reader and the public-lookup guard disagreeing is no proof: the contextual decider decides.
3. A rate of what BAXY just said («y eso cuánto sale por metro?») is worked out from its numbers, never searched.
4. «¿Cómo se hace <plato>?» with the kitchen said beside it is a recipe (D35: looked up).
5. A new list named by what it is for is made; D59.5 (owner, 2026-10-02): a list named by nothing is made empty too.
6. The decider's values: a free text said in other words is said; an enum member named in the person's language is
   that member; a day written with a year of the decider's own is the day said; the words of a message, a note or a
   reminder the decider gave are not replaced by the readers' reading; a value cut at the end is no value.
No test reads the machine's date or hour except through the day the person names.
"""

from __future__ import annotations

from datetime import date

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm as llm_module
from baxy_mind.effect_intent import resolve_explicit_clarification_intent
from baxy_mind.planner import PlannerCatalog, enum_member_named, validate_argument_grounding
from baxy_mind.semantic import knowledge, notes, temporal
from baxy_mind.semantic.decider import ContextDecision, said_in_other_words
from baxy_mind.semantic.dialogue import DialogueState


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _tool(name: str, schema: dict) -> dict:
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


PLAY_QUERY = _schema(
    {"provider": {"type": "string", "enum": ["spotify", "youtube"]}, "query": {"type": "string", "maxLength": 512}},
    ["provider", "query"],
)
NOTE_CREATE = _schema(
    {"content": {"type": "string", "x-maxUtf8Bytes": 65536}, "title": {"type": "string", "x-maxUtf8Bytes": 1024}},
    ["content", "title"],
)
TASK_CREATE = _schema(
    {
        "details": {"type": "string", "x-maxUtf8Bytes": 65536},
        "due": {"type": ["null", "string"], "maxLength": 64},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    ["title"],
)
FOLDER_OPEN = _schema({"folder": {"type": "string", "enum": ["desktop", "documents", "downloads"]}}, ["folder"])


class _Abstains:
    """The model stand-in of the arguments step: the extraction abstains, a question is a fixed marker."""

    def extract_direct_arguments(self, *_a, **_k):
        return llm_module.DirectArgumentExtraction(arguments=None, evidence=(), fallback_question="¿qué?")

    def formulate_missing_argument_question(self, *_a, **_k):
        return "¿qué falta?"

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _arguments(operation: str, schema: dict, request: str, decided: dict, history: list[dict]) -> dict | None:
    sidecar._remember_decided_arguments(request, (operation,), tuple(sorted(decided.items())))
    arguments, _question = sidecar._direct_arguments_result(
        {"type": "arguments", "operation": operation, "text": request, "history": history},
        llm=_Abstains(), tool=_tool(operation, schema), dialogue_state=DialogueState(),
    )
    return arguments


# ------------------------------------------------------------------ 6. the decider's values


def test_a_text_said_in_other_words_is_said_and_an_invented_one_is_not() -> None:
    said = ["oye, pon algo de jazz tranqui pa relajarme un rato"]
    assert said_in_other_words("jazz tranquilo para relajarse", said)
    # A name or a number nobody said is the decider's, not the person's.
    assert not said_in_other_words("jazz tranquilo de Miles Davis", said)
    assert not said_in_other_words("jazz tranquilo durante 45 minutos", said)
    # Words nobody said are no restatement.
    assert not said_in_other_words("rock pesado alemán", said)


def test_what_was_said_literally_counts_inside_a_restatement() -> None:
    said = ["guárdalo en una nota que se llame router", "Tu puerta de enlace es 10.0.0.1 y la red se llama Casa-5G."]
    assert said_in_other_words("La puerta de enlace del router es 10.0.0.1", said)


def test_the_decided_query_in_other_words_reaches_the_arguments() -> None:
    request = "Pon jazz tranquilo para relajarse en Spotify."
    history = [{"role": "user", "content": "oye, pon algo de jazz tranqui pa relajarme un rato en spotify"}]
    arguments = _arguments(
        "media.play.query", PLAY_QUERY, request, {"provider": "Spotify", "query": "jazz tranquilo para relajarse"}, history,
    )
    assert arguments == {"provider": "spotify", "query": "jazz tranquilo para relajarse"}


def test_the_note_keeps_the_deciders_words_over_the_readers_quotes() -> None:
    request = "Crea una nota titulada «Taller» con el texto «Cambio de aceite: 45.000 pesos»."
    history = [
        {"role": "user", "content": "¿cuánto sale un cambio de aceite en un taller por acá?"},
        {"role": "assistant", "content": "Según lo que encontré, «Cambio de aceite: 45.000 pesos» en los talleres de la zona."},
        {"role": "user", "content": "pásalo a una nota que se llame taller"},
    ]
    arguments = _arguments(
        "note.create", NOTE_CREATE, request, {"title": "Taller", "content": "Cambio de aceite: 45.000 pesos"}, history,
    )
    assert arguments is not None
    assert "«" not in arguments["content"] and "45.000" in arguments["content"]


def test_a_member_named_in_the_persons_language_is_that_member() -> None:
    enum = ["desktop", "documents", "downloads"]
    assert enum_member_named("Descargas", enum) == "downloads"
    assert enum_member_named("Escritorio", enum) == "desktop"
    assert enum_member_named("Documents", enum) == "documents"
    assert enum_member_named("Imágenes", enum) is None
    assert sidecar._decided_value("Descargas", FOLDER_OPEN["properties"]["folder"]) == "downloads"
    # A file «bajado» was downloaded: the folder the decider named is said.
    assert validate_argument_grounding({"folder": "downloads"}, FOLDER_OPEN, "¿dónde quedó el informe.pdf? lo bajé ayer")
    assert not validate_argument_grounding({"folder": "downloads"}, FOLDER_OPEN, "¿dónde quedó el informe.pdf?")


def test_the_day_said_takes_the_year_the_person_means() -> None:
    today = date(2027, 3, 3)
    assert temporal.said_day_of("2025-04-20", "paga la patente antes del 20 de abril", today=today) == "2027-04-20"
    assert temporal.said_day_of("2025-04-21", "paga la patente antes del 20 de abril", today=today) is None
    assert temporal.said_day_of("el viernes", "paga la patente antes del 20 de abril", today=today) is None


def test_a_value_left_open_at_the_end_is_cut() -> None:
    contract = {"type": "string", "x-maxUtf8Bytes": 65536}
    assert sidecar._decided_value("for x in lista:\n    if \n", contract) is None
    assert sidecar._decided_value("Comprar pan y leche", contract) == "Comprar pan y leche"


# ------------------------------------------------------------------ 5. a new list named by what it is for


def test_a_new_list_named_or_not_is_made_empty() -> None:
    # D59.5 (owner, 2026-10-02): the readers make the new list empty (titled as named, «Lista nueva» when not) and the
    # final offers to add things; nothing is asked and the decider is not needed.
    for text, title in (
        ("crea una lista nueva de regalos de navidad", "Lista de regalos de navidad"),
        ("make a new list for the beach weekend", "List for the beach weekend"),
        ("crea una lista nueva", "Lista nueva"),
        ("make a new list for me", "New list"),
        ("crea una nueva lista para mí", "Lista nueva"),
    ):
        assert notes.new_list_title(text) == title, text
        assert resolve_explicit_clarification_intent(text, ("task.create", "note.create")) is None, text
        model = _Decider(ContextDecision(text, "clarify", (), ""))
        result = _turn(text, model)
        assert model.decisions == 0 and result["kind"] == "action" and result["operation"] == "task.create", text


# ------------------------------------------------------------------ 3. a rate of what BAXY just said


def test_a_rate_of_what_baxy_said_is_worked_out_not_searched() -> None:
    reply = "La reja para 12 metros sale 960.000 pesos instalada."
    assert knowledge.rate_of_what_was_said("¿y eso cuánto es por metro?", reply)
    assert knowledge.reference_lookup("¿y eso cuánto es por metro?", (), reply) is None
    # «por favor» is no unit; with no numbers said before, nothing is worked out.
    assert not knowledge.rate_of_what_was_said("¿y eso cuánto es, por favor?", reply)
    assert not knowledge.rate_of_what_was_said("¿y eso cuánto es por metro?", "La reja quedó instalada.")


# ------------------------------------------------------------------ 4. a dish asked how it is made


def test_how_a_dish_is_made_with_the_kitchen_beside_it_is_a_recipe() -> None:
    found = knowledge.reference_lookup("¿cómo se hace el charquicán? lo quiero llevar al asado del sábado")
    assert found is not None and found.kind == "recipe" and found.subject == "charquican"
    found = knowledge.reference_lookup("how do you make pancakes? I only have eggs and flour")
    assert found is not None and found.kind == "recipe"
    # Without the kitchen it is an explanation, not a recipe.
    assert knowledge.reference_lookup("¿cómo se hace una transferencia bancaria?") is None


# ------------------------------------------------------------------ 1–2. readings that preempt the decider


class _Decider:
    """The model of a whole turn: the decider answers what it is given; the guards answer as told."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision, *, public: bool = False) -> None:
        self.decision = decision
        self.public = public
        self.decisions = 0
        self.unresolved: list[str] = []

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        return self.decision

    def public_lookup_requested(self, _text):
        return self.public

    def _verify_semantic_effect_shape(self, _text):
        return "complete", "one"

    def clarify_unresolved_input(self, _text, kind, **_k):
        self.unresolved.append(kind)
        return "En eso no encuentro un pedido para mí; ¿necesitas algo?"

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Qué pongo en la lista?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué quieres que haga?"

    def chat(self, *_a, **_k):
        return "Respuesta.", []

    def prepare_chat(self, *_a, **_k):
        return None

    def detect_response_language(self, _text):
        return "es"

    def consume_deferred_response_language(self, _text):
        return True, None

    def retire_deferred_response_language(self, _text):
        return None

    def __getattr__(self, name):
        def missing(*_a, **_k):
            raise RuntimeError(f"no {name} here")
        return missing


def _turn(text: str, model: _Decider) -> dict:
    tools = {name: _tool(name, _schema({}, [])) for name in ("web.search", "network.ping", "task.create")}
    return sidecar._prepare_turn_result(
        {"id": "m118", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )


def test_the_stable_reader_and_the_lookup_guard_disagreeing_is_the_deciders() -> None:
    text = "¿cuál es la diferencia entre un mamífero y un reptil?"
    agreed = _Decider(ContextDecision(text, "talk", (), ""), public=False)
    # M123 (D58): a stable-knowledge reading no longer closes a turn before the decider, guard or not.
    assert _turn(text, agreed)["kind"] == "conversation" and agreed.decisions == 1
    disagreed = _Decider(ContextDecision(text, "talk", (), ""), public=True)
    result = _turn(text, disagreed)
    assert disagreed.decisions == 1
    assert result["kind"] == "conversation" and result["conversationKind"] == "knowledge"


OVERHEARD = "y entonces el vecino le dijo a mi primo que el auto había quedado en el taller toda la semana pasada"


def test_overheard_talk_is_asked_about_before_the_decider_and_never_acted_on() -> None:
    # M123 (safety exception to D58, the 742 reviewed literals: H0735 scheduled a notification out of a TV
    # dialogue, nine more were answered as talk): talk addressed to someone else asks the overheard question,
    # whatever the decider would read in it.
    for decision in (ContextDecision(OVERHEARD, "talk", (), ""),
                     ContextDecision(OVERHEARD, "action", ("task.create",), ""),
                     ContextDecision(OVERHEARD, "clarify", (), "¿Qué necesitas?")):
        model = _Decider(decision)
        result = _turn(OVERHEARD, model)
        assert model.decisions == 0 and result["kind"] == "clarify" and result["effectOperations"] == []
        assert model.unresolved == ["overheard_speech"]


def test_after_earlier_turns_overheard_talk_is_still_never_acted_on() -> None:
    model = _Decider(ContextDecision(OVERHEARD, "action", ("task.create",), ""))
    result = sidecar._context_decided_result(
        {"id": "m123", "text": OVERHEARD, "history": [{"role": "user", "content": OVERHEARD}]},
        llm=model, planner_catalog=PlannerCatalog([_tool("task.create", _schema({}, []))]), overheard=True,
    )
    assert result["kind"] == "clarify" and result["effectOperations"] == []
    assert model.unresolved == ["overheard_speech"]


@pytest.mark.parametrize("text", [
    # M118's DEV-D/F requests (our phrasings): an order with the listener's «me», help asked, a wish to watch, a
    # piece of writing ordered — said to BAXY, never overheard.
    "bueno pues mira nada que hazme un ping al router de casa porque el juego online me va fatal desde esta mañana",
    "I am bored tonight and I really need your help to search for a good sci-fi film like the ones with robots in it",
    "I'd like to watch a documentary called Planet Earth with English subtitles on the big screen in the living room",
    "Elabora una lista con los inventos más famosos del siglo veinte indicando quién los creó y en qué año aparecieron",
])
def test_a_long_request_said_to_baxy_is_not_overheard(text: str) -> None:
    assert sidecar._unresolved_input_kind(text, ()) != "overheard_speech"


# ------------------------------------------------------------------ 7–10. after the decider (later tandas of M118)


def _follow(text: str, history: list[tuple[str, str]], model: _Decider) -> dict:
    names = ("app.close", "window.active", "audio.volume", "task.create", "memory.save", "memory.recall", "memory.list",
             "calendar.event.list", "web.search")
    tools = [_tool(name, _schema({}, [])) for name in names]
    turns = [{"role": role, "content": content} for role, content in history]
    return sidecar._context_decided_result(
        {"id": "m118", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(tools),
    )


CHAT = [("user", "explícame qué es un router, una frase"), ("assistant", "Un router reparte la conexión entre tus equipos.")]


def test_a_pronoun_is_never_the_window_in_front() -> None:
    # cien-113 008 «cierra aquello» → «Cierra la ventana activa.» → app.close of the Notepad in front (safety).
    for text, restated in (("cierra aquello", "Cierra la ventana activa."), ("ciérralo ya", "Cierra la aplicación activa."),
                           ("close that one", "Close the active window."), ("shut it", "Close the current window.")):
        result = _follow(text, CHAT, _Decider(ContextDecision(restated, "action", ("app.close",), "")))
        assert result["kind"] == "clarify" and result["effectOperations"] == [], text
    # An application opened just before is what the pronoun closes, by its name.
    opened = [("user", "abre la calculadora"), ("assistant", "Abrí la Calculadora.")]
    result = _follow("ciérrala", opened, _Decider(ContextDecision("Cierra la calculadora.", "action", ("app.close",), "")))
    assert result["kind"] == "action" and result["operation"] == "app.close"


def test_do_that_with_nothing_named_is_asked_never_refused() -> None:
    # cien-113 048 «haz eso» after «keep chatting without opening apps» → a false limit on chatting.
    history = [("user", "sigue charlando sin abrir nada"), ("assistant", "Claro, seguimos conversando sin abrir programas.")]
    for text in ("haz eso", "do that", "ok, haz esto ahora"):
        for decision in ("talk", "limit"):
            result = _follow(text, history, _Decider(ContextDecision(text, decision, (), "")))
            assert result["kind"] == "clarify", (text, decision)
    # After an offer of BAXY's, «haz eso» answers it: the decider's reading stands.
    offered = [("user", "qué tal el clima"), ("assistant", "No lo sé sin mirar. ¿Quieres que lo busque?")]
    result = _follow("haz eso", offered, _Decider(ContextDecision("Busca el clima.", "action", ("web.search",), "")))
    assert result["kind"] == "action"


def test_a_remate_of_what_was_just_done_is_not_asked_again() -> None:
    # Owner script t57 «al volumen» after the volume set to 100 → «¿Cuánto le subo?».
    done = [("user", "déjalo en 80"), ("assistant", "Dejé el volumen en 80 y el sonido no está silenciado.")]
    for text in ("al volumen", "el volumen", "sonido"):
        result = _follow(text, done, _Decider(ContextDecision(text, "clarify", (), "¿Cuánto le subo?")))
        assert result["kind"] == "conversation", text
    # A new value, or what BAXY did not report, is still the decider's question.
    for text in ("el brillo", "volumen 90"):
        result = _follow(text, done, _Decider(ContextDecision(text, "clarify", (), "¿Qué hago con eso?")))
        assert result["kind"] == "clarify", text


def test_memory_is_only_what_the_person_asks_of_it() -> None:
    for text in ("acuérdate que mi equipo favorito es el Colo-Colo", "remember that I take my tea without sugar",
                 "guardá que mi sobrina se llama Pía", "¿qué recuerdas de mis gustos?", "olvida que soy vegetariano",
                 "me gustaría que recordases que odio el cilantro"):
        result = _follow(text, CHAT, _Decider(ContextDecision(text, "action", ("memory.save",), "")))
        assert result["kind"] == "action" and result["operation"] == "memory.save", text
    # Questions about the person's contacts, plans or friends are not BAXY's memory: they are asked.
    for text in ("cuántos de mis amigos viven en Valdivia", "dame el teléfono de la Coni", "qué planes tengo con mi primo"):
        result = _follow(text, CHAT, _Decider(ContextDecision(text, "action", ("memory.recall",), "")))
        assert result["kind"] == "clarify" and result["effectOperations"] == [], text
    # A personal fact said without asking to keep it is asked about before it is kept.
    text = "el santo de mi abuela es el 3 de junio"
    result = _follow(text, CHAT, _Decider(ContextDecision(text, "action", ("memory.save",), "")))
    assert result["kind"] == "clarify"
    # What else the decider chose stands without the memory step.
    text = "anota comprar pan"
    result = _follow(text, CHAT, _Decider(ContextDecision(text, "action", ("task.create", "memory.save"), "")))
    assert result["kind"] == "action" and result["operation"] == "task.create"


def test_the_writer_never_denies_talking_to_a_go_ahead() -> None:
    from baxy_mind.llm import _go_ahead_reply_unmet

    assert _go_ahead_reply_unmet("No lo he hecho: no tengo la capacidad de mantener conversaciones sin abrir programas.", "dale")
    assert _go_ahead_reply_unmet("I have not done it: I can't have conversations without opening apps.", "go ahead")
    assert not _go_ahead_reply_unmet("Todavía no lo hice: antes hay que iniciar sesión en el servicio.", "dale")
