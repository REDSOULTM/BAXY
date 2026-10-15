"""Goal v3, punto 6 / criterio 7: etiquetas fuera de la tabla de alias que llegan a su control por significado.

Cada etiqueta (tests/data/cu_etiquetas_fuera_tabla.json) es el nombre inglés de un control de una vista REAL del
journal (tests/data/cu_semejanza_vistas.json, con los nombres en español que mostró la ventana), fuera de
``_LABEL_ALIASES`` (``label_alternatives`` no da el destino), y el camino del producto
(``cu_rules.deterministic_step`` con ``SemanticMatcher``: ``_semantic_step`` → ``semantic_pick`` con
``CLICK_SIMILARITY``/``CLICK_MARGIN``) la pulsa con las filas reales de E5-small congeladas
(scripts/cu_semejanza_congelar.py), sin cargar el modelo. Contracasos: el destino quitado de la vista no deja ningún
clic por parecido, y un interruptor o un control que quita nunca se pulsa por parecido aunque E5 lo ponga primero.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from baxy_mind import cu_view
from baxy_mind import cu_meaning
from baxy_mind import cu_rules
from baxy_mind.semantic import cu_semejanza
from baxy_mind.semantic.missions import fold, label_alternatives

_DATA = Path(__file__).parent / "data"
_VIEWS = {view["case"]: view for view in json.loads((_DATA / "cu_semejanza_vistas.json").read_text(encoding="utf-8"))}
_LABELS = json.loads((_DATA / "cu_etiquetas_fuera_tabla.json").read_text(encoding="utf-8"))
_PAIRS = [(row["case"], row["label"], row["target"]) for row in _LABELS["pairs"]]
_NEVER = [(row["case"], row["label"], row["control"], row["why"]) for row in _LABELS["never"]]
_BY_MEANING = {cu_meaning.REASON_SIMILAR, cu_meaning.REASON_UNFOLD, cu_meaning.REASON_ARRIVED_BY_EFFECT}


class _FrozenE5:
    """The real E5-small rows (float16) frozen by scripts/cu_semejanza_congelar.py; a text without a row fails."""

    def __init__(self) -> None:
        keys = json.loads((_DATA / "cu_semejanza_e5.json").read_text(encoding="utf-8"))
        rows = np.load(_DATA / "cu_semejanza_e5.npy").astype(np.float32)
        self._rows = {key: row / np.linalg.norm(row) for key, row in zip(keys, rows)}

    def __call__(self, texts, *, prefix: str = "query"):
        return np.stack([self._rows[f"{prefix}: {text}"] for text in texts])


_E5 = _FrozenE5()


def _matcher() -> cu_meaning.SemanticMatcher:
    return cu_meaning.SemanticMatcher(_E5, cu_semejanza.EmbeddingCache())


def _view(case: str, without: str | None = None) -> dict:
    view = copy.deepcopy(_VIEWS[case])
    return {"window": view["window"], "controls": [c for c in view["controls"] if c.get("name") != without], "text": {}}


def _step(goal: str, view: dict, semantic: cu_meaning.SemanticMatcher | None = None) -> dict | None:
    return cu_rules.deterministic_step(goal=goal, view=view, history=[], semantic=semantic)


def test_there_are_at_least_twenty_distinct_labels_outside_the_table() -> None:
    labels = {fold(label) for _, label, _ in _PAIRS}
    assert len(labels) >= 20
    for case, label, target in _PAIRS:
        assert fold(target) not in {fold(name) for name in label_alternatives(label)}, label
        assert fold(label) not in {fold(name) for name in label_alternatives(target)}, label
        # A real name of that real view, exactly once.
        assert [c.get("name") for c in _VIEWS[case]["controls"]].count(target) == 1, (case, target)


@pytest.mark.parametrize(("case", "label", "target"), _PAIRS, ids=[label for _, label, _ in _PAIRS])
def test_a_label_outside_the_table_presses_its_control_by_meaning(case: str, label: str, target: str) -> None:
    for goal in (f"ir a {label}", label):
        literal = _step(goal, _view(case))
        assert literal is None or literal["arguments"].get("label") != target, (goal, literal)
        step = _step(goal, _view(case), _matcher())
        assert step is not None and step["operation"] == "input.visible.click", (goal, step)
        assert step["reason"] == cu_meaning.REASON_SIMILAR, (goal, step)
        # Review r10a finding 5: the alias says it was picked by resemblance.
        assert step["arguments"]["label"] == target and step["alias"] == {
            "from": label, "to": target, "by": cu_meaning.SOURCE_SEMANTIC,
        }, (goal, step)
        index = next(c["i"] for c in _VIEWS[case]["controls"] if c.get("name") == target)
        assert step["arguments"]["index"] == index


@pytest.mark.parametrize(("case", "label", "target"), _PAIRS, ids=[label for _, label, _ in _PAIRS])
def test_without_its_control_in_the_view_no_click_by_meaning(case: str, label: str, target: str) -> None:
    absent = _view(case, without=target)
    for goal in (f"ir a {label}", label):
        step = _step(goal, absent, _matcher())
        assert step is None or step.get("reason") not in _BY_MEANING, (goal, step)
        # What the product does without the encoder (the literal search), or the model with the similar names shown.
        assert step is None or step == _step(goal, absent), (goal, step)


@pytest.mark.parametrize(("case", "label", "control", "why"), _NEVER, ids=[f"{c}-{label}" for c, label, _, _ in _NEVER])
def test_a_switch_or_a_removal_is_never_pressed_by_meaning(case: str, label: str, control: str, why: str) -> None:
    view = _view(case)
    assert not label_alternatives(label), label
    found = next(c for c in view["controls"] if c.get("name") == control)
    if why == "switch":
        assert cu_view._is_switch(found), found
    # E5 puts the dangerous control first in the view: only the safety filters keep it from a click.
    scored = _matcher().scored(label, view)
    assert scored and scored[0][0] == control, scored[:3]
    for goal in (f"ir a {label}", label):
        step = _step(goal, view, _matcher())
        assert step is None or step["arguments"].get("label") != control, (goal, step)
        assert step is None or step.get("reason") not in _BY_MEANING, (goal, step)


def test_switches_and_a_removal_past_threshold_and_margin_are_held_by_the_filters_alone() -> None:
    # The strongest contracases: without the safety filters ``semantic_pick`` would press them (measured: «advanced
    # view», «pixels», «percentage», «hide obs windows from screen capture» and «remove» → «Eliminar»).
    strong = set()
    for case, label, control, why in _NEVER:
        scored = _matcher().scored(label, _view(case))
        if cu_semejanza.semantic_pick(scored, lambda name: True) == control:
            strong.add((label, why))
    assert len(strong) >= 5 and {why for _, why in strong} == {"switch", "removal"}, strong
