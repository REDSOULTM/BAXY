"""R125: a hypothesis stays a hypothesis behind a frame that denies an order.

The counterfactual and past/hypothetical detectors are anchored to the front of
the request. A denial frame sits in front of the body, and neither
``_strip_request_envelope`` nor ``explicit_non_action_frame`` removes it, so the
anchor never reached the hypothesis: 21 of 21 framed surfaces were missed across
three languages and the seven frames R27 used, against 3 of 3 detected bare.

The repair scopes ``_strip_explicit_no_action_frame`` -- which R25 already paid
for -- to these two detectors alone. The second half of this module is the part
that matters most: it pins the *limit* of that scope, because stripping the
frame before every anchored pattern would take away the ``leading_negation`` net
that closes a denial-framed body which merely quotes an order.
"""

from __future__ import annotations

import pytest

from baxy_mind.__main__ import _explicit_stable_no_effect_turn_decision


# The four denial frames R27 generated per language. They are reworded from the
# ones R25 and R26 used, which is precisely why a hand-listed frame class kept
# missing them.
DENIAL_FRAMES = (
    "No assignment for the computer, just answer me: ",
    "Do not put any mandate through on the machine, only tell me: ",
    "This would never be a provision for the PC, let us talk: ",
    "No direction ever goes to the laptop, answer me and that is all: ",
    "Ninguna encomienda para el ordenador, contéstame nomás: ",
    "No tramites mandato alguno en la máquina, sólo dime: ",
    "Jamás sería una disposición para el equipo, charlemos: ",
    "Nunca va una indicación al laptop, answer me y ya: ",
)

COUNTERFACTUAL_BODIES = (
    "What would happen if another computer lost its Wi-Fi",
    "What pasaría si another computer lost su Wi-Fi",
    "Qué ocurriría si otra computadora perdiera su Wi-Fi",
)


@pytest.mark.parametrize("body", COUNTERFACTUAL_BODIES)
def test_a_bare_counterfactual_is_answered_as_knowledge(body: str) -> None:
    decision = _explicit_stable_no_effect_turn_decision(body)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "knowledge"
    assert decision["effect_operations"] == []


@pytest.mark.parametrize("frame", DENIAL_FRAMES)
@pytest.mark.parametrize("body", COUNTERFACTUAL_BODIES)
def test_a_framed_counterfactual_is_answered_not_refused(frame: str, body: str) -> None:
    """The frame must not turn a question about a hypothesis into a refusal.

    ``knowledge`` is what makes the model answer. ``unsupported`` -- which is
    what ``leading_negation`` alone produces -- makes it say it cannot, and that
    is the visible defect: the person asked something answerable.
    """

    decision = _explicit_stable_no_effect_turn_decision(frame + body)

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["conversation_kind"] == "knowledge"
    assert decision["effect_operations"] == []


@pytest.mark.parametrize("frame", DENIAL_FRAMES)
def test_a_denial_frame_around_a_quoted_order_still_grants_no_effect(
    frame: str,
) -> None:
    """The limit of the repair, and the reason it is not applied in bulk.

    A body that merely quotes an order keeps reading the unstripped text
    everywhere else in the classifier, so the denial still closes the turn as
    conversation and no operation is granted. If a later change ever strips the
    frame before every anchored pattern, this is the test that fails.
    """

    decision = _explicit_stable_no_effect_turn_decision(frame + "abre Chrome ahora")

    assert decision is not None
    assert decision["mode"] == "conversation"
    assert decision["operation"] is None
    assert decision["effect_operations"] == []
    assert decision["effect_count"] == "zero"
