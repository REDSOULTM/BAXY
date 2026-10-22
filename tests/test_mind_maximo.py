"""BAXY Renew al máximo, tanda 1 (artifacts/renew/maximo/MAXIMO.md): resources and latency without changing decisions.
Each test holds one lever, so it can be measured and withdrawn on its own."""
import json
from pathlib import Path

import pytest


def test_the_model_server_keeps_no_prompt_cache_in_ram_and_ten_checkpoints(tmp_path: Path, monkeypatch) -> None:
    # 3.3: the cache in RAM held nothing (no prompt fit its 1,536 MiB) and 32 checkpoints cost ~1.6 GB of RAM.
    from baxy_mind import llm_server
    launched: list[list[str]] = []

    class Process:
        def __init__(self, command, **kwargs) -> None:
            launched.append(command)

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(llm_server.subprocess, "Popen", Process)
    monkeypatch.setattr(llm_server.threading, "Thread", lambda **kwargs: type("T", (), {"start": lambda self: None})())
    llm_server.LlmServer("model.gguf", "llama-server.exe").start()
    command = launched[0]
    assert command[command.index("-cram") + 1] == "0"
    assert command[command.index("-ctxcp") + 1] == "10"
    assert "-cms" not in command and "--checkpoint-min-step" not in command


CATALOG = ("system_power", "app_open", "app_close", "app_snap", "window_resolve", "window_snap")


def _doubted(name_tokens: list[str], weakest: int, rivals: list[tuple[str, float]]) -> dict:
    """A reply that calls the tool spelled by `name_tokens`, unsure (p 0.5) at its `weakest` token, with those rivals."""
    import math
    from test_mind_doubt_policy import _token
    tokens = [_token(t, 0.5 if i == weakest else 1.0) for i, t in enumerate(name_tokens)]
    tokens[weakest]["top_logprobs"] += [{"token": t, "logprob": math.log(q)} for t, q in rivals]
    head = [_token("<tool_call>", 0.95), _token("\n", 1.0), _token("<", 1.0), _token("function", 1.0)]
    name = "".join(name_tokens).lstrip("=")
    return {"choices": [{"message": {"content": "", "tool_calls": [{"id": "c1", "function": {
        "name": name, "arguments": "{}"}}]}, "logprobs": {"content": [*head, *tokens, _token(">", 1.0)]}}]}


@pytest.mark.parametrize("name_tokens, weakest, rivals, expected", [
    # The first token of the name: every tool «app» begins counts, in the catalog's order, within the four places.
    (["=", "system", "_power"], 1, [("app", 0.3), ("window", 0.1)], ["system_power", "app_open", "app_close", "app_snap"]),
    # A later token: one tool each; a token that begins no tool, one under p 0.01 and the chosen tool again do not count.
    (["=", "window", "_resolve"], 2, [("_snap", 0.2), ("_foo", 0.1), ("_res", 0.05), ("_open", 0.005)],
     ["window_resolve", "window_snap"]),
    # A token that carries the «=» of «<function=»; one that writes nothing of the name, or leaves the «=» out, is none.
    (["=app", "_close"], 0, [("=window", 0.2), ("=", 0.1), ("app", 0.05)], ["app_close", "window_resolve", "window_snap"]),
    # A token that closes the name: only that very name.
    (["=", "app", "_snap"], 2, [("_open>", 0.1), ("_s>", 0.05)], ["app_snap", "app_open"]),
])
def test_the_doubts_candidates_come_from_the_catalog_without_asking_the_server(tmp_path: Path, monkeypatch, name_tokens,
                                                                               weakest, rivals, expected) -> None:
    # 4.1: per rival, the chat's prompt was applied again and the name completed (/apply-template, /completion): ~0.8 s
    # per doubtful turn. The fake server only answers chat: any other call would leave its rival out.
    from baxy_mind.mind import Mind
    from test_mind_doubt_policy import FakeServer, FakeSystemOne
    monkeypatch.setenv("BAXY_S1_DOUBT", "")
    monkeypatch.setenv("BAXY_S1_VETO", "0.9")
    reply = _doubted(name_tokens, weakest, rivals)
    chosen = reply["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
    server = FakeServer([reply])
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.call_tokens = [248058]
    mind.tools = [{"type": "function", "function": {"name": n, "description": "Tool. More.", "parameters": {}}}
                  for n in CATALOG]
    mind.wire_to_op = {n: n.replace("_", ".") for n in CATALOG}
    one = FakeSystemOne(chosen)
    mind.system_one = one  # type: ignore[assignment]
    assert mind.decide(1, "hazlo")["kind"] == "action"
    assert [o for o in one.asked[0]["options"] if o in CATALOG] == expected
    assert len(server.bodies) == 1


@pytest.mark.parametrize("bound", ["tokens", "turns"])
def test_a_cut_history_keeps_room_so_the_next_turns_do_not_move_its_start(tmp_path: Path, monkeypatch, bound) -> None:
    # 1.4: cut just under its bound, a full session cut a turn at every new one and re-read its whole history each time.
    # 1.3: each check sent the whole history to /tokenize; now only the turns not counted yet.
    from baxy_mind import mind as mind_module
    from baxy_mind.mind import TRIM_TO, TURN_ROOM_TOKENS
    from test_mind_final import _mind, _say
    mind, server = _mind(tmp_path, [_say("Vale.") for _ in range(20)])
    counted: list[str] = []
    server.tokenize = lambda text: counted.append(text) or [0] * (len(text) // 4)
    room = 1500  # tokens; a turn here is ~160
    if bound == "tokens":
        monkeypatch.setattr(mind_module, "HISTORY_TURNS", 100)
        mind.prefix_tokens = server.context - TURN_ROOM_TOKENS - room
    turn = 0
    while not mind.trimmed_turns:
        turn += 1
        mind.decide(turn, f"pedido {turn}: " + "palabra " * 40)
    # What the cut kept: from the first clock it left to the request (the note of the cut and the reply come after).
    history = "".join(json.dumps(m, ensure_ascii=False) for m in mind.conversation[1:-1])
    assert len(mind._turn_starts()) <= mind_module.HISTORY_TURNS * TRIM_TO
    assert bound == "turns" or len(history) // 4 <= room * TRIM_TO
    first, cut = json.dumps(mind.conversation[:2], ensure_ascii=False), mind.trimmed_turns
    for later in range(turn + 1, turn + 4):
        counted.clear()
        mind.decide(later, f"pedido {later}: " + "palabra " * 40)
        assert mind.trimmed_turns == cut and json.dumps(mind.conversation[:2], ensure_ascii=False) == first
        # Counted again: the new turn, the one before (its reply came after it was counted) and, after a cut, the
        # first one (the note of the cut went into it); never the turns between.
        assert all(f"pedido {later}:" in text or f"pedido {later - 1}:" in text or "[Conversación recortada" in text
                   for text in counted)
