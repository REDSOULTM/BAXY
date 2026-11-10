"""The name of a conversation that closes (owner, 2026-11-08: «que el LLM reciba la instrucción de darle un nombre a la
conversación de no más de X palabras … para después yo poder ubicarla»). The model writes it, typed (a JSON schema); the
code only compares its form, and an unusable one is no name (the App keeps the first sentence and the date)."""
import json
from pathlib import Path

import pytest


def _named(text: str) -> dict:
    return {"choices": [{"message": {"content": json.dumps({"titulo": text}, ensure_ascii=False)},
                         "finish_reason": "stop"}]}


def _talked(tmp_path: Path, *replies):
    from test_mind_final import _mind, _say
    mind, server = _mind(tmp_path, [_say("Mañana en Viña: 18 °C y nublado."), *replies])
    mind.decide(1, "qué tiempo hace mañana en viña del mar")
    return mind, server


def test_the_model_names_the_closed_conversation_as_its_slot_holds_it(tmp_path: Path) -> None:
    from baxy_mind import mind as mind_module
    mind, server = _talked(tmp_path, _named("Clima de mañana en Viña"))
    conversation = mind.export_session()
    decision = server.bodies[0]["messages"]
    mind.new_session()  # the App starts the next conversation first: the name never makes the person wait
    assert mind.title_of(conversation) == "Clima de mañana en Viña"
    asked = server.bodies[-1]
    # what the slot already holds (system, tools, the conversation as it was rendered) and one ask after it
    assert asked["messages"][:2] == decision[:2]
    assert asked["messages"][-1]["role"] == "user" and str(mind_module.TITLE_MAX_WORDS) in asked["messages"][-1]["content"]
    assert asked["tools"] == server.bodies[0]["tools"] and asked["tool_choice"] == "none"
    assert asked["response_format"]["type"] == "json_schema"
    assert asked["temperature"] == 0.0 and asked["chat_template_kwargs"] == {"enable_thinking": False}
    assert mind.conversation == []  # the new conversation is untouched


@pytest.mark.parametrize("reply", [
    _named("Una conversación larga sobre el clima de mañana"),  # past TITLE_ACCEPTED_WORDS
    _named("  "),
    _named("Clima\nde mañana"),
    {"choices": [{"message": {"content": "Clima de mañana"}, "finish_reason": "stop"}]},  # not the schema
    {"choices": [{"message": {"content": '{"titulo": "Clima de'}, "finish_reason": "length"}]},
    RuntimeError("server gone"),
])
def test_a_name_the_model_could_not_give_is_no_name(tmp_path: Path, reply) -> None:
    mind, _ = _talked(tmp_path, reply)
    assert mind.title_of(mind.export_session()) == ""


def test_a_name_one_word_past_the_ask_is_kept(tmp_path: Path) -> None:
    mind, _ = _talked(tmp_path, _named("Por qué el cielo es azul"))
    assert mind.title_of(mind.export_session()) == "Por qué el cielo es azul"


def test_quotes_around_the_name_are_left_out(tmp_path: Path) -> None:
    mind, _ = _talked(tmp_path, _named("«Clima de mañana»"))
    assert mind.title_of(mind.export_session()) == "Clima de mañana"


def test_a_conversation_without_a_request_is_not_named_and_the_model_is_not_asked(tmp_path: Path) -> None:
    from test_mind_final import _mind
    mind, server = _mind(tmp_path, [])
    assert mind.title_of(mind.export_session()) == ""
    assert server.bodies == []


def test_the_name_is_not_written_to_the_trace(tmp_path: Path) -> None:
    # the trace keeps no words a private turn kept out; a name made from the conversation is never written there
    mind, _ = _talked(tmp_path, _named("Clima de mañana en Viña"))
    mind.title_of(mind.export_session())
    trace = "".join(p.read_text(encoding="utf-8") for p in tmp_path.rglob("*") if p.is_file())
    assert "Clima de mañana en Viña" not in trace


