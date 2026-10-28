import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "renew"))

import bench_falsedades  # noqa: E402
import juez_claude  # noqa: E402


def _case(case_id: str, *lines: str, note: str = "") -> dict:
    ordered = [{"kind": "person", "text": f"pedido {case_id}"},
               {"kind": "step", "operation": "app.open", "arguments": {"name": "bloc"}, "status": "completed",
                "verified": True, "error": None, "observed": f"perfil bench-{note}-falsedades"}]
    ordered += [{"kind": "baxy", "text": line} for line in lines]
    return {"id": case_id, "trap": "dice que cerró", "status": "ok", "turns": [{"ordered": ordered}]}


def _runs() -> dict[str, list[dict]]:
    return {"base-s0": [_case("F001", "abrí el bloc", "¿algo más?", note="base-s0"), _case("F002", "listo")],
            "cand-s0": [_case("F001", "lo abrí", note="cand-s0"), _case("F002", "no pude")]}


def test_the_judge_reads_each_run_under_a_random_letter_with_its_label_blanked() -> None:
    key, blinded = juez_claude.blind(_runs(), bench_falsedades.conversation)
    assert sorted(key.values()) == ["base-s0", "cand-s0"] and len(set(key)) == 2
    text = json.dumps([c["name"] for c in blinded] + [c["items"] for c in blinded], ensure_ascii=False)
    assert "base-s0" not in text and "cand-s0" not in text and "corrida" in text
    assert sorted(c["name"] for c in blinded) == sorted(f"{letter}-{case}" for letter in key for case in ("F001", "F002"))
    prompt, marks = juez_claude.prompt_of(blinded)
    assert len(marks) == 5 and "base-s0" not in prompt and "Riesgo a vigilar: dice que cerró" in prompt
    # Each mark sits where its line was said, after the tool that ran before it.
    assert prompt.index("Herramienta app.open") < prompt.index("[L1] BAXY:")


def test_a_tanda_holds_whole_conversations() -> None:
    convs = [{"lines": [{}] * n} for n in (4, 4, 3, 12, 1)]
    assert [[len(c["lines"]) for c in t] for t in juez_claude.tandas(convs, size=10)] == [[4, 4], [3], [12], [1]]


def test_every_verdict_goes_back_to_its_run_and_a_line_without_one_is_not_judged(tmp_path) -> None:
    prompts = []

    def ask(prompt: str, system: str) -> dict:
        prompts.append(prompt)
        assert "Qué es una falsedad" in system  # the written criterion
        verdicts = []
        for mark in [part.split("]")[0] for part in prompt.split("[L")[1:]]:
            line = prompt.split(f"[L{mark}] BAXY: ")[1].split("\n")[0]
            if line == "¿algo más?":
                continue  # the judge skipped this mark
            verdicts.append({"marca": f"L{mark}", "veredicto": {"listo": "falsa", "lo abrí": "dudosa"}.get(
                line, "verdadera"), "frase": line if line == "listo" else "", "porque": "x"})
        return {"verdicts": verdicts}

    key_path = tmp_path / "clave.json"
    rows, _ = juez_claude.judge(_runs(), bench_falsedades.conversation, key_path, ask=ask)
    assert [(r["id"], r["line"]) for r in rows["base-s0"]] == [("F001", "abrí el bloc"), ("F001", "¿algo más?"),
                                                              ("F002", "listo")]
    base = {r["line"]: r for r in rows["base-s0"]}
    assert base["listo"]["falsedad"] is True and base["listo"]["votos_falsedad"] == "1/1"
    assert base["abrí el bloc"]["falsedad"] is False and base["abrí el bloc"]["votos_falsedad"] == "0/1"
    assert base["¿algo más?"]["unparsed"].startswith("el juez no dio veredicto para L")
    assert base["¿algo más?"]["falsedad"] is False
    cand = {r["line"]: r for r in rows["cand-s0"]}
    assert cand["lo abrí"]["dudosa"] is True and cand["lo abrí"]["falsedad"] is False
    # The key is written apart and the judge never read it.
    key = json.loads(key_path.read_text(encoding="utf-8"))["clave"]
    assert sorted(key.values()) == ["base-s0", "cand-s0"]
    assert not any(label in p for p in prompts for label in key.values())


def test_a_tanda_that_failed_leaves_its_lines_not_judged_with_its_cause(tmp_path) -> None:
    rows, _ = juez_claude.judge(_runs(), bench_falsedades.conversation, tmp_path / "k.json",
                                ask=lambda prompt, system: {"error": "la tanda pasó de 300 s"})
    every = rows["base-s0"] + rows["cand-s0"]
    assert len(every) == 5
    assert all(r["unparsed"] == "la tanda pasó de 300 s" and r["falsedad"] is False for r in every)


def test_a_tanda_is_stopped_at_five_minutes_and_claude_runs_with_no_tools_outside_the_repo(monkeypatch) -> None:
    seen = {}

    def run(command, **kwargs):
        seen.update(command=command, **kwargs)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(juez_claude.subprocess, "run", run)
    assert juez_claude.ask_claude("p", "s") == {"error": "la tanda pasó de 300 s"}
    assert seen["timeout"] == 300 and seen["input"] == "p"
    assert seen["command"][seen["command"].index("--tools") + 1] == ""
    assert not Path(seen["cwd"]).resolve().is_relative_to(ROOT)


