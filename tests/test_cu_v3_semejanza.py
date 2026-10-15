"""Parecido de significado en computer use (goal v3, r5a/decision.md P1–P5).

P1: el lugar que nombra un objetivo se empareja por significado (E5) con los nombres de la vista; el clic sin modelo
sólo pasa el umbral y el margen calibrados y los filtros de seguridad, y si no, decide el modelo con los parecidos a la
vista, nunca la búsqueda directa. P2: la línea de parecidos y el reintento sin «none». P3: llegada por efecto. P4: el
campo de búsqueda por su nombre y los atajos sólo sobre un campo de búsqueda. P5: abrir lo plegado antes de buscar.

Dos encoders: uno falso de vectores fijos (umbrales, margen y filtros) y las filas reales de E5-small congeladas sobre
las vistas del journal de la pasada r3 (scripts/cu_semejanza_congelar.py), sin cargar el modelo.
"""

from __future__ import annotations

import copy
import json
import math
import time
from pathlib import Path

import numpy as np
import pytest

from baxy_mind import computer_use
from baxy_mind import cu_fields
from baxy_mind import cu_acts
from baxy_mind import cu_meaning
from baxy_mind import cu_lookup
from baxy_mind import cu_rules
from baxy_mind import cu_evidence
from baxy_mind import cu_model_calls
from baxy_mind import cu_step_prompt
from baxy_mind.semantic import cu_semejanza
from baxy_mind.semantic.missions import _LABEL_ALIASES, fold

_DATA = Path(__file__).parent / "data"
_VIEWS = {view["case"]: view for view in json.loads((_DATA / "cu_semejanza_vistas.json").read_text(encoding="utf-8"))}


class _FrozenE5:
    """The real E5-small rows of the frozen views (float16), looked up by prefix and text."""

    def __init__(self) -> None:
        keys = json.loads((_DATA / "cu_semejanza_e5.json").read_text(encoding="utf-8"))
        rows = np.load(_DATA / "cu_semejanza_e5.npy").astype(np.float32)
        self._rows = {key: row / np.linalg.norm(row) for key, row in zip(keys, rows)}
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def __call__(self, texts, *, prefix: str = "query"):
        self.calls.append((prefix, tuple(texts)))
        return np.stack([self._rows[f"{prefix}: {text}"] for text in texts])


_E5 = _FrozenE5()


def _matcher() -> cu_meaning.SemanticMatcher:
    return cu_meaning.SemanticMatcher(_E5, cu_semejanza.EmbeddingCache())


def _view(case: str, without: str | None = None) -> dict:
    view = copy.deepcopy(_VIEWS[case])
    controls = [control for control in view["controls"] if control.get("name") != without]
    return {"window": view["window"], "controls": controls, "text": {}}


class _Vectors:
    """A fake encoder: each text is a fixed unit vector at an angle, so cos = cos(angle difference)."""

    def __init__(self, angles: dict[str, float]) -> None:
        self.angles = angles

    def __call__(self, texts, *, prefix: str = "query"):
        return np.array([[math.cos(self.angles[text]), math.sin(self.angles[text])] for text in texts])


def _angle(similarity: float) -> float:
    return math.acos(similarity)


# ------------------------------------------------------------------ P1 con encoder falso


def _fake_view(*controls: dict) -> dict:
    return {"window": {"title": "App", "process": "app"}, "controls": list(controls), "text": {}}


def _fake(names: dict[str, float], label: str = "video library") -> cu_meaning.SemanticMatcher:
    angles = {label: 0.0, **{name: _angle(similarity) for name, similarity in names.items()}}
    return cu_meaning.SemanticMatcher(_Vectors(angles), cu_semejanza.EmbeddingCache())


def test_a_similar_name_past_threshold_and_margin_is_clicked_with_its_alias() -> None:
    view = _fake_view(
        {"i": 3, "kind": "ListItem", "name": "Biblioteca de videos"},
        {"i": 4, "kind": "ListItem", "name": "Biblioteca de música"},
    )
    semantic = _fake({"Biblioteca de videos": 0.90, "Biblioteca de música": 0.85})
    step = cu_rules.deterministic_step(goal="ir a video library", view=view, history=[], semantic=semantic)
    assert step == {
        "operation": "input.visible.click", "arguments": {"label": "Biblioteca de videos", "index": 3},
        "reason": cu_meaning.REASON_SIMILAR,
        # Review r10a finding 5: the alias says it was picked by resemblance.
        "alias": {"from": "video library", "to": "Biblioteca de videos", "by": cu_meaning.SOURCE_SEMANTIC},
    }


def test_below_the_threshold_or_the_margin_the_model_decides_never_the_search() -> None:
    search = {"i": 9, "kind": "Edit", "name": "Buscar"}
    close = _fake_view({"i": 3, "kind": "ListItem", "name": "Biblioteca de videos"}, {"i": 4, "kind": "ListItem", "name": "Videos"}, search)
    narrow = _fake({"Biblioteca de videos": 0.90, "Videos": 0.885, "Buscar": 0.70})
    assert cu_rules.deterministic_step(goal="ir a video library", view=close, history=[], semantic=narrow) is None
    low = _fake({"Biblioteca de videos": 0.845, "Videos": 0.70, "Buscar": 0.70})
    assert cu_rules.deterministic_step(goal="ir a video library", view=close, history=[], semantic=low) is None
    # Contracase: nothing similar at all → the literal search, as without an encoder.
    unlike = _fake({"Biblioteca de videos": 0.70, "Videos": 0.70, "Buscar": 0.70})
    literal = cu_rules.deterministic_step(goal="ir a video library", view=close, history=[])
    assert literal is not None and literal["arguments"]["label"] == "Buscar"
    assert cu_rules.deterministic_step(goal="ir a video library", view=close, history=[], semantic=unlike) == literal


