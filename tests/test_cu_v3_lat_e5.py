"""lat-e5: el motor de computer use nunca bloquea esperando al codificador E5 (r13a/latencia.md, causa 1).

Medido sobre 104 misiones: 47 pasaron 5–15 s del paso 1 o 2 esperando a E5 (11 la asignación entera de 15 s) y el
modelo nunca tardó más de 2,1 s. Ahora ningún paso espera al codificador para decidir (nombre en pantalla, regla,
traducción del rótulo por el modelo, el modelo con la vista); sólo espera, con tope de 2 s, saber si un clic llegó por
su efecto, que es lo único que sólo el emparejamiento contesta. Contracaso v3-14: con E5 frío y sin traducción no se
teclea «video library» en una ventana en español: decide el modelo con la vista.
La carga del catálogo cede el worker mientras dura una misión, y el tiempo del codificador va aparte del del modelo.

r27 (bancos r23b, r23j, c24b y c25: 285 misiones): el paso de regla esperó 17 veces a E5 (≥ 1 s; 16 de ellas los 2 s
enteros). En 15 seguía frío al acabar la espera y en las 2 en que cargó (r23b n5 y u3) tampoco pulsó por semejanza:
la regla dio el mismo clic que con E5 frío (n5) o decidió el modelo (u3). Esa espera no decidió nada y se retiró.
"""

from __future__ import annotations

import copy
import json
import queue
import threading
import time
from pathlib import Path

import numpy as np
import pytest

from baxy_mind import computer_use
from baxy_mind import cu_meaning
from baxy_mind import cu_rules
from baxy_mind import cu_model_calls
from baxy_mind import router as router_module
from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
from baxy_mind.semantic import cu_semejanza

_DATA = Path(__file__).parent / "data"
_VIEWS = {view["case"]: view for view in json.loads((_DATA / "cu_semejanza_vistas.json").read_text(encoding="utf-8"))}
_V3_14_OBJECTIVE = "open media player, go to the video library and sort by date added"


def _view(case: str) -> dict:
    view = copy.deepcopy(_VIEWS[case])
    return {"window": view["window"], "controls": view["controls"], "text": {}}


class _NeverReady:
    """An E5 worker still loading, on a fake clock: ``try_ready(timeout)`` records the wait it was asked for and adds
    it to ``waited`` without sleeping; it never turns ready, so encoding fails like the router's."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    @property
    def waited(self) -> float:
        return sum(self.waits)

    def try_ready(self, timeout: float = 0.0) -> bool:
        self.waits.append(float(timeout))
        return False

    def begin_request(self, budget: float) -> None:  # noqa: ARG002 - the matcher renews it before encoding
        pass

    def __call__(self, texts, *, prefix: str = "query"):
        raise TimeoutError("router worker response timed out")


class _Model:
    """The local model: the label's translation (``la traducción de una etiqueta``) and the step, in order."""

    def __init__(self, translation: dict | None, *steps: dict) -> None:
        self.translation = translation if translation is not None else {"es": [], "en": []}
        self.steps = list(steps)
        self.labels: list[str] = []

    def _post_schema_object(self, payload: dict, label: str) -> object:
        self.labels.append(label)
        if label == "la traducción de una etiqueta":
            return self.translation
        if label != "el paso de computer use":
            return {}  # the route's hints: none
        return self.steps.pop(0) if self.steps else {"act": "none"}


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mind's row cache is per process: the fake encoders here never leave rows for other tests."""

    monkeypatch.setattr(cu_meaning, "_SEMANTIC_CACHE", cu_semejanza.EmbeddingCache())


@pytest.fixture
def cold(monkeypatch: pytest.MonkeyPatch) -> cu_meaning._ColdWait:
    """The mind's cold allowance as it starts (``ENCODER_COLD_WAIT_SECONDS``), fresh for each test."""

    allowance = cu_meaning._ColdWait(cu_meaning.ENCODER_COLD_WAIT_SECONDS)
    monkeypatch.setattr(cu_meaning, "_COLD_WAIT", allowance)
    return allowance


def _decide(model: _Model, encoder, goal: str, objective: str = _V3_14_OBJECTIVE, history: list | None = None) -> dict:
    return computer_use.decide_step(
        model, objective=objective, goal=goal, application=None, success_check=None, view=_view("v3-14"),
        history=history or [], budget_left=8, application_names=[], encoder=encoder,
    )


