"""M118 (2026-10-01, D58): BAXY helps the decider and never loses what it gets right.

Evidence: a per-rule ledger of DEV-D and DEV-F replayed offline with the isolated decider's decision (full3, product
prompt) as the model's output, attributing every change between the isolated decider and the product to the rule that
made it. Each rule with breaks was narrowed to where the model is wrong; the tests use phrasings of our own.

1. Long talk with no order verb the readers know (overheard speech) is read by the contextual decider; only its
   question, when it asks, is the overheard one.
2. The stable-knowledge reader and the public-lookup guard disagreeing is no proof: the contextual decider decides.
3. A rate of what BAXY just said («y eso cuánto sale por metro?») is worked out from its numbers, never searched.
4. «¿Cómo se hace <plato>?» with the kitchen said beside it is a recipe (D35: looked up).
5. A new list named by what it is for is made; only a list named by nothing asks what goes on it.
6. The decider's values: a free text said in other words is said; an enum member named in the person's language is
   that member; a day written with a year of the decider's own is the day said; the words of a message, a note or a
   reminder the decider gave are not replaced by the readers' reading; a value cut at the end is no value.
No test reads the machine's date or hour except through the day the person names.
"""

from __future__ import annotations

from datetime import date

from baxy_mind import __main__ as sidecar
from baxy_mind import llm as llm_module
from baxy_mind.effect_intent import resolve_explicit_clarification_intent
from baxy_mind.planner import PlannerCatalog, enum_member_named, validate_argument_grounding
from baxy_mind.semantic import knowledge, notes, temporal
from baxy_mind.semantic.decider import ContextDecision, said_in_other_words
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.normalize import fold


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


def test_a_named_new_list_is_the_deciders_and_an_unnamed_one_asks() -> None:
    for text in ("crea una lista nueva de regalos de navidad", "make a new list for the beach weekend"):
        assert notes.named_list_creation(fold(text)), text
        # The reader still knows what such a list lacks (asked when the decider refuses it and the surface is re-read).
        intent = resolve_explicit_clarification_intent(text, ("task.create", "note.create"))
        assert intent is not None and intent.missing_fields == ("list_entries",), text
        model = _Decider(ContextDecision(text, "action", ("task.create",), ""))
        result = _turn(text, model)
        assert model.decisions == 1 and result["kind"] == "action" and result["operation"] == "task.create", text
    for text in ("crea una lista nueva", "make a new list for me", "crea una nueva lista para mí"):
        assert not notes.named_list_creation(fold(text)), text
        model = _Decider(ContextDecision(text, "action", ("task.create",), ""))
        result = _turn(text, model)
        assert model.decisions == 0 and result["kind"] == "clarify", text


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
    assert _turn(text, agreed)["kind"] == "conversation" and agreed.decisions == 0
    disagreed = _Decider(ContextDecision(text, "talk", (), ""), public=True)
    result = _turn(text, disagreed)
    assert disagreed.decisions == 1
    assert result["kind"] == "conversation" and result["conversationKind"] == "knowledge"


OVERHEARD = "y entonces el vecino le dijo a mi primo que el auto había quedado en el taller toda la semana pasada"


def test_overheard_talk_is_the_deciders_and_only_its_question_is_the_overheard_one() -> None:
    talk = _Decider(ContextDecision(OVERHEARD, "talk", (), ""))
    result = _turn(OVERHEARD, talk)
    assert talk.decisions == 1 and result["kind"] == "conversation"
    asks = _Decider(ContextDecision(OVERHEARD, "clarify", (), "¿Qué necesitas?"))
    result = _turn(OVERHEARD, asks)
    assert asks.decisions == 1 and result["kind"] == "clarify"
    assert asks.unresolved == ["overheard_speech"] and result.get("preserveObjective") is False