def test_an_extension_of_the_same_name_does_not_count_against_the_margin() -> None:
    view = _fake_view(
        {"i": 1, "kind": "ListItem", "name": "Firewall y protección de red"},
        {"i": 2, "kind": "Text", "name": "Firewall y protección de red, No se requiere ninguna acción."},
    )
    semantic = _fake(
        {"Firewall y protección de red": 0.873, "Firewall y protección de red, No se requiere ninguna acción.": 0.865},
        label="firewall & network protection",
    )
    step = cu_rules.deterministic_step(goal="ir a firewall & network protection", view=view, history=[], semantic=semantic)
    assert step is not None and step["arguments"] == {"label": "Firewall y protección de red", "index": 1}
    assert cu_semejanza.same_name_extension("Vídeo", "Vídeo, 2 elementos")
    assert not cu_semejanza.same_name_extension("Tabla", "Deshacer Insertar tabla")


@pytest.mark.parametrize("control", [
    {"i": 1, "kind": "CheckBox", "name": "Mantener la relación de aspecto", "state": "on"},
    {"i": 1, "kind": "Button", "name": "Eliminar biblioteca"},
    {"i": 1, "kind": "Button", "name": "Deshacer Insertar tabla"},
    {"i": 1, "kind": "Button", "name": "Repetir Insertar tabla"},
    {"i": 1, "kind": "Button", "name": "Suscribirse"},
    {"i": 1, "kind": "Button", "name": "Cerrar Reproductor multimedia"},
    {"i": 1, "kind": "Button", "name": "Abrir en una ventana nueva"},
    {"i": 1, "kind": "DataItem", "name": "Biblioteca de videos"},
    {"i": 1, "kind": "Text", "name": "Biblioteca de videos"},
])
def test_the_safety_filters_never_press_by_meaning(control: dict) -> None:
    view = _fake_view(control, {"i": 2, "kind": "ListItem", "name": "Otra cosa"})
    semantic = _fake({control["name"]: 0.95, "Otra cosa": 0.70})
    step = cu_rules.deterministic_step(goal="ir a video library", view=view, history=[], semantic=semantic)
    assert step is None or step["arguments"].get("index") != 1


def test_a_switch_is_pressed_by_meaning_only_when_the_goal_switches_it() -> None:
    switch = {"i": 1, "kind": "CheckBox", "name": "Mantener la relación de aspecto", "state": "on"}
    view = _fake_view(switch, {"i": 2, "kind": "Button", "name": "Aceptar"})
    semantic = _fake({switch["name"]: 0.92, "Aceptar": 0.70}, label="keep aspect ratio")
    off = cu_rules.deterministic_step(goal="desactivar keep aspect ratio", view=view, history=[], semantic=semantic)
    assert off is not None and off["arguments"] == {"label": switch["name"], "index": 1}
    going = cu_rules.deterministic_step(goal="ir a keep aspect ratio", view=view, history=[], semantic=semantic)
    assert going is None or going["arguments"].get("index") != 1


def test_no_click_by_meaning_in_a_window_that_writes_to_people() -> None:
    view = _fake_view(
        {"i": 1, "kind": "ListItem", "name": "Biblioteca de videos"},
        {"i": 2, "kind": "Edit", "name": "Escribe un mensaje"},
    )
    semantic = _fake({"Biblioteca de videos": 0.95, "Escribe un mensaje": 0.70})
    step = cu_rules.deterministic_step(goal="ir a video library", view=view, history=[], semantic=semantic)
    assert step is None or step["arguments"].get("index") != 1


def test_an_encoder_that_fails_or_runs_out_of_time_keeps_the_literal_step() -> None:
    view = _fake_view({"i": 3, "kind": "ListItem", "name": "Biblioteca de videos"}, {"i": 9, "kind": "Edit", "name": "Buscar"})

    def expired(texts, *, prefix="query"):
        raise TimeoutError("interactive encoder budget expired")

    literal = cu_rules.deterministic_step(goal="ir a video library", view=view, history=[])
    semantic = cu_meaning.SemanticMatcher(expired, cu_semejanza.EmbeddingCache())
    assert cu_rules.deterministic_step(goal="ir a video library", view=view, history=[], semantic=semantic) == literal
    assert cu_semejanza.similar_names("video library", ["Biblioteca de videos"], expired) == ()


class _BudgetE5:
    """The frozen E5 rows behind a request deadline, as the mind's RequestBudgetEncoder: past it, TimeoutError."""

    def __init__(self) -> None:
        self.deadline: float | None = None
        self.opened: list[float] = []

    def begin_request(self, budget_seconds: float) -> None:
        self.opened.append(budget_seconds)
        self.deadline = time.monotonic() + budget_seconds

    def __call__(self, texts, *, prefix: str = "query"):
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise TimeoutError("interactive encoder budget expired")
        return _E5(texts, prefix=prefix)


def test_a_slow_label_translation_does_not_spend_the_encoder_budget() -> None:
    # Review of P1: the request's encoder budget opened on arrival; a translation by the model that came first in the
    # step used it up and the click by meaning depended on the clock. The matcher renews it to what the encoder alone
    # has spent.
    view = _view("v3-14")
    encoder = _BudgetE5()
    encoder.begin_request(cu_semejanza.ENCODER_BUDGET_SECONDS)  # the request's arrival (__main__)

    def slow(label: str) -> tuple[str, ...]:
        time.sleep(cu_semejanza.ENCODER_BUDGET_SECONDS + 0.1)
        return ()

    semantic = cu_meaning.SemanticMatcher(encoder, cu_semejanza.EmbeddingCache())
    step = cu_rules.deterministic_step(goal="ir a video library", view=view, history=[], translate=slow, semantic=semantic)
    assert step is not None and step["reason"] == cu_meaning.REASON_SIMILAR
    assert step["arguments"]["label"] == "Biblioteca de videos"
    assert encoder.opened[1] <= cu_semejanza.ENCODER_BUDGET_SECONDS
    # Contracase: once the encoder itself has spent the step's budget, the step is exactly the literal one.
    spent = cu_meaning.SemanticMatcher(encoder, cu_semejanza.EmbeddingCache(), budget_seconds=0.0)
    literal = cu_rules.deterministic_step(goal="ir a video library", view=view, history=[])
    assert cu_rules.deterministic_step(goal="ir a video library", view=view, history=[], semantic=spent) == literal


