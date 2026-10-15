"""The match by meaning (semantic/cu_semejanza.py): the step's encoder with its budget and the mind's cold
allowance, the control a name by meaning may press, and the collapsed control opened first.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Iterable

from .semantic.cu_buscar import frame_button
from .semantic.missions import fold
from .semantic.cu_semejanza import (
    ENCODER_BUDGET_SECONDS, HINT_SIMILARITY, EmbeddingCache, acts_on_the_window, comparable, semantic_pick,
    similar_hints, similar_names, undoes_or_repeats,
)
from .cu_view import _drawn, _in_title_bar, _is_switch, _scroll_part, _state_unknown_switch, names_another_place
from .cu_fields import _message_window
from .cu_acts import _click
from .cu_languages import _TRANSLATED_ITEM_KINDS, _translation_clickable


# The encoder's rows by name for the life of the mind: a window's names repeat from one step to the next.
_SEMANTIC_CACHE = EmbeddingCache()
# The kinds a click without the model may land on by meaning alone: places and offers of the window's interface.
_SEMANTIC_CLICK_KINDS = frozenset({"ListItem", "TabItem", "TreeItem", "MenuItem", "Hyperlink", "Button"})
# A free goal is matched by meaning only while it is short enough to be a control's name («creá un documento en
# blanco»); a whole sentence only ranks (measured: its margin falls to 0.008–0.011).
_FREE_GOAL_WORDS = 6
REASON_SIMILAR = "el objetivo nombra este control con otras palabras: es el único que lo dice con margen"
REASON_ARRIVED_BY_EFFECT = "el clic en el control que nombra el objetivo cambió la ventana"
# The encoder's cold start (pasada v3 05:40, v3-14, reproduced on the real mind process): the E5 worker is spawned 3 s
# after the mind and needs ~12 s more to load (8 s of them importing sentence_transformers), longer while the GPU model
# warms up. A mission that starts in that window spent the step's 0.75 s at each step waiting for a worker that was not
# there and went literal: «video library» typed in the search with «Biblioteca de videos» on screen.
# lat-e5 (r13a, 104 missions: 47 of them spent 5–15 s of step 1 or 2 here, 11 the whole 15 s; the model itself never
# took more than 2.1 s): a step never waits for the encoder to decide. While it loads the step decides by what needs
# no encoder (a name on screen, a rule, the label's translation by the model, the model with the view: r27, the rule
# step's wait ended still cold in 15 of 17 and pressed by meaning in none). One ask waits, the one only the match
# answers: whether a click arrived by its effect (``_arrived_by_effect``), out of an
# allowance of at most this much in the whole life of the mind (a cold start; never a warm mind's step); the encoding
# keeps its own budget (``ENCODER_BUDGET_SECONDS``). Owner's rule: more than 3 s without a sign is unacceptable.
ENCODER_COLD_WAIT_SECONDS = 2.0


class _ColdWait:
    """The mind's one allowance for waiting on a loading encoder (``ENCODER_COLD_WAIT_SECONDS``), spent once."""

    def __init__(self, seconds: float) -> None:
        self._left = float(seconds)
        self._lock = threading.Lock()

    def ready(self, probe: Callable[[float], Any]) -> bool:
        """``probe(timeout)`` is the encoder's ``try_ready``: ready now, or after waiting what is left of the
        allowance. A worker that failed for good answers at once and spends nothing."""

        try:
            if probe(0.0):
                return True
        except Exception:  # noqa: BLE001 - an encoder that cannot say it is ready is not ready
            return False
        with self._lock:
            if self._left <= 0:
                return False
            started = time.monotonic()
            try:
                return bool(probe(self._left))
            except Exception:  # noqa: BLE001
                return False
            finally:
                self._left -= time.monotonic() - started


_COLD_WAIT = _ColdWait(ENCODER_COLD_WAIT_SECONDS)


