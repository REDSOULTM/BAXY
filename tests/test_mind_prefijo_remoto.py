"""Encargo 27 (flota 03-11): the prefix kept between starts with a remote model server (BAXY_MIND_LLAMA_REMOTE,
measurement only). The server writes the slot's state in ITS --slot-save-path, on the other machine; the mind keeps
only the facts beside it in its own folder. Every start of a VM re-read the ~44,000-token prefix (~17 s on the PC's
4060 Ti) because restore_prefix looked for the state on the mind's disk. A product start (its own server) is as before."""
import http.server
import json
import threading
from pathlib import Path

import pytest

from baxy_mind import llm_server
from baxy_mind.llm_server import LlmServer


class _Server:
    """A llama-server whose --slot-save-path is its own folder (another machine's disk): a save writes the state with
    its token count, a restore of a file it does not have fails as llama-server's does (HTTP 400, «Unable to restore
    slot»), and every slot action is recorded."""

    def __init__(self, folder: Path, model_path: str = "/workspace/models/baxy.gguf", tokens: int = 44023) -> None:
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.model_path = model_path
        self.tokens = tokens
        self.actions: list[str] = []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def _answer(self, payload: dict, status: int = 200) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:  # noqa: N802 - http.server's name
                self._answer({"total_slots": 9, "build_info": "b11609-fcac19079", "model_path": fake.model_path,
                              "default_generation_settings": {"n_ctx": 53248}, "media_marker": "<__media_x__>"})

            def do_POST(self) -> None:  # noqa: N802 - http.server's name
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                action = self.path.split("action=")[-1]
                fake.actions.append(action)
                if action == "erase":
                    return self._answer({"id_slot": 0, "n_erased": 1})
                state = fake.folder / body["filename"]
                if action == "save":
                    state.write_text(str(fake.tokens), encoding="utf-8")
                    return self._answer({"id_slot": 0, "filename": state.name, "n_saved": fake.tokens})
                if not state.is_file():
                    return self._answer({"error": {"code": 400, "message": "Unable to restore slot: No available space "
                                                   "in KV cache or invalid slot save file"}}, 400)
                return self._answer({"id_slot": 0, "filename": state.name,
                                     "n_restored": int(state.read_text(encoding="utf-8"))})

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def port(self) -> int:
        return self.httpd.server_address[1]


@pytest.fixture
def remote(tmp_path: Path):
    servers: list[_Server] = []

    def make(**kwargs: object) -> _Server:
        servers.append(_Server(tmp_path / f"pod-{len(servers)}", **kwargs))  # type: ignore[arg-type]
        return servers[-1]

    yield make
    for server in servers:
        server.httpd.shutdown()


def _mind(monkeypatch: pytest.MonkeyPatch, local: Path, server: _Server | None, port: int | None = None) -> LlmServer:
    """A mind's LlmServer whose own slot folder is ``local`` (the VM's disk): remote on ``server``, or local talking to
    ``port`` as if it had launched it."""
    monkeypatch.setenv("BAXY_VISION_SLOT_DIR", str(local))
    monkeypatch.delenv("BAXY_MIND_SLOT", raising=False)
    monkeypatch.delenv("BAXY_MIND_LLAMA_PORT", raising=False)
    if server is not None:
        monkeypatch.setenv("BAXY_MIND_LLAMA_REMOTE", str(server.port))
    else:
        monkeypatch.delenv("BAXY_MIND_LLAMA_REMOTE", raising=False)
    mind = LlmServer(str(local / "model.gguf"), "llama-server.exe")
    if server is not None:
        mind.start()
        mind.wait_ready(10)
    else:
        mind.port = port or 0
        mind._ready.set()
    return mind


WARM = [{"messages": [{"role": "system", "content": "BAXY"}], "tools": [], "max_tokens": 1}]


