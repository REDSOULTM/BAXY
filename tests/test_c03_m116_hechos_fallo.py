"""M116 (2026-10-01): a step that failed for a reason of the PC says what it attempted.

On DEV-F v4e2 (a1739b28) the arguments of F-s005, F-s014, F-s033, F-w01-t4, F-w05-t2, F-w29-t2 (drafts with WhatsApp
or Discord closed), F-w51-t2 (the volume already at its maximum), F-w30-t2/t3/t4 and F-w58-t4 (a window to maximize or
place whose application was absent or closed) were understood and the PC failed; the failure facts carried only the
cause and one target, so the final could not say what was attempted («No pude dejar escrito el mensaje «Lupita».») and
the turn's record hid the arguments. The App now sends them with the failure (C#: ``Baxy.App.AttemptedArguments``,
``MindPlanBoundary.WithStepFacts`` / ``WithNotDone``; M116HechosFalloTests): ``attempted`` (the step's readable
arguments) and ``notDone`` (the effects the failure left undone). Here: the writer is given them and told to name them
with the cause, its drafts that say them are published, the floor says them when every draft dies, a clock they hold
is not invented, and the record the measurement builds from the composed facts shows them.

Every phrasing below is our own.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from baxy_mind import llm, operation_floor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import comprension_eval as ce  # noqa: E402
import comprension_window as cw  # noqa: E402


class _Scripted(llm.LlmRuntime):
    """A writer that answers the given drafts in order, then runs out of time; it keeps what it was sent."""

    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = None
        self.drafts = list(drafts)
        self.sent: list[dict] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(payload)
        if not self.drafts:
            raise TimeoutError("se agotó el presupuesto de composición")
        return {"choices": [{"message": {"content": self.drafts.pop(0)}, "finish_reason": "stop"}]}


def _compose(text: str, situation: dict, drafts: list[str], intent: str = "error") -> tuple[str, _Scripted]:
    writer = _Scripted(drafts)
    facts = {"situation": json.dumps(situation, ensure_ascii=False), "mustNotAskFollowUp": True}
    return writer.compose_user_message(text, intent, facts), writer


def _failed(operation: str, error: str, **extra: object) -> dict:
    return {"kind": "operation", "operation": operation, "polarity": "failure", "verified": False,
            "succeeded": False, "error": error, **extra}


def _mission(reason: dict) -> dict:
    """What MissionNarration.CreateFailureMessage sends for a plan that ended at its first step."""

    return {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
            "reason": reason}


# WhatsApp is not open on this PC: the draft for Ana failed (the App's facts, as M116HechosFalloTests builds them).
WHATSAPP_CLOSED = _mission(_failed(
    "message.draft", "whatsapp_client_not_running", target="Ana",
    attempted={"channel": "whatsapp", "recipient": "Ana", "text": "llego tarde al ensayo"},
))
# «ponlo a la izquierda» with Nébula not installed: the resolve failed and the snap was never run.
WINDOW_ABSENT = _mission(_failed(
    "window.resolve", "app_not_found", target="Nébula", attempted={"applicationName": "Nébula"},
    notDone=[{"operation": "window.snap", "target": "Nébula", "attempted": {"side": "left"}}],
))
VOLUME_AT_MAXIMUM = _mission(_failed(
    "audio.volume.adjust", "volume_already_at_maximum", attempted={"direction": "up", "amount": 15},
))


def _writer_facts(writer: _Scripted) -> str:
    return writer.sent[0]["messages"][-1]["content"]


# ------------------------------------------------------------------ 1. the writer is given what was attempted


def test_the_writer_is_given_what_was_attempted_and_told_to_name_it() -> None:
    final, writer = _compose(
        "déjale escrito a Ana en WhatsApp que llego tarde al ensayo, no lo mandes",
        WHATSAPP_CLOSED,
        ["No pude dejarle escrito a Ana en WhatsApp «llego tarde al ensayo» porque WhatsApp no está abierto."],
    )
    assert final == "No pude dejarle escrito a Ana en WhatsApp «llego tarde al ensayo» porque WhatsApp no está abierto."
    sent = _writer_facts(writer)
    assert '"attempted": {"channel": "whatsapp", "recipient": "Ana", "text": "llego tarde al ensayo"}' in sent
    assert "Los hechos traen lo que se intentó (attempted)" in sent


def test_the_effect_left_undone_reaches_the_writer_as_its_plain_act() -> None:
    _final, writer = _compose(
        "mejor ponlo a la izquierda", WINDOW_ABSENT,
        ["No pude poner Nébula a la izquierda: no está instalada en este equipo."],
    )
    sent = _writer_facts(writer)
    assert '"notDone": [{"action": "colocar la ventana", "target": "Nébula", "attempted": {"side": "left"}}]' in sent
    payload = llm._compose_situation_payload(WINDOW_ABSENT, "en", "put it on the left")
    assert payload["reason"]["notDone"] == [
        {"action": "snap the window", "target": "Nébula", "attempted": {"side": "left"}}
    ]


def test_a_failure_with_nothing_attempted_gets_no_such_instruction() -> None:
    _final, writer = _compose(
        "abre la app de notas", _mission(_failed("app.open", "app_not_found")),
        ["No pude abrir la app de notas porque no está instalada."],
    )
    assert "attempted" not in _writer_facts(writer)


@pytest.mark.parametrize(
    ("text", "situation", "draft"),
    [
        # A follow-up whose words are not the message's: the draft quotes what the facts attempted.
        ("igual mándaselo", WHATSAPP_CLOSED,
         "No pude dejarle escrito a Ana en WhatsApp «llego tarde al ensayo» porque WhatsApp no está abierto."),
        ("ok put it on the left", WINDOW_ABSENT, "I couldn't put Nébula on the left: it isn't installed on this PC."),
        ("pues unos 15 y ahí la dejamos", VOLUME_AT_MAXIMUM, "No subí el volumen 15 puntos: ya estaba al máximo."),
    ],
)
def test_a_draft_that_names_what_was_attempted_is_published(text: str, situation: dict, draft: str) -> None:
    final, _writer = _compose(text, situation, [draft, "", ""])
    assert final == draft


def test_a_clock_the_step_attempted_is_no_invented_clock() -> None:
    # Twin of the App's UserMessagePolicy.InventedClock (M116HechosFalloTests.AClockTheFailedStepAttemptedIsNoInventedClock).
    attempted = _mission(_failed("message.draft", "whatsapp_client_not_running", target="Ana",
                                 attempted={"channel": "whatsapp", "recipient": "Ana", "text": "paso por ti a las 8"}))
    reply = "No pude dejarle escrito a Ana en WhatsApp «paso por ti a las 8:00» porque WhatsApp no está abierto."
    assert not llm._failure_invents_a_clock(reply, "igual déjaselo escrito", attempted)
    bare = _mission(_failed("message.draft", "whatsapp_client_not_running", target="Ana"))
    assert llm._failure_invents_a_clock(reply, "igual déjaselo escrito", bare)


# ------------------------------------------------------------------ 2. the floor says it when every draft dies


@pytest.mark.parametrize(
    ("situation", "spanish", "english"),
    [
        (WHATSAPP_CLOSED,
         "No pude dejar escrito el mensaje para «Ana» en WhatsApp: «llego tarde al ensayo».",
         "I couldn't leave the message written for «Ana» on WhatsApp: «llego tarde al ensayo»."),
        (WINDOW_ABSENT,
         "No pude colocar la ventana «Nébula» a la izquierda.",
         "I couldn't snap the window «Nébula» on the left."),
    ],
)
def test_the_floor_names_what_was_attempted(situation: dict, spanish: str, english: str) -> None:
    assert operation_floor.floor_final(situation, False) == spanish
    assert operation_floor.floor_final(situation, True) == english
    # Every draft dies (a time the facts do not hold, then nothing): the floor is the final.
    final, _writer = _compose("dale", situation, ["Listo, quedó hecho a las 07:45.", "", ""])
    assert final == spanish


def test_the_floor_never_says_the_message_was_the_target() -> None:
    # F-s014: «No pude dejar escrito el mensaje «Lupita».» read the recipient as the message's words.
    reason = _failed("message.draft", "whatsapp_client_not_running", target="Lupita")
    assert operation_floor.floor_final(_mission(reason), False) == "No pude dejar escrito el mensaje para «Lupita»."


# ------------------------------------------------------------------ 3. the record shows the arguments understood


def test_the_record_the_measurement_builds_shows_what_was_attempted(tmp_path: Path, monkeypatch) -> None:
    # The measurement is unchanged (scripts/comprension_window.py reads every node of the composed facts that names
    # an operation; scripts/comprension_eval.py looks for the gold's words there): the facts now hold the arguments.
    audit = tmp_path / "compose-audit.jsonl"
    monkeypatch.setenv("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH", str(audit))
    monkeypatch.setenv("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT", "1")
    _compose("déjale escrito a la Ana en WhatsApp que llego tarde al ensayo", WHATSAPP_CLOSED,
             ["No pude dejarle escrito a Ana en WhatsApp «llego tarde al ensayo» porque WhatsApp no está abierto."])
    _compose("mejor ponlo a la izquierda", WINDOW_ABSENT,
             ["No pude poner Nébula a la izquierda: no está instalada en este equipo."])
    records = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines() if line.strip()]
    arguments = cw.composed_arguments(records, {str(record.get("trace")) for record in records})
    assert ce.args_hold([["ana"], ["llego tarde"]], arguments.get("message.draft"))
    assert ce.args_hold([["nebula", "nébula"], ["left"]], arguments.get("window.snap"))
