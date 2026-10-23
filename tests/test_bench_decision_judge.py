"""The decision bench's judge of a text case (scripts/renew/bench_decision.py): with reply_re / reply_not_re (holdout of
the goal «ayudas», SEALED_AYUDAS.md) the words count, normalized; without them any spoken answer counts, as before."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

from bench_decision import judge  # noqa: E402


def _said(reply: str) -> dict:
    return {"kind": "conversation", "reply": reply}


def test_a_text_case_without_regexes_takes_any_spoken_answer() -> None:
    assert judge({"kind": "text"}, _said("Claro."), None) is True
    assert judge({"kind": "text"}, _said("  "), None) is False
    assert judge({"kind": "text"}, {"kind": "action", "operation": "app.open"}, None) is False


def test_a_text_case_must_say_what_reply_re_asks_and_never_what_reply_not_re_forbids() -> None:
    expect = {"kind": "text", "reply_re": "todavia no|aun no|proximamente", "reply_not_re": "active|activado"}
    assert judge(expect, _said("Ese modo todavía no está disponible."), None) is True
    assert judge(expect, _said("Ese modo no existe."), None) is False
    assert judge(expect, _said("Listo, lo he activado; aún no narra todo."), None) is False


def test_lists_of_regexes_all_must_match_and_none_may() -> None:
    expect = {"kind": "text", "reply_re": ["paint", "no pude"], "reply_not_re": ["cerre", "listo"]}
    assert judge(expect, _said("No pude cerrar Paint."), None) is True
    assert judge(expect, _said("Cerré Paint."), None) is False


def test_an_argument_the_catalog_renamed_is_checked_under_its_new_name() -> None:
    # 1d321726d renamed filesystem.sandbox.diff.named's leftQuery/rightQuery to leftFileName/rightFileName; a bank written
    # before it (decision2 P212) names the old ones, which no call can carry any more.
    expect = {"kind": "call", "op": "filesystem.sandbox.diff.named",
              "args": {"leftQuery": "version1", "rightQuery": "version2"}}
    called = {"kind": "action", "operation": "filesystem.sandbox.diff.named"}
    assert judge(expect, called, {"leftFileName": "version1.txt", "rightFileName": "version2.txt"}) is True
    assert judge(expect, called, {"leftFileName": "version2.txt", "rightFileName": "version1.txt"}) is False
