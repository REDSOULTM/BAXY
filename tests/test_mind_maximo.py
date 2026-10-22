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


def test_only_the_decision_asks_the_server_for_its_token_probabilities(tmp_path: Path) -> None:
    # 9.5: every call asked for top_logprobs (the server sorts the vocabulary at every token), for a doubt read only in
    # turn.decide; a continuation and the last answer now go without them.
    from test_mind_final import _call, _mind, _say
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Paint"}), _call("app_open", {"appId": "Paint"}),
                                    _say("Abrí Paint.")])
    mind.decide(1, "abre paint")
    mind.continue_turn(2, json.dumps({"status": "completed"}))
    mind.continue_turn(3, json.dumps({"status": "completed"}), final=True)
    decide, follow, last = server.bodies
    assert decide["logprobs"] is True and decide["top_logprobs"] == 10
    assert not {"logprobs", "top_logprobs"} & (set(follow) | set(last))
    assert last["tool_choice"] == "none"