def test_the_rows_are_cached_by_name_across_steps() -> None:
    cache = cu_semejanza.EmbeddingCache()
    calls: list[tuple[str, ...]] = []
    vectors = _Vectors({"video library": 0.0, "Biblioteca de videos": 0.3, "Música": 1.0})

    def encode(texts, *, prefix="query"):
        calls.append(tuple(texts))
        return vectors(texts, prefix=prefix)

    cu_semejanza.similar_names("video library", ["Biblioteca de videos", "Música"], encode, cache=cache)
    cu_semejanza.similar_names("video library", ["Biblioteca de videos", "Música"], encode, cache=cache)
    assert calls == [("video library",), ("Biblioteca de videos", "Música")]


# ------------------------------------------------------------------ P1 con E5 real sobre vistas congeladas


@pytest.mark.parametrize(("case", "goal", "name"), [
    ("v3-14", "ir a video library", "Biblioteca de videos"),
    ("v3-62", "ir a firewall & network protection", "Firewall y protección de red"),
    ("v3-01", "presentacion en blanco", "Presentación en blanco"),
    ("t-long-2", "creá un documento en blanco", "Documento en blanco"),
])
def test_real_e5_presses_the_measured_destination(case: str, goal: str, name: str) -> None:
    view = _view(case)
    literal = cu_rules.deterministic_step(goal=goal, view=view, history=[])
    assert literal is None or literal["arguments"].get("label") != name
    step = cu_rules.deterministic_step(goal=goal, view=view, history=[], semantic=_matcher())
    assert step is not None and step["operation"] == "input.visible.click" and step["reason"] == cu_meaning.REASON_SIMILAR
    assert step["arguments"]["label"] == name and step["alias"]["to"] == name


def test_real_e5_keeps_the_literal_click_when_the_name_is_on_screen() -> None:
    # v3-52: «video» already finds «Vídeo» by its letters; the match by meaning changes nothing.
    view = _view("v3-52")
    literal = cu_rules.deterministic_step(goal="ir a video", view=view, history=[])
    assert literal is not None and literal["arguments"]["label"] == "Vídeo"
    assert cu_rules.deterministic_step(goal="ir a video", view=view, history=[], semantic=_matcher()) == literal


def test_real_e5_never_presses_the_aspect_ratio_switch_to_resize() -> None:
    # Contracase t-form-1: «cambiale el tamaño a la imagen» puts «Mantener la relación de aspecto» first (0.845).
    view = _view("t-form-1")
    step = cu_rules.deterministic_step(goal="cambiale el tamaño a la imagen", view=view, history=[], semantic=_matcher())
    assert step is None or step["arguments"].get("label") != "Mantener la relación de aspecto"
    hints = cu_step_prompt._similar_controls("cambiale el tamaño a la imagen", view, (), _matcher())
    assert "Mantener la relación de aspecto" not in [control.get("name") for control in hints]


def test_real_e5_never_presses_undo_or_redo_to_insert_a_table() -> None:
    # Contracase t-form-3: «Repetir/Deshacer Insertar tabla» ranks before «Tabla».
    view = _view("t-form-3")
    view["controls"].append({"i": 900, "kind": "Button", "name": "Deshacer Insertar tabla"})
    for goal in ("Insert a table", "insert table", "hacer clic en Insert a table"):
        step = cu_rules.deterministic_step(goal=goal, view=view, history=[], semantic=_matcher())
        assert step is None or not cu_semejanza.undoes_or_repeats(step["arguments"].get("label"))
    hints = cu_step_prompt._similar_controls("Insert a table", view, (), _matcher())
    assert hints and not any(cu_semejanza.undoes_or_repeats(control.get("name")) for control in hints)


def _unfolded(view: dict) -> dict:
    for control in view["controls"]:
        if control.get("state") == "collapsed":
            del control["state"]
    return view


def test_real_e5_opens_the_most_similar_menu_then_leaves_close_calls_to_the_model() -> None:
    # t-menu-3: «view» → «Ver» is first but by 0.022: no click by meaning. «Ver» is a collapsed menu: P5 opens it
    # before any search (the literal path pressed ctrl_k and typed «view» into «Insertar vínculo»).
    view = _view("t-menu-3")
    literal = cu_rules.deterministic_step(goal="ir a view", view=view, history=[])
    assert literal is None or literal["arguments"].get("label") != "Ver"
    opened = cu_rules.deterministic_step(goal="ir a view", view=view, history=[], semantic=_matcher())
    assert opened is not None and opened["arguments"] == {"label": "Ver", "index": 8}
    # With nothing folded, the model decides and sees «Ver» as similar.
    flat = _unfolded(_view("t-menu-3"))
    assert cu_rules.deterministic_step(goal="ir a view", view=flat, history=[], semantic=_matcher()) is None
    hints = cu_step_prompt._similar_controls("ir a view", flat, (), _matcher())
    assert "Ver" in [control.get("name") for control in hints]


def test_real_e5_never_presses_when_the_destination_is_absent() -> None:
    # Neither P1 (a click by meaning) nor P5 (opening a collapsed control) fires on a view without the destination:
    # review of P5, which opened the window's system menu, the account menu and the quick access toolbar.
    by_meaning = {cu_meaning.REASON_SIMILAR, cu_meaning.REASON_UNFOLD}
    for case, view in _VIEWS.items():
        absent = _view(case, without=view["target"])
        for label in view["labels"]:
            for goal in (f"ir a {label}", label):
                step = cu_rules.deterministic_step(goal=goal, view=absent, history=[], semantic=_matcher())
                assert step is None or step.get("reason") not in by_meaning, (case, goal, step)


