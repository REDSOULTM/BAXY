"""BAXY Renew al máximo W5 (mind.PREFILL_MARK): once a turn has ended, its conversation is read into the slot as the
next request will show it, so the next decision reads only its own words. The model's prompt does not change: every
body it gets is the same, byte for byte, with and without the read ahead.

The double renders prompts with the model's own chat template (tests/fixtures/qwen35_chat_template.jinja, as the
GGUF BAXY-Qwen3.5-4B-ft-c2e1 carries it) and keeps the slot as llama-server does: a request keeps the cached text up to
where its prompt differs and reads the rest, and what the model wrote stays after the prompt as it was generated."""
import json
import os
import urllib.error
from pathlib import Path

import pytest
from jinja2.sandbox import ImmutableSandboxedEnvironment

from baxy_mind.mind import CLOCK_MARK, PREFILL_MARK, Mind

TEMPLATE = (Path(__file__).parent / "fixtures" / "qwen35_chat_template.jinja").read_text(encoding="utf-8")
TOOLS = [
    {"type": "function", "function": {"name": "app_open", "description": "Open an application.", "parameters": {
        "type": "object", "properties": {"appId": {"type": "string"}, "foreground": {"type": "boolean"}},
        "required": ["appId"]}}},
    {"type": "function", "function": {"name": "ask_user", "description": "Ask the person.", "parameters": {
        "type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
]


def _raise(message: str) -> None:
    raise ValueError(message)


class SlotServer:
    """llama-server's double: the chat template, one slot and what each request had to read again (in characters)."""

    context = 53248

    def __init__(self, replies: list) -> None:
        environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        environment.filters["tojson"] = lambda value, **_: json.dumps(value, ensure_ascii=False)
        environment.globals["raise_exception"] = _raise
        self._template = environment.from_string(TEMPLATE)
        self.replies = replies
        self.bodies: list[dict] = []
        self.prompts: list[str] = []
        self.prefilled: list[str] = []
        self.templates = 0
        self.read: list[int] = []
        self.slot = ""
        self.fail_prefill: Exception | None = None

    def render(self, body: dict) -> str:
        # As llama-server hands them to the template: a call's arguments as an object.
        messages = [{**m, "tool_calls": [{**c, "function": {**c["function"],
                                                           "arguments": json.loads(c["function"]["arguments"])}}
                                         for c in m["tool_calls"]]} if m.get("tool_calls") else m
                    for m in body["messages"]]
        return self._template.render(messages=messages, tools=body.get("tools"), add_generation_prompt=True,
                                     enable_thinking=False)

    def _read(self, prompt: str) -> None:
        kept = len(os.path.commonprefix([self.slot, prompt]))
        self.read.append(len(prompt) - kept)
        self.slot = prompt

    def chat(self, body: dict, **_) -> dict:
        self.bodies.append(json.loads(json.dumps(body)))
        prompt = self.render(body)
        self.prompts.append(prompt)
        self._read(prompt)
        reply = self.replies.pop(0)
        message = reply["choices"][0]["message"]
        written = message.get("content") or ""
        for call in message.get("tool_calls") or []:
            arguments = json.loads(call["function"]["arguments"])
            written += f"<tool_call>\n<function={call['function']['name']}>\n" + "".join(
                f"<parameter={k}>\n{v if isinstance(v, str) else json.dumps(v)}\n</parameter>\n"
                for k, v in arguments.items()) + "</function>\n</tool_call>"
        self.slot += written  # what the model wrote, as it wrote it, after the generation prompt
        return reply

    def read_prefix(self, body: dict, on_progress=None) -> dict:
        return self.chat(body)  # the warm-up's chat: the same reply, streamed with its progress by the real server

    def template(self, body: dict, timeout: float = 10.0) -> str:
        self.templates += 1
        return self.render(body)

    def prefill(self, prompt: str, timeout: float = 60.0) -> dict:
        if self.fail_prefill is not None:
            raise self.fail_prefill
        self.prefilled.append(prompt)
        before = len(self.read)
        self._read(prompt)
        return {"timings": {"cache_n": len(prompt) - self.read[before], "prompt_n": self.read[before], "prompt_ms": 1.0,
                            "predicted_n": 1, "predicted_ms": 0.0}}

    def tokenize(self, text: str) -> list[int]:
        return [0] * (len(text) // 4)


def _call(name: str, arguments: dict) -> dict:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}}]}


