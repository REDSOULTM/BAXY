"""Latency of a turn after a tool (w6-lat, 2026-10-23): on the holdout v4 the first spoken answer after a tool went 3.4 →
4.3 s p50, turn.continue reading 124 → 156 tokens and re-reading the call it had just written. What the model reads is
shorter or read once; what BAXY decides on it is never changed here."""
import json
import pathlib

import pytest

from test_mind_aids import _trace
from test_mind_final import _call, _mind, _say


def _results(server) -> list[str]:
    """The tool messages of the last request, as the model read them."""
    return [message["content"] for message in server.bodies[-1]["messages"] if message.get("role") == "tool"]


# Aid «result_dedup» (w6-lat, 2026-10-23): turn.continue read 124 → 156 tokens on the holdout v4; what the facts line
# says of a result is not said in it again.
OPENED_AT = json.dumps({"status": "completed", "verification": "readback",
                        "observed": {"appId": "Spotify", "alreadyRunning": True, "windowId": "win_1"}},
                       separators=(",", ":"))
WRITTEN = json.dumps({"status": "completed", "verification": "readback",
                      "observed": {"name": "compras.txt", "fullPath": r"C:\Users\ana\compras.txt", "size": 19}},
                     separators=(",", ":"))


@pytest.mark.parametrize("setting", ["all", "result_dedup", "none", "short_refs"])
def test_what_the_facts_line_says_of_a_result_is_not_said_in_it_again(tmp_path: pathlib.Path, monkeypatch,
                                                                       setting: str) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Spotify"}), _call("file_write", {"name": "compras.txt"}),
                                    _say("Listo.")])
    mind.decide(1, "abre spotify y guarda la lista")
    mind.continue_turn(2, OPENED_AT)
    mind.continue_turn(3, WRITTEN)
    tools = _results(server)
    if setting in ("all", "result_dedup"):
        assert tools[0] == ('{"observed":{"appId":"Spotify","windowId":"win_1"}}\n[En este turno: app_open → '
                            'completado y verificado; ya estaba abierta antes de esta llamada]')
        assert tools[1].startswith('{"observed":{"name":"compras.txt","size":19}}\n[En este turno: ')
    else:  # the mind as it was before it: the result as the App wrote it
        assert tools[0].startswith(OPENED_AT + "\n[En este turno: ")
        assert tools[1].startswith(WRITTEN + "\n[En este turno: ")
    # The line is the same either way, so every fact left out of the result is still there, once.
    assert tools[1].endswith(r"file_write → completado y verificado en C:\Users\ana\compras.txt]")
    assert not [r for r in _trace(mind) if r["stage"] == "turn.aid"]


@pytest.mark.parametrize("facts,kept", [
    # Nothing of these is in their line: they come as the App wrote them.
    ({"status": "needs_confirmation", "next": "nothing ran"}, None),
    ({"status": "failed", "error": "window_not_found", "observed": {"fullPath": r"C:\x"}}, None),
    ({"status": "completed", "replayed": True, "verification": "readback"}, None),
    ({"status": "completed", "effectUncertain": True, "verification": "readback"}, None),
    # An application BAXY started: the line does not say so, so alreadyRunning false stays.
    ({"status": "completed", "verification": "readback", "observed": {"alreadyRunning": False}},
     {"observed": {"alreadyRunning": False}}),
    ({"status": "completed", "verification": "delivered_only", "observed": {"after": {"changed": [{"index": 3}]}}},
     {"observed": {"after": {"changed": [{"index": 3}]}}}),
    ({"status": "completed", "verification": "delivered_only", "observed": {"after": {"same": True}}}, {}),
    ({"status": "failed", "error": "window_state_not_verified",
      "observed": {"stateAfter": {"state": "minimized", "requestedStateReached": True, "authority": "win32"}}},
     {"status": "failed", "error": "window_state_not_verified",
      "observed": {"stateAfter": {"state": "minimized", "authority": "win32"}}}),
    ({"status": "completed", "verification": "none", "error": "result_unreadable"}, {"error": "result_unreadable"}),
])
def test_a_field_leaves_the_result_only_where_its_line_says_it(facts: dict, kept: dict | None) -> None:
    from baxy_mind.mind import _deduplicated, _outcome
    observation = json.dumps(facts, separators=(",", ":"))
    line = _outcome(observation)
    shown = _deduplicated(observation, line)
    assert shown == (observation if kept is None else json.dumps(kept, separators=(",", ":")))
    # Whatever left the result is in the line written from the whole result.
    assert _outcome(observation) == line


