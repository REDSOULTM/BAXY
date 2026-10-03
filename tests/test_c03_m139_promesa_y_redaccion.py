"""M139 (DEV-G v4n, 2026-10-03): a reply never promises an effect that did not happen, and fewer drafts end with no final.

1. G-s120 «yo uh I'm starving, get a large pepperoni pie delivered from the Domino's on 5th for me» (gold: limit), decided
   social: both talk drafts said the limit («I can't deliver food or place orders for you.», «…cannot interact with the
   physical world or order food.») and died as told_failure; the recovery composed the talk again and published «I will
   get a large pepperoni pie delivered from Domino's on 5th for you.». Now
   a) the acts done in the world by asking someone (get delivered, call, book, pay, reserve…) are promised or told done
      in the first person like saving or opening, so that reply is an effect claim in every conversation reply,
      recovered or not (``llm._EN_WORLD_ACTS``, ``llm._WORLD_ACT_INFINITIVES``);
   b) a told failure that is a present inability, not a failed attempt nor not knowing, is the limit the model saw
      (``llm.talk_reply_tells_a_limit``, audit reason «told_limit»): the turn's recovery says it as a limit.
2. Drafts with no final:
   - G-s011 «dale, abrime el bloc de notas…» (Notepad already running): «Abriste…» was told «you did it, say what you
     did» and the retries wrote «Abrió el Bloc de notas…»; the hint for an app already running says it was already open.
   - G-s021 «bro abre Discord y mutea el micro…» (microphone already muted): «He abierto Discord…» died as
     missing_prior_open («abierto» is «abrir») and «…ya estaba silenciado, así que no hubo cambio» as asserted_failure.
   - G-w33-t4 «bueno, ya que no puedes con eso, al menos ponme una alarma para las 9 de la noche»: «ya que» read as
     «¿qué…?» made it a question about BAXY's limits (here and in the App, which never asked the decider).
   - G-w44-t2 «y eso pa dos» after the recipe for four: «500 g» and «250 ml» for «1 kg» and «1/2 litro» halved died as
     unsourced_figures.
   - G-s037, G-w35-t1, G-w36-t4/t5: refused by the App only (tests/Baxy.Integration.Tests/M139RedaccionTests.cs).
Each fix carries the row's own text and phrasings of our own, and what must not change.
"""

from __future__ import annotations

import copy
import json
from fractions import Fraction

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.llm import ConversationReplyContractError, LlmRuntime
from baxy_mind.semantic.request import INTENT_CAPABILITY, INTENT_REFUSE, read_request

TALK = json.dumps({"kind": "conversation", "polarity": "success"})
PIZZA = "yo uh I'm starving, get a large pepperoni pie delivered from the Domino's on 5th for me"


class _Drafts(LlmRuntime):
    """The drafts stand in for the model in order (the last one repeats); every request is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.requests.append(copy.deepcopy(payload))
        content = self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


class _Writer(LlmRuntime):
    """Talk drafts in order; out of drafts, it runs out of time."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self._drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(copy.deepcopy(payload))
        if not self._drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self._drafts.pop(0)}, "finish_reason": "stop"}]}


def _system_text(payload: dict) -> str:
    return "\n".join(str(item.get("content") or "") for item in payload["messages"] if item.get("role") == "system")


# ------------------------------------------------------------------ 1a. a promise of an act on the world


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        # G-s120: the recovered reply, word for word.
        (PIZZA, "I will get a large pepperoni pie delivered from Domino's on 5th for you."),
        ("can you book me a table for two at the italian place tonight", "I'll call the restaurant and book it for you."),
        ("resérvame una mesa para dos esta noche en el italiano", "Claro, te reservo una mesa para dos esta noche."),
        ("pídeme una pizza a domicilio", "Voy a llamar a la pizzería para que te la traigan."),
        ("paga la luz", "Ya pagué la factura de la luz."),
        ("order me some sushi", "I'm calling the sushi place now."),
    ],
)
def test_a_promised_or_claimed_act_on_the_world_is_an_effect_claim(request_text: str, reply: str) -> None:
    assert llm.conversation_world_claim(reply, request_text) == "effect_claim"
    # The recovery and the App's fallback compose conversation through the same contract.
    assert llm.compose_visible_defect(reply, "conversation", request_text, {"situation": TALK}) == "effect_claim"


