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


def _clocks(server) -> list[str]:
    return [m["content"] for m in server.bodies[-1]["messages"] if str(m.get("content") or "").startswith("[Reloj:")]


def test_the_clock_says_which_calls_ran_in_the_session_even_after_a_cut(tmp_path: Path, monkeypatch) -> None:
    # 8.1 (F015: «¿ya lo cerraste?» → «Sí» with nothing run): the session's calls and how they ended, from a count of
    # the session's own; a cut history no longer shows them, and a «none» read from it would be false.
    from baxy_mind import mind as mind_module
    from test_mind_final import _call, _mind, _say
    monkeypatch.setattr(mind_module, "HISTORY_TURNS", 1)
    mind, server = _mind(tmp_path, [_say("Hola."), _call("app_open", {"appId": "Paint"}), _say("Abrí Paint."),
                                    _say("Sí."), _say("Vale.")])
    mind.decide(1, "hola")
    assert _clocks(server)[-1].endswith("llamadas a herramientas en esta sesión: ninguna]")
    mind.decide(2, "abre paint")
    mind.continue_turn(3, json.dumps({"status": "completed", "verification": "readback"}))
    mind.decide(4, "¿ya lo abriste?")
    assert mind.trimmed_turns and len(_clocks(server)) == 1
    assert _clocks(server)[-1].endswith("llamadas a herramientas en esta sesión: 1 (app_open → completado y verificado)]")
    kept = mind.export_session()
    mind.load_session(kept)
    mind.decide(5, "gracias")
    assert "en esta sesión: 1 (app_open → completado y verificado)" in _clocks(server)[-1]


def test_the_clock_lists_only_the_last_calls_of_a_long_session(tmp_path: Path) -> None:
    from baxy_mind.mind import SESSION_CALLS
    from test_mind_final import _call, _mind, _say
    calls = SESSION_CALLS + 2
    mind, server = _mind(tmp_path, [*[_call("app_open", {"appId": f"App{i}"}) for i in range(calls)], _say("Listo."),
                                    _say("Sí.")])
    mind.decide(1, "abre todas")
    for i in range(calls):
        mind.continue_turn(2 + i, json.dumps({"status": "failed", "error": f"e{i}"}), final=i == calls - 1)
    mind.decide(99, "¿las abriste?")
    clock = _clocks(server)[-1]
    assert f"en esta sesión: {calls}, las {SESSION_CALLS} últimas (app_open → falló (e2) / " in clock
    assert "(e1)" not in clock and "falló (e9))]" in clock
    mind.new_session()
    mind.server.replies.append(_say("Hola."))
    mind.decide(100, "hola")
    assert _clocks(server)[-1].endswith("en esta sesión: ninguna]")


def test_a_session_kept_before_the_count_says_how_many_calls_it_shows(tmp_path: Path) -> None:
    from test_mind_final import _call, _mind, _say
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Paint"}), _say("Abrí Paint."), _say("Sí.")])
    mind.decide(1, "abre paint")
    mind.continue_turn(2, json.dumps({"status": "completed"}))
    kept = [m for m in mind.export_session() if m.get("role") != "baxy.session"]
    mind.load_session(kept)
    mind.decide(3, "¿lo abriste?")
    assert _clocks(server)[-1].endswith("llamadas a herramientas en esta sesión: 1]")


def test_a_call_whose_result_never_came_is_in_the_session_calls(tmp_path: Path) -> None:
    # 8.1: the turn ended while the call ran; it may have run, so the clock never says that none did.
    from test_mind_final import _call, _mind, _say
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Paint"}), _say("Sí.")])
    mind.decide(1, "cierra paint")
    mind.decide(2, "¿ya lo cerraste?")
    assert _clocks(server)[-1].endswith("en esta sesión: 1 (app_close → sin resultado: pudo o no ocurrir)]")


def test_a_full_history_leaves_out_its_oldest_results_before_it_drops_turns(tmp_path: Path) -> None:
    # 1.1: past its bound the history dropped whole turns (about three were left); the bodies of the oldest results go
    # first now, while their calls and the line of each turn's facts stay, and what is left out says its ids are gone.
    from test_mind_final import _call, _mind, _say
    mind, _ = _mind(tmp_path, [_call("input_visible_controls", {"application": "Paint"}), _say("Listo.")] * 7)
    for turn in range(7):
        mind.decide(turn, f"pedido {turn}")
        mind.continue_turn(turn, json.dumps({"status": "completed", "observed": {"windowId": f"w{turn}",
                                                                                "text": "x" * 5000}}))
    assert mind.trimmed_turns == 0
    assert len([m for m in mind.conversation if m.get("tool_calls")]) == 7
    results = [m["content"] for m in mind.conversation if m["role"] == "tool"]
    # Cut down to TRIM_TO of its characters, as a cut is: the next turns leave the oldest results as they were. Four,
    # not three: since 8.1 each clock also lists the session's calls, so each turn here grows ~50 characters per call.
    assert ["míralo de nuevo" in r for r in results] == [True] * 4 + [False] * 3
    assert "ids" in results[0] and "w0" not in results[0]
    # 8.2: a result with no typed verification is «sin verificar»; the line of the turn's facts stays as it was.
    assert "[En este turno: input_visible_controls → terminó sin verificar su efecto]" in results[0]
    assert "x" * 5000 in results[-1]


