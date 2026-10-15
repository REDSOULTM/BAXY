"""M89 (2026-09-30, independent review of the official-window DEV-D run v3r, HEAD 50cee2c6): the rows v3o had right
and v3r broke, and the reviewer's remaining search, argument and wording rows.

Evidence: %LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3r-devD/ (REVIEW.reviewed.jsonl, RUN.jsonl,
compose-audit.jsonl, turn-audit.jsonl; trace = «t» + ordinal), the rows replayed here kept in
tests/data/c03_m89_v3r_evidence.json. Each test replays the recorded message, the decider's recorded restatement and
decision (turn-audit), or the recorded draft and payload the composer judged:

1. The place of the weather (p20-t2 «…for March 2nd in Palo Alto» asked the service for «March 2nd in Palo Alto»;
   w04-t1 «mañana viajo temprano a Rosario … ¿cómo va a estar el clima allá?» read Curicó's).
2. List entries said before BAXY's question (p37-t2 «Include items on the shopping list» after «beer and chips»).
3. A possessive inside a set phrase is not the person's data (p24-t2 «…I change my mind. Now I want … like Lizzo.»).
4. The newest release of a program is public (w20-t3 «what's the latest version of Python right now?»).
5. Where to find something names the site (p34-t3): the retry hint no longer forbids what the veto lets through.
6. The partial report after «no lo encontré» (p31-t1, p34-t1): both drafts opened «Los datos proporcionados…».
7. Wording: s003 «sábado 26 de 2026», s006 the limit said twice, s042 «No te pido encargar…», p35-t3 «lo que me diste
   en la situación».
8. The album asked of what is playing (w05-t3 «de qué disco es esta» → the song's name again).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from baxy_mind import consulted_answers
from baxy_mind import payload_fact_checks
from baxy_mind import search_report
from baxy_mind import visible_defect
from baxy_mind import unsupported_answers
from baxy_mind import limit_voice
from baxy_mind import clock_facts
from baxy_mind.llm import LlmRuntime
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.media import asks_the_album, asks_what_is_playing
from baxy_mind.semantic.patterns import list_entries_said_before
from baxy_mind.semantic.system import _weather_location
from baxy_mind.semantic.web import _weather_lookup_query, asks_latest_release, names_own_data
from baxy_mind import context_decision

TURNS = json.loads(
    (Path(__file__).parent / "data" / "c03_m89_v3r_evidence.json").read_text(encoding="utf-8")
)["turns"]


# ------------------------------------------------------------------ 1. the place of the weather


def test_d_p20_t2_a_time_said_before_the_place_is_not_the_place() -> None:
    # turn-audit request 1024: the decider restated «What's the weather forecast for March 2nd in Palo Alto?»; the
    # service answered weather_place_not_found for «March 2nd in Palo Alto».
    restated = "What's the weather forecast for March 2nd in Palo Alto?"
    assert TURNS["D-p20-t2"]["drafts"][0]["payload"]["reason"]["cause"].startswith("the weather service knows no place")
    assert _weather_location(restated) == "Palo Alto"
    assert _explicit_arguments_from_evidence("weather.current", restated) == {"location": "Palo Alto"}
    for text, place in (
        ("¿Cómo pinta el clima mañana en Cali?", "Cali"),
        ("clima para el viernes en Lima por favor", "Lima"),
        ("weather for tomorrow in New York", "New York"),
        ("What's the weather in San Leandro on Monday, October 5th?", "San Leandro"),
        ("clima de mañana en Buenos Aires", "Buenos Aires"),
    ):
        assert _weather_location(text) == place, text


def test_d_w04_t1_the_question_that_closes_the_message_is_the_weather_asked_there() -> None:
    # turn-audit request 1365 (explicit_effects): weather.current with no location, and Curicó's weather was read.
    text = TURNS["D-w04-t1"]["text"]
    assert "Curicó" in TURNS["D-w04-t1"]["published"]
    assert _weather_lookup_query(text) is not None
    assert _weather_location(text) == "Rosario"
    # Ronda 19: «Che» marks Argentina; the hint goes with the town (the adapter uses it only among namesakes).
    assert _explicit_arguments_from_evidence("weather.current", text) == {"location": "Rosario", "dialectCountry": "AR"}
    assert _weather_location("I'm flying out tomorrow to Denver. What's the weather like there?") == "Denver"
    # A person met there is no town, and a message with no weather question in it is none.
    assert _weather_location("voy a ver a Juan, ¿cómo está el clima allá?") is None
    assert _weather_lookup_query("mañana viajo a Rosario, ¿me pasas el número de mi vieja?") is None


# ------------------------------------------------------------------ helpers of the decided turn


class _Decider:
    """The contextual decider of v3r: the recorded restatement and decision (turn-audit)."""

    def __init__(self, request: str, decision: str, operations: tuple[str, ...] = (), **arguments: object) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(
            request=request, decision=decision, operations=operations, question="", arguments=tuple(arguments.items()),
        )
        self.decisions = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        self.decisions += 1
        return self.decided

    @staticmethod
    def clarify_after_turn_failure(*_args: object, **_kwargs: object) -> str:
        return "Would you like me to add beer and chips to your shopping list?"


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


TOOLS = ("task.create", "task.delete", "web.search", "software.python.status", "system.identity", "weather.current")
WELCOME = ("assistant", "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?")


def _decided(text: str, history: list[tuple[str, str]], model: _Decider) -> dict[str, object]:
    turns = [{"role": role, "content": content} for role, content in history]
    return context_decision._context_decided_result(
        {"id": "m89", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog([_tool(name) for name in TOOLS]),
    )


# ------------------------------------------------------------------ 2. list entries said before the question


BEER = [WELCOME, ("user", "beer and chips"), ("assistant", TURNS["D-p37-t1"]["published"])]


def test_d_p37_t2_the_entries_the_question_was_about_go_on_the_list_named() -> None:
    # v3r: the M84 guard turned the decider's action into a question, and the question asked to confirm the add.
    assert TURNS["D-p37-t2"]["published"] == "Would you like me to add beer and chips to your shopping list?"
    model = _Decider("Add beer and chips to the shopping list.", "action", ("task.create",), title="beer and chips",
                     details="shopping list")
    result = _decided(TURNS["D-p37-t2"]["text"], BEER, model)
    # M113: the restatement names two entries, and each is a task of its own (M111 makes each one a step).
    assert result["kind"] == "plan" and result["effectOperations"] == ["task.create", "task.create"]
    assert list_entries_said_before("Include items on the shopping list", "beer and chips",
                                    "What would you like me to do with beer and chips?")


def test_an_item_asked_anew_is_still_asked() -> None:
    # M84 (DEV-D v3o p17-t3) stands: after «hiking» was added, «add an item to my swimming list» names no entry.
    history = [WELCOME, ("user", "add an item to a list"), ("assistant", "What item would you like to add to the list?"),
               ("user", "hiking"), ("assistant", "I've added hiking to your list.")]
    result = _decided("nevermind add an item to my swimming list", history,
                      _Decider("Add swimming to my list.", "action", ("task.create",), title="swimming"))
    assert result["kind"] == "clarify"
    # Not after a question that is about something else, nor when the last message was a request of its own.
    assert not list_entries_said_before("Include items on the shopping list", "beer and chips", "Anything else?")
    assert not list_entries_said_before("Include items on the shopping list", "add beer and chips",
                                        "What would you like me to do with add beer and chips?")


# ------------------------------------------------------------------ 3. a possessive inside a set phrase


def test_d_p24_t2_changing_ones_mind_is_no_data_of_ones_own() -> None:
    text = TURNS["D-p24-t2"]["text"]
    assert not names_own_data(text)
    history = [WELCOME, ("user", "I am in a mood to watch movie online and I need your help to search for a nice "
                                 "Fantasy Movie like Elijah Wood."), ("assistant", "I couldn't find it.")]
    # turn-audit request 1104: the decider's web.search (argument «query») became a clarification as own data.
    result = _decided(text, history, _Decider(text, "action", ("web.search",), query="drama movies with Lizzo"))
    assert result["kind"] == "action" and result["operation"] == "web.search"
    for own in ("what's on my calendar", "llama a mi madre", "where do I live", "cuándo es mi cita"):
        assert names_own_data(own), own
    for idiom in ("in my opinion who is the best singer", "en mi opinión quién es mejor, Messi o Maradona",
                  "oh my god who won the match"):
        assert not names_own_data(idiom), idiom


# ------------------------------------------------------------------ 4. the newest release is public


def test_d_w20_t3_the_latest_version_is_looked_up_not_read_from_this_pc() -> None:
    text = TURNS["D-w20-t3"]["text"]
    assert TURNS["D-w20-t3"]["published"].startswith("Están instaladas las versiones")
    assert asks_latest_release(text)
    history = [WELCOME, ("user", "can you write a python script"), ("assistant", "```python\nprint(1)\n```")]
    # turn-audit request 1754: «¿Qué versiones de Python hay instaladas en el PC?», software.python.status.
    model = _Decider("¿Qué versiones de Python hay instaladas en el PC?", "action", ("software.python.status",))
    result = _decided(text, history, model)
    assert result["kind"] == "action" and result["operation"] == "web.search"
    assert result["objective"] == text
    for installed in ("and which one tengo instalada yo?", "¿tengo la última versión de python?",
                      "is the latest version of python installed on my pc?", "qué versión de python tengo"):
        assert not asks_latest_release(installed), installed
    installed = _decided("qué versión de python tengo", history,
                         _Decider("¿Qué versión de Python tengo?", "action", ("software.python.status",)))
    assert installed["operation"] == "software.python.status"


# ------------------------------------------------------------------ 5. where to find it names the site


def _search_facts(payload: dict) -> dict:
    return {"situation": json.dumps({
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": payload["seen"],
    }, ensure_ascii=False)}


def test_d_p34_t3_a_site_that_holds_the_list_is_the_answer() -> None:
    turn = TURNS["D-p34-t3"]
    payload = turn["drafts"][0]["payload"]
    # v3r: first «No hay un listado único…» (unsourced), then «Las fuentes mencionan…» (the search shown), then the
    # vague third draft was published.
    assert [draft["reason"] for draft in turn["drafts"]] == [
        "search_report_unsourced_claim", "search_report_shows_the_search", "",
    ]
    named = ("Wikipedia tiene la categoría «Cápsulas del tiempo», y nanova.org reúne 8 cápsulas del tiempo "
             "históricas que fascinan hoy.")
    assert not search_report._search_report_shows_the_search(named, payload, turn["text"])
    assert search_report._search_report_shows_the_search(turn["drafts"][1]["draft"], payload, turn["text"])


# ------------------------------------------------------------------ 6. the partial report after «no lo encontré»


class _Writer(LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.requests: list[dict] = []

    def _post(self, payload: dict, **_kwargs: object) -> dict:
        self.requests.append(copy.deepcopy(payload))
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


@pytest.mark.parametrize("ident", ["D-p31-t1", "D-p34-t1"])
def test_the_partial_report_is_told_its_own_defect(ident: str) -> None:
    turn = TURNS[ident]
    recorded = [draft for draft in turn["drafts"] if draft["stage"].startswith("partial_after_not_found")]
    assert [draft["reason"] for draft in recorded] == ["copied_instruction", "copied_instruction"]
    assert all(draft["draft"].startswith("Los datos proporcionados") for draft in recorded)
    assert "nunca por «los datos»" in consulted_answers.PARTIAL_REPORT_PROMPT
    not_found = next(draft for draft in turn["drafts"] if draft["stage"] == "first")
    writer = _Writer([recorded[0]["draft"], recorded[1]["draft"]])
    answer = writer._answer_after_not_found(
        "No lo encontré.", turn["text"], _search_facts(not_found["payload"]), said=None, deadline=None,
    )
    assert answer.startswith("No pude comprobarlo") or answer == ""
    assert writer.requests[0]["messages"][0]["content"] == consulted_answers.PARTIAL_REPORT_PROMPT
    assert writer.requests[1]["messages"][0]["content"].endswith("di directamente lo que dicen.")


# ------------------------------------------------------------------ 7. wording


def test_d_s003_a_day_and_a_year_with_no_month_is_a_broken_date() -> None:
    draft = TURNS["D-s003"]["drafts"][0]
    assert draft["draft"] == "El finde pasado cayó el sábado 26 de 2026 y el domingo 27 de 2026."
    text = TURNS["D-s003"]["text"]
    assert payload_fact_checks._payload_fact_defect(draft["draft"], draft["payload"], text) == "missing_name"
    for whole in ("El finde pasado cayó el sábado 26 y el domingo 27 de septiembre.",
                  "El finde pasado fue el sábado 26 de septiembre de 2026 y el domingo 27 de septiembre de 2026."):
        assert payload_fact_checks._payload_fact_defect(whole, draft["payload"], text) == "", whole
    assert clock_facts._DATE_WITHOUT_MONTH.search("saturday 26, 2026") is not None
    assert clock_facts._DATE_WITHOUT_MONTH.search("saturday, september 26, 2026") is None


def test_d_s006_d_s042_a_limit_said_twice_or_as_asking_the_person() -> None:
    assert limit_voice.limit_voice_defect(TURNS["D-s006"]["published"], TURNS["D-s006"]["text"]) == "limit_repeats_itself"
    assert unsupported_answers._unsupported_answer_contract_failure(TURNS["D-s006"]["published"], TURNS["D-s006"]["text"]) == (
        "unsupported_limit_repeats_itself"
    )
    assert limit_voice.limit_voice_defect("No confirmo pedidos.", TURNS["D-s006"]["text"]) == ""
    assert limit_voice.limit_voice_defect(TURNS["D-s042"]["published"], TURNS["D-s042"]["text"]) == "limit_asks_the_person"
    assert limit_voice.limit_voice_defect("No encargo ni compro pasteles de camote.", TURNS["D-s042"]["text"]) == ""
    # The owner's own wording of a limit («No detengo la cámara inteligente. Eso no lo hago.») is two clauses.
    assert limit_voice.limit_voice_defect("No detengo la cámara inteligente. Eso no lo hago.", "detén la cámara") == ""


def test_d_p35_t3_the_situation_is_the_prompt_spoken_of() -> None:
    turn = TURNS["D-p35-t3"]
    retry = next(draft for draft in turn["drafts"] if draft["stage"] == "retry")
    assert retry["published"] and "lo que me diste en la situación" in retry["draft"]
    assert visible_defect.compose_visible_defect(retry["draft"], "status", turn["text"], {}) == "copied_instruction"
    assert visible_defect.compose_visible_defect(
        "Puedo equivocarme: lo que te dije sale de lo que leí, y si algo te suena raro, conviene comprobarlo.",
        "status", turn["text"], {},
    ) == ""
    assert visible_defect.compose_visible_defect("Te conviene ahorrar en la situación que me contaste.", "status", "consejo", {}) == ""


# ------------------------------------------------------------------ 8. the album of what is playing


def _media_facts(payload: dict) -> dict:
    return {"situation": json.dumps({
        "kind": "operation", "operation": "media.status", "polarity": "success", "verified": True, "succeeded": True,
        "observed": payload["seen"],
    }, ensure_ascii=False)}


def test_d_w05_t3_the_album_asked_is_said_or_said_unknown() -> None:
    turn = TURNS["D-w05-t3"]
    draft = turn["drafts"][0]
    assert draft["draft"] == "Está sonando Piano Bar de Charly García."
    assert asks_the_album(turn["text"]) and asks_what_is_playing(turn["text"])
    # The session read of v3r carried no album: repeating the song does not answer.
    assert visible_defect.compose_visible_defect(draft["draft"], "status", turn["text"], _media_facts(draft["payload"])) == (
        "missing_name"
    )
    unknown = "Está sonando Piano Bar de Charly García; de qué disco es no lo sé desde aquí."
    assert visible_defect.compose_visible_defect(unknown, "status", turn["text"], _media_facts(draft["payload"])) == ""
    # With the album the session publishes (WindowsMediaSessionAdapter now writes «album»), it is the answer.
    published = copy.deepcopy(draft["payload"])
    published["seen"]["album"] = "Clics Modernos"
    facts = _media_facts(published)
    assert visible_defect.compose_visible_defect(draft["draft"], "status", turn["text"], facts) == "missing_name"
    answer = "Está sonando Piano Bar de Charly García, del disco Clics Modernos."
    assert visible_defect.compose_visible_defect(answer, "status", turn["text"], facts) == ""
    # Another question about what is playing keeps its checks.
    assert not asks_the_album("pon el disco Clics Modernos")