def _say(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _mind(tmp_path: Path, replies: list, monkeypatch: pytest.MonkeyPatch) -> tuple[Mind, SlotServer]:
    # A clock that does not move, so two runs of the same conversation send the same text.
    monkeypatch.setattr(Mind, "_clock", lambda self: f"{CLOCK_MARK} jueves 22/10/2026 18:30 hora local]")
    server = SlotServer(replies)
    tmp_path.mkdir(parents=True, exist_ok=True)
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.tools = json.loads(json.dumps(TOOLS))
    mind.call_tokens = [248058]
    return mind, server


def _two_turns(mind: Mind, prefill: bool) -> None:
    mind.decide(1, "abre paint")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "readback", "observed": {
        "appId": "Paint", "foreground": True}}))
    if prefill:
        assert mind.prefill() is True
    mind.decide(3, "¿ya lo abriste?")


def _replies() -> list:
    return [_call("app_open", {"appId": "Paint", "foreground": True}), _say("Abrí Paint."), _say("Sí, Paint está abierto.")]


def test_the_next_decision_reads_only_its_own_words_and_gets_the_same_prompt(tmp_path: Path,
                                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    ahead, server = _mind(tmp_path / "a", _replies(), monkeypatch)
    _two_turns(ahead, prefill=True)
    plain, before = _mind(tmp_path / "b", _replies(), monkeypatch)
    _two_turns(plain, prefill=False)

    # The model gets the same bodies, and so the same prompts, with the read ahead and without it.
    assert server.bodies == before.bodies and server.prompts == before.prompts
    following = server.prompts[-1]
    # What was read ahead is the start of the next prompt to the character, and ends where the new turn begins.
    read_ahead = server.prefilled[0]
    assert following.startswith(read_ahead) and following[len(read_ahead):].startswith(f"<|im_start|>user\n{CLOCK_MARK}")
    assert read_ahead.endswith("<|im_end|>\n") and PREFILL_MARK not in read_ahead
    # Without it the decision read the whole previous turn again: from its first assistant message, whose empty
    # <think></think> the slot holds and the new prompt no longer writes.
    kept, again = following[:len(following) - before.read[-1]], following[len(following) - before.read[-1]:]
    # (characters: «<think>» in the slot and «<tool_call>» in the prompt share their first two)
    assert kept.endswith(f"{CLOCK_MARK} jueves 22/10/2026 18:30 hora local]<|im_end|>\n<|im_start|>user\nabre paint"
                         "<|im_end|>\n<|im_start|>assistant\n<t")
    assert "<function=app_open>" in again and "Abrí Paint." in again
    assert "<think>\n\n</think>\n\n<tool_call>" in before.prompts[1]
    assert "<think>\n\n</think>\n\n<tool_call>" not in following
    # With it, the decision reads only its own turn; the same work was done before it, while BAXY spoke.
    assert server.read[-1] == len(following) - len(read_ahead)
    assert server.read[-1] < before.read[-1] and server.read[-2] + server.read[-1] == before.read[-1]
    row = [json.loads(line) for line in (tmp_path / "a" / "turns.jsonl").read_text(encoding="utf-8").splitlines()
           if '"warm.history"' in line][0]
    assert row["prompt_n"] == server.read[-2] and "text" not in row and "content" not in row
    # P0.8: what the slot already held is traced too, so a broken prefix shows as a small cache_n beside a large prompt_n.
    assert row["cache_n"] == len(read_ahead) - server.read[-2]


def test_no_turn_changes_what_was_read_ahead_of_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # noche 2026-10-27 (P0.8, auditoría del prefijo): whatever only a turn knows (the ear's unsure words, a call waiting
    # for the «sí») goes after what the wake read into the slot, or a long session reads its whole history again.
    turns = [("abre paint", None, None), ("pon música", [("música", 0.4)], None),
             ("no, déjalo", None, {"operation": "app.close", "arguments": {"appId": "Paint"}}),
             ("sube el volumen", [("volumen", 0.5)], {"operation": "file.delete", "arguments": {"path": "a.txt"}})]
    mind, server = _mind(tmp_path, [_say(f"Hecho {n}.") for n in range(len(turns))], monkeypatch)
    for n, (text, unsure, pending) in enumerate(turns):
        assert mind.prefill(clock=True) is True
        first = len(server.prompts)
        mind.decide(n, text, pending, unsure)
        assert server.prompts[first].startswith(server.prefilled[-1]), text


def test_a_confirmation_pressed_after_it_reads_on_from_what_was_read_ahead(tmp_path: Path,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    # The label of a Sí/No is a request of the person's too: the history before it has the same form.
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Paint"}), _say("¿Lo abro?"), _say("Abrí Paint.")],
                         monkeypatch)
    mind.decide(1, "abre paint")
    mind.continue_turn(2, json.dumps({"status": "needs_confirmation"}), final=True)
    assert mind.prefill() is True
    mind.confirm(3, True, "Sí")
    mind.continue_turn(4, json.dumps({"status": "completed", "verification": "readback"}))
    assert server.prompts[-1].startswith(server.prefilled[0])


def test_nothing_is_read_ahead_while_a_turn_waits_or_with_nothing_to_read(tmp_path: Path,
                                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Paint"}), _call("ask_user", {"question": "¿Cuál?"})],
                         monkeypatch)
    assert mind.prefill() is False  # an empty conversation
    mind.decide(1, "abre paint")
    assert mind.prefill() is False  # its call waits for the App's result
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "readback"}))
    assert mind.prefill() is False  # the model asked: the person's words come as that question's result
    mind._turn, mind._beat = None, {"conv": [], "queue": []}
    assert mind.prefill() is False  # a heartbeat is open
    mind._beat = None
    monkeypatch.setenv("BAXY_RENEW_PREFILL", "0")
    assert mind.prefill() is False
    assert server.templates == 0 and server.prefilled == []


