"""M107 (2026-10-01): an action always has a visible final.

On the unseen DEV-D messages 12 of 299 turns ended with an empty final for an action (decision path context_decider 8,
explicit_effects 4): «composition_failed: no_response;retry_exhausted» — every draft was vetoed and the mind's last
resort (llm._deterministic_final) had no sentence for that operation — plus 2 on the M102 path that moves the
notification just set (plan notification.cancel.latest + notification.schedule). The texts of those turns are not
read here; the fix is the floor every operation has (baxy_mind.operation_floor, data/operation_floor.v1.json): its
plain clause, done, failed or left uncertain, with what was observed, and for a plan each step's result. The App reads
the same data (Baxy.App.OperationFloor; tests/data/c03_m107_floor_twins.json is checked on both sides).

Every phrasing below is our own.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm, operation_floor
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.dialogue import DialogueState

ROOT = Path(__file__).resolve().parents[1]
TWINS = json.loads((ROOT / "tests" / "data" / "c03_m107_floor_twins.json").read_text(encoding="utf-8"))
PLAIN_CATALOG = json.loads(
    (ROOT / "src" / "baxy_mind" / "data" / "decider_catalog.es.v1.json").read_text(encoding="utf-8")
)["operations"]
SHAPES = {
    "success": {"polarity": "success", "verified": True, "succeeded": True, "observed": {"version": 1}},
    "failure": {"polarity": "failure", "verified": False, "succeeded": False, "error": "provider_failed"},
    "uncertain": {"polarity": "failure", "verified": False, "succeeded": False, "error": "verification_failed",
                  "effectUncertain": True},
}
# A verified result that is no action to tell from the catalog clause: the clock and the PC's measurements have their
# own finals, and the search is not shown (owner's rule 2026-09-24; its not-found is the mind's own fallback).
NO_SUCCESS_FLOOR = {
    operation for operation, entry in operation_floor.floor_data()["operations"].items() if entry.get("noSuccessFloor")
}


def test_only_answers_that_are_values_or_hidden_have_no_success_floor() -> None:
    assert NO_SUCCESS_FLOOR == {"system.time", "system.status", "web.search"}


class _Scripted(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _final(text: str, situation: dict, drafts: list[str], intent: str = "status") -> str:
    facts = {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}
    return _Scripted(drafts).compose_user_message(text, intent, facts)


def _op(operation: str, observed: dict | None = None, ok: bool = True, **extra: object) -> dict:
    situation: dict = {"kind": "operation", "operation": operation, "polarity": "success" if ok else "failure",
                       "verified": ok, "succeeded": ok}
    if observed is not None:
        situation["observed"] = {"version": 1, **observed}
    situation.update(extra)
    return situation


# ------------------------------------------------------------------ 1. every operation has its floor


def test_every_catalog_operation_has_its_plain_clause() -> None:
    data = operation_floor.floor_data()
    assert set(PLAIN_CATALOG) <= set(data["operations"])
    for operation, entry in data["operations"].items():
        for language in ("es", "en"):
            infinitive, past = entry[language]
            assert infinitive and past and "{" not in infinitive + past, operation


@pytest.mark.parametrize("language", ["es", "en"])
@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("operation", sorted(PLAIN_CATALOG))
def test_every_completable_result_has_a_floor(operation: str, shape: str, language: str) -> None:
    situation = {"kind": "operation", "operation": operation, **SHAPES[shape]}
    floor = operation_floor.floor_final(situation, language == "en")
    if shape == "success" and operation in NO_SUCCESS_FLOOR:
        assert floor == ""
        return
    assert floor and floor[0].isupper() and floor.endswith(".") and "{" not in floor and operation not in floor
    # A failure or an uncertain effect is never told as done.
    opening = {
        ("failure", "es"): "No pude ", ("failure", "en"): "I couldn't ",
        ("uncertain", "es"): "Intenté ", ("uncertain", "en"): "I tried to ",
    }.get((shape, language))
    if opening:
        assert floor.startswith(opening), floor
    # The last resort has a final for it (its own sentence or the floor).
    assert llm._deterministic_final(situation, {}, "", language)


@pytest.mark.parametrize("case", TWINS["cases"], ids=lambda case: case["id"])
def test_the_twin_fixture_is_what_the_mind_says(case: dict) -> None:
    # The C# OperationFloor reads the same fixture (M107SueloAccionesTests.TheAppSaysWhatTheMindSays).
    assert operation_floor.floor_final(case["situation"], False) == case["es"]
    assert operation_floor.floor_final(case["situation"], True) == case["en"]


@pytest.mark.parametrize(
    "situation",
    [
        # Owner's review of M75: a turn not understood keeps no fixed final.
        {"kind": "failure", "polarity": "failure", "cause": "turn_runtime_failure", "operationAttempted": False},
        {"kind": "status", "polarity": "success", "cause": "acting", "phase": "acting"},
        {"kind": "clarification", "polarity": "pending", "cause": "ambiguous_request"},
        {"kind": "operation", "operation": "system.power", "polarity": "pending", "status": "pending",
         "error": "confirmation_required"},
        # A plan that ran nothing and names no step has no action to tell.
        {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
         "reason": "plan_incomplete"},
        {"kind": "failure", "polarity": "failure", "cause": "result_unverified", "effectUncertain": True},
    ],
)
def test_no_action_named_has_no_floor(situation: dict) -> None:
    assert operation_floor.floor_final(situation, False) == ""
    assert operation_floor.floor_final(situation, True) == ""


def test_the_typed_failures_said_whole_come_from_the_shared_data() -> None:
    assert llm._DETERMINISTIC_FAILURES["external_verification_failed"] == (
        "No pude confirmar que se hiciera el cambio.", "I couldn't confirm that the change was made.",
    )
    assert set(llm._DETERMINISTIC_FAILURES) == set(operation_floor.floor_data()["failures"])


# ------------------------------------------------------------------ 2. what was observed, never more


@pytest.mark.parametrize(
    ("request_text", "situation", "intent", "final"),
    [
        ("ábreme la calcu", _op("app.open", {"appId": "windows.calculator", "displayName": "Calculadora",
                                            "alreadyRunning": False, "processId": 8}), "status",
         "Abrí la aplicación «Calculadora»."),
        ("cerrá el bloc", _op("app.close", {"processId": 3, "windowClosed": True}), "status", "Cerré la ventana."),
        ("pegá la ventana a la derecha", _op("window.snap", {"side": "right"}), "status",
         "Coloqué la ventana: a la derecha."),
        ("silenciá todo", _op("audio.mute", {"state": {"muted": True, "volumePercent": 25}, "applied": True}),
         "status", "Silencié el sonido: volumen al 25 %."),
        ("apagame el bluetooth", _op("bluetooth.radio.set", {"state": False, "changed": True}), "status",
         "Apagué el Bluetooth."),
        ("¿tengo el wifi prendido?", _op("wifi.radio.status", {"radioOn": False}), "status",
         "Consulté el Wi-Fi: está apagado."),
        ("qué notas tengo", _op("note.list", {"count": 2, "notes": [{"title": "Recetas"}, {"title": "Taller"}]}),
         "status", "Revisé tus notas; hay 2: «Recetas» y «Taller»."),
        ("conectate a la red de la oficina", _op("wifi.connect.named", {"ssid": "Oficina-2", "connected": True}),
         "status", "Me conecté a la red Wi-Fi «Oficina-2»."),
        ("dale play a Encanto en disney", _op("streaming.play.named", {"title": "Encanto", "playbackStatus": "playing"}),
         "status", "Puse a reproducir en streaming «Encanto»: se está reproduciendo."),
        ("put some daft punk on spotify", _op("media.play.query", {"title": "One More Time", "artist": "Daft Punk",
                                                                 "playbackStatus": "playing"}), "status",
         "I played the music «One More Time» by Daft Punk: it is playing."),
        ("con qué usuario estás corriendo", _op("system.identity", {"userName": "marta", "domain": "CASA"}), "status",
         "Consulté la cuenta de Windows: «marta»."),
        ("qué copié recién", _op("clipboard.read.text", {"text": "turno de las 9"}), "status",
         "Leí el portapapeles: dice «turno de las 9»."),
        ("bajá un poco el brillo", _op("system.settings.adjust", {"setting": "brightness", "direction": "down",
                                                                 "amount": 10, "baselineValues": [45],
                                                                 "values": [35]}), "status", "Cambié el brillo."),
        ("activá no molestar", _op("system.settings.set", {"setting": "do_not_disturb", "value": 1, "before": 0}),
         "status", "Cambié el modo no molestar."),
        ("could you launch obsidian", _op("app.open", ok=False, error="app_not_found"), "error",
         "I couldn't open the app."),
        ("pasá el informe a la carpeta de trabajo", _op("filesystem.move", ok=False, error="verification_failed",
                                                       effectUncertain=True), "error",
         "Intenté mover el archivo, pero no pude confirmar si se hizo."),
    ],
)
def test_an_action_whose_drafts_all_died_is_told_from_its_facts(
    request_text: str, situation: dict, intent: str, final: str,
) -> None:
    # Drafts that die: a time the facts do not hold, then nothing written twice.
    drafts = ["Listo, ya quedó todo hecho a las 07:45.", "", ""]
    assert _final(request_text, situation, drafts, intent) == final


def test_a_name_too_long_or_with_quotes_is_not_said() -> None:
    long_title = "x" * 130
    assert operation_floor.floor_final(_op("note.create", {"title": long_title}), False) == "Creé la nota."
    assert operation_floor.floor_final(_op("note.create", {"title": "la «buena»"}), False) == "Creé la nota."


# ------------------------------------------------------------------ 3. the moved notification (M102), end to end

CHILE = timezone(timedelta(hours=-3))
SET = "recuérdame en 40 minutos sacar la ropa de la lavadora"
MOVE = "ah no, mejor en una hora"


def _scheduled(due: datetime, title: str = "sacar la ropa de la lavadora", kind: str = "reminder") -> dict:
    stamp = due.astimezone(timezone.utc).isoformat()
    return _op("notification.schedule", {"kind": kind, "title": title, "dueUtc": stamp, "nextRunUtc": stamp,
                                         "taskName": "BAXY-Reminder-m107", "state": "Ready",
                                         "authority": "windows_task_scheduler_postread"})


def _step(situation: dict) -> str:
    return json.dumps({**situation, "readOnly": False}, ensure_ascii=False)


def _clock(due: datetime) -> str:
    local = due.astimezone()
    return f"{'la' if local.hour == 1 else 'las'} {local:%H:%M}"


def test_the_move_is_a_plan_and_its_floor_says_each_step() -> None:
    first_due = datetime.now(CHILE).replace(microsecond=0) + timedelta(minutes=40)
    state = DialogueState()
    state.expect(SET, ["notification.schedule"])
    state.record(_scheduled(first_due))

    class NoDecider:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"the decider was asked ({name})")

    history = [
        {"role": "user", "content": SET},
        {"role": "assistant", "content": "Te lo recordaré."},
        {"role": "user", "content": MOVE},
    ]
    tool = {"type": "function", "function": {
        "name": "notification_schedule", "canonical_name": "notification.schedule", "description": "Catalog leaf.",
        "risk": "low_reversible",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    }}
    result = sidecar._prepare_turn_result(
        {"id": "m107", "text": MOVE, "history": history},
        llm=NoDecider(), planner_catalog=PlannerCatalog([tool]), encoder=lambda _texts: (), tool_by_name={},
        dialogue_state=state,
    )
    assert result["kind"] == "plan"
    assert result["effectOperations"] == ["notification.cancel.latest", "notification.schedule"]

    # What the shell's mission returns once both steps ran: the latest reminder cancelled, the same one set again.
    new_due = datetime.now(CHILE).replace(microsecond=0) + timedelta(hours=1)
    cancelled = _op("notification.cancel.latest", {"kind": "reminder", "taskName": "BAXY-Reminder-m107",
                                                   "canceled": True,
                                                   "authority": "windows_task_scheduler_absence_postread"})
    mission = {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
               "steps": [_step(cancelled), _step(_scheduled(new_due))], "completedRequest": result["objective"]}
    day = "" if new_due.astimezone().date() == datetime.now().astimezone().date() else "mañana a "
    final = (f"Cancelé el último recordatorio y puse el recordatorio «sacar la ropa de la lavadora» para "
             f"{day}{_clock(new_due)}.")
    assert operation_floor.floor_final(mission, False) == final
    # Every draft is vetoed: a time the facts do not hold, the move told as a second reminder, a promise.
    drafts = [
        f"Listo, te aviso a las {(new_due + timedelta(minutes=7)).astimezone():%H:%M}.",
        "Ahora tienes dos recordatorios para sacar la ropa.",
        "Voy a cambiar la hora del recordatorio.",
    ]
    assert _final(MOVE, mission, drafts) == final


def test_a_move_whose_new_time_could_not_be_set_says_what_was_done() -> None:
    cancelled = _op("notification.cancel.latest", {"kind": "alarm", "canceled": True})
    failed = {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 1,
              "steps": [_step(cancelled)],
              "reason": _op("notification.schedule", ok=False, error="notification_schedule_invalid")}
    drafts = ["Listo, la alarma quedó para las 06:15.", "Tu alarma sigue igual.", ""]
    assert _final("no, mejor a las seis y cuarto", failed, drafts, "error") == (
        "Cancelé la última alarma, pero no pude programar el aviso."
    )
    uncertain = {**failed, "reason": json.dumps(_op("notification.schedule", ok=False,
                                                    error="notification_scheduler_failed", effectUncertain=True))}
    assert _final("actually make it 6:15", uncertain, drafts, "error") == (
        "I cancelled the latest alarm and I tried to set the alarm or reminder, but I couldn't confirm whether it was "
        "done."
    )


def test_a_move_with_nothing_left_to_cancel_says_so() -> None:
    nothing = _op("notification.cancel.latest", {"kind": "reminder", "canceled": False})
    new_due = datetime.now(CHILE).replace(microsecond=0) + timedelta(minutes=90)
    mission = {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 2,
               "steps": [_step(nothing), _step(_scheduled(new_due, "llamar a la abuela"))]}
    day = "" if new_due.astimezone().date() == datetime.now().astimezone().date() else "mañana a "
    assert operation_floor.floor_final(mission, False) == (
        "No había ningún recordatorio pendiente que cancelar y puse el recordatorio «llamar a la abuela» para "
        f"{day}{_clock(new_due)}."
    )


@pytest.mark.parametrize(
    ("days", "spanish", "english"),
    [
        (1, "para mañana a {article} {clock}", "for tomorrow at {clock}"),
        (9, "para el {day} de {month} a {article} {clock}", "for {month_en} {day} at {clock}"),
    ],
)
def test_the_scheduled_time_carries_its_day_when_it_is_not_today(days: int, spanish: str, english: str) -> None:
    now = datetime.now().astimezone().replace(hour=10, minute=0, second=0, microsecond=0)
    due = now + timedelta(days=days, hours=5, minutes=30)
    local = due.astimezone()
    months = operation_floor.floor_data()["templates"]
    words = {"article": "la" if local.hour == 1 else "las", "clock": f"{local:%H:%M}", "day": local.day,
             "month": months["es"]["months"][local.month - 1], "month_en": months["en"]["months"][local.month - 1]}
    situation = _scheduled(due, "regar el jardín", "alarm")
    assert operation_floor.floor_final(situation, False, now=now) == (
        f"Puse la alarma «regar el jardín» {spanish.format(**words)}."
    )
    assert operation_floor.floor_final(situation, True, now=now) == (
        f"I scheduled the alarm «regar el jardín» {english.format(**words)}."
    )
