"""Encargo H2: lo que el equipo no tiene se dice como tal y el estado de un dispositivo nunca se inventa.

Tandas redpc fin1/fin2 sobre 0650deac3 (``cu-v3/tandas_fin{1,2}_redpc``):
- t2-c03 t4, t3-c04, t4-c04 t1/t2: un monitor que no expone su brillo (estado_antes «Brightness []», WMI «not
  supported») se dijo «Intenté poner el brillo…, pero no pude confirmar si se hizo», también tras la corrección.
- t1-c11, t2-c15, t4-c11: «No pude encender el bluetooth porque la radio no se detectó», redactado por el modelo.
- t3-c09 t1: «Conectado» (de Ethernet) dicho como «los auriculares están conectados» (el agrupado de la vista se prueba
  en tests/Baxy.Providers.Windows.Tests/ScreenStateLinesTests.cs; aquí, desde el encargo H3, la respuesta del suelo).
Un dispositivo ausente es un dato (``computerUse.limits.devices``): el suelo lo dice con su causa, como una misión
(tests/Baxy.Integration.Tests/EstabH2DispositivosTests.cs fija las mismas frases en la App).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from baxy_mind import cu_finals, deterministic_finals, operation_floor
from baxy_mind.semantic import limits

_ROOT = Path(__file__).resolve().parent.parent
_BRIGHTNESS = "Este equipo no deja cambiar el brillo desde Windows (el monitor no lo expone)."


def _situation(operation: str, error: str, attempted: dict, *, uncertain: bool = False, **extra: object) -> dict:
    """The situation as the writer got it in the tandas (compose_audit), with the code the provider answers now."""

    reason = {
        "kind": "operation", "operation": operation, "polarity": "failure", "verified": False, "succeeded": False,
        "error": error, "attempted": attempted,
    }
    if uncertain:
        reason.update(cause="external_effect_ambiguous", effectUncertain=True)
    return {"kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
            "reason": json.dumps(reason), **extra}


@pytest.mark.parametrize(
    ("operation", "error", "attempted", "said", "language", "final"),
    [
        # t1-c11 t1, t4-c11 t1 (es) and t2-c15 t1 (en): bluetooth.radio.set → bluetooth_radio_not_found.
        ("bluetooth.radio.set", "bluetooth_radio_not_found", {"state": True},
         "enciende el bluetooth que quiero conectar los cascos", "es", "Este equipo no tiene Bluetooth."),
        ("bluetooth.radio.set", "bluetooth_radio_not_found", {"state": True},
         "turn bluetooth on, gonna connect my headphones", "en", "This computer has no Bluetooth."),
        # t2-c03 t4, t3-c04 t1, t4-c04 t1: the monitor does not expose its brightness (provider: brightness_not_supported).
        ("system.settings.set", "brightness_not_supported", {"setting": "brightness", "value": 30},
         "ok y ahora baja el brillo a like 30", "es", _BRIGHTNESS),
        ("system.settings.set", "brightness_not_supported", {"setting": "brightness", "value": 40},
         "pon el brillo al 40", "es", _BRIGHTNESS),
        ("system.settings.adjust", "brightness_not_supported", {"setting": "brightness", "direction": "down"},
         "lower the brightness a bit", "en",
         "This computer doesn't let Windows change the brightness (the monitor doesn't expose it)."),
        # The Wi-Fi adapter absent (live n5's device), also from a scan that finds no wireless interface.
        ("wifi.radio.set", "wifi_radio_not_found", {"state": True}, "prende el wifi", "es",
         "Este equipo no tiene adaptador Wi-Fi."),
        ("wifi.scan", "wifi_radio_not_found", {}, "qué redes wifi hay", "es", "Este equipo no tiene adaptador Wi-Fi."),
    ],
)
def test_an_absent_device_is_said_by_the_floor_as_the_computers_limit(
    operation: str, error: str, attempted: dict, said: str, language: str, final: str,
) -> None:
    situation = _situation(operation, error, attempted)
    assert operation_floor.tells_first(situation)
    assert deterministic_finals._floor_first_final(situation, {}, said, language) == final


def test_the_correction_says_the_limit_again_never_the_unconfirmed_attempt() -> None:
    # t4-c04 t2 «joder que te he dicho brillo no volumen»: the read finds the same absence (nothing is tried) and the
    # floor says it once more as the same result (data «again»), not «no pude confirmar».
    situation = _situation(
        "system.settings.set", "brightness_not_supported", {"setting": "brightness", "value": 40},
        correctedFinal={"previousReply": _BRIGHTNESS},
    )
    final = deterministic_finals._floor_first_final(situation, {}, "joder que te he dicho brillo no volumen", "es")
    assert final == _BRIGHTNESS
    assert operation_floor.again(final, english=False) == "El resultado es el mismo. " + _BRIGHTNESS


def test_a_brightness_left_unconfirmed_keeps_its_own_floor() -> None:
    # Contracase (the notebook's monitor exposes its brightness): a set whose read after differs is no limit.
    situation = _situation(
        "system.settings.set", "brightness_postread_failed", {"setting": "brightness", "value": 40}, uncertain=True,
    )
    final = deterministic_finals._floor_first_final(situation, {}, "pon el brillo al 40", "es")
    assert final == "Intenté poner el brillo: 40 %, pero no pude confirmar si se hizo."
    assert "brightness_postread_failed" not in operation_floor.failure_sentences()


def test_every_absence_the_device_provider_answers_is_a_device_of_the_data() -> None:
    # One source: the provider's codes for hardware the computer lacks are the data's «absent» codes.
    source = (_ROOT / "src" / "Baxy.Providers.Windows" / "External" / "WindowsDeviceControlAdapter.cs").read_text(
        encoding="utf-8")
    answered = set(re.findall(r"[\"'](\w+_radio_not_found)[\"']", source))
    answered |= set(re.findall(r'BrightnessNotSupported = "(\w+)"', source))
    absent = {code for device in limits.limits_data()["devices"].values() for code in device["absent"]}
    assert answered == {"wifi_radio_not_found", "bluetooth_radio_not_found", "brightness_not_supported"}
    assert answered <= absent
    assert "wifi_interface_unavailable" not in source


@pytest.mark.parametrize(
    ("goal", "device"),
    [("ir a brillo", "brightness"), ("go to brightness settings", "brightness"),
     # Contracases: the display's page exists whatever the monitor exposes.
     ("ir a pantalla", None), ("ir a sistema", None)],
)
def test_the_brightness_place_needs_its_monitor(goal: str, device: str | None) -> None:
    assert limits.required_device(goal) == device


def test_a_mission_stopped_at_the_brightness_says_the_limit() -> None:
    observed = {"goal": "ir a brillo", "application": "Configuración", "reached": False, "steps": [],
                "stoppedBy": "computer_use_limit_device", "absentDevice": "brightness"}
    assert cu_finals.limit_final(observed, english=False) == (
        "No puedo ir a «brillo»: este equipo no deja cambiar el brillo desde Windows (el monitor no lo expone).")


def test_a_state_is_said_as_the_one_of_what_its_line_names() -> None:
    # t3-c09 t1: «fijate si los auriculares están conectados» over a screen whose «Conectado» was Ethernet's. Encargo
    # H3: the floor answers it from the device rows (the writer's instruction that H2 added is gone, tanda n5 showed it
    # was not enough); tests/test_estab_h3_dispositivo.py holds the rest.
    seen = {"goal": "ir a bluetooth", "reached": True, "question": "fijate si los auriculares están conectados",
            "screen": {"lines": ["Ethernet: Conectado", "REDPC", "B760M H"]}}
    assert cu_finals.question_answer(seen, english=False) == (
        "No vi los auriculares en la pantalla; lo que veo es «Ethernet» (Conectado).")
    # Contracase: a mission with no question is not answered.
    assert cu_finals.question_answer({**seen, "question": None}, english=False) == ""
