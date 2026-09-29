"""M76 (2026-09-29, independent review of the official-window DEV-D run v3l): zero questions for a datum already given.

Evidence: %LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3l-devD/ (REVIEW.reviewed.jsonl, turn-audit.jsonl,
compose-audit.jsonl, run.map.json, shell-trace.jsonl). Each test below replays the recorded text, restatement or
verified observation of one flagged row; the causes:

1. An operation with every field optional asked it (D-s014, D-s054, D-s080 «¿En qué ciudad…?»): the extraction
   abstained and the shell asked the optional place. With nothing required nothing is missing; the weather reads this
   PC's place, and «aquí» names that place too.
2. A place visited in English was not read (D-p25-t1 «I'm visiting Martinez soon … the weather there» → Curicó).
3. Write guards asked as jargon (D-w17-t2 «Which task ID and expected version…?», D-p06-t3, D-p08-t3, D-s019): a
   version or revision is read from the item, never asked.
4. A time taken back was kept by the restatement (D-s097 «en 2 , no espera en 3 minutos» → 2 minutes).
5. A duration counted from another moment was read from now (D-w02-t3 «media hora antes de eso» → +30 min).
6. A list named without «de» was not read (D-p08-t2 «Pon huevos en mi lista Navidad» → «¿Qué título…?»).
7. The notification just set, moved by its new time alone (D-w16-t2 «Actually, make it 6:30.», D-w04-t4 «Mejor a las 6
   en punto…», D-w18-t5 «wait no, make it una hora»), asked «¿A qué hora y qué tipo…?».
8. A film named without its service was asked the title too (D-p19-t1).
9. A rest of a stated length was not timed (D-s120 «Cojamos un descanso de 14 minutos…»).
10. A task marked done asked its internal identity (D-w17-t2 «mark the first one done» after the listing): it crosses
    task.resolve.exact like task.delete, with the title the listing told.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import LlmRuntime, _required_compose_input, person_askable_fields
from baxy_mind.planner import required_predecessors
from baxy_mind.semantic.arguments import partial_explicit_arguments
from baxy_mind.semantic.decider import faithful_request
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.notes import list_entry_request, list_removal_request, task_completion_title
from baxy_mind.semantic.system import names_this_place
from baxy_mind.semantic.temporal import notification_retiming, taken_back_time, timed_break, timed_task

# ------------------------------------------------------------------ the catalog's schemas (ProductCatalog.cs)


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


WEATHER = _schema({"location": {"type": ["string", "null"], "x-maxUtf8Bytes": 128}}, [])
SCHEDULE = _schema(
    {
        "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    ["dueUtc", "kind", "title"],
)
CANCEL_AT = _schema(
    {
        "hour": {"type": "integer", "minimum": 0, "maximum": 23},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "minute": {"type": "integer", "minimum": 0, "maximum": 59},
        "period": {"type": "string", "enum": ["am", "pm"]},
    },
    ["hour", "kind"],
)
CANCEL_LATEST = _schema({"kind": {"type": "string", "enum": ["alarm", "reminder"]}}, ["kind"])
TASK_CREATE = _schema(
    {
        "details": {"type": "string", "x-maxUtf8Bytes": 65536},
        "due": {"type": ["string", "null"], "maxLength": 64},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    ["title"],
)
TASK_CAS = _schema(
    {
        "expectedVersion": {"type": "integer", "minimum": 1},
        "taskId": {"type": "string", "maxLength": 36, "x-nonWhitespace": True},
    },
    ["expectedVersion", "taskId"],
)
TASK_UPDATE = _schema(
    {
        "details": {"type": "string", "x-maxUtf8Bytes": 65536},
        "due": {"type": ["string", "null"], "maxLength": 64},
        "expectedVersion": {"type": "integer", "minimum": 1},
        "taskId": {"type": "string", "maxLength": 36, "x-nonWhitespace": True},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    ["details", "due", "expectedVersion", "taskId", "title"],
)
TASK_RESOLVE = _schema(
    {"includeDeleted": {"type": "boolean"}, "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True}},
    ["title"],
)
STREAMING = _schema(
    {
        "service": {"type": "string", "enum": ["disney_plus", "netflix"]},
        "title": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
    },
    ["service", "title"],
)


def _tool(name: str, schema: dict, description: str = "Operación del catálogo.") -> dict:
    return {
        "type": "function",
        "function": {
            "name": name.replace(".", "_"),
            "canonical_name": name,
            "description": description,
            "parameters": json.loads(json.dumps(schema)),
        },
    }


def _content(envelope: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(envelope, ensure_ascii=False)}}]}


CHILE = timezone(timedelta(hours=-3))  # America/Santiago on 2026-09-29, the PC of the run


# ------------------------------------------------------------------ 1. every field optional: nothing to ask


# The restatements the App sent to the arguments step (turn-audit requests 83, 320 and 472).
@pytest.mark.parametrize(
    "row, objective",
    [
        ("D-s014", "¿Qué previsión de tiempo hay para las cuatro?"),
        ("D-s054", "¿A qué hora comenzará a oscurecerse aquí?"),
        ("D-s080", "¿A qué hora ya no habrá la luz del sol por las calles hoy?"),
    ],
)
def test_an_abstention_on_an_all_optional_schema_reads_the_default_place(row: str, objective: str) -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post = MagicMock(return_value=_content({"grounded": False, "arguments": None}))
    runtime.formulate_missing_argument_question = MagicMock(side_effect=AssertionError(f"{row} asked again"))
    tool = _tool("weather.current", WEATHER, "Lee el clima del lugar nombrado o de la ubicación de este PC.")

    extraction = runtime.extract_direct_arguments(objective, tool)
    arguments, question = sidecar.prepare_direct_argument_result(runtime, objective, tool, extraction.arguments)

    assert extraction.arguments == {}
    assert (arguments, question) == ({}, "")


def test_a_place_nobody_said_is_left_out_and_a_place_said_is_kept() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime.formulate_missing_argument_question = MagicMock(side_effect=AssertionError("asked"))
    tool = _tool("weather.current", WEATHER)
    # D-s014: a town the model brought is this PC's own, never asked and never sent as said.
    assert sidecar.prepare_direct_argument_result(
        runtime, "¿Qué previsión de tiempo hay para las cuatro?", tool, {"location": "Curicó"},
    ) == ({}, "")
    assert sidecar.prepare_direct_argument_result(runtime, "Clima en Oviedo", tool, {"location": "Oviedo"}) == (
        {"location": "Oviedo"}, "",
    )


def test_here_names_this_pcs_place() -> None:
    # D-s054's restatement «…oscurecerse aquí?»: «aquí» is read with no place, as this PC's.
    assert names_this_place("aquí") and names_this_place("around here") and names_this_place("mi ciudad")
    assert not names_this_place("Aquino") and not names_this_place("Hereford")
    assert sidecar._normalize_grounded_operation_arguments(
        "weather.current", {"location": "aquí"}, "¿A qué hora comenzará a oscurecerse aquí?",
    ) == {}


# ------------------------------------------------------------------ 2. a place visited


def test_the_weather_there_is_the_place_visited() -> None:
    assert sidecar._ground_explicit_arguments(
        "weather.current", "I'm visiting Martinez soon and would like the check the weather there please", WEATHER,
    ) == {"location": "Martinez"}
    # Without «there», or with nobody's place named, nothing is taken for it.
    assert sidecar._ground_explicit_arguments(
        "weather.current", "I'm visiting my mom soon, what's the weather there?", WEATHER,
    ) == {"location": None}


# ------------------------------------------------------------------ 3. a write guard is never asked


def test_the_question_asks_which_task_never_its_version() -> None:
    runtime = object.__new__(LlmRuntime)
    seen: list[dict] = []

    def fake_post_schema(payload: dict, _label: str) -> dict:
        seen.append(payload)
        return {"requested_fields": ["taskId"], "question": "Which task should I mark as done?"}

    runtime._post_schema_object = fake_post_schema
    # D-w17-t2: task.complete's unresolved fields were (expectedVersion, taskId).
    question = runtime.formulate_missing_argument_question(
        "Mark the first task on my list as done.", "", _tool("task.complete", TASK_CAS), ("expectedVersion", "taskId"),
    )
    context = json.loads(seen[0]["messages"][1]["content"])
    schema = seen[0]["response_format"]["json_schema"]["schema"]
    assert question == "Which task should I mark as done?"
    assert [item["field"] for item in context["missing_arguments"]] == ["taskId"]
    assert schema["properties"]["requested_fields"]["items"]["enum"] == ["taskId"]


def test_the_same_call_question_never_asks_a_version() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post = MagicMock(
        return_value=_content({"grounded": False, "arguments": None, "fallback_question": "Which task should I change?"}),
    )
    # D-p06-t3 «Change that from bacon to eggs.» restated «Change the task from bacon to eggs.».
    extraction = runtime.extract_direct_arguments("Change the task from bacon to eggs.", _tool("task.update", TASK_UPDATE))
    system = runtime._post.call_args.args[0]["messages"][0]["content"]
    asked = re.search(r"Si falta un dato obligatorio \((\[.*?\])\)", system)
    assert extraction.fallback_question == "Which task should I change?"
    assert asked is not None and "expectedVersion" not in json.loads(asked.group(1))


def test_the_missing_value_the_shell_names_drops_the_guards() -> None:
    assert person_askable_fields(("content", "expectedRevision", "expectedTitle", "noteId", "title")) == (
        "content", "noteId", "title",
    )
    assert person_askable_fields(("expectedVersion",)) == ("expectedVersion",)  # nothing else: still which one
    situation = {"kind": "clarification", "polarity": "pending", "missingValue": "expectedVersion, taskId"}
    assert _required_compose_input(situation) == "taskId"


# ------------------------------------------------------------------ 4. a time taken back


S097 = "Quiero retomar el entrenamiento de glúteo en 2 , no espera en 3 minutos"


def test_a_time_taken_back_is_not_the_request() -> None:
    assert taken_back_time(S097) is not None and taken_back_time(S097).kept == "en 3 minutos"
    # turn-audit request 565: the decider restated it «Pon un temporizador de 2 minutos…».
    fidelity = faithful_request("Pon un temporizador de 2 minutos para retomar el entrenamiento de glúteo.", S097, [])
    assert (fidelity.kind, fidelity.request) == ("person", S097)
    # A restatement with the time kept stays.
    assert faithful_request(
        "Pon un recordatorio en 3 minutos para retomar el entrenamiento de glúteo.", S097, [],
    ).kind == "kept"


def test_the_time_kept_is_scheduled_with_the_task_as_said() -> None:
    assert timed_task(S097) == timed_task(S097).__class__("retomar el entrenamiento de glúteo", "en 3 minutos")
    before = datetime.now(timezone.utc)
    arguments = sidecar._ground_explicit_arguments(
        "notification.schedule", S097, SCHEDULE, history=[{"role": "user", "content": S097}],
    )
    assert arguments is not None and arguments["title"] == "retomar el entrenamiento de glúteo"
    due = datetime.fromisoformat(arguments["dueUtc"].replace("Z", "+00:00"))
    assert timedelta(minutes=2, seconds=50) < due - before < timedelta(minutes=3, seconds=10)
    # D-s121 «Pause exercise at 8:30 actually 9:30.»: the time kept may leave its lead to the one taken back.
    assert timed_task("Pause exercise at 8:30 actually 9:30.") == timed_task(S097).__class__("Pause exercise", "at 9:30")


# ------------------------------------------------------------------ 5. a duration counted from another moment


def test_half_an_hour_before_that_is_not_half_an_hour_from_now() -> None:
    text = "ponme una alarma media hora antes de eso"
    assert sidecar._ground_explicit_arguments("notification.schedule", text, SCHEDULE) is None
    assert sidecar._normalize_grounded_operation_arguments(
        "notification.schedule", {"dueUtc": "media hora", "kind": "alarm", "title": "alarma"}, text,
    ) is None
    # From now it still is.
    assert sidecar._normalize_grounded_operation_arguments(
        "notification.schedule", {"dueUtc": "media hora", "kind": "alarm", "title": "alarma"},
        "ponme una alarma en media hora",
    ) is not None


# ------------------------------------------------------------------ 6. a list named after the word


def test_a_list_named_right_after_the_word_is_read() -> None:
    assert list_entry_request("Pon huevos en mi lista Navidad") == ("huevos", "lista Navidad")
    assert sidecar._ground_explicit_arguments("task.create", "Pon huevos en mi lista Navidad.", TASK_CREATE) == {
        "title": "huevos", "details": "lista Navidad",
    }
    # D-p06-t2 «Add to the Walmart list»: in English the name goes before the word.
    assert list_entry_request("add eggs to the Walmart list") == ("eggs", "Walmart list")
    assert list_removal_request("quita los huevos de la lista Navidad").entry == "huevos"
    # A courtesy is not a name; a playlist is still music.
    assert list_entry_request("pon leche en la lista por favor") == ("leche", "lista")
    assert list_entry_request("añade la canción a mi lista de reproducción") is None


# ------------------------------------------------------------------ 7. the notification just set, moved


def _state_after(observed: dict, request: str) -> DialogueState:
    """The dialogue state as the run left it: the turn that set the notification verified it (compose-audit)."""

    state = DialogueState()
    state.expect(request, ["notification.schedule"])
    state.record({
        "kind": "operation", "operation": "notification.schedule", "polarity": "success", "verified": True,
        "succeeded": True, "observed": observed,
    })
    return state


W16 = ({"version": 1, "kind": "alarm", "title": "alarm for 6:45 tomorrow morning, please",
        "dueUtc": "2026-09-30T09:45:00+00:00", "taskName": "BAXY-Alarm-50d29d2a8dd04168a2cc49324f44808e"},
       "Hey, could you set an alarm for 6:45 tomorrow morning, please?")
W04 = ({"version": 1, "kind": "reminder", "title": "cargar el termo y el mate", "dueUtc": "2026-09-30T09:15:00+00:00",
        "taskName": "BAXY-Reminder-ab2ccd9ec3894f6a90a9387bbbb0a608"},
       "Dale. Poneme un recordatorio para mañana a las 6:15 que diga cargar el termo y el mate")
W18 = ({"version": 1, "kind": "reminder", "title": "tomar un descanso", "dueUtc": "2026-09-29T20:57:47+00:00",
        "taskName": "BAXY-Reminder-fdccbb91a07849ff8b11b0b91eeb19f8"},
       "y remind me en 45 minutes to take a break")
NOW = datetime(2026, 9, 29, 17, 30, tzinfo=CHILE)


def test_a_new_clock_moves_the_alarm_just_set_on_its_day() -> None:
    state = _state_after(*W16)
    state.expect("Change the alarm to 6:30 tomorrow morning.", ["notification.cancel.at", "notification.schedule"])
    moved = state.retimed_notification("Actually, make it 6:30.", now=NOW, zone=CHILE)
    assert moved is not None
    assert sidecar._retimed_step_arguments("notification.cancel.at", moved, CANCEL_AT) == {
        "hour": 6, "minute": 45, "period": "am", "kind": "alarm",
    }
    # The old title said the old time; the alarm is set again by its kind.
    assert sidecar._retimed_step_arguments("notification.schedule", moved, SCHEDULE) == {
        "dueUtc": "2026-09-30T09:30:00Z", "kind": "alarm", "title": "alarm",
    }


def test_a_clock_without_its_part_of_the_day_keeps_the_old_one() -> None:
    state = _state_after(*W04)
    state.expect("Cambia el recordatorio …", ["notification.cancel.at", "notification.schedule"])
    moved = state.retimed_notification("Mejor a las 6 en punto, que si no no llego al micro", now=NOW, zone=CHILE)
    assert moved is not None
    assert sidecar._retimed_step_arguments("notification.cancel.at", moved, CANCEL_AT) == {
        "hour": 6, "minute": 15, "period": "am", "kind": "reminder",
    }
    assert sidecar._retimed_step_arguments("notification.schedule", moved, SCHEDULE) == {
        "dueUtc": "2026-09-30T09:00:00Z", "kind": "reminder", "title": "cargar el termo y el mate",
    }


def test_a_new_duration_counts_from_now() -> None:
    state = _state_after(*W18)
    state.expect("wait no, make it una hora", ["notification.cancel.latest", "notification.schedule"])
    moved = state.retimed_notification("wait no, make it una hora")
    assert moved is not None
    assert sidecar._retimed_step_arguments("notification.cancel.latest", moved, CANCEL_LATEST) == {"kind": "reminder"}
    before = datetime.now(timezone.utc)
    scheduled = sidecar._retimed_step_arguments("notification.schedule", moved, SCHEDULE)
    assert scheduled is not None and (scheduled["kind"], scheduled["title"]) == ("reminder", "tomar un descanso")
    due = datetime.fromisoformat(scheduled["dueUtc"].replace("Z", "+00:00"))
    assert timedelta(minutes=59) < due - before < timedelta(minutes=61)


def test_only_a_change_of_what_the_last_turn_set_is_a_move() -> None:
    assert notification_retiming("a las 6") is None  # may answer a question
    assert notification_retiming("Actually, make it 6:30.") is not None
    # Nothing set by the turn before: no move.
    state = DialogueState()
    state.expect("¿qué hora es?", ["system.time"])
    assert state.retimed_notification("Actually, make it 6:30.", now=NOW, zone=CHILE) is None
    # A turn in between that set nothing: no move either.
    state = _state_after(*W16)
    state.expect("¿qué hora es?", ["system.time"])
    state.expect("Actually, make it 6:30.", ["notification.cancel.at", "notification.schedule"])
    assert state.retimed_notification("Actually, make it 6:30.", now=NOW, zone=CHILE) is None


# ------------------------------------------------------------------ 8. a film named without its service


def test_a_film_named_without_its_service_asks_only_the_service() -> None:
    said = "I'd like to watch a movie called After the Wedding with Spanish subtitles on."
    restated = "Play the movie After the Wedding with Spanish subtitles."  # turn-audit request 1002
    for text in (said, restated):
        assert partial_explicit_arguments("streaming.play.named", text, STREAMING) == {"title": "After the Wedding"}
        assert sidecar._stated_argument_fields("streaming.play.named", text, STREAMING) == ("title",)
    assert partial_explicit_arguments("streaming.play.named", "watch Stranger Things on Netflix", STREAMING) == {}
    runtime = object.__new__(LlmRuntime)
    runtime.formulate_missing_argument_question = MagicMock(return_value="Netflix or Disney+?")
    arguments, question = sidecar.prepare_direct_argument_result(
        runtime, restated, _tool("streaming.play.named", STREAMING), {"title": "After the Wedding"},
    )
    assert (arguments, question) == (None, "Netflix or Disney+?")
    assert runtime.formulate_missing_argument_question.call_args.args[3] == ("service",)


KNOWN_SEARCH = _schema(
    {
        "folder": {"type": "string", "enum": ["all_known", "desktop", "documents", "downloads"]},
        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        "query": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
        "subdirectory": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
    },
    ["folder", "query"],
)
PDF_READ = _schema(
    {
        "fileName": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
        "folder": {"type": "string", "enum": ["all_known", "desktop", "documents", "downloads"]},
        "maximumCharacters": {"type": "integer", "minimum": 200, "maximum": 200000},
    },
    ["fileName", "folder"],
)


def test_the_known_folder_named_is_never_asked_again() -> None:
    # D-w15-t2 «vale, resumemelo en tres puntos», restated «Resumí en tres puntos el informe trimestral de Documentos.»
    # (turn-audit request 1624); the plan asked «¿En qué carpeta conocida deseas buscar y qué nombre exacto…?».
    objective = "Resumí en tres puntos el informe trimestral de Documentos."
    for schema, still_missing in ((KNOWN_SEARCH, ("query",)), (PDF_READ, ("fileName",))):
        partial = partial_explicit_arguments("filesystem.known.search", objective, schema)
        assert partial == {"folder": "documents"}
        assert sidecar.normalize_objective_arguments(partial, schema, objective) == (None, still_missing)
    # A folder the operation does not take is not offered; two folders named decide none.
    assert partial_explicit_arguments("streaming.play.named", objective, STREAMING) == {}
    assert partial_explicit_arguments("filesystem.known.search", "de Descargas a Documentos", KNOWN_SEARCH) == {}


# ------------------------------------------------------------------ 9. a rest of a stated length


def test_a_rest_of_a_stated_length_is_timed() -> None:
    text = "Cojamos un descanso de 14 minutos del yoga para el yoga."
    assert timed_break(text) == timed_task(S097).__class__(
        "descanso de 14 minutos del yoga para el yoga", "en 14 minutos", "alarm",
    )
    before = datetime.now(timezone.utc)
    # turn-audit request 702 restated it «Cojamos un descanso de 14 minutos del yoga.»; the person's text is read too.
    arguments = sidecar._ground_explicit_arguments(
        "notification.schedule", "Cojamos un descanso de 14 minutos del yoga.", SCHEDULE,
        history=[{"role": "user", "content": text}],
    )
    assert arguments is not None and arguments["kind"] == "alarm"
    due = datetime.fromisoformat(arguments["dueUtc"].replace("Z", "+00:00"))
    assert timedelta(minutes=13, seconds=50) < due - before < timedelta(minutes=14, seconds=10)
    assert timed_break("let's take a 10 minute break") is not None
    assert timed_break("tomemos una pausa") is None  # no length: nothing to time


# ------------------------------------------------------------------ 10. a task marked done


# compose-audit t315: the verified listing BAXY told before «mark the first one done».
LISTING = {
    "tasks": [
        {"taskId": "0fd37d83-6f96-4b82-a1c6-9de123985517", "title": "tomates", "completed": False, "version": 1},
        {"taskId": "7ae839dd-2390-476c-b346-6259b7291bce", "title": "Lista del súper", "completed": False, "version": 1},
        {"taskId": "8cdfeabb-878f-405b-bd0e-72e9a86a2863", "title": "beer and chips", "completed": False, "version": 1},
    ],
}


def test_a_task_marked_done_crosses_the_resolver() -> None:
    assert required_predecessors("task.complete") == ("task.resolve.exact",)
    assert required_predecessors("task.reopen") == ("task.resolve.exact",)
    objective = "Mark the first task on my list as done."  # turn-audit request 1665
    skeleton = sidecar._explicit_plan_skeleton(("task.complete",), (objective,))
    assert [(step["operation"], step["dependsOn"], step["argumentsMode"]) for step in skeleton["steps"]] == [
        ("task.resolve.exact", [], "literal"),
        ("task.complete", ["step_1"], "after_dependencies"),
    ]
    observations = [{
        "operation": "task.resolve.exact", "verified": True, "status": "completed",
        "result": {"taskId": "0fd37d83-6f96-4b82-a1c6-9de123985517", "expectedVersion": 1, "reviewLabel": "tomates",
                   "deleted": False, "status": "open"},
    }]
    assert sidecar._verified_dependency_identity_arguments(
        "task.complete", objective, observations, _tool("task.complete", TASK_CAS),
    ) == {"taskId": "0fd37d83-6f96-4b82-a1c6-9de123985517", "expectedVersion": 1}


def test_the_first_one_is_the_first_task_the_listing_told() -> None:
    state = DialogueState()
    state.expect("baxy whats on my to do list", ["task.list"])
    state.record({"kind": "operation", "operation": "task.list", "polarity": "success", "verified": True,
                  "succeeded": True, "observed": LISTING})
    state.expect("Mark the first task on my list as done.", ["task.complete"])
    assert state.pointed_listed_title("mark the first one done") == "tomates"
    assert state.pointed_listed_title("Mark the first task on my list as done.") == "tomates"
    assert state.pointed_listed_title("márcame la última como hecha") == "beer and chips"
    assert state.pointed_listed_title("mark it done") is None
    # Without the listing the turn before, no place in a list is read.
    fresh = DialogueState()
    fresh.expect("mark the first one done", ["task.complete"])
    assert fresh.pointed_listed_title("mark the first one done") is None


def test_a_task_marked_done_by_its_title() -> None:
    assert task_completion_title("mark buy milk as done") == "buy milk"
    assert task_completion_title("marca la tarea llamar a Ana como hecha") == "llamar a Ana"
    assert task_completion_title("complete the task renew car registration") == "renew car registration"
    assert task_completion_title("mark the first one done") is None
    assert task_completion_title("complete the form") is None
    assert sidecar._ground_explicit_arguments("task.resolve.exact", "mark buy milk as done", TASK_RESOLVE) == {
        "title": "buy milk",
    }