# ------------------------------------------------------------------ el paso no espera


def test_the_cold_allowance_is_at_most_two_seconds() -> None:
    # Owner's rule: more than 3 s without a sign is unacceptable; the model itself answers in ~0.9 s.
    assert 0.0 < cu_meaning.ENCODER_COLD_WAIT_SECONDS <= 2.0


def test_a_step_that_does_not_depend_on_the_match_never_waits(cold: cu_meaning._ColdWait) -> None:
    # r13a v2-v3-14 step 3: «sort by date added» (a free goal, no check) waited 8.7 s for E5 before the model, which
    # then took ~1 s. The model decides with the view at once; the encoder is only probed.
    encoder = _NeverReady()
    model = _Model(None, {"act": "click", "i": 21})
    decided = _decide(model, encoder, "sort by date added")
    assert decided["operation"] == "input.visible.click" and decided["arguments"]["label"] == "Ordenar por"
    assert decided["source"] == cu_meaning.SOURCE_MODEL and decided["encoder"] == cu_meaning.ENCODER_COLD
    assert encoder.waits and encoder.waited == 0.0
    # The allowance is kept for a step that does depend on the match.
    assert cold._left == pytest.approx(cu_meaning.ENCODER_COLD_WAIT_SECONDS)


def test_a_name_on_screen_by_translation_needs_no_encoder(cold: cu_meaning._ColdWait) -> None:
    # The label's translation by the model (~0.7 s) finds «Biblioteca de videos» on screen: pressed, nothing waited.
    encoder = _NeverReady()
    model = _Model({"es": ["Biblioteca de videos"], "en": []})
    decided = _decide(model, encoder, "ir a video library")
    assert decided["operation"] == "input.visible.click" and decided["arguments"]["label"] == "Biblioteca de videos"
    assert decided["alias"]["to"] == "Biblioteca de videos"
    assert encoder.waited == 0.0 and "el paso de computer use" not in model.labels


def test_a_rule_step_with_no_name_of_the_goal_on_screen_never_waits(cold: cu_meaning._ColdWait) -> None:
    # r27 (before: this step waited the whole allowance, 2 s): no name of the goal on screen, said or translated, and
    # the encoder loading. Nothing is waited and nothing is looked up blind: the step is the model's, with the view.
    encoder = _NeverReady()
    matcher = cu_meaning.SemanticMatcher(encoder, cu_semejanza.EmbeddingCache())
    step = cu_rules.deterministic_step(
        goal="ir a video library", view=_view("v3-14"), history=[], semantic=matcher, objective=_V3_14_OBJECTIVE,
    )
    assert step is None
    assert encoder.waits and encoder.waited == 0.0 and matcher.state == cu_meaning.ENCODER_COLD
    assert cold._left == pytest.approx(cu_meaning.ENCODER_COLD_WAIT_SECONDS)
    # Banco B n2 and x1 (the 2 s were spent before «Abrir navegación»): a rule with a way that needs no encoder takes
    # it at once, the same step as without an encoder.
    calculator = {
        "window": {"title": "Calculadora", "process": "CalculatorApp"},
        "controls": [
            {"i": 0, "kind": "Button", "name": "Abrir navegación"}, {"i": 1, "kind": "Text", "name": "Estándar"},
            {"i": 2, "kind": "Button", "name": "Raíz cuadrada"}, {"i": 3, "kind": "Button", "name": "Igual a"},
        ],
        "text": {},
    }
    encoder = _NeverReady()
    matcher = cu_meaning.SemanticMatcher(encoder, cu_semejanza.EmbeddingCache())
    opened = cu_rules.deterministic_step(goal="ir a Científica", view=calculator, history=[], semantic=matcher)
    assert opened is not None and opened["arguments"]["label"] == "Abrir navegación"
    assert opened == cu_rules.deterministic_step(goal="ir a Científica", view=calculator, history=[])
    assert encoder.waited == 0.0


def test_a_cold_answer_without_waiting_is_asked_again_by_a_step_that_waits() -> None:
    encoder = _NeverReady()
    matcher = cu_meaning.SemanticMatcher(encoder, cu_semejanza.EmbeddingCache(), cold_wait=cu_meaning._ColdWait(1.0))
    view = _view("v3-14")
    assert matcher.scored("video library", view) == () and encoder.waits == [0.0]
    assert matcher.scored("video library", view) == () and encoder.waits == [0.0]  # memoized
    assert matcher.scored("video library", view, wait=True) == ()
    assert encoder.waits == [0.0, 0.0, 1.0]
    assert matcher.scored("video library", view, wait=True) == () and len(encoder.waits) == 3