def _expired(texts, *, prefix="query"):
    raise TimeoutError("interactive encoder budget expired")


@pytest.mark.parametrize(("case", "goal"), [
    ("v3-62", "ir a cortafuegos"), ("v3-37", "ir a cortafuegos"), ("v3-30", "ir a cortafuegos"),
    ("v3-01", "ir a plantillas"), ("v3-02", "ir a fade"), ("v3-03b", "ir a slide sorter"), ("v3-03a", "add a new slide"),
    ("t-form-3", "ir a insert table"), ("v3-14", "ir a video library"), ("t-menu-3", "ir a view"),
])
def test_an_encoder_down_or_out_of_time_opens_nothing_folded(case: str, goal: str) -> None:
    # Review of P5: with no similarity at all nothing was ranked and the first collapsed control in view order won
    # («Sistema», the account «APELLIDO EJEMPLO PERSONA A»). Now the step is exactly the literal one.
    view = _view(case)
    literal = cu_rules.deterministic_step(goal=goal, view=view, history=[])
    down = cu_meaning.SemanticMatcher(_expired, cu_semejanza.EmbeddingCache())
    assert cu_rules.deterministic_step(goal=goal, view=view, history=[], semantic=down) == literal


def _framed(*controls: dict) -> dict:
    return {
        "window": {"title": "Presentación1 - PowerPoint", "process": "app", "rect": {"x": 165, "y": 157, "w": 1424, "h": 732}},
        "controls": [
            {"i": 0, "kind": "MenuItem", "name": "Sistema", "state": "collapsed"},
            {"i": 1, "kind": "MenuItem", "name": "Cuenta de Ana Pérez", "state": "collapsed", "rect": {"x": 1345, "y": 158, "w": 63, "h": 60}},
            {"i": 2, "kind": "Button", "name": "Minimizar", "rect": {"x": 1408, "y": 158, "w": 60, "h": 60}},
            {"i": 3, "kind": "Button", "name": "Cerrar", "rect": {"x": 1528, "y": 158, "w": 60, "h": 60}},
            *controls,
        ],
        "text": {},
    }


def test_p5_never_opens_the_system_menu_nor_the_title_bar_even_when_similar() -> None:
    view = _framed(
        {"i": 4, "kind": "Button", "name": "Diseño", "state": "collapsed", "rect": {"x": 300, "y": 260, "w": 80, "h": 40}},
        {"i": 5, "kind": "Edit", "name": "Buscar", "rect": {"x": 600, "y": 168, "w": 300, "h": 40}},
    )
    semantic = _fake({"Sistema": 0.95, "Cuenta de Ana Pérez": 0.86, "Minimizar": 0.70, "Cerrar": 0.70, "Diseño": 0.88, "Buscar": 0.70},
                     label="plantillas")
    step = cu_rules.deterministic_step(goal="ir a plantillas", view=view, history=[], semantic=semantic)
    assert step is not None and step["arguments"] == {"label": "Diseño", "index": 4} and step["reason"] == cu_meaning.REASON_UNFOLD
    # The system menu (no rectangle) is never shown as similar; the account in the title bar is never opened.
    assert "Sistema" not in [control["name"] for control in cu_step_prompt._similar_controls("ir a plantillas", view, (), semantic)]
    account = _fake({"Sistema": 0.95, "Cuenta de Ana Pérez": 0.95, "Minimizar": 0.70, "Cerrar": 0.70, "Diseño": 0.85, "Buscar": 0.70},
                    label="plantillas")
    step = cu_rules.deterministic_step(goal="ir a plantillas", view=view, history=[], semantic=account)
    assert step is None or step["arguments"]["label"] not in ("Sistema", "Cuenta de Ana Pérez")
    # Contracase: below the floor nothing is opened, whatever its place in the view: the literal search.
    low = _fake({"Sistema": 0.95, "Cuenta de Ana Pérez": 0.70, "Minimizar": 0.70, "Cerrar": 0.70, "Diseño": 0.80, "Buscar": 0.70},
                label="plantillas")
    literal = cu_rules.deterministic_step(goal="ir a plantillas", view=view, history=[])
    assert cu_rules.deterministic_step(goal="ir a plantillas", view=view, history=[], semantic=low) == literal


def _pick(label: str, names: list[str]) -> str | None:
    scored = cu_semejanza.similar_names(label, names, _E5, cache=cu_semejanza.EmbeddingCache())
    return cu_semejanza.semantic_pick(scored, lambda name: not cu_semejanza.undoes_or_repeats(name))


def test_calibration_precision_on_the_measured_pairs_and_the_label_table() -> None:
    """τ/δ (cu_semejanza.CLICK_SIMILARITY/CLICK_MARGIN): over the pairs with a verified arrival of the r3 pass and the
    Spanish/English pairs of the label table placed in the real views, a click by meaning lands on the right control
    at least 98 % of the times it fires, and fires on a good share of them."""

    fired = right = pairs = 0
    measured = {
        "v3-14": ["video library"], "v3-62": ["firewall & network protection"], "v3-01": ["presentacion en blanco", "blank presentation"],
        "t-long-2": ["creá un documento en blanco", "blank document"], "v3-52": ["video"], "t-form-2": ["abrir el dialogo de reemplazar"],
        "t-menu-3": ["view"], "v3-03a": ["add a new slide"], "v3-03b": ["slide sorter"], "v3-02": ["fade"], "v3-37": ["nueva de simbolo del sistema"],
    }
    for case, labels in measured.items():
        names = [control["name"] for control in _VIEWS[case]["controls"] if control.get("name")]
        for label in labels:
            pairs += 1
            picked = _pick(label, names)
            fired += picked is not None
            right += picked == _VIEWS[case]["target"]
    views = list(_VIEWS.values())
    for number, group in enumerate(sorted(sorted(group) for group in _LABEL_ALIASES)):
        for label in group:
            for target in group:
                if fold(label) == fold(target):
                    continue
                view = views[(number + len(label)) % len(views)]
                names = [control["name"] for control in view["controls"] if control.get("name")]
                if any(fold(name) in {fold(word) for word in group} for name in names):
                    continue
                pairs += 1
                picked = _pick(label, [*names, target])
                fired += picked is not None
                right += picked == target
    assert pairs > 300
    assert right / fired >= 0.98, (right, fired)
    assert fired / pairs >= 0.4, (fired, pairs)


