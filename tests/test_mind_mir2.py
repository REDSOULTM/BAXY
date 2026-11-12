"""MIR2 (VIVO5 fila 4, 2026-11-10): a look of an earlier turn read by OCR (capture.screenshot + ocr.read, the results as
OperationVisibleFacts.FromOutcome leaves them) is told as the screen of its moment whose capture is gone, as MIR1 tells a
look described by vision: the mark is read from the data (the results' «captureId»), not from the operation's name."""
import datetime as _dt
import json

from test_mind_mir1 import CAPTURE, _call, _clock_of

# CaptureVisionAdapter.ReadOcrAsync without «authority» (OperationVisibleFacts.OpaqueKeys), text as tesseract gave it.
OCR_TEXT = "BAXY\nActivo\nSalió a internet\nHistorial 1\n88 Capacidades 191\n12 pedidos - todo local"


def _read_by_ocr(tmp_path, monkeypatch):
    from test_mind_final import _mind, _say
    monkeypatch.setenv("BAXY_AYUDAS", "")
    # MIR4: the note tells the capture's age from the turn's moment (CAPTURE_AGE_NOTE), fixed here 30 s after it.
    from baxy_mind.mind import Mind
    monkeypatch.setattr(Mind, "_now", staticmethod(lambda: _dt.datetime(2026, 11, 10, 12, 33, 43, tzinfo=_dt.timezone.utc)))
    mind, server = _mind(tmp_path, [_call("k1", "capture_screenshot", {}),
                                    _call("k2", "ocr_read", {"captureId": CAPTURE}),
                                    _say("Dice «BAXY, Activo»."), _say("Sigue diciendo lo mismo.")])
    mind.risk = {"capture_screenshot": "privacy_sensitive", "ocr_read": "privacy_sensitive"}
    mind.decide(1, "mira mi pantalla y dime qué dice")
    mind.continue_turn(2, json.dumps({"status": "completed", "verification": "output_only", "observed": {
        "version": 1, "captureId": CAPTURE, "width": 1920, "height": 1080, "sha256": "ab" * 32,
        "scope": "virtual_screen", "createdAtUtc": "2026-11-10T12:33:13Z"}}))
    mind.continue_turn(3, json.dumps({"status": "completed", "verification": "output_only", "observed": {
        "version": 1, "captureId": CAPTURE, "language": "spa+eng", "text": OCR_TEXT, "textSha256": "cd" * 32,
        "lineCount": 6, "layout": {"available": False, "reason": "backend_returns_flat_text"}}}))
    return mind, server


def test_a_look_read_by_ocr_in_an_earlier_turn_is_told_as_the_screen_of_its_moment(tmp_path, monkeypatch):
    mind, server = _read_by_ocr(tmp_path, monkeypatch)
    mind.decide(4, "¿y qué más dice ahí?")
    clock = _clock_of(server)
    moment = _dt.datetime(2026, 11, 10, 12, 33, 13, tzinfo=_dt.timezone.utc).astimezone().strftime("%H:%M")
    gone = f"; su captura ya se borró: lo que mostró es la pantalla de las {moment}"
    assert f"capture_screenshot → lectura: sólo miró, sin abrir, cerrar ni cambiar nada{gone}" in clock
    assert f"ocr_read → lectura: sólo miró, sin abrir, cerrar ni cambiar nada{gone}" in clock
    notes = [str(message["content"]) for message in server.bodies[-1]["messages"] if message["role"] == "user"]
    assert notes[-2].startswith("[Pantalla: la última captura se tomó hace 30 segundos y ya se borró")
    assert notes[-1] == "¿y qué más dice ahí?"
    # What ocr_read gave is told, by its own name, as the screen of then (CAPTURE_NOTE names the calls of that capture).
    assert "lo que mostraron capture_screenshot y ocr_read es la pantalla de hace 30 segundos" in notes[-2]
    # What the OCR read stays in the conversation, as of then.
    assert any("88 Capacidades 191" in str(message.get("content"))
               for message in server.bodies[-1]["messages"] if message["role"] == "tool")
