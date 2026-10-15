"""M143 (D58, 2026-10-03): first-turn readers, second round, on DEV-H (window v4o-devH), with a SAFETY case first.

DEV-H (iterable) first messages where a reader decided against the isolated decider full3, or lost an argument the
decider gave:

0. SAFETY H-w12-t1 «escríbeme en python una función que me diga si un año es bisiesto…» → message.recipient.resolve +
   message.send to «python una función». With no client named, a message needs someone it goes to: the person's own
   clitic on the writing verb («escríbeme», «mándame», «write me») makes the writing content for the person, and a
   bare «en» says where it is written, never who it goes to (``semantic.messaging.message_request_any_channel``).
1. Readers that overrode the decider: «mi equipo» who plays is no agenda event (H-s003); «en el Spotify» (H-s037); the
   folder pulled up is opened, not searched (H-s070); a search that orders the video played (H-s075); a folder opened
   beside the latest file (H-s081); a capture of «esta ventana» (H-s084); an order with its reason after it, and
   «for a second» (H-s089); a place known only through someone, after talk (H-s092); «recuérdame qué me falta» asks
   to be told now (H-s016); «una hora antes de las 9» is the alarm's time (H-s047).
2. Arguments lost: «lo último que bajé» is in Downloads (H-w32-t1); a field with one possible member that the decider
   gave (H-w21-t1); a tag question after a list's entries is no entry (H-s116); H-s009 is M141's (checked here).

Every variant phrasing is our own; the DEV-H texts are the rows themselves. The clock is fixed where time matters.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import arguments, temporal
from baxy_mind.semantic.decider import ContextDecision
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.media import _youtube_search_query
from baxy_mind.semantic.messaging import message_draft_request, message_request_any_channel
from baxy_mind.semantic.notes import agenda_read_request, list_entries
from baxy_mind.semantic.patterns import resolve_explicit_clarification_intent, resolve_explicit_effects
from baxy_mind import turn_decide
from baxy_mind import argument_grounding
from baxy_mind import decided_arguments

OPERATIONS = tuple(
    json.loads(
        (pathlib.Path(sidecar.__file__).parent / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
    )["operations"]
)
# Saturday 3 October 2026, 12:30 in Chile (UTC-3).
LOCAL = timezone(timedelta(hours=-3))
NOW = datetime(2026, 10, 3, 12, 30, tzinfo=LOCAL)


class _Decider:
    """The model of a whole turn: the decider answers what it is given; every other call is neutral."""

    _native_tool_policy_enabled = False

    def __init__(self, decision: ContextDecision | None = None) -> None:
        self.decision = decision
        self.decisions = 0

    def decide_in_context(self, *_a, **_k):
        self.decisions += 1
        if self.decision is None:
            raise AssertionError("the decider was not to be asked")
        return self.decision

    def formulate_explicit_clarification_question(self, *_a, **_k):
        return "¿Dónde?"

    def clarify_after_turn_failure(self, *_a, **_k):
        return "¿Qué necesitas?"

    def public_lookup_requested(self, _text):
        return False

    def operation_is_the_requested_effect(self, *_a, **_k):
        return True

    def _verify_semantic_effect_shape(self, _text):
        return "no_effect", "zero"

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


def _tool(name: str) -> dict:
    schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    return {"type": "function", "function": {"name": name.replace(".", "_"), "canonical_name": name,
                                             "description": name, "risk": "read_only", "parameters": schema}}


def _turn(text: str, model: _Decider) -> dict:
    tools = {name: _tool(name) for name in OPERATIONS}
    return turn_decide._prepare_turn_result(
        {"id": "m143", "text": text, "history": [{"role": "user", "content": text}]},
        llm=model, planner_catalog=PlannerCatalog(list(tools.values())), encoder=lambda _t: (), tool_by_name=tools,
        dialogue_state=DialogueState(),
    )


def _decided_turn(text: str, decision: str, operations: tuple[str, ...] = (), question: str = "") -> tuple[dict, int]:
    model = _Decider(ContextDecision(request=text, decision=decision, operations=operations, question=question))
    result = _turn(text, model)
    return result, model.decisions


def _read(text: str) -> tuple[str, ...] | None:
    found = resolve_explicit_effects(text, OPERATIONS)
    return None if found is None else tuple(found.operations)


def _asked(text: str) -> tuple[str, ...] | None:
    found = resolve_explicit_clarification_intent(text, OPERATIONS)
    return None if found is None else tuple(found.missing_fields)


# ------------------------------------------------------------------ 0. SAFETY: no message without someone it goes to

H_W12_T1 = "escríbeme en python una función que me diga si un año es bisiesto, es para una práctica de la uni"


@pytest.mark.parametrize(
    "text",
    [
        H_W12_T1,
        # our own: the person's clitic, a place of writing, English
        "escribe en python una función que diga hola",
        "escríbeme para mi amiga un poema que diga te amo",
        "mándame a mi correo un resumen que diga lo de hoy",
        "mándame un mensaje a Lucas que diga hola",
        "escribe en la pizarra que mañana no hay clase",
        "write me a python function that says if a year is a leap year",
        "send me a text that says hi",
        # a client named too: still the words for the person
        "escríbeme un poema en whatsapp para mi amiga que diga te amo",
        "mándame por whatsapp a Lucas que llego tarde",
    ],
)
def test_writing_for_the_person_is_never_a_message_to_someone(text: str) -> None:
    assert message_request_any_channel(text) is None
    assert message_draft_request(text) is None
    assert "message.send" not in (_read(text) or ())


def test_h_w12_t1_the_function_is_written_in_the_reply() -> None:
    result, decisions = _decided_turn(H_W12_T1, "talk")
    assert result["kind"] == "conversation"
    assert "message.send" not in (result.get("effectOperations") or [])
    assert decisions <= 1


@pytest.mark.parametrize(
    ("text", "recipient"),
    [
        ("escribile a Lucas que llego tarde", "Lucas"),
        ("mandale al grupo Musica: prueba 1", "Musica"),
        ("enviale un mensaje en el grupo Musica que diga hola", "Musica"),
        ("text Lucas that I am late", "Lucas"),
    ],
)
def test_a_message_to_someone_named_is_still_sent(text: str, recipient: str) -> None:
    found = message_request_any_channel(text)
    assert found is not None and found[0] == recipient
    assert _read(text) == ("message.recipient.resolve", "message.send")


# ------------------------------------------------------------------ 1. readers that overrode the decider


@pytest.mark.parametrize(
    "text",
    [
        "oiga parce, ¿a qué hora es que juega mi equipo hoy?",  # H-s003
        "what time does my team play tonight?",
        "¿a qué hora juegan mis Lakers mañana?",
    ],
)
def test_h_s003_whoever_plays_is_no_agenda_event(text: str) -> None:
    assert not agenda_read_request(text)
    assert _read(text) != ("calendar.event.list",)


@pytest.mark.parametrize(
    "text", ["¿a qué hora es mi partido de fútbol?", "what time is my play tonight?", "cuándo es mi brunch con Jennifer"],
)
def test_the_person_s_own_event_is_still_the_agenda(text: str) -> None:
    assert agenda_read_request(text)


def test_h_s003_the_decider_decides_the_match() -> None:
    result, decisions = _decided_turn("oiga parce, ¿a qué hora es que juega mi equipo hoy?", "clarify",
                                      question="¿Cuál es tu equipo?")
    assert decisions == 1 and result["kind"] == "clarify"


@pytest.mark.parametrize(
    "text",
    [
        "a ver, ponme algo de Rosalía en el Spotify, lo que sea, da igual",  # H-s037
        "pon algo de Rosalía en el spotify",
        "play some Bad Bunny on my Spotify",
    ],
)
def test_h_s037_spotify_with_its_article_is_where_to_play(text: str) -> None:
    assert _read(text) == ("media.play.query",)


def test_music_with_no_provider_named_is_still_youtube() -> None:
    assert _read("ponme algo de Rosalía") == ("media.play.youtube",)


def test_h_s037_the_query_is_the_artist() -> None:
    found = argument_grounding._ground_explicit_arguments(
        "media.play.query", "a ver, ponme algo de Rosalía en el Spotify, lo que sea, da igual", PLAY_QUERY,
    )
    assert found == {"provider": "spotify", "query": "Rosalía"}


@pytest.mark.parametrize(
    "text",
    [
        "can you pull up my downloads folder, I'm trying to find that installer I grabbed earlier",  # H-s070
        "muéstrame la carpeta de descargas",
        "bring up my documents folder please",
    ],
)
def test_h_s070_the_folder_pulled_up_is_the_decider_s_to_open(text: str) -> None:
    assert _read(text) != ("filesystem.known.search",)
    result, decisions = _decided_turn(text, "action", ("filesystem.folder.open",))
    assert decisions == 1 and result["effectOperations"] == ["filesystem.folder.open"]


def test_a_thing_searched_in_a_folder_is_still_a_search() -> None:
    assert _read("track down the installer in my downloads folder") == ("filesystem.known.search",)


@pytest.mark.parametrize(
    "text",
    [
        "can you find that video of the guy building a treehouse in bali and put it on youtube",  # H-s075
        "busca el video del gato que toca piano y ponlo en youtube",
    ],
)
def test_h_s075_a_search_that_orders_it_played_is_no_results_page(text: str) -> None:
    assert _youtube_search_query(text) is None
    assert _read(text) != ("browser.navigate",)


def test_a_youtube_search_is_still_the_results_page() -> None:
    assert _youtube_search_query("buscá videos de gatos en youtube") == "videos de gatos"
    assert _read("find cat videos on youtube") == ("browser.navigate",)


@pytest.mark.parametrize(
    "text",
    [
        "abreme descargas y el ultimo archivo que baje",  # H-s081
        "open my downloads folder and the latest file in it",
        "abre la carpeta de documentos y el último archivo",
    ],
)
def test_h_s081_a_folder_opened_beside_the_latest_file(text: str) -> None:
    assert _read(text) != ("filesystem.file.open.latest",)
    result, decisions = _decided_turn(text, "action", ("filesystem.folder.open", "filesystem.file.open.latest"))
    assert decisions == 1
    assert sorted(result["effectOperations"]) == ["filesystem.file.open.latest", "filesystem.folder.open"]


def test_the_latest_file_of_a_folder_is_still_read() -> None:
    assert _read("abre el último archivo de descargas") == ("filesystem.file.open.latest",)
    assert _read("abreme el ultimo archivo que baje en descargas") == ("filesystem.file.open.latest",)


@pytest.mark.parametrize(
    "text",
    [
        "sácale un pantallazo a esta ventana nomás",  # H-s084
        "take a screenshot of this window",
        "toma una captura de esta ventana",
        "toma una captura de la ventana activa",
    ],
)
def test_h_s084_a_capture_of_the_window_pointed_at(text: str) -> None:
    assert _read(text) == ("capture.active.window",)


@pytest.mark.parametrize("text", ["sácame un pantallazo", "hazme una captura de pantalla", "take a screenshot of the screen"])
def test_a_capture_is_still_the_whole_screen(text: str) -> None:
    assert _read(text) == ("capture.screenshot",)


@pytest.mark.parametrize(
    "text",
    [
        "minimise everything for a second, i need to find a file on the desktop",  # H-s089
        "minimiza todo un momento, tengo que buscar un archivo en el escritorio",
        "minimize everything for a sec",
    ],
)
def test_h_s089_the_order_with_its_reason_after_it(text: str) -> None:
    result, decisions = _decided_turn(text, "action", ("window.minimize.all",))
    assert result["effectOperations"] == ["window.minimize.all"]
    assert decisions == 0


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        ("Me encanta cómo lo definís, oye, hablando de amor, pon una canción de amor en YouTube", "media.play.youtube"),
        ("mira, pon algo de Soda Stereo", "media.play.youtube"),
    ],
)
def test_talk_before_an_order_still_leaves_the_order(text: str, operation: str) -> None:
    result, decisions = _decided_turn(text, "talk")
    assert decisions == 0 and result["effectOperations"] == [operation]


def test_h_s092_someone_s_place_after_talk_is_never_this_town() -> None:
    text = "so like, is it gonna rain where my grandma lives this weekend?"
    assert _read(text) != ("weather.current",)
    result, decisions = _decided_turn(text, "clarify", question="Which city does your grandma live in?")
    assert decisions == 1 and result["kind"] == "clarify"
    assert _asked("bueno, ¿va a llover donde vive mi abuela el finde?") == ("location",)


def test_the_weather_of_a_named_town_after_talk_is_still_read() -> None:
    result, decisions = _decided_turn("so like, is it gonna rain in Boston this weekend?", "talk")
    assert decisions == 0 and result["effectOperations"] == ["weather.current"]


@pytest.mark.parametrize(
    "text",
    [
        "oye, recuérdame qué me falta por hacer hoy de mi lista de pendientes",  # H-s016
        "recuérdame lo que tengo pendiente hoy",
        "recuérdame qué nos queda por hacer esta semana",
        "remind me what I have left to do today",
    ],
)
def test_h_s016_what_is_left_is_told_now(text: str) -> None:
    assert _asked(text) is None
    assert _read(text) not in {("reminder.create",), ("notification.schedule",)}
    result, decisions = _decided_turn(text, "action", ("task.list",))
    assert decisions == 1 and result["effectOperations"] == ["task.list"]


def test_a_reminder_of_what_to_do_is_still_a_reminder() -> None:
    assert _asked("recuérdame que compre leche") == ("due_time",)
    assert _read("recuérdame que me tome la pastilla hoy a las 9") == ("reminder.create",)


H_S047 = "¿me podrías poner una alarma una hora antes de las 9?"


def _local(due: str) -> datetime:
    return datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(LOCAL)


@pytest.mark.parametrize(
    ("text", "hour", "minute"),
    [
        (H_S047, 20, 0),  # 9 is next at 21:00 (D61)
        ("set an alarm an hour before 9", 20, 0),
        ("pon una alarma media hora antes de las 7 de la mañana", 6, 30),
    ],
)
def test_h_s047_an_alarm_before_a_clock_rings_that_long_before_it(text: str, hour: int, minute: int) -> None:
    assert _asked(text) is None
    # The Spanish orders are read; the English one is the decider's, and its arguments are read alike.
    assert _read(text) in {("notification.schedule",), None}
    raw = arguments._explicit_arguments_from_evidence("notification.schedule", text)
    assert raw is not None
    read = argument_grounding._normalize_grounded_operation_arguments("notification.schedule", dict(raw), text, now_utc=NOW)
    assert read is not None and read["kind"] == "alarm"
    due = _local(read["dueUtc"])
    assert (due.hour, due.minute) == (hour, minute)


def test_h_s047_the_advance_counts_from_the_clock_it_names() -> None:
    advance = temporal.said_advance(H_S047)
    assert advance is not None and advance.minutes == 60 and advance.clock.hour == 9
    assert advance.phrase == "una hora antes de las 9"


def test_an_advance_of_no_moment_said_still_reads_nothing() -> None:
    assert arguments._explicit_arguments_from_evidence(
        "notification.schedule", "ponme una alarma media hora antes de eso",
    ) is None
    assert _asked("pon una alarma") == ("alarm_time",)


# ------------------------------------------------------------------ 2. arguments the decider gave

OPEN_LATEST = {"type": "object", "properties": {"folder": {"type": "string",
                                                           "enum": ["desktop", "documents", "downloads", "pictures"]}},
               "required": ["folder"], "additionalProperties": False}
PLAY_QUERY = {"type": "object", "properties": {"provider": {"type": "string", "enum": ["spotify"]},
                                               "query": {"type": "string"}},
              "required": ["provider", "query"], "additionalProperties": False}
SNAP = {"type": "object", "properties": {"side": {"type": "string", "enum": ["left", "right"]},
                                         "windowId": {"type": "string"}},
        "required": ["side", "windowId"], "additionalProperties": False}


def _alone(text: str, operations: tuple[str, ...], decided: dict, operation: str, schema: dict) -> dict | None:
    decided_arguments._remember_decided_arguments(text, operations, tuple(decided.items()))
    tool = {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "parameters": schema}}
    said = decided_arguments._with_decided_restatements(operation, text, schema, text)
    return decided_arguments._decided_arguments_alone(operation, text, tool, said)


@pytest.mark.parametrize(
    "text", ["che, abrime lo último que bajé", "abre lo que bajé ayer", "ábreme el último archivo que bajé"],
)
def test_h_w32_t1_what_was_downloaded_is_in_downloads(text: str) -> None:
    got = _alone(text, ("filesystem.file.open.latest",), {"folder": "Descargas"}, "filesystem.file.open.latest",
                 OPEN_LATEST)
    assert got == {"folder": "downloads"}


def test_a_folder_nobody_said_is_still_not_taken() -> None:
    assert _alone("abre lo último", ("filesystem.file.open.latest",), {"folder": "Descargas"},
                  "filesystem.file.open.latest", OPEN_LATEST) is None


@pytest.mark.parametrize(
    ("text", "decided"),
    [
        ("che baxy, tirá algún tema de charly garcia de los ochenta, el que sea",  # H-w21-t1
         {"provider": "Spotify", "query": "Charly García 80s"}),
        ("ponme algo de Soda Stereo", {"provider": "Spotify", "query": "Soda Stereo"}),
        ("play something by Daft Punk", {"provider": "spotify", "query": "Daft Punk"}),
    ],
)
def test_h_w21_t1_the_only_provider_the_decider_gave_is_not_asked(text: str, decided: dict) -> None:
    got = _alone(text, ("media.play.query",), decided, "media.play.query", PLAY_QUERY)
    assert got is not None and got["provider"] == "spotify" and got["query"] == decided["query"]


def test_a_member_of_several_is_still_said_or_asked() -> None:
    # «left» was never said: a field with two members is the person's choice.
    decided_arguments._remember_decided_arguments("pon chrome a un lado", ("window.snap",), (("side", "left"),))
    assert decided_arguments._with_decided_restatements("window.snap", "pon chrome a un lado", SNAP, "pon chrome a un lado") == (
        "pon chrome a un lado"
    )
    # The decider gave no provider: none is invented.
    assert _alone("ponme algo de Soda Stereo", ("media.play.query",), {"query": "Soda Stereo"}, "media.play.query",
                  PLAY_QUERY) is None


@pytest.mark.parametrize(
    ("text", "entries"),
    [
        ("Ey, anótame en la lista del mercado plátano maduro, arepas de chócolo y queso costeño, ¿sí?",  # H-s116
         ("plátano maduro", "arepas de chócolo", "queso costeño")),
        ("apúntame en la lista de la compra leche, pan y huevos, ¿vale?", ("leche", "pan", "huevos")),
        ("add to my shopping list eggs, bread and milk, ok?", ("eggs", "bread", "milk")),
        ("añade pan, leche y huevos a la lista de la compra", ("pan", "leche", "huevos")),
    ],
)
def test_h_s116_a_tag_after_the_entries_is_no_entry(text: str, entries: tuple[str, ...]) -> None:
    body = text.removeprefix("Ey, ")
    found = list_entries(body)
    assert found is not None and found[0] == entries


def test_h_s116_one_task_per_entry() -> None:
    text = "Ey, anótame en la lista del mercado plátano maduro, arepas de chócolo y queso costeño, ¿sí?"
    result, decisions = _decided_turn(text, "action", ("task.create",))
    assert decisions == 0 and result["effectOperations"] == ["task.create"] * 3


def test_h_s009_the_plan_takes_the_decider_s_application() -> None:
    # M141 already: «minimiza todo y abreme la calculadora» → app.open {"appId": "Calculadora"}.
    objective = "Minimiza todas las ventanas y abre la Calculadora."
    decided_arguments._remember_decided_arguments(objective, ("window.minimize.all", "app.open"), (("app", "Calculadora"),))
    tool = {"type": "function", "function": {"name": "app_open", "canonical_name": "app.open", "description": "app.open",
                                             "parameters": {"type": "object", "properties": {"appId": {"type": "string"}},
                                                            "required": ["appId"], "additionalProperties": False}}}
    got = decided_arguments._plan_step_decided_arguments(
        "app.open", ("window.minimize.all", "app.open"), objective, tool,
        [{"role": "user", "content": "minimiza todo y abreme la calculadora"}],
    )
    assert got == {"appId": "Calculadora"}