def _ready_now(probe: Callable[[float], Any]) -> bool:
    """The encoder's ``try_ready`` without waiting: an encoder that cannot say it is ready is not ready."""

    try:
        return bool(probe(0.0))
    except Exception:  # noqa: BLE001
        return False
# What the step's encoder was (``SemanticMatcher.state``), for the shell's trace: «ready» it answered, «cold» it was
# still loading (or is gone for good) past the cold allowance, «failed» it took the budget or failed answering.
ENCODER_READY, ENCODER_COLD, ENCODER_FAILED = "ready", "cold", "failed"
# Where a step came from (``decide_step``'s «source»): the model, a rule of the engine, or a name matched by meaning.
SOURCE_MODEL, SOURCE_RULE, SOURCE_SEMANTIC = "model", "rule", "semantic"


class SemanticMatcher:
    """The similarity of a goal's label to the names a view shows (``semantic/cu_semejanza.py``), memoized for one
    step; ``encode`` is the mind's interactive encoder (``encode(texts, prefix=…)``) and its rows are cached by name
    across steps. Any failure of the encoder is «no similar name»: the literal behaviour stays.

    The step's encoder budget (``ENCODER_BUDGET_SECONDS``) counts only the time spent in the encoder: the label's
    translation (a model call that may come first in the same step) never spends it (review of P1: on a goal in
    another language the translation used up the budget and the click by meaning depended on the clock). Before each
    encoding the encoder's own request deadline, when it has one (``begin_request``), is renewed to what is left.

    An encoder that says whether it is loaded (``try_ready``) and is still loading answers «no similar name» at once
    (``state`` cold): only a call with ``wait`` (a step that truly depends on the match) waits for it, out of the
    mind's cold allowance (``ENCODER_COLD_WAIT_SECONDS``) and never out of the step's budget. ``spent_ms`` is the time
    this step spent in the encoder (waiting and encoding), for the shell's trace apart from the model's time."""

    def __init__(
        self, encode: Callable[..., Any] | None, cache: EmbeddingCache | None = None,
        budget_seconds: float = ENCODER_BUDGET_SECONDS, cold_wait: _ColdWait | None = None,
    ) -> None:
        self._encode = encode
        self._cache = cache if cache is not None else _SEMANTIC_CACHE
        # Per key: the scores and whether they were a cold answer given without waiting (asked again by a call that
        # waits).
        self._memo: dict[tuple[object, ...], tuple[tuple[tuple[str, float], ...], bool]] = {}
        self._left = float(budget_seconds)
        self._cold_wait = cold_wait if cold_wait is not None else _COLD_WAIT
        # «» until the encoder is asked; then ENCODER_READY, ENCODER_COLD or ENCODER_FAILED (the last answer).
        self.state = ""
        self.spent_ms = 0.0

    def scored(
        self, label: str, view: dict, other_labels: Iterable[str] = (), *, wait: bool = False,
    ) -> tuple[tuple[str, float], ...]:
        controls = view.get("controls") if isinstance(view, dict) else None
        names = tuple(
            str(control.get("name")).strip() for control in (controls if isinstance(controls, list) else [])
            if isinstance(control, dict) and str(control.get("name") or "").strip() and not _scroll_part(control, view)
        )
        others = tuple(str(name) for name in other_labels if str(name).strip())
        key = (fold(label).strip(), others, names)
        memo = self._memo.get(key)
        if memo is None or (wait and memo[1]):
            started = time.monotonic()
            try:
                scored = self._similar(label, names, others, wait=wait)
                self._memo[key] = (scored, not wait and self.state == ENCODER_COLD)
            finally:
                self.spent_ms += (time.monotonic() - started) * 1000.0
        return self._memo[key][0]

    def _similar(
        self, label: str, names: tuple[str, ...], others: tuple[str, ...], *, wait: bool = False,
    ) -> tuple[tuple[str, float], ...]:
        if self._encode is None:
            return ()
        if not (str(label or "").strip() or others) or not any(comparable(name) for name in names):
            # Nothing to compare (every name a long text): the encoder is not asked and says nothing of its state.
            return ()
        if self._left <= 0:
            # The budget spent: the encoder failed unless it already answered in this step (it spent it answering).
            if self.state != ENCODER_READY:
                self.state = ENCODER_FAILED
            return ()
        probe = getattr(self._encode, "try_ready", None)
        if callable(probe) and not (self._cold_wait.ready(probe) if wait else _ready_now(probe)):
            self.state = ENCODER_COLD
            return ()
        renew = getattr(self._encode, "begin_request", None)
        try:
            if callable(renew):
                renew(self._left)
        except Exception:  # noqa: BLE001 - the encoder is advisory: a budget it cannot open is «no similar name»
            self.state = ENCODER_FAILED
            return ()
        started = time.monotonic()
        scored: tuple[tuple[str, float], ...] = ()
        try:
            scored = similar_names(
                label, names, self._encode, other_labels=others, cache=self._cache, budget_seconds=self._left,
            )
            return scored
        finally:
            self._left -= time.monotonic() - started
            self.state = ENCODER_READY if scored or not names else ENCODER_FAILED