@pytest.mark.parametrize(
    ("request_text", "reply"),
    [
        ("tell me something fun", "I'll get you a fun fact: octopuses have three hearts."),
        ("who is John?", "You have a friend called John, from what you told me."),
        ("háblame de Juan", "Tienes un amigo llamado Juan, según me contaste."),
        ("I want pizza tonight", "I got it: pizza sounds great tonight."),
        ("pídeme una pizza", "Si quieres, ¿te digo qué pizzerías hay cerca?"),
        (PIZZA, "I don't order food or have it delivered."),
    ],
)
def test_talk_that_promises_nothing_is_not_an_effect_claim(request_text: str, reply: str) -> None:
    assert llm.conversation_world_claim(reply, request_text) == ""


def test_the_recovered_conversation_no_longer_publishes_the_promise() -> None:
    writer = _Drafts([
        "I will get a large pepperoni pie delivered from Domino's on 5th for you.",
        "I don't order food or have it delivered.",
    ])
    reply = writer.compose_user_message(PIZZA, "conversation", {"situation": TALK})
    assert reply == "I don't order food or have it delivered."
    assert len(writer.requests) == 2


# ------------------------------------------------------------------ 1b. a talk draft that said the limit


@pytest.mark.parametrize(
    ("reply", "limit"),
    [
        # G-s120's two drafts.
        ("I can't deliver food or place orders for you.", True),
        ("I have not delivered the pepperoni pie yet: I am a companion who lives on your PC and cannot interact with "
         "the physical world or order food.", True),
        ("No puedo pedir comida a domicilio.", True),
        ("Eso no lo hago: reservar mesas en restaurantes.", True),
        # A failed attempt, not knowing or not being sure is no limit.
        ("I couldn't reach your streaming account.", False),
        ("No tengo certeza absoluta ni puedo garantizar resultados.", False),
        ("No puedo saber cómo te sientes hoy.", False),
        ("I can't tell which captions that film ships with.", False),
    ],
)
def test_a_present_inability_is_the_limit(reply: str, limit: bool) -> None:
    assert llm.talk_reply_tells_a_limit(reply) is limit


def test_social_drafts_that_said_the_limit_end_as_a_limit_wording_failure() -> None:
    writer = _Writer([
        "I can't deliver food or place orders for you.",
        json.dumps({"answer": "I have not delivered the pepperoni pie yet: I am a companion who lives on your PC and "
                              "cannot interact with the physical world or order food."}),
    ])
    with pytest.raises(ConversationReplyContractError) as refused:
        writer.chat(PIZZA, history=[], conversation_kind="social", response_language="en", temperature=0.0)
    assert refused.value.audit_reason == "told_limit"
    assert sidecar._turn_failure_kind(refused.value) == sidecar.LIMIT_WORDING_FAILURE


def test_a_failed_attempt_told_in_talk_stays_a_talk_failure() -> None:
    writer = _Writer([
        "I cannot reach your streaming account.",
        json.dumps({"answer": "I couldn't reach your streaming account."}),
    ])
    with pytest.raises(ConversationReplyContractError) as refused:
        writer.chat("Sounds good, carry on with that.", history=[], conversation_kind="knowledge",
                    response_language="en", temperature=0.0)
    assert refused.value.audit_reason == "told_failure"
    assert sidecar._turn_failure_kind(refused.value) == sidecar.CONVERSATION_WORDING_FAILURE


class _Composer:
    """The recovery's composer: what it is asked, and its answer for each intent."""

    def __init__(self, replies: dict[str, str]) -> None:  # noqa: D107
        self.replies = replies
        self.asked: list[str] = []

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("a limit is not asked about")

    def compose_user_message(self, _text: str, intent: str, _facts: dict) -> str:
        self.asked.append(intent)
        return self.replies.get(intent, "")


def test_the_recovery_says_the_limit_the_drafts_saw() -> None:
    composer = _Composer({
        "conversation": "I will get a large pepperoni pie delivered from Domino's on 5th for you.",
        "error": "I don't order food or have it delivered.",
    })
    result = sidecar._recover_failed_turn(
        {"id": "843", "text": PIZZA, "history": []},
        composer,
        attempts=1,
        failure_kinds=(sidecar.LIMIT_WORDING_FAILURE,),
        conversation_kinds=("social",),
    )
    assert composer.asked == ["error"]
    assert result["kind"] == "conversation"
    assert result["reply"] == "I don't order food or have it delivered."
    assert result["conversationKind"] == "unsupported"


# ------------------------------------------------------------------ 2. drafts with no final


