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


def test_an_any_case_is_met_by_any_of_its_options() -> None:
    # decision3 Q084: the date answered from the turn's clock (the design) or read with system.time.
    expect = {"kind": "any", "options": [{"kind": "text"}, {"kind": "call", "op": "system.time", "args": {}}]}
    assert judge(expect, _said("Hoy es jueves 15 de octubre."), None) is True
    assert judge(expect, {"kind": "action", "operation": "system.time"}, {}) is True
    assert judge(expect, {"kind": "action", "operation": "web.search"}, {"query": "fecha"}) is False


def test_an_any_case_checks_the_arguments_of_each_option() -> None:
    # decision3 Q263: folder documents, or the known folder at the head of the path (the provider maps it).
    expect = {"kind": "any", "options": [
        {"kind": "call", "op": "filesystem.create.directory", "args": {"folder": "documents", "relativePath": "proyectos"}},
        {"kind": "call", "op": "filesystem.create.directory",
         "args": {"relativePath": r"re:(^|[/\\])(documentos|documents|mis documentos)[/\\]proyectos"}}]}
    called = {"kind": "action", "operation": "filesystem.create.directory"}
    assert judge(expect, called, {"relativePath": "Documentos/Proyectos"}) is True
    assert judge(expect, called, {"relativePath": "Proyectos", "folder": "documents"}) is True
    assert judge(expect, called, {"relativePath": "Proyectos"}) is False


def test_an_any_case_whose_options_were_all_retired_is_not_counted() -> None:
    expect = {"kind": "any", "options": [{"kind": "call", "op": "routine.list"}, {"kind": "call_any", "ops": ["routine.read"]}]}
    assert judge(expect, {"kind": "action", "operation": "routine.list"}, {}) is None


def test_a_case_with_a_pending_confirmation_reaches_the_mind_with_it() -> None:
    from bench_decision import decide
    seen = {}

    class Mind:
        def decide(self, request_id, text, pending=None, unsure=None):
            seen.update(id=request_id, text=text, pending=pending)
            return {"kind": "action"}

    pending = {"operation": "file.trash", "arguments": {"fileName": "a.txt"}}
    decide(Mind(), {"id": "X1", "text": "dale", "pending": pending})
    assert seen == {"id": "X1", "text": "dale", "pending": pending}
    decide(Mind(), {"id": "X2", "text": "abre paint"})
    assert seen["pending"] is None



def test_a_case_with_the_words_the_ear_was_unsure_of_reaches_the_mind_with_them() -> None:
    """P1.4 (noche 2026-10-27): voice.Heard's doubts reach the model only beside a spoken request, so a case can carry
    them (``unsure``: [word, p] pairs) and the bench measures the decision the model makes with that fact."""
    from bench_decision import decide
    seen = {}

    class Mind:
        def decide(self, request_id, text, pending=None, unsure=None):
            seen.update(text=text, unsure=unsure)
            return {"kind": "conversation"}

    decide(Mind(), {"id": "X3", "text": "pon el volumen en treinta", "unsure": [["treinta", 0.2]]})
    assert seen == {"text": "pon el volumen en treinta", "unsure": [["treinta", 0.2]]}
    decide(Mind(), {"id": "X4", "text": "abre paint"})
    assert seen["unsure"] is None

# Audit w8-medir (2026-10-23): an argument of a code list is that code. As part of the text, «close» passed close_all,
# «space» backspace and «escape» ctrl_shift_escape; free text (a name, a path) is still met by the text that holds it.
CATALOG = {"capabilities": [
    {"name": "browser.control", "argumentsSchema": {"properties": {
        "action": {"type": "string", "enum": ["close", "close_all", "new_tab"]}}}},
    {"name": "input.key.press", "argumentsSchema": {"properties": {
        "key": {"type": "string", "enum": ["space", "backspace", "escape", "ctrl_shift_escape"]}}}},
    {"name": "app.open", "argumentsSchema": {"properties": {
        "appId": {"type": "string"}, "place": {"type": "string", "enum": ["game", "gamemode"]}}}},
]}


def _call(op: str) -> dict:
    return {"kind": "action", "operation": op}


def test_a_code_of_the_arguments_list_must_be_that_code() -> None:
    from bench_decision import enums_of
    enums = enums_of(CATALOG)
    close = {"kind": "call", "op": "browser.control", "args": {"action": "close"}}
    assert judge(close, _call("browser.control"), {"action": "close_all"}, enums) is False
    assert judge(close, _call("browser.control"), {"action": "Close "}, enums) is True
    space = {"kind": "call", "op": "input.key.press", "args": {"key": "space"}}
    assert judge(space, _call("input.key.press"), {"key": "backspace"}, enums) is False
    escape = {"kind": "call", "op": "input.key.press", "args": {"key": "escape"}}
    assert judge(escape, _call("input.key.press"), {"key": "ctrl_shift_escape"}, enums) is False
    # Without the catalog the judge reads as before the audit (a run re-judged without --catalog).
    assert judge(close, _call("browser.control"), {"action": "close_all"}) is True


def test_free_text_and_a_value_outside_the_list_are_still_part_of_the_text() -> None:
    from bench_decision import enums_of
    enums = enums_of(CATALOG)
    chrome = {"kind": "call", "op": "app.open", "args": {"appId": "chrome", "place": "re:^game$"}}
    assert judge(chrome, _call("app.open"), {"appId": "Google Chrome", "place": "game"}, enums) is True
    assert judge(chrome, _call("app.open"), {"appId": "Google Chrome", "place": "gamemode"}, enums) is False
    # An expectation written for a code the list no longer has is read as text, as it was.
    older = {"kind": "call", "op": "app.open", "args": {"place": "mode"}}
    assert judge(older, _call("app.open"), {"place": "gamemode"}, enums) is True


def test_an_any_case_hands_the_codes_to_each_option() -> None:
    from bench_decision import enums_of
    expect = {"kind": "any", "options": [{"kind": "call", "op": "browser.control", "args": {"action": "close"}},
                                         {"kind": "ask"}]}
    assert judge(expect, _call("browser.control"), {"action": "close_all"}, enums_of(CATALOG)) is False
