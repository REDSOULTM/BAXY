"""PAN7 (VIVO21 fila 6, 14-11-2026): «cierra la calculadora y el bloc de notas»: the calculator closed, the Bloc de notas
asked whether to save (close_prompted) and stayed; after BAXY's question and the person's «sí», «Ya cerré el Bloc de
notas» with no call. The rule of acts reads kinds, and the calculator's close backed any «cerré». The rule
``unclosed_name`` reads the name: a close claimed of an application whose close calls of the conversation never
completed, while none that completed names it."""
from __future__ import annotations

import json

from baxy_mind import answer_check, mind


def _call(app: str, completed: bool, outcome: str, observed: dict | None = None) -> dict:
    return {"op": "app.close", "tool": "app_close", "arguments": {"appId": app}, "target": app,
            "observation": json.dumps({"status": "completed" if completed else "failed", **(observed or {})}),
            "outcome": outcome, "completed": completed, "read": False}


CALC = _call("Calculator", True, "completado")
NOTEPAD = _call("Notepad", False, "falló: close_prompted", {"error": "close_prompted"})


def _check(answer: str, earlier: list[dict], receipts: list[dict] | None = None) -> list[dict]:
    session = [(c["op"], c["completed"], c["read"]) for c in earlier]
    return answer_check.check(answer, "sí", receipts or [], session, earlier=earlier, said_app=mind.names_app)


def test_a_close_claimed_of_the_app_whose_close_never_completed_is_contradicted() -> None:
    found = _check("Ya cerré el Bloc de notas.", [CALC, NOTEPAD])
    assert [f["rule"] for f in found] == ["unclosed_name"]
    assert "Notepad" in found[0]["fact"] and "Calculator" in found[0]["fact"]


def test_in_english_too() -> None:
    assert [f["rule"] for f in _check("I closed Notepad.", [CALC, NOTEPAD])] == ["unclosed_name"]
    assert [f["rule"] for f in _check("I've closed the calculator and Notepad.", [CALC, NOTEPAD])] == ["unclosed_name"]


def test_the_state_told_of_it_too() -> None:
    # The bench (PAN7, cerre-en s1): «Notepad is now closed.» after the «yes», with no call.
    for said in ("Notepad is now closed.", "Notepad has been closed.", "El Bloc de notas ya está cerrado."):
        assert "unclosed_name" in [f["rule"] for f in _check(said, [CALC, NOTEPAD])], said
    for said in ("Notepad is not closed yet.", "The calculator is closed; Notepad is still open.",
                 "If Notepad is closed, tell me."):
        assert "unclosed_name" not in [f["rule"] for f in _check(said, [CALC, NOTEPAD])], said


def test_both_named_in_one_claim() -> None:
    assert [f["rule"] for f in _check("Ya cerré la calculadora y el bloc de notas.", [CALC, NOTEPAD])] == ["unclosed_name"]


def test_a_pronoun_for_the_app_named_in_the_sentence() -> None:
    # The bench (PAN7, cerre-es s4): «El Bloc de notas ya te preguntó si quieres guardar; con tu sí, lo cerré sin guardar».
    said = "El Bloc de notas ya te preguntó si quieres guardar; con tu sí, lo cerré sin guardar los cambios."
    assert [f["rule"] for f in _check(said, [CALC, NOTEPAD])] == ["unclosed_name"]
    # Control: the pronoun of the one that did close.
    assert _check("La calculadora estaba abierta, y la cerré.", [CALC, NOTEPAD]) == []
    assert _check("Cerré la calculadora; el Bloc de notas sigue abierto porque pide guardar.", [CALC, NOTEPAD]) == []


def test_the_close_that_completed_is_no_finding() -> None:
    assert _check("Ya cerré la calculadora.", [CALC, NOTEPAD]) == []


def test_saying_it_did_not_close_is_no_finding() -> None:
    assert _check("Cerré la calculadora, pero no pude cerrar el Bloc de notas: pide guardar.", [CALC, NOTEPAD]) == []


def test_a_later_close_that_completed_backs_it() -> None:
    again = _call("Notepad", True, "completado")
    assert _check("Ya cerré el Bloc de notas.", [CALC, NOTEPAD], [again]) == []
    assert _check("Ya cerré el Bloc de notas.", [CALC, NOTEPAD, again]) == []


def test_a_close_by_window_alone_names_nothing_and_backs_it() -> None:
    by_window = {**_call("", True, "completado"), "arguments": {"windowId": "win_2"}, "target": None}
    assert _check("Ya cerré el Bloc de notas.", [CALC, NOTEPAD, by_window]) == []


def test_with_no_name_reader_nothing_changes() -> None:
    session = [(c["op"], c["completed"], c["read"]) for c in (CALC, NOTEPAD)]
    assert answer_check.check("Ya cerré el Bloc de notas.", "sí", [], session, earlier=[CALC, NOTEPAD]) == []
