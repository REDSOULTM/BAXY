"""Estabilización A (2026-10-11): the decider's reply to a request never depends on what its slot evaluated before.

Evidence (r31-m1, «mandale a Ron92 que si se conecta a las 9 pa jugar»): the mind built the same request byte for byte
in three commits, and it came out ``message.send`` or ``message.draft`` depending on the context checkpoint
llama-server resumed the hybrid model from (161 or 216 tokens evaluated); the previous decision's length, from
another conversation, set that checkpoint, and the first word of the rewrite was a 0.004-0.17 nat tie. The decider's
slot is now put in one saved state (the prefix every decision shares) before each decision: restored from the
server's slot file, built and saved the first time.
"""

from __future__ import annotations

import json
import time
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from baxy_mind import llm
from baxy_mind import llm_settings
from baxy_mind.llm import LlmRuntime
from baxy_mind.llm_transport import ChatCompletionConnectionPool, SlotState, post_chat_completion, prepare_slot_state

ENDPOINT = "http://127.0.0.1:39000"
TOOLS = (("app.open", "Abre una aplicación."), ("message.send", "Envía un mensaje."))
SIGNATURES = {"app.open": ("appId",), "message.send": ("text",)}


class _Server:
    """A llama-server seen from the wire: every request (route, body); a save writes the slot file."""

    def __init__(self, directory: Path, refuse_restore: bool = False) -> None:
        self.directory = directory
        self.refuse_restore = refuse_restore
        self.refuse_chat = False
        self.refuse_save = False
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def connection(self, *_args: object, **_kwargs: object) -> Any:
        server = self

        class Response:
            reason = "OK"
            headers: dict[str, str] = {}
            will_close = False

            def __init__(self, status: int, body: dict[str, Any]) -> None:
                self.status = status
                self.body = body

            def read(self) -> bytes:
                return json.dumps(self.body).encode("utf-8")

            def close(self) -> None:
                return None

        class Connection:
            sock = MagicMock()
            pending: Response | None = None

            def request(self, _method: str, path: str, *, body: bytes, headers: dict[str, str]) -> None:
                del headers
                data = json.loads(body.decode("utf-8"))
                server.sent.append((path, data))
                if path.endswith("action=save") and not server.refuse_save:
                    (server.directory / data["filename"]).write_bytes(b"state")
                refused = (
                    (path.endswith("action=restore") and server.refuse_restore)
                    or (path.endswith("completions") and server.refuse_chat)
                    or (path.endswith("action=save") and server.refuse_save)
                )
                reply = {"choices": [{"message": {"content": "{}"}}]} if path.endswith("completions") else {}
                self.pending = Response(400 if refused else 200, {"error": "invalid"} if refused else reply)

            def getresponse(self) -> Response:
                assert self.pending is not None
                return self.pending

            def close(self) -> None:
                return None

        return Connection()


def _decide(server: _Server, pool: ChatCompletionConnectionPool, state: SlotState, text: str) -> None:
    with patch("baxy_mind.llm_transport.http.client.HTTPConnection", side_effect=server.connection):
        post_chat_completion(
            {"messages": [{"role": "system", "content": "catálogo"}, {"role": "user", "content": text}]},
            endpoint_for_attempt=lambda: ENDPOINT,
            timeout_for_attempt=lambda: 1.0,
            connection_pool=pool,
            reserved_slot=True,
            slot_state=state,
        )


def _settled(pool: ChatCompletionConnectionPool) -> None:
    """Wait for the slot's restore after the reply (``baxy-slot-restore``) to hand the slot back."""

    deadline = time.monotonic() + 5
    while pool._busy_slots and time.monotonic() < deadline:
        time.sleep(0.005)
    assert not pool._busy_slots


def _routes(server: _Server) -> list[str]:
    return [path for path, _ in server.sent]


CHAT, RESTORE, SAVE = "/v1/chat/completions", "/slots/2?action=restore", "/slots/2?action=save"


