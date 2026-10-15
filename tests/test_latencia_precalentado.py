"""Tanda t4-r6 (2026-10-08): la voz se precalienta al arrancar la mente, nunca en el primer turno."""

from __future__ import annotations

import threading

from typing import Any

import pytest

import baxy_mind.__main__ as sidecar
from baxy_mind import voice as voice_module
from baxy_mind.voice import VoiceRuntimeImports


class _Importer:
    def __init__(self, failing: frozenset[str] = frozenset()) -> None:
        self.ran_on: list[tuple[str, str]] = []
        self.failing = failing

    def __call__(self, name: str, **_kwargs: Any) -> object:
        self.ran_on.append((name, threading.current_thread().name))
        if name in self.failing:
            raise OSError("no audio device")
        return object()


def test_the_voice_import_runs_off_the_request_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    importer = _Importer()
    monkeypatch.setattr(
        voice_module, "_VOICE_RUNTIME_IMPORTS", VoiceRuntimeImports(("sherpa_onnx", "silero_vad"), importer)
    )
    thread = sidecar._prewarm_voice()
    assert thread is not None and thread.daemon
    thread.join(2.0)
    assert importer.ran_on == [("sherpa_onnx", "baxy-voice-imports"), ("silero_vad", "baxy-voice-imports")]
    assert threading.current_thread().name not in {name for _, name in importer.ran_on}


def test_a_failing_import_is_left_to_voice_status(monkeypatch: pytest.MonkeyPatch) -> None:
    importer = _Importer(failing=frozenset({"sounddevice"}))
    imports = VoiceRuntimeImports(("sounddevice",), importer)
    monkeypatch.setattr(voice_module, "_VOICE_RUNTIME_IMPORTS", imports)
    thread = sidecar._prewarm_voice()
    assert thread is not None
    thread.join(2.0)
    assert not thread.is_alive()
    assert imports.wait(0) == {"sounddevice": False}


def test_the_voice_runtime_is_warmed_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contracaso: un segundo arranque del calentamiento no importa otra vez."""

    importer = _Importer()
    monkeypatch.setattr(voice_module, "_VOICE_RUNTIME_IMPORTS", VoiceRuntimeImports(("sherpa_onnx",), importer))
    first = sidecar._prewarm_voice()
    assert first is not None
    first.join(2.0)
    assert sidecar._prewarm_voice() is None
    assert importer.ran_on == [("sherpa_onnx", "baxy-voice-imports")]


@pytest.mark.parametrize(("configured", "warmed"), [(True, True), (False, False)])
def test_main_warms_the_voice_only_beside_a_served_model(
    monkeypatch: pytest.MonkeyPatch, configured: bool, warmed: bool
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(sidecar, "_prewarm_voice", lambda: calls.append("prewarm"))
    monkeypatch.setattr(sidecar, "_run_control_plane", lambda _lifecycle: calls.append("serve") or 0)
    if configured:
        monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "fixture.gguf")
    else:
        # Contracaso: a sidecar without a model (tests, tooling) imports no voice runtime in the background.
        monkeypatch.delenv("BAXY_MIND_LLM_GGUF", raising=False)
    assert sidecar.main() == 0
    assert calls == (["prewarm", "serve"] if warmed else ["serve"])
