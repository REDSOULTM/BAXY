"""MIR4 (VIVO8 fila 5, MIR3 §1): with the capture taken in the clock's own minute the note «la última captura, de las
22:00, … es la pantalla de entonces» read as now with the clock at 22:00. The note tells how long ago it was taken."""
import datetime as _dt
import json

import pytest

CAPTURE = "capture_" + "cd" * 16
TAKEN = "2026-11-11T01:00:00Z"


def _call(call_id: str, name: str, arguments: dict) -> dict:
    function = {"name": name}
    function["arguments"] = json.dumps(arguments)
    return {"choices": [{"message": {"content": "", "tool_calls": [{"id": call_id, "function": function}]}}]}


def _note(tmp_path, monkeypatch, now: _dt.datetime, taken: str = TAKEN) -> str:
    from baxy_mind.mind import Mind
    from test_mind_final import _mind, _say
    monkeypatch.setenv("BAXY_AYUDAS", "")
    monkeypatch.setattr(Mind, "_now", staticmethod(lambda: now), raising=False)
    mind, server = _mind(tmp_path, [_call("k1", "capture_screenshot", {}),
                                    _call("k2", "ocr_read", {"captureId": CAPTURE}),
                                    _say("Dice «Paso 1 de 3» y «Siguiente»."), _say("Nada más.")])
    mind.risk = {"capture_screenshot": "read_only", "ocr_read": "read_only"}
    mind.decide(1, "mira mi pantalla y dime qué dice")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "output_only", "observed": {
        "captureId": CAPTURE, "createdAtUtc": taken, "width": 1920, "height": 1080}}))
    mind.continue_turn(3, json.dumps({"status": "completed", "verification": "output_only", "observed": {
        "captureId": CAPTURE, "text": "Paso 1 de 3\nSiguiente"}}))
    mind.decide(4, "¿y qué más dice ahí?")
    notes = [str(message["content"]) for message in server.bodies[-1]["messages"] if message["role"] == "user"]
    assert notes[-1] == "¿y qué más dice ahí?"
    return notes[-2]


@pytest.mark.parametrize("seconds, age", [(40, "40 segundos"), (1, "1 segundo"), (65, "1 minuto"), (220, "3 minutos"),
                                          (7300, "2 horas")])
def test_a_capture_of_the_clocks_own_minute_is_told_by_how_long_ago_it_was_taken(tmp_path, monkeypatch, seconds, age):
    now = _dt.datetime(2026, 11, 11, 1, 0, tzinfo=_dt.timezone.utc) + _dt.timedelta(seconds=seconds)
    assert _note(tmp_path, monkeypatch, now) == (
        f"[Pantalla: la última captura se tomó hace {age} y ya se borró: lo que mostraron capture_screenshot y ocr_read "
        f"es la pantalla de hace {age}; en este turno aún no se miró la de ahora.]")


def test_a_capture_ahead_of_the_clock_keeps_the_clocks_time(tmp_path, monkeypatch):
    now = _dt.datetime(2026, 11, 11, 0, 59, tzinfo=_dt.timezone.utc)
    moment = _dt.datetime(2026, 11, 11, 1, 0, tzinfo=_dt.timezone.utc).astimezone().strftime("%H:%M")
    assert _note(tmp_path, monkeypatch, now) == (
        f"[Pantalla: la última captura, de las {moment}, ya se borró: lo que mostraron capture_screenshot y ocr_read es "
        "la pantalla de entonces; en este turno aún no se miró la de ahora.]")