def test_a_read_ahead_that_fails_leaves_the_conversation_as_it_was(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    mind, server = _mind(tmp_path, [_say("Hola."), _say("Bien.")], monkeypatch)
    mind.decide(1, "hola")
    kept = json.dumps(mind.conversation, ensure_ascii=False)
    server.fail_prefill = urllib.error.URLError("refused")
    assert mind.prefill() is False
    assert json.dumps(mind.conversation, ensure_ascii=False) == kept
    assert mind.decide(2, "¿cómo estás?")["reply"] == "Bien."
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["failure"] for r in rows if r["stage"] == "warm.history"] == ["URLError"]
    assert mind.gave_way is None


def test_a_read_ahead_that_gives_way_says_so_and_not_as_a_failure(tmp_path: Path,
                                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    # Revisión de NB-R1-X4: giving way to a request that waits is not a failure; the mind keeps that it is owed.
    from baxy_mind.llm_server import Yielded
    mind, server = _mind(tmp_path, [_say("Hola.")], monkeypatch)
    mind.decide(1, "hola")
    server.fail_prefill = Yielded("a request waits")
    assert mind.prefill() is False and mind.gave_way is False
    server.fail_prefill = None
    assert mind.prefill() is True and mind.gave_way is None
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()
            if '"warm.history"' in line]
    assert rows[0]["yielded"] is True and "failure" not in rows[0]
    assert "yielded" not in rows[1] and "failure" not in rows[1]