# ------------------------------------------------------------------ contracaso v3-14


def test_contracase_v3_14_a_cold_encoder_without_translation_never_types_the_english_name(cold: cu_meaning._ColdWait) -> None:
    # Live v3-14 (pasada 05:40): E5 cold and «video library» typed into the search with «Biblioteca de videos» on
    # screen. Now, the encoder still loading and no translation: the model decides with the view, nothing waited.
    encoder = _NeverReady()
    model = _Model({"es": [], "en": []}, {"act": "click", "i": 8})
    decided = _decide(model, encoder, "ir a video library")
    assert "el paso de computer use" in model.labels
    assert decided["operation"] == "input.visible.click" and decided["arguments"]["label"] == "Biblioteca de videos"
    assert decided["source"] == cu_meaning.SOURCE_MODEL and encoder.waited == 0.0
    # Review of lat-e5, finding 1: the model takes nothing, and the held search is its fallback (what the step did
    # before the hold), never a stop of the mission; the hold cost one model call.
    model = _Model({"es": [], "en": []}, {"act": "none"}, {"act": "none"})
    decided = _decide(model, _NeverReady(), "ir a video library")
    literal = cu_rules.deterministic_step(goal="ir a video library", view=_view("v3-14"), history=[])
    assert literal is not None and literal["operation"] != "none"
    assert "el paso de computer use" in model.labels
    assert {key: decided[key] for key in ("operation", "arguments")} == {key: literal[key] for key in ("operation", "arguments")}


# ------------------------------------------------------------------ revisión de lat-e5, hallazgo 1: la retención es
# sólo la del contracaso


_HOLLOW_OBJECTIVE = "open steam and go to hollow knight"


def _steam_view() -> dict:
    """A Spanish Steam library drawn with a tree (the reviewer's case): its search field, no «Hollow Knight» listed."""

    names = [
        ("ListItem", "Página principal"), ("ListItem", "Colecciones"), ("ListItem", "Descargas"),
        ("Edit", "Buscar en la biblioteca"), ("Text", "Juegos recientes"), ("Text", "Todos los juegos"),
        ("Button", "Agregar un juego"), ("Button", "Ordenar por nombre"),
    ]
    return {
        "window": {"title": "Steam", "process": "steamwebhelper"},
        "controls": [{"i": index, "kind": kind, "name": name} for index, (kind, name) in enumerate(names)],
        "text": {},
    }


def _decide_on(view: dict, model: _Model, encoder, goal: str, objective: str) -> dict:
    return computer_use.decide_step(
        model, objective=objective, goal=goal, application=None, success_check=None, view=view, history=[],
        budget_left=8, application_names=[], encoder=encoder,
    )


def _same_step(decided: dict, literal: dict | None) -> bool:
    return literal is not None and {key: decided.get(key) for key in ("operation", "arguments")} == {
        key: literal[key] for key in ("operation", "arguments")
    }


class _FailedE5:
    """A loaded E5 whose encoding ran out of time (state «failed»), never a loading one."""

    def try_ready(self, timeout: float = 0.0) -> bool:
        return True

    def begin_request(self, budget: float) -> None:  # noqa: ARG002
        pass

    def __call__(self, texts, *, prefix: str = "query"):
        raise TimeoutError("router worker response timed out")


def test_contracase_a_name_the_translator_gives_back_as_said_is_looked_up_without_the_model(
    cold: cu_meaning._ColdWait,
) -> None:
    # «ir a hollow knight» on a Spanish Steam with E5 cold: the translator gives the name itself back (a proper name,
    # it does not translate), so the search for it is the step, as before lat-e5; no model step, no 0.9 s more.
    view = _steam_view()
    literal = cu_rules.deterministic_step(goal="ir a hollow knight", view=view, history=[], objective=_HOLLOW_OBJECTIVE)
    assert literal is not None and literal["operation"] != "none"
    model = _Model({"es": ["Hollow Knight"], "en": ["Hollow Knight"]})
    decided = _decide_on(view, model, _NeverReady(), "ir a hollow knight", _HOLLOW_OBJECTIVE)
    assert _same_step(decided, literal) and "el paso de computer use" not in model.labels