# ------------------------------------------------------------------ P2: el prompt


class _Model:
    def __init__(self, *steps: dict) -> None:
        self.steps = list(steps)
        self.payloads: list[dict] = []

    def _post_schema_object(self, payload: dict, label: str) -> object:
        self.payloads.append(copy.deepcopy(payload))
        return self.steps.pop(0) if self.steps else {"act": "none"}


def test_the_prompt_lists_the_similar_controls_and_the_retry_names_one_without_none() -> None:
    view = _unfolded(_view("t-menu-3"))
    model = _Model({"act": "done", "evidence": "zoom"}, {"act": "click", "i": 8})
    decision = computer_use.decide_step(
        model, objective="Zoom in twice in Notepad using the View menu", goal="ir a view", application=None,
        success_check=None, view=view, history=[], budget_left=8, application_names=[], encoder=_E5,
    )
    first_user = model.payloads[0]["messages"][1]["content"]
    assert "Parecidos al objetivo: [8] Ver" in first_user
    retry = model.payloads[1]["messages"][-1]["content"]
    assert "«Ver»" in retry and "none" not in retry
    assert decision["operation"] == "input.visible.click" and decision["arguments"]["label"] == "Ver"
    assert "Resolvé sólo el Objetivo actual" in cu_step_prompt.STEP_PROMPT


def test_without_a_similar_control_the_retry_still_offers_none() -> None:
    assert "o none si no hay ninguno" in cu_step_prompt.retry_instruction("no está en la vista", [])
    assert "none" not in cu_step_prompt.retry_instruction("no está", [{"i": 3, "name": "Ver"}])


def test_a_model_none_after_a_hint_falls_back_to_the_literal_search() -> None:
    view = _fake_view({"i": 3, "kind": "ListItem", "name": "Biblioteca de videos"}, {"i": 9, "kind": "Edit", "name": "Buscar"})
    angles = {"video library": 0.0, "Biblioteca de videos": _angle(0.85), "Buscar": _angle(0.70)}
    model = _Model({"act": "none"})
    decision = computer_use._decide_step(
        model, objective="ir a video library", goal="ir a video library", application=None, success_check=None,
        view=view, history=[], budget_left=8, application_names=[], subgoal=0, subgoal_count=1,
        translator=cu_model_calls.LabelTranslator(None, enabled=False),
        semantic=cu_meaning.SemanticMatcher(_Vectors(angles), cu_semejanza.EmbeddingCache()),
    )
    assert len(model.payloads) == 1
    assert decision["operation"] == "input.visible.click" and decision["arguments"]["label"] == "Buscar"


def test_the_similar_names_come_first_in_a_cut_listing() -> None:
    controls = [{"i": n, "kind": "Button", "name": f"Botón {n}"} for n in range(40)]
    controls.append({"i": 40, "kind": "ListItem", "name": "Biblioteca de videos"})
    shown = cu_step_prompt._ranked_controls(controls, "ir a video library", 30, (), {"controls": controls}, ["Biblioteca de videos"])
    assert any(control["name"] == "Biblioteca de videos" for control in shown)


# ------------------------------------------------------------------ P3: llegada por efecto


def _clicked(label: str, *, changed: bool) -> dict:
    return {"step": 1, "operation": "input.visible.click", "label": label, "ok": True, "changed": changed}


def test_a_free_goal_is_reached_by_the_effect_of_its_click() -> None:
    view = _view("t-long-2")
    view["newText"] = ["Documento1 - Word", "Página 1 de 1"]
    view["text"] = {"T": ["Documento1 - Word"], "B": ["Página 1 de 1"]}
    arrived = cu_evidence._arrived_by_effect("creá un documento en blanco", view, [_clicked("Documento en blanco", changed=True)], _matcher())
    assert arrived is not None and arrived["operation"] == "done" and arrived["arguments"]["evidence"] == "Documento1 - Word"
    # Contracases: a click that changed nothing, or on another control, reaches nothing.
    assert cu_evidence._arrived_by_effect("creá un documento en blanco", view, [_clicked("Documento en blanco", changed=False)], _matcher()) is None
    assert cu_evidence._arrived_by_effect("creá un documento en blanco", view, [_clicked("Abrir", changed=True)], _matcher()) is None


def test_a_tab_that_never_shows_selected_is_reached_when_new_lines_appear() -> None:
    view = _fake_view({"i": 1, "kind": "TabItem", "name": "Dibujar"}, {"i": 2, "kind": "Button", "name": "Lápiz"})
    view["newText"] = ["Lápiz", "Borrador"]
    view["text"] = {"T": ["Lápiz", "Borrador"]}
    model = _Model()
    decision = computer_use._decide_step(
        model, objective="en OneNote andá a la pestaña dibujar", goal="ir a la pestaña dibujar", application=None,
        success_check="control:dibujar:selected", view=view, history=[_clicked("Dibujar", changed=True)], budget_left=8,
        application_names=[], subgoal=0, subgoal_count=1, translator=cu_model_calls.LabelTranslator(None, enabled=False),
        semantic=_fake({"Dibujar": 0.9, "Lápiz": 0.7}, label="dibujar"),
    )
    assert decision == {"operation": "done", "arguments": {"evidence": "Lápiz"}, "reason": cu_meaning.REASON_ARRIVED_BY_EFFECT}
    assert not model.payloads


