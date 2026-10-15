"""Tanda t4-r6 (apps y ventanas): what a turn already did is told when a later step fails, a request for a new
document never writes into one the person already has, and a dialog of the application that blocks a mission is said
in the person's words."""

from __future__ import annotations

from baxy_mind import payload_fact_checks

SIDE_BY_SIDE = "ponme el navegador y el word uno al lado del otro"


def _placement_failed_payload(placed_operation: str = "window.snap", read_only: bool = False) -> dict:
    return {
        "outcome": "failed",
        "completedStepsInOrder": [
            {"operation": "window.resolve", "resultAtThisStep": {"readOnly": True, "seen": {"count": 1}}},
            {
                "operation": placed_operation,
                "resultAtThisStep": {
                    "readOnly": read_only,
                    "seen": {"side": "left", "window": {"processName": "opera", "title": "Vlog - YouTube - Opera"}},
                },
            },
        ],
        "reason": {"outcome": "failed", "cause": "a detail needed for one of the actions was missing"},
    }


def test_a_window_placed_before_the_failure_is_told() -> None:
    # t4-r6 c19, the published final word for word.
    draft = (
        "No puedo colocar el navegador y Word uno al lado del otro porque la acción de colocarlos requería un detalle "
        "que no se proporcionó."
    )
    assert payload_fact_checks._payload_fact_defect(draft, _placement_failed_payload(), SIDE_BY_SIDE) == "missing_prior_placement"


def test_a_final_that_tells_the_placed_window_passes() -> None:
    draft = "Puse Opera a la izquierda, pero no pude acomodar Word."
    assert payload_fact_checks._payload_fact_defect(draft, _placement_failed_payload(), SIDE_BY_SIDE) == ""
    assert payload_fact_checks._payload_fact_defect(
        "I snapped Opera to the left, but Word could not be placed.", _placement_failed_payload(), SIDE_BY_SIDE,
    ) == ""
    # Where the window ended up tells it in both languages alike.
    assert payload_fact_checks._payload_fact_defect(
        "Opera está a la izquierda, pero no pude acomodar Word.", _placement_failed_payload(), SIDE_BY_SIDE,
    ) == ""
    assert payload_fact_checks._payload_fact_defect(
        "Opera is on the left, but Word could not be placed.", _placement_failed_payload(), SIDE_BY_SIDE,
    ) == ""


def test_no_placement_done_asks_for_nothing_more() -> None:
    """Contracaso: only reads before the failure (or a read-only placement result) leave nothing done to tell."""

    draft = "No pude acomodar las ventanas."
    assert payload_fact_checks._payload_fact_defect(draft, _placement_failed_payload(read_only=True), SIDE_BY_SIDE) == ""
    payload = _placement_failed_payload()
    payload["outcome"] = "completed"
    assert payload_fact_checks._payload_fact_defect("Listo.", payload, SIDE_BY_SIDE) != "missing_prior_placement"
