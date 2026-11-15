"""VER3B (13-11-2026): to «cuánta memoria ram tiene esta compu» the model answered «Tienes 32 GB de RAM instalados.» with
no call at all (VER3 held-out, Esencial, 2 of 3 seeds; the base read it with system.status). The rule «number» compares a
size with the numbers of the turn's results, and with no result at all it read nothing. A size told while nothing of the
conversation shows that number (no result of the turn or still shown, not the person's words, not a fact the App gave in
the system text) is a reading of the PC nothing made: the rule «unread_size», and the model is told so keeping its tools
so it may look (STATE_NOTE), as «estoy al día» with nothing that looked (ACT1)."""
import json
from pathlib import Path

from baxy_mind.answer_check import check
from baxy_mind.mind import STATE_NOTE
from test_mind_aids import _trace
from test_mind_final import _call, _mind, _say

MEMORY = {"status": "completed", "verification": "output_only", "observed": {
    "memory": {"totalBytes": 17_179_869_184, "availableBytes": 6_442_450_944}}}


def _rules(answer: str, request: str, receipts=(), session=(), earlier=None, told: str | None = None) -> set[str]:
    return {f["rule"] for f in check(answer, request, list(receipts), list(session), earlier=earlier, system_text=told)}


def _read(op: str, observed: dict) -> dict:
    return {"op": op, "tool": op.replace(".", "_"), "arguments": {}, "observation": json.dumps(
        {"status": "completed", "observed": observed}), "outcome": "completed", "completed": True, "read": True}


def test_a_size_told_with_nothing_that_read_it_is_found() -> None:
    for answer, request in (("Tienes 32 GB de RAM instalados.", "cuánta memoria ram tiene esta compu"),
                            ("Te quedan 120 GB libres en el disco C:.", "cuanto espacio me queda"),
                            ("Your graphics card has 8 GB of video memory.", "how much vram do i have")):
        assert "unread_size" in _rules(answer, request), answer


def test_a_size_a_result_shows_or_the_person_said_is_not() -> None:
    reading = _read("system.status", MEMORY["observed"])
    # Read in this turn: the rule «number» is the one that compares it.
    assert "unread_size" not in _rules("Tienes 16 GB de RAM.", "cuánta ram tengo", [reading],
                                       [("system.status", True, True)])
    # Read in an earlier turn that the conversation still shows.
    assert "unread_size" not in _rules("Sí, son 16 GB en total.", "¿y en total?", [], [("system.status", True, True)],
                                       earlier=[reading])
    # The person's own number.
    assert "unread_size" not in _rules("Con 32 GB de RAM te alcanza para eso.", "tengo 32 gb de ram, me alcanza?")
    # A fact the App put in the system text (the card's free video memory, VRAM4B).
    told = "la tarjeta gráfica de este PC tenía 3,2 GB de memoria de vídeo libres y el perfil Completo necesita unos 6,1 GB."
    assert "unread_size" not in _rules("Porque tu tarjeta tenía 3,2 GB libres y Completo necesita 6,1 GB.",
                                       "por qué estás en esencial", told=told)


def test_a_session_not_known_whole_is_not_read() -> None:
    assert not [f for f in check("Tienes 32 GB de RAM.", "cuánta ram tengo", [], None) if f["rule"] == "unread_size"]


# ---- the mind --------------------------------------------------------------------------------------------------------
def test_the_model_is_told_and_may_look(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_say("Tienes 32 GB de RAM instalados."), _call("system_status", {"scope": "memory"}),
                                    _say("Tienes 16 GB de RAM.")])
    mind.configure({"capabilities": [
        {"name": "system.status", "description": "Reads the PC's status.", "risk": "read_only",
         "argumentsSchema": {"type": "object", "properties": {"scope": {"type": "string"}}}}]})
    result = mind.decide(1, "cuánta memoria ram tiene esta compu")
    assert result["kind"] == "action" and result["operation"] == "system.status"
    note = server.bodies[-1]["messages"][-1]
    assert note["role"] == "user" and note["content"].startswith(STATE_NOTE[:40])
    assert "tool_choice" not in server.bodies[-1]  # its tools stay: it may look
    checks = [r for r in _trace(mind) if r["stage"] == "turn.check"]
    assert checks[0]["findings"][0]["rule"] == "unread_size"
    final = mind.continue_turn(1, json.dumps(MEMORY))
    assert final.get("reply") == "Tienes 16 GB de RAM."
