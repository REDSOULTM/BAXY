"""M55 (v3b window set, F-w06-t1 «pon el word a la izquierda y el chrome a la derecha», F-w06-t2 «no, al revés»,
F-w08-t1 «…put Chrome on the left half and Slack on the right…»): the decider lists each kind of effect once, so
two windows arrived as one ``window.snap``; the plan resolved both in a single ``window.resolve`` and the Core
answered «invalid selector». Each window is now its own resolve and snap, read from its own clause; the side of
each snap is the person's; a mixed selector is never sent."""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent
from baxy_mind.planner import normalize_grounded_arguments, validate_json_schema_instance

APPLICATIONS = ("Word", "Google Chrome", "Slack", "Excel", "Spotify")
RESOLVE_SCHEMA = {
    "type": "object",
    "properties": {
        "applicationName": {"type": "string", "maxLength": 256},
        "byTitle": {"type": "boolean"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        "offset": {"type": "integer", "minimum": 0},
        "process": {"type": "string", "maxLength": 260},
    },
    "required": [],
    "additionalProperties": False,
}
SNAP_SCHEMA = {
    "type": "object",
    "properties": {
        "side": {"type": "string", "enum": ["left", "right"]},
        "windowId": {"type": "string", "maxLength": 36},
    },
    "required": ["side", "windowId"],
    "additionalProperties": False,
}
SNAP_TOOL = {"function": {"canonical_name": "window.snap", "parameters": SNAP_SCHEMA}}

# The decider's restatements in the v3b run (turn-audit requests 898, 904 and 933), verbatim.
RESTATED_T1 = "Coloca la ventana de Word en la mitad izquierda y la de Chrome en la mitad derecha."
RESTATED_T2 = "Coloca la ventana de Word en la mitad derecha y la de Chrome en la mitad izquierda."
RESTATED_W08 = "Snap the Chrome window to the left half and the Slack window to the right half of the screen."


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pon el word a la izquierda y el chrome a la derecha", (("Word", "left"), ("Google Chrome", "right"))),
        (RESTATED_T1, (("Word", "left"), ("Google Chrome", "right"))),
        (RESTATED_T2, (("Word", "right"), ("Google Chrome", "left"))),
        (RESTATED_W08, (("Google Chrome", "left"), ("Slack", "right"))),
        (
            "Can you put Chrome on the left half and Slack on the right so I can see the board and the chat at the "
            "same time?",
            (("Google Chrome", "left"), ("Slack", "right")),
        ),
        (
            "pon el word a la izquierda, el chrome a la derecha y spotify a la izquierda",
            (("Word", "left"), ("Google Chrome", "right"), ("Spotify", "left")),
        ),
        ("Coloca la ventana de Chrome en la mitad izquierda.", (("Google Chrome", "left"),)),
    ],
)
def test_each_window_of_a_placing_request_is_read_with_its_own_side(text: str, expected: tuple) -> None:
    pairs = effect_intent.application_snap_pairs(text, APPLICATIONS)
    assert pairs is not None
    assert tuple((name, side) for name, side, _ in pairs) == expected
    # Each clause reads back as that one window alone.
    for name, side, clause in pairs:
        assert effect_intent.application_snap_pairs(clause, APPLICATIONS)[0][:2] == (name, side)


@pytest.mark.parametrize(
    "text",
    [
        "pon chrome a la izquierda y chrome a la derecha",
        "pon esta ventana a la izquierda y chrome a la derecha",
        "pon el word a la izquierda y abre spotify",
        "pon el notepad a la izquierda y el chrome a la derecha",
        "abre chrome",
    ],
)
def test_a_window_outside_the_catalog_or_a_second_non_placing_clause_abstains(text: str) -> None:
    assert effect_intent.application_snap_pairs(text, APPLICATIONS) is None


def _run_plan(objective: str) -> list[tuple[str, dict]]:
    """The explicit plan of a decided ``window.snap`` and what each step grounds, the Core observations faked."""

    split = mind.window_snap_plan_split(("window.snap",), (objective,), objective, APPLICATIONS)
    assert split is not None
    skeleton = mind._explicit_plan_skeleton(*split)
    grounded: list[tuple[str, dict]] = []
    for index, step in enumerate(skeleton["steps"]):
        if step["operation"] == "window.resolve":
            assert step["argumentsMode"] == "literal" and step["dependsOn"] == []
            arguments = mind._ground_explicit_arguments("window.resolve", step["purpose"], RESOLVE_SCHEMA, APPLICATIONS)
            assert mind._normalize_grounded_operation_arguments("window.resolve", arguments, objective) == arguments
        else:
            assert step["operation"] == "window.snap" and step["argumentsMode"] == "after_dependencies"
            assert step["dependsOn"] == [f"step_{index}"]
            window_id = f"window_{index:08d}"
            observations = [{
                "stepId": step["dependsOn"][0], "operation": "window.resolve", "verified": True,
                "status": "completed", "result": {"windows": [{"windowId": window_id, "processName": "app"}]},
            }]
            arguments = mind._verified_dependency_identity_arguments(
                "window.snap", objective, observations, SNAP_TOOL, APPLICATIONS, purpose=step["purpose"],
            )
            assert arguments is not None and arguments["windowId"] == window_id
            source = mind.trusted_plan_grounding_source(objective, observations)
            assert normalize_grounded_arguments(arguments, SNAP_SCHEMA, source) == arguments
        assert validate_json_schema_instance(arguments, RESOLVE_SCHEMA if step["operation"] == "window.resolve" else SNAP_SCHEMA)
        grounded.append((step["operation"], {key: value for key, value in arguments.items() if key != "windowId"}))
    return grounded


