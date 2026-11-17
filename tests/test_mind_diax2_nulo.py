"""DIAX2 (casos del dueño 16-11, F11 y F12): Qwen3.5's template writes a call's top-level value with Jinja's «| string»,
so a null the model wrote («<parameter=consequence>\\nnull\\n») comes back in the next request as Python's «None». The
model reads its own call back with «None» and writes it so in the calls after it; llama-server reads «None» as the text
"None", and input_visible_click refused each one (invalid_arguments, «expected one of the allowed values or null»): on the
owner's PC 9 of 9 clicks after the first null of the conversation, «No guardar» of Word's dialog among them. Given as
the text «null» the template writes it as it came, as aid «calls_as_written» already does for a boolean."""
import json
from pathlib import Path

import pytest

from baxy_mind import call_format
from baxy_mind.mind import _as_written
from plantillas_llamada import gemma4, llama32, qwen35
from test_mind_prefill import _call, _mind, _say

CLICK = {"type": "function", "function": {"name": "input_visible_click", "description": "Click a visible control.",
                                          "parameters": {"type": "object", "properties": {
                                              "consequence": {"type": ["string", "null"],
                                                              "enum": ["irreversible", "overwrite", None]},
                                              "label": {"type": "string"},
                                              "index": {"type": ["integer", "null"]}},
                                              "required": ["consequence", "label"]}}}


def test_the_probes_tell_a_template_that_writes_null_as_none() -> None:
    assert call_format.derive(qwen35).nulls_as_text is True
    assert call_format.CALIBRATED.nulls_as_text is True
    assert call_format.derive(llama32).nulls_as_text is False  # tojson: «null»
    assert call_format.derive(gemma4).nulls_as_text is False


def test_a_top_level_null_is_written_as_the_text_null_and_nothing_else_changes() -> None:
    arguments = {"consequence": None, "label": "No guardar", "items": [None], "options": {"x": None}, "n": 0}
    messages = [{"role": "assistant", "content": "", "tool_calls": [
        {"id": "a", "type": "function", "function": {"name": "input_visible_click",
                                                     "arguments": json.dumps(arguments)}}]}]
    shown = _as_written(messages)
    assert json.loads(shown[0]["tool_calls"][0]["function"]["arguments"]) == {**arguments, "consequence": "null"}
    assert json.loads(messages[0]["tool_calls"][0]["function"]["arguments"]) == arguments  # the input is not changed
    # Only booleans for a template that writes «None» as it came (none known; the flag says it).
    kept = _as_written(messages, nulls=False)
    assert kept[0]["tool_calls"][0] is messages[0]["tool_calls"][0]


@pytest.mark.parametrize("setting", ["all", "calls_as_written", "none"])
def test_the_next_request_shows_the_null_the_model_wrote_not_none(tmp_path: Path, monkeypatch,
                                                                  setting: str) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server = _mind(tmp_path, [_call("input_visible_click", {"consequence": None, "label": "Documento en blanco"}),
                                    _say("Listo, abrí un documento en blanco.")], monkeypatch)
    mind.tools = [CLICK]
    mind.decide(1, "abre un documento en blanco")
    held = server.slot
    assert "<parameter=consequence>\nnull\n</parameter>" in held  # as the model wrote it
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "readback"}))
    after = server.prompts[-1]
    if setting == "none":  # as before: the template rewrote it, and the model reads «None» back
        assert "<parameter=consequence>\nNone\n</parameter>" in after
    else:
        assert "<parameter=consequence>\nnull\n</parameter>" in after and "None" not in after
        assert after.startswith(held)  # and the slot reads on from what it held
    call = next(m for m in mind.export_session() if m.get("tool_calls"))["tool_calls"][0]
    assert json.loads(call["function"]["arguments"]) == {"consequence": None, "label": "Documento en blanco"}