def test_contracase_a_held_search_the_model_declines_is_still_the_step(cold: cu_meaning._ColdWait) -> None:
    # The translator gave nothing (no name, not even the said one): the model decides first, and its «none» falls back
    # to the search, never a stop (the reviewer's repro stopped here).
    view = _steam_view()
    literal = cu_rules.deterministic_step(goal="ir a hollow knight", view=view, history=[], objective=_HOLLOW_OBJECTIVE)
    model = _Model({"es": [], "en": []}, {"act": "none"}, {"act": "none"})
    decided = _decide_on(view, model, _NeverReady(), "ir a hollow knight", _HOLLOW_OBJECTIVE)
    assert "el paso de computer use" in model.labels and _same_step(decided, literal)


def test_contracase_a_loaded_encoder_that_failed_is_no_hold(cold: cu_meaning._ColdWait) -> None:
    # «failed» is a loaded E5 out of time (or a worker gone mid-step): the hold is for the cold start alone, so the
    # search goes on as before, with no model step.
    for view, goal, objective in (
        (_steam_view(), "ir a hollow knight", _HOLLOW_OBJECTIVE),
        (_view("v3-14"), "ir a video library", _V3_14_OBJECTIVE),
    ):
        literal = cu_rules.deterministic_step(goal=goal, view=view, history=[], objective=objective)
        model = _Model({"es": [], "en": []})
        decided = _decide_on(view, model, _FailedE5(), goal, objective)
        assert decided.get("encoder") == cu_meaning.ENCODER_FAILED
        assert _same_step(decided, literal) and "el paso de computer use" not in model.labels


def test_the_translator_tells_a_name_given_back_from_no_name() -> None:
    as_said = cu_model_calls.LabelTranslator(_Model({"es": ["Hollow Knight"], "en": ["hollow knight"]}))
    assert as_said("hollow knight") == () and as_said.said_as_is("Hollow Knight")
    empty = cu_model_calls.LabelTranslator(_Model({"es": [], "en": []}))
    assert empty("hollow knight") == () and not empty.said_as_is("hollow knight")
    # A real translation is a translation, never «as said».
    named = cu_model_calls.LabelTranslator(_Model({"es": ["Biblioteca de videos", "video library"], "en": []}))
    assert named("video library") == ("Biblioteca de videos",) and not named.said_as_is("video library")


# ------------------------------------------------------------------ revisión de lat-e5, hallazgo 3: la llegada por
# efecto espera al codificador que carga


class _ReadyOnWait:
    """An E5 still loading that is ready once a step waits for it, on a fake clock (no sleep): ``try_ready(0)`` is
    False until a wait was asked. Its rows put the place's name and «Biblioteca de videos» together."""

    def __init__(self, near: dict[str, float]) -> None:
        self.near = near
        self.waits: list[float] = []
        self.loaded = False

    def try_ready(self, timeout: float = 0.0) -> bool:
        self.waits.append(float(timeout))
        self.loaded = self.loaded or timeout > 0
        return self.loaded

    def begin_request(self, budget: float) -> None:  # noqa: ARG002
        pass

    def __call__(self, texts, *, prefix: str = "query"):
        if not self.loaded:
            raise TimeoutError("router worker response timed out")
        angles = [np.arccos(self.near.get(str(text), 0.1)) for text in texts]
        return np.asarray([[np.cos(angle), np.sin(angle)] for angle in angles], dtype=np.float32)


