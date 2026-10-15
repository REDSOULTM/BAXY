"""Pasada r7 del goal v3: los nombres de un lugar buscados a ciegas y el encoder que la promoción del catálogo ocupaba.

Vistas reales congeladas del journal del banco (tests/data/cu_v3_vistas_motor_lugar.json).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from baxy_mind import router as router_module
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_validate
from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder

_DATA = json.loads((Path(__file__).parent / "data" / "cu_v3_vistas_motor_lugar.json").read_text(encoding="utf-8"))


def _view(key: str) -> dict:
    return _DATA[key]["vista"]


def _not_found(step: int, label: str) -> dict:
    return {"step": step, "operation": "input.visible.click", "label": label, "ok": False, "error": "visible_button_not_found"}


def _blind(step: dict | None) -> str | None:
    if step is None or step.get("operation") != "input.visible.click" or step.get("reason") != cu_lookup.REASON_BY_NAME:
        return None
    return str((step.get("arguments") or {}).get("label") or "")


# ------------------------------------------------------------------ nombres buscados a ciegas (v3-58, t-scroll-4)


def test_two_names_found_nowhere_end_the_blind_lookups_on_the_real_browser_view() -> None:
    # v3-58: «ir a configuracion» in a browser whose view lists 20 of 68 controls; the five names of the place were
    # each clicked by label alone and found nowhere, a step of ~1.7 s each, and the cycle started over.
    view = _view("edge_ayuda")
    history: list[dict] = []
    blind: list[str] = []
    for number in range(1, 8):
        step = cu_rules.deterministic_step(goal="ir a configuracion", view=view, history=history)
        label = _blind(step)
        if label is None:
            break
        blind.append(label)
        history.append(_not_found(number, label))
    assert blind[0] == "configuracion"
    assert len(blind) == 2, blind


def test_the_older_failures_still_count_when_the_window_of_history_moved_on() -> None:
    # The shell keeps every name the tree did not hold in the sub-goal's history: with two of them there, a later
    # step (after other acts) never looks the place up blind again.
    view = _view("edge_ayuda")
    history = [
        _not_found(1, "configuracion"), _not_found(2, "ajustes"),
        {"step": 7, "operation": "app.open", "appId": "Microsoft Edge", "ok": True},
        {"step": 8, "operation": "input.visible.click", "label": "Actualizar", "index": 7, "ok": True, "changed": True},
    ]
    step = cu_rules.deterministic_step(goal="ir a configuracion", view=view, history=history)
    assert _blind(step) is None


def test_contracase_one_name_not_found_leaves_the_other_language_name() -> None:
    # The second name is still looked up: a Spanish window asked in English (measured on Paint: «blue» then «azul»).
    view = _view("edge_ayuda")
    step = cu_rules.deterministic_step(goal="ir a configuracion", view=view, history=[_not_found(1, "configuracion")])
    assert _blind(step) not in (None, "configuracion")


def test_a_path_is_never_clicked_as_a_name_on_the_real_explorer_view() -> None:
    # t-scroll-4: «ir a c:\windows\system32» on Explorer (20 of 87 listed) clicked the path by label and found nothing.
    step = cu_rules.deterministic_step(goal="ir a c:\\windows\\system32", view=_view("explorador_descargas"), history=[])
    assert _blind(step) is None


def test_contracase_a_plain_name_on_the_same_explorer_view_is_still_looked_up_blind() -> None:
    step = cu_rules.deterministic_step(goal="ir a recientes", view=_view("explorador_descargas"), history=[])
    assert _blind(step) == "recientes"


# ------------------------------------------------------------------ un «done» que cita el control que lo haría (t-long-2)


def _validate(raw: dict, view: dict, goal: str, history: list[dict] | None = None) -> dict:
    return cu_validate.validate_decision(
        raw, view=view, last_failed=None, application_names=("Word",), history=history or [], goal=goal,
        objective=goal, application="Word",
    )


def test_a_done_citing_the_item_that_does_it_before_any_step_is_that_click_on_the_real_word_view() -> None:
    # t-long-2: «creá un documento en blanco» answered done with «Documento en blanco» (the start gallery's item) and
    # no step; refused, the model said none and the mission stopped on the first sub-goal of seven.
    decision = _validate({"act": "done", "evidence": "Documento en blanco"}, _view("word_inicio"), "creá un documento en blanco")
    assert decision["operation"] == "input.visible.click"
    assert decision["arguments"] == {"label": "Documento en blanco", "index": 11}


def test_contracase_a_done_citing_no_pressable_control_is_still_refused() -> None:
    view = _view("word_inicio")
    # A field, a toggle, a name no control carries and an item the goal does not name (v3-17's twin: «Galería» for
    # «recortar»): the done stays refused, nothing is pressed.
    for evidence in ("Buscar un archivo", "Ocultar o mostrar región", "Documento nuevo en blanco", "Nuevo", "Abrir"):
        decision = _validate({"act": "done", "evidence": evidence}, view, "creá un documento en blanco")
        assert decision["operation"] == "none", evidence


def test_contracase_a_done_citing_a_removal_or_an_account_act_is_never_pressed() -> None:
    # A done says the act is already done: pressing «Eliminar» on whatever is chosen now, or a second «Comprar», is
    # no act the model chose (revisión adversarial de la rama): the done stays refused.
    view = {
        "window": {"title": "Archivos", "rect": [0, 0, 1000, 800]},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Eliminar", "rect": [10, 10, 50, 30]},
            {"i": 1, "kind": "Button", "name": "Comprar", "rect": [60, 10, 110, 30]},
            {"i": 2, "kind": "ListItem", "name": "informe.docx", "state": "selected", "rect": [10, 50, 300, 70]},
        ],
    }
    for goal, evidence in (("eliminar el archivo informe.docx", "Eliminar"), ("comprar el juego", "Comprar")):
        decision = _validate({"act": "done", "evidence": evidence}, view, goal)
        assert decision["operation"] == "none", (goal, decision)


def test_the_press_made_of_a_done_carries_the_models_reason() -> None:
    decision = _validate({"act": "done", "evidence": "Documento en blanco", "why": "la galería lo ofrece"},
                         _view("word_inicio"), "creá un documento en blanco")
    assert decision["operation"] == "input.visible.click" and decision["reason"] == "la galería lo ofrece"


def test_contracase_after_an_act_the_done_is_judged_as_before() -> None:
    # With a verified act of its own the done is judged on its evidence (here on screen): never turned into a click.
    acted = [{"step": 1, "operation": "input.visible.click", "label": "Nuevo", "index": 6, "ok": True, "changed": True}]
    decision = _validate({"act": "done", "evidence": "Documento en blanco"}, _view("word_inicio"), "creá un documento en blanco", acted)
    assert decision["operation"] != "input.visible.click"


_OPENED_BLANK = [
    {"step": 1, "operation": "app.open", "appId": "Word", "ok": True},
    {"step": 2, "operation": "input.visible.click", "label": "Documento en blanco", "index": 11, "ok": True, "changed": True},
]


def test_a_done_citing_a_control_as_the_prompt_lists_it_is_that_controls_name_on_the_real_word_view() -> None:
    # Live check of the fix (t-long-2): the blank document opened and the model cited «Document «Documento1»», the
    # way the step's prompt lists the control; refused as «not in the view», it answered none.
    decision = _validate({"act": "done", "evidence": "Document «Documento1»"}, _view("word_documento"),
                         "creá un documento en blanco", _OPENED_BLANK)
    assert decision["operation"] == "done"
    assert decision["arguments"] == {"evidence": "Documento1"}
    # The second live check: the name alone in guillemets («Contenido de la página 1», the page's field).
    bare = _validate({"act": "done", "evidence": "«Contenido de la página 1»"}, _view("word_documento"),
                     "creá un documento en blanco", _OPENED_BLANK)
    assert bare["operation"] == "done" and bare["arguments"] == {"evidence": "Contenido de la página 1"}


def test_contracase_a_kind_the_control_does_not_have_or_a_sentence_stays_as_cited() -> None:
    view = _view("word_documento")
    for evidence in ("Button «Documento1»", "Document «Documento2»", "«Documento2»", "se abrió «Documento1» en blanco"):
        decision = _validate({"act": "done", "evidence": evidence}, view, "creá un documento en blanco", _OPENED_BLANK)
        assert decision["operation"] == "none", evidence


def test_contracase_a_place_goal_keeps_its_own_done() -> None:
    # «ir a X» needs no act: its done is the arrival's evidence, never a press.
    decision = _validate({"act": "done", "evidence": "Documento en blanco"}, _view("word_inicio"), "ir a inicio")
    assert decision["operation"] != "input.visible.click"


# ------------------------------------------------------------------ el encoder ocupado por el fondo (21 casos de r7)


class _Worker:
    """A router whose ``encode`` holds one lock like the real worker and logs who it served, in order."""

    def __init__(self, seconds: float) -> None:
        self.router = ProcessIntentRouter.__new__(ProcessIntentRouter)
        self.lock = threading.Lock()
        self.log: list[tuple[str, int]] = []
        self.started = threading.Event()
        self.seconds = seconds
        self.router.encode = self.encode  # type: ignore[method-assign]
        self.router.try_ready = lambda timeout=0.0: True  # type: ignore[method-assign]

    def encode(self, texts, timeout: float = 1.0, *, prefix: str = "query"):  # noqa: ANN001
        if not self.lock.acquire(timeout=timeout):
            raise TimeoutError("router worker is busy")
        try:
            self.started.set()
            time.sleep(self.seconds)
            self.log.append((prefix, len(texts)))
            return np.asarray([[float(len(text)), 1.0] for text in texts], dtype=np.float32)
        finally:
            self.lock.release()


def test_a_background_batch_is_encoded_in_chunks_with_the_same_rows() -> None:
    worker = _Worker(0.0)
    background = RequestBudgetEncoder(worker.router, offline_timeout=5.0)
    texts = [f"documento {index} " + "x" * (index % 7) for index in range(100)]
    rows = background(texts, prefix="passage")
    assert rows.shape == (100, 2)
    assert [float(row[0]) for row in rows] == [float(len(text)) for text in texts]
    chunk = router_module.BACKGROUND_ENCODER_CHUNK
    assert chunk < 100 and [count for _, count in worker.log] == [chunk] * (100 // chunk) + [100 % chunk] * bool(100 % chunk)


def test_an_interactive_step_is_served_before_the_next_background_chunk() -> None:
    worker = _Worker(0.15)
    background = RequestBudgetEncoder(worker.router, offline_timeout=5.0)
    interactive = RequestBudgetEncoder(worker.router)
    chunk = router_module.BACKGROUND_ENCODER_CHUNK
    texts = [f"herramienta {index}" for index in range(4 * chunk)]
    thread = threading.Thread(target=lambda: background(texts, prefix="passage"))
    thread.start()
    assert worker.started.wait(2.0)
    interactive.begin_request(0.75)
    try:
        assert interactive.try_ready(0.0)
        rows = interactive(["Configuración", "Ajustes"], prefix="query")
    finally:
        interactive.end_request()
    thread.join(5.0)
    assert rows.shape == (2, 2)
    # The interactive request waited at most the chunk in flight, never the whole batch.
    assert worker.log[:2] == [("passage", chunk), ("query", 2)], worker.log
    assert worker.log[2:] == [("passage", chunk)] * 3, worker.log


def _router_state(ready: bool, failed: bool = False) -> ProcessIntentRouter:
    router = ProcessIntentRouter.__new__(ProcessIntentRouter)
    router._lock = threading.Lock()
    router._is_ready = ready
    router._failed = failed
    router._closed = threading.Event()
    return router


def test_a_loaded_worker_busy_with_a_background_chunk_is_ready_at_once() -> None:
    # Live check of the fix (v3-15): step 1 waited E5's load and got its answer; step 2 found a chunk of the
    # catalog's promotion holding the worker, read «not ready» and went cold and literal.
    router = _router_state(ready=True)
    router._lock.acquire()
    try:
        started = time.monotonic()
        assert router.try_ready(0.0) is True
        assert time.monotonic() - started < 0.05
    finally:
        router._lock.release()


def test_contracase_a_loading_or_failed_worker_is_not_ready_while_the_lock_is_held() -> None:
    for router in (_router_state(ready=False), _router_state(ready=True, failed=True)):
        router._lock.acquire()
        try:
            assert router.try_ready(0.0) is False
        finally:
            router._lock.release()


def test_contracase_the_background_never_stalls_behind_a_marked_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router_module, "BACKGROUND_YIELD_SECONDS", 0.05)
    worker = _Worker(0.0)
    background = RequestBudgetEncoder(worker.router, offline_timeout=5.0)
    with worker.router.foreground():
        started = time.monotonic()
        rows = background([f"t{index}" for index in range(70)], prefix="passage")
    assert rows.shape == (70, 2)
    assert time.monotonic() - started < 2.0
    # Unmarked, it does not wait at all.
    assert worker.router.yield_to_foreground(0.01) is True