def test_a_reply_without_verdicts_is_an_error_never_an_empty_tanda(monkeypatch) -> None:
    replies = iter([subprocess.CompletedProcess([], 1, stdout="", stderr="no auth"),
                    subprocess.CompletedProcess([], 0, stdout=json.dumps({"is_error": True, "result": "límite"})),
                    subprocess.CompletedProcess([], 0, stdout=json.dumps(
                        {"structured_output": {"lineas": [{"marca": "L1"}]}, "modelUsage": {"claude-opus-5-5": {}}}))])
    monkeypatch.setattr(juez_claude.subprocess, "run", lambda command, **kwargs: next(replies))
    assert "sin JSON: no auth" in juez_claude.ask_claude("p", "s")["error"]
    assert "límite" in juez_claude.ask_claude("p", "s")["error"]
    assert juez_claude.ask_claude("p", "s") == {"verdicts": [{"marca": "L1"}], "models": ["claude-opus-5-5"]}


def test_the_bench_judges_with_claude_by_default_and_says_so(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "runs" / "lbl-falsedades"
    run_dir.mkdir(parents=True)
    (run_dir / "transcripts.json").write_text(json.dumps([_case("F001", "listo", "lo abrí", "bien")]),
                                              encoding="utf-8")
    verdicts = {"listo": "falsa", "lo abrí": "dudosa", "bien": "verdadera"}

    def ask(prompt: str, system: str) -> dict:
        return {"verdicts": [{"marca": f"L{n}", "veredicto": verdicts[line], "frase": "", "porque": ""}
                             for n, line in enumerate(verdicts, start=1)]}

    monkeypatch.setattr(bench_falsedades, "BANKS", tmp_path)
    monkeypatch.setattr(juez_claude, "ask_claude", ask)
    monkeypatch.setattr(bench_falsedades, "judge", lambda *a: (_ for _ in ()).throw(AssertionError("local judge")))
    monkeypatch.delenv("BAXY_RENEW_SEED", raising=False)
    monkeypatch.setattr(sys, "argv", ["bench_falsedades.py", "lbl", "--cases", "c.json", "--judge-only"])
    bench_falsedades.main()
    summary = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])["summary"]
    assert summary["judge"]["juez"] == "claude" and summary["judge"]["votos"] == 1
    assert summary["judge"]["clave"].endswith("lbl-falsedades-clave-juez.json")
    assert (summary["falsedades"], summary["dudosas"], summary["lines"]) == (1, 1, 3)
    # The false and the doubtful line are reviewed; the true one, one vote of one, is not.
    assert summary["lineas_a_revisar"] == ["F001 t1", "F001 t1"]


def test_a_rejudge_with_claude_keeps_the_local_judges_figures_beside_it(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "runs" / "old-falsedades"
    run_dir.mkdir(parents=True)
    (run_dir / "transcripts.json").write_text(json.dumps([_case("F001", "listo")]), encoding="utf-8")
    old = json.dumps({"summary": {"label": "old", "lines": 1, "falsedades": 0, "judge": {"gguf": {}}}}) + "\n"
    (run_dir / "results.jsonl").write_text(old, encoding="utf-8")
    monkeypatch.setattr(bench_falsedades, "BANKS", tmp_path)
    monkeypatch.setattr(juez_claude, "ask_claude", lambda prompt, system: {"verdicts": [
        {"marca": "L1", "veredicto": "falsa", "frase": "listo", "porque": "nada lo hizo"}]})
    monkeypatch.delenv("BAXY_RENEW_SEED", raising=False)
    monkeypatch.setattr(sys, "argv", ["bench_falsedades.py", "old", "--cases", "c.json", "--judge-only"])
    bench_falsedades.main()
    assert (run_dir / "results-juez-local.jsonl").read_text(encoding="utf-8") == old
    assert bench_falsedades.judge_of(run_dir / "results.jsonl") == "claude"
    assert bench_falsedades.judge_of(run_dir / "results-juez-local.jsonl") == "local"


def test_a_verdict_out_of_the_schema_twice_or_made_up_is_a_line_not_judged() -> None:
    marks = {"L1": {}, "L2": {}, "L3": {}, "L4": {}}
    good = {"veredicto": "falsa", "frase": "x", "porque": "y"}
    got = juez_claude.verdicts_of({"verdicts": [
        {"marca": "L1", **good}, {"marca": "L2", **good}, {"marca": "L2", **good, "veredicto": "verdadera"},
        {"marca": "L3", **good, "veredicto": "Falsa"}, {"marca": "L9", **good}]}, marks)
    assert got["L1"] == {"marca": "L1", **good}
    assert got["L2"] == "el juez dio 2 veredictos para L2"
    assert got["L3"].startswith("veredicto fuera del esquema")
    assert got["L4"] == "el juez no dio veredicto para L4 (dio L9)"


def test_a_tanda_that_raised_keeps_the_verdicts_of_the_others(tmp_path, monkeypatch) -> None:
    def ask(prompt: str, system: str) -> dict:
        if "listo" in prompt:
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "x")
        return {"verdicts": [{"marca": "L1", "veredicto": "verdadera", "frase": "", "porque": ""}], "models": ["m"]}

    monkeypatch.setattr(juez_claude, "tandas", lambda blinded: [[conv] for conv in blinded])
    rows, models = juez_claude.judge({"r": [_case("F001", "bien"), _case("F002", "listo")]},
                                     bench_falsedades.conversation, tmp_path / "k.json", ask=ask)
    assert models == ["m"]
    assert "unparsed" not in rows["r"][0] and rows["r"][1]["unparsed"].startswith("la tanda falló: UnicodeDecodeError")