def test_every_decision_starts_from_the_one_saved_state(tmp_path: Path) -> None:
    server = _Server(tmp_path)
    pool = ChatCompletionConnectionPool(max_connections=3, server_slots=True)
    state = SlotState(tmp_path / "decider-a.bin", {"prompt": "<sistema>catálogo<fin>", "n_predict": 1})
    _decide(server, pool, state, "abre discord porfa")
    _settled(pool)
    # The first time the prefix is evaluated on the decider's slot and saved there; once the reply is handed over,
    # the slot is put back in that state.
    assert _routes(server) == ["/completion", SAVE, CHAT, RESTORE]
    assert server.sent[0][1] == {"prompt": "<sistema>catálogo<fin>", "n_predict": 1, "id_slot": 2}
    assert server.sent[-1][1] == {"filename": "decider-a.bin"}
    # Whatever the slot evaluated last (a long decision, a short one), the next one finds it in the same state.
    for text in ("x" * 4000, "mandale a Ron92 que si se conecta a las 9 pa jugar", "sí"):
        server.sent.clear()
        _decide(server, pool, state, text)
        _settled(pool)
        assert _routes(server) == [CHAT, RESTORE]
        assert server.sent[0][1]["id_slot"] == 2 and server.sent[0][1]["messages"][-1]["content"] == text
    pool.close()


def test_a_slot_not_put_back_is_restored_before_the_request(tmp_path: Path) -> None:
    server = _Server(tmp_path)
    pool = ChatCompletionConnectionPool(max_connections=3, server_slots=True)
    state = SlotState(tmp_path / "decider-a.bin", {"prompt": "p", "n_predict": 1})
    state.path.write_bytes(b"state")
    # A decision that failed (or was cancelled) leaves its slot as it was: nothing is restored after it.
    server.refuse_chat = True
    with pytest.raises(urllib.error.HTTPError):
        _decide(server, pool, state, "abre discord")
    _settled(pool)
    assert _routes(server) == [RESTORE, CHAT]
    server.sent.clear()
    server.refuse_chat = False
    _decide(server, pool, state, "abre discord")
    _settled(pool)
    assert _routes(server) == [RESTORE, CHAT, RESTORE]
    pool.close()


def test_a_replaced_server_builds_the_state_again(tmp_path: Path) -> None:
    """Revisión A H1 (redpc): on a new server a restored file met a slot without the decider's adapter, the server
    cleared it when the decision brought the adapter and the first decision was evaluated whole (0+6827, another
    reply). The runtime drops the saved states with the server it retires; its successor builds them again."""

    runtime = object.__new__(LlmRuntime)
    runtime._decider_state_dir = tmp_path
    runtime._process = None
    pool = ChatCompletionConnectionPool(max_connections=3, server_slots=True)
    runtime._http_connection_pool = pool
    state = SlotState(tmp_path / "decider-a.bin", {"prompt": "p", "n_predict": 1, "cache_prompt": False})
    state.path.write_bytes(b"state")
    (tmp_path / "owner.lock").write_bytes(b"")
    server = _Server(tmp_path)
    _decide(server, pool, state, "abre discord")
    _settled(pool)
    assert _routes(server) == [RESTORE, CHAT, RESTORE]
    runtime._stop_owned_process()
    assert not state.path.exists() and (tmp_path / "owner.lock").exists()
    server.sent.clear()
    _decide(server, pool, state, "abre discord")
    _settled(pool)
    assert _routes(server) == ["/completion", SAVE, CHAT, RESTORE]
    pool.close()