def test_a_click_that_arrived_is_told_by_its_effect_while_e5_loads(cold: cu_meaning._ColdWait) -> None:
    # The model pressed «Biblioteca de videos» for «video library» while E5 loaded; the window changed and shows the
    # video page. The arrival is judged by the match, waited for (fake clock), never a second click on it.
    view = _view("v3-14")
    for control in view["controls"]:
        if control.get("name") == "Biblioteca de música":
            control.pop("state", None)
        if control.get("name") == "Biblioteca de videos":
            control["state"] = "selected"
    view["controls"].append({"i": 23, "kind": "Text", "name": "No se encontró ningún video"})
    view["newTextAfterClick"] = ["No se encontró ningún video"]
    history = [{
        "operation": "input.visible.click", "label": "Biblioteca de videos", "index": 8, "ok": True, "changed": True,
        "surfaceChanged": True,
    }]
    encoder = _ReadyOnWait({"video library": 1.0, "Biblioteca de videos": 0.95})
    model = _Model(None, {"act": "click", "i": 8})
    decided = computer_use.decide_step(
        model, objective=_V3_14_OBJECTIVE, goal="ir a video library", application=None, success_check=None, view=view,
        history=history, budget_left=8, application_names=[], encoder=encoder,
    )
    assert decided["operation"] == "done" and decided["reason"] == cu_meaning.REASON_ARRIVED_BY_EFFECT
    assert decided["arguments"]["evidence"] == "No se encontró ningún video"
    assert "el paso de computer use" not in model.labels
    assert max(encoder.waits) == pytest.approx(cu_meaning.ENCODER_COLD_WAIT_SECONDS)
    # Contracase: a warm mind (the allowance spent) never waits; the step is the model's as before.
    encoder = _ReadyOnWait({"video library": 1.0, "Biblioteca de videos": 0.95})
    cold._left = 0.0
    decided = computer_use.decide_step(
        _Model(None, {"act": "none"}), objective=_V3_14_OBJECTIVE, goal="ir a video library", application=None,
        success_check=None, view=view, history=history, budget_left=8, application_names=[], encoder=encoder,
    )
    assert decided.get("reason") != cu_meaning.REASON_ARRIVED_BY_EFFECT and max(encoder.waits) == 0.0


# ------------------------------------------------------------------ revisión de lat-e5, hallazgo 5: la misión suelta
# el worker al terminar


def test_a_step_that_ends_the_mission_frees_the_worker() -> None:
    assert computer_use.ends_mission({"operation": "none"}, 0, 1)
    assert computer_use.ends_mission({"operation": "done"}, 1, 2)
    assert computer_use.ends_mission({"operation": "done"}, 0, 0)
    # Contracases: a sub-goal reached before the last one, and any act, keep the hold.
    assert not computer_use.ends_mission({"operation": "done"}, 0, 2)
    assert not computer_use.ends_mission({"operation": "input.visible.click"}, 1, 2)
    assert not computer_use.ends_mission({}, 0, 1)


def test_contracase_a_place_said_in_the_windows_language_is_still_looked_up(cold: cu_meaning._ColdWait) -> None:
    # The hold is only for a name said in another language: «biblioteca de fotos» on a Spanish window is looked up
    # the way the window offers, as without an encoder.
    encoder = _NeverReady()
    model = _Model({"es": [], "en": []})
    decided = _decide(
        model, encoder, "ir a biblioteca de fotos", objective="abrí el reproductor multimedia y andá a la biblioteca de fotos",
    )
    literal = cu_rules.deterministic_step(goal="ir a biblioteca de fotos", view=_view("v3-14"), history=[])
    assert literal is not None
    assert {key: decided[key] for key in ("operation", "arguments")} == {key: literal[key] for key in ("operation", "arguments")}
    assert "el paso de computer use" not in model.labels


def test_contracase_a_translation_not_on_screen_is_looked_up_by_the_windows_name(cold: cu_meaning._ColdWait) -> None:
    # With a translation the search types the window's language's name: the encoder adds nothing to it.
    view = _view("v3-14")
    view["controls"] = [control for control in view["controls"] if control.get("name") != "Biblioteca de videos"]
    model = _Model({"es": ["Biblioteca de videos"], "en": []})
    decided = computer_use.decide_step(
        model, objective=_V3_14_OBJECTIVE, goal="ir a video library", application=None, success_check=None, view=view,
        history=[], budget_left=8, application_names=[], encoder=_NeverReady(),
    )
    assert decided["operation"] != "none" and "el paso de computer use" not in model.labels


# ------------------------------------------------------------------ tiempo del codificador aparte


class _SlowE5:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def try_ready(self, timeout: float = 0.0) -> bool:
        return True

    def __call__(self, texts, *, prefix: str = "query"):
        time.sleep(self.seconds)
        return np.asarray([[1.0, float(len(text))] for text in texts], dtype=np.float32)


def test_the_step_reports_its_time_in_the_encoder_apart_from_the_model() -> None:
    decided = _decide(_Model(None, {"act": "click", "i": 21}), _SlowE5(0.05), "sort by date added")
    assert decided["encoderMs"] >= 40
    # A step that never asks the encoder says nothing of it.
    plain = _decide(_Model(None, {"act": "click", "i": 21}), None, "sort by date added")
    assert "encoderMs" not in plain


