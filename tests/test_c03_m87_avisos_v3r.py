"""M87 (2026-09-30, DEV-D real-app run v3r, HEAD 50cee2c6 = v3o + M83 + M84 + M85): the five turns that ended with no
published reply (⚠), new against v3o. Every payload, situation and draft is the one that run recorded
(tests/data/c03_m87_v3r_evidence.json, from window/v3r-devD/compose-audit.jsonl and RUN.jsonl); the shell's side is
tests/Baxy.Integration.Tests/M87AvisosV3rTests.cs.

- D-s001 «¿cuántas horas quedan para el finde?» (mind): M85 counts the hours left (54 h 46 min); the drafts that said
  them («quedan 54 horas y 46 minutos») were refused as a contrary clock (reversed_result), the one without today's
  weekday as missing_name, and there was no final. The hours counted are allowed like a countdown's, and the weekend
  countdown has a final from its facts.
- D-s025 «si pasan cuarenta minutos, ¿qué hora será?» (App): the mind's final «Serán las 17:54.» (17:14 + 40 min) was
  filtered by the shell, whose later-clock reader lacked M85's «si pasan». The drafts added the forty minutes twice
  (18:34); the writer is told the span is already added.
- D-p23-t2, D-p24-t1, D-p29-t2 (App): M83's answer from memory was asked in three forms at once and written in all
  three («Ingredients:» of a drama film, «A recipe for a spooky atmosphere»), and was published without the checks
  of any other report; the shell refused it (reversed_result, unsafe_language, missing_literal_fact). The form is now
  read from the request, and the answer passes the mind's twin of the shell's judgement, which masks the memory
  notice as the shell does.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from baxy_mind import llm
from baxy_mind.llm import LlmRuntime
from baxy_mind.semantic.knowledge import memory_answer_form

TURNS = json.loads(
    (Path(__file__).parent / "data" / "c03_m87_v3r_evidence.json").read_text(encoding="utf-8")
)["turns"]


def _facts(ident: str) -> dict:
    return {"situation": json.dumps(TURNS[ident]["situation"], ensure_ascii=False)}


def _recorded(ident: str, stage: str) -> str:
    return next(item["draft"] for item in TURNS[ident]["drafts"] if item["stage"] == stage)


def _visible(draft: str, ident: str, user: str | None = None) -> str:
    return llm.compose_visible_defect(draft, "status", TURNS[ident]["text"] if user is None else user, _facts(ident))


class _Writer(LlmRuntime):
    """The drafts stand in for the model, in order (the last one repeats); every request is kept."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        content = self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def test_the_evidence_is_the_five_unpublished_turns() -> None:
    assert {ident: TURNS[ident]["terminal"] for ident in TURNS} == {
        "D-s001": "composition_failed", "D-s025": "filtered", "D-p23-t2": "composition_failed",
        "D-p24-t1": "composition_failed", "D-p29-t2": "composition_failed",
    }


# ------------------------------------------------------------------ D-s001: the hours left until the weekend


def test_d_s001_the_hours_counted_are_not_a_contrary_clock() -> None:
    assert TURNS["D-s001"]["payload"]["hours_until"] == "54 h 46 min"
    for stage in ("first", "third"):
        assert _visible(_recorded("D-s001", stage), "D-s001") == "", stage
    # Today's weekday stays owed (the shell's missing_literal_fact), and a clock that is neither this PC's nor the
    # hours counted is still a contrary claim.
    assert _visible(_recorded("D-s001", "retry"), "D-s001") == "missing_name"
    assert _visible(
        "Hoy es miércoles y quedan 54 horas y 46 minutos para el fin de semana; son las 18:20.", "D-s001",
    ) == "reversed_result"


def test_d_s001_the_first_recorded_draft_is_published() -> None:
    drafts = [item["draft"] for item in TURNS["D-s001"]["drafts"]]
    reply = _Writer(drafts).compose_user_message(TURNS["D-s001"]["text"], "status", _facts("D-s001"))
    assert reply == drafts[0]