def _decide(view: dict, goal: str, history: list[dict], success_check: str | None, semantic) -> tuple[dict, "_Model"]:
    model = _Model()
    decision = computer_use._decide_step(
        model, objective=goal, goal=goal, application=None, success_check=success_check, view=view, history=history,
        budget_left=8, application_names=[], subgoal=0, subgoal_count=1,
        translator=cu_model_calls.LabelTranslator(None, enabled=False), semantic=semantic,
    )
    return decision, model


def test_a_tab_is_not_reached_by_effect_while_the_window_marks_a_sibling_selected() -> None:
    # Review of P3: «Dibujar» not selected, «Inicio» selected and only its tooltip new: no arrival, the check decides.
    view = _fake_view(
        {"i": 1, "kind": "TabItem", "name": "Dibujar"},
        {"i": 2, "kind": "TabItem", "name": "Inicio", "state": "selected"},
    )
    view["newText"] = ["Dibujar (Alt+D)"]
    view["text"] = {"T": ["Dibujar (Alt+D)"]}
    semantic = _fake({"Dibujar": 0.9, "Inicio": 0.7, "Dibujar (Alt+D)": 0.9}, label="dibujar")
    clicked = [{**_clicked("Dibujar", changed=True), "kind": "TabItem"}]
    decision, _ = _decide(view, "ir a la pestaña dibujar", clicked, "control:dibujar:selected", semantic)
    assert decision.get("reason") != cu_meaning.REASON_ARRIVED_BY_EFFECT
    # Nor with no tab selected when the only new line is the clicked name's tooltip.
    unmarked = {**view, "controls": [{"i": 1, "kind": "TabItem", "name": "Dibujar"}, {"i": 2, "kind": "TabItem", "name": "Inicio"}]}
    assert cu_evidence._arrived_by_effect("ir a la pestaña dibujar", unmarked, clicked, semantic) is None


def test_a_click_that_opened_a_menu_is_no_arrival() -> None:
    # Review of P3, measured on Steam: «BIBLIOTECA» only opened «Página principal · Colecciones · Descargas».
    lines = ["Página principal", "Colecciones", "Descargas"]
    view = {
        "window": {"title": "Steam", "process": "steamwebhelper", "focused": None},
        "controls": [{"i": 0, "kind": "Pane", "name": "Chrome Legacy Window", "state": ""}],
        "text": {"TL": ["TIENDA BIBLIOTECA COMUNIDAD", *lines], "L": ["Alan Wake"]},
        "newText": lines,
    }
    semantic = _fake({"Chrome Legacy Window": 0.70}, label="biblioteca")
    clicked = [{"step": 1, "operation": "input.visible.click", "label": "BIBLIOTECA", "ok": True, "changed": True}]
    assert cu_evidence._arrived_by_effect("ir a biblioteca", view, clicked, semantic) is None
    decision, _ = _decide(view, "ir a biblioteca", clicked, None, semantic)
    assert decision["operation"] != "done"
    assert decision == cu_rules.deterministic_step(goal="ir a biblioteca", view=view, history=clicked)
    # Contracases: the clicked control left expanded, or an open menu in the view, is no arrival either.
    expanded = _fake_view({"i": 1, "kind": "Button", "name": "Biblioteca", "state": "expanded"})
    expanded.update(newText=["Tus juegos", "Instalados ahora"], text={"C": ["Tus juegos", "Instalados ahora"]})
    one_click = [_clicked("Biblioteca", changed=True)]
    assert cu_evidence._arrived_by_effect("ir a biblioteca", expanded, one_click, semantic) is None
    menu = _fake_view({"i": 1, "kind": "Button", "name": "Biblioteca"}, {"i": 2, "kind": "Menu", "name": "Contexto"})
    menu.update(newText=["Tus juegos", "Instalados ahora"], text={"C": ["Tus juegos", "Instalados ahora"]})
    assert cu_evidence._arrived_by_effect("ir a biblioteca", menu, one_click, semantic) is None
    # The same click with neither, a page that appeared: arrival by effect.
    page = _fake_view({"i": 1, "kind": "Button", "name": "Biblioteca"})
    page.update(newText=["Tus juegos ordenados por nombre"], text={"C": ["Tus juegos ordenados por nombre"]})
    arrived = cu_evidence._arrived_by_effect("ir a biblioteca", page, one_click, semantic)
    assert arrived is not None and arrived["arguments"]["evidence"] == "Tus juegos ordenados por nombre"


# ------------------------------------------------------------------ P4: búsqueda por nombre


def test_the_search_field_is_chosen_by_name_even_as_a_document() -> None:
    # v3-29/v3-30: the Character Map's «Buscar:» is a Document; «Ir a Unicode:» is the only Edit.
    view = _fake_view(
        {"i": 1, "kind": "Edit", "name": "Ir a Unicode:"},
        {"i": 2, "kind": "Document", "name": "Buscar:"},
        {"i": 3, "kind": "Button", "name": "Seleccionar"},
    )
    step = cu_lookup._find_step("omega", view, [], navigate=False)
    assert step is not None and step["arguments"] == {"label": "Buscar:", "index": 2}
    # Contracase: a Document that does not say it searches is the person's work, never a search field.
    work = _fake_view({"i": 1, "kind": "Document", "name": "Documento"}, {"i": 2, "kind": "Edit", "name": "Buscar en documento"})
    assert cu_lookup._find_step("omega", work, [], navigate=False)["arguments"]["index"] == 2


def _work_document(name: str, value: str) -> dict:
    document = {"i": 1, "kind": "Document", "name": name, "state": "focused", "value": value}
    return {
        "window": {"title": f"{name} - Editor", "process": "editor", "focused": dict(document)},
        "controls": [document, {"i": 2, "kind": "Button", "name": "Inicio"}], "text": {},
    }


