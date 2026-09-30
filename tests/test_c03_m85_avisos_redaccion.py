"""M85: the ⚠, the inventions and the wording of the independent review of the official-window DEV-D run v3o.

Each case is a real turn of window/v3o-devD (HEAD 5761e1ab); its drafts, payloads and the App's refusals of the mind's
own replies are the recorded ones (tests/data/c03_m85_v3o_evidence.json, from compose-audit.jsonl and events.jsonl).

⚠ (composition_failed):
- w02-t2 «y si allá son las 10 de la mañana acá qué hora es» after «qué hora es en madrid»: talked, the writer said this
  PC's clock (clock_pattern). «allá» is the place of the clock question before; the conversion is system.time's.
- w20-t1: the script asked «can you write it?» was written; the App's twin of asks_for_code lacked M81's pronoun form
  and refused it as internal_code (tests/Baxy.Integration.Tests/M85AvisosRedaccionTests.cs).
- p35-t2 «podrías explicarme como lo hiciste?» after BAXY only asked a question: «no tengo acceso a cómo lo hice» three
  times. The writer is told that nothing was done yet.
- p27-t3: a search report ran on to 160 tokens and spent 4.0 of the 5 s; the web answer's budget is 120 now.
- w20-t4: the decider read «¿Qué versión de Python tengo instalada?» as system.identity; the three drafts invented a
  Python version and were rightly refused (no code change: the choice is the decider's).
Inventions: p09-t3 «I did not add barbells…» right after adding them; p24-t5 «Confirmed, the procedure will proceed.»;
p27-t1 «the latest sci-fi flick…» with no title (after the App refused the mind's honest question back).
Wording: w01-t2 «No he añadido sal al agua.», p31-t2/p35-t3 how sure the last answer is, p32-t2/p36-t2 a list and more
dialogue lines, p27-t5 an echo, p04-t1 «¿Dónde?» to «Dónde?», s025 «si pasan cuarenta minutos, ¿qué hora será?».
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue, temporal
from baxy_mind.semantic.conversation import (
    adds_to_a_dialogue,
    asks_a_list_or_table,
    asks_about_own_past_act,
    asks_for_code,
    ends_asking_the_person,
    stable_no_effect,
    without_quoted_speech,
)
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.network import hours_until_asked
from baxy_mind.semantic.request import INTENT_CAPABILITY, asks_about_reliability, read_request

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m85_v3o_evidence.json").read_text(encoding="utf-8"))
CONVERSATION = json.dumps({"kind": "conversation", "polarity": "success"})


def _case(ident: str) -> dict:
    return EVIDENCE[ident]


def _stage(ident: str, stage: str = "first") -> dict:
    return next(item for item in _case(ident)["stages"] if item["stage"] == stage)


def _visible(draft: str, user_text: str, situation: str = CONVERSATION, **facts: object) -> str:
    return llm.compose_visible_defect(draft, "conversation", user_text, {"situation": situation, **facts})


class _Writer(llm.LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats); every payload sent is kept."""

    def __init__(self, drafts: list[str], finishes: list[str] | None = None) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)
        self._finishes = list(finishes or [])
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(payload)
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        finish = self._finishes.pop(0) if self._finishes else "stop"
        return {"choices": [{"message": {"content": content}, "finish_reason": finish}]}


def _system_text(payload: dict) -> str:
    return " ".join(str(message["content"]) for message in payload["messages"] if message["role"] == "system")


def _sent_text(payload: dict) -> str:
    return "\n".join(str(message.get("content")) for message in payload["messages"])


class _Decider:
    def __init__(self, decision: ContextDecision) -> None:
        self.decision = decision

    def decide_in_context(self, *_args: object, **_kwargs: object) -> ContextDecision:
        return self.decision

    def clarify_after_turn_failure(self, *_args: object, **_kwargs: object) -> str:
        return "¿Qué lugar buscas?"

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list]:
        return "Claro.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "es"


def _tool(operation: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"), "canonical_name": operation,
            "description": f"Authenticated catalog leaf {operation}.", "risk": "read_only",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
    }


def _history(ident: str) -> list[dict]:
    return [*_case(ident)["lived"], {"role": "user", "content": _case(ident)["text"]}]


