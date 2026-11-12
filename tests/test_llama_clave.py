"""PRV1 (revisión de privacidad 2026-11-09, PRIV-04): BAXY's llama-server started with no key, on the loopback, and by
default it «reflects any Origin header back with credentials allowed» (llama.cpp, tools/server/README.md, «CORS»): a
page open in a browser of this PC, or another program, could ask the model and read or erase the slot that holds the
conversation. Every server BAXY starts takes a key at random («--api-key KEY … (env: LLAMA_API_KEY)», the same README)
in its environment, never on its command line, and every request of BAXY's carries it. With doubles: the server itself
is tried on the notebook (llama-server answers 401 «Invalid API Key» without it)."""
import io
import json
import urllib.request
from pathlib import Path

from baxy_mind import external_model, llm_server, system_one


class _Started:
    """What a start gave subprocess.Popen."""

    seen: list[tuple[list[str], dict]] = []

    def __init__(self, command, **kwargs) -> None:
        _Started.seen.append((list(command), kwargs))
        self.returncode = None

    def poll(self) -> int | None:
        return None

    def kill(self) -> None:
        pass


class _Reply(io.BytesIO):
    status = 200


def _mind_server(monkeypatch, tmp_path: Path) -> llm_server.LlmServer:
    _Started.seen = []
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(tmp_path / "slots"))
    monkeypatch.setattr(llm_server.subprocess, "Popen", _Started)
    monkeypatch.setattr(llm_server.threading.Thread, "start", lambda self: None)
    return llm_server.LlmServer("model.gguf", "llama-server.exe")


def test_the_minds_server_starts_with_a_key_in_its_environment_and_none_on_its_command_line(monkeypatch, tmp_path) -> None:
    server = _mind_server(monkeypatch, tmp_path)
    server.start()
    command, given = _Started.seen[0]
    assert len(server.key) >= 32
    assert given["env"]["LLAMA_API_KEY"] == server.key
    assert given["env"]["LOCALAPPDATA"] == str(tmp_path)  # the rest of the environment is this process's
    assert server.key not in " ".join(command) and "--api-key" not in command
    assert ["--host", "127.0.0.1"] == command[command.index("--host"):command.index("--host") + 2]


def test_each_start_of_baxy_has_another_key_and_the_apps_key_is_taken_when_given(monkeypatch, tmp_path) -> None:
    first = _mind_server(monkeypatch, tmp_path).key
    second = _mind_server(monkeypatch, tmp_path).key
    assert first != second
    monkeypatch.setenv("BAXY_MIND_LLAMA_KEY", "la-de-la-app")
    assert _mind_server(monkeypatch, tmp_path).key == "la-de-la-app"
    assert llm_server.server_key({"BAXY_MIND_LLAMA_KEY": "  "}) not in ("", "  ")


def test_every_request_of_the_mind_to_its_server_carries_the_key(monkeypatch, tmp_path) -> None:
    server = _mind_server(monkeypatch, tmp_path)
    server._ready.set()
    asked: list[urllib.request.Request] = []
    slots = [{"id": 0, "id_task": 1, "n_prompt_tokens": 2, "next_token": [{"n_decoded": 3}]}]
    answers = {"/health": {"status": "ok"}, "/props": {"total_slots": 1}, "/slots": slots,
               "/tokenize": {"tokens": [1]}, "/apply-template": {"prompt": "p"},
               "/v1/chat/completions": {"choices": [{"message": {"content": "Hola."}}]}}

    def urlopen(request, timeout):
        assert isinstance(request, urllib.request.Request), f"a bare address carries no key: {request}"
        asked.append(request)
        return _Reply(json.dumps(answers[request.selector.split("?")[0]]).encode("utf-8"))

    monkeypatch.setattr(llm_server.urllib.request, "urlopen", urlopen)
    server.tokenize("hola")
    server.template({"messages": [], "tools": [], "chat_template_kwargs": {}})
    server.chat({"messages": []})
    server._look(None)
    server.slot = 0
    server._slot_missing()
    server.slot = 1
    server._slot_missing()
    server.prefix_key({"warm": 1})
    server._wait_health()

    paths = {request.selector for request in asked}
    assert {"/tokenize", "/apply-template", "/v1/chat/completions", "/slots", "/props", "/health"} <= paths
    assert all(request.get_header("Authorization") == f"Bearer {server.key}" for request in asked)


class _Line:
    """A connection of http.client's: what was asked through it, and one reply."""

    asked: list[tuple[str, dict]] = []
    reply = b"{}"

    def __init__(self, host, port, timeout=None) -> None:
        self.sock = self

    def settimeout(self, seconds) -> None:
        pass

    def request(self, method, url, body=None, headers=None) -> None:
        _Line.asked.append((url, dict(headers or {})))

    def getresponse(self) -> _Reply:
        return _Reply(_Line.reply)

    def close(self) -> None:
        pass


