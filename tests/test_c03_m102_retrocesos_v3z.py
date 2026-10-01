"""M102 (2026-10-01, independent review of the official-window DEV-D run v3z): regressions and open items.

Evidence: %LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3z-devD/ (REVIEW.reviewed.jsonl, RUN.jsonl,
turn-audit.jsonl, compose-audit.jsonl; trace = «t» + ordinal); the payloads and drafts replayed here are in
tests/data/c03_m102_evidence.json.

1. D-w18-t5 «wait no, make it una hora» after «y remind me en 45 minutes to take a break»: the decider chose
   notification.schedule alone, restated «Recuerda tomar un descanso a las 04:12.», and a second reminder was set an
   hour after the first, which stayed. The move of what the last turn set is decided from the dialogue state.
2. D-p24-t4 «Yes, do it for me.» after Netflix asked to sign in: the decider said «limit», and «I do not handle tasks
   outside my scope.» was published. A yes or a go-ahead is never a limit.
3. D-p12-t2 «Bring up 24/7 stores near me» → «There are 24/7 delivery services and verified store maps available…»: a
   finder, a locator or a map «available» is the page describing itself.
4. D-p26-t2 «…and Fandango are the places mentioned for movies in Santa Rosa.»: «the places mentioned» tells the
   pages, and Fandango is the site a result belongs to, not a cinema.
5. D-p31-t1 «No encontré una lista…»: both partial drafts opened with «Los resultados mencionan que…» / «Los datos
   proporcionados confirman que…»; the frame is taken off the draft's own words and judged again.
6. D-s017, D-w10-t1 (recipes): the provider reads the recipe a results page publishes as schema.org data
   (SearchPageRecipe, C# tests); here, such a reading is a reference the recipe prompt writes from.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import decider, dialogue
from baxy_mind.semantic.dialogue import DialogueState

EVIDENCE = json.loads(
    (Path(__file__).resolve().parent / "data" / "c03_m102_evidence.json").read_text(encoding="utf-8")
)
CHILE = timezone(timedelta(hours=-3))


def _schema(properties: dict[str, object], required: list[str]) -> dict[str, object]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


SCHEDULE = _schema(
    {
        "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    ["dueUtc", "kind", "title"],
)
CANCEL_LATEST = _schema({"kind": {"type": "string", "enum": ["alarm", "reminder"]}}, ["kind"])


# ------------------------------------------------------------------ 1. the notification just set, moved


def _set(kind: str, title: str, due: datetime, request: str) -> DialogueState:
    """The dialogue state right after the turn that set the notification (compose-audit of t323)."""

    state = DialogueState()
    state.expect(request, ["notification.schedule"])
    state.record({
        "kind": "operation", "operation": "notification.schedule", "polarity": "success", "verified": True,
        "succeeded": True,
        "observed": {"version": 1, "kind": kind, "title": title,
                     "dueUtc": due.astimezone(timezone.utc).isoformat(), "taskName": "BAXY-Reminder-m102"},
    })
    return state


W18_SAID = "y remind me en 45 minutes to take a break"
W18_REPLY = "Recuerda tomar un descanso a las 03:12."
MOVE = "wait no, make it una hora"


def test_a_new_duration_moves_the_reminder_just_set_without_the_decider() -> None:
    due = datetime.now(CHILE).replace(microsecond=0) + timedelta(minutes=45)
    state = _set("reminder", "tomar un descanso", due, W18_SAID)
    request = state.moved_notification_request(MOVE, zone=CHILE)
    assert request is not None and "«tomar un descanso»" in request and f"{due:%H:%M}" in request
    assert request.endswith("una hora")

    class NoDecider:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"the decider was asked ({name})")

    history = [
        {"role": "assistant", "content": "Hola, soy BAXY. ¿En qué puedo ayudarte hoy?"},
        {"role": "user", "content": W18_SAID},
        {"role": "assistant", "content": W18_REPLY},
        {"role": "user", "content": MOVE},
    ]
    result = sidecar._prepare_turn_result(
        {"id": "m102", "text": MOVE, "history": history},
        llm=NoDecider(), planner_catalog=PlannerCatalog([_tool("notification.schedule")]), encoder=lambda _texts: (),
        tool_by_name={},
        dialogue_state=state,
    )
    assert result["kind"] == "plan" and result["operation"] is None
    assert result["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]
    assert result["objective"].startswith(("cancela el recordatorio «tomar un descanso»",
                                           "cancel the reminder «tomar un descanso»"))

    # The plan (after the shell's expect) cancels the latest reminder and sets it again an hour from now.
    state.expect(result["objective"], result["effectOperations"])
    moved = state.retimed_notification(MOVE)
    assert moved is not None
    assert sidecar._retimed_step_arguments("notification.cancel.latest", moved, CANCEL_LATEST) == {"kind": "reminder"}
    before = datetime.now(timezone.utc)
    scheduled = sidecar._retimed_step_arguments("notification.schedule", moved, SCHEDULE)
    assert scheduled is not None and (scheduled["kind"], scheduled["title"]) == ("reminder", "tomar un descanso")
    due_utc = datetime.fromisoformat(scheduled["dueUtc"].replace("Z", "+00:00"))
    assert timedelta(minutes=59) < due_utc - before < timedelta(minutes=61)


def test_a_new_clock_moves_the_alarm_just_set() -> None:
    now = datetime.now(CHILE).replace(second=0, microsecond=0)
    tomorrow = (now + timedelta(days=1)).replace(hour=6, minute=45)
    state = _set("alarm", "despertar", tomorrow, "pon una alarma mañana a las 6:45 para despertar")
    request = state.moved_notification_request("Actually, make it 6:30.", now=now, zone=CHILE)
    assert request == "cancel the alarm «despertar» set for 06:45 and set it again at 06:30"


def test_only_a_move_of_what_the_last_turn_set_is_decided_here() -> None:
    due = datetime.now(CHILE) + timedelta(minutes=45)
    state = _set("reminder", "tomar un descanso", due, W18_SAID)
    # Another request, not a move of the time.
    assert state.moved_notification_request("y otro para regar las plantas", zone=CHILE) is None
    # A turn in between that set nothing: no move.
    state.expect("¿qué hora es?", ["system.time"])
    assert state.moved_notification_request(MOVE, zone=CHILE) is None
    # Nothing set at all.
    assert DialogueState().moved_notification_request(MOVE, zone=CHILE) is None


def test_a_bare_number_after_a_timer_is_left_to_the_decider() -> None:
    # Tanda 7 «actually make it 9» after a timer of 5 minutes: the minutes as much as the clock.
    state = _set("alarm", "temporizador", datetime.now(CHILE) + timedelta(minutes=5), "pon un temporizador de 5 minutos")
    assert state.moved_notification_request("actually make it 9", zone=CHILE) is None
    assert state.moved_notification_request("no, mejor 10", zone=CHILE) is None
    assert state.moved_notification_request("actually make it 9 minutes", zone=CHILE) is not None
    assert state.moved_notification_request("mejor a las 9", zone=CHILE) is not None


# ------------------------------------------------------------------ 2. a go-ahead is never a limit


class _Decider:
    """The contextual decider of v3z: the recorded restatement and decision (turn-audit request 1119)."""

    def __init__(self, request: str, decision: str) -> None:  # noqa: D107
        self.decided = decider.ContextDecision(request=request, decision=decision, operations=(), question="")
        self.chats = 0

    def decide_in_context(self, *_args: object, **_kwargs: object) -> decider.ContextDecision:
        return self.decided

    def chat(self, *_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        self.chats += 1
        return "Netflix still needs you to sign in on this PC before I can play Hustlers.", []

    @staticmethod
    def detect_response_language(_text: str) -> str:
        return "en"


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


P24 = [
    ("user", "Search for something else and I change my mind. Now I want to watch Drama movies like Lizzo."),
    ("assistant", "The drama movie like Lizzo is Hustlers."),
    ("user", "Yes, Hustlers is okay for me."),
    ("assistant", "The streaming of Hustlers failed because Netflix requires a sign-in on this PC before playback "
                  "can begin."),
]


@pytest.mark.parametrize("text", ["Yes, do it for me.", "That is confirmed to proceed.", "sí, dale"])
def test_a_yes_after_a_failure_is_no_limit(text: str) -> None:
    model = _Decider("Sign in to Netflix and play Hustlers.", "limit")
    turns = [{"role": role, "content": content} for role, content in P24]
    result = sidecar._context_decided_result(
        {"id": "m102", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog([_tool("streaming.play.named"), _tool("web.search")]),
    )
    assert result["kind"] == "conversation" and result["conversationKind"] == "knowledge"
    assert model.chats == 1


def test_a_request_after_a_failure_keeps_its_limit() -> None:
    assert dialogue.gives_go_ahead("Yes, do it for me.")
    assert not dialogue.gives_go_ahead("log into my Netflix account for me")
    model = _Decider("Log into my Netflix account.", "limit")
    turns = [{"role": role, "content": content} for role, content in P24]
    text = "log into my Netflix account for me"
    result = sidecar._context_decided_result(
        {"id": "m102", "text": text, "history": [*turns, {"role": "user", "content": text}]},
        llm=model,
        planner_catalog=PlannerCatalog([_tool("streaming.play.named"), _tool("web.search")]),
    )
    assert result["kind"] == "conversation" and result["conversationKind"] == "unsupported"


# ------------------------------------------------------------------ 3–4. search reports that tell the pages


def _row(rid: str) -> tuple[str, dict, str]:
    row = EVIDENCE[rid]
    return row["draft"], row["payload"], row["text"]


def test_a_finder_or_a_map_available_is_the_page_describing_itself() -> None:
    draft, payload, said = _row("D-p12-t2")
    assert draft == "There are 24/7 delivery services and verified store maps available near Curico."
    assert llm._payload_fact_defect(draft, payload, said) == "search_report_page_voice"
    # v3o and v3u published the same pages told as a finder.
    for told in (
        "I found a 24/7 store finder for liquor, vape, and cannabis shops in Curico. There is also a 24-hour "
        "on-demand delivery service available there.",
        "I found on-demand delivery services and a verified store finder for liquor, vape shops, and cannabis "
        "dispensaries near Curico.",
    ):
        assert llm._payload_fact_defect(told, payload, said) == "search_report_page_voice"
    # The honest report stands.
    assert llm._payload_fact_defect("I couldn't find 24/7 stores near Curico.", payload, said) == ""


def test_the_places_mentioned_and_the_site_read_are_the_search_shown() -> None:
    draft, payload, said = _row("D-p26-t2")
    assert llm._search_result_site_brands(payload) == {"fandango"}
    assert llm._payload_fact_defect(draft, payload, said) == "search_report_shows_the_search"
    # Each defect on its own.
    assert llm._payload_fact_defect(
        "Santa Rosa Cinemas, Roxy Stadium 14 and Airport Stadium 12 are the places mentioned.", payload, said,
    ) == "search_report_shows_the_search"
    assert llm._payload_fact_defect(
        "Santa Rosa Cinemas, Roxy Stadium 14 and Fandango show movies in Santa Rosa.", payload, said,
    ) == "search_report_shows_the_search"
    # The cinemas read, said as such, are the answer.
    assert llm._payload_fact_defect(
        "Santa Rosa Cinemas, Roxy Stadium 14 and Airport Stadium 12 show movies in Santa Rosa.", payload, said,
    ) == ""
    # FINAL v1 F-p08-t2 (reviewed right): sites offered as sites, where to look.
    draft, payload, said = _row("F-p08-t2")
    assert llm._payload_fact_defect(draft, payload, said) == ""


def test_a_name_the_pages_are_about_is_no_site() -> None:
    payload = {"operation": "web.search", "seen": {"query": "best electric car", "results": [
        {"title": "Tesla Model Y | Tesla", "url": "https://www.tesla.com/modely", "snippet": "Model Y is an SUV."},
        {"title": "Electric cars 2026 - El País", "url": "https://elpais.com/motor/", "snippet": "Los mejores."},
    ], "authority": "duckduckgo_lite_https"}}
    assert llm._search_result_site_brands(payload) == {"el pais"}


# ------------------------------------------------------------------ 5. the partial report without its frame


def test_the_partial_report_is_said_without_the_results_as_its_speaker() -> None:
    _, payload, said = _row("D-p31-t1")
    facts = {"situation": {"kind": "operation", "operation": "web.search", "polarity": "success", "verified": True,
                           "succeeded": True, "observed": payload["seen"]}}
    drafts = {
        # partial_after_not_found (search_report_shows_the_search)
        "Los resultados mencionan que Javier Milei será el 13° presidente de la democracia argentina desde 1983, pero "
        "no listan los nombres de los últimos 10 presidentes ni fechas específicas para cada uno. Tampoco se encuentran "
        "cifras ni detalles sobre cómo la convertibilidad afectó los sueldos y el ascenso social en los textos "
        "proporcionados.":
        "Javier Milei será el 13° presidente de la democracia argentina desde 1983. No encontré los nombres de los "
        "últimos 10 presidentes ni fechas específicas para cada uno, ni cifras ni detalles sobre cómo la "
        "convertibilidad afectó los sueldos y el ascenso social.",
        # partial_after_not_found_retry (copied_instruction)
        "Los datos proporcionados confirman que Javier Milei será el 13° presidente de Argentina desde la democracia "
        "en 1983, pero no listan los nombres de los últimos 10 presidentes ni mencionan cifras sobre el desarrollo "
        "económico, el impacto de la convertibilidad en los sueldos ni el ascenso social.":
        "Javier Milei será el 13° presidente de Argentina desde la democracia en 1983. No encontré los nombres de los "
        "últimos 10 presidentes ni cifras sobre el desarrollo económico, el impacto de la convertibilidad en los "
        "sueldos ni el ascenso social.",
    }
    for draft, expected in drafts.items():
        assert llm.compose_visible_defect(draft, "status", said, facts) or llm._payload_fact_defect(draft, payload, said)
        unframed = llm._unframed_partial(draft, english=False)
        assert unframed == expected
        assert llm.compose_visible_defect(unframed, "status", said, facts) == ""
        assert llm._payload_fact_defect(unframed, payload, said) == ""
    assert llm._unframed_partial(
        "The results mention that Javier Milei is the 13th president since 1983, but they do not list the others.",
        english=True,
    ) == "Javier Milei is the 13th president since 1983. I couldn't find the others."
    # A narration with no statement of its own is left as it is (and stays vetoed).
    assert llm._unframed_partial("Los resultados no mencionan nada de eso.", english=False) == (
        "Los resultados no mencionan nada de eso."
    )


# ------------------------------------------------------------------ 6. a recipe read from a results page


def test_a_recipe_a_page_publishes_is_a_reference() -> None:
    evidence = ("Ingredientes (para 4 personas):\n- 2 tazas de harina de maíz precocida\n- 2 1/2 tazas de agua tibia\n"
                "Preparación:\n1. Mezcla el agua con la sal y agrega la harina poco a poco.")
    situation = {"kind": "operation", "operation": "web.search", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": {
                     "query": "receta arepas de queso", "count": 1, "reference": "recipe", "servings": 4,
                     "authority": "recipe_page_jsonld",
                     "results": [{"title": "Arepas de queso", "url": "https://cocina.example.com/arepas",
                                  "snippet": evidence}]}}
    reference = llm._reference_of(situation)
    assert reference is not None and reference["kind"] == "recipe" and reference["servings"] == 4
    assert "2 1/2 tazas de agua tibia" in reference["text"]
    assert not llm._read_no_recipe(situation)


@pytest.mark.parametrize("rid", ["D-s017", "D-w10-t1"])
def test_what_was_read_about_a_dish_is_not_its_recipe(rid: str) -> None:
    draft, payload, said = _row(rid)
    assert llm._payload_fact_defect(draft, payload, said) == "search_report_recipe_not_read"
    # Saying the recipe was not found is the report.
    not_found = "I couldn't find a recipe for southern-style mac and cheese." if rid == "D-s017" else (
        "No encontré una receta de arepas de queso."
    )
    assert llm._payload_fact_defect(not_found, payload, said) == ""
    # What is asked about the dish, not its recipe, is answered from the same reading.
    assert not llm._search_report_recipe_not_read(draft, payload, "¿de dónde son las arepas?")
