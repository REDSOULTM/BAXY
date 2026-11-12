"""Aid «check_which_way» (RUT8, the owner's routine «tiempo» = the play/pause key): the result of a media_control that
changed the state says which way it went (previousPlaybackStatus, then playbackStatus). An answer that tells it the other
way («Pausé lo que estaba sonando y ahora se está reproduciendo» after a toggle that resumed: 8 of 36 in Esencial;
«Estaba pausado, ahora suena» after one that paused: 2 of 3 in Completo, INFORME_RUT7.md) is contradicted by those two
fields and the model is asked once more with them. Every word stays the model's; an answer that tells it as it went, a
negation, or a turn that went both ways is not touched."""
import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import CHECK_NOTE
from test_answer_check import _r
from test_mind_final import _call, _mind, _say


def _control(before: str | None, after: str, action: str = "toggle") -> dict:
    observed = {"version": 1, "sourceAppUserModelId": "navegador", "title": "Volcanes de Islandia", "artist": "Canal Brezo",
                "commandSent": "pause" if after == "paused" else "play", "previousPlaybackStatus": before,
                "playbackStatus": after, "authority": "windows_smtc"}
    if before is None:
        del observed["previousPlaybackStatus"], observed["commandSent"]
    return {"status": "completed", "verification": "readback" if before else "unchanged", "observed": observed}


def _way(answer: str, *results: dict) -> list[dict]:
    receipts = [_r("media.control", result, {"action": "toggle"}) for result in results]
    return [f for f in check(answer, "tiempo", receipts, [(r["op"], r["completed"], r["read"]) for r in receipts])
            if f["rule"] == "which_way"]


RESUMED, PAUSED = _control("paused", "playing"), _control("playing", "paused")


@pytest.mark.parametrize("answer", [
    "Pausé el documental de volcanes que estaba pausado y ahora está sonando.",
    "Pausé lo que estaba sonando. Ahora está reproduciendo el documental de volcanes.",
    "He pausado lo que estaba sonando y ahora está reproduciéndose.",
    "Pausaste el documental de volcanes que ya estaba sonando en el navegador.",
    "Lo puse en pausa, ahora está reproduciendo el documental de volcanes.",
    "He puesto en pausa el documental de volcanes que estaba reproduciendo en el navegador.",
    "Ya estaba sonando un documental de volcanes en tu navegador, y ahora sigue.",
    "I paused the documentary that was playing.",
])
def test_a_pause_told_after_a_control_that_resumed_is_contradicted(answer: str) -> None:
    found = _way(answer, RESUMED)
    assert len(found) == 1, answer
    assert "previousPlaybackStatus «paused»" in found[0]["fact"] and "playbackStatus «playing»" in found[0]["fact"]
    assert "estaba en pausa y ahora suena" in found[0]["fact"]


@pytest.mark.parametrize("answer", [
    "Estaba pausado, ahora suena el documental de volcanes del Canal Brezo.",
    "Lo puse en pausa. Ahora está sonando el documental de volcanes.",
    "Ya está reproduciendo el documental de volcanes del Canal Brezo.",
    "Reproduje el documental de volcanes que estaba pausado.",
    "Reanudé el documental de volcanes.",
    "Now playing the volcano documentary.",
])
def test_a_resume_told_after_a_control_that_paused_is_contradicted(answer: str) -> None:
    found = _way(answer, PAUSED)
    assert len(found) == 1, answer
    assert "estaba sonando y ahora está en pausa" in found[0]["fact"]


@pytest.mark.parametrize(("answer", "result"), [
    ("Reanudé el documental de volcanes que estaba pausado.", RESUMED),
    ("Estaba en pausa, ahora suena el documental de volcanes.", RESUMED),
    ("Ya está reproduciendo el documental de volcanes que estaba pausado.", RESUMED),
    ("Lo que estaba pausado ahora suena.", RESUMED),
    ("Ya le di play a lo que estaba pausado.", RESUMED),
    ("No lo pausé: estaba en pausa y ahora suena.", RESUMED),
    ("Pausé el documental de volcanes que estaba sonando en el navegador.", PAUSED),
    ("Lo que estaba sonando se ha pausado.", PAUSED),
    ("Lo puse en pausa.", PAUSED),
    ("El vídeo del documental de volcanes ahora está pausado.", PAUSED),
    ("Está pausado; lo que estaba sonando era un documental de volcanes.", PAUSED),
    ("I paused the documentary that was playing.", PAUSED),
])
def test_an_answer_that_tells_it_as_it_went_is_not_touched(answer: str, result: dict) -> None:
    assert _way(answer, result) == [], answer


def test_a_turn_that_went_both_ways_or_a_result_with_no_state_before_is_not_read() -> None:
    assert _way("Pausé el documental y después lo reanudé.", PAUSED, RESUMED) == []
    assert _way("Pausé el documental.", _control(None, "playing", "play")) == []
    assert _way("Reproduje el documental.", _control(None, "paused", "pause")) == []


def test_the_model_is_asked_once_more_with_the_two_states(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("media_control", {"action": "toggle"}),
                                    _say("Pausé lo que estaba sonando y ahora se está reproduciendo."),
                                    _say("Estaba en pausa; ahora suena Volcanes de Islandia.")])
    mind.configure({"capabilities": [{"name": "media.control", "description": "Controla lo que suena.",
                                      "risk": "low_reversible", "argumentsSchema": {"type": "object", "properties": {
                                          "action": {"type": "string"}}}}]})
    mind.decide(1, "Baxy, dale al botón de reproducir o pausar")
    result = mind.continue_turn(1, json.dumps(RESUMED, ensure_ascii=False))
    assert result["kind"] == "conversation" and result["reply"] == "Estaba en pausa; ahora suena Volcanes de Islandia."
    note = server.bodies[-1]["messages"][-1]["content"]
    assert note.startswith(CHECK_NOTE[:40]) and "previousPlaybackStatus «paused»" in note


def test_with_the_aid_off_the_answer_stands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    said = "Pausé lo que estaba sonando y ahora se está reproduciendo."
    mind, _ = _mind(tmp_path, [_call("media_control", {"action": "toggle"}), _say(said)])
    mind.configure({"capabilities": [{"name": "media.control", "description": "Controla lo que suena.",
                                      "risk": "low_reversible", "argumentsSchema": {"type": "object", "properties": {
                                          "action": {"type": "string"}}}}]})
    mind.decide(1, "Baxy, dale al botón de reproducir o pausar")
    assert mind.continue_turn(1, json.dumps(RESUMED, ensure_ascii=False))["reply"] == said
