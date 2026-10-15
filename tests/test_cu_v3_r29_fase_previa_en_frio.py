"""Ronda 29: the first turn does not pay what does not depend on the request.

Banco Br27 (cu-v3/latencia_r27.md, cu-v3/r26/fase-previa-en-frio.md): the first ``turn.decide`` of every start cost
893 ms p50 and a later one of the same shape 180–400 ms. Measured without a model on redpc, the first
``_prepare_turn_result`` of a process cost 387 ms (1 348 ms where the Hunspell lexicon is installed) and the next ones
154, 160, 64, 25 and 22 ms: the first compilation of the expressions of ``semantic`` and the lazy data loads. Now the
readers read the test requests of ``data/readers_warmup.v1.json`` once when the catalog is configured, beside the
model's load: measured after it, the first turn costs 20 ms.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue
from baxy_mind.semantic.catalog import GameCatalogIndex, build_application_catalog_index

from test_cu_v3_cobertura import APPS, OPERATIONS, _tool
from baxy_mind import turn_decide
from baxy_mind import turn_audit as turn_audit_module
from baxy_mind import sidecar_lifecycle

ROOT = Path(__file__).resolve().parents[1]
# The applications the test requests name are installed here, as on the PC of the bench: where one is missing the
# reading of that request ends at the decider (no model in the warm-up) and the others still warm their readers.
PLACES = APPS + ("Calculadora", "Configuración")
REQUESTS = json.loads((ROOT / "src/baxy_mind/data/readers_warmup.v1.json").read_text(encoding="utf-8"))["requests"]

# A fresh process decides two orders of the bench (never the warm-up's own requests) and says what each one cost.
_MEASURE = """
import json, sys, time
sys.path.insert(0, "tests")
from baxy_mind import __main__  # noqa: F401 - the cold import of the whole sidecar
from baxy_mind import turn_decide
from baxy_mind.planner import PlannerCatalog
from baxy_mind.semantic import dialogue
from baxy_mind.semantic.catalog import GameCatalogIndex, build_application_catalog_index
from test_cu_v3_cobertura import APPS, OPERATIONS, _tool
tools = {name: _tool(name) for name in OPERATIONS}
resources = (PlannerCatalog(list(tools.values())), tools, build_application_catalog_index(APPS), GameCatalogIndex())
if sys.argv[1] == "warm":
    turn_decide._start_readers_warmup(*resources).join()
spent = []
for text in ("en Fotos andá a Álbumes", "en Spotify buscá una canción y ponela"):
    started = time.perf_counter()
    try:
        turn_decide._prepare_turn_result(
            {"id": "m", "text": text, "history": [{"role": "user", "content": text}]}, llm=object(),
            planner_catalog=resources[0], encoder=lambda _text: (), tool_by_name=tools,
            application_names=resources[2], game_catalog=resources[3], dialogue_state=dialogue.DialogueState(),
        )
    except Exception:
        pass
    spent.append(time.perf_counter() - started)
