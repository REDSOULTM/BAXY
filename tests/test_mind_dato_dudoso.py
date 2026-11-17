"""Aid «unsure_fact» (DIAX3, F1 of the owner's use 2026-11-16): «quién es X?» of a cartoon was answered from memory
with a series and an author made up, its doubt at 1.0 (p(call) 0.000: the doubt reads whether to call, not whether the
words are known). The decision's own token probabilities say which figures and names the model chose among others nearly
as likely; such an answer is not said, the model writes a web_search itself and answers from it. Only the shape of a word
is read. The phrases here are made up."""
import json
import math
from pathlib import Path

from baxy_mind.mind import DATED_NOTE, unsure_fact_words

from test_mind_final import _call, _mind, _say


def _scored(pairs: list[tuple[str, float]]) -> dict:
    """A reply in words with each token's probability, as the decision reads them (logprobs)."""
    return {"choices": [{"message": {"content": "".join(token for token, _ in pairs)},
                         "logprobs": {"content": [{"token": token, "logprob": math.log(p)} for token, p in pairs]}}]}


_MADE_UP = [("Pan", 0.9), ("cracio", 0.95), (" es", 0.9), (" un", 0.8), (" grupo", 0.3), (" fundado", 0.7), (" en", 0.9),
            (" ", 0.9), ("1", 0.99), ("9", 0.99), ("8", 0.6), ("2", 0.12), (" por", 0.8), (" Jorge", 0.08), (" Pan", 0.7),
            ("cracio", 0.9), (".", 0.9)]
_KNOWN = [("Bob", 0.9), (" Esponja", 0.95), (" fue", 0.8), (" creado", 0.7), (" por", 0.9), (" Stephen", 0.85),
          (" Hill", 0.9), ("enburg", 0.99), (".", 0.9), (" Un", 0.05), (" clásico", 0.1), (".", 0.9)]


def _searching(tmp_path: Path, replies: list) -> tuple:
    """A mind whose catalog has web.search and system.status, as the product's (the aid needs a search to offer)."""
    mind, server = _mind(tmp_path, replies)
    mind.configure({"capabilities": [{"name": op, "description": "Does it.", "risk": "read_only"}
                                     for op in ("web.search", "system.status")]})
    return mind, server


def _trace(mind) -> list[dict]:
    return [json.loads(line) for line in mind.trace.read_text(encoding="utf-8").splitlines()]


def test_figures_and_names_written_unsure_are_the_words_and_a_sentence_start_is_not() -> None:
    assert unsure_fact_words(_scored(_MADE_UP)) == ["1982", "Jorge"]
    # «Un» opens a sentence and «clásico» has no capital: neither is shaped as a datum
    assert unsure_fact_words(_scored(_KNOWN)) == []
    assert unsure_fact_words(_say("Pancracio es un grupo de 1982.")) == []  # no probabilities, nothing read


def test_an_answer_with_unsure_data_is_not_said_and_the_model_writes_the_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _searching(tmp_path, [_scored(_MADE_UP)])
    fills: list[str] = []

    def fill_call(body, wire):
        fills.append(wire)
        return {"name": "web_search", "arguments": {"query": "pancracio"}, "timings": {}}

    server.fill_call = fill_call
    step = mind.decide(1, "Quien es pancracio?")
    assert step["kind"] == "action" and step["operation"] == "web.search" and fills == ["web_search"]
    assert step["arguments"] == {"query": "pancracio"} and len(server.bodies) == 1
    said = [m.get("content") for m in mind.conversation]
    assert not any("1982" in str(content) for content in said)
    assert [r["stage"] for r in _trace(mind)].count("turn.unsure") == 1


def test_without_a_fill_the_model_decides_again_with_the_note_and_its_answer_stands(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _searching(tmp_path, [_scored(_MADE_UP), _scored(_MADE_UP)])
    server.fill_call = lambda body, wire: None
    step = mind.decide(1, "Quien es pancracio?")
    assert step["kind"] == "conversation" and step["reply"].startswith("Pancracio es un grupo")
    assert server.bodies[-1]["messages"][-1]["content"] == DATED_NOTE and len(server.bodies) == 2
    assert DATED_NOTE not in [m.get("content") for m in mind.conversation]


def test_known_words_answers_after_a_call_and_the_aid_off_are_not_held(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _searching(tmp_path, [_scored(_KNOWN)])
    assert mind.decide(1, "¿quién es bob esponja?")["kind"] == "conversation" and len(server.bodies) == 1
    mind, server = _searching(tmp_path, [_call("system_status", {}), _scored(_MADE_UP)])
    mind.decide(2, "¿cómo está el PC?")
    assert mind.continue_turn(2, json.dumps({"status": "completed"}))["kind"] == "conversation"
    assert len(server.bodies) == 2
    monkeypatch.setenv("BAXY_AYUDAS", "none")
    mind, server = _searching(tmp_path, [_scored(_MADE_UP)])
    assert mind.decide(3, "Quien es pancracio?")["kind"] == "conversation" and len(server.bodies) == 1
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _mind(tmp_path, [_scored(_MADE_UP)])  # no web.search in the catalog: nothing to offer
    assert mind.decide(3, "Quien es pancracio?")["kind"] == "conversation" and len(server.bodies) == 1


def test_a_story_whose_unsure_names_are_not_the_persons_is_said_as_written(tmp_path: Path, monkeypatch) -> None:
    # DIAX3 control: «inventa un cuento de dos líneas sobre un perro astronauta» named its characters with p < 0.2
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    story = [("Un", 0.6), (" perro", 0.9), (" llamado", 0.7), (" Rocco", 0.06), (" voló", 0.4), (" a", 0.9),
             (" la", 0.9), (" Luna", 0.3), (" en", 0.8), (" ", 0.9), ("2", 0.1), ("0", 0.9), ("8", 0.15), ("0", 0.9), (".", 0.9)]
    assert unsure_fact_words(_scored(story)) == ["Rocco", "2080"]
    mind, server = _searching(tmp_path, [_scored(story)])
    server.fill_call = lambda body, wire: {"name": "web_search", "arguments": {"query": "perro"}, "timings": {}}
    step = mind.decide(1, "inventa un cuento de dos líneas sobre un perro astronauta")
    assert step["kind"] == "conversation" and "Rocco" in step["reply"] and len(server.bodies) == 1


def test_the_turn_goes_on_with_the_searchs_results_and_its_answer_is_said(tmp_path: Path, monkeypatch) -> None:
    # DIAX3 bench, 2026-11-16: the aid's mark took the turn's «unsure» key, the doubt's held call, and the continuation
    # with the search's results failed (TypeError: 'bool' object is not subscriptable)
    monkeypatch.delenv("BAXY_AYUDAS", raising=False)
    mind, server = _searching(tmp_path, [_scored(_MADE_UP), _say("Pancracio es un personaje de dibujos animados.")])
    server.fill_call = lambda body, wire: {"name": "web_search", "arguments": {"query": "pancracio"}, "timings": {}}
    assert mind.decide(1, "Quien es pancracio?")["operation"] == "web.search"
    results = {"status": "completed", "observed": {"results": [{"title": "Pancracio", "snippet": "dibujos animados"}]}}
    step = mind.continue_turn(1, json.dumps(results))
    assert step["kind"] == "conversation" and step["reply"] == "Pancracio es un personaje de dibujos animados."