@pytest.mark.parametrize("with_encoder", [False, True])
@pytest.mark.parametrize(("name", "value"), [
    ("Búsqueda de empleo", "Querida empresa, adjunto mi CV"),
    ("Spotify – Buscar", ""),
    ("Buscar", "Querida empresa, adjunto mi CV"),
])
def test_a_document_is_never_selected_whole_or_typed_into_as_a_search(name: str, value: str, with_encoder: bool) -> None:
    # Review of P4: a Document whose name only contains a search word is the person's work (an editor, or a web
    # window's root named like its title); one whose whole name is «Buscar» but holds text is never selected whole.
    view = _work_document(name, value)
    semantic = _fake({name: 0.70, "Inicio": 0.72}, label="Configuración") if with_encoder else None
    histories = [
        [],
        [{"step": 1, "operation": "input.key.press", "key": "ctrl_k", "ok": True}],
        [{"step": 1, "operation": "input.key.press", "key": "ctrl_f", "ok": True}],
        [{"step": 1, "operation": "input.visible.click", "label": name, "index": 1, "ok": True, "changed": True}],
    ]
    for history in histories:
        for newtext in (None, [], [name]):
            seen = view if newtext is None else {**view, "newText": newtext}
            step = cu_rules.deterministic_step(goal="ir a Configuración", view=seen, history=history, semantic=semantic)
            if step is None:
                continue
            assert step["operation"] != "input.text.type", (history, step)
            assert step.get("arguments", {}).get("key") != "ctrl_a", (history, step)


def test_a_search_document_is_a_small_one_line_field() -> None:
    window = {"title": "App", "process": "app", "rect": {"x": 0, "y": 0, "w": 1000, "h": 800}}
    small = {"i": 2, "kind": "Document", "name": "Buscar:", "rect": {"x": 10, "y": 10, "w": 200, "h": 24}}
    page = {"i": 3, "kind": "Document", "name": "Contenido", "rect": {"x": 0, "y": 40, "w": 1000, "h": 760}}
    assert cu_fields._search_document({"window": window, "controls": [small, page]}, small)
    # Contracases: the same name on a page-sized document, or as the largest document of the view, is no search.
    big = {**small, "rect": {"x": 0, "y": 40, "w": 1000, "h": 760}}
    assert not cu_fields._search_document({"window": window, "controls": [big]}, big)
    tiny_page = {**page, "rect": {"x": 0, "y": 40, "w": 50, "h": 10}}
    assert not cu_fields._search_document({"window": window, "controls": [small, tiny_page]}, small)
    assert not cu_fields._search_document({"window": window, "controls": []}, {**small, "name": "Búsqueda de empleo"})


def test_a_shortcut_that_opened_another_field_is_closed_never_typed_into() -> None:
    # t-menu-3: ctrl_k opened «Insertar vínculo» and «view» was typed there.
    link = {
        "window": {"title": "Bloc de notas", "process": "notepad", "focused": {"kind": "Edit", "name": "Texto para mostrar", "value": ""}},
        "controls": [{"i": 1, "kind": "Edit", "name": "Texto para mostrar", "state": "focused"}],
        "newText": ["Insertar vínculo", "Texto para mostrar"], "text": {},
    }
    after_k = [{"step": 1, "operation": "input.key.press", "key": "ctrl_k", "ok": True}]
    assert cu_lookup._find_step("view", link, after_k) == cu_acts._key("escape")
    # A field named as a search, or brought up with a search prompt, takes the name.
    find = {**link, "window": {**link["window"], "focused": {"kind": "Edit", "name": "Buscar", "value": ""}},
            "controls": [{"i": 1, "kind": "Edit", "name": "Buscar", "state": "focused"}], "newText": ["Buscar"]}
    assert cu_lookup._find_step("view", find, after_k) == cu_acts._type("view")


# ------------------------------------------------------------------ P5: lo plegado antes de buscar


def test_a_collapsed_control_is_opened_before_searching_at_most_two() -> None:
    view = _fake_view(
        {"i": 1, "kind": "Button", "name": "Categoría", "state": "collapsed"},
        {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "collapsed"},
        {"i": 3, "kind": "Edit", "name": "Buscar en el Panel de control"},
    )
    semantic = _fake({"Categoría": 0.85, "Nueva pestaña": 0.82, "Buscar en el Panel de control": 0.75}, label="iconos grandes")
    first = cu_rules.deterministic_step(goal="ir a iconos grandes", view=view, history=[], semantic=semantic)
    assert first is not None and first["arguments"] == {"label": "Categoría", "index": 1}
    opened = [_clicked("Categoría", changed=True), {**_clicked("Otra", changed=True), "step": 2}]
    second = cu_rules.deterministic_step(goal="ir a iconos grandes", view=view, history=opened, semantic=semantic)
    # Never the split button (its click runs its act); with nothing else folded, the search.
    assert second is not None and second["arguments"]["label"] == "Buscar en el Panel de control"
    # Contracase (review of P5): a collapsed control below the similarity floor is never opened, whatever its place.
    unlike = _fake({"Categoría": 0.80, "Nueva pestaña": 0.82, "Buscar en el Panel de control": 0.75}, label="iconos grandes")
    literal = cu_rules.deterministic_step(goal="ir a iconos grandes", view=view, history=[])
    assert cu_rules.deterministic_step(goal="ir a iconos grandes", view=view, history=[], semantic=unlike) == literal


# ------------------------------------------------------------------ auditoría de las llamadas


def test_the_model_call_audit_keeps_the_prompt_and_raw_reply_of_computer_use_steps(tmp_path, monkeypatch) -> None:
    from baxy_mind import llm as llm_module

    audit = tmp_path / "model_calls.jsonl"
    monkeypatch.setenv("BAXY_MIND_MODEL_CALL_AUDIT_PATH", str(audit))
    reply = {"choices": [{"finish_reason": "stop", "message": {"content": '{"act":"click","i":8}'}}]}
    monkeypatch.setattr(llm_module, "post_chat_completion", lambda *args, **kwargs: reply)
    runtime = object.__new__(llm_module.LlmRuntime)
    runtime._request_identity = "7"
    runtime._post({"messages": [
        {"role": "system", "content": cu_step_prompt.STEP_PROMPT},
        {"role": "user", "content": "Objetivo: ir a view\nVista:\n8 · MenuItem · «Ver»"},
    ], "max_tokens": 160})
    runtime._post({"messages": [{"role": "system", "content": "Otro rol"}, {"role": "user", "content": "secreto 1234"}]})
    rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["messages"][1]["content"].endswith("«Ver»") and rows[0]["raw_reply"] == '{"act":"click","i":8}'
    assert "messages" not in rows[1] and "raw_reply" not in rows[1] and "1234" not in audit.read_text(encoding="utf-8")


