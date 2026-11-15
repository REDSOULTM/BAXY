"""Aid «exit_unnamed», R4A (c129-R4: after «No pude cerrar Velmora», «ya, una vez más» went to baxy_exit 9 of 10 seeds with
ver3b in Esencial and 12 of 30 with pan6 in Completo; in Bypass it closes BAXY with no «sí»). Only the form is compared,
as «said_place» compares a location: neither the person's words of this turn nor those of their turn before name BAXY
(its name as the ear writes it, routines.NAMES, anywhere in them). Nothing closes; the result says
so, as data, and the model decides again, once per turn: the same call again runs as written."""
import json
from pathlib import Path

from test_mind_final import _call, _mind, _say

FAILED = [{"role": "user", "content": "Cierra Velmora"},
          {"role": "assistant", "content": "No pude cerrar Velmora: quedó abierto en segundo plano."}]


def _not_run(mind) -> list[dict]:
    told = []
    for message in mind.conversation:
        if message["role"] == "tool" and str(message.get("content")).startswith("{"):
            body = json.loads(str(message["content"]).split("\n", 1)[0])
            if body.get("status") == "not_run":
                told.append(body)
    return told


def test_closing_baxy_nobody_named_goes_back_and_the_model_decides_again(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("baxy_exit", {}), _call("app_close", {"appId": "Velmora"})])
    mind.new_session(FAILED)
    step = mind.decide(1, "ya, una vez más")
    assert step["kind"] == "action" and step["operation"] == "app_close"
    told = _not_run(mind)
    assert len(told) == 1 and told[0]["error"] == "baxy_not_named"
    assert told[0]["theirWordsBefore"] == "Cierra Velmora"
    assert "no se ejecutó" in next(m["content"] for m in mind.conversation if m["role"] == "tool")


def test_it_is_told_once_and_the_same_call_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("baxy_exit", {}), _call("baxy_exit", {})])
    assert mind.decide(1, "ciérrate")["operation"] == "baxy_exit"
    assert len(_not_run(mind)) == 1


def test_baxy_named_in_the_words_closes_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    for said in ("cierra BAXY", "Baxi, cierra baxi por hoy", "quit Baxy", "apaga a baxi, porfa"):
        mind, _ = _mind(tmp_path, [_call("baxy_exit", {})])
        assert mind.decide(1, said)["operation"] == "baxy_exit", said
        assert _not_run(mind) == [], said


def test_baxy_named_in_their_turn_before_closes_it(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_say("¿Seguro?"), _call("baxy_exit", {})])
    mind.decide(1, "quiero cerrar BAXY")
    assert mind.decide(2, "sí, dale")["operation"] == "baxy_exit"
    assert _not_run(mind) == []


def test_the_name_said_first_names_it_too(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, _ = _mind(tmp_path, [_call("baxy_exit", {})])
    assert mind.decide(1, "Baxi, ciérrate")["operation"] == "baxy_exit"
    assert _not_run(mind) == []


def test_without_the_aid_it_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, _ = _mind(tmp_path, [_call("baxy_exit", {})])
    mind.new_session(FAILED)
    assert mind.decide(1, "ya, una vez más")["operation"] == "baxy_exit"