# ------------------------------------------------------------------ ⚠ w02-t2: «allá» is the place asked before


W02_T2 = "y si allá son las 10 de la mañana acá qué hora es"


def test_w02_t2_there_is_the_place_of_the_clock_question_before() -> None:
    assert _case("D-w02-t2")["text"] == W02_T2
    resolved = temporal.clock_there_request(W02_T2, ["baxy qué hora es en madrid"])
    assert resolved == "y si en madrid son las 10 de la mañana acá qué hora es"
    read = temporal.clock_elsewhere(temporal._fold(resolved))
    assert read is not None and read.place == "madrid" and read.clock_is_there
    assert (read.clock.hour, read.clock.minute) == (10, 0)
    assert temporal.clock_there_request("and if it's 9 am there, what time is it here?", ["what time is it in Tokyo"]) == (
        "and if it's 9 am in Tokyo, what time is it here?"
    )


@pytest.mark.parametrize(
    ("text", "prior"),
    [
        (W02_T2, ["pon música de los 80"]),  # no clock question before
        ("¿y allá hace frío?", ["baxy qué hora es en madrid"]),  # not a clock question
        ("qué hora es en lima", ["baxy qué hora es en madrid"]),  # names its own place
    ],
)
def test_there_without_an_earlier_clock_place_stays_as_said(text: str, prior: list[str]) -> None:
    assert temporal.clock_there_request(text, prior) is None


def test_w02_t2_the_decider_s_talk_is_this_pc_s_clock_read_with_the_place() -> None:
    # v3o turn-audit request 1334: mode talk, «¿Qué hora es en Madrid si allá son las 10 de la mañana?».
    decider = _Decider(ContextDecision("¿Qué hora es en Madrid si allá son las 10 de la mañana?", "talk", (), ""))
    result = sidecar._context_decided_result(
        {"id": "m85", "text": W02_T2, "history": _history("D-w02-t2")},
        llm=decider,
        planner_catalog=PlannerCatalog([_tool("system.time"), _tool("web.search")]),
    )
    assert result["kind"] == "action" and result["operation"] == "system.time"
    assert result["objective"] == "y si en madrid son las 10 de la mañana acá qué hora es"


def test_s025_a_clock_later_on_talked_is_this_pc_s_clock_read() -> None:
    text = "si pasan cuarenta minutos, ¿qué hora será?"
    assert temporal.clock_later_asked(text) == ("si pasan cuarenta minutos", 40)
    assert temporal.clock_later_asked("what time will it be if 40 minutes pass") == ("if 40 minutes pass", 40)
    decider = _Decider(ContextDecision(text, "talk", (), ""))
    result = sidecar._context_decided_result(
        {"id": "m85", "text": text, "history": [{"role": "user", "content": text}]},
        llm=decider,
        planner_catalog=PlannerCatalog([_tool("system.time")]),
    )
    assert result["kind"] == "action" and result["operation"] == "system.time"


def test_talk_that_is_no_clock_stays_talk() -> None:
    text = "¿por qué España tiene el horario de Europa central?"
    decider = _Decider(ContextDecision(text, "talk", (), ""))
    result = sidecar._context_decided_result(
        {"id": "m85", "text": text, "history": [{"role": "user", "content": text}]},
        llm=decider,
        planner_catalog=PlannerCatalog([_tool("system.time")]),
    )
    assert result["kind"] == "conversation"


def _madrid_clock_situation() -> dict:
    return json.loads(_stage("D-w02-t1")["situation"])


def test_w02_t2_the_conversion_is_computed_and_its_last_resort_is_said_from_the_figures() -> None:
    situation = _madrid_clock_situation()
    user_text = "y si en madrid son las 10 de la mañana acá qué hora es"
    payload = llm._compose_situation_payload(situation, "es", user_text)
    assert {key: payload[key] for key in ("given", "givenAt", "clock", "clockAt")} == {
        "given": "10:00", "givenAt": "Madrid", "clock": "05:00", "clockAt": "aquí",
    }
    final = llm._deterministic_final(situation, payload, user_text, "es")
    assert final == "Si en Madrid son las 10:00, aquí son las 05:00."
    assert llm.compose_visible_defect(final, "status", user_text, {"situation": json.dumps(situation)}) == ""
    assert llm._payload_fact_defect(final, payload, user_text) == ""
    # The recorded draft said this PC's clock read of the turn before as the answer.
    assert llm._payload_fact_defect(_stage("D-w02-t2")["draft"].replace("allá", "en Madrid"), payload, user_text) != ""


