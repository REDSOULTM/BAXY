"""Held-out: a call that came back «unchanged» is not handed again to the App while nothing else changed, the facts
line of a repeat after its own change, and the «ya estaba» answer check by the first call of each operation."""
import json
from pathlib import Path

import pytest

from test_answer_check import DONE, _r, _rules
from test_mind_bucle import _trace
from test_mind_final import _call, _mind, _say

AGAIN_LINE = "ya había quedado así por la misma llamada hecha antes en este turno"
BEFORE_LINE = "ya estaba así antes de esta llamada"


def _changed(observed: dict) -> str:
    return json.dumps({"status": "completed", "verification": "readback", "observed": observed})


def _same(observed: dict) -> str:
    return json.dumps({"status": "completed", "verification": "unchanged", "observed": observed})


def _turn(tmp_path: Path, request: str, calls: list, results: list[str], answer: str,
          risk: dict | None = None) -> tuple:
    """Every call but the last is handed over and answered with its result; returns the step after the last result."""
    mind, server = _mind(tmp_path, [*calls, _say(answer), _say(answer)])
    if risk:
        mind.risk = risk
    step = mind.decide(1, request)
    steps = [step]
    for index, result in enumerate(results):
        assert step["kind"] == "action", (index, step)
        step = mind.continue_turn(2 + index, result)
        steps.append(step)
    return mind, server, steps


def _tool_messages(server) -> list[str]:
    return [m.get("content") or "" for m in server.bodies[-1]["messages"] if m.get("role") == "tool"]


def _leading_json(text: str) -> dict:
    return json.JSONDecoder().raw_decode(text.lstrip())[0]


def _assert_closed(mind, server, step: dict, first_result: str) -> None:
    assert step["kind"] == "conversation", step
    denied = _leading_json(_tool_messages(server)[-1])
    assert denied["status"] == "not_run"
    assert denied["earlier"] == json.loads(first_result)
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "unchanged_closed"] == ["unchanged_closed"]


# ---- A: positives ----------------------------------------------------------------------------------------------------
def test_brightness_already_at_level_is_not_set_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    level = {"level": 65}
    first = _same({"brightness": 65})
    mind, server, steps = _turn(tmp_path, "deja el brillo en 65",
                                [_call("display_brightness", level), _call("display_brightness", level)],
                                [first], "El brillo está en 65.")
    _assert_closed(mind, server, steps[-1], first)


def test_dark_mode_repeat_with_keys_in_another_order_is_not_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first = _same({"theme": "dark", "scope": "apps"})
    mind, server, steps = _turn(tmp_path, "pon el tema oscuro en las aplicaciones",
                                [_call("settings_dark_mode", {"enabled": True, "scope": "apps"}),
                                 _call("settings_dark_mode", {"scope": "apps", "enabled": True})],
                                [first], "Las aplicaciones usan el tema oscuro.")
    _assert_closed(mind, server, steps[-1], first)


@pytest.mark.parametrize("read_verification", ["output_only", "readback"])
def test_a_read_between_does_not_count_as_a_change(tmp_path: Path, monkeypatch, read_verification: str) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first = _same({"wifi": "on"})
    status = json.dumps({"status": "completed", "verification": read_verification,
                         "observed": {"wifi": "on", "network": "Casa-5G"}})
    mind, server, steps = _turn(tmp_path, "conéctate al wifi",
                                [_call("network_wifi", {"state": "on"}), _call("network_status", {}),
                                 _call("network_wifi", {"state": "on"})],
                                [first, status], "El wifi está encendido.",
                                risk={"network_status": "read_only"})
    assert steps[1]["kind"] == "action"
    _assert_closed(mind, server, steps[-1], first)