def test_a_turn_past_the_context_makes_room_in_its_history_before_it_ends(tmp_path: Path) -> None:
    # 1.2: a turn whose results outgrew the context cut them and answered in words at once (15 context_shrunk in the
    # trace, each one ended its mission). The turns before it give room first (their results, then themselves), then its
    # own earlier results; the newest stays whole and the model goes on with its tools.
    from test_mind_final import _call, _mind, _overflow, _say
    look = _call("input_visible_controls", {"application": "Paint"})
    mind, server = _mind(tmp_path, [look, _say("Listo.")] * 3 + [look] * 7)
    chat = server.chat
    server.chat = lambda body: (_ for _ in ()).throw(_overflow()) \
        if len(json.dumps(body["messages"][1:], ensure_ascii=False)) > 22000 else chat(body)

    def seen(n: int) -> str:
        return json.dumps({"status": "completed", "observed": {"windowId": f"w{n}", "text": str(n % 10) * 4000}})

    for turn in range(3):
        mind.decide(turn, f"pedido {turn}")
        mind.continue_turn(turn, seen(turn))
    assert mind.decide(3, "mira Paint otra vez")["kind"] == "action"
    for step in range(3, 9):
        assert mind.continue_turn(step, seen(step))["kind"] == "action"
    assert not any("tool_choice" in body for body in server.bodies)
    assert mind.trimmed_turns == 3
    assert len([m for m in mind.conversation if m.get("tool_calls")]) == 7
    results = [m["content"] for m in server.bodies[-1]["messages"] if m["role"] == "tool"]
    # The earlier turns' results went at the second result, the turns themselves at the fifth, and only then the turn's
    # own results but the newest; the one after them came in whole.
    assert ["míralo de nuevo" in r for r in results] == [True] * 4 + [False] * 2
    assert "8" * 4000 in results[-1]


# --- 9.2a: the notice is the model's words, not the code's (invariant 5: cero respuestas visibles fijas) ---------------

def _warm_mind(tmp_path: Path, notice_reply):
    from test_mind_final import FakeServer, _say
    from baxy_mind.mind import Mind

    class Server(FakeServer):
        def chat(self, body: dict, timeout: float = 120.0) -> dict:
            return super().chat(body)

        def tokenize(self, text: str) -> list[int]:
            return [248058] if text == "<tool_call>" else super().tokenize(text)

        def prefix_key(self, warm) -> str:
            return "key"

        def restore_prefix(self, key: str) -> None:
            return None  # no prefix kept: the warm-up runs (al máximo V1, test_maximo_velocidad)

        def save_prefix(self, key: str, facts: dict) -> bool:
            return True

    replies = [{"choices": [{"message": {"content": "H"}}], "usage": {"prompt_tokens": 37000}},
               notice_reply if isinstance(notice_reply, Exception) else _say(notice_reply)]
    server = Server(replies)
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.tools = [{"type": "function", "function": {"name": "app_open", "parameters": {}}}]
    mind.warm()
    return mind, server


def test_the_notice_is_written_by_the_model_once_at_warm_up(tmp_path: Path) -> None:
    from baxy_mind import mind as mind_module
    mind, server = _warm_mind(tmp_path, "«Dame un segundo.»")
    assert not hasattr(mind_module, "NOTICE")  # no phrase of BAXY's is fixed in the code
    assert mind.notice == "Dame un segundo."
    assert mind.prefix_tokens == 37000
    warm, notice = server.bodies
    # The same cached prefix (system prompt and tools) and words only: the token that opens a call cannot be sampled.
    assert notice["messages"][0] == warm["messages"][0] and notice["tools"] == warm["tools"]
    assert notice["tool_choice"] == "none" and notice["logit_bias"] == [[248058, False]]
    assert notice["temperature"] == 0.0 and notice["max_tokens"] <= 32


@pytest.mark.parametrize("written", ["", "   ", "Ya abrí la aplicación que me pediste y todo quedó funcionando perfecto.",
                                     "Un momento.\nYa está.", "<tool_call>"])
def test_a_notice_the_model_did_not_write_usably_goes_empty(tmp_path: Path, written: str) -> None:
    mind, _ = _warm_mind(tmp_path, written)
    assert mind.notice == ""


def test_a_failed_notice_call_leaves_the_notice_empty_and_the_warm_up_done(tmp_path: Path) -> None:
    mind, _ = _warm_mind(tmp_path, TimeoutError("slow"))
    assert mind.notice == "" and mind.prefix_tokens == 37000