def test_the_read_ahead_and_the_streams_own_connections_carry_the_key_too(monkeypatch, tmp_path) -> None:
    # Revisión a ciegas de PRV1: this only read _headers() and counted the source's text, so a connection of
    # http.client's opened without the key (the read ahead's, a waited turn's stream and its reply) passed. The three
    # are asked here through a double, as the mind asks them.
    server = _mind_server(monkeypatch, tmp_path)
    server._ready.set()
    _Line.asked = []
    monkeypatch.setattr(llm_server.http.client, "HTTPConnection", _Line)
    monkeypatch.setattr(llm_server.select, "select", lambda read, write, failed, timeout: (read, [], []))

    def urlopen(request, timeout):
        raise AssertionError(f"not through a connection of its own: {request.selector}")

    monkeypatch.setattr(llm_server.urllib.request, "urlopen", urlopen)
    patient = server.REQUEST_SECONDS + 60

    assert server.prefill("lo que el turno traerá") == {}
    server.advanced = lambda: None  # a turn someone waits for: its stream and its reply on their own connections
    _Line.reply = b'data: {"choices": [{"delta": {"content": "Hola."}}]}\n\ndata: [DONE]\n'
    streamed = server.chat({"messages": []}, timeout=patient, on_text=lambda text, done: False)
    assert streamed["choices"][0]["message"]["content"] == "Hola."
    _Line.reply = b'{"choices": [{"message": {"content": "Hola."}}]}'
    assert server.chat({"messages": [], "logprobs": True}, timeout=patient)["choices"][0]["message"]["content"] == "Hola."

    assert [path for path, _headers in _Line.asked] == ["/completion", "/v1/chat/completions", "/v1/chat/completions"]
    assert all(headers.get("Authorization") == f"Bearer {server.key}" for _path, headers in _Line.asked)

    assert server._headers() == {"Content-Type": "application/json", "Authorization": f"Bearer {server.key}"}
    source = Path(llm_server.__file__).read_text(encoding="utf-8")
    # No request is built beside the two that carry the key (_headers, _get): a new one written by hand would go without.
    assert source.count('"Content-Type": "application/json"') == 1
    assert source.count("urllib.request.urlopen(f\"") == 0 and source.count("urlopen(\"http") == 0


def test_system_ones_server_starts_with_a_key_and_its_question_carries_it(monkeypatch, tmp_path) -> None:
    _Started.seen = []
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(system_one.subprocess, "Popen", _Started)
    one = system_one.SystemOne("s1.gguf", "llama-server.exe")
    one._launch()
    command, given = _Started.seen[0]
    assert given["env"]["LLAMA_API_KEY"] == one.key and one.key not in " ".join(command)

    asked: list[urllib.request.Request] = []

    def urlopen(request, timeout):
        asked.append(request)
        return io.BytesIO(b'{"answers": {"operacion": {"choice": "responder_con_palabras"}}}')

    monkeypatch.setattr(system_one.urllib.request, "urlopen", urlopen)
    assert one._ask("hola", None, {"responder_con_palabras": "x"}, 1.0) == {"choice": "responder_con_palabras"}
    assert asked[0].get_header("Authorization") == f"Bearer {one.key}"


def test_the_engine_of_another_model_starts_with_a_key_the_translator_carries(monkeypatch, tmp_path) -> None:
    _Started.seen = []
    monkeypatch.setattr(external_model.subprocess, "Popen", _Started)
    monkeypatch.setattr(external_model, "_end_with_this_process", lambda process: None)
    monkeypatch.setattr(llm_server, "declared_build", lambda path: "b11609")
    monkeypatch.setattr(llm_server, "declared_backend", lambda path, build: "cuda")
    asked: list = []

    def direct(request, timeout):
        asked.append(request)
        return io.BytesIO(b"{}")

    monkeypatch.setattr(external_model, "_direct", direct)
    monkeypatch.setattr(external_model, "_show", lambda url, model: {
        "modelfile": "FROM " + str(tmp_path / "modelo.gguf"), "model_info": {"x.context_length": 4096}})

    class Declares:
        context, num_ctx = 4096, 4096

    monkeypatch.setattr(external_model, "Ollama", lambda url, model, context: Declares())
    backend, engine, refusal = external_model.local_backend(
        "http://127.0.0.1:11434", "otro:latest", 16384, 0, str(tmp_path / "llama-server.exe"))

    command, given = _Started.seen[0]
    assert refusal is None and len(engine.key) >= 32
    assert given["env"]["LLAMA_API_KEY"] == engine.key and engine.key not in " ".join(command)
    assert backend.key == engine.key and backend.headers()["Authorization"] == f"Bearer {engine.key}"
    probe = next(request for request in asked if not isinstance(request, str))
    assert probe.get_header("Authorization") == f"Bearer {engine.key}"


def test_a_closed_conversations_name_asked_aside_carries_the_key_too(monkeypatch, tmp_path) -> None:
    # INT21: MEN1 (M5) asks that name on a connection of its own that gives way to a turn (LlmServer._aside); written
    # beside PRV1, its request went without the key, and llama-server answers such a request 401.
    server = _mind_server(monkeypatch, tmp_path)
    monkeypatch.setattr(server, "wait_ready", lambda timeout: None)
    monkeypatch.setattr(server, "yields", lambda: False)
    sent: list[dict] = []

    class Connection:
        def __init__(self, host, port, timeout) -> None:
            self.sock = object()

        def request(self, method, selector, data, headers) -> None:
            sent.append(dict(headers))

        def getresponse(self) -> _Reply:
            return _Reply(b'{"choices": [{"message": {"content": "Las alarmas de la semana"}}]}')

        def close(self) -> None:
            pass

    monkeypatch.setattr(llm_server.http.client, "HTTPConnection", Connection)
    monkeypatch.setattr(llm_server.select, "select", lambda read, write, error, wait: (read, [], []))
    reply = server.chat({"messages": []}, timeout=30, gives_way=True)
    assert reply["choices"][0]["message"]["content"] == "Las alarmas de la semana"
    assert len(sent) == 1 and sent[0].get("Authorization") == f"Bearer {server.key}"
