"""M99 (2026-10-01): the wording rows of the independent review of the official-window DEV-D run v3x, and the reserve
audit causes A5 (the weather asked through what it decides) and A6 (an operation nobody asked for).

Evidence, part 1: %LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3x-devD/ (REVIEW.reviewed.jsonl, raw-replies.jsonl,
compose-audit.jsonl; trace = «t» + ordinal), the rows replayed here kept in tests/data/c03_m99_v3x_evidence.json.

1. A reply that says the person's words back (p27-t5) or BAXY's last message again (p31-t3) is no answer; new lines of
   a dialogue are only the new ones (p36-t3); calling off what was asked is acknowledged, never told as cancelled
   (p01-t3); how far the last answer can be trusted is answered without speaking of access (p35-t3).
2. A question back is asked in the person's language, not the one a translation was asked into (w15-t3); the recovery
   question is judged against the message (s053).
3. Reports: today's sunset behind the clock is past (s054); a reminder is never an order to the person (w18-t4).
4. A film to watch at a named cinema is looked up (p28-t1); code uses functions that exist (p30).

Part 2 (reserve held out: these tests use their own phrasings, never the reserve's): the weather decides a snow chore,
the car's roof and the time to go out walking, and «¿sabes el tiempo?»/«abre la temperatura» ask it (A5); the decider's
keyboard, wallpaper or routine on a message that names none of them, something offered to BAXY, and a clock said alone
act on nothing; a song is never a task, a light is never a title, information is never music and a singer's concert
calendar is not the person's agenda (A6).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from baxy_mind import llm
from baxy_mind import llm_prompts
from baxy_mind import payload_fact_checks
from baxy_mind import visible_defect
from baxy_mind import conversation_shape
from baxy_mind import dialogue_history
from baxy_mind import weather_facts
from baxy_mind.llm_chat import ConversationReplyContractError
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue, reading, temporal, web
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.grammar import _fold
from baxy_mind.semantic.notes import list_entry_request
from baxy_mind.semantic.patterns import _explicit_named_music_query, operation_domain_is_grounded
from baxy_mind.semantic.request import addressed_language
from baxy_mind import turn_recovery
from baxy_mind import context_decision

EVIDENCE = json.loads((Path(__file__).parent / "data" / "c03_m99_v3x_evidence.json").read_text(encoding="utf-8"))
TURNS = EVIDENCE["turns"]


def _raw(ident: str, attempt: int) -> str:
    return next(row["raw_reply"] for row in TURNS[ident]["raw"] if row["attempt"] == attempt)


def _turn(ident: str) -> list[dict]:
    return [{"role": "user", "content": TURNS[ident]["text"]}, {"role": "assistant", "content": TURNS[ident]["published"]}]


class _Writer(llm.LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats); every payload sent is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self._drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(copy.deepcopy(payload))
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def _said_to_the_model(payload: dict) -> str:
    return "\n".join(str(message["content"]) for message in payload["messages"])


# ------------------------------------------------------------------ 1. conversation replies


def test_d_p27_t5_the_persons_words_written_back_by_the_repair_are_refused() -> None:
    text = TURNS["D-p27-t5"]["text"]
    assert TURNS["D-p27-t5"]["published"] == "That's a lot."
    writer = _Writer([_raw("D-p27-t5", 1), _raw("D-p27-t5", 2)])
    with pytest.raises(ConversationReplyContractError) as refused:
        writer.chat(text, history=_turn("D-p27-t4"), conversation_kind="knowledge", response_language="en",
                    temperature=0.0)
    assert refused.value.audit_reason == "echo"
    # A greeting or thanks is still answered in kind.
    assert not dialogue_history._says_the_person_back("Thanks!", "thanks")


def test_d_p31_t3_the_last_answer_again_is_refused() -> None:
    text = TURNS["D-p31-t3"]["text"]
    last = TURNS["D-p31-t2"]["published"]
    assert TURNS["D-p31-t3"]["published"] == last
    writer = _Writer([_raw("D-p31-t3", 1), _raw("D-p31-t3", 2)])
    with pytest.raises(ConversationReplyContractError) as refused:
        writer.chat(text, history=_turn("D-p31-t2"), conversation_kind="social", response_language="es",
                    temperature=0.0)
    assert refused.value.audit_reason == "repeats_last_answer"
    # The first draft that is the last answer again is written again, told why.
    answer = "Gracias a ti; ojalá la próxima vez pueda comprobarlo antes de contestarte."
    writer = _Writer([last, json.dumps({"answer": answer})])
    reply, _ = writer.chat(text, history=_turn("D-p31-t2"), conversation_kind="social", response_language="es",
                           temperature=0.0)
    assert reply == answer
    assert "repetía palabra por palabra tu mensaje anterior" in _said_to_the_model(writer.sent[1])


def test_the_last_answer_asked_again_is_the_answer() -> None:
    last = "La capital de Australia es Canberra."
    assert dialogue_history._repeats_the_last_answer(last, last, "gracias")
    assert dialogue_history._repeats_the_last_answer("La capital de Australia es Canberra", last + " Tiene unos 450 000 habitantes.",
                                        "ok")
    assert not dialogue_history._repeats_the_last_answer(last, last, "¿qué dijiste?")
    assert not dialogue_history._repeats_the_last_answer("Es Canberra.", last, "gracias")


def test_d_p36_t3_new_lines_of_a_dialogue_are_only_the_new_ones() -> None:
    before = TURNS["D-p36-t2"]["published"]
    drafted = _raw("D-p36-t3", 1)
    new = conversation_shape._new_dialogue_lines(drafted, before)
    assert new.count("\n") == 0 and new.startswith("Ellen Ripley:") and "piel negra" in new
    for line in before.splitlines():
        assert line not in new
    writer = _Writer([drafted])
    reply, _ = writer.chat(TURNS["D-p36-t3"]["text"], history=_turn("D-p36-t2"), conversation_kind="knowledge",
                           response_language="es", temperature=0.0)
    assert reply == new
    # Nothing old, or nothing new: left as it is.
    assert conversation_shape._new_dialogue_lines("Ash: \"Nuevo.\"", before) == ""
    assert conversation_shape._new_dialogue_lines(before, before) == ""


def test_d_p01_t3_calling_off_what_was_asked_is_acknowledged() -> None:
    text = TURNS["D-p01-t3"]["text"]
    assert dialogue.takes_back(text, TURNS["D-p01-t2"]["text"])
    writer = _Writer(["Okay, I'll leave it there."])
    reply, _ = writer.chat(text, history=_turn("D-p01-t1") + _turn("D-p01-t2"), conversation_kind="knowledge",
                           response_language="en", temperature=0.0)
    assert reply == "Okay, I'll leave it there."
    said = _said_to_the_model(writer.sent[0])
    assert "calls off what they asked just before" in said and TURNS["D-p01-t2"]["published"] in said
    # Taking back an effect BAXY reports done is the retraction, not this.
    writer = _Writer(["Vale, quito las pesas de tu lista."])
    writer.chat("no, no añadas pesas", history=[{"role": "user", "content": "añade pesas a mi lista de gimnasio"},
                                              {"role": "assistant", "content": "He añadido pesas a tu lista."}],
                conversation_kind="knowledge", response_language="es", temperature=0.0)
    assert "deja sin efecto lo que pidió" not in _said_to_the_model(writer.sent[0])


def test_d_p35_t3_how_far_the_last_answer_can_be_trusted_is_answered_without_access() -> None:
    text = TURNS["D-p35-t3"]["text"]
    honest = "Lo que te dije del FODA de Adidas salió de lo que sé, sin comprobarlo: conviene verificar lo importante."
    writer = _Writer([_raw("D-p35-t3", 1), json.dumps({"answer": honest})])
    reply, _ = writer.chat(text, history=_turn("D-p35-t1"), conversation_kind="knowledge", response_language="es",
                           temperature=0.0)
    assert reply == honest
    # Before it writes, and again in the repair after the draft that spoke of access.
    for payload in writer.sent:
        assert "salió de lo que sabes, sin comprobarlo" in _said_to_the_model(payload)


# ------------------------------------------------------------------ 2. questions back


def test_d_w15_t3_the_question_back_is_in_the_persons_language() -> None:
    said = TURNS["D-w15-t3"]["text"]
    row = TURNS["D-w15-t3"]["drafts"][0]
    assert row["draft"] == "Could you clarify which specific detail is missing?"
    assert addressed_language(said, "en") == "es"
    assert addressed_language("translate this sentence into English", "en") == "en"
    assert addressed_language("respóndeme en inglés", "en") == "en"
    facts = {"situation": row["situation"]}
    question = "¿Cómo se llama el informe trimestral que quieres traducir?"
    assert visible_defect.compose_visible_defect(question, "clarification", said, facts) == ""
    # The recorded English question is now refused, and the writer is told the person's language.
    assert visible_defect.compose_visible_defect(row["draft"], "clarification", said, facts) == "wrong_language"
    writer = _Writer([question])
    assert writer.compose_user_message(said, "clarification", facts) == question
    assert "Idioma obligatorio: español" in _said_to_the_model(writer.sent[0])


def test_d_s053_the_recovery_question_that_offers_back_the_one_named_is_not_asked() -> None:
    text = TURNS["D-s053"]["text"]
    question = TURNS["D-s053"]["published"]
    model = MagicMock()
    model.clarify_after_turn_failure.return_value = question
    model.compose_user_message.return_value = question
    result = turn_recovery._recover_failed_turn({"id": "s053", "text": text, "history": []}, model,
                                          failure_kinds=("contract", "contract"))
    assert question not in (result.get("question"), result.get("reply"))
    model.clarify_after_turn_failure.return_value = "¿Qué Miguel?"
    result = turn_recovery._recover_failed_turn({"id": "s053", "text": text, "history": []}, model,
                                          failure_kinds=("contract", "contract"))
    assert (result["kind"], result["question"]) == ("clarify", "¿Qué Miguel?")


# ------------------------------------------------------------------ 3. reports


def test_d_s054_todays_sunset_behind_the_clock_is_past() -> None:
    text = TURNS["D-s054"]["text"]
    published = TURNS["D-s054"]["published"]
    assert published == "Se pondrá el sol en Curicó a las 19:48 de hoy."
    read = {"location": "Curico", "country": "Chile", "observedAtLocal": "2026-09-30T22:45",
            "today": {"date": "2026-09-30", "weekday": "miércoles", "sunrise": "07:12", "sunset": "19:48"}}
    seen = weather_facts._project_weather_read(read, text)
    assert seen["today"] == {"date": "2026-09-30", "weekday": "miércoles", "sunset": "19:48", "sunsetPassed": True}
    payload = {"operation": "weather.current", "seen": seen}
    assert weather_facts._weather_fact_defect(published, payload, text) == "weather_sun_time_passed"
    assert weather_facts._weather_fact_defect("Hoy el sol se puso en Curicó a las 19:48.", payload, text) == ""
    # Read before the sunset, the time to come is said as to come.
    earlier = weather_facts._project_weather_read({**read, "observedAtLocal": "2026-09-30T17:05"}, text)
    # M105: still ahead is marked False (not left unmarked), so «se puso» before it is caught.
    assert earlier["today"]["sunsetPassed"] is False
    assert weather_facts._weather_fact_defect(published, {"operation": "weather.current", "seen": earlier}, text) == ""
    assert "already happened today" in weather_facts._weather_focus(text, english=True)


def test_d_w18_t4_a_reminder_is_never_an_order_to_the_person() -> None:
    row = TURNS["D-w18-t4"]["drafts"][-1]
    assert row["draft"] == "Recuerda en 45 minutos que te toca tomar un descanso a las 23:56."
    text = TURNS["D-w18-t4"]["text"]
    assert payload_fact_checks._payload_fact_defect(row["draft"], row["payload"], text) == "schedule_told_as_order"
    for kept in ("Te recordaré tomar un descanso a las 23:56.", "I'll remind you to take a break at 23:56.",
                 "Listo: a las 23:56 te aviso para que tomes un descanso."):
        assert payload_fact_checks._payload_fact_defect(kept, row["payload"], text) == "", kept
    assert payload_fact_checks._payload_fact_defect("Remember to take a break at 23:56.", row["payload"], text) == (
        "schedule_told_as_order"
    )


# ------------------------------------------------------------------ 4. a cinema, code


def _tool(op: str) -> dict:
    return {"type": "function", "function": {
        "name": op.replace(".", "_"), "canonical_name": op, "description": f"Authenticated catalog leaf {op}.",
        "risk": "read_only", "parameters": {"type": "object", "properties": {}, "required": [],
                                            "additionalProperties": False}}}


_OPERATIONS = ("web.search", "weather.current", "system.time", "notification.schedule", "streaming.play.named",
               "input.keyboard.layout", "desktop.wallpaper.set", "routine.phrase.create", "media.play.query")
CATALOG = PlannerCatalog([_tool(op) for op in _OPERATIONS])


def _decided(text: str, decision: ContextDecision, history: list[dict] | None = None) -> dict:
    model = MagicMock()
    model.decide_in_context.return_value = decision
    model.clarify_after_turn_failure.return_value = "¿Qué quieres que haga?"
    model.chat.return_value = ("Hola.", [])
    model.detect_response_language.return_value = "es"
    turns = [*(history or []), {"role": "user", "content": text}]
    return context_decision._context_decided_result({"id": "m99", "text": text, "history": turns}, llm=model,
                                           planner_catalog=CATALOG)


def test_d_p28_t1_a_film_at_a_named_cinema_is_looked_up() -> None:
    text = TURNS["D-p28-t1"]["text"]
    assert TURNS["D-p28-t1"]["decision"] == "conversation:unsupported"
    assert web.asks_what_a_cinema_shows(text)
    result = _decided(text, ContextDecision(request=text, decision="limit", operations=(), question=""))
    assert (result["kind"], result["operation"]) == ("action", "web.search")
    for other in ("I like movies in English", "¿me recomiendas películas en Español?", "quiero ver una peli"):
        assert not web.asks_what_a_cinema_shows(other), other
    assert web.asks_what_a_cinema_shows("qué películas dan en el Cine Hoyts de Ñuñoa")


def test_d_p30_code_uses_what_exists_and_does_the_join() -> None:
    for prompt in (llm_prompts.CODE_REQUEST_PROMPT, llm_prompts.CODE_REQUEST_PROMPT_EN):
        assert "exact" in prompt
    assert "el código hace esa unión" in llm_prompts.CODE_REQUEST_PROMPT


# ------------------------------------------------------------------ part 2, A5: the weather asked through what it decides


@pytest.mark.parametrize(
    "text",
    [
        "do I have to shovel the sidewalk tomorrow?",
        "¿tendré que quitar la nieve de la vereda mañana?",
        "¿conviene abrir el techo corredizo hoy?",
        "should we open the moonroof",
        "what time should I go for a run",
        "¿cuándo me conviene salir a caminar?",
        "¿me dices el tiempo?",
        "muéstrame la temperatura",
    ],
)
def test_the_weather_is_read_when_it_decides_the_question(text: str) -> None:
    assert web._weather_lookup_query(text) is not None, text


@pytest.mark.parametrize(
    "text",
    [
        "abre el techo solar",
        "¿a qué hora debería salir a trabajar?",
        "should I open the file",
        "dime el tiempo de cocción",
        "¿sabes el tiempo que tarda el envío?",
        "where can I buy a snow shovel",
    ],
)
def test_what_the_weather_does_not_decide_is_not_read(text: str) -> None:
    assert web._weather_lookup_query(text) is None, text


# ------------------------------------------------------------------ part 2, A6: an operation nobody asked for


@pytest.mark.parametrize(
    ("text", "restated", "operation", "acts"),
    [
        ("arranca la charla de ted en inglés", "Cambia el idioma del teclado a inglés.", "input.keyboard.layout", False),
        ("cambia el teclado a inglés", "Cambia el idioma del teclado a inglés.", "input.keyboard.layout", True),
        ("muéstrame un azul tranquilo", "Cambia el fondo de escritorio a un azul.", "desktop.wallpaper.set", False),
        ("pon un fondo de pantalla azul", "Cambia el fondo de escritorio a azul.", "desktop.wallpaper.set", True),
        ("avísame cuando oigas algo de Chile", "Crea una rutina que haga una captura al oír «Chile».",
         "routine.phrase.create", False),
    ],
)
def test_an_object_the_decider_brought_is_asked_about(text: str, restated: str, operation: str, acts: bool) -> None:
    result = _decided(text, ContextDecision(request=restated, decision="action", operations=(operation,), question=""))
    assert result["kind"] == ("action" if acts else "clarify"), result


def test_something_offered_to_baxy_orders_nothing() -> None:
    for offered in ("¿quieres una pizza?", "quieres netflix y una manta", "do you want a coffee?"):
        assert dialogue.offers_to_baxy(offered), offered
    for asked in ("¿quieres poner la tele?", "do you want to open spotify", "¿quieres que la ponga?",
                  "quieres ponerme jazz"):
        assert not dialogue.offers_to_baxy(asked), asked
    result = _decided("¿quieres netflix y palomitas?", ContextDecision(
        request="Pon algo en Netflix.", decision="action", operations=("streaming.play.named",), question=""))
    assert result["kind"] == "conversation"


def test_a_clock_said_alone_sets_nothing_unless_it_answers() -> None:
    for alone in ("a las ocho y cuarto", "las nueve de la noche", "half past seven", "las 7:30"):
        assert temporal.said_only_a_clock(alone), alone
    for other in ("seven", "ponme una alarma a las 7", "mañana a las ocho tengo dentista"):
        assert not temporal.said_only_a_clock(other), other
    schedule = ContextDecision(request="Pon una alarma a las 21:30.", decision="action",
                               operations=("notification.schedule",), question="")
    assert _decided("las nueve y media", schedule)["kind"] == "clarify"
    asked = [{"role": "user", "content": "despiértame mañana"}, {"role": "assistant", "content": "¿A qué hora?"}]
    assert _decided("las nueve y media", schedule, asked)["kind"] == "action"


def test_a_song_is_never_a_task_and_a_light_is_never_a_title() -> None:
    assert list_entry_request("mete una canción en la lista activa") is None
    assert list_entry_request("añade pan a la lista de la compra") == ("pan", "lista de la compra")
    assert _explicit_named_music_query("pon una luz cálida") is None
    assert _explicit_named_music_query("pon Despacito") == "Despacito"


def test_information_is_never_music() -> None:
    found = reading.read("useful garage information", available_operations=("media.play.query", "media.play.youtube"))
    assert found.effects is None or "media.play.query" not in found.effects.operations


def test_a_published_event_calendar_is_not_the_persons_agenda() -> None:
    public = "haz un resumen del calendario de partidos del colo colo"
    assert web.public_event_subject(_fold(public))
    assert operation_domain_is_grounded(public, "calendar.event.list") is False
    assert not web.public_event_subject(_fold("muéstrame mi calendario de la semana"))
