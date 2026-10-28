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
    mind, server = _mind(tmp_path, [_say(f"Vale {n}.") for n in range(20)])  # never the last answer again (say_once)
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
    # «Sí.» after ten failures contradicts them (aid «answer_check»): the model is asked once more («No.»).
    mind, server = _mind(tmp_path, [*[_call("app_open", {"appId": f"App{i}"}) for i in range(calls)], _say("Listo."),
                                    _say("Sí."), _say("No.")])
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
    # «Sí.» over a call with no result is asked once more (aid «answer_check»): nothing completed that close.
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Paint"}), _say("Sí."), _say("No lo sé.")])
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
    # Renew al máximo (w5): the cut (at the fifth turn, past the characters) is one rewrite: the turns down to
    # TRIM_TURNS_TO of the count and every kept closed turn without its bodies; the next turns are only added.
    assert mind.trimmed_turns == 3
    assert len([m for m in mind.conversation if m.get("tool_calls")]) == 4
    results = [m["content"] for m in mind.conversation if m["role"] == "tool"]
    assert ["míralo de nuevo" in r for r in results] == [True] * 2 + [False] * 2
    assert "ids" in results[0] and "w3" not in results[0]
    # 8.2: a result with no typed verification is «sin verificar»; the line of the turn's facts stays as it was.
    assert "[En este turno: input_visible_controls → terminó sin verificar su efecto]" in results[0]
    assert "x" * 5000 in results[-1]
    # What the person asked in the turns cut, and how their calls ended, stay in the note of the cut.
    assert "«pedido 0» → input_visible_controls → terminó sin verificar su efecto" in mind.conversation[0]["content"]


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


def _big_result(tmp_path: Path, chars: int, prefix: int = 40000):
    """A turn whose one look returned `chars` characters (~chars/4 tokens with the fake tokenizer)."""
    from test_mind_final import _call, _mind, _say
    mind, server = _mind(tmp_path, [_call("input_visible_controls", {"application": "Paint"}), _say("Listo.")])
    mind.prefix_tokens = prefix
    mind.decide(1, "mira Paint")
    text = "".join(str(n % 10) for n in range(chars))
    observation = json.dumps({"status": "completed", "observed": {"text": text}})
    mind.continue_turn(2, observation)
    return mind, server, observation, text, _last_result(server)


def _last_result(server) -> str:
    return next(m["content"] for m in reversed(server.bodies[-1]["messages"]) if m.get("tool_call_id"))


def test_a_result_past_the_room_of_a_turn_reaches_the_model_cut_and_says_so(tmp_path: Path) -> None:
    # P0.10 (noche 27-10, NB-R1-X5): the mind had no bound per result and trusted the kernel's 8 KiB, but a process list
    # reaches 48,000 characters and some turn.continue re-read 10-12k tokens. A result past the room the history keeps
    # for one (RESULT_TOKENS) is cut by size before it is sent, never after a refusal, and the cut is said where the
    # model reads; its facts line stays whole after it.
    from baxy_mind.mind import CUT_RESULT, RESULT_TOKENS
    mind, server, observation, text, content = _big_result(tmp_path, 48000)
    assert len(server.bodies) == 2  # no refusal, no room made after it
    body, facts = content.split("\n[En este turno: ")
    kept, note = body.split(CUT_RESULT.split("{")[0])
    assert kept.startswith('{"observed":{"text":"' + text[:1000]) and text[:9000] in kept
    whole = len(kept) + int(note.split(" ")[0])
    assert note == CUT_RESULT.format(n=whole - len(kept), total=whole)[len(CUT_RESULT.split("{")[0]):]
    assert len(server.tokenize(body)) <= RESULT_TOKENS
    assert facts.startswith("input_visible_controls → ")
    # What the answer check reads is the result as it came.
    assert mind._turn["receipts"][-1]["observation"] == observation


def test_a_result_whose_tokens_cannot_be_counted_is_cut_by_characters_and_the_turn_goes_on(tmp_path: Path) -> None:
    # Review of P0.10: the call was already counted as done when the tokenizer failed, and the turn broke with the result
    # outside the conversation (the next decision then read it as never answered).
    from test_mind_final import _call, _mind, _say
    from baxy_mind.mind import CUT_RESULT, RESULT_TOKENS, TURN_FACTS
    mind, server = _mind(tmp_path, [_call("input_visible_controls", {"application": "Paint"}), _say("Listo.")])
    mind.prefix_tokens = 40000
    mind.decide(1, "mira Paint")
    server.tokenize = lambda text: (_ for _ in ()).throw(TimeoutError("budget spent"))
    assert mind.continue_turn(2, json.dumps({"status": "completed", "observed": {"text": "7" * 48000}}))["kind"]
    body = _last_result(server).split(TURN_FACTS)[0]
    assert CUT_RESULT.split("{")[0] in body and len(body) <= RESULT_TOKENS
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_bytes().splitlines()]
    assert any(row.get("stage") == "turn.result_cap" and row.get("error") == "TimeoutError" for row in rows)
    assert any(row.get("stage") == "turn.aid" and row.get("aids", {}).get("result_cap") for row in rows)


