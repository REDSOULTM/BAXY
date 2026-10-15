"""Ronda 22 (e5-vivo): la respuesta tardía del encoder E5 no se tira.

Tandas de uso real sobre r20 (2026-10-09): 12 pasos «e5_failed», todos en el tope de 0,75 s del paso con el worker
listo. Medido con el runtime y el PC cargado: 30 nombres 1,6–3,6 s y 60 nombres 4,0–6,3 s (en r17, 108–655 ms). La
petición vencida quedaba abandonada por su id y su respuesta se descartaba; el paso siguiente volvía a pedir los mismos
nombres de la vista y volvía a pasarse: la regla quedaba ciega en todos los pasos. Ahora las filas de la respuesta
tardía se guardan (validadas por id, cantidad y forma) y el paso siguiente las usa sin codificar; el tope del paso se
respeta y cada fallo deja su causa en la traza opcional del encoder.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from baxy_mind import cu_meaning
from baxy_mind import router as router_module
from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
from baxy_mind.semantic import cu_semejanza


class _Pipe:
    def __init__(self) -> None:
        self.payload = ""

    def write(self, value: str) -> None:
        self.payload += value

    @staticmethod
    def flush() -> None:
        return None


class _Process:
    def __init__(self) -> None:
        self.stdin = _Pipe()
        self.killed = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        del timeout
        self.returncode = 0 if self.returncode is None else self.returncode
        return self.returncode


def _router() -> ProcessIntentRouter:
    router = ProcessIntentRouter.__new__(ProcessIntentRouter)
    router._process = _Process()
    router._responses = queue.Queue()
    router._lock = threading.Lock()
    router._is_ready = True
    router._failed = False
    router._failure = ""
    router._next_request_id = 1
    router._late_request_id = None
    router._late_since = 0.0
    router._failure_times = []
    router._restarts_left = 0
    router._closed = threading.Event()
    return router


def _sent(router: ProcessIntentRouter) -> list[dict]:
    return [json.loads(line) for line in router._process.stdin.payload.splitlines()]


def _abandon(encoder: RequestBudgetEncoder, texts: list[str], prefix: str = "passage") -> None:
    encoder.begin_request(0.02)
    try:
        with pytest.raises(TimeoutError):
            encoder(texts, prefix=prefix)
    finally:
        encoder.end_request()


def _ask(encoder: RequestBudgetEncoder, texts: list[str], prefix: str = "passage", budget: float = 0.02):
    encoder.begin_request(budget)
    try:
        return encoder(texts, prefix=prefix)
    finally:
        encoder.end_request()


# ------------------------------------------------------------------ la respuesta tardía se guarda


def test_the_late_reply_of_a_step_serves_the_next_step_without_encoding_again() -> None:
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla", "Sonido"])
    # The worker finishes the abandoned request after the step's deadline.
    router._responses.put({"type": "encode.result", "id": 1, "rows": [[1.0, 0.0], [0.0, 1.0]]})

    started = time.perf_counter()
    rows = _ask(encoder, ["Pantalla", "Sonido"])
    # Timed right after the step's call: the assertions below (np.testing loads lazily) are no part of the step.
    elapsed = time.perf_counter() - started

    np.testing.assert_array_equal(rows, [[1.0, 0.0], [0.0, 1.0]])
    assert len(_sent(router)) == 1, "the same names are never sent again"
    assert router._late_request_id is None
    assert elapsed < cu_semejanza.ENCODER_BUDGET_SECONDS


def test_contracase_only_the_names_not_kept_are_encoded() -> None:
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla"])
    router._responses.put({"type": "encode.result", "id": 1, "rows": [[1.0, 0.0]]})
    router._responses.put({"type": "encode.result", "id": 2, "rows": [[0.0, 1.0]]})

    rows = _ask(encoder, ["Pantalla", "Brillo"], budget=1.0)

    np.testing.assert_array_equal(rows, [[1.0, 0.0], [0.0, 1.0]])
    sent = _sent(router)
    assert [request["texts"] for request in sent] == [["Pantalla"], ["Brillo"]]


def test_contracase_rows_kept_for_passages_never_answer_a_query() -> None:
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla"], prefix="passage")
    router._responses.put({"type": "encode.result", "id": 1, "rows": [[1.0, 0.0]]})
    router._responses.put({"type": "encode.result", "id": 2, "rows": [[0.5, 0.5]]})

    rows = _ask(encoder, ["Pantalla"], prefix="query", budget=1.0)

    np.testing.assert_array_equal(rows, [[0.5, 0.5]])
    assert [request["prefix"] for request in _sent(router)] == ["passage", "query"]


@pytest.mark.parametrize(
    "late",
    [
        {"type": "error", "id": 1, "code": "request_failed"},
        {"type": "encode.result", "id": 1, "rows": [[1.0, 0.0]]},  # one row for two names
        {"type": "encode.result", "id": 1, "rows": [[float("nan"), 0.0], [0.0, 1.0]]},
    ],
)
def test_contracase_a_late_error_or_malformed_reply_is_never_kept(late: dict) -> None:
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla", "Sonido"])
    router._responses.put(late)
    router._responses.put({"type": "encode.result", "id": 2, "rows": [[0.25, 0.75], [0.75, 0.25]]})

    rows = _ask(encoder, ["Pantalla", "Sonido"], budget=1.0)

    np.testing.assert_array_equal(rows, [[0.25, 0.75], [0.75, 0.25]])
    assert len(_sent(router)) == 2
    assert router.late_rows(["Pantalla", "Sonido"], "passage") == {}


def test_contracase_a_reply_of_another_id_is_never_kept_and_retires_the_channel() -> None:
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla"])
    router._responses.put({"type": "encode.result", "id": 7, "rows": [[1.0, 0.0]]})

    assert router.late_rows(["Pantalla"], "passage") == {}
    assert router._failed, "a desynced channel is retired as before"


def test_contracase_a_retired_generation_leaves_nothing_to_keep() -> None:
    router = _router()
    router._restarts_left = 1
    router._launch_and_read = lambda **_kwargs: None
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla"])
    with router._lock:
        router._retire_channel_locked("test")
    router._launcher.join(timeout=1.0)

    assert router._late_request_id is None
    assert router._late_batch == ()
    assert router.late_rows(["Pantalla"], "passage") == {}


def test_a_reply_still_pending_never_holds_the_step() -> None:
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla"])

    started = time.perf_counter()
    kept = router.late_rows(["Pantalla"], "passage")
    elapsed = time.perf_counter() - started

    assert kept == {}
    assert elapsed < cu_semejanza.ENCODER_BUDGET_SECONDS
    assert router._late_request_id == 1


def test_the_kept_rows_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router_module, "LATE_ROWS_LIMIT", 2)
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["a", "b", "c"])
    router._responses.put({"type": "encode.result", "id": 1, "rows": [[1.0], [2.0], [3.0]]})

    kept = router.late_rows(["a", "b", "c"], "passage")

    assert sorted(kept) == ["b", "c"]


# ------------------------------------------------------------------ la causa del fallo


@pytest.mark.parametrize("case", ["busy", "late_pending", "timeout"])
def test_every_failure_says_its_cause_in_the_encoder_trace(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = tmp_path / "model_calls.jsonl"
    monkeypatch.setenv("BAXY_MIND_MODEL_CALL_AUDIT_PATH", str(audit))
    router = _router()
    encoder = RequestBudgetEncoder(router)
    if case == "late_pending":
        _abandon(encoder, ["Pantalla"])
    if case == "busy":
        router._lock.acquire()
    try:
        with pytest.raises(TimeoutError):
            _ask(encoder, ["Sonido"])
    finally:
        if case == "busy":
            router._lock.release()

    rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["schema"] == "baxy.encoder-call-timing.v1"
    assert rows[-1]["outcome"] == "failed"
    assert rows[-1]["cause"] == case
    assert encoder.last_cause == case
    assert "Sonido" not in audit.read_text(encoding="utf-8"), "the trace carries no content"


def test_contracase_an_answer_clears_the_cause_and_is_traced_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audit = tmp_path / "model_calls.jsonl"
    monkeypatch.setenv("BAXY_MIND_MODEL_CALL_AUDIT_PATH", str(audit))
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla"])
    router._responses.put({"type": "encode.result", "id": 1, "rows": [[1.0, 0.0]]})
    router._responses.put({"type": "encode.result", "id": 2, "rows": [[0.0, 1.0]]})

    _ask(encoder, ["Pantalla", "Sonido"], budget=1.0)

    last = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert (last["outcome"], last["cause"], last["texts"], last["reused_late"]) == ("ok", "", 1, 1)
    assert encoder.last_cause == ""


def test_without_the_audit_path_nothing_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAXY_MIND_MODEL_CALL_AUDIT_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    router = _router()
    encoder = RequestBudgetEncoder(router)
    _abandon(encoder, ["Pantalla"])
    assert list(tmp_path.iterdir()) == []


# ------------------------------------------------------------------ el paso de computer use


def test_a_step_after_a_failed_step_on_the_same_view_matches_by_meaning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cu_meaning, "_SEMANTIC_CACHE", cu_semejanza.EmbeddingCache())
    router = _router()
    encoder = RequestBudgetEncoder(router)
    view = {"window": {"title": "Configuración"}, "controls": [
        {"name": "Pantalla", "kind": "ListItem"}, {"name": "Sonido", "kind": "ListItem"},
    ], "text": {}}

    first = cu_meaning.SemanticMatcher(encoder, budget_seconds=0.05)
    encoder.begin_request(0.05)
    try:
        assert first.scored("display", view) == ()
    finally:
        encoder.end_request()
    assert first.state == cu_meaning.ENCODER_FAILED
    # The query («display») was abandoned; its reply arrives after the step, the names were never sent.
    router._responses.put({"type": "encode.result", "id": 1, "rows": [[1.0, 0.0]]})
    router._responses.put({"type": "encode.result", "id": 2, "rows": [[0.9, 0.1], [0.1, 0.9]]})

    second = cu_meaning.SemanticMatcher(encoder, budget_seconds=0.75)
    encoder.begin_request(0.75)
    try:
        scored = second.scored("display", view)
    finally:
        encoder.end_request()

    assert second.state == cu_meaning.ENCODER_READY
    assert scored[0][0] == "Pantalla"
    assert [request["texts"] for request in _sent(router)] == [["display"], ["Pantalla", "Sonido"]]
