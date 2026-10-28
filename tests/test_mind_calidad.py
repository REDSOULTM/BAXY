"""Revisión de calidad de la mente (2026-10-25): defectos de recursos, hilos y estado de src/baxy_mind, cada uno con su
prueba."""
import pathlib

import pytest

from baxy_mind import llm_server, system_one

EXE = "llama-server.exe"  # a stand-in: nothing is run


class _Process:
    returncode = 0

    def poll(self) -> int:
        return 0

    def terminate(self) -> None:
        pass

    def wait(self, _timeout: float | None = None) -> int:
        return 0


def test_the_model_servers_logs_are_not_held_open_by_the_mind(
        monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """The log a llama-server writes is its own handle: the mind opened it for Popen and never closed its copy, one more
    for every start again of System One's server."""
    logs = []

    def popen(_command, stdout=None, **_kwargs):
        logs.append(stdout)
        return _Process()

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_VISION_SLOT_DIR", raising=False)
    monkeypatch.delenv("BAXY_MIND_MMPROJ", raising=False)
    monkeypatch.delenv("BAXY_MIND_LLAMA_PORT", raising=False)
    monkeypatch.setattr(llm_server.subprocess, "Popen", popen)
    monkeypatch.setattr(system_one.subprocess, "Popen", popen)
    server = llm_server.LlmServer("qwen.gguf", EXE)
    server.start()
    laya = system_one.SystemOne("laya.gguf", EXE)
    laya._launch()
    laya.restarts = 1
    laya._launch()
    assert len(logs) == 3 and all(log.closed for log in logs)


def _stdin(monkeypatch: pytest.MonkeyPatch, data: bytes) -> None:
    import io
    import sys
    from types import SimpleNamespace

    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(data)))


def test_a_request_of_exactly_the_line_limit_is_read_as_the_app_writes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """The App sends a request whose JSON is up to 1 MiB (MindSidecarClient.MaximumLineBytes, the line without its
    end) and the mind writes its replies on the same contract (write_message); the reader counted the line's end too,
    so a request of exactly 1 MiB was a protocol violation and the mind exited (65)."""
    from baxy_mind import protocol

    head, tail = b'{"type":"session.load","pad":"', b'"}'
    line = head + b"x" * (protocol.MAX_LINE_BYTES - len(head) - len(tail)) + tail
    assert len(line) == protocol.MAX_LINE_BYTES
    _stdin(monkeypatch, line + b"\n" + line + b"\r\n")
    assert protocol.read_message()["type"] == "session.load"
    assert protocol.read_message()["type"] == "session.load"
    assert protocol.read_message() is None
    # One byte more is still refused, with or without its line end.
    longer = head + b"x" * (protocol.MAX_LINE_BYTES + 1 - len(head) - len(tail)) + tail
    for ending in (b"\n", b"\r\n", b""):
        _stdin(monkeypatch, longer + ending)
        with pytest.raises(protocol.ProtocolViolation) as refused:
            protocol.read_message()
        assert refused.value.code == "line_too_large"


def _found(url: str) -> str:
    import json

    return json.dumps({"status": "completed", "observed": {"results": [{"title": "Lluvia", "url": url}]}})