def test_a_read_ahead_past_its_budget_goes_on_from_what_the_slot_read_and_not_for_ever(tmp_path: Path,
                                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    # uso-124 (RX 7600, 2026-11-05): ~100 tokens/s and a history of 5,000 tokens more after a web.fetch. The read ahead
    # ended at its 24 s and nothing went on with it, so 45 s later the next decision read it, ended at its own 24 s, and
    # the person heard nothing. The server keeps what a cancelled prompt read, so another round goes on from there.
    from baxy_mind.mind import PREFILL_ROUNDS

    mind, server = _mind(tmp_path, [_say("Hola.")], monkeypatch)
    mind.decide(1, "hola")
    server.fail_prefill = TimeoutError("the request's time ran out")
    for _ in range(PREFILL_ROUNDS - 1):
        assert mind.prefill(mind.gave_way or False) is False and mind.gave_way is False
    assert mind.prefill(False) is False and mind.gave_way is None  # as a person's next turn would read it itself
    server.fail_prefill = None
    assert mind.prefill() is True and mind.gave_way is None
    server.fail_prefill = TimeoutError("the request's time ran out")
    assert mind.prefill() is False and mind.gave_way is False  # a new history has its rounds again


def test_a_read_ahead_that_fails_otherwise_is_not_read_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mind, server = _mind(tmp_path, [_say("Hola.")], monkeypatch)
    mind.decide(1, "hola")
    server.fail_prefill = OSError("the server fell")
    assert mind.prefill() is False and mind.gave_way is None


def _sidecar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, incoming: list, events: list[str]):
    """The sidecar's loop on a fake server, mind and voice, reading ``incoming`` and writing into ``events``."""
    from baxy_mind import __main__ as sidecar

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

        def decide(self, request_id, text, pending, unsure=None, front=None, named=None):
            return {"type": "turn.result", "id": request_id}

        def continue_turn(self, request_id, observation, final, beat):
            return {"type": "turn.result", "id": request_id}

        def confirm(self, request_id, approve, label):
            return {"type": "turn.result", "id": request_id}

        def new_session(self) -> None:
            pass

        def load_session(self, conversation) -> None:
            pass

        def end_beat(self) -> None:
            pass

        def prefill(self) -> bool:
            events.append("prefill")
            return True

    class FakeSpeech:
        failure = ""  # a voice that can speak (the hello offers voice.speak)
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
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")  # the server is a fake
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", lambda: incoming.pop(0))
    monkeypatch.setattr(sidecar.protocol, "write_message",
                        lambda message: events.append(str(message.get("type"))
                                                      + (f":{message['id']}" if "id" in message else "")))
    return sidecar, FakeMind


def test_the_sidecar_reads_ahead_only_after_answering_and_only_after_a_turn_or_a_load(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    incoming = [{"type": "turn.decide", "id": 1, "text": "hola"}, {"type": "session.new", "id": 2},
                {"type": "turn.continue", "id": 3, "observation": "{}"}, {"type": "session.load", "id": 4,
                                                                         "conversation": []},
                {"type": "turn.beat.end", "id": 5}, {"type": "turn.confirm", "id": 6, "approve": True, "label": "Sí"},
                None]
    sidecar, _ = _sidecar(tmp_path, monkeypatch, incoming, events)
    assert sidecar.main() == 0
    assert [e for e in events if e != "hello"] == [
        "turn.result:1", "prefill", "session.ready:2", "turn.result:3", "prefill", "session.ready:4", "prefill",
        "turn.beat.ended:5", "prefill", "turn.result:6"]


def test_a_request_that_fails_leaves_its_reason_in_the_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # P1.13: a decide past its budget answered request_failed, and its reason went only to the stderr the App drops.
    events: list[str] = []
    incoming = [{"type": "turn.decide", "id": 7, "text": "hola"}, None]
    sidecar, fake_mind = _sidecar(tmp_path, monkeypatch, incoming, events)
    rows: list[tuple] = []

    def decide(self, request_id, text, pending, unsure=None, front=None, named=None):
        raise TimeoutError("the request's time budget is spent")

    monkeypatch.setattr(fake_mind, "decide", decide)
    monkeypatch.setattr(fake_mind, "_log", lambda self, stage, started, reply, **fields: rows.append((stage, fields)),
                        raising=False)
    assert sidecar.main() == 0
    assert "error:7" in events
    assert rows == [("request.failed", {"kind": "turn.decide",
                                        "failure": "TimeoutError(\"the request's time budget is spent\")"})]


@pytest.mark.parametrize(("error", "code"), [(TimeoutError("timed out"), "request_timed_out"),
                                             (RuntimeError("no open turn to continue"), "request_failed")])
def test_a_request_past_its_budget_says_so_in_its_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                         error: Exception, code: str) -> None:
    # R7-NB-1 (CU C03): the App asks again for a decision whose request ran past its budget, never for one that failed
    # otherwise (a context with no room left, a fault), which would fail the same way.
    sidecar, fake_mind = _sidecar(tmp_path, monkeypatch, [{"type": "turn.continue", "id": 8, "observation": "{}"}, None],
                                  [])
    codes: list = []
    monkeypatch.setattr(sidecar.protocol, "write_message", lambda message: codes.append(message.get("code")))

    def continue_turn(self, request_id, observation, final=False, beat=False):
        raise error

    monkeypatch.setattr(fake_mind, "continue_turn", continue_turn, raising=False)
    monkeypatch.setattr(fake_mind, "_log", lambda self, stage, started, reply, **fields: None, raising=False)
    assert sidecar.main() == 0
    assert code in codes