def test_a_server_that_cannot_save_is_asked_without_a_state(tmp_path: Path) -> None:
    """Revisión A H4: a refused save rebuilt the prefix before and after every decision; now that server's
    requests go without the state until the server is replaced."""

    server = _Server(tmp_path)
    server.refuse_save = True
    pool = ChatCompletionConnectionPool(max_connections=3, server_slots=True)
    state = SlotState(tmp_path / "decider-a.bin", {"prompt": "p", "n_predict": 1})
    _decide(server, pool, state, "abre discord")
    _settled(pool)
    assert _routes(server) == ["/completion", SAVE, CHAT]
    for text in ("busca el clima", "sí"):
        server.sent.clear()
        _decide(server, pool, state, text)
        _settled(pool)
        assert _routes(server) == [CHAT]
    pool.invalidate()
    server.sent.clear()
    server.refuse_save = False
    _decide(server, pool, state, "abre discord")
    _settled(pool)
    assert _routes(server) == ["/completion", SAVE, CHAT, RESTORE]
    pool.close()


def test_a_state_the_server_cannot_read_is_built_again(tmp_path: Path) -> None:
    server = _Server(tmp_path, refuse_restore=True)
    pool = ChatCompletionConnectionPool(max_connections=3, server_slots=True)
    state = SlotState(tmp_path / "decider-a.bin", {"prompt": "p", "n_predict": 1})
    state.path.write_bytes(b"cut short")
    _decide(server, pool, state, "abre discord")
    _settled(pool)
    # The decision is still asked (it evaluates its whole prompt); the unreadable file is dropped and built again.
    assert _routes(server) == [RESTORE, CHAT, "/completion", SAVE]
    assert state.path.read_bytes() == b"state"
    server.sent.clear()
    server.refuse_restore = False
    _decide(server, pool, state, "abre discord")
    _settled(pool)
    assert _routes(server) == [CHAT, RESTORE]
    pool.close()


def test_a_request_without_a_state_or_a_slot_is_sent_as_before(tmp_path: Path) -> None:
    server = _Server(tmp_path)
    pool = ChatCompletionConnectionPool(max_connections=3, server_slots=True)
    with patch("baxy_mind.llm_transport.http.client.HTTPConnection", side_effect=server.connection):
        post_chat_completion(
            {"messages": [{"role": "user", "content": "hola"}]},
            endpoint_for_attempt=lambda: ENDPOINT,
            timeout_for_attempt=lambda: 1.0,
            connection_pool=pool,
        )
    unslotted = ChatCompletionConnectionPool(max_connections=3)
    _decide(server, unslotted, SlotState(tmp_path / "d.bin", {"prompt": "p"}), "hola")
    assert _routes(server) == [CHAT, CHAT]
    pool.close()
    unslotted.close()


# ------------------------------------------------------------------ the state the runtime asks for


def _chatml(messages: list[dict[str, str]]) -> str:
    rendered = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages)
    return rendered + "<|im_start|>assistant\n"


def _template_server(rendered: list[dict[str, Any]]) -> Any:
    def urlopen(request: Any, timeout: float = 0.0) -> Any:
        del timeout
        assert request.full_url == ENDPOINT + "/apply-template"
        body = json.loads(request.data.decode("utf-8"))
        rendered.append(body)
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"prompt": _chatml(body["messages"])}).encode("utf-8")
        return response

    return urlopen


def _runtime(directory: Path | None) -> LlmRuntime:
    runtime = object.__new__(LlmRuntime)
    runtime._decider_state_dir = directory
    runtime._decider_adapter = None
    runtime._endpoint = ENDPOINT
    runtime._ensure_started = lambda: None
    return runtime


