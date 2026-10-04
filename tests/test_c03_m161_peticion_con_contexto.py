"""M161 (2026-10-04, D58; mind/v4w DEV-I and DEV-H with the same written history as the isolated full3 decider): a
clear request with the person's own context around it is no unresolved input.

The largest class of written-history lastre was ``unresolved_input_clarification``: «I don't see a request for me in
that; do you need something?» before the decider was asked, where the isolated decider acted or talked right.

- I-s017 «my cousin Dani just texted me from Tokyo, what time is it over there for her» (system.time)
- I-s066 «oye cachai a cuánto está el dólar hoy día, es que tengo que pagarle al gringo del depto» (web)
- I-s078 «che, nada, mi viejo me preguntó cuántos habitantes tiene Mar del Plata y la verdad ni idea, fijate vos» (web)
- I-s110 «need una función python que reciba un texto y me diga cuántas vocales tiene, incluyendo las con tilde» (talk)
- H-s004 «che, salió la temporada nueva de The Bear y la quiero arrancar ya, ponémela en Disney así la veo mientras
  ceno» (streaming.play.named)
- H-s093 «whats the dollar to mexican peso rate todya, im wiring money to my cousin in guadalajara» (web)
- H-s112 «I'm on a work call and the browser is blasting, drop Chrome's volume to 15 but leave everything else where
  it is» (audio.app.volume.set)

Why it went through: the overheard-speech guard (DIALOGUE1513, ``semantic.guards._overheard_speech``) reads fifteen
words or more with no question mark as talk the microphone caught unless the message OPENS asking or ordering, or an
order verb of a closed list starts a clause. Context first and the request after it («…, what time is it over
there»), a discourse marker before it («oye cachai a cuánto…»), a question relayed («mi viejo me preguntó cuántos…»),
an English order verb the list lacks («drop Chrome's volume»), «whats» without its apostrophe and a thing asked for
(«need una función python que…») all read as overheard. M123 asks the overheard question before the decider (the safety
exception to D58), so the decider never got to decide.

Now (``semantic.guards._request_clause``): a clause of the message that opens asking or ordering — after a comma, after
the markers that open speech, after who asked it — is said to BAXY as a whole message is. Talk the microphone caught
has no such clause and is still asked about before the decider, whatever the decider would read in it (H0735).

Once the decider decides I-s110 (talk), M53 looked «cuántas vocales tiene» up: a piece of code needed or wanted («need
una función python que…») is now code asked for (``semantic.conversation.asks_for_code``, M50), written in the talk.

Rows are quoted with their real text; every other phrasing is our own.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.effect_intent import _fold
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.conversation import asks_for_code
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.guards import _overheard_speech, _unresolved_input_kind


def _overheard(text: str) -> bool:
    return _overheard_speech(_fold(text).strip())


# ------------------------------------------------------------------ the rows


@pytest.mark.parametrize("text", [
    "my cousin Dani just texted me from Tokyo, what time is it over there for her",
    "oye cachai a cuánto está el dólar hoy día, es que tengo que pagarle al gringo del depto",
    "che, nada, mi viejo me preguntó cuántos habitantes tiene Mar del Plata y la verdad ni idea, fijate vos",
    "need una función python que reciba un texto y me diga cuántas vocales tiene, incluyendo las con tilde",
    "che, salió la temporada nueva de The Bear y la quiero arrancar ya, ponémela en Disney así la veo mientras ceno",
    "whats the dollar to mexican peso rate todya, im wiring money to my cousin in guadalajara",
    "I'm on a work call and the browser is blasting, drop Chrome's volume to 15 but leave everything else where it is",
    # DEV-G rows of the same route (the isolated decider right on each).
    "ps anota en la lista del mercado que me hace falta leche, panela y huevos",
    "che, viste a cómo anda el dólar blue hoy, tengo que cambiar unos mangos antes del viaje",
    "o sea, resúmeme el pdf ese que se llama contrato_arriendo_2026, like en tres puntos",
    "my sister just moved to Osaka for work and I never know when it's ok to call her, what time is it over there right now",
])
def test_a_request_with_the_persons_context_is_not_overheard(text: str) -> None:
    assert not _overheard(text)
    assert _unresolved_input_kind(text) != "overheard_speech"


# ------------------------------------------------------------------ our own phrasings, both languages


@pytest.mark.parametrize("text", [
    # The question after the context, after a comma.
    "mi hermana se fue a vivir a Madrid hace un mes y nunca sé cuándo llamarla, qué hora es allá ahora mismo",
    "my uncle is flying in from Lisbon next week and I want to pick him up, what time does it get dark over there",
    # The question after the markers that open speech.
    "oye fíjate cachai a cuánto está el euro hoy, es que le tengo que pagar el arriendo a una señora de Madrid",
    "anyway how much does a liter of milk cost in Canada these days, my roommate keeps saying it is crazy expensive",
    # A question relayed by who asked it.
    "bueno, mi abuela me preguntó cuántos años tiene la catedral de Santiago y no le supe contestar nada de nada",
    "so my boss asked me how many people live in Rotterdam and honestly I had no clue at all what to tell him",
    # An order after the context.
    "estoy viendo una peli con mi amiga y el sonido está muy fuerte, bájale el volumen a 20 que ya es tarde aquí",
    "my roommate is sleeping and the speakers are way too loud right now, drop the volume to 10 and leave the rest",
    # A thing asked for by what it has to do.
    "necesito una función en javascript que reciba una lista de números y me devuelva solo los pares ordenados",
    "I need a small script that reads a csv file and tells me how many rows have an empty email column in them",
])
def test_the_same_shapes_in_other_words_are_said_to_baxy(text: str) -> None:
    assert _unresolved_input_kind(text) != "overheard_speech"


# ------------------------------------------------------------------ what must not change


@pytest.mark.parametrize("text", [
    # DIALOGUE1513 / M118 / M91: talk among others, first person included, no clause that asks or orders.
    "y entonces el vecino le dijo a mi primo que el auto había quedado en el taller toda la semana pasada",
    "entonces mi prima le dijo al vecino que el perro se había escapado otra vez por la reja del patio anoche",
    "y entonces le dije a mi hermano que la próxima semana íbamos a ir todos juntos al campo con los niños",
    "yo creo que en lo personal esa broma es mi favorita porque la contó mi tío en la cena del domingo pasado",
    # A question word that opens a relative or a comparison after a comma is talk («donde», «como», «cuando»).
    "fuimos a la casa de la playa, donde vivía mi abuela cuando era chica, y nos quedamos ahí toda la tarde",
    "el calor se va de la atmósfera, como lo absorben las plantas, y por eso no se queda nada de calor ahí",
    # A relayed statement, not a question («dice que»).
    "mi hermano dice que cuando llegue a la casa vamos a ver la final con todos los primos y los vecinos",
    # The other language: talk about others in English, no request clause.
    "and then my cousin told the landlord that the heater had been broken for the whole winter last year",
    "my brother said that the game was over by the time they got to the stadium with all of their friends",
    # Same verb, other shape: an English verb with no object after it, a past order told.
    "she told him to drop it and then they all went home early because the rain did not stop the whole night",
])
def test_talk_the_microphone_caught_is_still_overheard(text: str) -> None:
    assert _unresolved_input_kind(text) == "overheard_speech"


def test_a_row_the_gold_asks_about_stays_asked() -> None:
    # DEV-I I-w34-t1 (gold: ask): the order verb is not one the guard reads; it keeps the overheard question.
    assert _unresolved_input_kind(
        "the telly's blaring in the next room as it is, bring the volume down on here"
    ) == "overheard_speech"


# ------------------------------------------------------------------ the whole turn


class _Decider:
    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision
        self.decisions = 0
        self.unresolved: list[str] = []

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        return self.decision

    def public_lookup_requested(self, _text):
        return False

    def _verify_semantic_effect_shape(self, _text):
        return "complete", "one"

    def clarify_unresolved_input(self, _text, kind, **_k):
        self.unresolved.append(kind)
        return "En eso no encuentro un pedido para mí; ¿necesitas algo?"

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
    tool = {"type": "function", "function": {
        "name": "web_search", "canonical_name": "web.search", "description": "web.search", "risk": "read_only",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}}}
    return sidecar._prepare_turn_result(
        {"id": "m161", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog([tool]), encoder=lambda _t: (), tool_by_name={"web.search": tool},
        dialogue_state=DialogueState(),
    )


def test_the_decider_decides_a_request_with_its_context() -> None:
    # I-s110: the isolated decider wrote the function in the talk (M50); the product asked whether anything was needed.
    text = "need una función python que reciba un texto y me diga cuántas vocales tiene, incluyendo las con tilde"
    model = _Decider(ContextDecision("Escribe una función en Python que cuente las vocales de un texto.", "talk", (), ""))
    result = _turn(text, model)
    assert model.decisions == 1 and model.unresolved == []
    assert result["kind"] == "conversation"


@pytest.mark.parametrize("text, request_", [
    ("whats the dollar to mexican peso rate todya, im wiring money to my cousin in guadalajara",
     "What's the USD to Mexican peso rate today?"),
    ("oye cachai a cuánto está el dólar hoy día, es que tengo que pagarle al gringo del depto",
     "¿A cuánto está el dólar hoy?"),
])
def test_the_deciders_lookup_is_the_turn(text: str, request_: str) -> None:
    model = _Decider(ContextDecision(request_, "action", ("web.search",), ""))
    result = _turn(text, model)
    assert model.decisions == 1 and model.unresolved == []
    assert result["kind"] == "action" and result["effectOperations"] == ["web.search"]


@pytest.mark.parametrize("text", [
    "need una función python que reciba un texto y me diga cuántas vocales tiene, incluyendo las con tilde",
    "necesito un script en bash que me renombre todas las fotos de una carpeta con la fecha en que se tomaron",
    "I want a small function that tells me whether a year is a leap year or not, nothing fancy please",
])
def test_a_piece_of_code_needed_is_code_asked_for(text: str) -> None:
    # M50: written in the talk, never looked up (M53 read «cuántas vocales tiene» as a fact to search).
    assert asks_for_code(text)


@pytest.mark.parametrize("text", [
    "quiero ir a la función de las ocho del teatro municipal con mi mamá",
    "I need a break from all this, the week has been really long",
    "necesito una mano con la mudanza el sábado, ¿quién puede venir?",
])
def test_needing_something_else_is_not_code(text: str) -> None:
    assert not asks_for_code(text)


def test_overheard_talk_is_still_asked_before_the_decider() -> None:
    # M123: whatever the decider would do with it.
    text = "yo creo que en lo personal esa broma es mi favorita porque la contó mi tío en la cena del domingo pasado"
    model = _Decider(ContextDecision(text, "action", ("web.search",), ""))
    result = _turn(text, model)
    assert model.decisions == 0 and model.unresolved == ["overheard_speech"]
    assert result["kind"] == "clarify" and result["effectOperations"] == []