def test_a_null_key_does_not_make_the_window_call_another(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first = _same({"window": 4412, "state": "minimized"})
    mind, server, steps = _turn(tmp_path, "minimiza la hoja de cálculo",
                                [_call("window_minimize", {"window": 4412}),
                                 _call("window_minimize", {"window": 4412, "monitor": None})],
                                [first], "La hoja de cálculo está minimizada.")
    _assert_closed(mind, server, steps[-1], first)


def test_notifications_silenced_already_are_not_silenced_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first = _same({"doNotDisturb": True})
    mind, server, steps = _turn(tmp_path, "que no me lleguen avisos",
                                [_call("notifications_quiet", {"on": True}),
                                 _call("notifications_quiet", {"on": True})],
                                [first], "Los avisos están en silencio.")
    _assert_closed(mind, server, steps[-1], first)


def test_projection_mode_change_then_unchanged_then_closed_with_the_first_result(tmp_path: Path,
                                                                                  monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mode = {"mode": "duplicate"}
    first = _changed({"before": "extend", "mode": "duplicate"})
    mind, server, steps = _turn(tmp_path, "duplica la pantalla en el proyector",
                                [_call("display_mode", mode), _call("display_mode", mode), _call("display_mode", mode)],
                                [first, _same({"mode": "duplicate"})], "La pantalla está duplicada.")
    assert steps[1]["kind"] == "action"
    _assert_closed(mind, server, steps[-1], first)


# ---- B: the facts line of a repeat after its own change ------------------------------------------------------------
def test_a_window_closed_by_the_turn_then_closed_again_is_told_as_the_turn_s_doing(tmp_path: Path,
                                                                                     monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    target = {"window": 90211}
    mind, server, steps = _turn(tmp_path, "cierra la ventana del visor de fotos",
                                [_call("window_close", target), _call("window_close", target)],
                                [_changed({"window": 90211, "closed": True}),
                                 _same({"window": 90211, "closed": True})],
                                "Cerré el visor de fotos.")
    assert steps[-1]["kind"] == "conversation"
    later = " ".join(_tool_messages(server))
    assert AGAIN_LINE in later
    assert BEFORE_LINE not in later


def test_bluetooth_turned_on_then_repeated_is_told_as_the_turn_s_doing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    state = {"enabled": True}
    mind, server, steps = _turn(tmp_path, "activa el bluetooth",
                                [_call("bluetooth_power", state), _call("bluetooth_power", state),
                                 _call("bluetooth_status", {})],
                                [_changed({"before": False, "enabled": True}), _same({"enabled": True}),
                                 json.dumps({"status": "completed", "verification": "output_only",
                                             "observed": {"enabled": True}})],
                                "El bluetooth está encendido.", risk={"bluetooth_status": "read_only"})
    assert steps[-1]["kind"] == "conversation"
    later = " ".join(_tool_messages(server))
    assert AGAIN_LINE in later
    assert BEFORE_LINE not in later


# ---- A: negatives (the same call is handed over again) -------------------------------------------------------------
def test_a_key_press_that_changed_twice_is_handed_over_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    key = {"key": "PageDown"}
    mind, _, steps = _turn(tmp_path, "baja dos páginas",
                           [_call("input_key", key), _call("input_key", key)],
                           [_changed({"scrolled": True, "page": 2})], "Bajé dos páginas.")
    assert steps[-1]["kind"] == "action" and steps[-1]["arguments"] == key
    assert mind.continue_turn(3, _changed({"scrolled": True, "page": 3}))["kind"] == "conversation"
    assert not [r for r in _trace(mind) if r.get("kind") == "unchanged_closed"]


def test_a_relative_brightness_step_that_changed_is_handed_over_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    step_up = {"delta": 15}
    mind, _, steps = _turn(tmp_path, "sube un poco más el brillo",
                           [_call("display_brightness_step", step_up), _call("display_brightness_step", step_up)],
                           [_changed({"before": 40, "brightness": 55})], "Subí el brillo.")
    assert steps[-1]["kind"] == "action" and steps[-1]["arguments"] == step_up
    assert not [r for r in _trace(mind) if r.get("kind") == "unchanged_closed"]


def test_the_same_tool_on_another_window_is_handed_over(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _, steps = _turn(tmp_path, "maximiza las dos ventanas del editor",
                           [_call("window_maximize", {"window": 3001}), _call("window_maximize", {"window": 3002})],
                           [_same({"window": 3001, "state": "maximized"})], "Las dos están maximizadas.")
    assert steps[-1]["kind"] == "action" and steps[-1]["arguments"] == {"window": 3002}
    assert not [r for r in _trace(mind) if r.get("kind") == "unchanged_closed"]


def test_the_same_setting_at_another_level_is_handed_over(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _, steps = _turn(tmp_path, "pon la luz nocturna al 70",
                           [_call("display_night_light", {"strength": 40}),
                            _call("display_night_light", {"strength": 70})],
                           [_same({"strength": 40})], "La luz nocturna está al 70.")
    assert steps[-1]["kind"] == "action" and steps[-1]["arguments"] == {"strength": 70}


def test_the_same_call_after_another_call_changed_something_is_handed_over(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    airplane = {"enabled": False}
    mind, _, steps = _turn(tmp_path, "quita el modo avión y enciende el wifi",
                           [_call("network_airplane_mode", airplane), _call("network_wifi", {"state": "on"}),
                            _call("network_airplane_mode", airplane)],
                           [_same({"airplane": False}), _changed({"before": "off", "wifi": "on"})],
                           "Encendí el wifi.")
    assert steps[-1]["kind"] == "action" and steps[-1]["arguments"] == airplane
    assert not [r for r in _trace(mind) if r.get("kind") == "unchanged_closed"]


# ---- C: the «ya estaba» answer and the first call of each operation ------------------------------------------------
def _so(op: str, observed: dict, arguments: dict) -> dict:
    return _r(op, {"status": "completed", "verification": "unchanged", "observed": observed}, arguments)


def _set(op: str, observed: dict, arguments: dict) -> dict:
    return _r(op, {**DONE, "observed": observed}, arguments)


def test_brightness_said_already_after_the_turn_set_it() -> None:
    args = {"level": 65}
    receipts = [_set("display.brightness", {"before": 20, "brightness": 65}, args),
                _so("display.brightness", {"brightness": 65}, args)]
    assert "already" in _rules("El brillo ya estaba en 65 por ciento.", receipts)


def test_dark_mode_said_needless_after_the_turn_set_it() -> None:
    args = {"enabled": True}
    receipts = [_set("settings.dark_mode", {"before": "light", "theme": "dark"}, args),
                _so("settings.dark_mode", {"theme": "dark"}, args), _so("settings.dark_mode", {"theme": "dark"}, args)]
    assert "already" in _rules("No hizo falta cambiar nada: el tema oscuro ya estaba puesto.", receipts)


def test_wifi_said_already_on_with_a_single_change() -> None:
    receipts = [_set("network.wifi", {"before": "off", "wifi": "on"}, {"state": "on"})]
    assert "already" in _rules("Tu wifi ya estaba encendido.", receipts)


def test_windows_said_already_maximized_after_the_turn_did_it() -> None:
    args = {"window": 5120}
    receipts = [_set("window.maximize", {"before": "normal", "state": "maximized"}, args),
                _so("window.maximize", {"state": "maximized"}, args)]
    assert "already" in _rules("Esas ventanas ya estaban maximizadas.", receipts)


def test_bluetooth_said_already_had_after_the_turn_turned_it_on() -> None:
    args = {"enabled": True}
    receipts = [_set("bluetooth.power", {"before": False, "enabled": True}, args),
                _so("bluetooth.power", {"enabled": True}, args)]
    assert "already" in _rules("El equipo ya tenía el bluetooth activo, no toqué nada.", receipts)


def test_two_operations_both_changed_first_and_said_already() -> None:
    receipts = [_set("display.mode", {"before": "extend", "mode": "duplicate"}, {"mode": "duplicate"}),
                _set("notifications.quiet", {"before": False, "doNotDisturb": True}, {"on": True}),
                _so("notifications.quiet", {"doNotDisturb": True}, {"on": True})]
    assert "already" in _rules("Dupliqué la pantalla; los avisos ya estaban en silencio.", receipts)


def test_already_is_true_when_another_operation_was_so_at_its_first_call() -> None:
    receipts = [_set("network.wifi", {"before": "off", "wifi": "on"}, {"state": "on"}),
                _so("bluetooth.power", {"enabled": True}, {"enabled": True})]
    assert "already" not in _rules("Encendí el wifi; el bluetooth ya estaba activo.", receipts)


def test_already_is_true_when_the_first_call_of_the_operation_was_so() -> None:
    args = {"strength": 40}
    receipts = [_so("display.night_light", {"strength": 40}, args),
                _set("display.night_light", {"before": 40, "strength": 40}, args)]
    assert "already" not in _rules("La luz nocturna ya estaba al 40.", receipts)


def test_saying_it_was_not_so_is_not_an_already_claim() -> None:
    receipts = [_set("settings.dark_mode", {"before": "light", "theme": "dark"}, {"enabled": True})]
    assert "already" not in _rules("El tema oscuro no estaba activado, así que lo activé.", receipts)


def test_an_answer_without_already_is_not_flagged() -> None:
    receipts = [_set("display.brightness", {"before": 30, "brightness": 80}, {"level": 80}),
                _so("display.brightness", {"brightness": 80}, {"level": 80})]
    assert "already" not in _rules("Subí el brillo al 80 por ciento.", receipts)