def test_the_state_is_the_prefix_both_openings_share(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    rendered: list[dict[str, Any]] = []
    first, _ = runtime._decider_payload("abre discord porfa", [], TOOLS, SIGNATURES)
    history = [
        {"role": "user", "content": "abre discord porfa"},
        {"role": "assistant", "content": "Abrí «Discord»."},
    ]
    second, _ = runtime._decider_payload("mandale a Ron92 que ya voy", history, TOOLS, SIGNATURES)
    with patch("baxy_mind.llm.urllib.request.urlopen", side_effect=_template_server(rendered)):
        state = runtime._decider_slot_state(first)
        assert runtime._decider_slot_state(second) is state
    # Rendered once per catalog, with the decider's own template options.
    assert len(rendered) == 2 and all(body["chat_template_kwargs"] == {"enable_thinking": False} for body in rendered)
    prompt = state.prefix["prompt"]
    assert prompt.endswith("<|im_end|>\n<|im_start|>") and first["messages"][0]["content"] in prompt
    # The prefix of every decision, however its dialogue opens.
    for payload in (first, second):
        assert _chatml(payload["messages"]).startswith(prompt)
    # Revisión A H2: built from nothing, never from a context checkpoint of what the slot held (measured: a rebuild
    # on a used slot evaluated 6567+210 and every later decision changed).
    assert state.prefix["n_predict"] == 1 and state.prefix["cache_prompt"] is False
    assert state.path.parent == tmp_path and state.path.suffix == ".bin"


def test_another_catalog_or_adapter_is_another_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    with patch("baxy_mind.llm.urllib.request.urlopen", side_effect=_template_server([])):
        payload, _ = runtime._decider_payload("abre discord", [], TOOLS, SIGNATURES)
        state = runtime._decider_slot_state(payload)
        state.path.write_bytes(b"state")
        other, _ = runtime._decider_payload("abre discord", [], TOOLS[:1], {"app.open": ("appId",)})
        assert runtime._decider_slot_state(other).path != state.path
        # The previous catalog's state is not kept beside it (170 MB each).
        assert not state.path.exists()
        adapted = {**payload, "lora": [{"id": 0, "scale": 1.0}]}
        adapted_state = runtime._decider_slot_state(adapted)
    assert adapted_state.path != state.path
    # The prefix is evaluated with the decider's adapter, as every decision is.
    assert adapted_state.prefix["lora"] == [{"id": 0, "scale": 1.0}]


def test_without_slot_files_or_a_rendering_the_decision_is_asked_as_before(tmp_path: Path) -> None:
    payload, _ = _runtime(None)._decider_payload("abre discord", [], TOOLS, SIGNATURES)
    assert _runtime(None)._decider_slot_state(payload) is None
    runtime = _runtime(tmp_path)
    with patch("baxy_mind.llm.urllib.request.urlopen", side_effect=urllib.error.URLError("caído")):
        assert runtime._decider_slot_state(payload) is None


class _Recorder(LlmRuntime):
    """The runtime without a server: ``_post`` records what the decider would send."""

    def __init__(self, directory: Path) -> None:
        self._gguf = None
        self._parallel_turn_verification = True
        self._decider_state_dir = directory
        self._endpoint = ENDPOINT
        self.posts: list[dict[str, Any]] = []

    def _ensure_started(self) -> None:
        return None

    def _post(self, payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.posts.append(kwargs)
        content = json.dumps({"request": "x", "decision": "talk", "operations": [], "question": ""})
        return {"choices": [{"message": {"content": content}}]}

    def _prepare_slot(self, state: SlotState, cancellation: Any) -> None:
        self.posts.append({"slot_state": state, "reserved_slot": True, "warm": True})


def test_warmup_prepared_and_asked_decisions_share_the_state(tmp_path: Path) -> None:
    runtime = _Recorder(tmp_path)
    with patch("baxy_mind.llm.urllib.request.urlopen", side_effect=_template_server([])):
        runtime.warm_decider(TOOLS, signatures=SIGNATURES)
        deadline = time.monotonic() + 5
        while not runtime.posts and time.monotonic() < deadline:
            time.sleep(0.005)
        # Revisión A H5: the warmup builds the state and asks nothing to decode.
        assert runtime.posts == [{"slot_state": runtime.posts[0]["slot_state"], "reserved_slot": True, "warm": True}]
        runtime.begin_request(10.0)
        runtime.prepare_decision("abre discord", [], TOOLS, signatures=SIGNATURES)
        runtime.decide_in_context("abre discord", [], TOOLS, signatures=SIGNATURES)
        runtime.decide_in_context("busca el clima", [{"role": "user", "content": "hola"}], TOOLS, signatures=SIGNATURES)
        runtime.end_request()
    states = {id(kwargs["slot_state"]) for kwargs in runtime.posts}
    assert len(runtime.posts) == 3 and len(states) == 1
    assert all(kwargs["reserved_slot"] is True for kwargs in runtime.posts)


def test_the_owned_server_saves_slots_in_its_own_directory_removed_on_close(tmp_path: Path) -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._server = "llama-server.exe"
    runtime._gguf = "qwen.gguf"
    runtime._port = 12345
    runtime._parallel_turn_verification = True
    assert "--slot-save-path" not in runtime._server_command()
    directory = tmp_path / "baxy-decider-slot-x"
    directory.mkdir()
    (directory / "decider-a.bin").write_bytes(b"state")
    runtime._decider_state_dir = directory
    command = runtime._server_command()
    assert command[command.index("--slot-save-path") + 1] == str(directory)
    runtime.close()
    assert not directory.exists() and runtime._decider_state_dir is None


def test_starting_the_multi_slot_server_creates_its_slot_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._server = "llama-server.exe"
    runtime._gguf = "qwen.gguf"
    runtime._parallel_turn_verification = True
    runtime._endpoint = None
    runtime._process = None
    commands: list[list[str]] = []

    def popen(command: list[str], **_kwargs: object) -> Any:
        commands.append(command)
        raise OSError("sin servidor en el test")

    monkeypatch.setattr(llm.llm_startup, "require_vram_for", lambda *_a, **_k: None)
    monkeypatch.setattr(llm.subprocess, "Popen", popen)
    with pytest.raises(OSError):
        runtime._ensure_started_locked()
    directory = Path(commands[0][commands[0].index("--slot-save-path") + 1])
    assert directory.is_dir() and directory == runtime._decider_state_dir
    runtime.close()
    assert not directory.exists()


def test_a_gone_mind_s_slot_directory_is_swept_at_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Revisión A H3: a mind killed without ``close`` left 170 MB in %TEMP%; the next one sweeps it, never the
    directory of a mind that still runs (its ``owner.lock`` stays open)."""

    monkeypatch.setattr(llm_settings.tempfile, "tempdir", str(tmp_path))
    gone = tmp_path / "baxy-decider-slot-gone"
    gone.mkdir()
    (gone / "owner.lock").write_bytes(b"")
    (gone / "decider-a.bin").write_bytes(b"state")
    running, running_lock = llm_settings._own_decider_state_dir()
    (running / "decider-a.bin").write_bytes(b"state")
    unrelated = tmp_path / "otro"
    unrelated.mkdir()
    mine, mine_lock = llm_settings._own_decider_state_dir()
    try:
        assert not gone.exists() and unrelated.exists()
        assert (running / "decider-a.bin").exists() and mine.is_dir() and (mine / "owner.lock").exists()
    finally:
        running_lock.close()
        mine_lock.close()


def test_the_warmup_builds_the_state_on_the_reserved_slot_and_the_decision_finds_it(tmp_path: Path) -> None:
    server = _Server(tmp_path)
    pool = ChatCompletionConnectionPool(max_connections=3, server_slots=True)
    state = SlotState(tmp_path / "decider-a.bin", {"prompt": "p", "n_predict": 1, "cache_prompt": False})
    with patch("baxy_mind.llm_transport.http.client.HTTPConnection", side_effect=server.connection):
        prepare_slot_state(pool, ENDPOINT, state, timeout=1.0)
        assert _routes(server) == ["/completion", SAVE]
        assert server.sent[0][1] == {"prompt": "p", "n_predict": 1, "cache_prompt": False, "id_slot": 2}
        prepare_slot_state(pool, ENDPOINT, state, timeout=1.0)  # already there: nothing sent
        assert _routes(server) == ["/completion", SAVE]
    _decide(server, pool, state, "abre discord")
    _settled(pool)
    assert _routes(server) == ["/completion", SAVE, CHAT, RESTORE]
    pool.close()
