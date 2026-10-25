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
