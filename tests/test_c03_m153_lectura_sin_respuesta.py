"""M153 (2026-10-04): a turn understood and done never ends with no final because the guard refuses every draft.

Measured on the sealed set (metadata only, the same code in two rounds): one ``filtered: no_response`` turn in the good
round, five in the bad one — four task.list reads of seven open tasks (first drafts refused as ``reversed_result`` or
``task_title_not_named``, then the composition budget ran out) and one notification.schedule (three drafts of ≈49 bytes
refused as ``extra_claim``). The writer is stochastic; the guard is not:

* the read-only check (``_payload_fact_defect``: «the turn read a state; it did not change it») took a first-person
  verb inside a record title quoted back («hago la cena», «bajo eléctrico») for BAXY's own change, and «bajo el título»
  for «I lower» (DEV-G v4s G-w01-t3, a first draft refused);
* the mute check and the question check (``compose_visible_defect``) took a reminder titled «poner el celular en
  silencio» / «mute the TV» for a mute, and «¿Tomaste la pastilla?» for BAXY asking;
* the floor (``_deterministic_final``) quotes the same titles, so it died with the drafts and the turn had no final.

Record titles are now masked for those lexical checks only (``_record_titles``); a draft that really reverses the read
(the tasks told as done, or none when there are seven) is still refused. Every phrasing below is our own unless it is
a DEV-F/G/H row's.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from baxy_mind import llm

TITLES = [
    "queso gaudá laminado", "marraqueta para la once", "dos paltas hass", "llamar al contador mañana",
    "Renovar el pasaporte", "oat milk", "lemon cookies",
]
# A title that holds a first-person verb of change: the person's words, read back.
VERB_TITLES = TITLES[:5] + ["hago la cena", "bajo eléctrico nuevo"]
NOW = datetime(2026, 3, 4, 15, 0).astimezone()


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "_local_now", lambda: NOW)


class _Scripted(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _final(text: str, situation: dict, drafts: list[str]) -> str:
    facts = {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}
    return _Scripted(drafts).compose_user_message(text, "status", facts)


def _tasks(titles: list[str], completed: int = -1) -> dict:
    tasks = [
        {"taskId": f"id{index}", "title": title, "completed": index == completed, "deleted": False,
         "updatedAtUtc": "2026-10-03T09:31:50.4692362+00:00", "version": 1}
        for index, title in enumerate(titles)
    ]
    return {"kind": "operation", "operation": "task.list", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"tasks": tasks, "count": len(tasks), "mode": "tasks", "limit": 20}}


def _reminder(title: str, hour: int, kind: str = "reminder", days: int = 0) -> dict:
    due = NOW.replace(hour=hour, minute=0) + timedelta(days=days)
    stamp = due.astimezone(timezone.utc).isoformat()
    return {"kind": "operation", "operation": "notification.schedule", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "kind": kind, "title": title, "dueUtc": stamp,
                                            "taskName": "BAXY-Reminder-m153", "state": "Ready", "nextRunUtc": stamp,
                                            "authority": "windows_task_scheduler_postread"}}


def _quoted(titles: list[str], english: bool = False) -> str:
    named = [f"«{title}»" for title in titles]
    return ", ".join(named[:-1]) + (" and " if english else " y ") + named[-1]


def _defect(draft: str, situation: dict, user_text: str) -> str:
    facts = {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}
    payload = {"seen": llm._merged_observed(situation), "operation": situation["operation"]}
    if situation["operation"] == "notification.schedule":
        payload["seen"] = llm._project_scheduled_notification(situation["observed"], situation, "es", user_text)
    return llm.compose_visible_defect(draft, "status", user_text, facts) or llm._payload_fact_defect(
        draft, payload, user_text,
    )


# ------------------------------------------------------------------ 1. a right list of seven open tasks is published


def _right_lists(titles: list[str]) -> list[tuple[str, str]]:
    es, en = _quoted(titles), _quoted(titles, english=True)
    return [
        ("que tengo pendiente para hoy baxy", f"Tienes 7 tareas pendientes: {es}."),
        ("q tengo pendiente pa esta semana", f"Tienes siete tareas pendientes: {es}. Ninguna está completada."),
        ("oye que cosas me quedan por hacer hoy dia, muestrame la lista",
         f"Tienes 7 tareas pendientes y todas siguen sin hacer: {es}."),
        ("¿ya terminé todas mis tareas?", f"No, todavía te quedan 7: {es}. Aún no has completado ninguna."),
        ("muéstrame mis tareas", "Tienes 7 tareas pendientes:\n" + "\n".join(f"- {title}" for title in titles)),
        ("lee lo que llevo", "Tus pendientes son:\n" + "\n".join(f"{n}. {title}" for n, title in enumerate(titles, 1))),
        ("anything still outstanding on my to-do list, or have I cleared the lot?",
         f"You have 7 open tasks: {en}. None of them is completed yet."),
        ("whats left en la lista then", f"Nothing is checked off yet; still pending: {en}."),
    ]


@pytest.mark.parametrize(("user_text", "draft"), _right_lists(VERB_TITLES))
def test_a_title_with_a_verb_of_change_is_not_baxy_changing_anything(user_text: str, draft: str) -> None:
    # Before M153 every one of these died as reversed_result («hago», «bajo» inside a title), and so did the floor.
    assert _final(user_text, _tasks(VERB_TITLES), [draft]) == draft


@pytest.mark.parametrize(("user_text", "draft"), _right_lists(TITLES))
def test_a_list_that_already_passed_passes_the_same(user_text: str, draft: str) -> None:
    assert _final(user_text, _tasks(TITLES), [draft]) == draft


# ------------------------------------------------------------------ 2. a list that reverses the read is still refused


def _reversed_lists(titles: list[str]) -> list[tuple[str, str, str]]:
    es, en = _quoted(titles), _quoted(titles, english=True)
    return [
        ("que tengo pendiente", "No tienes tareas pendientes.", "task_title_not_named"),
        ("what's on my to-do list", "Your to-do list is empty.", "task_title_not_named"),
        ("que tengo pendiente", f"Ya completaste todas: {es}.", "reversed_result"),
        ("que tengo pendiente", f"Todas tus tareas están completadas: {es}.", "reversed_result"),
        ("que tengo pendiente", f"Marqué como hechas {es}.", "reversed_result"),
        ("what's on my to-do list", f"All done: {en}.", "reversed_result"),
        ("what's on my to-do list", f"You've already finished {en}.", "reversed_result"),
        ("que tengo pendiente", f"Tienes 3 tareas pendientes: {es}.", "listing_wrong_count"),
        # BAXY's own change in a read is still its claim, beside the titles.
        ("que tengo pendiente", f"Bajo el volumen; tienes pendientes {es}.", "reversed_result"),
    ]


@pytest.mark.parametrize("titles", [TITLES, VERB_TITLES], ids=["plain", "verb_titles"])
@pytest.mark.parametrize("case", range(9))
def test_a_reversed_list_is_still_refused(titles: list[str], case: int) -> None:
    # The done claims over plain titles passed before M153 (no check read them); now they are the reversal they are.
    user_text, draft, reason = _reversed_lists(titles)[case]
    assert _defect(draft, _tasks(titles), user_text) == reason


def test_a_task_read_as_done_may_be_said_done() -> None:
    # Only a read with every task open makes «está completada» a reversal.
    situation = _tasks(TITLES, completed=0)
    draft = f"«queso gaudá laminado» ya está completada; te quedan {_quoted(TITLES[1:])}."
    assert _defect(draft, situation, "que tengo pendiente") == ""


# ------------------------------------------------------------------ 3. the floor when every draft is refused or late


@pytest.mark.parametrize(
    ("user_text", "drafts", "expected"),
    [
        # The budget ran out after one refused draft (sealed turns B, C, D).
        ("que tengo pendiente para hoy baxy", ["No tienes tareas pendientes."],
         f"Tienes pendientes {_quoted(VERB_TITLES)}."),
        # Two refused drafts, then out of time (sealed turn A).
        ("q tengo pendiente pa esta semana",
         [f"Ya completaste todas: {_quoted(VERB_TITLES)}.", f"Marqué como hechas {_quoted(VERB_TITLES)}."],
         f"Tienes pendientes {_quoted(VERB_TITLES)}."),
        ("anything still outstanding on my to-do list?", [], f"Pending: {_quoted(VERB_TITLES, english=True)}."),
    ],
)
def test_the_task_list_floor_tells_the_titles_read(user_text: str, drafts: list[str], expected: str) -> None:
    assert _final(user_text, _tasks(VERB_TITLES), drafts) == expected


# ------------------------------------------------------------------ 4. a reminder told with its title


@pytest.mark.parametrize(
    ("user_text", "title", "hour", "draft"),
    [
        ("recuérdame a las diez poner el celular en silencio", "Poner el celular en silencio", 22,
         "Te recordaré a las 22:00 poner el celular en silencio."),
        ("recuérdame a las diez poner el celular en silencio", "Poner el celular en silencio", 22,
         "Listo, a las 22:00 te aviso: «Poner el celular en silencio»."),
        ("remind me at 9pm to mute the tv", "Mute the TV", 21, "Reminder set for 9 PM: «Mute the TV»."),
        ("a las nueve pregúntame si tomé la pastilla", "¿Tomaste la pastilla?", 21,
         "Te avisaré a las 21:00: «¿Tomaste la pastilla?»."),
        ("recuérdame a las siete que hago la cena", "Hago la cena", 19, "Te avisaré a las 19:00: «Hago la cena»."),
    ],
)
def test_a_reminder_title_is_no_claim_of_baxy(user_text: str, title: str, hour: int, draft: str) -> None:
    # Before M153: extra_claim (mute, question) or reversed_result three times, the floor too, and no final.
    assert _final(user_text, _reminder(title, hour), [draft, draft, draft]) == draft


def test_dev_g_g_w01_t3_the_alarm_under_its_title() -> None:
    # DEV-G v4s G-w01-t3: the first draft was refused («bajo» read as «I lower») and cost a retry.
    draft = "He programado la alarma para mañana a las 07:00 bajo el título \"Turno temprano\"."
    situation = _reminder("Turno temprano", 7, kind="alarm", days=1)
    assert _final("ya baxy dejame una alarma mañana a las 7 que tengo turno temprano", situation, [draft]) == draft


@pytest.mark.parametrize(
    ("user_text", "draft", "reason"),
    [
        # A mute of BAXY's own, a question of its own and a lowering of its own are still claims.
        ("recuérdame a las siete sacar la basura", "Silencié el teléfono y te avisaré a las 19:00.", "extra_claim"),
        ("recuérdame a las siete sacar la basura", "Te avisaré a las 19:00. ¿Quieres algo más?", "extra_claim"),
        ("recuérdame a las siete sacar la basura", "Bajo el volumen y te aviso a las 19:00.", "reversed_result"),
        # A day the read does not hold is still invented.
        ("recuérdame a las siete sacar la basura", "Te avisaré mañana a las 19:00 para sacar la basura.",
         "extra_claim"),
    ],
)
def test_a_reminder_claim_of_baxy_is_still_refused(user_text: str, draft: str, reason: str) -> None:
    assert _defect(draft, _reminder("Sacar la basura", 19), user_text) == reason


@pytest.mark.parametrize(
    ("user_text", "expected"),
    [
        ("recuérdame a las diez poner el celular en silencio",
         "Puse el recordatorio «Poner el celular en silencio» para las 22:00."),
        ("remind me at ten pm to put the phone on silent",
         "I scheduled the reminder «Poner el celular en silencio» for 22:00."),
    ],
)
def test_the_reminder_floor_tells_its_time_and_title(user_text: str, expected: str) -> None:
    assert _final(user_text, _reminder("Poner el celular en silencio", 22), []) == expected
