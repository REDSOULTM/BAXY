"""M80 (2026-09-30, independent review of the official-window DEV-D run v3m): zero questions for a datum already given.

Evidence: %LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3m-devD/ (REVIEW.reviewed.jsonl, turn-audit.jsonl,
compose-audit.jsonl, RUN.jsonl, run.map.json). Each test replays the recorded text, restatement or verified observation
of one flagged row; the causes:

1. A moment one notification cannot hold asked everything again (D-s104 «…para la cena a las 18:00 hoy.» at 19:35 →
   «¿Cuál es la hora exacta, qué tipo … y qué título…?»; D-s108 «…Monday, Tuesday and Wednesday of this week for 7am»
   on a Tuesday → «What time … and what should the title be?»): only when is asked, saying why.
2. A music service the catalog does not play on was asked for (D-s069 «I need Pandora to play me a birthday song.» →
   «Which music provider should be used…?»): it is the limit.
3. task.update replaces every field, so a change of the task just made asked its due date and which task (D-p06-t2,
   D-p06-t3, D-p08-t3): the fields not changed are kept from the task the store verified.
4. «nevermind» before a new order hid the order (D-p17-t3 «nevermind add an item to my swimming list» added
   «swimming»): the item is asked.
5. The Task Scheduler is shared by every BAXY data root (D-w16-t2: six runs left six alarms at 06:45; D-w18-t5: «cancel
   the latest» took an arbitrary reminder because RegistrationInfo.Date is empty): a BAXY resolves, cancels and lists
   only the notifications whose ring script is in its own data root, and the latest is the pending one written last.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import DirectArgumentExtraction, LlmRuntime
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.notes import task_change
from baxy_mind.semantic.patterns import known_unsupported_effect_request, resolve_explicit_clarification_intent
from baxy_mind.semantic.temporal import UnschedulableTime, unschedulable_time


def _schema(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


# The catalog's schemas (ProductCatalog.cs).
SCHEDULE = _schema(
    {
        "dueUtc": {"type": "string", "maxLength": 64, "x-nonWhitespace": True},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "recurrence": {"type": "string", "enum": ["daily", "hourly"]},
        "title": {"type": "string", "x-maxUtf8Bytes": 1024, "x-nonWhitespace": True},
    },
    ["dueUtc", "kind", "title"],
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


def _tool(name: str, schema: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name.replace(".", "_"),
            "canonical_name": name,
            "description": "Operación del catálogo.",
            "parameters": json.loads(json.dumps(schema)),
        },
    }


CHILE = timezone(timedelta(hours=-3))
RUN_NOW = datetime(2026, 9, 29, 19, 35, tzinfo=CHILE)  # Tuesday, the run's hour (shell-trace t104)
S104 = "Programa una alarma nueva para la cena a las 18:00 hoy."
S108 = "Set a 'wake-up' alarm for Monday, Tuesday and Wednesday of this week for 7am"


# ------------------------------------------------------------------ 1. a moment one notification cannot hold


def test_todays_clock_already_past_and_several_days_are_read() -> None:
    assert unschedulable_time(S104, RUN_NOW) == UnschedulableTime("a las 18:00", ("hoy",), ())
    assert unschedulable_time(S108, RUN_NOW) == UnschedulableTime("7am", ("monday", "tuesday"), ("wednesday",))
    # A moment one notification holds is none of this.
    assert unschedulable_time("Programa una alarma para la cena a las 21:00 hoy.", RUN_NOW) is None
    assert unschedulable_time("Set an alarm for Thursday at 7am", RUN_NOW) is None
    assert unschedulable_time("pon una alarma a las 18:00", RUN_NOW) is None
    assert unschedulable_time("pon una alarma el 3 de octubre a las 18:00", RUN_NOW) is None


@pytest.mark.parametrize(
    "row, text, language, said",
    [
        ("D-s104", S104, "es", ("18:00", "already passed", "19:35")),
        ("D-s108", S108, "en", ("7am", "monday, tuesday", "several days", "already passed")),
    ],
)
def test_only_when_is_asked_saying_why(row: str, text: str, language: str, said: tuple[str, ...]) -> None:
    runtime = object.__new__(LlmRuntime)
    runtime.formulate_missing_argument_question = MagicMock(return_value="¿Cuándo?")
    question = sidecar._unschedulable_time_question(
        runtime, "notification.schedule", text, text, _tool("notification.schedule", SCHEDULE), language, now=RUN_NOW,
    )
    assert question == "¿Cuándo?", row
    call = runtime.formulate_missing_argument_question.call_args
    assert call.args[3] == ("dueUtc",)
    assert call.kwargs["response_language"] == language
    ask = call.kwargs["ask_as"]["dueUtc"]
    assert all(part in ask for part in said), ask
    assert "never ask them" in ask


def test_a_moment_a_notification_holds_asks_nothing_here() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime.formulate_missing_argument_question = MagicMock(side_effect=AssertionError("asked"))
    tool = _tool("notification.schedule", SCHEDULE)
    assert sidecar._unschedulable_time_question(
        runtime, "notification.schedule", "pon una alarma a las 21:00 hoy", "", tool, "es", now=RUN_NOW,
    ) == ""
    assert sidecar._unschedulable_time_question(runtime, "task.create", S104, S104, tool, "es", now=RUN_NOW) == ""


# ------------------------------------------------------------------ 2. a music service not offered


def test_a_music_service_not_offered_is_the_limit() -> None:
    available = ("media.play.query", "media.play.youtube", "media.play.exact")
    assert known_unsupported_effect_request("I need Pandora to play me a birthday song.", available)
    assert known_unsupported_effect_request("pon música en Deezer", available)
    # Spotify and YouTube are played; opening an app is not playing on it.
    assert not known_unsupported_effect_request("play a birthday song on Spotify", available)
    assert not known_unsupported_effect_request("pon cumpleaños feliz en YouTube", available)
    assert not known_unsupported_effect_request("abre Tidal", available)


# ------------------------------------------------------------------ 3. a change of the task just made


# compose-audit t143 and t150: the tasks the store verified before the change.
BACON = {"taskId": "c329d7e7-5026-4acc-9f1e-1cd52478d6b7", "title": "bacon", "details": "shopping list",
         "completed": False, "deleted": False, "createdAtUtc": "2026-09-29T22:28:06.8862847+00:00",
         "updatedAtUtc": "2026-09-29T22:28:06.8862847+00:00", "version": 1}
HUEVOS = {"taskId": "d994119e-b8bf-4138-a31a-3284cd94004c", "title": "huevos", "details": "lista Navidad",
          "completed": False, "deleted": False, "createdAtUtc": "2026-09-29T22:28:23.4361982+00:00",
          "updatedAtUtc": "2026-09-29T22:28:23.4361982+00:00", "version": 1}


def _after_create(request: str, observed: dict) -> DialogueState:
    state = DialogueState()
    state.expect(request, ["task.create"])
    state.record({"kind": "operation", "operation": "task.create", "polarity": "success", "verified": True,
                  "succeeded": True, "observed": observed})
    return state


def test_the_readers_read_only_what_changes() -> None:
    # The person's messages and the decider's restatements (turn-audit requests 841, 845, 873).
    assert task_change("Change to that eggs. Add to the Walmart list.", "bacon") == {
        "title": "eggs", "details": "Walmart list",
    }
    assert task_change("Change that from bacon to eggs.", "bacon") == {"title": "eggs"}
    assert task_change("Change the task from bacon to eggs.", "bacon") == {"title": "eggs"}
    assert task_change("No, cámbialo a la lista Comida", "huevos") == {"details": "lista Comida"}
    assert task_change("Cambia los huevos de la lista Navidad a la lista Comida.", "huevos") == {
        "details": "lista Comida",
    }
    assert task_change("cambia el tocino por huevos", "tocino") == {"title": "huevos"}
    # «from X to Y» names the task by its old name; another old name changes nothing.
    assert task_change("Change it from milk to eggs.", "bacon") == {}
    assert task_change("change it", "bacon") == {}


def test_the_task_just_made_stays_through_a_question_and_leaves_with_another_effect() -> None:
    state = _after_create("Add bacon for me", BACON)
    state.expect("Change the grocery list to eggs and add it to the Walmart list.", ["task.update"])
    assert state.edited_task() == {
        "taskId": BACON["taskId"], "expectedVersion": 1, "title": "bacon", "details": "shopping list", "due": None,
    }
    # D-p06-t3 came after BAXY's question: nothing was done in between, the task is the same.
    state.expect("Change the task from bacon to eggs.", ["task.update"])
    assert state.edited_task() is not None and state.edited_task()["taskId"] == BACON["taskId"]
    # Another effect done after it: «cámbialo» no longer points at it.
    state.record({"kind": "operation", "operation": "task.update", "polarity": "failure", "verified": False,
                  "succeeded": False})
    other = _after_create("Add bacon for me", BACON)
    other.expect("¿qué hora es?", ["system.time"])
    other.record({"kind": "operation", "operation": "system.time", "polarity": "success", "verified": True,
                  "succeeded": True, "observed": {"time": "19:35"}})
    other.expect("Change that from bacon to eggs.", ["task.update"])
    assert other.edited_task() is None


@pytest.mark.parametrize(
    "row, created, person, objective, changed",
    [
        ("D-p06-t2", BACON, "Change to that eggs. Add to the Walmart list.",
         "Change the grocery list to eggs and add it to the Walmart list.", {"title": "eggs", "details": "Walmart list"}),
        ("D-p06-t3", BACON, "Change that from bacon to eggs.", "Change the task from bacon to eggs.", {"title": "eggs"}),
        ("D-p08-t3", HUEVOS, "No, cámbialo a la lista Comida", "Cambia los huevos de la lista Navidad a la lista Comida.",
         {"details": "lista Comida"}),
    ],
)
def test_a_change_keeps_what_was_not_changed(row: str, created: dict, person: str, objective: str, changed: dict) -> None:
    state = _after_create("…", created)
    state.expect(objective, ["task.update"])
    runtime = object.__new__(LlmRuntime)
    runtime.extract_direct_arguments = MagicMock(side_effect=AssertionError(f"{row} extracted"))
    runtime.formulate_missing_argument_question = MagicMock(side_effect=AssertionError(f"{row} asked"))
    arguments, question = sidecar._edited_task_arguments(
        runtime, objective, person, _tool("task.update", TASK_UPDATE), state.edited_task(), f"{objective}\n{person}",
        "en",
    )
    assert question == ""
    assert arguments == {
        "taskId": created["taskId"], "expectedVersion": 1, "title": created["title"], "details": created["details"],
        "due": None, **changed,
    }


def test_the_model_reads_only_the_fields_that_change_and_each_must_be_said() -> None:
    state = _after_create("Add bacon for me", BACON)
    runtime = object.__new__(LlmRuntime)
    seen: list[dict] = []

    def extract(text: str, tool: dict, **_: object):
        seen.append(tool["function"]["parameters"])
        return DirectArgumentExtraction({"title": "turkey bacon", "details": "Costco"}, (), "")

    runtime.extract_direct_arguments = extract
    runtime.formulate_missing_argument_question = MagicMock(side_effect=AssertionError("asked"))
    arguments, question = sidecar._edited_task_arguments(
        runtime, "Make it turkey bacon.", "make it turkey bacon", _tool("task.update", TASK_UPDATE),
        state.edited_task(), "Make it turkey bacon.\nmake it turkey bacon", "en",
    )
    # Neither the identity nor the version is ever the model's; «Costco» was not said.
    assert seen[0]["required"] == [] and set(seen[0]["properties"]) == {"title", "details", "due"}
    assert question == ""
    assert arguments is not None and (arguments["title"], arguments["details"]) == ("turkey bacon", "shopping list")


def test_nothing_changed_asks_what_to_change_never_which_task() -> None:
    state = _after_create("Add bacon for me", BACON)
    runtime = object.__new__(LlmRuntime)
    runtime.extract_direct_arguments = MagicMock(return_value=DirectArgumentExtraction({}, (), ""))
    runtime.formulate_missing_argument_question = MagicMock(return_value="What should I change in bacon?")
    arguments, question = sidecar._edited_task_arguments(
        runtime, "Change it.", "change it", _tool("task.update", TASK_UPDATE), state.edited_task(), "change it", "en",
    )
    assert (arguments, question) == (None, "What should I change in bacon?")
    call = runtime.formulate_missing_argument_question.call_args
    assert call.args[3] == ("title",) and "never ask which one" in call.kwargs["ask_as"]["title"]


# ------------------------------------------------------------------ 4. «nevermind» before a new order


def test_an_order_after_taking_the_last_one_back_is_read() -> None:
    available = ("task.create", "note.create")
    intent = resolve_explicit_clarification_intent("nevermind add an item to my swimming list", available)
    assert intent is not None and intent.missing_fields == ("list_entries",)
    assert resolve_explicit_clarification_intent("never mind, add an item to my list", available) is not None


# ------------------------------------------------------------------ 5. the notifications this data root set


SCRIPT = Path(__file__).resolve().parents[1] / "src" / "Baxy.Providers.Windows" / "External" / (
    "WindowsScheduledNotification.ps1"
)
# The Task Scheduler cmdlets replaced by functions (a function wins over a cmdlet): nothing real is read or removed.
STUBS = r"""
$global:Tasks = [ordered]@{}
foreach ($entry in (ConvertFrom-Json $env:M80_TASKS)) { $global:Tasks[$entry.name] = $entry.next }
$global:Removed = @()
function Get-ScheduledTask { param([string]$TaskName, $ErrorAction)
    foreach ($name in @($global:Tasks.Keys)) {
        if ($name -like $TaskName) { [pscustomobject]@{ TaskName = $name; RegistrationInfo = [pscustomobject]@{ Date = $null } } }
    } }