def test_a_shortened_address_keeps_the_result_compact_with_the_dedup_on(tmp_path: pathlib.Path, monkeypatch) -> None:
    long_url = "https://example.org/" + "a" * 150
    page = json.dumps({"status": "completed", "verification": "output_only",
                       "observed": {"finalUrl": long_url, "title": "x"}}, separators=(",", ":"))
    for setting, expected in (("all", '{"observed":{"finalUrl":"ref:r1","title":"x"}}'),
                              ("short_refs", '{"status": "completed", "verification": "output_only", "observed": '
                                             '{"finalUrl": "ref:r1", "title": "x"}}')):
        monkeypatch.setenv("BAXY_AYUDAS", setting)
        mind, server = _mind(tmp_path, [_call("web_fetch", {"url": "https://example.org"}), _say("Listo.")])
        mind.decide(1, "lee la página")
        mind.continue_turn(2, page)
        tool = _results(server)[-1]
        assert tool.startswith(expected + "\n[En este turno: ")


# Aid «calls_as_written» (w6-lat): the call's booleans as the model wrote them, so the request after it starts with what
# the slot holds (the prompt and the call as written) and reads only the result.
@pytest.mark.parametrize("setting", ["all", "calls_as_written", "none", "result_dedup"])
def test_the_request_after_a_call_starts_with_the_call_as_the_model_wrote_it(tmp_path: pathlib.Path, monkeypatch,
                                                                             setting: str) -> None:
    from test_mind_prefill import _call as _slot_call
    from test_mind_prefill import _mind as _slot_mind
    from test_mind_prefill import _say as _slot_say
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server = _slot_mind(tmp_path, [_slot_call("app_open", {"appId": "Paint", "foreground": True}),
                                         _slot_say("Abrí Paint.")], monkeypatch)
    mind.decide(1, "abre paint")
    held = server.slot  # the decision's prompt and the call as the model wrote it («foreground» true)
    assert "<parameter=foreground>\ntrue\n</parameter>" in held
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "readback",
                                      "observed": {"appId": "Paint"}}))
    after = server.prompts[-1]
    if setting in ("all", "calls_as_written"):
        assert after.startswith(held)
        assert server.read[-1] == len(after) - len(held)  # only the result and what follows it
    else:  # as before: from the value the template rewrote on, read again
        assert not after.startswith(held) and "<parameter=foreground>\nTrue\n</parameter>" in after
        assert server.read[-1] > len(after) - len(held)
    # The conversation keeps the call as it was: only the request is written so.
    call = next(m for m in mind.export_session() if m.get("tool_calls"))["tool_calls"][0]
    assert json.loads(call["function"]["arguments"]) == {"appId": "Paint", "foreground": True}


def test_only_top_level_booleans_are_written_as_text() -> None:
    from baxy_mind.mind import _as_written
    nested = {"appId": "Paint", "n": 3, "x": 0.5, "items": [True], "options": {"on": False}, "foreground": False}
    messages = [{"role": "user", "content": "true"},
                {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "a", "type": "function", "function": {"name": "app_open", "arguments": json.dumps(nested)}},
                    {"id": "b", "type": "function", "function": {"name": "ask_user",
                                                                  "arguments": json.dumps({"question": "¿cuál?"})}}]},
                {"role": "tool", "tool_call_id": "a", "content": '{"ok":true}'}]
    shown = _as_written(messages)
    assert json.loads(shown[1]["tool_calls"][0]["function"]["arguments"]) == {**nested, "foreground": "false"}
    assert shown[1]["tool_calls"][1] is messages[1]["tool_calls"][1]  # nothing to write otherwise: as it was
    assert shown[0] is messages[0] and shown[2] is messages[2]
    assert json.loads(messages[1]["tool_calls"][0]["function"]["arguments"]) == nested  # the input is not changed


# The KV cache's types (w6-lat 5): an option for an A/B, never the default.
@pytest.mark.parametrize("setting,types", [("", ("q8_0", "q8_0")), ("q4_0", ("q4_0", "q4_0")),
                                           (" Q8_0 , q4_0 ", ("q8_0", "q4_0"))])
def test_the_kv_cache_is_q8_0_unless_baxy_renew_kv_says_otherwise(tmp_path: pathlib.Path, monkeypatch, setting: str,
                                                                    types: tuple[str, str]) -> None:
    from baxy_mind import llm_server
    launched: list[list[str]] = []

    class Process:
        def __init__(self, command, **kwargs) -> None:
            launched.append(command)

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAXY_RENEW_KV", setting)
    monkeypatch.setattr(llm_server.subprocess, "Popen", Process)
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **kwargs: type("T", (), {"start": lambda self: None})())
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server.start()
    command = launched[0]
    assert (command[command.index("-ctk") + 1], command[command.index("-ctv") + 1]) == types
    # The types are among the server's settings, and so in the kept prefix's key (prefix_key): another type, another
    # prefix, never a state of the other types restored.
    assert "-ctk" in server._settings and types[0] in server._settings


@pytest.mark.parametrize("setting", ["q3_k", "q8_0,q4_0,f16", "turbo"])
def test_a_kv_type_llama_server_does_not_take_fails_the_start_with_its_cause(monkeypatch, setting: str) -> None:
    from baxy_mind import llm_server
    monkeypatch.setenv("BAXY_RENEW_KV", setting)
    with pytest.raises(RuntimeError, match="BAXY_RENEW_KV"):
        llm_server.LlmServer("model.gguf", "llama-server.exe")
