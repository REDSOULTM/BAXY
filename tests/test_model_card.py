"""MODX2: the decision's sampling, reasoning and doubt come from the model's card (model_card.py), the entry of a table
that matches what the model file declares of itself; the stock model's card keeps exactly what the mind always sent,
and a model no entry matches, or whose file is not read, too."""
import json
from pathlib import Path

from baxy_mind import model_card
from plantillas_llamada import gemma4, qwen35
from test_mind_final import _say
from test_mind_otro_formato import TemplateServer
from baxy_mind.mind import Mind

QWEN35 = {"general.architecture": "qwen35", "general.size_label": "4B", "general.basename": "Qwen3.5-4B"}
GEMMA4 = {"general.architecture": "gemma4", "general.size_label": "12B", "general.sampling.temp": 1.0}


def _started(tmp_path: Path, replies: list, render, single: str, declared: dict) -> tuple[Mind, TemplateServer]:
    server = TemplateServer(replies, render, single)
    server.declared = declared
    mind = Mind(server, tmp_path / "turns.jsonl")  # type: ignore[arg-type]
    mind.warm()
    return mind, server


def _own(tmp_path: Path, monkeypatch, entries: list) -> None:
    path = tmp_path / "cards.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setenv("BAXY_MODEL_CARDS", str(path))


def test_the_stock_models_card_sends_what_the_mind_always_sent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("BAXY_MODEL_CARDS", raising=False)
    assert model_card.card_for(QWEN35).name == "qwen3.5" and model_card.card_for(QWEN35).decide == {}
    mind, server = _started(tmp_path, [_say("Hola.")], qwen35, "<tool_call>", QWEN35)
    mind.decide(1, "hola")
    body = server.bodies[-1]
    keys = list(body)
    assert keys[keys.index("temperature"):keys.index("seed") + 1] == ["temperature", "top_p", "top_k", "min_p", "seed"]
    assert (body["temperature"], body["top_p"], body["top_k"], body["min_p"]) == (0.2, 0.8, 20, 0.0)
    assert body["chat_template_kwargs"] == {"enable_thinking": False} and "thinking_budget_tokens" not in body
    assert not (tmp_path / "turns.jsonl").exists() or "warm.card" not in (tmp_path / "turns.jsonl").read_text("utf-8")


def test_a_model_no_entry_matches_or_whose_file_is_not_read_keeps_what_the_mind_sent(tmp_path: Path,
                                                                                    monkeypatch) -> None:
    monkeypatch.delenv("BAXY_MODEL_CARDS", raising=False)
    assert model_card.card_for({}) == model_card.NONE
    assert model_card.card_for({"general.architecture": "unheard-of"}) == model_card.NONE
    mind, server = _started(tmp_path, [_say("Hola.")], gemma4, "<|tool_call>", {})
    mind.decide(1, "hola")
    body = server.bodies[-1]
    assert body["temperature"] == 0.2 and "top_k" not in body and "top_p" not in body


def test_an_entry_of_a_persons_own_table_sets_the_decisions_sampling_reasoning_and_doubt(tmp_path: Path,
                                                                                         monkeypatch) -> None:
    _own(tmp_path, monkeypatch, [{"name": "gemma4-12b", "match": {"general.architecture": "gemma4",
                                                                  "general.size_label": ["12B", "E4B"]},
                                  "decide": {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "bogus": 3},
                                  "thinking_budget": 256, "doubt": 0.25, "source": "ficha"}])
    card = model_card.card_for(GEMMA4)
    assert card.decide == {"temperature": 1.0, "top_p": 0.95, "top_k": 64} and card.doubt == 0.25
    mind, server = _started(tmp_path, [_say("Hola.")], gemma4, "<|tool_call>", GEMMA4)
    assert mind._doubt_threshold() == 0.25
    mind.decide(1, "hola")
    body = server.bodies[-1]
    assert (body["temperature"], body["top_p"], body["top_k"]) == (1.0, 0.95, 64)
    assert body["chat_template_kwargs"] == {"enable_thinking": True} and body["thinking_budget_tokens"] == 256
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text("utf-8").splitlines()]
    [row] = [r for r in rows if r["stage"] == "warm.card"]
    assert row["card"] == "gemma4-12b" and row["thinking_budget"] == 256
    # A bench's arm still moves the temperature and the doubt with its variables.
    monkeypatch.setenv("BAXY_S1_DOUBT", "0")
    assert mind._doubt_threshold() == 0.0
    # A model that reasons first is not held by a doubt read from its thinking's first tokens.
    assert not mind._doubted("turn.decide", {}, False)


def test_the_shipped_table_matches_by_declared_keys_only() -> None:
    table = json.loads(model_card.TABLE.read_text(encoding="utf-8"))
    for entry in table["cards"]:
        assert entry["match"] and all(key.startswith("general.") for key in entry["match"])
        assert set(entry.get("decide") or {}) <= set(model_card.SAMPLING)
        assert entry["source"]


def test_a_familys_name_fits_by_its_beginning_and_nothing_else_does(tmp_path: Path, monkeypatch) -> None:
    _own(tmp_path, monkeypatch, [{"name": "llama3", "match": {"general.architecture": "llama",
                                                              "general.basename": "Llama-3*"},
                                  "decide": {"temperature": 0.6, "top_p": 0.9}, "source": "x"}])
    llama32 = {"general.architecture": "llama", "general.basename": "Llama-3.2-3B-Instruct"}
    assert model_card.card_for(llama32).name == "llama3"
    assert model_card.card_for({**llama32, "general.basename": "SmolLM2-1.7B"}).name != "llama3"
    assert model_card.card_for({"general.architecture": "llama"}).name != "llama3"  # no name declared: no fit


def test_the_shipped_table_decides_granite_greedy_and_leaves_every_other_family_as_it_was(monkeypatch) -> None:
    # MODX2, measured: greedy raised granite-4.2-3b on the fixed gate and the held-out with no more falsehoods or actions
    # not asked for; every maker's own sampling lowered or did not raise the others (the table's sources).
    monkeypatch.delenv("BAXY_MODEL_CARDS", raising=False)
    assert model_card.card_for({"general.architecture": "granite", "general.size_label": "3B"}).decide == {
        "temperature": 0.0}
    for architecture in ("qwen35", "gemma4", "llama", "mistral3"):
        card = model_card.card_for({"general.architecture": architecture, "general.basename": "Llama-3.2-3B"})
        assert card.decide == {} and card.thinking_budget == 0 and card.doubt is None
