"""Arranque de la mente (auditoría 2026-10-08, hallazgos 2 y 7): la voz nunca hace esperar ni tumba la mente.

Evidencia: ``v2-v3-04`` (corrida 4) y ``v2-s02``: el primer ``voice.status`` tardó más de 10 s importando el
runtime de voz (``silero_vad`` importa torch: 3,9 s en reposo, más junto al calentamiento del modelo) y el turno
esperó detrás; ``v2-u7``, ``v2-t-file-3`` y ``v2-v3-20``: el calentamiento del decisor terminaba en
``ConnectionError`` porque la app se cerraba mientras aún leía.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from baxy_mind import voice as voice_module
from baxy_mind.llm import LlmRuntime
from baxy_mind.llm_transport import ChatCompletionCancelled, SlotState
from baxy_mind.voice import VoiceEngine, VoiceRuntimeImports

# ------------------------------------------------------------------ the voice runtime imports once, off the caller


class _SlowImporter:
    """A cold import that finishes only when the test says so (no real clock)."""

    def __init__(self, missing: frozenset[str] = frozenset()) -> None:
        self.release = threading.Event()
        self.calls: list[tuple[str, str]] = []
        self.missing = missing

    def __call__(self, name: str, **_kwargs: Any) -> object:
        self.calls.append((name, threading.current_thread().name))
        self.release.wait(5)
        if name in self.missing:
            raise ImportError(name)
        return object()


def test_a_cold_voice_import_never_holds_the_reader() -> None:
    importer = _SlowImporter()
    imports = VoiceRuntimeImports(("sherpa_onnx", "silero_vad"), importer)
    started = time.monotonic()
    assert imports.wait(0.05) is None
    assert time.monotonic() - started < 1.0
    importer.release.set()
    assert imports.wait(5) == {"sherpa_onnx": True, "silero_vad": True}
    # Imported once, on its own thread, however many readers asked.
    assert imports.wait(0) == {"sherpa_onnx": True, "silero_vad": True}
    assert importer.calls == [
        ("sherpa_onnx", "baxy-voice-imports"),
        ("silero_vad", "baxy-voice-imports"),
    ]


def test_a_missing_voice_module_is_a_fact_not_a_failure() -> None:
    importer = _SlowImporter(missing=frozenset({"livekit.wakeword"}))
    importer.release.set()
    imports = VoiceRuntimeImports(("sherpa_onnx", "livekit.wakeword"), importer)
    assert imports.wait(5) == {"sherpa_onnx": True, "livekit.wakeword": False}


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class _FlakyImporter:
    """``sounddevice`` at logon: PortAudio fails before the audio service is up, then loads."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls: list[str] = []

    def __call__(self, name: str, **_kwargs: Any) -> object:
        self.calls.append(name)
        if len(self.calls) <= self.failures:
            raise OSError("Error querying device -1")
        return object()


def _settled(imports: VoiceRuntimeImports, expected: dict[str, bool]) -> dict[str, bool] | None:
    deadline = time.monotonic() + 5
    loaded = imports.wait(5)
    while loaded != expected and time.monotonic() < deadline:
        time.sleep(0.005)
        loaded = imports.wait(5)
    return loaded


def test_a_passing_import_failure_heals_on_a_later_read() -> None:
    """Contracaso del caché: el micrófono no queda «no disponible» para siempre en el proceso."""

    clock = _Clock()
    importer = _FlakyImporter(failures=1)
    imports = VoiceRuntimeImports(("sounddevice",), importer, clock=clock)
    assert imports.wait(5) == {"sounddevice": False}
    # Within the interval nothing is imported again (an absent module is not hammered).
    assert imports.wait(5) == {"sounddevice": False}
    assert importer.calls == ["sounddevice"]
    clock.now += voice_module.VOICE_IMPORT_RETRY_SECONDS
    # The read that starts the retry answers what is known now, never pending.
    assert imports.wait(0) == {"sounddevice": False}
    assert _settled(imports, {"sounddevice": True}) == {"sounddevice": True}
    assert importer.calls == ["sounddevice", "sounddevice"]


