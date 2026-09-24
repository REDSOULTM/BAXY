"""Tanda 4 (2026-09-24, official window): four mechanisms that answered the wrong way.

A. A question for information about the world reached the limit («¿cuál es la edad promedio…?» → «Eso no lo
   hago.»): the decider proposed a web search, the domain gate withdrew it, and the retired-effect guard kept the
   limit as if a reading of this machine had been withdrawn. A withdrawn public lookup observed nothing of this
   machine; the question is answered (or looked up). A question about a far place is answered too.
B. A fact that changes was recited («¿cuántas copas mundiales tiene Argentina?» → «2»): tallies of what is won or
   held, populations, prices, current holders, records, the last and the next edition are looked up.
C. «No pude entender bien la solicitud…» was published: BAXY's own first-person limit («No reanudo la lectura…»,
   «No leo libros en voz alta») failed both the limit contract and the composer's boundary check, the recovery
   asked the person to say it again, and a maker the person named was taken for one BAXY invented.
D. «spell potato» → «Potato.»: spelling is answered with the letters.

Every phrasing here is a paraphrase none of the fixes names.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import (
    _conversation_presentation_shape,
    _names_the_boundary,
    _reading_fold,
    _shaped_conversation_answer_violates_contract,
    _shaped_presentation_text,
    _unsupported_answer_contract_failure,
    spelling_word,
)
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.patterns import out_of_world_request
from baxy_mind.semantic.reading import read
from baxy_mind.semantic.web import asks_for_information, record_fact_query
from test_c03_pointless_questions import _NoEvidence, _tool

# ------------------------------------------------------------------ A. a world question is never a limit

_OPERATIONS = ("web.search", "system.time", "app.open", "media.play.query", "note.create")


class _WithdrawnSearchLlm:
    """The decider of the real run: a web search (or «unsupported»), the lookup guard says it is not a lookup."""

    def __init__(self, *, refuses: bool = False) -> None:
        self.refuses = refuses
        self.kinds: list[object] = []

    def decide_turn(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        if self.refuses:
            return {
                "mode": "conversation", "operation": None, "question": "", "conversation_kind": "unsupported",
                "effect_count": "zero", "effect_operations": [], "effect_verification": "not_applicable",
                "response_language": "es",
            }
        return {
            "mode": "action", "operation": "web.search", "question": "", "conversation_kind": "",
            "effect_count": "one", "effect_operations": ["web.search"], "effect_verification": "grounding_required",
            "response_language": "es",
        }

    def chat(self, *_args: object, conversation_kind: object = None, **_kwargs: object) -> tuple[str, list[object]]:
        self.kinds.append(conversation_kind)
        return ("Eso no lo hago." if conversation_kind == "unsupported" else "Unos setenta años."), []

    @staticmethod
    def extract_direct_arguments(text: str, *_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(arguments={"query": text}, fallback_question="¿Qué busco?")

    @staticmethod
    def operation_is_the_requested_effect(*_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def public_lookup_requested(_text: str) -> bool:
        return False

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


def _world_turn(text: str, llm: _WithdrawnSearchLlm) -> dict[str, object]:
    tools = {
        operation: _tool(operation, required=("query",) if operation == "web.search" else ())
        for operation in _OPERATIONS
    }
    return sidecar._prepare_turn_result(
        {"id": "turn-world", "text": text, "history": [{"role": "user", "content": text}]},
        llm=llm,
        planner_catalog=PlannerCatalog(list(tools.values())),
        turn_evidence=_NoEvidence(),
        encoder=lambda _texts: (),
        tool_by_name=tools,
    )


_WORLD_QUESTIONS = (
    "¿Cuántos años vive en promedio un perro?",
    "cuál es la esperanza de vida de una tortuga",
    "¿Qué distancia hay entre la Tierra y la Luna?",
    "¿Dónde queda Madagascar?",
    "¿Quién pintó la Mona Lisa?",
    "¿A qué temperatura hierve el agua?",
    "¿Hay vida en Marte?",
    "¿Es verdad que los pulpos tienen tres corazones?",
    "dime la capital de Canadá",
    "decime cuántos huesos tiene el cuerpo humano",
    "cuéntame por qué se extinguieron los dinosaurios",
    "hola, ¿me podrías decir cuánto mide la torre Eiffel?",
    "quisiera saber cómo se hace el pan",
    "What is the average lifespan of a cat?",
    "How far is Mars from the Sun?",
    "Does a shark have bones?",
    "tell me what a black hole is",
    "can you tell me how tall Mount Everest is?",
    "I'd like to know how many teeth an adult has",
    "¿cuál es el average lifespan de un humano?",
    "dime how many bones tiene un gato",
    "¿a cuántos años se jubila la gente normalmente?",
)


@pytest.mark.parametrize("text", _WORLD_QUESTIONS)
def test_a_withdrawn_public_lookup_leaves_a_world_question_answered_not_refused(text: str) -> None:
    llm = _WithdrawnSearchLlm()

    result = _world_turn(text, llm)

    assert not (result["kind"] == "conversation" and result.get("conversationKind") == "unsupported")
    assert "unsupported" not in llm.kinds


@pytest.mark.parametrize("text", _WORLD_QUESTIONS)
def test_a_world_question_the_decider_refused_is_answered(text: str) -> None:
    llm = _WithdrawnSearchLlm(refuses=True)

    result = _world_turn(text, llm)

    assert not (result["kind"] == "conversation" and result.get("conversationKind") == "unsupported")


@pytest.mark.parametrize(
    "text",
    ["prepárame un café", "pide una pizza a domicilio", "make me a sandwich", "order me an uber", "cómprame un auto"],
)
def test_what_baxy_does_not_do_stays_a_limit(text: str) -> None:
    result = _world_turn(text, _WithdrawnSearchLlm(refuses=True))

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"


@pytest.mark.parametrize(
    "text",
    [
        "¿cuál es el río más largo del mundo?", "por qué los gatos ronronean", "dime la capital de Perú",
        "explícame qué es la fotosíntesis", "oye, ¿sabes cuántas patas tiene una araña?", "¿Existen los agujeros de gusano?",
        "why do we dream", "tell me who invented the radio", "do you know why the sea is salty?", "Are tomatoes a fruit?",
    ],
)
def test_the_form_of_a_question_for_information(text: str) -> None:
    assert asks_for_information(text)


@pytest.mark.parametrize(
    "text", ["prepárame un café", "abre Spotify", "¿puedes regar las plantas?", "can you walk my dog?", "lava los platos"],
)
def test_an_order_is_not_a_question_for_information(text: str) -> None:
    assert not asks_for_information(text)


@pytest.mark.parametrize("text", ["¿hay agua en Marte?", "how far is Pluto from Earth?", "¿qué tan frío es Neptuno?"])
def test_a_question_about_a_far_place_is_not_bounded_as_unreachable(text: str) -> None:
    assert not out_of_world_request(text)


@pytest.mark.parametrize("text", ["send flowers to Deimos", "manda una carta a Plutón", "rent a studio on Haumea"])
def test_an_order_for_a_far_place_is_still_unreachable(text: str) -> None:
    assert out_of_world_request(text)


# ------------------------------------------------------------------ B. what changes is looked up

_CHANGING_FACTS = (
    "¿cuántos mundiales ganó Brasil?",
    "cuantas copas del mundo tiene Alemania",
    "oye, ¿cuántas Champions tiene el Real Madrid?",
    "¿me puedes decir cuántos títulos tiene Nadal?",
    "cuántos balones de oro tiene Messi",
    "cuántos goles lleva Cristiano Ronaldo en su carrera",
    "¿cuántas medallas de oro ganó Michael Phelps?",
    "cuantos grammys tiene Bad Bunny",
    "¿cuántos seguidores tiene Shakira en Instagram?",
    "cuántas veces ganó Italia el mundial",
    "how many world cups does France have",
    "how many Grammys has Beyoncé won?",
    "how many Super Bowls have the Patriots won",
    "hey, how many Oscars did Parasite win?",
    "how many times has Spain won the Euros",
    "can you tell me how many gold medals Usain Bolt won?",
    "oye baxy, how many titles tiene el Barça",
    "¿cuántos world cups tiene Argentina?",
    "¿cuántos habitantes tiene Chile?",
    "cuánta gente vive en Tokio",
    "what's the population of India",
    "¿cuánto cuesta un iPhone 16?",
    "¿cuál es el precio del bitcoin?",
    "how much does a Tesla Model 3 cost",
    "¿quién es el actual campeón de la NBA?",
    "¿quién ganó el último mundial?",
    "¿qué equipo ganó la Champions pasada?",
    "quién tiene el récord de goles en un año",
    "¿quién es la persona más rica del mundo?",
    "¿cuándo es el próximo mundial?",
    "who is the current world chess champion",
    "who won the last Super Bowl?",
    "who holds the record for most home runs",
    "what's the tallest building in the world",
    "who's the reigning Wimbledon champion",
)


@pytest.mark.parametrize("text", _CHANGING_FACTS)
def test_a_fact_that_changes_is_looked_up_in_the_persons_words(text: str) -> None:
    query = record_fact_query(text)
    assert query is not None and query.lower() in text.lower()
    reading = read(text, available_operations=("web.search", "system.time", "note.create"))
    assert reading.effects is not None and reading.effects.operations == ("web.search",)


@pytest.mark.parametrize(
    "text",
    [
        "¿cuántos goles metí en el partido de ayer?", "cuántos seguidores tengo en instagram", "how many followers do I have",
        "cuánto me costó el celular", "¿cuántas pestañas tengo abiertas?", "cuánto cuesta mi plan de celular",
        "¿cuánto es 5 más 3?", "how much is 12 times 7", "cuántos centímetros tiene una pulgada",
        "how many legs does a spider have", "¿cuántas copas de vino puedo tomar?", "¿cuánto vale la pena esperar?",
        "¿quién ganó la segunda guerra mundial?",
    ],
)
def test_own_things_arithmetic_and_stable_facts_are_not_lookups(text: str) -> None:
    assert record_fact_query(text) is None


# ------------------------------------------------------------------ C. a limit in BAXY's voice is a limit


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        ("empezar a leer el libro", "No leo libros en voz alta."),
        ("retoma la clase de francés", "No retomo clases de francés."),
        ("sigue leyendo la novela", "No leo novelas en voz alta."),
        ("riega las plantas del balcón", "No riego plantas."),
        ("llama un taxi", "No llamo taxis."),
        ("dame un masaje", "No doy masajes."),
        ("barre la cocina", "Yo no barro cocinas."),
        ("programa la lavadora", "Lo siento, no programo lavadoras."),
        ("start reading the book", "I don't read books aloud."),
        ("resume the french lesson", "I don't resume lessons."),
        ("wash the dishes", "I never wash dishes."),
        ("empieza el audiobook", "No reproduzco audiobooks."),
        ("book un vuelo a Lima", "No reservo vuelos."),
    ],
)
def test_a_first_person_limit_passes_the_limit_contract_and_the_composer(request_text: str, reply: str) -> None:
    assert _unsupported_answer_contract_failure(reply, request_text) == ""
    assert _names_the_boundary(_reading_fold(reply))


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        ("empezar a leer el libro", "No sé qué libro."),
        ("start reading the book", "I don't know which book."),
        ("walk the dog", "I don't understand."),
        ("abre la puerta", "No tengo manos."),
        ("léeme el cuento", "No entiendo el cuento."),
        ("lava los platos", "No solo lavo, también seco."),
        # What he perceives is an observation of the machine, never a limit.
        ("muestra los dispositivos conectados", "No veo ningún dispositivo conectado."),
        ("list the connected devices", "I don't see any connected devices."),
    ],
)
def test_ignorance_and_talk_are_not_a_limit(request_text: str, reply: str) -> None:
    assert _unsupported_answer_contract_failure(reply, request_text) != ""
    assert not _names_the_boundary(_reading_fold(reply))


class _RecoveryLlm:
    def __init__(self) -> None:
        self.composed: list[tuple[str, dict[str, object]]] = []

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        raise ValueError("the bounded question timed out")

    def compose_user_message(self, _text: str, intent: str, payload: dict[str, str]) -> str:
        self.composed.append((intent, json.loads(payload["situation"])))
        return "¿Qué libro quieres que lea?" if intent == "clarification" else "No leo libros en voz alta."


@pytest.mark.parametrize(
    "text", ["retomar el libro", "continuar la lección", "keep going with the chapter", "sigue con el curso"],
)
def test_a_failed_turn_is_asked_about_its_missing_piece_not_said_again(text: str) -> None:
    llm = _RecoveryLlm()

    result = sidecar._recover_failed_turn(
        {"id": "turn-failed", "text": text, "history": []}, llm, failure_kinds=("runtime", "runtime"),
    )

    assert result["kind"] == "clarify"
    assert result["question"] == "¿Qué libro quieres que lea?"
    assert llm.composed == [("clarification", {"kind": "clarification", "cause": "ambiguous_request", "polarity": "pending"})]


def test_a_failed_limit_is_recovered_as_the_limit() -> None:
    llm = _RecoveryLlm()

    result = sidecar._recover_failed_turn(
        {"id": "turn-limit", "text": "empezar a leer el libro", "history": []},
        llm,
        failure_kinds=(sidecar.LIMIT_WORDING_FAILURE, sidecar.LIMIT_WORDING_FAILURE),
    )

    assert result["kind"] == "conversation"
    assert result["conversationKind"] == "unsupported"
    assert result["reply"] == "No leo libros en voz alta."
    assert llm.composed[0][0] == "error" and llm.composed[0][1]["cause"] == "out_of_catalog"


@pytest.mark.parametrize(
    ("asked", "reply"),
    [
        ("¿en qué calle de Google Maps vives?", "No vivo en ninguna calle de Google Maps; soy BAXY y vivo en este PC."),
        ("¿te hizo Microsoft?", "No, no me hizo Microsoft: soy BAXY y vivo en este PC."),
    ],
)
def test_a_maker_the_person_named_is_not_an_invented_maker(asked: str, reply: str) -> None:
    assert not _shaped_conversation_answer_violates_contract(reply, asked, "identity")


def test_a_maker_nobody_named_is_still_invented() -> None:
    assert _shaped_conversation_answer_violates_contract(
        "Me creó Google en un laboratorio.", "¿quién te creó?", "identity",
    )


# ------------------------------------------------------------------ D. spelling is the letters


@pytest.mark.parametrize(
    ("text", "word"),
    [
        ("spell banana", "banana"),
        ("can you spell necessary?", "necessary"),
        ("how do you spell 'definitely'", "definitely"),
        ("how is receive spelled?", "receive"),
        ("what's the spelling of Wednesday?", "wednesday"),
        ("spell the word beautiful for me", "beautiful"),
        ("deletrea murciélago", "murciélago"),
        ("¿Cómo se deletrea la palabra zanahoria?", "zanahoria"),
        ("¿me puedes deletrear esternocleidomastoideo?", "esternocleidomastoideo"),
        ("puedes deletrearme el apellido González", "gonzález"),
        ("baxy, deletrea camión", "camión"),
        ("¿cómo se escribe cigüeña letra por letra?", "cigüeña"),
        ("write necessary letter by letter", "necessary"),
        ("spell la palabra ñandú", "ñandú"),
        ("deletrea the word knowledge", "knowledge"),
    ],
)
def test_a_spelling_request_takes_the_spelling_shape_with_its_word(text: str, word: str) -> None:
    assert spelling_word(text) == word
    assert _conversation_presentation_shape(text, conversation_kind="knowledge", has_history=False) == "spelling"
    assert json.loads(_shaped_presentation_text(text, "spelling", response_language="es"))["word"] == word
    assert read(text, available_operations=("web.search", "input.text.type", "note.create")).effects is None


@pytest.mark.parametrize(
    "text",
    ["spell check this document", "cast a spell on me", "deletrea", "spell it", "how do you spell that",
     "escribe hola en el bloc de notas", "what does spelling mean"],
)
def test_other_uses_of_spell_are_not_spelling(text: str) -> None:
    assert spelling_word(text) is None


@pytest.mark.parametrize(
    ("word", "reply", "accepted"),
    [
        ("potato", "Potato se deletrea P-O-T-A-T-O.", True),
        ("potato", "P, O, T, A, T, O.", True),
        ("murciélago", "Murciélago se escribe m-u-r-c-i-é-l-a-g-o.", True),
        ("potato", "Potato.", False),
        ("potato", "Potato: p-o-t-a-t-o-e.", False),
        ("camión", "c-a-m-i-o.", False),
        ("necessary", "Necessary is spelled with two s.", False),
        ("necessary", "¿Quieres que lo deletree?", False),
    ],
)
def test_the_spelling_contract_accepts_only_the_letters(word: str, reply: str, accepted: bool) -> None:
    assert _shaped_conversation_answer_violates_contract(reply, f"spell {word}", "spelling") is (not accepted)
