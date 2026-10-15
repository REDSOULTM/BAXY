"""v3 r6 lectores, tanda t2-r4 c18: «pon el Word y el Edge uno al lado del otro» puso un tutorial de YouTube.

El lector de música tomó las mayúsculas de Word y Edge como un título y el de ``window.snap`` sólo entendía una app
con un lado. Dos ventanas «lado a lado» (o «uno al lado del otro», «en pantalla dividida», «side by side») son ahora
dos ``window.snap``: la primera nombrada a la izquierda, la segunda a la derecha. El lector de música no toma dos cosas
puestas una al lado de la otra; un título solo («pon Side by Side», «pon Edge of Seventeen») sigue sonando.
"""

from __future__ import annotations

import pytest

from baxy_mind import __main__ as mind
from baxy_mind import effect_intent
from baxy_mind.planner import normalize_grounded_arguments, validate_json_schema_instance

from test_c03_m55_window_pairs import RESOLVE_SCHEMA, SNAP_SCHEMA, SNAP_TOOL
from baxy_mind import plan_shape
from baxy_mind import argument_grounding
from baxy_mind import plan_dependencies

APPLICATIONS = ("Word", "Microsoft Edge", "Google Chrome", "Spotify", "Excel")
AVAILABLE = (
    "window.snap", "window.resolve", "window.focus", "window.minimize", "media.play.query", "media.play.youtube",
    "app.open", "app.close", "web.search", "mission.computer.use",
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pon el Word y el Edge uno al lado del otro", (("Word", "left"), ("Microsoft Edge", "right"))),
        ("pon Word y Edge lado a lado", (("Word", "left"), ("Microsoft Edge", "right"))),
        ("pon lado a lado el Excel y el Chrome", (("Excel", "left"), ("Google Chrome", "right"))),
        ("ponme el Excel y el Word uno al lado del otro", (("Excel", "left"), ("Word", "right"))),
        ("poné el Chrome y el Word en pantalla dividida", (("Google Chrome", "left"), ("Word", "right"))),
        ("divide la pantalla entre Word y Edge", (("Word", "left"), ("Microsoft Edge", "right"))),
        ("put Word and Edge side by side", (("Word", "left"), ("Microsoft Edge", "right"))),
        ("Can you put Excel and Chrome next to each other?", (("Excel", "left"), ("Google Chrome", "right"))),
    ],
)
def test_two_windows_beside_each_other_are_two_snaps(text: str, expected: tuple) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPLICATIONS)
    assert intent is not None and intent.operations == ("window.snap",)
    pairs = effect_intent.application_snap_pairs(text, APPLICATIONS)
    assert pairs is not None
    assert tuple((name, side) for name, side, _ in pairs) == expected
    # Each clause reads back alone as that window with its side, the way the single-window reader reads it.
    for name, side, clause in pairs:
        assert effect_intent.resolve_application_snap(clause, APPLICATIONS) == (name, side)


@pytest.mark.parametrize(
    "text",
    [
        # Contracasos: nada que ponga las dos cosas una al lado de la otra, la misma ventana dos veces, una ventana
        # que el catálogo no tiene, o una sola cosa.
        "pon Word y Edge",
        "pon el Word y el Word lado a lado",
        "pon el Word y el Slack uno al lado del otro",
        "pon el Word lado a lado",
    ],
)
def test_without_two_installed_windows_beside_each_other_no_snap_is_read(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPLICATIONS)
    assert intent is None or "window.snap" not in intent.operations
    assert intent is None or "media.play.youtube" not in intent.operations


@pytest.mark.parametrize(
    ("text", "operation"),
    [
        # Contracasos del lector de música: un título solo sigue sonando.
        ("pon Coldplay", "media.play.youtube"),
        ("pon Edge of Seventeen", "media.play.youtube"),
        ("pon música en Edge", "media.play.youtube"),
        ("pon Side by Side", "media.play.youtube"),
    ],
)
def test_a_title_alone_is_still_played(text: str, operation: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPLICATIONS)
    assert intent is not None and intent.operations == (operation,)


def test_the_music_reader_never_takes_two_things_placed_beside_each_other() -> None:
    from baxy_mind.semantic.patterns import _explicit_named_music_query

    assert _explicit_named_music_query("pon el Word y el Edge uno al lado del otro") is None
    assert _explicit_named_music_query("pon el Word y el Slack uno al lado del otro") is None
    assert _explicit_named_music_query("pon Side by Side") == "Side by Side"