def test_a_second_remote_start_restores_the_prefix_the_server_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                                   remote) -> None:
    server = remote()
    local = tmp_path / "vm"
    first = _mind(monkeypatch, local, server)
    key = first.prefix_key(WARM)
    assert first.restore_prefix(key) is None  # nothing kept yet: the warm-up runs
    assert first.save_prefix(key, {"prefix_tokens": 44020})
    # The state is on the server's disk; the VM keeps only its facts.
    assert (server.folder / f"{llm_server.PREFIX}{key}.slot").is_file()
    assert sorted(path.name for path in local.iterdir()) == [f"{llm_server.PREFIX}{key}.json"]

    second = _mind(monkeypatch, local, server)
    assert second.prefix_key(WARM) == key
    assert second.restore_prefix(key) == {"prefix_tokens": 44020}
    assert server.actions == ["save", "restore"]


def test_a_remote_server_without_the_state_has_it_saved_again(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                              remote) -> None:
    # A new pod (or the PC's server with another folder) does not have the state the VM's facts speak of: the restore
    # fails, the warm-up runs and the save puts the state there again.
    local = tmp_path / "vm"
    first = _mind(monkeypatch, local, remote())
    key = first.prefix_key(WARM)
    assert first.save_prefix(key, {"prefix_tokens": 44020})
    other = remote()
    again = _mind(monkeypatch, local, other)
    assert again.restore_prefix(again.prefix_key(WARM)) is None
    assert again.save_prefix(key, {"prefix_tokens": 44020})
    assert (other.folder / f"{llm_server.PREFIX}{key}.slot").is_file()
    assert _mind(monkeypatch, local, other).restore_prefix(key) == {"prefix_tokens": 44020}


def test_a_remote_state_that_is_not_the_one_saved_is_not_taken(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                                 remote) -> None:
    # llama-server checks the file's shape (magic, layers, KV types, valid tokens; llama_state_seq_load_file and
    # server-context.cpp:2957-3000 at b11609), not that it holds this prefix. A state of another length under the same
    # name (written by another start meanwhile) is not this prefix: the slot is erased and the warm-up runs.
    server = remote()
    local = tmp_path / "vm"
    first = _mind(monkeypatch, local, server)
    key = first.prefix_key(WARM)
    assert first.save_prefix(key, {"prefix_tokens": 44020})
    (server.folder / f"{llm_server.PREFIX}{key}.slot").write_text("1200", encoding="utf-8")
    assert _mind(monkeypatch, local, server).restore_prefix(key) is None
    assert server.actions == ["save", "restore", "erase"]


def test_the_remote_key_names_the_model_the_server_serves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                                           remote) -> None:
    # The VM's own settings and files say nothing of the model the remote server loaded: a state of another GGUF with
    # the same shapes would load without an error. Its path and its slot's context (/props) are part of the key.
    local = tmp_path / "vm"
    one = _mind(monkeypatch, local, remote(model_path="/workspace/models/c4c2.gguf")).prefix_key(WARM)
    same = _mind(monkeypatch, local, remote(model_path="/workspace/models/c4c2.gguf")).prefix_key(WARM)
    other = _mind(monkeypatch, local, remote(model_path="/workspace/models/c5.gguf")).prefix_key(WARM)
    assert one == same != other


def test_a_product_start_keeps_its_key_and_needs_the_state_on_its_own_disk(monkeypatch: pytest.MonkeyPatch,
                                                                            tmp_path: Path, remote) -> None:
    # The product's own server writes the state in the mind's folder: without the file there nothing is asked of it,
    # and the key does not change with what /props says of the model (the GGUF's own stamp is in it already).
    local = tmp_path / "pc"
    server = remote(model_path="a.gguf")
    other = remote(model_path="b.gguf")
    mind = _mind(monkeypatch, local, None, server.port)
    key = mind.prefix_key(WARM)
    assert _mind(monkeypatch, local, None, other.port).prefix_key(WARM) == key
    local.mkdir(parents=True, exist_ok=True)
    (local / f"{llm_server.PREFIX}{key}.json").write_text(json.dumps({"prefix_tokens": 7}), encoding="utf-8")
    assert mind.restore_prefix(key) is None
    assert server.actions == []