def test_d_s001_the_weekend_countdown_has_a_final_from_its_facts() -> None:
    situation, payload, text = TURNS["D-s001"]["situation"], TURNS["D-s001"]["payload"], TURNS["D-s001"]["text"]
    final = llm._deterministic_final(situation, payload, text, "es")
    assert final == "Hoy es miércoles; quedan 54 h 46 min para el fin de semana."
    assert _visible(final, "D-s001") == ""
    assert llm._payload_fact_defect(final, payload, text, said=text) == ""
    # The three drafts refused: the final from the facts is published instead of no reply.
    weekday_missing = _recorded("D-s001", "retry")
    reply = _Writer([weekday_missing]).compose_user_message(text, "status", _facts("D-s001"))
    assert reply == final


def test_the_weekend_countdown_final_in_days_in_english_and_on_the_weekend() -> None:
    wednesday = datetime(2026, 9, 30, 17, 13, tzinfo=timezone(timedelta(hours=-3)))
    situation = TURNS["D-s001"]["situation"]
    days = {"operation": "system.time", **llm._calendar_facts(wednesday, "¿cuánto falta para el finde?", "es")}
    assert llm._deterministic_final(situation, days, "¿cuánto falta para el finde?", "es") == (
        "Hoy es miércoles; quedan 3 días para el fin de semana."
    )
    english = {"operation": "system.time", **llm._calendar_facts(wednesday, "how many hours until the weekend", "en")}
    assert llm._deterministic_final(situation, english, "how many hours until the weekend", "en") == (
        "Today is Wednesday; 54 h 47 min left until the weekend."
    )
    saturday = {"operation": "system.time", **llm._calendar_facts(wednesday + timedelta(days=3), "¿cuánto falta para el finde?", "es")}
    assert llm._deterministic_final(situation, saturday, "¿cuánto falta para el finde?", "es") == (
        "Hoy es sábado: ya es fin de semana."
    )
    # A weekday named as the target is not this final's (it would name a second weekday).
    friday = {"operation": "system.time", **llm._calendar_facts(wednesday, "¿cuánto falta para el viernes?", "es")}
    assert llm._deterministic_final(situation, friday, "¿cuánto falta para el viernes?", "es") == ""


# ------------------------------------------------------------------ D-s025: the clock after a span that passes


def test_d_s025_the_writer_is_told_the_span_is_already_added() -> None:
    text = TURNS["D-s025"]["text"]
    assert TURNS["D-s025"]["payload"]["clock"] == "17:54"  # 17:14 observed + 40 min (M40)
    # The three recorded drafts added the forty minutes again (18:34) and stay refused.
    for stage in ("first", "retry", "third"):
        assert _visible(_recorded("D-s025", stage), "D-s025") != "", stage
    # The final the shell filtered is right, and a draft that copies the clock is published.
    assert _visible(_recorded("D-s025", "deterministic_fallback"), "D-s025") == ""
    writer = _Writer(["Dentro de cuarenta minutos serán las 17:54."])
    assert writer.compose_user_message(text, "status", _facts("D-s025")) == "Dentro de cuarenta minutos serán las 17:54."
    prompt = " ".join(str(message["content"]) for message in writer.requests[0]["messages"])
    assert "Never add the span again" in prompt


# ------------------------------------------------------------------ D-p23-t2, D-p24-t1, D-p29-t2: memory answers


@pytest.mark.parametrize(("request_text", "form"), [
    ("Search for scary movies.", "list"),
    ("Look for a drama film.", "prose"),
    ("Search for a nice fantasy movie like Elijah Wood.", "prose"),
    ("Dime los últimos 10 presidentes democráticos de Argentina", "list"),
    ("Dame una receta sencilla de arepas de queso.", "recipe"),
    ("¿Cuál es la distancia de Barcelona a París?", "prose"),
    ("recomiéndame unas películas de terror", "list"),
])
def test_the_form_of_an_answer_from_memory_is_read_from_the_request(request_text: str, form: str) -> None:
    assert memory_answer_form(request_text) == form