def test_another_place_s_clock_last_resort() -> None:
    situation = _madrid_clock_situation()
    payload = json.loads(json.dumps(_stage("D-w02-t1")["payload"]))
    assert llm._deterministic_final(situation, payload, "baxy qué hora es en madrid", "es") == "En Madrid son las 19:49."
    english = llm._compose_situation_payload(situation, "en", "and if it's 10 am in Madrid, what time is it here?")
    assert llm._deterministic_final(situation, english, "and if it's 10 am in Madrid, what time is it here?", "en") == (
        "If it's 10:00 in Madrid, it's 05:00 here."
    )


# ------------------------------------------------------------------ ⚠ w20-t1: the script asked with «write it»


def test_w20_t1_the_script_asked_with_a_pronoun_is_code_asked_for() -> None:
    text = _case("D-w20-t1")["text"]
    assert asks_for_code(text)
    rejected = _case("D-w20-t1")["app_rejection"]
    assert rejected["reason"] == "internal_code" and rejected["reply"].startswith("```python")
    assert _visible(rejected["reply"], text) == ""
    # w20-t2: the change asked after it is code too (the App refused the pandas script the same way).
    assert _case("D-w20-t2")["app_rejection"]["reason"] == "internal_code"
    assert asks_for_code(_case("D-w20-t2")["text"], (text,))


@pytest.mark.parametrize(
    ("text", "asked"),
    [("tengo un script que falla, ¿me lo puedes escribir de nuevo?", True),
     ("necesito una función que ordene fechas, escríbela", True),
     ("escríbelo en una nota", False), ("write it down", False)],
)
def test_the_code_request_reader_matches_the_app(text: str, asked: bool) -> None:
    # Twin cases of M85AvisosRedaccionTests.TheCodeRequestReaderMatchesTheMind.
    assert asks_for_code(text) is asked


# ------------------------------------------------------------------ ⚠ p35-t2: nothing was done yet


P35_T2 = "podrías explicarme como lo hiciste?"


@pytest.mark.parametrize("text", [P35_T2, "¿cómo lo hiciste?", "¿ya lo hiciste?", "how did you do it?",
                                  "what did you do?", "did you do it?"])
def test_asking_how_baxy_did_it(text: str) -> None:
    assert asks_about_own_past_act(text)


@pytest.mark.parametrize("text", ["what did you say?", "¿qué es un exoplaneta?", "¿cómo se hace un FODA?"])
def test_other_questions_ask_no_past_act(text: str) -> None:
    assert not asks_about_own_past_act(text)


def test_p35_t2_the_recorded_drafts_still_die_and_an_honest_one_passes() -> None:
    text = _case("D-p35-t2")["text"]
    for stage in ("first", "retry", "third"):
        assert _visible(_stage("D-p35-t2", stage)["draft"], text) == "internal_code"
    assert _visible("Todavía no hice el análisis FODA de Adidas: te pregunté si querías datos específicos.", text) == ""


def test_p35_t2_the_composer_is_told_nothing_was_done_yet() -> None:
    question = _case("D-p35-t2")["lived"][-1]["content"]
    writer = _Writer(["Todavía no hice el análisis FODA de Adidas: te pregunté si querías datos específicos."])
    published = writer.compose_user_message(
        _case("D-p35-t2")["text"], "conversation",
        {"situation": CONVERSATION, "context": question, "priorRequests": [_case("D-p35-t2")["lived"][0]["content"]]},
    )
    assert published.startswith("Todavía no hice el análisis FODA")
    assert "todavía no hiciste lo que pidió" in _sent_text(writer.sent[0])
    assert question in _sent_text(writer.sent[0])


