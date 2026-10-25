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