def test_the_sidecar_answers_session_title_with_the_models_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from baxy_mind import __main__ as sidecar
    written: list[dict] = []
    asked: list[list] = []
    incoming = [{"type": "session.title", "id": 7, "conversation": [{"role": "user", "content": "hola"}]},
                {"type": "session.title", "id": 8, "conversation": "no es una lista"}, None]

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            pass

        def start(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeMind:
        foresee = None
        gave_way = None

        def __init__(self, *args) -> None:
            pass

        def title_of(self, conversation: list) -> str:
            asked.append(conversation)
            return "Saludo inicial"

    class FakeSpeech:
        failure = ""

        def foresee(self, text, done):
            return True

        def prepare(self) -> None:
            pass

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
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    import threading
    import time
    answered = threading.Event()

    def read() -> dict | None:
        if len(incoming) == 2:  # the next request comes once the first is answered: nothing waited meanwhile
            answered.wait(3)
        elif len(incoming) == 1:
            until = time.monotonic() + 3
            while len([m for m in written if m.get("type") == "session.titled"]) < 2 and time.monotonic() < until:
                time.sleep(0.01)
        return incoming.pop(0)

    def write(message: dict) -> None:
        written.append(message)
        if message.get("type") == "session.titled":
            answered.set()

    monkeypatch.setattr(sidecar.protocol, "read_message", read)
    monkeypatch.setattr(sidecar.protocol, "write_message", write)
    assert sidecar.main() == 0
    titled = [m for m in written if m.get("type") == "session.titled"]
    assert titled == [{"type": "session.titled", "id": 7, "title": "Saludo inicial"},
                      {"type": "session.titled", "id": 8, "title": ""}]
    assert asked == [[{"role": "user", "content": "hola"}]]


# NB, 2026-11-08 (30 held-out conversations, stock Qwen3.5-4B): asked in Spanish, the 8 English ones were named in
# Spanish. The ask goes in the language the person spoke (language_id, as the voice reads it).
@pytest.mark.parametrize(("said", "asked_in"), [
    ("whats the difference between weather and climate", "TITLE_ASK_EN"),
    ("que diferencia hay entre el tiempo y el clima", "TITLE_ASK"),
])
def test_the_name_is_asked_in_the_language_the_person_spoke(tmp_path: Path, said: str, asked_in: str) -> None:
    from baxy_mind import mind as mind_module
    from test_mind_final import _mind, _say
    mind, server = _mind(tmp_path, [_say("Weather is short-term; climate is the long average."), _named("Weather and climate")])
    mind.decide(1, said)
    mind.title_of(mind.export_session())
    assert server.bodies[-1]["messages"][-1]["content"] == getattr(mind_module, asked_in)


# Revisión total (M5, 2026-11-09): the name was asked on the request loop with up to TITLE_SECONDS of its own, and only
# looked at whether a request waited before it began; on a GPU that takes 20-60 s a turn (RX 7600 on Vulkan, AMD2) the
# first turn of the new conversation waited behind it. The name's chat gives way as a read ahead does.

class _SlowNames:
    """A llama-server double: the chat that asks for a name (the one with a response_format) is answered ``name_after``
    seconds later, and tells when the mind closed its connection first; any other chat is answered at once."""

    def __init__(self, name_after: float) -> None:
        import threading
        import time
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        self.naming, self.dropped, self.deciding = threading.Event(), threading.Event(), threading.Event()
        self.decided_at: float | None = None
        self.chats: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, value: dict | list) -> None:
                data = json.dumps(value).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802 - http.server's name
                self._json({"status": "ok"} if self.path == "/health" else [])

            def do_POST(self) -> None:  # noqa: N802 - http.server's name
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/tokenize":
                    return self._json({"tokens": [0] * (len(str(body.get("content") or "")) // 4)})
                if self.path == "/apply-template":
                    return self._json({"prompt": json.dumps(body.get("messages"))})
                if self.path != "/v1/chat/completions":
                    return self._json({"timings": {}})
                outer.chats.append(body)
                if "response_format" not in body:
                    if outer.decided_at is None:
                        outer.decided_at = time.perf_counter()
                        outer.deciding.set()
                    return self._json({"choices": [{"finish_reason": "stop", "index": 0,
                                                    "message": {"role": "assistant", "content": "Hola."}}]})
                outer.naming.set()
                until = time.monotonic() + name_after
                self.connection.settimeout(0.05)
                while time.monotonic() < until:
                    try:
                        if self.connection.recv(1) == b"":
                            return outer.dropped.set()
                    except TimeoutError:
                        continue
                    except OSError:
                        return outer.dropped.set()
                self._json(_named("Clima de mañana"))

            def log_message(self, format: str, *args) -> None:  # noqa: A002 - http.server's signature
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.http.daemon_threads = True
        self.port = self.http.server_address[1]
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.http.shutdown()
        self.http.server_close()


NAME_ASK = {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "nombra la conversación"}],
            "tools": [], "max_tokens": 40, "temperature": 0.0, "seed": 0,
            "response_format": {"type": "json_schema", "json_schema": {"name": "titulo", "schema": {}}}}


def _own_server(port: int):
    from baxy_mind.llm_server import LlmServer
    server = LlmServer("model.gguf", "llama-server.exe")
    server.port = port
    server._ready.set()
    return server


def test_a_name_s_chat_gives_way_at_once_to_a_request_that_waits() -> None:
    import threading
    import time
    from baxy_mind.llm_server import Yielded
    llama = _SlowNames(name_after=5.0)
    try:
        server = _own_server(llama.port)
        waiting = threading.Event()
        server.yields = waiting.is_set
        threading.Timer(0.3, waiting.set).start()
        started = time.monotonic()
        with pytest.raises(Yielded):
            server.chat(NAME_ASK, timeout=15.0, gives_way=True)
        assert time.monotonic() - started < 1.5
        assert llama.dropped.wait(2)  # its connection closed: llama-server cancels the task, the slot is the request's
        # With a request already waiting nothing is sent.
        with pytest.raises(Yielded):
            server.chat(NAME_ASK, timeout=15.0, gives_way=True)
        assert len(llama.chats) == 1
    finally:
        llama.close()


def test_with_nothing_waiting_the_name_s_chat_is_answered_and_a_turn_s_own_chat_never_gives_way() -> None:
    llama = _SlowNames(name_after=0.2)
    try:
        server = _own_server(llama.port)
        assert server.chat(NAME_ASK, timeout=15.0, gives_way=True) == _named("Clima de mañana")
        assert not llama.dropped.is_set()
        # A request's own chat is the one the queue's requests wait behind: only what nobody waits for gives way.
        server.yields = lambda: True
        turn = {key: value for key, value in NAME_ASK.items() if key != "response_format"}
        assert server.chat(turn, timeout=15.0)["choices"][0]["message"]["content"] == "Hola."
    finally:
        llama.close()


def test_a_name_that_gave_way_is_no_name_and_its_row_says_so(tmp_path: Path) -> None:
    from baxy_mind.llm_server import Yielded
    mind, server = _talked(tmp_path, Yielded("a request waits"))
    assert mind.title_of(mind.export_session()) == ""
    assert server.gave_way is True  # asked as what nobody waits for
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(row["named"], row["gave_way"]) for row in rows if row.get("stage") == "session.title"] == [(False, True)]