def test_p35_t2_the_turn_s_own_reply_is_told_nothing_was_done_yet() -> None:
    writer = _Writer(["Todavía no hice el análisis FODA: te pregunté si querías datos específicos."])
    writer.chat(P35_T2, history=_case("D-p35-t2")["lived"], conversation_kind="knowledge", response_language="es")
    assert "todavía no hiciste lo que pidió" in _system_text(writer.sent[0])
    # Not after an answer that did something.
    writer = _Writer(["Lo calculé con la fórmula del área."])
    writer.chat(P35_T2, history=[{"role": "user", "content": "área de un círculo de radio 2"},
                                 {"role": "assistant", "content": "Son 12,57 unidades cuadradas."}],
                conversation_kind="knowledge", response_language="es")
    assert "todavía no hiciste" not in _system_text(writer.sent[0])


# ------------------------------------------------------------------ ⚠ p27-t3: the web answer's budget


def test_p27_t3_a_web_answer_leaves_time_for_the_shorter_retry() -> None:
    stage = _stage("D-p27-t3")
    assert stage["reason"] == "cut_by_length"
    writer = _Writer(
        [stage["draft"], "Eugene Dynarski was in two Steven Spielberg movies: «El diablo sobre ruedas» and "
         "«Encuentros en la tercera fase»."],
        ["length", "stop"],
    )
    published = writer.compose_user_message(_case("D-p27-t3")["text"], "status", {"situation": stage["situation"]})
    assert writer.sent[0]["max_tokens"] == 120
    assert "shorter" in _sent_text(writer.sent[1])
    assert published.startswith("Eugene Dynarski was in two Steven Spielberg movies")


# ------------------------------------------------------------------ inventions


def test_p09_t3_a_prohibition_of_what_was_just_done_takes_it_back() -> None:
    text = _case("D-p09-t3")["text"]
    lived = _case("D-p09-t3")["lived"]
    assert dialogue.retracts_the_last_effect(text, lived[-1]["content"])
    # It is decided with the conversation (the contextual decider), never closed as talk about a rule.
    assert stable_no_effect(text, _history("D-p09-t3")) is None
    assert stable_no_effect(text, []) is not None


@pytest.mark.parametrize(
    ("text", "last_reply", "retracts"),
    [
        ("no, mejor no añadas la leche", "He añadido leche a tu lista de la compra.", True),
        ("don't set it", "I've set the alarm for 7:00.", False),  # the thing is not named
        ("don't add barbells", "What should I add to your fitness list?", False),  # nothing was done
        ("don't add barbells", "I couldn't add barbells to your list.", False),  # it failed
        ("don't open chrome", "I've added barbells to your fitness list.", False),  # another act
        ("no añadas nada más", "He añadido leche a tu lista de la compra.", False),
    ],
)
def test_what_takes_the_last_effect_back(text: str, last_reply: str, retracts: bool) -> None:
    assert dialogue.retracts_the_last_effect(text, last_reply) is retracts


@pytest.mark.parametrize(
    ("reply", "user_text"),
    [
        ("I did not add barbells to your fitness list.", "never mind do not add barbells to my fitness list"),  # p09-t3
        ("No he añadido sal al agua.", "oye y cuánta sal le echo al agua, más o menos, cachai"),  # w01-t2
    ],
)
def test_a_write_denied_in_a_turn_that_ran_nothing(reply: str, user_text: str) -> None:
    assert llm.conversation_world_claim(reply, user_text) == "own_write_denied"
    assert _visible(reply, user_text) == "own_write_denied"


def test_w01_t2_the_recorded_draft_dies() -> None:
    assert _visible(_stage("D-w01-t2")["draft"], _case("D-w01-t2")["text"]) == "own_write_denied"


@pytest.mark.parametrize(
    ("reply", "user_text"),
    [
        ("No, no añadí leche a la lista.", "¿añadiste leche a la lista?"),  # asked about BAXY's own act
        ("No añadí la leche a la lista.", "añade leche a la lista"),  # the act asked for
        ("No pude hacer la foto.", "¿Serías capaz de hacer foto ahora?"),  # a failed attempt: asserted_failure's
    ],
)
def test_a_denial_asked_for_is_no_invented_write(reply: str, user_text: str) -> None:
    assert llm.conversation_world_claim(reply, user_text) != "own_write_denied"


