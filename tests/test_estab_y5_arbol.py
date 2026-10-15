"""Estabilización y5 (banco h1, «en el Explorador de archivos andá a Descargas y después a Imágenes»).

«Imágenes» of Explorer's navigation tree was seen and pressed; it stayed chosen and the folder stayed «Downloads». The
mind said so (``click_without_effect``) and the final said «no vi el control para seguir». The stop the App writes for
that code (``computer_use_click_without_effect``) is said with its own cause, never as a control not seen.
"""

from baxy_mind import operation_floor
from baxy_mind.cu_projection import project_seen

# The real h1 receipt (evidencia_h1/v2-y5/compose_audit.jsonl), with the stop the App now writes.
H1_OBSERVED = {
    "goal": "ir a descargas; luego ir a imagenes",
    "application": "Explorador de archivos",
    "reached": False,
    "steps": [
        {"step": 1, "operation": "input.visible.click", "subgoal": 0, "label": "Downloads", "ok": True,
         "method": "invoke", "surfaceChanged": False, "placeMoved": True, "selected": True, "name": "Downloads",
         "kind": "TreeItem", "changed": True, "broughtNew": True},
        {"step": 2, "operation": "input.visible.click", "subgoal": 1, "label": "Imágenes", "ok": True,
         "method": "message", "surfaceChanged": False, "placeMoved": False, "selected": True, "name": "Imágenes",
         "kind": "TreeItem", "changed": True, "broughtNew": False},
    ],
    "window": {"title": "Downloads - Explorador de archivos", "process": "explorer", "foreground": True},
    "joined": False,
    "stoppedBy": "computer_use_click_without_effect",
    "subgoals": [
        {"goal": "ir a descargas", "application": "Explorador de archivos", "reached": True},
        {"goal": "ir a imagenes", "application": "Explorador de archivos", "reached": False},
    ],
}


def test_y5_a_pressed_control_that_left_the_window_is_said_as_such():
    causes = operation_floor.floor_data()["computerUse"]["causes"]
    for language in ("es", "en"):
        seen = project_seen(H1_OBSERVED, language)
        assert seen["stoppedBecause"] == causes["computer_use_click_without_effect"][language]
        assert seen["stoppedBecause"] != causes["computer_use_no_step_visible"][language]


def test_y5_contracase_a_screen_without_a_step_keeps_its_cause():
    causes = operation_floor.floor_data()["computerUse"]["causes"]
    seen = project_seen({**H1_OBSERVED, "stoppedBy": "computer_use_no_step_visible"}, "es")
    assert seen["stoppedBecause"] == causes["computer_use_no_step_visible"]["es"]