# ------------------------------------------------------------------ arranque en frío del encoder (pasada v3 05:40)


class _Loading:
    """The mind's interactive encoder while its E5 worker still loads: ``try_ready(timeout)`` is ready once the clock
    passes ``ready_at``; encoding before that fails like the router (it would have waited the whole step budget)."""

    def __init__(self, ready_after: float | None) -> None:
        self.ready_at = None if ready_after is None else time.monotonic() + ready_after
        self.loaded = ready_after == 0.0
        self.waits: list[float] = []
        self.renewed: list[float] = []

    def _ready(self) -> bool:
        self.loaded = self.loaded or (self.ready_at is not None and time.monotonic() >= self.ready_at)
        return self.loaded

    def try_ready(self, timeout: float = 0.0) -> bool:
        self.waits.append(timeout)
        if self._ready() or timeout <= 0:
            return self._ready()
        left = None if self.ready_at is None else self.ready_at - time.monotonic()
        time.sleep(timeout if left is None else max(0.0, min(timeout, left)))
        # Loaded within the wait (the sleep's clock may wake a tick early).
        self.loaded = left is not None and left <= timeout
        return self.loaded

    def begin_request(self, budget: float) -> None:
        self.renewed.append(budget)

    def __call__(self, texts, *, prefix: str = "query"):
        if not self._ready():
            raise TimeoutError("router worker response timed out")
        return _E5(texts, prefix=prefix)


def _step_with(encoder, cold: "cu_meaning._ColdWait") -> tuple[dict | None, str]:
    matcher = cu_meaning.SemanticMatcher(encoder, cu_semejanza.EmbeddingCache(), cold_wait=cold)
    step = cu_rules.deterministic_step(
        goal="ir a video library", view=_view("v3-14"), history=[], semantic=matcher,
        objective="open media player, go to the video library and sort by date added",
    )
    return step, matcher.state


def test_a_step_never_waits_for_the_encoder_still_loading_and_presses_by_meaning_once_loaded() -> None:
    # v3-14 live: E5 still loading at the mission's first steps; each step spent its 0.75 s and typed «video library»
    # into the search with «Biblioteca de videos» on screen. r27 (the rule step's wait, 2 s, ended still cold in 15 of
    # 17 and pressed by meaning in none): while the worker loads the step waits for nothing and looks nothing up blind
    # (the model's, with the view); once it is loaded the step presses the place by meaning, with its whole budget.
    encoder = _Loading(ready_after=None)
    cold = cu_meaning._ColdWait(5.0)
    step, state = _step_with(encoder, cold)
    assert step is None and state == cu_meaning.ENCODER_COLD and encoder.waits == [0.0] and not encoder.renewed
    encoder.loaded = True
    step, state = _step_with(encoder, cold)
    assert step is not None and step["arguments"]["label"] == "Biblioteca de videos"
    assert step["reason"] == cu_meaning.REASON_SIMILAR and state == cu_meaning.ENCODER_READY
    assert encoder.renewed and encoder.renewed[0] == pytest.approx(cu_semejanza.ENCODER_BUDGET_SECONDS)
    assert max(encoder.waits) == 0.0 and cold._left == pytest.approx(5.0)


def test_the_cold_allowance_is_spent_once_by_the_ask_that_waits() -> None:
    # The one ask that waits (whether a click arrived by its effect, ``SemanticMatcher.scored`` with ``wait``).
    cold = cu_meaning._ColdWait(0.3)
    never = _Loading(ready_after=None)
    view = _view("v3-14")
    matcher = cu_meaning.SemanticMatcher(never, cu_semejanza.EmbeddingCache(), cold_wait=cold)
    assert matcher.scored("video library", view, wait=True) == ()
    assert matcher.state == cu_meaning.ENCODER_COLD and never.waits == [0.0, 0.3]
    # The allowance gone, the next step asks without waiting (what is left is the sleep's clock tick at most).
    again = cu_meaning.SemanticMatcher(never, cu_semejanza.EmbeddingCache(), cold_wait=cold)
    assert again.scored("video library", view, wait=True) == ()
    assert never.waits[2:] and max(never.waits[2:]) < 0.05


def test_a_ready_encoder_never_waits() -> None:
    encoder = _Loading(ready_after=0.0)
    step, state = _step_with(encoder, cu_meaning._ColdWait(5.0))
    assert state == cu_meaning.ENCODER_READY and encoder.waits == [0.0]
    assert step is not None and step["arguments"]["label"] == "Biblioteca de videos"


def test_the_step_says_its_source_and_the_encoder_state() -> None:
    common = dict(
        objective="open media player, go to the video library and sort by date added", goal="ir a video library",
        application=None, success_check=None, view=_view("v3-14"), history=[], budget_left=8, application_names=[],
    )
    semantic = computer_use.decide_step(_Model(), **common, encoder=_E5)
    assert semantic["source"] == cu_meaning.SOURCE_SEMANTIC and semantic["encoder"] == cu_meaning.ENCODER_READY
    literal = computer_use.decide_step(_Model(), **common)
    assert literal["source"] == cu_meaning.SOURCE_RULE and "encoder" not in literal
    model = _Model({"act": "none"})
    decided = computer_use.decide_step(model, **{**common, "goal": "sort by date added"}, encoder=_E5)
    assert model.payloads and decided["source"] == cu_meaning.SOURCE_MODEL