def test_a_retry_imports_only_what_failed() -> None:
    clock = _Clock()
    importer = _SlowImporter(missing=frozenset({"livekit.wakeword"}))
    importer.release.set()
    imports = VoiceRuntimeImports(("sherpa_onnx", "livekit.wakeword"), importer, clock=clock)
    assert imports.wait(5) == {"sherpa_onnx": True, "livekit.wakeword": False}
    clock.now += voice_module.VOICE_IMPORT_RETRY_SECONDS
    imports.wait(0)
    deadline = time.monotonic() + 5
    while len(importer.calls) < 3 and time.monotonic() < deadline:
        time.sleep(0.005)
    assert [name for name, _ in importer.calls] == ["sherpa_onnx", "livekit.wakeword", "livekit.wakeword"]
    assert _settled(imports, {"sherpa_onnx": True, "livekit.wakeword": False}) == {
        "sherpa_onnx": True,
        "livekit.wakeword": False,
    }


def test_voice_status_answers_pending_while_the_runtime_imports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gemelo de v2-v3-04: el estado de voz responde en el acto y dice que aún carga."""

    importer = _SlowImporter()
    monkeypatch.setattr(voice_module, "_VOICE_RUNTIME_IMPORTS", VoiceRuntimeImports(importer=importer))
    engine = VoiceEngine(lambda _text: None)
    started = time.monotonic()
    status = engine.status()
    # It never waits on the import: the shell reads the state again (MainWindowViewModel).
    assert time.monotonic() - started < 1.0
    assert status["pending"] is True
    assert status["available"] is False and status["input"] is False and status["stt"] is False
    importer.release.set()


def test_voice_status_settles_once_the_runtime_is_imported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contracaso: con el runtime ya importado el estado no queda pendiente."""

    importer = _SlowImporter()
    importer.release.set()
    imports = VoiceRuntimeImports(importer=importer)
    assert imports.wait(5) is not None
    monkeypatch.setattr(voice_module, "_VOICE_RUNTIME_IMPORTS", imports)
    status = VoiceEngine.probe()
    assert status["pending"] is False
    assert status["vad"] is True


# ------------------------------------------------------------------ the decider warmup ends with the mind, named so


class _WarmRuntime(LlmRuntime):
    """The runtime without a server: the warmup read waits until it is cancelled."""

    def __init__(self, read_seconds: float = 5.0) -> None:
        self._gguf = None
        self.read_seconds = read_seconds
        self._parallel_turn_verification = True
        self.cancellations: list[Any] = []
        self.outcomes: list[str] = []
        self.started = threading.Event()

    def _decider_slot_state(self, payload: dict[str, Any]) -> SlotState:
        return SlotState(Path("decider-x.bin"), {"prompt": payload["messages"][0]["content"]})

    def _prepare_slot(self, state: SlotState, cancellation: Any) -> None:
        self.cancellations.append(cancellation)
        self.started.set()
        deadline = time.monotonic() + self.read_seconds
        while time.monotonic() < deadline:
            if cancellation is not None and cancellation.cancelled:
                self.outcomes.append("cancelled")
                raise ChatCompletionCancelled("inferencia especulativa cancelada")
            time.sleep(0.005)
        self.outcomes.append("read")


TOOLS = (("app.open", "Abre una aplicación."), ("web.search", "Busca en la web."))
SIGNATURES = {"app.open": ("appId",), "web.search": ("query",)}


def test_closing_the_mind_cancels_the_decider_warmup_still_reading() -> None:
    """Gemelo de v2-t-file-3: la app cierra 2-4 s tras catalog.ready, con el calentamiento aún leyendo."""

    runtime = _WarmRuntime()
    runtime.warm_decider(TOOLS, signatures=SIGNATURES)
    assert runtime.started.wait(5)
    runtime._retire_decider_warmup()
    deadline = time.monotonic() + 5
    while not runtime.outcomes and time.monotonic() < deadline:
        time.sleep(0.005)
    assert runtime.outcomes == ["cancelled"]
    assert runtime._decider_warmup is None


def test_close_retires_the_decider_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _WarmRuntime()
    retired: list[str] = []
    monkeypatch.setattr(runtime, "_retire_decider_warmup", lambda: retired.append("warmup"))
    try:
        runtime.close()
    except Exception:  # noqa: BLE001 - a server-less runtime may stop later in close; the order is what counts
        pass
    assert retired == ["warmup"]


def test_an_uncut_warmup_reads_to_its_end() -> None:
    """Contracaso: sin cierre, el calentamiento lee el catálogo entero y nada lo cancela."""

    runtime = _WarmRuntime(read_seconds=0.05)
    runtime.warm_decider(TOOLS, signatures=SIGNATURES)
    deadline = time.monotonic() + 5
    while not runtime.outcomes and time.monotonic() < deadline:
        time.sleep(0.005)
    assert runtime.outcomes == ["read"]
    assert runtime.cancellations[0] is not None and not runtime.cancellations[0].cancelled
