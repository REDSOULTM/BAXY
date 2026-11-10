"""MIR1 (VIVO3 fila A4, 2026-11-10): a look at the screen of an earlier turn is told, in the clock's calls of the session,
as the screen of its moment whose capture is gone (the App deletes captures when a turn ends, PRV1 PRIV-02 b)."""
import datetime as _dt
import json

import pytest

CAPTURE = "capture_" + "ab" * 16


def _call(call_id: str, name: str, arguments: dict) -> dict:
    function = {"name": name}
    function["arguments"] = json.dumps(arguments)
    return {"choices": [{"message": {"content": "", "tool_calls": [{"id": call_id, "function": function}]}}]}


def _looked(tmp_path, monkeypatch, setting: str = ""):
    from test_mind_final import _mind, _say
    monkeypatch.setenv("BAXY_AYUDAS", setting)
    mind, server = _mind(tmp_path, [_call("k1", "capture_screenshot", {}),
                                    _call("k2", "vision_describe", {"captureId": CAPTURE}),
                                    _say("Dice «Paso 1 de 3»."), _say("Sigue diciendo lo mismo.")])
    mind.risk = {"capture_screenshot": "read_only", "vision_describe": "read_only"}
    mind.decide(1, "mira mi pantalla y dime qué dice")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "output_only", "observed": {
        "captureId": CAPTURE, "createdAtUtc": "2026-11-10T09:29:12Z", "width": 1920, "height": 1080}}))
    mind.continue_turn(3, json.dumps({"status": "completed", "verification": "output_only", "observed": {
        "captureId": CAPTURE, "description": "Una ventana emergente dice «Paso 1 de 3»."}}))
    return mind, server


def _clock_of(server) -> str:
    return next(m["content"] for m in reversed(server.bodies[-1]["messages"])
                if str(m["content"]).startswith("[Reloj:"))


def test_a_look_of_an_earlier_turn_is_told_as_the_screen_of_its_moment_whose_capture_is_gone(tmp_path, monkeypatch):
    mind, server = _looked(tmp_path, monkeypatch)
    mind.decide(4, "¿y qué más dice ahí?")
    clock = _clock_of(server)
    moment = _dt.datetime(2026, 11, 10, 9, 29, 12, tzinfo=_dt.timezone.utc).astimezone().strftime("%H:%M")
    gone = f"; su captura ya se borró: lo que mostró es la pantalla de las {moment}"
    assert f"capture_screenshot → lectura: sólo miró, sin abrir, cerrar ni cambiar nada{gone}" in clock
    assert f"vision_describe → lectura: sólo miró, sin abrir, cerrar ni cambiar nada{gone}" in clock
    # And as a note of its own just before the person's words (CAPTURE_NOTE, measured in MIR1 §3).
    notes = [str(message["content"]) for message in server.bodies[-1]["messages"] if message["role"] == "user"]
    # MIR2: naming the calls that read that capture.
    assert notes[-2] == (f"[Pantalla: la última captura, de las {moment}, ya se borró: lo que mostraron capture_screenshot "
                         "y vision_describe es la pantalla de entonces; en este turno aún no se miró la de ahora.]")
    assert notes[-1] == "¿y qué más dice ahí?"
    # The look itself stays whole in the conversation: «¿qué decía la primera línea?» is still answered from it.
    tool_results = [message for message in server.bodies[-1]["messages"] if message["role"] == "tool"]
    assert any("Paso 1 de 3" in str(message.get("content")) for message in tool_results)


def test_while_a_call_waits_for_the_yes_the_capture_is_kept_and_nothing_is_said(tmp_path, monkeypatch):
    # MainWindowViewModel.ClearCapturesNoCallWaitsFor: a capture stays while a call waits for the person's «sí».
    mind, server = _looked(tmp_path, monkeypatch)
    mind.decide(4, "sí", pending={"operation": "file.write", "arguments": {"path": "a.txt"}})
    assert "se borró" not in _clock_of(server)
    assert not any("[Pantalla:" in str(message["content"]) for message in server.bodies[-1]["messages"])


@pytest.mark.parametrize("setting", ["none", "clock_omitted"])
def test_without_the_aid_the_clock_says_what_it_said(tmp_path, monkeypatch, setting):
    mind, server = _looked(tmp_path, monkeypatch, setting)
    mind.decide(4, "¿y qué más dice ahí?")
    assert "se borró" not in _clock_of(server)
    assert not any("[Pantalla:" in str(message["content"]) for message in server.bodies[-1]["messages"])