def test_word_left_and_chrome_right_is_two_resolves_and_two_snaps() -> None:
    assert _run_plan(RESTATED_T1) == [
        ("window.resolve", {"applicationName": "Word"}),
        ("window.snap", {"side": "left"}),
        ("window.resolve", {"applicationName": "Google Chrome"}),
        ("window.snap", {"side": "right"}),
    ]


def test_the_other_way_round_inverts_the_sides_of_the_same_windows() -> None:
    # «no, al revés»: the decider restated the previous request with the sides swapped (request 904).
    assert _run_plan(RESTATED_T2) == [
        ("window.resolve", {"applicationName": "Word"}),
        ("window.snap", {"side": "right"}),
        ("window.resolve", {"applicationName": "Google Chrome"}),
        ("window.snap", {"side": "left"}),
    ]


def test_the_standup_layout_in_english() -> None:
    assert _run_plan(RESTATED_W08) == [
        ("window.resolve", {"applicationName": "Google Chrome"}),
        ("window.snap", {"side": "left"}),
        ("window.resolve", {"applicationName": "Slack"}),
        ("window.snap", {"side": "right"}),
    ]


def test_one_window_keeps_the_one_step_plan_and_reads_the_restated_head() -> None:
    objective = "Coloca la ventana de Chrome en la mitad izquierda."
    assert mind.window_snap_plan_split(("window.snap",), (objective,), objective, APPLICATIONS) is None
    assert mind._ground_explicit_arguments("window.resolve", objective, RESOLVE_SCHEMA, APPLICATIONS) == {
        "applicationName": "Google Chrome"
    }
    observations = [{"stepId": "step_1", "operation": "window.resolve", "verified": True, "status": "completed",
                     "result": {"windows": [{"windowId": "window_00000001"}]}}]
    assert mind._verified_dependency_identity_arguments(
        "window.snap", objective, observations, SNAP_TOOL, APPLICATIONS,
    ) == {"side": "left", "windowId": "window_00000001"}


def test_a_step_purpose_only_picks_one_of_the_request_s_own_pairs() -> None:
    assert mind.window_snap_side_for_step(RESTATED_T1, "coloca la de chrome en la mitad derecha", APPLICATIONS) == {
        "side": "right"
    }
    # A purpose that swaps the side, names a window the request did not, or names both, picks nothing.
    assert mind.window_snap_side_for_step(RESTATED_T1, "coloca la de chrome en la mitad izquierda", APPLICATIONS) is None
    assert mind.window_snap_side_for_step(RESTATED_T1, "pon slack a la derecha", APPLICATIONS) is None
    assert mind.window_snap_side_for_step(RESTATED_T1, RESTATED_T1, APPLICATIONS) is None


def test_the_split_keeps_the_other_effects_of_the_turn_in_place() -> None:
    operations = ("window.snap", "capture.screenshot")
    evidence = (RESTATED_T1, "haz una captura")
    assert mind.window_snap_plan_split(operations, evidence, RESTATED_T1, APPLICATIONS) == (
        ("window.snap", "window.snap", "capture.screenshot"),
        (
            "coloca la ventana de word en la mitad izquierda",
            "coloca la de chrome en la mitad derecha",
            "haz una captura",
        ),
    )


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"applicationName": "Word"}, {"applicationName": "Word"}),
        ({"process": "chrome"}, {"process": "chrome"}),
        ({"process": "Word", "byTitle": True}, {"process": "Word", "byTitle": True}),
        ({"applicationName": "Word", "byTitle": False, "offset": 0}, {"applicationName": "Word"}),
        # Two windows read into one step, no selector at all, or a name with a title flag: the Core's
        # «invalid selector» (v3b F-w06-t1, F-w08-t1) is never requested.
        ({"applicationName": "Word", "process": "Chrome"}, None),
        ({}, None),
        ({"applicationName": "Word", "byTitle": True}, None),
        ({"applicationName": "Word", "offset": 20}, None),
    ],
)
def test_window_resolve_carries_exactly_one_selector(arguments: dict, expected: dict | None) -> None:
    assert mind._normalize_grounded_operation_arguments("window.resolve", arguments, RESTATED_T1) == expected