# ------------------------------------------------------------------ el catálogo cede el worker durante la misión


class _Worker:
    """A router whose ``encode`` holds one lock like the real worker and logs who it served, with the time."""

    def __init__(self) -> None:
        self.router = ProcessIntentRouter.__new__(ProcessIntentRouter)
        self.router._closed = threading.Event()
        self.lock = threading.Lock()
        self.log: list[tuple[str, int, float]] = []
        self.router.encode = self.encode  # type: ignore[method-assign]
        self.router.try_ready = lambda timeout=0.0: True  # type: ignore[method-assign]

    def encode(self, texts, timeout: float = 1.0, *, prefix: str = "query"):  # noqa: ANN001
        if not self.lock.acquire(timeout=timeout):
            raise TimeoutError("router worker is busy")
        try:
            self.log.append((prefix, len(texts), time.monotonic()))
            return np.asarray([[float(len(text)), 1.0] for text in texts], dtype=np.float32)
        finally:
            self.lock.release()


def test_the_catalog_promotion_leaves_the_worker_to_a_mission_until_its_hold_runs_out() -> None:
    worker = _Worker()
    background = RequestBudgetEncoder(worker.router, offline_timeout=5.0)
    interactive = RequestBudgetEncoder(worker.router)
    # Review of lat-e5, finding 7: real clock, so the bounds are what a loaded machine keeps: the hold (1.5 s) is far
    # longer than serving one step, and the order of the log proves the rest.
    worker.router.hold_background(1.5)
    held_at = time.monotonic()
    texts = [f"herramienta {index}" for index in range(3 * router_module.BACKGROUND_ENCODER_CHUNK)]
    thread = threading.Thread(target=lambda: background(texts, prefix="passage"))
    thread.start()
    time.sleep(0.1)
    interactive.begin_request(0.75)
    try:
        rows = interactive(["Biblioteca de videos"], prefix="query")
    finally:
        interactive.end_request()
    thread.join(5.0)
    assert rows.shape == (1, 2) and not thread.is_alive()
    # The step was served at once; no background chunk ran while the hold lasted, all of them after it.
    assert worker.log[0][0] == "query" and worker.log[0][2] - held_at < 1.0
    passages = [at for prefix, _, at in worker.log if prefix == "passage"]
    assert len(passages) == 3 and min(passages) - held_at >= 1.45


def test_a_small_background_batch_also_waits_for_the_hold() -> None:
    worker = _Worker()
    background = RequestBudgetEncoder(worker.router, offline_timeout=5.0)
    worker.router.hold_background(0.25)
    started = time.monotonic()
    background(["una"], prefix="passage")
    assert time.monotonic() - started >= 0.23


def test_contracase_the_hold_ends_by_itself_on_release_and_on_close() -> None:
    worker = _Worker()
    background = RequestBudgetEncoder(worker.router, offline_timeout=5.0)
    # Without a hold the background does not wait at all (real clock: far below the yield's 2 s and any hold).
    started = time.monotonic()
    background([f"t{index}" for index in range(20)], prefix="passage")
    assert time.monotonic() - started < 1.0
    # A later, shorter hold never shortens a longer one; release ends it at once (well before the 30 s hold).
    worker.router.hold_background(30.0)
    worker.router.hold_background(0.01)
    threading.Timer(0.2, worker.router.release_background).start()
    started = time.monotonic()
    background(["una"], prefix="passage")
    assert 0.15 <= time.monotonic() - started < 10.0
    # A closing router is never held.
    worker.router.hold_background(30.0)
    worker.router._closed.set()
    started = time.monotonic()
    assert worker.router.yield_to_foreground(0.01) is True
    assert time.monotonic() - started < 10.0


# ------------------------------------------------------------------ E5 arranca con la mente


def test_the_e5_worker_starts_with_the_mind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAXY_MIND_ROUTER_START_DELAY", raising=False)
    assert router_module.ROUTER_START_DELAY_SECONDS == 0.0
    router = ProcessIntentRouter.__new__(ProcessIntentRouter)
    waited: list[float] = []

    class _Closed(threading.Event):
        def wait(self, timeout: float | None = None) -> bool:
            waited.append(float(timeout or 0.0))
            return True  # closed: the launch stops before spawning anything

    router._closed = _Closed()
    router._launch_and_read(responses=queue.Queue())
    assert waited == [0.0]