def _semantic_control(view: dict, name: str, goal: str, wanted: str | None, kind: str | None, *, clicking: bool) -> dict | None:
    """The one control so named that a match by meaning may name (``clicking``: press without the model). Never a
    switch unless the goal switches something on or off, never one that removes, changes the account or opens another
    tab or window the goal does not ask for (``_translation_clickable``), never a frame button, an undo or a redo, a
    DataItem, nor a list or tree item of a window that writes to people; a click only on a place or an offer of the
    interface (``_SEMANTIC_CLICK_KINDS``) and never in a window that writes to people."""

    controls = view.get("controls") if isinstance(view, dict) else None
    carriers = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and str(control.get("name") or "").strip() == name and not _scroll_part(control, view)
    ]
    if len(carriers) != 1:
        return None
    control = carriers[0]
    control_kind = str(control.get("kind") or "")
    if _is_switch(control) != (wanted in ("on", "off")) or _state_unknown_switch(control):
        return None
    if kind is not None and control_kind != kind:
        return None
    if control_kind == "DataItem" or frame_button(fold(name)) or acts_on_the_window(name) or undoes_or_repeats(name):
        return None
    if not _drawn(view, control):
        # Listed but not drawn (the window's system menu): never a place a goal names.
        return None
    if not _translation_clickable(goal, name) or "disabled" in str(control.get("state") or "").split():
        return None
    if _message_window(view) and (clicking or control_kind in _TRANSLATED_ITEM_KINDS):
        return None
    if clicking and not _is_switch(control) and control_kind not in _SEMANTIC_CLICK_KINDS:
        return None
    return control


def _semantic_step(
    goal: str, target: str, view: dict, history: list[dict], wanted: str | None, kind: str | None,
    translated: Iterable[str], semantic: SemanticMatcher | None, tried: Iterable[str] = (),
) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    """(click, hints) by meaning when no name of the goal is on screen: the click only when the most similar name
    passes the calibrated similarity and margin (``semantic_pick``) and the safety filters (``_semantic_control``),
    with ``alias`` {from, to} for the shell's check; the hints are the names shown to the model as similar."""

    if semantic is None or not str(target or "").strip():
        return None, ()
    scored = semantic.scored(target, view, translated)
    if not scored:
        return None, ()
    pressed = {
        fold(step.get("label")) for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    } | {fold(label) for label in tried}

    def clickable(name: str) -> bool:
        # Estabilización G2: a name that holds the place and adds words of its own is another place, by meaning too.
        return (
            fold(name) not in pressed and not (wanted is None and kind is None and names_another_place(target, name, view))
            and _semantic_control(view, name, goal, wanted, kind, clicking=True) is not None
        )

    # A name already pressed in this sub-goal is no longer a lead: the step goes on as if it were not similar.
    hints = similar_hints(
        scored,
        lambda name: fold(name) not in pressed and _semantic_control(view, name, goal, wanted, kind, clicking=False) is not None,
    )
    picked = semantic_pick(scored, clickable)
    if picked is None:
        return None, hints
    control = _semantic_control(view, picked, goal, wanted, kind, clicking=True)
    if control is None:
        return None, hints
    step = _click(control, REASON_SIMILAR)
    # Review r10a finding 5: «by» says the name was picked by resemblance; the shell never counts it as a translation
    # confirmed nor as a strong arrival on its own.
    return {**step, "alias": {"from": target, "to": picked, "by": SOURCE_SEMANTIC}}, hints


