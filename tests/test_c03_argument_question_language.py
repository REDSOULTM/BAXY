"""M47: the question for a missing argument is asked in the turn's language.

FINAL 2026-09-28 F-w09-t5 «Sure, tomorrow at noon, please» (objective restated
as «Set a reminder for tomorrow at noon to pay the water bill.») was asked
«¿Es una alarma o un recordatorio?», and F-p02-t3 «no, clear out the last item
on the list» was asked in Spanish too. The shell now sends the language the
turn decision chose with the ``arguments`` request, and the mind binds both the
same-call fallback and the formulated question to it.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import sys
import traceback
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind import __main__ as sidecar
from baxy_mind.llm import (
    DirectArgumentExtraction,
    LlmRuntime,
    _build_direct_argument_payload,
)


_SCHEDULE_SCHEMA = {
    "type": "object",
    "properties": {
        "dueUtc": {"type": "string", "x-nonWhitespace": True},
        "kind": {"type": "string", "enum": ["alarm", "reminder"]},
        "title": {"type": "string", "x-nonWhitespace": True},
    },
    "required": ["dueUtc", "kind", "title"],
    "additionalProperties": False,
}


def _tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "notification_schedule",
            "canonical_name": "notification.schedule",
            "description": "Programa una alarma o un recordatorio local.",
            "parameters": json.loads(json.dumps(_SCHEDULE_SCHEMA)),
        },
    }


def _abstention(question: str) -> dict:
    content = json.dumps(
        {"grounded": False, "arguments": None, "fallback_question": question},
        ensure_ascii=False,
    )
    return {"choices": [{"message": {"content": content}}]}


def test_the_extraction_prompt_binds_the_fallback_to_the_turn_language() -> None:
    common = dict(
        text="Set a reminder for tomorrow at noon to pay the water bill.",
        canonical_name="notification.schedule",
        description="Programa una alarma o un recordatorio local.",
        schema=_SCHEDULE_SCHEMA,
        required_fields=("kind",),
        open_string_fields=("dueUtc", "title"),
    )
    english = _build_direct_argument_payload(**common, response_language="en")["messages"][0]["content"]
    unknown = _build_direct_argument_payload(**common)["messages"][0]["content"]
    assert "Mandatory language for the question: English." in english
    assert "Usa el idioma del pedido" not in english
    assert "Usa el idioma del pedido" in unknown


def test_a_fallback_in_the_other_language_is_formulated_again_in_the_turn_language() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post = MagicMock(return_value=_abstention("¿Quieres una alarma o un recordatorio?"))
    runtime.formulate_missing_argument_question = MagicMock(
        return_value="Should it be an alarm or a reminder?",
    )
    objective = "Set a reminder for tomorrow at noon to pay the water bill."

    extraction = runtime.extract_direct_arguments(objective, _tool(), response_language="en")
    arguments, question = sidecar.prepare_direct_argument_result(
        runtime, objective, _tool(), extraction.arguments, extraction.fallback_question,
        response_language="en",
    )

    assert extraction.fallback_question == ""
    assert arguments is None
    assert question == "Should it be an alarm or a reminder?"
    assert runtime.formulate_missing_argument_question.call_args.kwargs == {"response_language": "en"}


def test_a_fallback_already_in_the_turn_language_is_kept() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._post = MagicMock(return_value=_abstention("Should it be an alarm or a reminder?"))
    extraction = runtime.extract_direct_arguments(
        "Set a reminder for tomorrow at noon to pay the water bill.", _tool(), response_language="en",
    )
    assert extraction.fallback_question == "Should it be an alarm or a reminder?"


def test_the_formulated_question_is_bound_to_the_turn_language() -> None:
    runtime = object.__new__(LlmRuntime)
    seen: list[dict] = []

    def fake_post_schema(payload: dict, _label: str) -> dict:
        seen.append(payload)
        return {"requested_fields": ["kind"], "question": "Should it be an alarm or a reminder?"}

    runtime._post_schema_object = fake_post_schema
    question = runtime.formulate_missing_argument_question(
        "Crea un recordatorio para mañana a mediodía.", "", _tool(), ("kind",), response_language="en",
    )
    assert question == "Should it be an alarm or a reminder?"
    system = seen[0]["messages"][0]["content"]
    assert "Mandatory language for the question: English." in system
    assert "Usa el idioma del pedido" not in system


@pytest.mark.parametrize("language", ["en", None])
def test_the_arguments_request_carries_the_turn_language_to_the_question(monkeypatch, language) -> None:
    calls: dict[str, dict] = {}

    class RecordingLlm:
        def start_warmup(self):
            pass

        def wait_warmup(self, _timeout):
            return True

        def begin_request(self, *_args, **_kwargs):
            pass

        def end_request(self):
            pass

        def extract_direct_arguments(self, *_args, **kwargs):
            calls["extract"] = kwargs
            return DirectArgumentExtraction(None, (), "")

        def formulate_missing_argument_question(self, *_args, **kwargs):
            calls["formulate"] = kwargs
            return "Should it be an alarm or a reminder?"

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "never-loaded.gguf")
    monkeypatch.setattr(sidecar, "LlmRuntime", RecordingLlm)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", lambda: object())
    monkeypatch.setattr(
        sidecar.SkillRegistry, "load_default",
        lambda operations, encoder=None: sidecar.SkillRegistry([], operations, encoder),
    )

    def fail_dispatch_error(*_args):
        pytest.fail(traceback.format_exc())

    monkeypatch.setattr(sidecar, "technical_failure_message", fail_dispatch_error)
    lifecycle = SimpleNamespace(
        own_llm=lambda value: value,
        own_router=lambda value: value,
        own_planner_promotion=lambda _thread, stop: stop.set(),
    )
    request = {
        "type": "arguments", "id": "schedule-request", "operation": "notification.schedule",
        "text": "Set a reminder to pay the water bill.",
    }
    if language is not None:
        request["responseLanguage"] = language
    pending = iter([
        {
            "type": "catalog.configure", "id": "catalog",
            "capabilities": [{
                "name": "notification.schedule", "argumentsSchema": _SCHEDULE_SCHEMA,
                "risk": "low_reversible", "description": "Programa una alarma o un recordatorio local.",
            }],
        },
        request,
        None,
    ])
    replies: list[dict] = []
    assert sidecar._run_sidecar(
        lifecycle, read_message=lambda: next(pending), write_message=replies.append,
    ) == 0
    result = next(reply for reply in replies if reply.get("type") == "arguments.result")
    assert result["ok"] is False
    assert result["question"] == "Should it be an alarm or a reminder?"
    expected = {"response_language": language} if language else {}
    assert {k: v for k, v in calls["extract"].items() if k != "stated_fields"} == expected
    assert calls["formulate"] == expected