@pytest.mark.parametrize("ready", [True, False])
def test_the_sidecar_answers_a_turn_s_notice_once_its_audio_is_kept_and_none_without_a_voice(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ready: bool) -> None:
    # Feria 2026-10-27: the notice is the model's phrase for the call the App runs (turn.notice); the voice.speak that
    # follows finds its audio, and with no voice loaded the model is not asked.
    import threading
    from concurrent.futures import Future
    from baxy_mind import __main__ as sidecar
    replies: list[dict] = []
    asked: list[str] = []
    incoming = [{"type": "turn.notice", "id": 1}, None]

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
        notices_are_slow = False

        def __init__(self, *args) -> None:
            pass

        def notice_of(self) -> str:
            asked.append("notice")
            return "Busco vuelos a Lima."

    class FakeSpeech:
        failure = ""  # a voice that can speak (the hello offers voice.speak)
        def __init__(self) -> None:
            self.ready = ready
            self.kept = ""

        def set_notice(self, text: str) -> Future:
            self.kept = text
            done: Future = Future()
            done.set_result(None)
            return done

        def foresee(self, text, done):
            return True

        def close(self) -> None:
            pass

    class FakeVoice:
        def __init__(self, *args, **kwargs) -> None:
            self.speech = FakeSpeech()

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
    answered = threading.Event()

    def read() -> dict | None:
        if not incoming[0]:
            answered.wait(5)  # stdin closes only after the notice was answered: nothing else waits behind it
        return incoming.pop(0)

    def write(message: dict) -> None:
        replies.append(message)
        if message.get("type") == "turn.notice.result":
            answered.set()

    monkeypatch.setattr(sidecar.protocol, "read_message", read)
    monkeypatch.setattr(sidecar.protocol, "write_message", write)
    assert sidecar.main() == 0
    notice = [r for r in replies if r.get("type") == "turn.notice.result"]
    assert notice == [{"type": "turn.notice.result", "id": 1, "notice": "Busco vuelos a Lima." if ready else "",
                       "slow": False}]
    assert asked == (["notice"] if ready else [])


def _slot_server(answer: bool):
    """A local llama-server double for one POST: it answers at once, or, as one still reading a long prompt, answers
    nothing and tells when the client closed its connection (it gives up after 5 s)."""
    import http.server
    import threading
    closed = threading.Event()
    posted: list[tuple[str, dict]] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - http.server's name
            posted.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            if answer:
                data = b'{"timings": {}}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.connection.settimeout(5)
            try:
                if self.connection.recv(1) == b"":
                    closed.set()
            except OSError:
                pass

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - http.server's signature
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, closed, posted