def test_the_plan_is_one_resolve_and_one_snap_per_window_first_on_the_left() -> None:
    objective = "pon el Word y el Edge uno al lado del otro"
    split = mind.window_snap_plan_split(("window.snap",), (objective,), objective, APPLICATIONS)
    assert split is not None
    skeleton = plan_shape._explicit_plan_skeleton(*split)
    grounded: list[tuple[str, dict]] = []
    for index, step in enumerate(skeleton["steps"]):
        if step["operation"] == "window.resolve":
            arguments = argument_grounding._ground_explicit_arguments("window.resolve", step["purpose"], RESOLVE_SCHEMA, APPLICATIONS)
        else:
            assert step["operation"] == "window.snap" and step["dependsOn"] == [f"step_{index}"]
            window_id = f"window_{index:08d}"
            observations = [{
                "stepId": step["dependsOn"][0], "operation": "window.resolve", "verified": True,
                "status": "completed", "result": {"windows": [{"windowId": window_id, "processName": "app"}]},
            }]
            arguments = plan_dependencies._verified_dependency_identity_arguments(
                "window.snap", objective, observations, SNAP_TOOL, APPLICATIONS, purpose=step["purpose"],
            )
            assert arguments is not None and arguments["windowId"] == window_id
            source = argument_grounding.trusted_plan_grounding_source(objective, observations)
            assert normalize_grounded_arguments(arguments, SNAP_SCHEMA, source) == arguments
        assert validate_json_schema_instance(
            arguments, RESOLVE_SCHEMA if step["operation"] == "window.resolve" else SNAP_SCHEMA,
        )
        grounded.append((step["operation"], {key: value for key, value in arguments.items() if key != "windowId"}))
    assert grounded == [
        ("window.resolve", {"applicationName": "Word"}),
        ("window.snap", {"side": "left"}),
        ("window.resolve", {"applicationName": "Microsoft Edge"}),
        ("window.snap", {"side": "right"}),
    ]


def test_a_side_is_grounded_by_beside_each_other_but_not_by_a_bare_window() -> None:
    # Contracaso: sin lado dicho ni «lado a lado», un lado inventado no queda fundamentado.
    arguments = {"side": "left", "windowId": "window_00000001"}
    observations = [{
        "stepId": "step_1", "operation": "window.resolve", "verified": True, "status": "completed",
        "result": {"windows": [{"windowId": "window_00000001", "processName": "app"}]},
    }]
    source = argument_grounding.trusted_plan_grounding_source("pon el Word y el Edge lado a lado", observations)
    assert normalize_grounded_arguments(arguments, SNAP_SCHEMA, source) == arguments
    bare = argument_grounding.trusted_plan_grounding_source("pon el Word", observations)
    assert normalize_grounded_arguments(arguments, SNAP_SCHEMA, bare) is None


@pytest.mark.parametrize(
    "text",
    [
        # Revisión adversarial: un título que sólo contiene la frase, acreditado a dos artistas, sigue sonando.
        "pon side by side de ariana grande y nicki minaj",
        "pon la canción Side by Side de Ariana y Nicki",
    ],
)
def test_a_title_credited_to_two_artists_is_still_played(text: str) -> None:
    intent = effect_intent.resolve_explicit_effects(text, AVAILABLE, APPLICATIONS)
    assert intent is not None and intent.operations == ("media.play.youtube",)


def test_two_windows_beside_each_other_on_another_monitor_are_not_a_title() -> None:
    from baxy_mind.semantic.patterns import _explicit_named_music_query

    assert _explicit_named_music_query("pon el Word y el Edge uno al lado del otro en el otro monitor") is None


def test_one_window_in_split_screen_does_not_ground_a_side() -> None:
    # Revisión adversarial: una sola ventana «en pantalla dividida» no dice qué mitad; un lado inventado no se funda.
    arguments = {"side": "left", "windowId": "window_00000001"}
    observations = [{
        "stepId": "step_1", "operation": "window.resolve", "verified": True, "status": "completed",
        "result": {"windows": [{"windowId": "window_00000001", "processName": "app"}]},
    }]
    for objective in ("pon el Word en pantalla dividida", "pon Side by Side de Ariana Grande y Nicki Minaj"):
        source = argument_grounding.trusted_plan_grounding_source(objective, observations)
        assert normalize_grounded_arguments(arguments, SNAP_SCHEMA, source) is None