def test_a_result_within_the_room_of_a_turn_goes_whole(tmp_path: Path) -> None:
    from baxy_mind.mind import CUT_RESULT, RESULT_TOKENS
    _, _, _, text, content = _big_result(tmp_path, RESULT_TOKENS * 4 - 200)
    assert text + '"}}\n[En este turno: ' in content and CUT_RESULT.split("{")[0] not in content


def test_the_bound_per_result_is_an_aid_that_can_be_turned_off(tmp_path: Path, monkeypatch) -> None:
    from baxy_mind.mind import CUT_RESULT
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, server, observation, text, content = _big_result(tmp_path, 48000)
    assert text in content and CUT_RESULT.split("{")[0] not in content


# --- 9.2a: the notice is the model's words, not the code's (invariant 5: cero respuestas visibles fijas) ---------------
# Feria 2026-10-27: written once at warm-up it was the same phrase in every turn; the model writes it for the turn's call.

def _calling(tmp_path: Path, *notices):
    from test_mind_final import _call, _mind, _say
    replies = [_call("web_search", {"query": "vuelos a Lima"}), *[n if isinstance(n, Exception) else _say(n)
                                                                    for n in notices]]
    mind, server = _mind(tmp_path, replies)
    assert mind.decide(1, "busca vuelos a Lima")["kind"] == "action"
    return mind, server


def test_the_notice_is_written_by_the_model_for_the_call_the_app_runs(tmp_path: Path) -> None:
    from baxy_mind import mind as mind_module
    mind, server = _calling(tmp_path, "«Busco vuelos a Lima.»")
    decision = server.bodies[0]["messages"]
    assert not hasattr(mind_module, "NOTICE")  # no phrase of BAXY's is fixed in the code
    assert mind.notice_of() == "Busco vuelos a Lima."
    asked = server.bodies[1]
    # The turn as the model wrote it, the call still running, and words only: the token that opens a call cannot be
    # sampled; the conversation the turn goes on with is not changed.
    assert asked["messages"][:len(decision)] == decision
    assert asked["messages"][-2] == {"role": "tool", "tool_call_id": "c1", "content": mind_module.NOTICE_RUNNING}
    assert asked["tool_choice"] == "none" and asked["logit_bias"] == [[248058, False]]
    assert asked["temperature"] == 0.0 and asked["tools"] == server.bodies[0]["tools"]
    assert not any(m.get("content") == mind_module.NOTICE_RUNNING for m in mind.conversation)


def test_a_long_call_gets_another_notice_and_none_once_the_turn_answered(tmp_path: Path) -> None:
    # Al máximo, flujos: a call of 30 to 160 s said one notice and then nothing; each one now is other words.
    from test_mind_final import _say
    mind, server = _calling(tmp_path, "Busco vuelos a Lima.", "Sigo comparando horarios.")
    assert mind.notice_of() == "Busco vuelos a Lima."
    assert mind.notice_of() == "Sigo comparando horarios."
    server.replies.append(_say("Hay vuelos desde 200 dólares."))
    mind.continue_turn(2, json.dumps({"status": "completed", "results": []}))
    assert mind.notice_of() == ""
    assert len(server.bodies) == 4


def test_a_notice_already_said_in_the_turn_is_not_said_again(tmp_path: Path) -> None:
    from test_mind_final import _call, _say
    mind, server = _calling(tmp_path, "Busco vuelos a Lima.")
    assert mind.notice_of() == "Busco vuelos a Lima."
    server.replies += [_call("web_fetch", {"url": "https://example.org"}), _say("busco vuelos a lima")]
    assert mind.continue_turn(2, json.dumps({"status": "completed", "results": []}))["kind"] == "action"
    assert mind.notice_of() == ""
    assert "«Busco vuelos a Lima.»" in server.bodies[-1]["messages"][-1]["content"]  # told what it already said


# «Estoy procesando tu solicitud.» (holdout v5) was 1,81 s of audio the reply waited behind (fase 3, H7): a notice is a
# few words, one line, no markup.
@pytest.mark.parametrize("written", ["", "   ", "Ya abrí la aplicación que me pediste y todo quedó funcionando perfecto.",
                                     "Un momento.\nYa está.", "<tool_call>"])
def test_a_notice_the_model_did_not_write_usably_is_not_said(tmp_path: Path, written: str) -> None:
    mind, _ = _calling(tmp_path, written)
    assert mind.notice_of() == ""


def test_a_failed_notice_call_says_none_and_the_turn_goes_on(tmp_path: Path) -> None:
    from test_mind_final import _say
    mind, server = _calling(tmp_path, TimeoutError("slow"))
    assert mind.notice_of() == ""
    server.replies.append(_say("No encontré vuelos."))
    assert mind.continue_turn(2, json.dumps({"status": "completed", "results": []}))["reply"] == "No encontré vuelos."


def test_no_notice_is_written_with_no_turn_or_in_a_turn_kept_out_of_the_trace(tmp_path: Path) -> None:
    from test_mind_final import _call, _mind
    mind, server = _mind(tmp_path, [_call("memory_save", {"key": "clave", "value": "4321"})])
    mind.wire_to_op = {"memory_save": "memory.save"}
    assert mind.notice_of() == ""
    mind.decide(1, "guarda mi clave")
    assert mind.notice_of() == ""
    assert len(server.bodies) == 1