def test_the_short_references_of_turns_cut_out_are_not_kept(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Aid «short_refs»: every long address of the session stayed in Mind._refs for good, after the turns that showed it
    were cut out of the conversation: the exported session (the App's 1 MiB per line) and the state an early decision
    deep-copies grew with every address ever seen. What the conversation no longer shows is dropped; the numbers go on,
    so a new address never takes the number of one still shown."""
    from test_mind_final import _call, _mind, _say

    from baxy_mind import mind as mind_module

    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.setattr(mind_module, "HISTORY_TURNS", 2)
    first, second = ("https://news.example.org/rss/articles/" + letter * 300 + "?oc=5" for letter in "ab")
    mind, server = _mind(tmp_path, [_call("web_search", {"query": "clima"}), _say("Encontré una noticia."),
                                    _say("Hola."), _say("Hola."), _call("web_search", {"query": "lluvia"}),
                                    _say("Otra noticia.")])
    mind.decide(1, "el clima")
    mind.continue_turn(2, _found(first))
    mind.decide(3, "hola")
    assert mind.export_session()[-1]["refs"] == {"ref:r1": first}
    mind.decide(4, "hola")  # the first turn is cut out of the conversation
    assert "ref:r1" not in json_text(mind.conversation)
    assert mind.export_session()[-1]["refs"] == {}
    mind.decide(5, "y la lluvia")
    mind.continue_turn(6, _found(second))
    assert "ref:r2" in json_text(server.bodies[-1]["messages"])
    assert mind.export_session()[-1]["refs"] == {"ref:r2": second}


def json_text(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def test_the_sessions_calls_for_the_answer_check_do_not_grow_with_each_repeat(tmp_path: pathlib.Path,
                                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """Aid «answer_check»: Mind._calls kept one entry per call of the session, forever (exported with the session and
    deep-copied by every early decision), while the check only asks whether a call of a kind completed (or ran at
    all): the same (operation, completed, read) is kept once."""
    import json

    from test_mind_final import _call, _mind, _say

    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    replies = []
    for _ in range(5):
        replies += [_call("app_open", {"appId": "Spotify"}), _say("Abrí Spotify.")]
    mind, _ = _mind(tmp_path, replies)
    mind.wire_to_op = {"app_open": "app.open"}
    for turn in range(5):
        mind.decide(2 * turn, "abre Spotify")
        mind.continue_turn(2 * turn + 1, json.dumps({"status": "completed", "verification": "state"}))
    assert mind.export_session()[-1]["calls"] == [["app.open", True, False]]
    kept = mind.export_session()
    kept[-1]["calls"] = [["app.open", True, False]] * 3 + [["app.close", False, False]]
    mind.load_session(kept)
    assert mind.export_session()[-1]["calls"] == [["app.open", True, False], ["app.close", False, False]]


def test_a_trace_that_cannot_be_rotated_does_not_stop_the_mind_from_starting(tmp_path: pathlib.Path,
                                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """Past its cap the trace becomes turns.jsonl.1 when the mind starts; on Windows that fails while another process
    holds either file open (a bench reading it, a scan), and the PermissionError ended main() before the request loop,
    with llama-server already started. The trace then goes on in the same file and is capped at the next start."""
    from baxy_mind import __main__ as sidecar

    trace = tmp_path / "turns.jsonl"
    trace.write_bytes(b"x" * 200)

    def held(*_args) -> None:
        raise PermissionError(32, "The process cannot access the file because it is being used by another process")

    monkeypatch.setattr(sidecar.os, "replace", held)
    assert sidecar.bounded_trace(trace, limit=100) == trace
    assert trace.read_bytes() == b"x" * 200


def test_a_kept_prefix_that_cannot_be_written_or_cleaned_does_not_fail_the_warm_up(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """LlmServer.save_prefix only saves time at the next start, but a file of the slot folder held by another process
    (a scan of the 2 GB state just written) raised out of it: Mind.warm failed and the App was told the model did not
    start (catalog_runtime_failure) with the model up and warm."""
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(tmp_path))
    monkeypatch.delenv("BAXY_MIND_LLAMA_PORT", raising=False)
    server = llm_server.LlmServer("qwen.gguf", EXE)
    stale = tmp_path / f"{llm_server.PREFIX}old.slot"
    stale.write_bytes(b"old")
    monkeypatch.setattr(server, "_post", lambda *_args: {"n_saved": 10})
    real_unlink = pathlib.Path.unlink

    def unlink(self: pathlib.Path, missing_ok: bool = False) -> None:
        if self.name == stale.name:
            raise PermissionError(32, "being used by another process")
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(pathlib.Path, "unlink", unlink)
    assert server.save_prefix("new", {"prefix_tokens": 1, "notice": ""}) is True
    assert (tmp_path / f"{llm_server.PREFIX}new.json").is_file() and stale.is_file()

    def unwritable(self: pathlib.Path, *_args, **_kwargs) -> None:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(pathlib.Path, "write_text", unwritable)
    assert server.save_prefix("other", {"prefix_tokens": 1, "notice": ""}) is False
    assert not (tmp_path / f"{llm_server.PREFIX}other.json").exists()


def test_a_start_whose_prefix_differs_keeps_the_last_one_restored(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """P0.9 (feria, 2026-10-27): one start whose prefix had another key (its tools from a catalog that came late) saved
    its own state and removed every other one, so the next usual start re-read the whole prefix too (~30 s instead of
    under 3 s). The last state restored stays beside the one just saved; a third key removes the one used least
    recently."""
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(tmp_path))
    monkeypatch.delenv("BAXY_MIND_LLAMA_PORT", raising=False)
    server = llm_server.LlmServer("qwen.gguf", EXE)

    def post(path: str, body: dict, _timeout: float) -> dict:
        if "save" in path:
            (tmp_path / body["filename"]).write_bytes(b"state")
            return {"n_saved": 10}
        return {"n_restored": 10 if (tmp_path / body["filename"]).is_file() else 0}

    monkeypatch.setattr(server, "_post", post)
    assert server.save_prefix("usual", {"prefix_tokens": 7})
    assert server.save_prefix("late", {"prefix_tokens": 5})
    assert server.restore_prefix("usual") == {"prefix_tokens": 7}
    assert server.save_prefix("other", {"prefix_tokens": 6})
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        f"{llm_server.PREFIX}{key}.{suffix}" for key in ("other", "usual") for suffix in ("json", "slot")]


def test_the_model_servers_are_closed_even_when_the_voice_cannot_say_it_stopped(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """At the end the voice says it stopped (a voice.event on stdout); with the App gone that write fails, and the
    OSError skipped closing the speech, llama-server and System One's server: without a job object around the mind (a
    bench that runs it), both servers outlived it, the GPU's 4 GB held. Every step of the end runs."""
    from baxy_mind import __main__ as sidecar
    from baxy_mind.llm_server import LlmServer
    from baxy_mind.mind import Mind

    closed: list[str] = []

    class Server(LlmServer):
        def start(self):
            pass

        def close(self) -> None:
            closed.append("server")

    class Speech:
        def foresee(self, text, done):
            return True

        def close(self) -> None:
            closed.append("speech")

    class Voice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = Speech()

        def stop(self) -> None:
            raise OSError(22, "Invalid argument")  # stdout's pipe, the App gone

    class Laya:
        def __init__(self, *args) -> None:
            self.on_event = None

        def start(self):
            pass

        def close(self) -> None:
            closed.append("system_one")

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", EXE)
    monkeypatch.setenv("BAXY_S1_GGUF", "laya.gguf")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_VISION_SLOT_DIR", raising=False)
    monkeypatch.delenv("BAXY_MIND_LLAMA_PORT", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(sidecar, "LlmServer", Server)
    monkeypatch.setattr(sidecar, "SystemOne", Laya)
    monkeypatch.setattr(sidecar, "Mind", Mind)
    monkeypatch.setattr(sidecar, "Voice", Voice)
    monkeypatch.setattr(sidecar.protocol, "read_message", lambda: None)
    monkeypatch.setattr(sidecar.protocol, "write_message", lambda message: None)
    assert sidecar.main() == 0
    assert closed == ["speech", "server", "system_one"]


def test_system_ones_server_is_not_started_again_once_the_mind_closes(tmp_path: pathlib.Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """The watcher starts an exited server again after a pause; close() arriving between that pause and the start
    found the old process gone and terminated nothing, and the watcher then started a server nobody would close."""
    launched: list = []

    class Exited(_Process):
        returncode = 1

        def poll(self) -> int:
            return 1

    def popen(_command, stdout=None, **_kwargs):
        launched.append(Exited())
        return launched[-1]

    laya = system_one.SystemOne("laya.gguf", EXE)

    def free_port() -> int:
        laya.close()  # the mind ends right then
        return 5000

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(system_one.subprocess, "Popen", popen)
    monkeypatch.setattr(system_one, "_free_port", free_port)
    real_wait = system_one.threading.Event.wait
    monkeypatch.setattr(system_one.threading.Event, "wait",
                        lambda self, timeout=None: real_wait(self, min(timeout or 0.01, 0.01)))
    laya._launch()
    laya._watch()
    assert len(launched) == 1


def test_a_number_too_long_for_a_float_in_a_result_does_not_break_the_answer_check() -> None:
    """Aid «answer_check», rule «number»: each number in a result's short texts became a float, and one of 309 digits or
    more (a code, a pasted number) is infinite; told among the readings, int() of it raised OverflowError, the check
    failed and with it the whole turn (turn_runtime_failure instead of the answer)."""
    import json

    from baxy_mind.answer_check import check

    observed = {"status": "completed", "verification": "state", "observed": {"code": "9" * 320, "level": 40}}
    receipt = {"op": "audio.volume.set", "tool": "audio_volume_set", "arguments": {"level": 40},
               "observation": json.dumps(observed), "outcome": "completado y verificado", "completed": True,
               "read": False}
    findings = check("Listo, el volumen quedó en 45 %.", "sube el volumen", [receipt], [])
    assert [f["rule"] for f in findings] == ["number"] and "inf" not in findings[0]["fact"]


def test_an_answer_check_that_fails_leaves_the_answer_and_says_so_in_the_trace(
        monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Aid «answer_check»: Mind._check_answer called the heuristic unprotected, and any error in it (the one of 309
    digits was the first) failed the whole turn. A check that fails finds nothing: the answer stands, and the trace has
    a turn.check row with the error's type."""
    import json

    from baxy_mind import mind as mind_module
    from test_mind_aids import _trace
    from test_mind_final import _call, _mind, _say

    def broken(*_args, **_kwargs):
        raise ZeroDivisionError("a fault of the heuristic")

    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    monkeypatch.setattr(mind_module, "check_answer", broken)
    mind, server = _mind(tmp_path, [_call("app_close", {"appId": "Paint"}), _say("Cerré Paint.")])
    mind.wire_to_op = {"app_close": "app.close"}
    mind.decide(1, "cierra paint")
    result = mind.continue_turn(2, json.dumps({"status": "failed", "error": "window_not_found"}))
    assert result["kind"] == "conversation" and result["reply"] == "Cerré Paint." and len(server.bodies) == 2
    rows = [r for r in _trace(mind) if r["stage"] == "turn.check"]
    assert [(r["round"], r["error"], r["findings"]) for r in rows] == [(1, "ZeroDivisionError", [])]
    assert "a fault of the heuristic" not in json.dumps(rows)


def test_a_lone_surrogate_from_json_goes_to_the_app_as_a_replacement_character(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """json.loads accepts the escape of one half of a surrogate pair (a text cut mid-emoji) and gives a lone surrogate;
    encoded in UTF-8 it raised UnicodeEncodeError and the reply never reached the App. It goes as U+FFFD, the character
    System.Text.Json writes for one; a whole pair stays the emoji."""
    import io
    import json
    import types

    from baxy_mind import protocol

    out = io.BytesIO()
    monkeypatch.setattr(protocol.sys, "stdout", types.SimpleNamespace(buffer=out))
    cut = json.loads('"corta \ud83d"')
    protocol.write_message({"type": "turn.result", "reply": cut, "whole": json.loads('"\ud83d\ude00"')})
    sent = json.loads(out.getvalue().decode("utf-8"))
    assert sent["reply"] == "corta \ufffd" and sent["whole"] == "\U0001f600"


def test_a_lone_surrogate_in_a_turn_does_not_break_its_trace(tmp_path: pathlib.Path) -> None:
    """The trace row of a turn whose words carry a lone surrogate raised UnicodeEncodeError (not an OSError) out of
    Mind._write_row, and the turn failed with it."""
    import json

    from test_mind_aids import _trace
    from test_mind_final import _mind, _say

    mind, _ = _mind(tmp_path, [_say("Dime cuál quieres.")])
    result = mind.decide(1, json.loads('"pon la de \ud83d"'))
    assert result["reply"] == "Dime cuál quieres."
    assert any("pon la de \ufffd" in json.dumps(row, ensure_ascii=False) for row in _trace(mind))