# P5: at most this many collapsed controls are opened before a search.
_UNFOLDED_CONTROLS = 2
_UNFOLDED_KINDS = frozenset({"ComboBox", "Button", "MenuItem", "TreeItem"})


REASON_UNFOLD = "la opción puede estar dentro de un control plegado: lo abro antes de buscar"
# The steps a name matched by meaning chose (P1 click, P3 arrival by effect, P5 the collapsed control opened first).
_SEMANTIC_REASONS = frozenset({REASON_SIMILAR, REASON_ARRIVED_BY_EFFECT, REASON_UNFOLD})


def _collapsed_to_open(
    goal: str, target: str, view: dict, history: list[dict], translated: Iterable[str], semantic: SemanticMatcher,
    similar: Iterable[str] = (),
) -> dict[str, object] | None:
    """P5: the collapsed control to open next: a list, a menu button or a tree node the view marks collapsed whose
    name is similar to the goal by meaning (``HINT_SIMILARITY``, never by its place in the view: with the encoder
    down or out of time nothing is opened and the step is the literal one), not opened yet in this sub-goal, at most
    two per sub-goal. Never a split button (its click runs its own act, it does not unfold), a control the safety
    filters refuse (``_semantic_control``: account acts, removals, the window's frame), one not drawn on screen (the
    window's system menu) nor one in the title bar (the account, the quick access toolbar). When the model is shown
    similar names (``similar``), only the most similar of them is opened: any other is the model's choice."""

    controls = view.get("controls") if isinstance(view, dict) else None
    collapsed = [
        control for control in (controls if isinstance(controls, list) else [])
        if isinstance(control, dict) and "collapsed" in str(control.get("state") or "").split()
        and str(control.get("kind") or "") in _UNFOLDED_KINDS and str(control.get("name") or "").strip()
    ]
    if not collapsed:
        return None
    pressed = [
        fold(step.get("label")) for step in history
        if isinstance(step, dict) and step.get("operation") == "input.visible.click"
    ]
    unfolding = {fold(control.get("name")) for control in (controls or []) if isinstance(control, dict)
                 and {"collapsed", "expanded"} & set(str(control.get("state") or "").split())}
    if sum(1 for label in pressed if label in unfolding) >= _UNFOLDED_CONTROLS:
        return None
    scores = dict(semantic.scored(target, view, translated))
    if not scores:
        return None
    candidates = [
        control for control in collapsed
        if scores.get(str(control.get("name") or "").strip(), 0.0) >= HINT_SIMILARITY
        and fold(control.get("name")) not in pressed
        and _drawn(view, control) and not _in_title_bar(view, control)
        and _semantic_control(view, str(control.get("name") or "").strip(), goal, None, None, clicking=False) is not None
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda control: scores.get(str(control.get("name") or "").strip(), 0.0))
    shown = [name for name in similar if str(name).strip()]
    if shown and fold(shown[0]).strip() != fold(best.get("name")).strip():
        return None
    return _click(best, REASON_UNFOLD)


def _free_goal_label(goal: str) -> str | None:
    """A free goal short enough to be a control's name, as the label matched by meaning; None for a sentence."""

    said = str(goal or "").strip()
    return said if said and len(said.split()) <= _FREE_GOAL_WORDS else None