def test_p09_t3_the_retry_says_not_to_deny() -> None:
    writer = _Writer(["I did not add barbells to your fitness list.", "Barbells are already on your fitness list."])
    answer, _ = writer.chat(
        _case("D-p09-t3")["text"], history=_case("D-p09-t3")["lived"], conversation_kind="knowledge",
        response_language="en",
    )
    assert answer == "Barbells are already on your fitness list."
    assert "do not say what you did or did not do" in _system_text(writer.sent[1])


@pytest.mark.parametrize(
    "draft",
    [
        "Confirmed, the procedure will proceed.",  # v3o p24-t5 (published)
        "The plan is confirmed to proceed.",  # v3m p24-t5
        "Confirmado, el pedido seguirá adelante.",
        "The playback is now proceeding.",
    ],
)
def test_p24_t5_a_plan_settled_in_a_turn_that_ran_nothing(draft: str) -> None:
    assert llm.visible_reply_settles_a_plan(draft)
    assert _visible(draft, _case("D-p24-t5")["text"]) == "effect_claim"


@pytest.mark.parametrize(
    "draft",
    ["Confirmed that Paris is the capital of France.", "The trial will resume next week.",
     "¿Quieres que lo confirme?", "If you sign in to Netflix, the movie will play."],
)
def test_other_sentences_settle_nothing(draft: str) -> None:
    assert not llm.visible_reply_settles_a_plan(draft)


def test_p24_t5_the_recorded_drafts_die() -> None:
    for stage in ("first", "retry"):
        assert _visible(_stage("D-p24-t5", stage)["draft"], _case("D-p24-t5")["text"]) == "effect_claim"


def test_p27_t1_a_work_recommended_with_no_title_is_invented() -> None:
    third = _stage("D-p27-t1", "third")["draft"]
    assert third == _case("D-p27-t1")["published"]
    assert _visible(third, _case("D-p27-t1")["text"]) == "unnamed_work"
    assert llm.visible_reply_recommends_an_unnamed_work("Te recomiendo la última película de ciencia ficción.")


@pytest.mark.parametrize(
    "reply",
    [
        "You could watch «Interstellar» or «Arrival», two great sci-fi movies.",
        "You should watch Interstellar, a gripping movie about time and space.",
        "La última película de Kubrick fue Eyes Wide Shut.",
        "Una buena película siempre tiene un buen guion.",
        "What kind of movies do you usually enjoy?",
    ],
)
def test_a_named_work_or_no_recommendation_passes(reply: str) -> None:
    assert not llm.visible_reply_recommends_an_unnamed_work(reply)


def test_p27_t1_the_mind_s_honest_question_back_is_no_failure() -> None:
    # The App refused it as looks_like_failure and the fallback invented a film (events.jsonl posterior).
    rejected = _case("D-p27-t1")["app_rejection"]
    assert rejected["reason"] == "looks_like_failure" and ends_asking_the_person(rejected["reply"])
    assert _visible(rejected["reply"], _case("D-p27-t1")["text"]) == ""
    assert _visible("I couldn't find a movie for you. What do you like?", _case("D-p27-t1")["text"]) == "asserted_failure"
    # D-p26-t1's refused reply: an inability to act (BAXY does search the web) is still a failure told.
    assert _visible(
        "I can't browse the internet to find current movies. What kind of movies do you usually enjoy?",
        _case("D-p27-t1")["text"],
    ) == "asserted_failure"


# ------------------------------------------------------------------ wording


@pytest.mark.parametrize(
    "text",
    ["Gracias por la información, estas seguro al 100% que esto es así",  # p31-t2
     "Tengo la duda de si esta información es adecuada o puede que esté equivocada. ¿Qué tan confiable puedes ser?",
     "are you sure?", "is that right?", "¿puedo confiar en eso?"],
)
def test_p31_t2_p35_t3_how_far_the_last_answer_can_be_trusted(text: str) -> None:
    assert asks_about_reliability(text)
    assert INTENT_CAPABILITY not in read_request(text).intents


def test_p35_t3_what_baxy_does_is_still_a_capability_question() -> None:
    assert INTENT_CAPABILITY in read_request("¿qué puedes hacer?").intents
    assert not asks_about_reliability("¿qué puedes hacer?")