def test_only_the_form_asked_is_in_the_prompt() -> None:
    listing = llm._memory_answer_prompt("Search for scary movies.", [], True)
    assert "numbered list" in listing and "Ingredients" not in listing
    prose = llm._memory_answer_prompt("Look for a drama film.", [], True)
    assert "two to four sentences" in prose and "Ingredients" not in prose and "list" not in prose
    recipe = llm._memory_answer_prompt("Dame una receta sencilla de arepas de queso.", [], False)
    assert "«Ingredientes:»" in recipe and "lista" not in recipe


# The shell's jargon terms, as ModelMessageComposer sends them (UserMessagePolicy.ForbiddenResponseTerms).
SHELL_TERMS = [
    "planner", "router", "tool", "catálogo", "catalogo", "schema", "operación", "operacion", "capacidad interna",
    "language model", "modelo de lenguaje", "qwen", "resolver el efecto", "el efecto '", "opaque identity",
    "observed profile", "grounding", "checkpoint", "reconciliación", "reconciliacion", "motor local", "core",
    "datos verificables", "pasos verificables", "identificador interno", "wmi",
]
MEMORY_REQUEST = {
    "D-p23-t2": "Look for a drama film.",
    "D-p24-t1": "Search for a nice fantasy movie like Elijah Wood.",
    "D-p29-t2": "Search for scary movies.",
}


@pytest.mark.parametrize("ident", ["D-p23-t2", "D-p24-t1", "D-p29-t2"])
def test_the_recorded_answers_from_memory_are_refused_by_the_mind_too(ident: str) -> None:
    # The shell refused each (reversed_result, unsafe_language, missing_literal_fact); the mind now judges them first,
    # and with both attempts refused the not-found report stands.
    writer = _Writer([_recorded(ident, "from_memory")])
    facts = {**_facts(ident), "forbiddenResponseTerms": SHELL_TERMS}
    assert writer._compose_consulted_answer(
        MEMORY_REQUEST[ident], facts, TURNS[ident]["situation"], "en", writer._post, None, "t", memory=True,
    ) is None
    assert len(writer.requests) == 2


@pytest.mark.parametrize(("ident", "honest"), [
    ("D-p29-t2", "I couldn't check this; from memory, it may not be exact:\n1. The Conjuring (2013)\n2. Hereditary (2018)\n"
                 "3. The Exorcist (1973)"),
    ("D-p23-t2", "I couldn't check this; from memory, it may not be exact: The Shawshank Redemption (1994) is a drama "
                 "film about two prisoners who become friends over many years."),
    ("D-p24-t1", "I couldn't check this; from memory, it may not be exact: The Lord of the Rings: The Fellowship of the "
                 "Ring (2001) is a fantasy film starring Elijah Wood."),
])
def test_an_answer_from_memory_in_the_form_asked_passes_the_mind_twin(ident: str, honest: str) -> None:
    assert _visible(honest, ident) == ""
    # A failure of BAXY's own after the notice is still one.
    assert _visible(
        "I couldn't check this; from memory, it may not be exact: I cannot browse the internet right now.", ident,
    ) != ""


def test_d_p29_t2_a_refused_memory_answer_is_retried_and_the_second_is_said() -> None:
    reply = _recorded("D-p29-t2", "not_found_fallback")
    honest = "I couldn't check this; from memory, it may not be exact:\n1. The Conjuring (2013)\n2. Hereditary (2018)"
    writer = _Writer([_recorded("D-p29-t2", "from_memory"), honest])
    answer = writer._answer_after_not_found(reply, "Search for scary movies.", _facts("D-p29-t2"), said=None, deadline=None)
    assert answer == honest
    assert len(writer.requests) == 2
    assert "numbered list" in writer.requests[0]["messages"][0]["content"]
    assert "no headings" in writer.requests[1]["messages"][-1]["content"]


def test_d_p23_t2_two_refused_memory_answers_leave_the_not_found_report() -> None:
    reply = _recorded("D-p23-t2", "third")
    writer = _Writer([_recorded("D-p23-t2", "from_memory")])
    assert writer._answer_after_not_found(
        reply, "Look for a drama film.", _facts("D-p23-t2"), said=None, deadline=None,
    ) in {"", reply}
