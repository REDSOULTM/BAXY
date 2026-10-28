"""scripts/renew/juez_ciego.py: an e2e run turned into blind batches for Claude judges and their verdicts joined back."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import juez_ciego  # noqa: E402


def _bank(tmp_path: Path, n: int, criterio: bool = True) -> Path:
    path = tmp_path / "bank.json"
    path.write_text(json.dumps([{"id": f"C{i}", "turns": [{"text": f"pedido {i}", "reply_if_confirmation": "no"}],
                                 **({"criterio": f"criterio {i}"} if criterio else {})} for i in range(n)]),
                    encoding="utf-8")
    return path


def _run(tmp_path: Path, statuses: list[str]) -> Path:
    path = tmp_path / "results.jsonl"
    rows = [{"summary": {"ok": 0, "n": len(statuses)}}] + [
        {"id": f"C{i}", "ok": False, "status": status, "steps": [{"op": "app.open", "status": "completed",
                                                                  "verified": True}],
         "replies": [{"turn": 1, "text": f"respuesta {i}"}]} for i, status in enumerate(statuses)]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def _judge(out: Path, verdict) -> None:
    for prompt in sorted(out.glob("tanda_*.md")):
        text = prompt.read_text(encoding="utf-8")
        items = json.loads(text.split("```json\n")[1].split("\n```")[0])
        (out / prompt.name.replace("tanda_", "veredictos_").replace(".md", ".json")).write_text(
            json.dumps({item["codigo"]: verdict(item) for item in items}), encoding="utf-8")


def test_batches_hide_ids_and_join_back_every_case(tmp_path):
    out = tmp_path / "juez"
    written = juez_ciego.paquetes(_bank(tmp_path, 7), [_run(tmp_path, ["fallo"] * 6 + ["ok"])], 3, out, 1)
    assert [p.name for p in written] == ["tanda_01.md", "tanda_02.md", "tanda_03.md"]
    for prompt in written:
        assert '"C' not in prompt.read_text(encoding="utf-8")  # no judge sees a case id
    _judge(out, lambda item: {"cumple": item["pedido"][0]["dice"] != "pedido 2", "motivo": "x"})
    summary = juez_ciego.juntar(out)
    assert (summary["ok"], summary["n"]) == (6, 7)
    rows = json.loads((out / "resultado.json").read_text(encoding="utf-8"))["casos"]
    assert [r["id"] for r in rows if not r["ok"]] == ["C2"]


def test_a_case_whose_turns_never_ran_is_not_judged(tmp_path):
    out = tmp_path / "juez"
    juez_ciego.paquetes(_bank(tmp_path, 3), [_run(tmp_path, ["fallo", "void", "setup_fallido"])], 6, out, 1)
    _judge(out, lambda item: {"cumple": True, "motivo": "x"})
    summary = juez_ciego.juntar(out)
    assert summary["n"] == 1
    assert [x["id"] for x in summary["no_juzgados"]] == ["C1", "C2"]


def test_a_bank_without_criterio_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="no criterio"):
        juez_ciego.paquetes(_bank(tmp_path, 2, criterio=False), [_run(tmp_path, ["fallo"] * 2)], 6,
                            tmp_path / "juez", 1)


def test_join_refuses_a_missing_or_partial_or_malformed_batch(tmp_path):
    out = tmp_path / "juez"
    juez_ciego.paquetes(_bank(tmp_path, 4), [_run(tmp_path, ["fallo"] * 4)], 2, out, 1)
    with pytest.raises(SystemExit, match="was not judged"):
        juez_ciego.juntar(out)
    _judge(out, lambda item: {"cumple": "sí"})
    with pytest.raises(SystemExit, match="no yes or no"):
        juez_ciego.juntar(out)
    first = out / "veredictos_01.json"
    verdicts = json.loads(first.read_text(encoding="utf-8"))
    first.write_text(json.dumps(dict(list(verdicts.items())[:1])), encoding="utf-8")
    with pytest.raises(SystemExit, match="unjudged"):
        juez_ciego.juntar(out)


def test_a_used_folder_is_refused_and_the_key_stays_out_of_it(tmp_path):
    out = tmp_path / "juez"
    juez_ciego.paquetes(_bank(tmp_path, 2), [_run(tmp_path, ["fallo"] * 2)], 6, out, 1)
    assert not list(out.glob("clave*")) and (tmp_path / "juez.clave.json").exists()
    with pytest.raises(SystemExit, match="already exists"):
        juez_ciego.paquetes(_bank(tmp_path, 2), [_run(tmp_path, ["fallo"] * 2)], 6, out, 2)


def test_a_case_of_two_runs_never_shares_a_batch_with_itself(tmp_path):
    bank = _bank(tmp_path, 3)
    base = _run(tmp_path, ["fallo"] * 3)
    cand = tmp_path / "cand.jsonl"
    cand.write_text(base.read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "juez"
    for prompt in juez_ciego.paquetes(bank, [base, cand], 4, out, 3):
        items = json.loads(prompt.read_text(encoding="utf-8").split("```json\n")[1].split("\n```")[0])
        pedidos = [item["pedido"][0]["dice"] for item in items]
        assert len(pedidos) == len(set(pedidos))
    _judge(out, lambda item: {"cumple": True, "motivo": "x"})
    summary = juez_ciego.juntar(out)
    assert summary["n"] == 6 and {v["n"] for v in summary["por_corrida"].values()} == {3}


def test_a_void_run_is_listed_and_a_short_run_refused(tmp_path):
    void = tmp_path / "void.jsonl"
    void.write_text(json.dumps({"summary": {"void": "ventana del dueño", "ok": 0, "n": 2}}) + "\n", encoding="utf-8")
    out = tmp_path / "juez"
    juez_ciego.paquetes(_bank(tmp_path, 2), [void, _run(tmp_path, ["fallo"] * 2)], 6, out, 1)
    key = json.loads((tmp_path / "juez.clave.json").read_text(encoding="utf-8"))
    assert key["no_juzgados"] == [{"run": str(void), "status": "void", "motivo": "ventana del dueño"}]
    short = tmp_path / "short.jsonl"
    short.write_text("\n".join((_run(tmp_path, ["fallo"] * 2).read_text(encoding="utf-8").splitlines())[:2]),
                     encoding="utf-8")
    with pytest.raises(SystemExit, match="summary says n=2"):
        juez_ciego.paquetes(_bank(tmp_path, 2), [short], 6, tmp_path / "otro", 1)


def test_the_judge_sees_a_confirmation_asked(tmp_path):
    run = tmp_path / "results.jsonl"
    run.write_text("\n".join(json.dumps(r) for r in [{"summary": {"n": 1}}, {
        "id": "C0", "status": "fallo", "steps": [], "replies": [
            {"turn": 1, "text": "", "asked_confirmation": True, "confirmation_text": "¿Lo cierro?", "answered": None}]}]),
        encoding="utf-8")
    [prompt] = juez_ciego.paquetes(_bank(tmp_path, 1), [run], 6, tmp_path / "juez", 1)
    [item] = json.loads(prompt.read_text(encoding="utf-8").split("```json\n")[1].split("\n```")[0])
    assert item["respuestas"][0]["pidio_confirmacion"] is True
    assert item["respuestas"][0]["pregunta"] == "¿Lo cierro?"