NOTEPAD_ALREADY_RUNNING = json.dumps({
    "kind": "operation", "operation": "app.open", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"appId": "windows.notepad", "displayName": "Bloc de notas", "alreadyRunning": True,
                 "windowHandle": 2562682},
})
CALCULATOR_OPENED = json.dumps({
    "kind": "operation", "operation": "app.open", "polarity": "success", "verified": True, "succeeded": True,
    "observed": {"appId": "windows.calculator", "displayName": "Calculadora", "alreadyRunning": False,
                 "windowHandle": 1234},
})


@pytest.mark.parametrize(
    ("said", "first", "kept"),
    [
        # G-s011: the first draft and the honest one.
        ("dale, abrime el bloc de notas que tengo que anotar unos numeros antes de que se me olviden",
         "Abriste el Bloc de notas, que ya estaba abierto antes de tu acción.", "El Bloc de notas ya estaba abierto."),
        # G-s011's second draft (missing_state).
        ("ábreme el bloc de notas porfa",
         "Abrió el Bloc de notas, ya que estaba ejecutándose antes de que la operación se iniciara.",
         "El Bloc de notas ya estaba abierto."),
        # M142 (held-out v4o t10, the rioplatense imperative): the first of three drafts that died.
        ("abrí el bloc de notas",
         "Abriste el Bloc de notas, que ya estaba abierto antes de tu acción.", "El Bloc de notas ya estaba abierto."),
    ],
)
def test_an_app_already_running_is_told_already_open(said: str, first: str, kept: str) -> None:
    writer = _Drafts([first, kept])
    assert writer.compose_user_message(said, "status", {"situation": NOTEPAD_ALREADY_RUNNING}) == kept
    hint = _system_text(writer.requests[1])
    # M142: the hint says it was already open, shows the sentence and says nobody opened it, BAXY nor the person.
    assert "di sólo que ya estaba abierta" in hint and "Nadie la abrió" in hint
    assert "Lo hiciste tú" not in hint and "la abriste" not in hint


def test_an_app_opened_now_still_hears_that_it_did_it() -> None:
    writer = _Drafts(["Abriste la Calculadora, ya está abierta.", "Abrí la Calculadora."])
    assert writer.compose_user_message("abre la calculadora", "status", {"situation": CALCULATOR_OPENED}) == (
        "Abrí la Calculadora."
    )
    assert "Lo hiciste tú" in _system_text(writer.requests[1])


def _mission(mute_step: dict) -> str:
    return json.dumps({
        "kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
        "steps": [
            json.dumps({"kind": "operation", "operation": "app.open", "polarity": "success", "verified": True,
                        "succeeded": True, "observed": {"appId": "Discord", "displayName": "Discord",
                                                        "alreadyRunning": False, "windowHandle": 2230094},
                        "readOnly": False}),
            json.dumps(mute_step),
        ],
        "completedRequest": "Abre Discord y silencia el micrófono.",
    })


MIC_ALREADY_MUTED = _mission({"kind": "operation", "operation": "audio.microphone.mute", "polarity": "failure",
                              "verified": False, "succeeded": False, "error": "microphone_already_muted",
                              "readOnly": False})
MIC_MUTED_NOW = _mission({"kind": "operation", "operation": "audio.microphone.mute", "polarity": "success",
                          "verified": True, "succeeded": True, "observed": {"muted": True, "baselineMuted": False},
                          "readOnly": False})
DISCORD_PAYLOAD = {
    "kind": "status", "completedRequest": "Abre Discord y silencia el micrófono.", "outcome": "completed",
    "completedStepsInOrder": [
        {"operation": "app.open", "resultAtThisStep": {
            "readOnly": False, "outcome": "completed", "operation": "app.open",
            "seen": {"appId": "Discord", "displayName": "Discord", "windowHandle": 2230094,
                     "was_running_before_open": False}}},
        {"operation": "audio.microphone.mute", "resultAtThisStep": {
            "readOnly": False, "outcome": "already_as_asked", "operation": "audio.microphone.mute",
            "cause": "the person asked to mute (silence) the microphone and it was already muted, not picking up "
                     "sound; nothing was attempted and nothing changed"}},
    ],
}
DISCORD = "bro abre Discord y mutea el micro, que viene mi roommate"


