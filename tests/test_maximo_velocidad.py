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
    # A request that asks nothing of the PC's state: «¿está spotify abierto?» answered with no look is what the answer
    # check asks again (aid «answer_check», test_answer_check.py).
    result = mind.decide(1, "pon música")
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


# --- V1: the prompt prefix is kept on disk and restored at the next start --------------------------------------------

class _FakeLlama:
    """llama-server's double: the endpoints the warm-up uses and its slot files. Its one slot holds the last prompt it
    read; /slots save and restore write and read that in its --slot-save-path, as the server does."""

    def __init__(self, folder: Path) -> None:
        import http.server
        import threading
        import urllib.parse
        folder.mkdir(parents=True, exist_ok=True)
        self.folder, self.calls, self.slot, self.build, self.fail_restore = folder, [], "", "b11609-test", False
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _answer(self, status: int, payload: dict) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                fake.calls.append(self.path)
                self._answer(200, {"build_info": fake.build})

            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.calls.append(self.path)
                path, query = urllib.parse.urlsplit(self.path)[2:4]
                if path == "/tokenize":
                    return self._answer(200, {"tokens": [248058] if body["content"] == "<tool_call>" else [0]})
                if path == "/v1/chat/completions":
                    fake.slot = json.dumps(body["messages"], ensure_ascii=False)
                    said = body["messages"][-1]["content"]
                    if said == "hola":
                        return self._answer(200, {"choices": [{"message": {"content": "H"}}],
                                                  "usage": {"prompt_tokens": 37000}})
                    return self._answer(200, {"choices": [{"message": {"content": "Listo."}}]})
                state = fake.folder / body["filename"]
                if query == "action=save":
                    state.write_text(fake.slot, encoding="utf-8")
                    return self._answer(200, {"id_slot": 0, "filename": state.name, "n_saved": 10})
                if fake.fail_restore or not state.is_file():
                    return self._answer(400, {"error": {"code": 400, "message": "Unable to restore slot"}})
                fake.slot = state.read_text(encoding="utf-8")
                return self._answer(200, {"id_slot": 0, "filename": state.name, "n_restored": 10})

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def files(self) -> list[str]:
        return sorted(p.name for p in self.folder.iterdir())


_TOOLS = [{"type": "function", "function": {"name": "app_open", "description": "Open an application. Installed "
                                            "applications (use one of these names as appId): Paint; Spotify.",
                                            "parameters": {}}}]


def _warmed(tmp_path: Path, fake: _FakeLlama, tools: list | None = None, gguf: Path | None = None,
            context: int = 53248):
    from baxy_mind.llm_server import LlmServer
    from baxy_mind.mind import Mind
    if gguf is None:
        gguf = tmp_path / "model.gguf"
        if not gguf.exists():
            gguf.write_bytes(b"GGUF")
    server = LlmServer(str(gguf), "llama-server.exe", context=context)
    server.port, server.slot_dir = fake.httpd.server_address[1], fake.folder
    server._settings = ["-c", str(context)]  # what start() sets
    server._ready.set()
    mind = Mind(server, tmp_path / "turns.jsonl")
    mind.tools = json.loads(json.dumps(tools or _TOOLS))
    mind.warm()
    return mind


def _rows(tmp_path: Path, stage: str) -> list[dict]:
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    return [row for row in rows if row["stage"] == stage]


WARM = ["/tokenize", "/props", "/v1/chat/completions", "/slots/0?action=save"]


def test_a_start_restores_the_prefix_the_last_one_kept_instead_of_reading_it_again(tmp_path: Path) -> None:
    # Every start re-read ~44,600 tokens (18.3 s); the vision's own slot restore read 42,910 back in 0.74 s.
    fake = _FakeLlama(tmp_path / "slots")
    first = _warmed(tmp_path, fake)
    assert fake.calls == WARM
    assert first.prefix_tokens == 37000
    kept = fake.files()
    assert len(kept) == 2 and {Path(name).suffix for name in kept} == {".json", ".slot"}
    fake.calls.clear()
    again = _warmed(tmp_path, fake)  # the next start: a new server process and a new mind
    assert fake.calls == ["/tokenize", "/props", "/slots/0?action=restore"]  # nothing read again
    assert again.prefix_tokens == 37000
    assert fake.files() == kept
    assert [row.get("restored") for row in _rows(tmp_path, "warm.prefix")] == [False, True]


