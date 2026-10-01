"""M108 (2026-10-01): the final gate on a result's report, the machine's clock out of the tests, and a piece to make
never looked up.

1. M107 reported two leaks of the mind's final gate on a verified effect: a promise of the act («Voy a hacerlo
   enseguida.», «I'll do it right away», «Procederé…») and contract tokens («verified=true succeeded=true», field
   names, error codes, camelCase identifiers, JSON fragments). What was verified is told done or as it was seen; the
   report of a result names no contract token nobody said or observed. The App judges the same
   (UserMessagePolicy.PromisesTheAct / LeaksContractToken; tests/data/c03_m108_gate_twins.json is read on both sides),
   and a refused draft costs a retry, then the floor (M107), as any other.
2. tests/test_c03_m102_retrocesos_v3z.py failed at 09:15 («mejor a las 9»: the 9 nearer a timer was already past on the
   machine's clock). The composer reads the PC's clock in one place (llm._local_now), the floor takes it, and no recent
   test reads the machine's date or hour.
3. Layer A real log:86 «hazme un triangulo con las estaciones del ano» flipped from talk (v3z) to web.search (v4b) at
   the «public_lookup» stage (the guard, a model, read it as public information); a figure, a drawing or a piece of
   verse or fiction to make is never looked up, and neither is a message of punctuation alone («?»).

Every phrasing below is our own.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind import llm, operation_floor
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic.web import not_a_public_lookup
from test_c03_m101b_sin_vacios import _Scripted

ROOT = Path(__file__).resolve().parents[1]
TWINS = json.loads((ROOT / "tests" / "data" / "c03_m108_gate_twins.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ 1. the final gate


@pytest.mark.parametrize("case", TWINS["promises"], ids=lambda case: case["reply"][:40])
def test_a_promised_act_is_told_apart_from_a_told_one(case: dict) -> None:
    assert llm.visible_reply_promises_the_act(case["reply"]) is case["promise"]


@pytest.mark.parametrize("case", TWINS["tokens"], ids=lambda case: case["reply"][:40])
def test_a_contract_token_is_told_apart_from_the_persons_and_the_observed_words(case: dict) -> None:
    assert llm.visible_reply_leaks_a_contract_token(case["reply"], case["situation"], [case["said"]]) is case["leaks"]


def _bluetooth_off(ok: bool = True) -> dict:
    situation: dict = {"kind": "operation", "operation": "bluetooth.radio.set", "polarity": "success" if ok else "failure",
                       "verified": ok, "succeeded": ok}
    if ok:
        situation["observed"] = {"state": False}
    else:
        situation["error"] = "provider_failed"
    return situation


def _facts(situation: dict) -> dict:
    return {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}


def _final(text: str, situation: dict, drafts: list[str], intent: str = "status") -> str:
    return _Scripted(drafts).compose_user_message(text, intent, _facts(situation))


@pytest.mark.parametrize(
    ("said", "draft"),
    [
        ("apagá el bluetooth", "Voy a hacerlo enseguida."),
        ("turn the bluetooth off", "I'll do it right away."),
        ("apagá el bluetooth", "Procederé a apagar el bluetooth."),
    ],
)
def test_a_verified_effect_is_never_promised(said: str, draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", said, _facts(_bluetooth_off())) == "promised_effect"
    # A failure promised nothing that happened: its own checks judge it, not this one.
    assert llm.compose_visible_defect(draft, "error", said, _facts(_bluetooth_off(ok=False))) != "promised_effect"


@pytest.mark.parametrize(
    "draft",
    [
        "Listo, verified=true succeeded=true.",
        "Apagué el Bluetooth (succeeded: true).",
        "Apagué el Bluetooth: {\"state\": \"off\"}.",
        "Apagué el Bluetooth; state=off.",
        "Apagué el Bluetooth con el código 0x80070005.",
    ],
)
def test_a_contract_token_in_a_report_is_internal_code(draft: str) -> None:
    assert llm.compose_visible_defect(draft, "status", "apagá el bluetooth", _facts(_bluetooth_off())) == "internal_code"


def test_a_conversation_is_not_judged_as_the_report_of_a_result() -> None:
    # «debug=true» explained in talk is content, not a leak; the report checks are for a result's report only.
    facts = _facts({"kind": "conversation"})
    assert llm.compose_visible_defect("Pon debug=true en el archivo de configuración.", "status", "cómo activo el debug",
                                      facts) != "internal_code"


@pytest.mark.parametrize(
    ("said", "drafts", "final"),
    [
        # Every draft refused (a promise, a token, a promise): the floor tells what was verified.
        ("apagá el bluetooth", ["Voy a hacerlo enseguida.", "Listo, verified=true succeeded=true.",
                                "Procederé a apagar el bluetooth."], "Apagué el Bluetooth."),
        ("turn the bluetooth off", ["I'll do it right away.", "", ""], "I turned the Bluetooth off."),
        # The retry says it done: that draft is published.
        ("apagá el bluetooth", ["Lo hago enseguida.", "Listo, apagué el Bluetooth."], "Listo, apagué el Bluetooth."),
    ],
)
def test_a_refused_promise_or_token_costs_a_retry_then_the_floor(said: str, drafts: list[str], final: str) -> None:
    assert _final(said, _bluetooth_off(), drafts) == final


def test_a_completed_mission_is_not_promised_either() -> None:
    step = json.dumps({**_bluetooth_off(), "readOnly": False}, ensure_ascii=False)
    mission = {"kind": "status", "polarity": "success", "cause": "mission_completed", "stepCount": 1, "steps": [step]}
    assert llm.compose_visible_defect("Ahora mismo lo apago.", "status", "apagá el bluetooth", _facts(mission)) == (
        "promised_effect"
    )


def test_what_a_verified_notice_will_do_is_its_own_fact() -> None:
    due = datetime(2026, 3, 4, 23, 56, tzinfo=timezone.utc)
    situation = {"kind": "operation", "operation": "notification.schedule", "polarity": "success", "verified": True,
                 "succeeded": True, "observed": {"kind": "reminder", "title": "tomar un descanso",
                                                 "dueUtc": due.isoformat(), "nextRunUtc": due.isoformat()}}
    for draft in ("Te recordaré tomar un descanso.", "I'll remind you to take a break.", "Te voy a avisar a esa hora."):
        assert llm.compose_visible_defect(draft, "status", "recuérdame tomar un descanso", _facts(situation)) != (
            "promised_effect"
        )


def test_the_promised_futures_are_the_catalog_acts_and_doing() -> None:
    futures = llm._spanish_promised_futures()
    assert {"apagare", "abrire", "hare", "procedere", "pondre", "buscaremos"} <= futures
    # A preterite of a verb in «-rar» is no future: «recuperé», «preparé».
    assert not {"recupere", "prepare", "dejare"} & futures
    assert "buscar" in operation_floor.spanish_infinitives() and "buscarlo" not in operation_floor.spanish_infinitives()


# ------------------------------------------------------------------ 2. the PC's clock is injected


def _reminder_due(due: datetime) -> dict:
    return {"kind": "operation", "operation": "reminder.create", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, "title": "Regar el jardín", "dueUtc": due.isoformat()}}


def test_the_floor_tells_the_day_against_the_injected_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    due = datetime(2026, 3, 5, 13, 0, tzinfo=timezone.utc)
    local = due.astimezone()
    clock = f"{'la' if local.hour == 1 else 'las'} {local:%H:%M}"
    monkeypatch.setattr(llm, "_local_now", lambda: (due - timedelta(days=1)).astimezone())
    assert llm._deterministic_final(_reminder_due(due), {}, "recuérdame regar el jardín", "es") == (
        f"Creé el recordatorio «Regar el jardín» para mañana a {clock}."
    )
    monkeypatch.setattr(llm, "_local_now", lambda: (due - timedelta(hours=1)).astimezone())
    assert llm._deterministic_final(_reminder_due(due), {}, "recuérdame regar el jardín", "es") == (
        f"Creé el recordatorio «Regar el jardín» para {clock}."
    )


_RECENT_TEST = re.compile(r"^test_c03_m(9[4-9]|1\d\d)[a-z]?_")
_MACHINE_CLOCK = re.compile(r"\bdatetime\.now\(|\bdate\.today\(|\btime\.localtime\(|\bdatetime\.today\(")


def test_no_recent_test_reads_the_machines_date_or_hour() -> None:
    readers = [
        f"{path.name}:{number}"
        for path in sorted((ROOT / "tests").glob("test_c03_m*.py"))
        if _RECENT_TEST.match(path.name)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if _MACHINE_CLOCK.search(line) and not line.lstrip().startswith("#") and "_MACHINE_CLOCK" not in line
    ]
    assert readers == []


# ------------------------------------------------------------------ 3. a piece to make is never looked up

LOG_86 = "hazme un triangulo con las estaciones del ano"


@pytest.mark.parametrize(
    "text",
    [LOG_86, "hazme un triángulo con las estaciones del año", "dibújame una estrella con los planetas",
     "make me a pyramid with the days of the week", "escribe un poema sobre la lluvia", "?", "¿?", "??", "..."],
)
def test_a_piece_to_make_or_a_bare_mark_is_not_a_public_lookup(text: str) -> None:
    assert not_a_public_lookup(text)


@pytest.mark.parametrize(
    "text",
    ["cuánto mide el everest", "dame un resumen de las noticias de hoy",
     "hazme una lista de los mejores restaurantes de Santiago", "busca la letra de la canción Gracias a la vida"],
)
def test_information_to_look_up_still_is(text: str) -> None:
    assert not not_a_public_lookup(text)


class _GuardSaysLookUp:
    """The guard of v4b: it read the message as public information."""

    def public_lookup_requested(self, _text: str) -> bool:
        return True


def _catalog() -> PlannerCatalog:
    return PlannerCatalog([{"type": "function", "function": {
        "name": "web_search", "canonical_name": "web.search", "description": "Catalog leaf.", "risk": "read_only",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"],
                       "additionalProperties": False},
    }}])


@pytest.mark.parametrize("text", [LOG_86, "?"])
def test_the_guard_cannot_send_a_piece_to_make_or_a_bare_mark_to_the_web(text: str) -> None:
    assert not sidecar._public_lookup_applies(text, text, _GuardSaysLookUp(), ("web.search",), _catalog())


def test_the_guard_still_sends_a_figure_of_the_world() -> None:
    text = "cuánto mide el everest"
    assert sidecar._public_lookup_applies(text, text, _GuardSaysLookUp(), ("web.search",), _catalog())
