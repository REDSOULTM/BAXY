"""Fase 3.5b M67: a content that is BAXY's previous reply is copied from it, never asked again.

FINAL F-w14-t3: «baxy escribeme un query de sql q me saque los users activos del ultimo mes» → a ```sql answer →
«ahora q salgan ordenados por fecha…» → the SQL again → «perfect, copialo al clipboard». The decider chose
clipboard.write.text («Copia al portapapeles el query de SQL de usuarios activos del último mes.»), but the argument
extraction read only that restatement and asked «¿Qué texto quieres copiar al portapapeles?». F-w15-t4 «save that as
a note porfa» after a packing list was asked for the content the same way. The extraction now reads BAXY's last reply
beside the request and says, in the same decode, whether it is the content; code copies it verbatim.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from baxy_mind import __main__ as sidecar  # noqa: E402
from baxy_mind.llm import (  # noqa: E402
    LlmRuntime,
    _build_direct_argument_payload,
    _single_fenced_code,
)
from baxy_mind.semantic import decider  # noqa: E402

_CLIPBOARD_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string", "maxLength": 65_536}},
    "required": ["text"],
    "additionalProperties": False,
}
_NOTE_SCHEMA = {
    "type": "object",
    "properties": {
        "content": {"type": "string", "x-maxUtf8Bytes": 65_536},
        "title": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
    },
    "required": ["content", "title"],
    "additionalProperties": False,
}
_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string", "x-maxUtf8Bytes": 1_024, "x-nonWhitespace": True}},
    "required": ["query"],
    "additionalProperties": False,
}
_DESCRIPTIONS = {
    "clipboard.write.text": "Reemplaza texto del portapapeles y verifica contenido y secuencia mediante postlectura.",
    "note.create": "Crea una nota privada local y verifica su relectura.",
    "web.search": "Busca en la web.",
}

_SQL_V1 = "SELECT *\nFROM users\nWHERE last_login >= NOW() - INTERVAL '1 month';"
_SQL_V2 = "SELECT *\nFROM users\nWHERE last_login >= NOW() - INTERVAL '1 month'\nORDER BY last_login DESC;"
_SQL_REPLY = f"Aquí lo tienes, ordenado por fecha:\n\n```sql\n{_SQL_V2}\n```\n\nEl más reciente sale primero."
_SQL_HISTORY = [
    {"role": "user", "content": "baxy escribeme un query de sql q me saque los users activos del ultimo mes"},
    {"role": "assistant", "content": f"```sql\n{_SQL_V1}\n```"},
    {"role": "user", "content": "ahora q salgan ordenados por fecha, los mas nuevos primero"},
    {"role": "assistant", "content": _SQL_REPLY},
    {"role": "user", "content": "perfect, copialo al clipboard"},
]
_SQL_OBJECTIVE = "Copia al portapapeles el query de SQL de usuarios activos del último mes."

_PACKING_REPLY = "Packing list for the beach:\n- Sunscreen\n- Towel\n- Swimsuit\n- Water bottle"
_PACKING_HISTORY = [
    {"role": "user", "content": "what should I pack for a beach day?"},
    {"role": "assistant", "content": _PACKING_REPLY},
    {"role": "user", "content": "save that as a note porfa"},
]
_NOTE_OBJECTIVE = "Save the beach packing list as a note."


def _tool(operation: str, schema: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": operation.replace(".", "_"),
            "canonical_name": operation,
            "description": _DESCRIPTIONS[operation],
            "parameters": json.loads(json.dumps(schema)),
        },
    }


def _reply(envelope: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(envelope, ensure_ascii=False)}}]}


def _runtime(envelope: dict) -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)
    runtime._post = MagicMock(return_value=_reply(envelope))
    return runtime


# ------------------------------------------------------------------ the one-call contract


def test_the_payload_offers_the_reply_only_to_a_field_that_holds_a_text_of_its_own() -> None:
    common = dict(
        text=_SQL_OBJECTIVE,
        canonical_name="clipboard.write.text",
        description=_DESCRIPTIONS["clipboard.write.text"],
        schema=_CLIPBOARD_SCHEMA,
        required_fields=("text",),
        open_string_fields=("text",),
    )
    offered = _build_direct_argument_payload(**common, previous_reply=_SQL_REPLY, previous_reply_fields=("text",))
    envelope = offered["response_format"]["json_schema"]["schema"]
    # The decision comes first in the decode, and the model is never made to write the reply.
    assert envelope["required"][:2] == ["previous_reply_field", "previous_reply_part"]
    assert envelope["properties"]["previous_reply_field"]["enum"] == ["none", "text"]
    assert envelope["properties"]["arguments"]["anyOf"][0]["required"] == []
    assert _SQL_V2 in offered["messages"][1]["content"] and offered["messages"][1]["content"].startswith(_SQL_OBJECTIVE)
    assert "previous_reply_field" in offered["messages"][0]["content"]
    # Without a reply the contract is the one before M67, byte for byte.
    plain = _build_direct_argument_payload(**common)
    assert set(plain["response_format"]["json_schema"]["schema"]["properties"]) == {
        "grounded", "arguments", "fallback_question",
    }
    assert plain["messages"][1]["content"] == _SQL_OBJECTIVE and plain["max_tokens"] == 192
    assert "previous_reply" not in plain["messages"][0]["content"]


def test_a_query_or_a_short_name_never_takes_the_reply() -> None:
    runtime = _runtime({"grounded": True, "arguments": {"query": "usuarios activos"}, "fallback_question": "¿Qué?"})
    runtime.extract_direct_arguments(
        "Busca usuarios activos", _tool("web.search", _SEARCH_SCHEMA), previous_reply=_SQL_REPLY,
    )
    payload = runtime._post.call_args.args[0]
    assert "previous_reply_field" not in payload["response_format"]["json_schema"]["schema"]["properties"]
    assert payload["messages"][1]["content"] == "Busca usuarios activos"


def test_the_code_of_the_one_block_is_what_a_code_copy_takes() -> None:
    assert _single_fenced_code(_SQL_REPLY) == _SQL_V2
    assert _single_fenced_code(_PACKING_REPLY) is None
    assert _single_fenced_code("```py\na\n```\ntexto\n```js\nb\n```") is None
    assert _single_fenced_code("```\n\n```") is None


def test_the_previous_reply_is_the_last_assistant_turn_before_the_current_message() -> None:
    assert sidecar._previous_reply(_SQL_HISTORY) == _SQL_REPLY
    assert sidecar._previous_reply(_SQL_HISTORY[:-1]) == _SQL_REPLY
    # The person spoke again after it: that reply is no longer the one right before.
    assert sidecar._previous_reply(_SQL_HISTORY[:3] + [_SQL_HISTORY[4]]) is None
    assert sidecar._previous_reply([{"role": "user", "content": "copia hola"}]) is None
    assert sidecar._previous_reply(None) is None


# ------------------------------------------------------------------ the extraction


def test_copy_the_sql_of_the_previous_reply_verbatim() -> None:
    runtime = _runtime({
        "previous_reply_field": "text", "previous_reply_part": "code",
        "grounded": True, "arguments": {}, "fallback_question": "¿Qué texto quieres copiar al portapapeles?",
    })
    extraction = runtime.extract_direct_arguments(
        _SQL_OBJECTIVE, _tool("clipboard.write.text", _CLIPBOARD_SCHEMA), previous_reply=_SQL_REPLY,
    )
    assert extraction.arguments == {"text": _SQL_V2}
    assert extraction.previous_reply_field == "text"
    assert extraction.fallback_question == ""


def test_a_model_that_writes_the_reply_anyway_still_gets_the_reply_itself() -> None:
    runtime = _runtime({
        "previous_reply_field": "text", "previous_reply_part": "whole",
        "grounded": True, "arguments": {"text": "SELECT * FROM users"}, "fallback_question": "¿Qué texto?",
    })
    extraction = runtime.extract_direct_arguments(
        _SQL_OBJECTIVE, _tool("clipboard.write.text", _CLIPBOARD_SCHEMA), previous_reply=_SQL_REPLY,
    )
    assert extraction.arguments == {"text": _SQL_REPLY}


def test_the_model_saying_none_leaves_the_extraction_as_before() -> None:
    envelope = {"grounded": False, "arguments": None, "fallback_question": "¿Qué texto quieres copiar al portapapeles?"}
    runtime = _runtime({"previous_reply_field": "none", "previous_reply_part": "whole", **envelope})
    extraction = runtime.extract_direct_arguments(
        _SQL_OBJECTIVE, _tool("clipboard.write.text", _CLIPBOARD_SCHEMA), previous_reply=_SQL_REPLY,
    )
    assert extraction.arguments is None and extraction.previous_reply_field == ""
    assert extraction.fallback_question == "¿Qué texto quieres copiar al portapapeles?"
    # A text the model copied from the reply while saying it is not the content is not grounded in the request.
    runtime = _runtime({
        "previous_reply_field": "none", "previous_reply_part": "whole",
        "grounded": True, "arguments": {"text": "ORDER BY last_login DESC;"}, "fallback_question": "¿Qué texto?",
    })
    extraction = runtime.extract_direct_arguments(
        _SQL_OBJECTIVE, _tool("clipboard.write.text", _CLIPBOARD_SCHEMA), previous_reply=_SQL_REPLY,
    )
    assert extraction.arguments is None


def test_a_note_takes_the_list_and_a_title_said_in_it() -> None:
    runtime = _runtime({
        "previous_reply_field": "content", "grounded": True,
        "arguments": {"title": "Packing list for the beach"}, "fallback_question": "What should the note say?",
    })
    extraction = runtime.extract_direct_arguments(
        _NOTE_OBJECTIVE, _tool("note.create", _NOTE_SCHEMA), previous_reply=_PACKING_REPLY,
    )
    assert extraction.arguments == {"content": _PACKING_REPLY, "title": "Packing list for the beach"}
    # A title nobody said is left out, for the caller to ask alone; the content stays.
    runtime = _runtime({
        "previous_reply_field": "content", "grounded": True,
        "arguments": {"title": "Summer trip essentials"}, "fallback_question": "What should the note say?",
    })
    extraction = runtime.extract_direct_arguments(
        _NOTE_OBJECTIVE, _tool("note.create", _NOTE_SCHEMA), previous_reply=_PACKING_REPLY,
    )
    assert extraction.arguments == {"content": _PACKING_REPLY}


def test_a_decided_text_at_the_decider_bound_was_cut() -> None:
    cut = _SQL_REPLY[: decider.ARGUMENT_VALUE_CHARACTERS]
    assert sidecar._decided_value(cut, {"type": "string"}) is None
    assert sidecar._decided_value("SELECT 1", {"type": "string"}) == "SELECT 1"
    assert decider.response_schema(["clipboard.write.text"], with_arguments=True)["anyOf"][0]["properties"][
        "arguments"
    ]["additionalProperties"]["maxLength"] == decider.ARGUMENT_VALUE_CHARACTERS


# ------------------------------------------------------------------ the arguments request, end to end in the mind


def _run_arguments(monkeypatch, runtime, operation: str, schema: dict, text: str, history: list[dict]) -> dict:
    for name in ("start_warmup", "begin_request", "end_request"):
        setattr(runtime, name, MagicMock(return_value=None))
    runtime.wait_warmup = MagicMock(return_value=True)
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "never-loaded.gguf")
    monkeypatch.setattr(sidecar, "LlmRuntime", lambda *_args, **_kwargs: runtime)
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
    pending = iter([
        {
            "type": "catalog.configure", "id": "catalog",
            "capabilities": [{
                "name": operation, "argumentsSchema": schema,
                "risk": "low_reversible", "description": _DESCRIPTIONS[operation],
            }],
        },
        {"type": "arguments", "id": "m67", "operation": operation, "text": text, "history": history},
        None,
    ])
    replies: list[dict] = []
    assert sidecar._run_sidecar(lifecycle, read_message=lambda: next(pending), write_message=replies.append) == 0
    return next(reply for reply in replies if reply.get("type") == "arguments.result")


def test_f_w14_t3_the_sql_goes_to_the_clipboard_without_a_question(monkeypatch) -> None:
    runtime = _runtime({
        "previous_reply_field": "text", "previous_reply_part": "code",
        "grounded": False, "arguments": None, "fallback_question": "¿Qué texto quieres copiar al portapapeles?",
    })
    runtime.formulate_missing_argument_question = MagicMock(side_effect=AssertionError("nothing is asked"))
    result = _run_arguments(
        monkeypatch, runtime, "clipboard.write.text", _CLIPBOARD_SCHEMA, _SQL_OBJECTIVE, _SQL_HISTORY,
    )
    assert result["ok"] is True and result["question"] == ""
    assert result["arguments"] == {"text": _SQL_V2}


def test_f_w15_t4_the_note_keeps_the_list_and_asks_only_for_a_title_nobody_said(monkeypatch) -> None:
    runtime = _runtime({
        "previous_reply_field": "content", "grounded": False, "arguments": None,
        "fallback_question": "What title and content should the note have?",
    })
    runtime.formulate_missing_argument_question = MagicMock(return_value="What should the note be called?")
    result = _run_arguments(monkeypatch, runtime, "note.create", _NOTE_SCHEMA, _NOTE_OBJECTIVE, _PACKING_HISTORY)
    assert result["ok"] is False and result["question"] == "What should the note be called?"
    assert runtime.formulate_missing_argument_question.call_args.args[3] == ("title",)


def test_the_note_is_created_from_the_list_with_its_own_heading(monkeypatch) -> None:
    runtime = _runtime({
        "previous_reply_field": "content", "grounded": True,
        "arguments": {"title": "Packing list for the beach"}, "fallback_question": "What should the note say?",
    })
    runtime.formulate_missing_argument_question = MagicMock(side_effect=AssertionError("nothing is asked"))
    result = _run_arguments(monkeypatch, runtime, "note.create", _NOTE_SCHEMA, _NOTE_OBJECTIVE, _PACKING_HISTORY)
    assert result["ok"] is True
    assert result["arguments"] == {"content": _PACKING_REPLY, "title": "Packing list for the beach"}


def test_without_a_previous_reply_the_content_is_still_asked(monkeypatch) -> None:
    runtime = _runtime({
        "grounded": False, "arguments": None, "fallback_question": "¿Qué texto quieres copiar al portapapeles?",
    })
    result = _run_arguments(
        monkeypatch, runtime, "clipboard.write.text", _CLIPBOARD_SCHEMA, "Copia algo al portapapeles.",
        [{"role": "user", "content": "copia algo al portapapeles"}],
    )
    assert result["ok"] is False and result["question"] == "¿Qué texto quieres copiar al portapapeles?"
    payload = runtime._post.call_args_list[0].args[0]
    assert "previous_reply_field" not in payload["response_format"]["json_schema"]["schema"]["properties"]
    # M150: before asking, the decider read the turn (here its reply is no decision, so the question stands).
    decider = runtime._post.call_args_list[-1].args[0]
    assert decider["response_format"]["json_schema"]["name"] == "baxy_context_decision"


def test_the_model_saying_none_still_asks(monkeypatch) -> None:
    runtime = _runtime({
        "previous_reply_field": "none", "previous_reply_part": "whole",
        "grounded": False, "arguments": None, "fallback_question": "¿Qué texto quieres copiar al portapapeles?",
    })
    result = _run_arguments(
        monkeypatch, runtime, "clipboard.write.text", _CLIPBOARD_SCHEMA, _SQL_OBJECTIVE, _SQL_HISTORY,
    )
    assert result["ok"] is False and result["question"] == "¿Qué texto quieres copiar al portapapeles?"


def test_m67b_a_short_restatement_from_the_decider_never_replaces_the_previous_reply(monkeypatch) -> None:
    # M67b: the decider may restate the content («el query de SQL de usuarios activos») within its bound; that text
    # grounds in its own request, so alone it would be copied instead of the query. With a reply that can be the
    # content, the extraction, which reads the reply, decides.
    monkeypatch.setattr(sidecar, "_DECIDED_ARGUMENTS", {})
    sidecar._remember_decided_arguments(
        _SQL_OBJECTIVE, ("clipboard.write.text",), (("text", "el query de SQL de usuarios activos del último mes"),),
    )
    runtime = _runtime({
        "previous_reply_field": "text", "previous_reply_part": "code",
        "grounded": False, "arguments": None, "fallback_question": "¿Qué texto quieres copiar al portapapeles?",
    })
    runtime.formulate_missing_argument_question = MagicMock(side_effect=AssertionError("nothing is asked"))
    result = _run_arguments(
        monkeypatch, runtime, "clipboard.write.text", _CLIPBOARD_SCHEMA, _SQL_OBJECTIVE, _SQL_HISTORY,
    )
    assert result["ok"] is True and result["arguments"] == {"text": _SQL_V2}


def test_m67b_without_a_previous_reply_the_decider_values_still_settle_the_arguments() -> None:
    tool = _tool("clipboard.write.text", _CLIPBOARD_SCHEMA)
    assert sidecar._previous_reply_may_be_content(tool, _SQL_HISTORY) is True
    assert sidecar._previous_reply_may_be_content(tool, [{"role": "user", "content": "copia hola"}]) is False
    assert sidecar._previous_reply_may_be_content(_tool("web.search", _SEARCH_SCHEMA), _SQL_HISTORY) is False