@pytest.mark.parametrize("change", ["tools", "gguf", "context", "build"])
def test_a_prefix_made_of_anything_else_is_read_again_and_kept_beside_the_one_before(tmp_path: Path, change: str) -> None:
    fake = _FakeLlama(tmp_path / "slots")
    _warmed(tmp_path, fake)
    old = fake.files()
    fake.calls.clear()
    tools, gguf, context = None, None, 53248
    if change == "tools":  # an application installed since: its name is in app_open's description
        tools = json.loads(json.dumps(_TOOLS).replace("Spotify.", "Spotify; Steam."))
    elif change == "gguf":
        gguf = tmp_path / "other.gguf"
        gguf.write_bytes(b"GGUF2")
    elif change == "context":
        context = 49152
    else:
        fake.build = "b11700-test"
    _warmed(tmp_path, fake, tools, gguf, context)
    assert fake.calls == WARM  # its key has no state: no restore asked, the warm-up as always, then kept
    # P0.9: the other key's state stays too (a start with a late catalog must not cost the next one its prefix)
    assert len(fake.files()) == 4 and set(old) < set(fake.files())


def test_a_prefix_the_server_cannot_restore_is_read_again_and_kept_anew(tmp_path: Path) -> None:
    fake = _FakeLlama(tmp_path / "slots")
    _warmed(tmp_path, fake)
    kept = fake.files()
    fake.calls.clear()
    fake.fail_restore = True
    mind = _warmed(tmp_path, fake)
    assert fake.calls == ["/tokenize", "/props", "/slots/0?action=restore", *WARM[2:]]
    assert mind.prefix_tokens == 37000 and fake.files() == kept


def test_the_prefix_is_kept_only_before_any_turn_so_no_conversation_reaches_the_disk(tmp_path: Path) -> None:
    fake = _FakeLlama(tmp_path / "slots")
    mind = _warmed(tmp_path, fake)
    assert json.loads(next(fake.folder.glob("*.slot")).read_bytes())[-1]["content"] == "hola"
    for kept in fake.folder.iterdir():
        kept.unlink()
    mind.decide(1, "mi clave del banco es 4321")
    fake.calls.clear()
    mind.warm()  # the App configures the catalog again after a turn: the slot may hold the turn's checkpoints
    assert "/v1/chat/completions" in fake.calls and "/slots/0?action=save" not in fake.calls
    assert fake.files() == []


def test_the_vision_sets_the_slot_aside_in_the_same_folder_and_the_prefix_survives_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from baxy_mind import llm_server
    slots, projector = tmp_path / "slots", tmp_path / "mmproj.gguf"
    projector.write_bytes(b"GGUF")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(slots))  # LocalVisionEndpoint.SlotDirectory, run_renew.cmd
    monkeypatch.setenv("BAXY_MIND_MMPROJ", str(projector))
    fake = _FakeLlama(slots)
    _warmed(tmp_path, fake)
    prefix = fake.files()
    # The App's vision (WindowsVisibleVisionLocator): its state set aside, a question on the slot, the state put back.
    server = llm_server.LlmServer(str(tmp_path / "model.gguf"), "llama-server.exe")
    server.port = fake.httpd.server_address[1]
    server._ready.set()
    before = fake.slot
    assert server._post("/slots/0?action=save", {"filename": "baxy_vision_hold.bin"}, 5)["n_saved"]
    server.chat({"messages": [{"role": "user", "content": "¿Dónde está el botón Guardar?"}]})
    assert server._post("/slots/0?action=restore", {"filename": "baxy_vision_hold.bin"}, 5)["n_restored"]
    assert fake.slot == before
    assert fake.files() == sorted([*prefix, "baxy_vision_hold.bin"])  # one folder, neither file touched the other
    # The next start: a held state left behind is removed (it holds a conversation), the prefix stays and is restored.
    commands: list[list[str]] = []

    class Alive:
        def poll(self) -> None:
            return None

    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda command, **kw: commands.append(command) or Alive())
    monkeypatch.setattr(llm_server.LlmServer, "_wait_health", lambda self: None)
    llm_server.LlmServer(str(tmp_path / "model.gguf"), "llama-server.exe").start()
    command = commands[0]
    assert command.count("--slot-save-path") == 1 and command[command.index("--slot-save-path") + 1] == str(slots)
    assert "--mmproj" in command
    assert fake.files() == prefix
    fake.calls.clear()
    _warmed(tmp_path, fake)
    assert fake.calls[-1] == "/slots/0?action=restore"


def test_without_the_vision_the_prefix_has_its_folder_all_the_same(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    from baxy_mind import llm_server
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_VISION_SLOT_DIR", raising=False)
    monkeypatch.delenv("BAXY_MIND_MMPROJ", raising=False)
    commands: list[list[str]] = []
    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda command, **kw: commands.append(command) or object())
    monkeypatch.setattr(llm_server.LlmServer, "_wait_health", lambda self: None)
    llm_server.LlmServer("model.gguf", "llama-server.exe").start()
    command = commands[0]
    assert command[command.index("--slot-save-path") + 1] == str(tmp_path / "BAXY" / "renew" / "slots")
    assert "--mmproj" not in command
