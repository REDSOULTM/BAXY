"""Regression corpus for the deterministic state-query families.

The recognizer in ``baxy_mind.effect_intent`` decides these turns without the
model, so their contractual decision no longer depends on when the semantic
index becomes ready.  That property is only worth having if the recognizer
also refuses every neighbouring request that merely *looks* like a reading, so
this module drives the product's own labelled pools:

* ``POSITIVE_POOLS`` may never resolve to an operation other than its label;
* ``ABSTAIN_POOLS`` may never gain a state-family operation at all;
* the frozen 30-turn workload keeps the exact decisions this campaign promoted.
"""

from __future__ import annotations

import pytest

from baxy_mind.effect_intent import resolve_explicit_effects
from baxy_mind.tools.router_bank_sources import ABSTAIN_POOLS, POSITIVE_POOLS
from scripts.measure_mind_budget import TURN_TEXTS


AVAILABLE = frozenset(
    {
        "app.installed",
        "app.open",
        "audio.mute",
        "audio.status",
        "audio.volume",
        "audio.volume.adjust",
        "bluetooth.device.list",
        "browser.control",
        "browser.navigate",
        "browser.navigate.named",
        "browser.page.read",
        "browser.tabs.list",
        "capture.screenshot",
        "clipboard.copy",
        "clipboard.read.text",
        "email.latest.read",
        "filesystem.file.open.latest",
        "filesystem.folder.open",
        "game.catalog.list",
        "game.installed.named",
        "input.keyboard.open",
        "input.select.all",
        "input.text.type",
        "media.control",
        "media.play.exact",
        "media.play.query",
        "media.status",
        "network.ping",
        "network.status",
        "note.create",
        "note.list",
        "note.read",
        "note.search",
        "ocr.read",
        "peripheral.list",
        "reminder.create",
        "reminder.list",
        "routine.list",
        "system.process.list",
        "system.status",
        "system.time",
        "task.create",
        "task.list",
        "task.search",
        "web.search",
        "wifi.profile.list",
        "wifi.status",
        "window.active",
        "window.maximize",
        "window.minimize",
        "window.restore",
    }
)

STATE_OPERATIONS = frozenset(
    {
        "system.status",
        "audio.status",
        "audio.mute",
        "audio.volume",
        "audio.volume.adjust",
    }
)

# Pools whose label names an operation the deterministic recognizer can own.
# The remaining pools (memory.*, note.create paraphrases, ...) are covered by
# their own suites; here they only have to avoid producing a *wrong* effect.
_LABELLED_POOLS = {
    label: label.split(":")[0]
    for label in POSITIVE_POOLS
    if label.split(":")[0] in AVAILABLE
}

# Texts the recognizer deliberately leaves to the model, with the reason.
_SANCTIONED_ABSTENTIONS = {
    # «sistema» calificado por una coletilla no queda al final de la frase, y
    # relajar ese ancla reabriría «sistema solar» o «equipo médico».
    "cómo anda el sistema, todo bien?",
    # Una disyunción explícita nunca concede autoridad determinista.
    "cómo está el audio, muteado o no?",
}


def _operations(text: str) -> tuple[str, ...]:
    result = resolve_explicit_effects(text, AVAILABLE)
    return () if result is None else result.operations


@pytest.mark.parametrize(
    ("label", "text"),
    [(label, text) for label, texts in ABSTAIN_POOLS.items() for text in texts],
)
def test_distractor_pools_never_gain_a_state_effect(label: str, text: str) -> None:
    assert not STATE_OPERATIONS.intersection(_operations(text)), label


@pytest.mark.parametrize(
    ("label", "text"),
    [
        (label, text)
        for label, texts in POSITIVE_POOLS.items()
        for text in texts
    ],
)
def test_positive_pools_never_resolve_to_another_operation(
    label: str,
    text: str,
) -> None:
    expected = _LABELLED_POOLS.get(label)
    operations = _operations(text)
    if expected is None:
        assert not STATE_OPERATIONS.intersection(operations), label
        return
    assert operations in ((), (expected,)), label


@pytest.mark.parametrize(
    ("label", "text"),
    [
        (label, text)
        for label, texts in POSITIVE_POOLS.items()
        if label.split(":")[0] in {"system.status", "audio.status", "audio.mute"}
        for text in texts
        if text not in _SANCTIONED_ABSTENTIONS
    ],
)
def test_state_queries_are_decided_without_the_model(label: str, text: str) -> None:
    assert _operations(text) == (label.split(":")[0],), text


@pytest.mark.parametrize("text", sorted(_SANCTIONED_ABSTENTIONS))
def test_ambiguous_state_queries_have_an_exact_abstention_contract(text: str) -> None:
    assert _operations(text) == (), text


# Decisiones deterministas de la carga Mind de 30 turnos. La memoria privada
# pertenece a App y se valida en su propia compuerta; no aparece en esta carga.
# Un turno ausente aquí se resuelve con el modelo o una aclaración explícita a
# propósito (nivel relativo, número en letras, conversación o diagnóstico).
FROZEN_WORKLOAD_DECISIONS = {
    0: ("system.status",),
    1: ("system.status",),
    2: ("audio.volume",),
    3: ("audio.mute",),
    4: ("audio.status",),
    5: ("system.status",),
    6: ("system.status",),
    7: ("note.create",),
    8: ("network.ping",),
    9: ("system.time",),
    10: ("wifi.profile.list",),
    11: ("system.status",),
    12: ("system.status",),
    13: ("system.status",),
    14: ("system.status",),
    21: ("note.create",),
    22: ("system.status",),
    23: ("system.status",),
    24: ("audio.status",),
    25: ("wifi.status",),
    28: ("audio.volume",),
    29: ("system.status",),
}


@pytest.mark.parametrize("index", sorted(FROZEN_WORKLOAD_DECISIONS))
def test_frozen_workload_state_turns_are_deterministic(index: int) -> None:
    text = TURN_TEXTS[index]
    assert _operations(text) == FROZEN_WORKLOAD_DECISIONS[index], text


@pytest.mark.parametrize(
    "index",
    [
        index
        for index in range(len(TURN_TEXTS))
        if index not in FROZEN_WORKLOAD_DECISIONS
    ],
)
def test_frozen_workload_remaining_turns_stay_with_the_model(index: int) -> None:
    assert _operations(TURN_TEXTS[index]) == (), TURN_TEXTS[index]