function Get-ScheduledTaskInfo { param([string]$TaskName, $ErrorAction)
    $next = $global:Tasks[$TaskName]
    [pscustomobject]@{ NextRunTime = $(if ($next) { [datetime]::Parse($next) } else { [datetime]::MinValue }) } }
function Unregister-ScheduledTask { param([string]$TaskName, $Confirm)
    $global:Tasks.Remove($TaskName); $global:Removed += $TaskName }
"""


def _run_script(tmp_path: Path, tasks: list[dict], own: list[str], *arguments: str) -> dict:
    root = tmp_path / "scheduled-notifications"
    root.mkdir(exist_ok=True)
    for age, name in enumerate(reversed(own)):
        ring = root / f"{name}.ps1"
        ring.write_text("# ring", encoding="utf-8")
        stamp = datetime.now().timestamp() - 60 * (age + 1)
        os.utime(ring, (stamp, stamp))
    command = STUBS + f"& '{SCRIPT}' {' '.join(arguments)} -AlarmRoot '{root}'"
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
        env={**os.environ, "M80_TASKS": json.dumps(tasks)},
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _name(kind: str, digit: str) -> str:
    return f"BAXY-{kind}-{digit * 32}"


def test_the_latest_is_the_pending_one_this_data_root_wrote_last(tmp_path: Path) -> None:
    later = (datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds")
    # D-w18-t5: the break reminder is the last one written here; one already rang; another run's is pending too.
    written_first, written_last, rang, other_run = (_name("Reminder", digit) for digit in "abcd")
    tasks = [{"name": other_run, "next": later}, {"name": rang, "next": None},
             {"name": written_first, "next": later}, {"name": written_last, "next": later}]
    result = _run_script(tmp_path, tasks, [written_first, rang, written_last], "-Mode", "cancel", "-Kind", "reminder")
    # ``own`` is oldest first; the one that rang was written after the first but it no longer rings.
    assert result["canceled"] is True and result["taskName"] == written_last


def test_the_clock_resolves_among_the_notifications_this_data_root_set(tmp_path: Path) -> None:
    tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=6, minute=45, second=0, microsecond=0)
    at = tomorrow.isoformat(timespec="seconds")
    # D-w16-t2: six runs left an alarm at 06:45; this run's is the only one it set.
    mine = _name("Alarm", "e")
    tasks = [{"name": _name("Alarm", digit), "next": at} for digit in "12345"] + [{"name": mine, "next": at}]
    result = _run_script(
        tmp_path, tasks, [mine], "-Mode", "resolve-at", "-Kind", "alarm", "-Hour", "6", "-Minute", "45", "-Period", "am",
    )
    assert (result["ok"], result["matchCount"], result["taskName"]) == (True, 1, mine)
