"""The voice's output opens while the model writes any answer of a person's turn (src/baxy_mind/__main__.py): the
decision, the continuation after a tool and the answer to a confirmation, never a heartbeat's."""
import pathlib

import pytest


def test_the_output_opens_for_every_answer_of_a_person_s_turn(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from baxy_mind import __main__ as sidecar
    prepared: list[str] = []
    incoming = [{"type": "turn.decide", "id": 1, "text": "busca notas"},
                {"type": "turn.continue", "id": 2, "observation": "{}"},
                {"type": "turn.continue", "id": 3, "observation": "{}", "beat": True},
                {"type": "turn.confirm", "id": 4, "approve": True, "label": "Sí"},
                None]
    turn: list[str] = []

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            pass

        start = close = lambda self: None

    class FakeMind:
        notice = ""
        foresee = None
        gave_way = None

        def __init__(self, *args) -> None:
            pass

        def decide(self, request_id, text, pending, unsure=None, front=None, named=None):
            turn.append(f"decide:{request_id}")
            return {"type": "turn.result", "id": request_id}

        def continue_turn(self, request_id, observation, final, beat):
            turn.append(f"continue:{request_id}")
            return {"type": "turn.result", "id": request_id}

        def confirm(self, request_id, approve, label):
            turn.append(f"confirm:{request_id}")
            return {"type": "turn.result", "id": request_id}

        def prefill(self) -> bool:
            return False

    class FakeSpeech:
        failure = ""  # a voice that can speak (the hello offers voice.speak)
        def foresee(self, text, done):
            return True

        def prepare(self) -> None:
            prepared.append(f"before:{len(turn)}")

        def close(self) -> None:
            pass

    class FakeVoice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = FakeSpeech()

        def unsure(self, text: str) -> list:
            return []

        def stop(self) -> None:
            pass

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "its-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")  # the server is a fake
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", lambda: incoming.pop(0))
    monkeypatch.setattr(sidecar.protocol, "write_message", lambda message: None)
    assert sidecar.main() == 0
    # opened before the decision, the continuation and the confirmation's answer; not for the heartbeat's
    assert turn == ["decide:1", "continue:2", "continue:3", "confirm:4"]
    assert prepared == ["before:0", "before:1", "before:3"]


@pytest.mark.parametrize(("failure", "offered"), [
    ("FileNotFoundError('BAXY_RENEW_TTS_DIR has no tts.json')", False),  # no voice on this PC (AMD e2e 2026-11-04)
    ("", True),                                                            # loaded, or loading with its files there
])
def test_the_hello_offers_voice_speak_only_from_a_voice_that_can_speak(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, failure: str, offered: bool) -> None:
    """uso-82: the mind offered voice.speak always, and on a PC with no voice the App waited 10 s for every answer to
    sound (ProductConductorHost.SpeechWait). A voice that fails after the hello says so in its voice.speak.result."""
    from baxy_mind import __main__ as sidecar
    incoming = [{"type": "voice.speak", "id": 1, "text": "Son las tres."}, None]
    written: list[dict] = []

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            pass

        start = close = lambda self: None

    class FakeMind:
        notice = ""
        foresee = None
        gave_way = None

        def __init__(self, *args) -> None:
            pass

    class FakeSpeech:
        def __init__(self) -> None:
            self.failure = failure

        def foresee(self, text, done):
            return True

        def speak(self, text: str, notice: bool = False) -> bool:
            return not self.failure

        def close(self) -> None:
            pass

    class FakeVoice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = FakeSpeech()

        def stop(self) -> None:
            pass

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "its-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")  # the server is a fake
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", lambda: incoming.pop(0))
    monkeypatch.setattr(sidecar.protocol, "write_message", written.append)
    assert sidecar.main() == 0
    hello = next(message for message in written if message["type"] == "hello")
    result = next(message for message in written if message["type"] == "voice.speak.result")
    assert ("voice.speak" in hello["requests"]) is offered
    assert "voice.cancel" in hello["requests"]
    assert result["accepted"] is offered and result["speaks"] is offered
