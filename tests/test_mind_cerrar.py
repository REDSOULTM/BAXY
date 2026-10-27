"""Aid «close_unsaid» (feria 2026-10-27): «Abre el bloc de notas y escribe Hola feria científica», 3 of 4 runs: after
typing and a look, a click on «Cerrar» and on the «Sí» of what it asked, and the Notepad the person was shown closed. A
click whose label closes or quits, in a turn whose words say nothing of closing, is not handed to the App."""
import json
from pathlib import Path

from baxy_mind.mind import CLOSE_NOT_RUN

from test_mind_final import _call, _mind, _say

DONE = json.dumps({"status": "completed", "verification": "readback"})
VIEW = json.dumps({"status": "completed", "verification": "output_only",
                   "view": "Ventana «Bloc de notas» (Notepad, window 2623998), al frente\nControles:\n[21] Button «Cerrar»"})
CLOSE = _call("input_visible_click", {"label": "Cerrar", "index": 21, "window": 2623998})


def _trace(mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]


def test_a_close_nobody_asked_for_is_not_made_and_the_turn_answers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("app_open", {"appId": "Bloc de notas"}),
                                    _call("input_text_type", {"text": "Hola feria científica"}),
                                    _call("input_visible_controls", {"application": "Bloc de notas"}), CLOSE,
                                    _say("Abrí el Bloc de notas y escribí «Hola feria científica».")])
    step = mind.decide(1, "Abre el bloc de notas y escribe Hola feria científica.")
    for n, result in enumerate([DONE, DONE, VIEW]):
        step = mind.continue_turn(2 + n, result)
    assert step["kind"] == "conversation" and step["reply"].startswith("Abrí el Bloc de notas")
    assert any(CLOSE_NOT_RUN in str(m.get("content")) for m in mind.conversation)
    assert [r["kind"] for r in _trace(mind) if r.get("kind") == "close_unsaid"] == ["close_unsaid"]


def test_a_close_the_person_asked_for_is_made(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for words in ("Cierra el bloc de notas sin guardar.", "ciérralo", "close the notepad"):
        mind, _ = _mind(tmp_path, [_call("input_visible_controls", {"application": "Bloc de notas"}), CLOSE])
        mind.decide(1, words)
        step = mind.continue_turn(2, VIEW)
        assert step["kind"] == "action" and step["operation"] == "input_visible_click", words


def test_without_the_aid_the_close_is_made(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("input_visible_controls", {"application": "Bloc de notas"}), CLOSE])
    mind.decide(1, "escribe hola en el bloc de notas")
    assert mind.continue_turn(2, VIEW)["operation"] == "input_visible_click"