def test_p31_t2_the_reply_is_told_to_answer_about_the_last_answer() -> None:
    writer = _Writer(["No, no puedo asegurarlo: no encontré esa lista."])
    writer.chat(_case("D-p31-t2")["text"], history=_case("D-p31-t2")["lived"], conversation_kind="knowledge",
                response_language="es")
    system = _system_text(writer.sent[0])
    assert "cuánto puede fiarse de tu respuesta anterior" in system
    # The dialogue travels with it.
    assert _case("D-p31-t2")["lived"][-1]["content"] in _sent_text(writer.sent[0])


def test_p32_t2_the_list_asked_is_written_as_a_list() -> None:
    text = "Dame las claves que mencionas en esa respuesta en forma de lista o tabla."
    published = _case("D-p32-t2")["published"]
    assert asks_a_list_or_table(text)
    assert llm._misses_content_shape(published, text)
    listed = "- Conectar con lo que realmente importa\n- Mantener relaciones saludables\n- Encontrar propósito"
    assert not llm._misses_content_shape(listed, text)
    writer = _Writer([published, listed])
    answer, _ = writer.chat(text, history=_case("D-p32-t2")["lived"], conversation_kind="knowledge",
                            response_language="es")
    assert answer == listed
    assert "un elemento por línea" in _system_text(writer.sent[0])
    assert "un elemento por línea" in _system_text(writer.sent[1])


def test_p36_t2_more_lines_of_the_dialogue_are_written_as_dialogue() -> None:
    text = _case("D-p36-t2")["text"]
    assert adds_to_a_dialogue(text)
    recorded = _stage("D-p36-t2")["draft"]
    assert recorded == _case("D-p36-t2")["published"]
    assert _visible(recorded, text) == "content_shape"
    # The mind's own dialogue, refused by the App as looks_like_failure for Ash's «No puedo dejarlo ir».
    rejected = _case("D-p36-t2")["app_rejection"]
    assert rejected["reason"] == "looks_like_failure"
    assert "no puedo" not in without_quoted_speech(rejected["reply"]).casefold()
    assert not llm._misses_content_shape(rejected["reply"], text)
    assert _visible(rejected["reply"], text) == ""


def test_p27_t5_the_person_s_words_said_back_are_an_echo() -> None:
    assert llm._says_the_person_back("That is a lot.", "Nope, that's a lot.")
    assert _visible(_stage("D-p27-t5")["draft"], _case("D-p27-t5")["text"]) == "echo"
    assert not llm._says_the_person_back("That sounds good.", "That one sounds good.")  # p27-t4, reviewed ok
    assert not llm._says_the_person_back("Of course, that is a lot to take in.", "Nope, that's a lot.")
    # A greeting or thanks is answered in kind.
    assert not llm._says_the_person_back("¡Hola!", "hola")
    assert not llm._says_the_person_back("Gracias a ti.", "gracias")
    assert _visible("Buenas noches.", "buenas noches") == ""


def test_s001_the_hours_left_until_the_weekend_are_counted() -> None:
    stage = _stage("D-s001")
    situation = json.loads(stage["situation"])
    text = _case("D-s001")["text"]
    assert hours_until_asked(text) and not hours_until_asked("¿cuánto falta para el finde?")
    payload = llm._compose_situation_payload(situation, "es", text)
    # Observed Wednesday 2026-09-30 14:37 (UTC−3); the weekend begins on Saturday at 00:00.
    assert payload["days_until"] == 3 and payload["hours_until"] == "57 h 22 min"
    assert llm._misses_calendar_facts(stage["draft"], payload)  # «Quedan dos días para el fin de semana…»
    assert not llm._misses_calendar_facts("Quedan 57 h 22 min para el fin de semana; hoy es miércoles.", payload)
    assert "hours_until" in llm._calendar_instruction(text)


def test_p04_t1_the_person_s_question_said_back_asks_nothing() -> None:
    assert _case("D-p04-t1")["text"] == "Dónde?"
    assert not sidecar._recovery_question_is_valid("¿Dónde?", "Dónde?")
    assert sidecar._recovery_question_is_valid("¿Qué lugar buscas?", "Dónde?")