def name_then_turn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name_after: float, turn_after: float) -> dict:
    """The sidecar with its own LlmServer on a _SlowNames: the App asks for the closed conversation's name and, with the
    model ``turn_after`` seconds into writing it, a turn arrives. When each thing happened, from the turn's arrival."""
    import threading
    import time
    from baxy_mind import __main__ as sidecar
    from baxy_mind.mind import Mind
    from test_mind_prefill import TOOLS
    llama = _SlowNames(name_after)
    written: list[tuple[float, dict]] = []
    answered = threading.Event()
    at: dict[str, float] = {}
    incoming = [{"type": "session.title", "id": 7, "conversation": [
        {"role": "user", "content": "qué tiempo hace mañana en viña del mar"},
        {"role": "assistant", "content": "Mañana en Viña: 18 °C y nublado."}]},
        {"type": "turn.decide", "id": 8, "text": "hola"}, None]

    class ReadyMind(Mind):
        def __init__(self, server, trace, system_one=None) -> None:
            super().__init__(server, trace, system_one)
            self.tools = json.loads(json.dumps(TOOLS))
            self.call_tokens = [248058]

    class FakeSpeech:
        failure = ""

        def foresee(self, text, done):
            return True

        def prepare(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeVoice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = FakeSpeech()

        def unsure(self, text: str) -> list:
            return []

        def stop(self) -> None:
            pass

    def read() -> dict | None:
        if len(incoming) == 2:
            assert llama.naming.wait(10)
            time.sleep(turn_after)
            at["turn"] = time.perf_counter()
        elif len(incoming) == 1:
            answered.wait(name_after + 30)
        return incoming.pop(0)

    def write(message: dict) -> None:
        written.append((time.perf_counter(), message))
        if message.get("type") == "turn.result" or (message.get("type") == "error" and message.get("id") == 8):
            answered.set()

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("BAXY_MIND_LLAMA_REMOTE", str(llama.port))  # the double is the server: nothing is launched
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.delenv("BAXY_MIND_SLOT", raising=False)
    monkeypatch.setattr(sidecar, "Mind", ReadyMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", read)
    monkeypatch.setattr(sidecar.protocol, "write_message", write)
    try:
        assert sidecar.main() == 0
        dropped = llama.dropped.wait(2)
    finally:
        llama.close()
    said = {message["type"]: (when, message) for when, message in written if message.get("type") in (
        "session.titled", "turn.result")}
    return {"decision_started_s": (llama.decided_at or float("inf")) - at["turn"],
            "turn_answered_s": said["turn.result"][0] - at["turn"] if "turn.result" in said else float("inf"),
            "name_answered_s": said["session.titled"][0] - at["turn"] if "session.titled" in said else float("inf"),
            "titled": said.get("session.titled", (0.0, {}))[1], "result": said.get("turn.result", (0.0, {}))[1],
            "name_dropped": dropped,
            "order": [message["type"] for _, message in written if message.get("type") in said]}


def test_a_turn_that_comes_while_a_name_is_written_does_not_wait_for_it(tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    from baxy_mind import mind as mind_module
    monkeypatch.setattr(mind_module, "TITLE_SECONDS", 3.0)  # a slow server takes all of it: the test stays short
    seen = name_then_turn(tmp_path, monkeypatch, name_after=10.0, turn_after=0.3)
    assert seen["decision_started_s"] < 1.0
    assert seen["name_dropped"]  # the server is the turn's alone: its task for the name is cancelled
    assert seen["titled"] == {"type": "session.titled", "id": 7, "title": ""}  # the App keeps the first words
    assert seen["order"] == ["session.titled", "turn.result"]
    assert seen["result"]["kind"] == "conversation" and seen["result"]["reply"] == "Hola."