@pytest.mark.parametrize(
    "draft",
    [
        # G-s021's first two drafts, word for word.
        "Abri Discord y el micrófono ya estaba silenciado, así que no hubo cambio.",
        "He abierto Discord, pero el micrófono ya estaba silenciado por lo que no ha podido cambiar el estado.",
        "Abrí Discord; el micrófono ya estaba en silencio, así que no hubo ningún cambio.",
        "He abierto Discord y el micrófono ya estaba silenciado: nada cambió.",
    ],
)
def test_the_mission_tells_the_state_that_already_held(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", DISCORD, {"situation": MIC_ALREADY_MUTED}) == ""
    assert llm._payload_fact_defect(draft, DISCORD_PAYLOAD, DISCORD) == ""


def test_what_the_mission_tells_wrongly_is_still_refused() -> None:
    # No «ya estaba»: «no hubo cambio» alone tells a failed mission.
    assert llm.compose_visible_defect(
        "Abrí Discord pero no hubo cambio.", "status", DISCORD, {"situation": MIC_ALREADY_MUTED},
    ) == "asserted_failure"
    # The microphone muted by this mission: nothing changed is false.
    assert llm.compose_visible_defect(
        "Abrí Discord y el micrófono ya estaba silenciado, así que no hubo cambio.", "status", DISCORD,
        {"situation": MIC_MUTED_NOW},
    ) == "asserted_failure"
    # The opening left out is still missing.
    assert llm._payload_fact_defect(
        "El micrófono ya estaba silenciado.", DISCORD_PAYLOAD, DISCORD,
    ) == "missing_prior_open"


@pytest.mark.parametrize(
    "text",
    [
        # G-w33-t4, word for word.
        "bueno, ya que no puedes con eso, al menos ponme una alarma para las 9 de la noche",
        "puesto que no puedes abrir eso, ponme música",
        "dado que no puedes con el aire, apaga la pantalla",
    ],
)
def test_a_connective_que_asks_nothing_about_baxy(text: str) -> None:
    intents = read_request(text).intents
    assert INTENT_REFUSE not in intents
    assert INTENT_CAPABILITY not in intents


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("¿qué no puedes hacer?", INTENT_REFUSE),
        ("¿cuáles son tus límites?", INTENT_REFUSE),
        ("¿qué puedes hacer?", INTENT_CAPABILITY),
    ],
)
def test_a_question_about_baxy_is_still_read(text: str, intent: str) -> None:
    assert intent in read_request(text).intents


TORTILLA_PAGE = (
    "Tortilla de patatas\nIngredientes (para 4 personas):\n- 8 huevos grandes (tamaño L ó XL)\n"
    "- 1 kg de patatas (una patata grande por persona)\n- 1 cebolla mediana o grande (al gusto)\n"
    "- 1/2 litro de aceite de oliva (unos 2 vasos, para freir las patatas y la cebolla)\n- Sal\nPreparación:\n"
    "1. Pelar las patatas, lavarlas y secarlas con un paño.\n2. Se parte la cebolla en cuadraditos pequeños.\n"
    "3. En una fuente, se vierten los 8 huevos."
)
TORTILLA_FOR_TWO = (
    "Tortilla de patatas:\n- 4 huevos grandes\n- 500 g de patatas\n- 1/2 cebolla mediana o grande\n"
    "- 250 ml de aceite de oliva\n- Sal\n\nPreparación:\n1. Pelar, lavar y secar las patatas.\n"
    "2. Cortar la cebolla.\n3. Batir los huevos."
)
SAID = ["y eso pa dos", "oye baxy cómo se hace la tortilla de patatas pa cuatro personas"]


@pytest.mark.parametrize(
    ("draft", "ratio"),
    [
        # G-w44-t2: the draft that died five times.
        (TORTILLA_FOR_TWO, Fraction(1, 2)),
        ("- 500 gramos de patatas\n- 250 mililitros de aceite", Fraction(1, 2)),
        # Doubled, in the page's units.
        ("- 2 kg de patatas\n- 1 litro de aceite\n- 16 huevos", Fraction(2)),
        # Not scaled, in the other unit.
        ("- 1000 g de patatas\n- 500 ml de aceite", None),
    ],
)
def test_a_scaled_quantity_in_the_other_unit_is_the_pages(draft: str, ratio: Fraction | None) -> None:
    assert llm._reference_unsourced_figures(draft, TORTILLA_PAGE, SAID, ratio) == []


def test_a_quantity_the_page_does_not_give_is_still_unsourced() -> None:
    assert llm._reference_unsourced_figures(
        TORTILLA_FOR_TWO.replace("500 g", "700 g").replace("250 ml", "300 ml"), TORTILLA_PAGE, SAID, Fraction(1, 2),
    ) == ["700", "300"]
