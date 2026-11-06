"""Cosecha 04-11. F27: a web_search that left out the one name the person said is told so with the call that searches it.
F18: an answer with no call that says it cannot, about what no operation of the rule ``denial`` covers, is told what
web_search reaches, and the model reads what the person asked."""
import json
from pathlib import Path

import pytest

from baxy_mind.answer_check import check
from baxy_mind.mind import _names_left_out
from test_answer_check import _r
from test_mind_final import _call, _mind, _say


@pytest.mark.parametrize("request_, query, left", [
    ("Si busca Lumyra en internet", "trabajos universitarios", ["Lumyra"]),
    ("Sí, busca Zentrix Labs", "cursos online", ["Zentrix", "Labs"]),
    ("Busca a Zentrix en la web", "Zentrix empresa", []),  # the name is in it
    ("What is the capital of France?", "capital de Francia", []),  # another wording: it holds a word of theirs
    ("búscalo en internet", "fotosíntesis", []),  # no name written: lower case or none said
    ("si busca lumyra en internet", "trabajos universitarios", []),  # voice in lower case: nothing is read (a limit)
    ("Lumyra", "trabajos", []),  # a capital at the start of a sentence is no name
])
def test_a_query_that_left_out_every_name_the_person_said(request_: str, query: str, left: list[str]) -> None:
    assert _names_left_out(request_, json.dumps({"query": query})) == left


SEARCH = json.dumps({"status": "completed", "observed": {"query": "Lumyra", "results": [], "resultCount": 0}})


def _turn(tmp_path: Path, monkeypatch, aids: str = "") -> tuple:
    if aids:
        monkeypatch.setenv("BAXY_AYUDAS", aids)
    else:
        monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_call("web_search", {"query": "trabajos universitarios"}),
                                    _call("web_search", {"query": "trabajos universitarios"}), _say("Encontré ofertas.")])
    mind.wire_to_op = {"web_search": "web.search"}
    mind.risk = {**mind.risk, "web_search": "read_only"}
    return mind, server, mind.decide(1, "Si busca Lumyra en internet")


def test_that_search_is_held_with_the_name_and_the_call_and_the_same_again_runs(tmp_path: Path, monkeypatch) -> None:
    _, server, result = _turn(tmp_path, monkeypatch)
    told = next(m["content"] for m in server.bodies[1]["messages"] if m["role"] == "tool")
    assert '"status": "not_run"' in told and 'web_search {\\"query\\":\\"Lumyra\\"}' in told
    assert result["kind"] == "action" and result["arguments"]["query"] == "trabajos universitarios"


def test_holding_that_search_is_an_aid_that_can_be_switched_off(tmp_path: Path, monkeypatch) -> None:
    _, server, result = _turn(tmp_path, monkeypatch, "answer_check")
    assert result["kind"] == "action" and len(server.bodies) == 1


CATALOG = {"web.search": "Search the internet.", "file.read": "Read a file. More.", "app.open": "Open an application."}


@pytest.mark.parametrize("answer, rule", [
    ("No puedo hacer eso. No tengo herramientas para abrir Steam, navegar por su tienda ni ver sus páginas.", "denial_lookup"),
    ("I can't publish apps on that store.", "denial_lookup"),
    ("No puedo leer el archivo notas.txt.", "denial"),  # an operation of the table does it: the rule of before
    ("Si no me dices cuál, no puedo buscarlo.", None),  # a condition
    ("No puedo hacerlo sin tu confirmación.", None),  # a limit of its own
    ("Claro, te cuento cómo se hace.", None),
])
def test_a_denial_with_no_call_tells_what_web_search_reaches(answer: str, rule: str | None) -> None:
    found = [f["rule"] for f in check(answer, "Indícame cómo publicar un juego", [], [], CATALOG)
             if f["rule"].startswith("denial")]
    assert found == ([rule] if rule else [])


def test_no_lookup_is_told_without_web_search_in_the_catalog() -> None:
    assert not check("No puedo hacer eso.", "x", [], [], {"app.open": "Open."})


def test_the_note_keeps_the_tools_once_and_the_answer_after_it_is_the_models(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first = "No tengo herramientas para abrir esa tienda."
    mind, server = _mind(tmp_path, [_say(first), _call("web_search", {"query": "como publicar"}), _say(first)])
    mind.configure({"capabilities": [
        {"name": "web.search", "description": "Search the web.", "risk": "read_only", "group": "web",
         "argumentsSchema": {"type": "object", "properties": {"query": {"type": "string"}}}}]})
    result = mind.decide(1, "Indícame cómo publicar un juego")
    assert result["kind"] == "action", "it may search"
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "Nota interna" in note and "web_search" in note and first[:20] in note


def _memory_none() -> dict:
    return _r("memory.recall", {"status": "failed", "error": "memory_none"}, {"scope": "exact", "selector": "Lumyra"})


def _not_on_this_pc() -> dict:
    return _r("game.installed.named", {"status": "completed", "observed": {
        "state": "no_steam_or_epic_manifest_with_that_name", "matchCount": 0, "games": []}}, {"title": "Lumyra"})


def _rules(answer: str, receipts: list[dict]) -> list[str]:
    return [f["rule"] for f in check(answer, "¿Sabes algo de Lumyra?", receipts, []) if f["rule"] == "empty_lookup"]


# Cosecha 04-11 F13, F35: a look at what BAXY keeps or what this PC has that found nothing says how far it reaches.
def test_a_look_that_found_nothing_of_the_persons_says_how_far_it_reaches() -> None:
    assert _rules("No tengo nada guardado de Lumyra.", [_memory_none()]) == ["empty_lookup"]
    assert _rules("No veo Lumyra instalado.", [_not_on_this_pc()]) == ["empty_lookup"]
    found = _r("memory.recall", {"status": "completed", "observed": {"records": [{"value": "x"}], "totalCount": 1}}, {})
    assert not _rules("Sí, me contaste que x.", [found])
    searched = _r("web.search", {"status": "completed", "observed": {"results": []}}, {"query": "Lumyra"})
    assert not _rules("No encontré nada.", [_memory_none(), searched])


def test_the_note_of_that_look_has_the_persons_words_and_keeps_the_tools(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    first = "No tengo nada guardado de Lumyra."
    mind, server = _mind(tmp_path, [_call("memory_recall", {"scope": "exact", "selector": "Lumyra"}), _say(first),
                                    _call("web_search", {"query": "Lumyra"})])
    mind.wire_to_op = {"memory_recall": "memory.recall", "web_search": "web.search"}
    mind.risk = {**mind.risk, "memory_recall": "read_only", "web_search": "read_only"}
    mind.decide(1, "¿Sabes algo de Lumyra?")
    result = mind.continue_turn(2, _memory_none()["observation"])
    assert result["kind"] == "action"
    note = server.bodies[-1]["messages"][-1]["content"]
    assert "«¿Sabes algo de Lumyra?»" in note and "Haz lo que la persona dijo" in note
