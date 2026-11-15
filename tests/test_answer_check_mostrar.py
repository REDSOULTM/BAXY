"""Kind «mostrar», INT36D (gate i10-C25, «busca en los pagos realizados»: after only reading the window, «Ya te mostré los
pagos realizados: hay 24 movimientos…» 8 of 10 on int36c, two blind judges F, the 1.5.2 5): a claim of having shown the
person something, with no call that shows anything in the turn or the session (a reading shows nothing to them). The
same rule as every act of KINDS: it is read against the calls, not against the words."""
from baxy_mind.answer_check import check

READ = {"op": "input.visible.controls", "tool": "input_visible_controls", "arguments": {}, "observation": "{}",
        "outcome": "completado", "completed": True, "read": True}
OPENED = {"op": "app.open", "tool": "app_open", "arguments": {"appId": "Calculadora"}, "observation": "{}",
          "outcome": "completado y verificado", "completed": True, "read": False}
CLICKED = {"op": "input.visible.click", "tool": "input_visible_click", "arguments": {"index": 1}, "observation": "{}",
           "outcome": "completado", "completed": True, "read": False}


def _rules(answer: str, request: str, receipts: list[dict], session: list | None = None) -> list[str]:
    if session is None:
        session = [(r["op"], r["completed"], r["read"]) for r in receipts]
    return [f["rule"] for f in check(answer, request, receipts, session)]


def test_shown_after_only_a_reading_is_found() -> None:
    answer = "Ya te mostré los pagos realizados: hay 24 movimientos en total."
    assert "no_call" in _rules(answer, "busca en los pagos realizados", [READ])
    assert "no_call" in _rules("Te he mostrado la lista de canciones.", "¿qué canciones hay?", [READ])


def test_shown_after_a_call_that_shows_is_not() -> None:
    assert "no_call" not in _rules("Te mostré la calculadora.", "abre la calculadora", [OPENED])
    assert "no_call" not in _rules("Ya te mostré los pagos realizados.", "busca en los pagos", [READ, CLICKED])
    # a call of an earlier turn of the session
    assert "no_call" not in _rules("Ya te mostré la calculadora antes.", "¿y ahora?", [],
                                   session=[("app.open", True, False)])


def test_what_is_not_a_claim_of_showing_is_not() -> None:
    assert "no_call" not in _rules("¿Quieres que te muestre los pagos?", "busca en los pagos", [READ])
    assert "no_call" not in _rules("No te mostré nada todavía.", "¿qué me mostraste?", [READ])
    assert "no_call" not in _rules("Hay 24 pagos realizados.", "busca en los pagos realizados", [READ])
