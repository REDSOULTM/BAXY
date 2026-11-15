"""VER3 (13-11-2026): the prefix no longer says BAXY's version, and asked which it is the model sometimes answered with a
number of its own («Soy la versión 2.1.0», «I'm running version 2.1.4») without reading it (held-out, Esencial). A version
number told of BAXY itself with nothing of the conversation that read it is a reading nothing made, as «estoy al día» is
(ACT1): the rule «unread_version»; read (assistant.status, or baxy.update whose result says the one installed), or a
number a result of the turn shows, it is not."""
import json

from baxy_mind.answer_check import check


def _rules(answer: str, request: str, receipts=(), session=()) -> set[str]:
    return {f["rule"] for f in check(answer, request, list(receipts), list(session))}


def _read(op: str, observed: dict) -> dict:
    return {"op": op, "tool": op.replace(".", "_"), "arguments": {}, "observation": json.dumps(
        {"status": "completed", "observed": observed}), "outcome": "completed", "completed": True, "read": True}


def test_a_version_of_baxy_told_with_nothing_that_read_it_is_found() -> None:
    for answer, request in (("Soy la versión 2.1.0. ¿Te ayudo con algo más?", "che y vos que version sos"),
                            ("Mi versión actual es la 2.4.1.", "decime tu version"),
                            ("I'm running version 2.1.4.", "tell me your version number"),
                            ("Tienes instalada la versión 1.1.0 de BAXY.", "qué versión tengo")):
        assert "unread_version" in _rules(answer, request), answer


def test_the_most_recent_told_while_running_it_with_nothing_that_looked_is_found() -> None:
    # ACT1's rule, with the verb the model used: «estoy usando / ejecutando la versión más reciente» (held-out, Esencial).
    for answer in ("Estoy usando la versión más reciente de BAXY instalada en tu PC.",
                   "Estoy ejecutando la versión más reciente de BAXY instalada en este PC."):
        assert "unchecked_update" in _rules(answer, "oye q vercion estai usando tu"), answer
    update = _read("baxy.update", {"version": 1, "installed": "1.5.2", "checked": True, "latest": "1.5.2", "newer": False})
    assert "unchecked_update" not in _rules("Estoy usando la versión más reciente.", "estás al día", [update],
                                            [("baxy.update", True, True)])


def test_read_or_backed_by_a_result_it_is_not() -> None:
    status = _read("assistant.status", {"version": 1, "scope": "version", "installed": "1.5.2"})
    assert "unread_version" not in _rules("Soy la versión 1.5.2.", "qué versión eres", [status],
                                          [("assistant.status", True, True)])
    # Read earlier in the conversation: the session holds the reading.
    assert "unread_version" not in _rules("Sigo en la versión 1.5.2.", "y ahora", [], [("assistant.status", True, True)])
    update = _read("baxy.update", {"version": 1, "installed": "1.5.2", "checked": True, "latest": "1.5.2", "newer": False})
    assert "unread_version" not in _rules("Tengo la versión 1.5.2, la última.", "estás al día", [update],
                                          [("baxy.update", True, True)])


def test_other_versions_and_other_numbers_are_not_baxys() -> None:
    windows = _read("system.status", {"os": "Windows 11", "build": "10.0.26100"})
    assert "unread_version" not in _rules("Este PC tiene Windows 11, versión 10.0.26100.", "qué windows tengo",
                                          [windows], [("system.status", True, True)])
    assert "unread_version" not in _rules("La pantalla está a 1920x1080 y 60 Hz.", "qué resolución tengo")
    assert "unread_version" not in _rules("No sé qué versión de Chrome tienes.", "qué versión de chrome tengo")
