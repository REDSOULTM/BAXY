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
