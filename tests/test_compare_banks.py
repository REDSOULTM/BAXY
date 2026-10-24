"""compare_banks re-judges a stored decision run against a newer practice bank: a relabelled case is judged under its new
id and expectation, a retired one is left out, the rest keep their id and verdict."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

from compare_banks import mapping, rejudge  # noqa: E402

OLD = [
    {"id": "P001", "expect": {"kind": "call", "op": "system.time", "args": {}}},
    {"id": "P002", "expect": {"kind": "text"}},
    {"id": "P003", "expect": {"kind": "text"}},
]
NEW = [
    {"id": "Q001", "relabel_of": "P001",
     "expect": {"kind": "any", "options": [{"kind": "text"}, {"kind": "call", "op": "system.time", "args": {}}]}},
    {"id": "P002", "expect": {"kind": "text"}},
]
ROWS = [
    {"id": "P001", "kind": "conversation", "operation": None, "arguments": None, "reply": "Hoy es jueves."},
    {"id": "P002", "kind": "action", "operation": "web.search", "arguments": {"query": "x"}, "reply": None},
    {"id": "P003", "kind": "conversation", "operation": None, "arguments": None, "reply": "Claro."},
]


def test_relabelled_retired_and_kept_cases() -> None:
    by_old, retired = mapping(OLD, NEW)
    assert by_old["P001"]["id"] == "Q001" and by_old["P002"]["id"] == "P002" and retired == ["P003"]
    result = rejudge(ROWS, {c["id"]: c for c in OLD}, by_old)
    assert result["old"] == (1, 3)  # P003 only
    assert result["new"] == (1, 2)  # Q001 ok, P002 bad, P003 retired
    assert result["flips"] == ["P001→Q001 ok"]
    assert [(r["id"], r["ok"], r["relabel_of"]) for r in result["rows"]] == [("Q001", True, "P001"), ("P002", False, None)]


def test_a_row_with_an_error_is_a_failure_in_both_banks() -> None:
    by_old, _ = mapping(OLD, NEW)
    row = {**ROWS[0], "error": "RuntimeError('server')"}
    result = rejudge([row], {c["id"]: c for c in OLD}, by_old)
    assert result["old"] == (0, 1) and result["new"] == (0, 1) and result["flips"] == []


def test_a_rejudge_with_the_runs_catalog_holds_each_code_to_itself() -> None:
    # Audit w8-medir: the same bank as old and new re-judges a run with today's judge; with the catalog, close is not
    # close_all.
    from bench_decision import enums_of
    bank = [{"id": "H001", "expect": {"kind": "call", "op": "browser.control", "args": {"action": "close"}}}]
    row = {"id": "H001", "kind": "action", "operation": "browser.control", "arguments": {"action": "close_all"}}
    by_old, _ = mapping(bank, bank)
    catalog = {"capabilities": [{"name": "browser.control", "argumentsSchema": {"properties": {
        "action": {"enum": ["close", "close_all"]}}}}]}
    assert rejudge([row], {"H001": bank[0]}, by_old)["new"] == (1, 1)
    assert rejudge([row], {"H001": bank[0]}, by_old, enums_of(catalog))["new"] == (0, 1)
