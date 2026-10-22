"""BAXY Renew al máximo, velocidad (2026-10-22): the overhead BAXY adds to the model's own time, lever by lever."""
import json
import time
import types
from pathlib import Path

import pytest

from test_mind_final import _mind, _say


def _clock(step: float) -> types.SimpleNamespace:
    """A time module whose perf_counter moves `step` seconds per reading (the others are the real ones)."""
    ticks = iter(range(10_000))
    return types.SimpleNamespace(perf_counter=lambda: 100.0 + step * next(ticks), monotonic=time.monotonic,
                                 time=time.time, sleep=time.sleep)


# --- V4: the trace's times come from a clock that resolves them --------------------------------------------------------

def test_a_turns_time_in_the_trace_is_read_on_the_fine_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # On Windows, Python 3.12's monotonic clock moves in steps of ~15.6 ms: every ms of the trace was a multiple of it.
    from baxy_mind import mind as mind_module
    monkeypatch.setattr(mind_module, "time", _clock(0.0123))
    mind, _ = _mind(tmp_path, [_say("Hola.")])
    mind.decide(1, "hola")
    row = json.loads((tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert row["stage"] == "turn.decide" and row["ms"] == 12


def test_the_voices_times_are_read_on_the_same_fine_clock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # voice.speak's row (__main__.spoken) subtracts the voice's times from the mind's clock: both are perf_counter.
    import numpy as np
    from baxy_mind import voice_output
    from test_voice_output import _FakeStream, _player
    monkeypatch.setattr(voice_output, "time", _clock(0.0))
    told: list[tuple] = []
    speech = _player(tmp_path, monkeypatch, [], _FakeStream())
    speech._on_spoken = lambda queued, sounded, notice: told.append((queued, sounded))
    speech._play(iter([np.full(10, 0.1, np.float32)]), speech._generation, 100.0)
    assert told == [(100.0, 100.0 + _FakeStream.latency)]  # the first sound
    stamps: list[float] = []
    speech._sentences = lambda text: iter([text])  # type: ignore[method-assign]
    speech._play = lambda audio, generation, stamp, *rest: stamps.append(stamp)  # type: ignore[method-assign]
    assert speech.speak("Hola.")
    deadline = time.monotonic() + 5
    while not stamps and time.monotonic() < deadline:
        time.sleep(0.01)
    assert stamps == [100.0]  # when the answer was given


# --- V3: the doubt's rivals read the decision's prompt rendered once ----------------------------------------------------

def test_the_rivals_of_a_doubted_decision_share_one_rendered_prompt(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    # System One's options were the same with /apply-template asked once per rival: each one re-rendered the whole
    # prompt (decisions with System One 1.5-2.75 s against 1.1-1.4 s). Same options, one rendering.
    import io
    import math
    import urllib.parse
    from baxy_mind import llm_server
    from test_mind_doubt_policy import _layer2, _token
    weakest = _token("window", 0.54)
    weakest["top_logprobs"] += [{"token": t, "logprob": math.log(q)} for t, q in (("app", 0.3), ("file", 0.1),
                                                                                    ("web", 0.03))]
    tokens = [_token("<tool_call>", 0.95), _token("\n", 1.0), _token("<", 1.0), _token("function", 1.0),
              _token("=", 1.0), weakest, _token("_resolve", 1.0), _token(">", 1.0)]
    reply = {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": "window_resolve", "arguments": "{}"}}]}, "logprobs": {"content": tokens}}]}
    mind, _, one = _layer2(tmp_path, monkeypatch, "window_resolve", [])
    mind.tools = [{"type": "function", "function": {"name": n, "description": "Tool. More.", "parameters": {}}}
                  for n in ("window_resolve", "app_close", "file_read", "web_search")]
    mind.wire_to_op = {n: n.replace("_", ".") for n in ("window_resolve", "app_close", "file_read", "web_search")}
    server = llm_server.LlmServer("model.gguf", "llama-server.exe")
    server._ready.set()
    server.chat = lambda body, **kw: reply  # type: ignore[method-assign]
    rest = {"app": "_close", "file": "_read", "web": "_search"}
    calls: list[tuple[str, dict]] = []

    def urlopen(request, timeout):
        path, body = urllib.parse.urlsplit(request.full_url).path, json.loads(request.data)
        if path == "/tokenize":
            return io.BytesIO(json.dumps({"tokens": [0] * (len(body["content"]) // 4)}).encode("utf-8"))
        calls.append((path, body))
        if path == "/apply-template":
            assert body == {k: v for k, v in mind_body.items() if k in ("messages", "tools", "chat_template_kwargs")}
            return io.BytesIO(json.dumps({"prompt": "PROMPT"}).encode("utf-8"))
        assert body["prompt"].startswith("PROMPT<tool_call>\n<function=")
        return io.BytesIO(json.dumps({"content": rest[body["prompt"].rsplit("=", 1)[1]]}).encode("utf-8"))

    mind_body: dict = {}
    real_candidates = type(mind)._candidates
    monkeypatch.setattr(type(mind), "_candidates",
                        lambda self, chosen, doubt, body: mind_body.update(body) or real_candidates(self, chosen, doubt,
                                                                                                     body))
    monkeypatch.setattr(llm_server.urllib.request, "urlopen", urlopen)
    mind.server = server
    assert mind.decide(1, "eso")["operation"] == "window.resolve"
    assert [path for path, _ in calls] == ["/apply-template", "/completion", "/completion", "/completion"]
    assert all({k: v for k, v in body.items() if k != "prompt"} == {
        "n_predict": 24, "temperature": 0.0, "stop": [">", "\n"], "cache_prompt": True, "id_slot": 0}
        for path, body in calls[1:])
    assert list(one.asked[0]["options"]) == ["window_resolve", "app_close", "file_read", "web_search", "ask_user",
                                             "responder_con_palabras"]


# --- V2: an answer that comes straight from the decision is synthesized before the App has it --------------------------

def test_an_answer_straight_from_the_decision_is_synthesized_before_the_turn_returns_and_sounds_only_when_asked(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # turn.decide is not streamed (its doubt reads every token's probabilities), so foresee never ran for its words:
    # first sound p50 966 ms, p90 2,388. Now its first sentence is synthesized as soon as the reply is in.
    from test_maximo_stream import FIRST, REST, _until, _voice
    synthesized: list[str] = []
    played: list[str] = []
    speech = _voice(tmp_path, monkeypatch, synthesized, played)
    mind, server = _mind(tmp_path, [_say(FIRST + REST)])
    told: list[tuple] = []
    mind.foresee = lambda text, done: told.append((text, done)) or speech.foresee(text, done)
    result = mind.decide(1, "¿está spotify abierto?")
    assert "logprobs" in server.bodies[0]  # not streamed: the doubt is read
    assert told == [(result["reply"], True)]  # given to the voice before the turn's result went back
    _until(lambda: synthesized)
    assert synthesized == [FIRST.strip()] and played == []  # nothing sounds before the App publishes it
    assert speech.speak(result["reply"])  # the App's voice.speak, after publishing
    _until(lambda: len(played) == 2)
    assert played == [FIRST.strip(), REST] and synthesized == [FIRST.strip(), REST]  # the take was reused


def test_a_call_or_a_heartbeat_is_never_foreseen(tmp_path: Path) -> None:
    from test_mind_final import _call
    told: list[tuple] = []
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Spotify"}), _say(""), _say(""), _say("")])
    server.chat = (lambda chat: lambda body, on_text=None: chat(body))(server.chat)  # type: ignore[method-assign]
    mind.foresee = lambda text, done: told.append((text, done)) or True
    assert mind.decide(1, "abre spotify")["kind"] == "action"
    mind.beat(2, {"activity": "idle"})
    assert told == []
