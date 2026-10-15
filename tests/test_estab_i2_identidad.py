"""Encargo I2 (prueba de identidad en vivo en redpc, 2026-10-12, build 0650deac3).

«Activá el modo accesible» with the mode in normal switched it (the Core's receipt: ``changed: true``, decided with the
state read before the write) and the writer said «El modo accesible ya está activado.»: a switch made, told as one that
already held. A switch of a setting with an on/off state (BAXY's accessible mode and bypass, do not disturb, the night
light, airplane mode) is now the floor's either way: «Listo, activé…» when it switched, «…ya estaba así» only when the
receipt found it there. The brightness, a level, keeps the writer when it changed (its direction is the writer's).
"""

from __future__ import annotations

import pytest

from baxy_mind import llm, operation_floor

SET = "system.settings.set"


def _set(setting: str, value: int, changed: bool | None) -> dict:
    observed: dict = {"version": 1, "setting": setting, "value": value,
                      "authority": "baxy_profile_setting_postread"}
    if changed is not None:
        observed["changed"] = changed
    return {"kind": "operation", "operation": SET, "polarity": "success", "verified": True, "succeeded": True,
            "observed": observed}


class _Drafts(llm.LlmRuntime):
    def __init__(self, drafts: list[str]) -> None:  # noqa: D107
        self._gguf = r"D:\BAXYRuntime\assets\models\granite-4.2-3b-Q4_K_M.gguf"
        self._drafts = list(drafts)
        self.sent: list[str] = []

    def _post(self, payload, **_):  # noqa: ANN001, ANN201
        self.sent.append(payload["messages"][-1]["content"])
        content = self._drafts.pop(0) if len(self._drafts) > 1 else self._drafts[0]
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}


def test_the_live_turn_switched_from_normal_is_said_as_switched_never_drafted() -> None:
    drafts = _Drafts(["El modo accesible ya está activado."])
    said = drafts.compose_user_message("Activá el modo accesible", "status", {"situation": _set(
        "accessible_mode", 1, True)})
    assert said == "Listo, activé el modo accesible."
    assert drafts.sent == []


@pytest.mark.parametrize(
    ("setting", "value", "changed", "spanish", "english"),
    [
        ("accessible_mode", 1, True, "Listo, activé el modo accesible.", "I turned the accessible mode on."),
        ("accessible_mode", 0, True, "Listo, desactivé el modo accesible.", "I turned the accessible mode off."),
        ("accessible_mode", 1, False, "El modo accesible ya estaba así.", "The accessible mode was already that way."),
        ("confirmation_bypass", 0, True, "Apagué el modo bypass.", "I switched bypass mode off."),
        ("confirmation_bypass", 0, False, "El modo bypass ya estaba apagado.", "Bypass mode was already off."),
        ("do_not_disturb", 1, True, "Listo, activé el modo no molestar.", "I turned do not disturb on."),
        ("night_light", 0, True, "Listo, desactivé la luz nocturna.", "I turned the night light off."),
        ("airplane_mode", 1, True, "Listo, activé el modo avión.", "I turned airplane mode on."),
        ("airplane_mode", 0, False, "El modo avión ya estaba así.", "Airplane mode was already that way."),
        # A receipt with no «changed» (a Windows switch read only after the write) is still the switch asked.
        ("do_not_disturb", 0, None, "Listo, desactivé el modo no molestar.", "I turned do not disturb off."),
    ],
)
def test_every_on_off_setting_is_told_whole_from_its_receipt(
    setting: str, value: int, changed: bool | None, spanish: str, english: str,
) -> None:
    situation = _set(setting, value, changed)
    assert operation_floor.tells_first(situation)
    assert operation_floor.floor_final(situation, False) == spanish
    assert operation_floor.floor_final(situation, True) == english


def test_contracase_a_brightness_set_stays_the_writer_s_and_a_failure_names_the_way_asked() -> None:
    brightness = _set("brightness", 40, True)
    brightness["observed"]["baselineValues"] = [30]
    assert not operation_floor.tells_first(brightness)
    drafts = _Drafts(["Subí el brillo al 40 %."])
    assert drafts.compose_user_message("pon el brillo al 40", "status", {"situation": brightness}) == (
        "Subí el brillo al 40 %."
    )
    failed = {"kind": "operation", "operation": SET, "polarity": "failure", "status": "failed",
              "error": "baxy_setting_write_failed", "effectUncertain": True,
              "attempted": {"setting": "accessible_mode", "value": 1}}
    said = operation_floor.floor_final(failed, False)
    assert "activar el modo accesible" in said and "listo" not in said.lower()


# ------------------------------------------------------------------ llama-server huérfano (tanda fin2 t4 en redpc)
# The mind runs under the runtime's venv launcher, whose job lets children break away silently; llama-server then
# belonged to no job, and a mind killed without its close (the App's job or the launcher's closing) left it running.

_PARENT = """
import subprocess, sys, time
from baxy_mind.process_lifecycle import end_with_this_process
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
tied = end_with_this_process(child) if sys.argv[1] == "tie" else False
print(child.pid, tied, flush=True)
time.sleep(120)
"""


def _ends_within(pid: int, seconds: float) -> bool:
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x00100000 | 0x0001, False, pid)  # SYNCHRONIZE | PROCESS_TERMINATE
    if not handle:
        return True
    try:
        if kernel32.WaitForSingleObject(ctypes.c_void_p(handle), int(seconds * 1000)) == 0:
            return True
        kernel32.TerminateProcess(ctypes.c_void_p(handle), 1)  # only the exact child this test started
        return False
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


@pytest.mark.parametrize(("mode", "ends"), [("tie", True), ("free", False)])
def test_a_child_tied_to_the_mind_ends_when_the_mind_is_killed(mode: str, ends: bool) -> None:
    import os
    import pathlib
    import subprocess
    import sys

    env = {**os.environ, "PYTHONPATH": str(pathlib.Path(__file__).resolve().parents[1] / "src")}
    parent = subprocess.Popen([sys.executable, "-c", _PARENT, mode], stdout=subprocess.PIPE, text=True, env=env)
    try:
        pid, tied = parent.stdout.readline().split()
    finally:
        parent.kill()  # the mind killed without its close
        parent.wait(10)
    assert tied == ("True" if mode == "tie" else "False")
    # Contracase («free»): untied, the child outlives its parent (the orphan measured); the test ends it by its PID.
    assert _ends_within(int(pid), 5.0) is ends
