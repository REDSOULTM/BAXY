"""Rule «given_act», INT36B (a11-H1-dp, a11-P1-dp: after this turn's clipboard_paste completed, «Lo pegaste en lista.txt
del Bloc de notas» 5-8 of 10 with the 1.5.3 pieces, the 1.5.2 0-1; BAN2 b2p-13 «Ya apagaste la pantalla de la izquierda»
after BAXY's own display_monitor_set): BAXY's act told as the person's. Only the form: the second person preterite of a
kind of act, in a statement, while a call of that kind completed in this turn and the person's words tell no act of
theirs of that kind."""
from baxy_mind.answer_check import check

PASTE = {"op": "clipboard.paste", "tool": "clipboard_paste", "arguments": {}, "observation": "{}",
         "outcome": "completado y verificado", "completed": True, "read": False}
DARK = {"op": "display.monitor.set", "tool": "display_monitor_set", "arguments": {"active": False}, "observation": "{}",
        "outcome": "entregado", "completed": True, "read": False}
ASKED = "Pega en el bloc de notas lo que tengo copiado."


def _rules(answer: str, request: str, receipts: list[dict]) -> list[str]:
    session = [(r["op"], True, False) for r in receipts]
    return [f["rule"] for f in check(answer, request, receipts, session)]


def test_baxys_paste_told_as_the_persons_is_found() -> None:
    assert "given_act" in _rules("Lo pegaste en lista.txt del Bloc de notas.", ASKED, [PASTE])
    assert "given_act" in _rules("Ya apagaste la pantalla de la izquierda.", "apaga las dos pantallas", [DARK])


def test_what_the_person_did_before_or_asks_is_not() -> None:
    assert "given_act" not in _rules("Lo que copiaste ya está pegado en tu lista.", ASKED, [PASTE])
    assert "given_act" not in _rules("Lo pegué en lista.txt.", ASKED, [PASTE])
    assert "given_act" not in _rules("¿Ya lo pegaste?", ASKED, [PASTE])
    assert "given_act" not in _rules("No lo pegaste tú: lo pegué yo.", ASKED, [PASTE])
    assert "given_act" not in _rules("Lo pegaste tú antes.", "ya lo pegué yo, ¿quedó?", [PASTE])


def test_with_no_call_of_its_kind_in_the_turn_it_is_not() -> None:
    assert "given_act" not in _rules("Lo pegaste en lista.txt.", ASKED, [])