def test_a_read_ahead_gives_way_at_once_to_a_request_that_waits() -> None:
    # NB-R1, sesión larga en vivo (2026-10-27): a read ahead the server was slow to read (CPU at 90 %) ran out its 24 s
    # budget while the person's turn waited behind it. It ends as soon as a request waits, and its connection closes,
    # so llama-server drops the task.
    import threading
    import time
    from baxy_mind.llm_server import LlmServer, Yielded
    httpd, closed, posted = _slot_server(answer=False)
    try:
        server = LlmServer("model.gguf", "llama-server.exe")
        server.port = httpd.server_address[1]
        server._ready.set()
        waiting = threading.Event()
        server.yields = waiting.is_set
        threading.Timer(0.3, waiting.set).start()
        started = time.monotonic()
        with pytest.raises(Yielded):
            server.prefill("<|im_start|>system\nX<|im_end|>\n")
        assert time.monotonic() - started < 1.5
        assert closed.wait(2) and server.resident is None
        # With a request already waiting nothing is sent.
        with pytest.raises(Yielded):
            server.prefill("<|im_start|>system\nY<|im_end|>\n")
        assert len(posted) == 1
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_server_reads_the_text_into_its_one_slot_and_writes_nothing() -> None:
    # With nothing waiting the read ahead goes to its end, and the slot then holds its text.
    from baxy_mind.llm_server import LlmServer
    httpd, _, posted = _slot_server(answer=True)
    try:
        server = LlmServer("model.gguf", "llama-server.exe")
        server.port = httpd.server_address[1]
        server._ready.set()
        assert server.prefill("<|im_start|>system\nX<|im_end|>\n") == {"timings": {}}
        assert posted == [("/completion", {"prompt": "<|im_start|>system\nX<|im_end|>\n", "n_predict": 1,
                                           "temperature": 0.0, "cache_prompt": True, "id_slot": 0})]
        assert server.resident == "<|im_start|>system\nX<|im_end|>\n"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_the_sidecar_s_read_ahead_gives_way_while_a_request_waits(tmp_path: Path,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    import time
    from baxy_mind import __main__ as sidecar
    servers: list = []
    seen: list[bool] = []
    asked = threading.Event()
    incoming = [{"type": "turn.decide", "id": 1, "text": "hola"}, {"type": "turn.decide", "id": 2, "text": "y?"},
                None]

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            servers.append(self)

        def start(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeMind:
        foresee = None
        gave_way = None

        def __init__(self, *args) -> None:
            pass

        def decide(self, request_id, text, pending, unsure=None, front=None, named=None):
            return {"type": "turn.result", "id": request_id}

        def prefill(self) -> bool:
            if not seen:  # after the first turn: nothing waits, then the second turn comes
                seen.append(servers[0].yields())
                asked.set()
                until = time.monotonic() + 2
                while not servers[0].yields() and time.monotonic() < until:
                    time.sleep(0.01)
                seen.append(servers[0].yields())
            return False

    class FakeSpeech:
        failure = ""  # a voice that can speak (the hello offers voice.speak)
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
            asked.wait(5)
        return incoming.pop(0)

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", read)
    monkeypatch.setattr(sidecar.protocol, "write_message", lambda message: None)
    assert sidecar.main() == 0
    assert seen == [False, True]


def test_each_turn_row_says_how_long_its_prompt_was_and_how_much_of_it_is_the_prefix(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Noche P0.5: prompt_n alone is what was read again; with the whole prompt and the prefix (tools and system) the
    # trace splits every prompt into prefix, history and what is new, and shows the turns a cut made read again.
    reply = _say("Hola.")
    reply.update(timings={"prompt_n": 40, "prompt_ms": 50.0, "predicted_n": 3, "predicted_ms": 9.0},
                 usage={"prompt_tokens": 39040})
    mind, _ = _mind(tmp_path, [reply], monkeypatch)
    mind.prefix_tokens = 38500
    mind.decide(1, "hola")
    row = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_bytes().splitlines()
           if b'"turn.decide"' in line][0]
    assert (row["prompt_n"], row["prompt_tokens"], row["prefix_n"]) == (40, 39040, 38500)


def test_the_sidecar_reads_again_once_a_request_it_gave_way_to_is_answered(tmp_path: Path,
                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    # Revisión de NB-R1-X4: the App asks session.export after every turn; the read ahead gives way to it and is read
    # again once it is answered and nothing waits, so the next decision does not read the conversation cold.
    import threading
    import time
    from baxy_mind import __main__ as sidecar
    servers: list = []
    events: list[str] = []
    done = threading.Event()
    incoming = [{"type": "turn.decide", "id": 1, "text": "hola"}, {"type": "session.export", "id": 2}, None]

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            servers.append(self)

        def start(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeMind:
        foresee = None
        gave_way = None

        def __init__(self, *args) -> None:
            pass

        def decide(self, request_id, text, pending, unsure=None, front=None, named=None):
            return {"type": "turn.result", "id": request_id}

        def export_session(self) -> list:
            return []

        def prefill(self, clock: bool = False) -> bool:
            self.gave_way = None
            if "gave way" not in events:  # the App's export comes while it reads
                until = time.monotonic() + 2
                while not servers[0].yields() and time.monotonic() < until:
                    time.sleep(0.01)
                events.append("gave way")
                self.gave_way = clock
                return False
            events.append("prefill")
            done.set()
            return True

    class FakeSpeech:
        failure = ""  # a voice that can speak (the hello offers voice.speak)
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
        if len(incoming) == 1:
            done.wait(3)  # the App stays open until it was read again (or it never is)
        return incoming.pop(0)

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", read)
    monkeypatch.setattr(sidecar.protocol, "write_message",
                        lambda message: events.append(str(message.get("type"))
                                                      + (f":{message['id']}" if "id" in message else "")))
    assert sidecar.main() == 0
    assert [e for e in events if e != "hello"] == ["turn.result:1", "gave way", "session.exported:2", "prefill"]


def test_the_sidecar_does_not_read_again_while_an_early_decision_is_held(tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    # The mind holds the early decision's own state then (early.set_aside): it is read once that one is put back.
    import threading
    import time
    from baxy_mind import __main__ as sidecar
    servers: list = []
    events: list[str] = []
    done = threading.Event()
    incoming = [{"type": "turn.decide", "id": 1, "text": "hola"}, {"type": "session.export", "id": 2}, None]

    class FakeServer:
        REQUEST_SECONDS = 24.0
        name = "model.gguf"
        deadline = None

        def __init__(self, *args, **kwargs) -> None:
            servers.append(self)

        def start(self) -> None:
            pass

        def close(self) -> None:
            pass

    class FakeMind:
        foresee = None
        gave_way = None

        def __init__(self, *args) -> None:
            pass

        def export_session(self) -> list:
            return []

        def prefill(self, clock: bool = False) -> bool:
            self.gave_way = None
            if "gave way" not in events:
                until = time.monotonic() + 2
                while not servers[0].yields() and time.monotonic() < until:
                    time.sleep(0.01)
                events.append("gave way")
                self.gave_way, held[0] = clock, time.monotonic() + 0.3  # an early decision is held meanwhile
                return False
            events.append("prefill")
            done.set()
            return True

    held = [0.0]

    class FakeAnticipation:
        warm = False

        def __init__(self, *args, **kwargs) -> None:
            pass

        def settle(self, *args) -> None:
            return None

        def decide(self, request_id, *args) -> dict:
            return {"type": "turn.result", "id": request_id}

        def patience(self) -> float | None:
            return max(0.0, held[0] - time.monotonic()) if held[0] else None

        def expire(self) -> None:
            if held[0] and time.monotonic() >= held[0]:
                held[0] = 0.0
                events.append("expired")

    class FakeSpeech:
        failure = ""  # a voice that can speak (the hello offers voice.speak)
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
        if len(incoming) == 1:
            done.wait(3)
        return incoming.pop(0)

    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "model.gguf")
    monkeypatch.setenv("BAXY_MIND_LLAMA_SERVER", "llama-server.exe")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("BAXY_S1_GGUF", raising=False)
    monkeypatch.setattr(sidecar, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(sidecar, "LlmServer", FakeServer)
    monkeypatch.setattr(sidecar, "Mind", FakeMind)
    monkeypatch.setattr(sidecar, "Anticipation", FakeAnticipation)
    monkeypatch.setattr(sidecar, "Voice", FakeVoice)
    monkeypatch.setattr(sidecar.protocol, "read_message", read)
    monkeypatch.setattr(sidecar.protocol, "write_message",
                        lambda message: events.append(str(message.get("type"))
                                                      + (f":{message['id']}" if "id" in message else "")))
    assert sidecar.main() == 0
    assert [e for e in events if e != "hello"] == ["turn.result:1", "gave way", "session.exported:2", "expired",
                                                   "prefill"]
