import http.server
import threading

import pytest

from baxy_mind import llm_server
from baxy_mind.llm_server import LlmServer


class _Health(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - http.server's name
        self.send_response(200 if self.path == "/health" else 404)
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


def test_remoto_no_lanza_nada_y_espera_su_health(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Health)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("BAXY_MIND_LLAMA_REMOTE", str(httpd.server_port))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    lanzados: list[object] = []
    monkeypatch.setattr(llm_server.subprocess, "Popen", lambda *a, **k: lanzados.append(a))
    server = LlmServer(str(tmp_path / "model.gguf"), "llama-server.exe")
    try:
        assert server.port == httpd.server_port
        server.start()
        server.wait_ready(10)
        assert lanzados == []
        server.close()  # no process of its own: nothing to stop
    finally:
        httpd.shutdown()


def test_remoto_que_no_es_un_puerto_falla_con_su_causa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BAXY_MIND_LLAMA_REMOTE", "pod3")
    with pytest.raises(RuntimeError, match="not a port"):
        LlmServer("model.gguf", "llama-server.exe")