print(json.dumps(spent))
"""


def _fresh_process(mode: str) -> list[float]:
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        # The same on every machine: the optional Hunspell lexicon (0.9 s more of cold load where installed) stays out.
        "BAXY_MIND_LEXICON_DIR": str(ROOT / "no-lexicon-here"),
    }
    environment.pop(turn_audit_module.TURN_AUDIT_ENV, None)
    done = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", _MEASURE, mode],
        cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8", timeout=180, check=True,
    )
    return json.loads(done.stdout.strip().splitlines()[-1])


def _resources() -> tuple[Any, ...]:
    tools = {name: _tool(name) for name in OPERATIONS}
    return PlannerCatalog(list(tools.values())), tools, build_application_catalog_index(PLACES), GameCatalogIndex()


def test_after_the_warmup_the_first_turn_costs_what_a_later_one_costs() -> None:
    cold_first, cold_second = _fresh_process("cold")
    warm_first, warm_second = _fresh_process("warm")
    print(f"r29 ms: frío {cold_first * 1000:.0f}/{cold_second * 1000:.0f}, "
          f"calentado {warm_first * 1000:.0f}/{warm_second * 1000:.0f}")
    # Without it the first turn pays the cold work (the counter-case: this is what the warm-up takes away).
    assert cold_first > 2 * warm_first
    # With it the first turn is one more turn: within a wide margin of the second one, never the cold one's cost.
    assert warm_first < 3 * warm_second + 0.05
    assert warm_first < cold_first / 2


@pytest.mark.parametrize("text", REQUESTS)
def test_every_warmup_request_is_read_to_the_end_without_a_model(text: str) -> None:
    """``llm=object()``: whatever asked the model would raise. Each request is decided by the readers alone, so the
    whole path a first turn takes is the one warmed."""

    catalog, tools, applications, games = _resources()
    result = turn_decide._prepare_turn_result(
        {"text": text, "history": [{"role": "user", "content": text}]}, llm=object(), planner_catalog=catalog,
        encoder=lambda _text: (), tool_by_name=tools, application_names=applications, game_catalog=games,
        dialogue_state=dialogue.DialogueState(),
    )
    assert result["kind"] == "action" and result["effectOperations"]


def test_the_warmup_is_no_turn_nothing_is_audited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audit = tmp_path / "turn_audit.jsonl"
    monkeypatch.setenv(turn_audit_module.TURN_AUDIT_ENV, str(audit))
    catalog, tools, applications, games = _resources()

    thread = turn_decide._start_readers_warmup(catalog, tools, applications, games)
    assert thread.name == turn_audit_module._READERS_WARMUP_THREAD and thread.daemon
    thread.join(60)
    assert not thread.is_alive()
    assert not audit.exists()

    # Counter-case: the same reading inside a turn (the request lane's thread) is audited as before.
    text = REQUESTS[0]
    turn_decide._prepare_turn_result(
        {"id": "t1", "text": text, "history": [{"role": "user", "content": text}]}, llm=object(),
        planner_catalog=catalog, encoder=lambda _text: (), tool_by_name=tools, application_names=applications,
        game_catalog=games, dialogue_state=dialogue.DialogueState(),
    )
    assert audit.exists() and '"request_id":"t1"' in audit.read_text(encoding="utf-8")


def test_a_reading_that_would_ask_the_model_ends_there(monkeypatch: pytest.MonkeyPatch) -> None:
    read: list[str] = []

    def needs_the_model(message: dict[str, Any], *, llm: Any, **_resources: Any) -> dict[str, Any]:
        read.append(message["text"])
        return llm.chat(message["text"])  # object() has no model to ask

    for module in (sidecar, turn_decide):
        monkeypatch.setattr(module, "_prepare_turn_result", needs_the_model)
    turn_decide._warm_turn_readers(*_resources())
    assert read == REQUESTS


def _configure_the_catalog(
    monkeypatch: pytest.MonkeyPatch, warm: Any, wait_warmup: Any,
) -> list[dict[str, Any]]:
    """Answers one ``catalog.configure`` with the readers' warm-up ``warm`` and a model whose load is ``wait_warmup``."""

    written: list[dict[str, Any]] = []

    class FakeLlmRuntime:
        @staticmethod
        def start_warmup() -> None:
            return None

        @staticmethod
        def wait_warmup(timeout: float) -> bool:
            return wait_warmup(timeout)

        @staticmethod
        def begin_request(*_args: object, **_kwargs: object) -> None:
            return None

        @staticmethod
        def end_request() -> None:
            return None

        @staticmethod
        def close() -> None:
            return None

    class FakeRouter:
        @staticmethod
        def try_ready(_timeout: float = 0.0) -> bool:
            return True

        @staticmethod
        def encode(_texts: object, *, timeout: float, prefix: str = "query") -> list[list[float]]:
            return [[1.0]]

        @staticmethod
        def request_close() -> None:
            return None

        @staticmethod
        def close() -> None:
            return None

    tools = [_tool("app.open")]
    monkeypatch.setattr(sidecar, "LlmRuntime", FakeLlmRuntime)
    monkeypatch.setattr(sidecar, "ProcessIntentRouter", FakeRouter)
    monkeypatch.setattr(sidecar, "configure_tools", lambda _value: tools)
    monkeypatch.setattr(sidecar, "configure_application_catalog", lambda _value: ("Paint",))
    monkeypatch.setattr(sidecar, "_create_planner_resources", lambda _tools, encoder=None: ("catalog", "skills"))
    monkeypatch.setattr(turn_decide, "_warm_turn_readers", warm)
    monkeypatch.setenv("BAXY_MIND_LLM_GGUF", "fixture.gguf")
    pending = iter([{"type": "catalog.configure", "id": "c1", "capabilities": [], "applicationCatalog": []}])
    lifecycle = sidecar_lifecycle._SidecarLifecycle()
    try:
        sidecar._run_sidecar(
            lifecycle, read_message=lambda: next(pending, None), write_message=written.append,
            request_finished=lambda _message: None,
        )
    finally:
        lifecycle.close()
    return written


def test_the_catalog_starts_the_warmup_beside_the_wait_for_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """``catalog.configure`` waits for the model's load; the readers warm up meanwhile, in their own thread (never the
    request lane's), with the catalog just configured, and ``catalog.ready`` is answered as before."""

    warmed = threading.Event()
    seen: dict[str, Any] = {}

    def warm(*resources: Any) -> None:
        seen["thread"] = threading.current_thread().name
        seen["resources"] = resources
        warmed.set()

    def wait_warmup(_timeout: float) -> bool:
        # The model is still loading: the warm-up runs while the catalog request waits here.
        seen["ran_beside_the_wait"] = warmed.wait(10)
        return True

    written = _configure_the_catalog(monkeypatch, warm, wait_warmup)

    assert seen["ran_beside_the_wait"] is True
    assert seen["thread"] == turn_audit_module._READERS_WARMUP_THREAD != threading.current_thread().name
    catalog, tool_by_name, applications, games = seen["resources"]
    assert catalog == "catalog" and list(tool_by_name) == ["app.open"]
    assert isinstance(games, GameCatalogIndex) and not isinstance(applications, tuple)
    assert {"type": "catalog.ready", "id": "c1", "count": 1} in written


def test_a_model_ready_before_the_readers_still_answers_after_the_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    """FL2 (Full gate, 2026-10-13): a model that was ready first had ``catalog.ready`` answered while the warm-up still
    read, and the first turn compiled the same expressions as the warm-up at the same time (``grammar._compiled``
    counted misses it never kept). The first turn comes after the warm-up."""

    release = threading.Event()
    finished = threading.Event()

    def warm(*_resources: Any) -> None:
        release.wait(10)
        finished.set()

    def wait_warmup(_timeout: float) -> bool:
        # The model is ready at once; the warm-up is still reading when the wait returns.
        assert not finished.is_set()
        threading.Timer(0.2, release.set).start()
        return True

    written = _configure_the_catalog(monkeypatch, warm, wait_warmup)

    assert finished.is_set()
    assert {"type": "catalog.ready", "id": "c1", "count": 1} in written
