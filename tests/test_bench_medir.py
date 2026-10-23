"""Audit of the measuring tools (w8-medir, 2026-10-23): what a run records about itself, with doubles (no product, no
model server)."""
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import run_meta  # noqa: E402


def test_a_files_hash_is_kept_by_path_size_and_time(tmp_path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"x" * 1000)
    cache = tmp_path / "cache.json"
    first = run_meta.sha256_file(model, cache)
    assert first == run_meta.sha256_file(model) and len(first) == 64
    assert list(json.loads(cache.read_text(encoding="utf-8")).values()) == [first]
    assert run_meta.fingerprint(model, cache) == {"path": str(model), "bytes": 1000, "sha256": first}
    assert run_meta.fingerprint(tmp_path / "missing.gguf") == {"path": str(tmp_path / "missing.gguf"), "bytes": None,
                                                               "sha256": None}
    assert run_meta.fingerprint(None) is None


def test_the_minds_hash_is_the_same_for_a_copy_and_changes_with_its_code(tmp_path) -> None:
    mind = tmp_path / "a" / "baxy_mind"
    (mind / "data").mkdir(parents=True)
    (mind / "mind.py").write_text("SEED = 0\n", encoding="utf-8")
    (mind / "data" / "english.json").write_text("{}", encoding="utf-8")
    (mind / "__pycache__").mkdir()
    (mind / "__pycache__" / "mind.py").write_text("compiled", encoding="utf-8")
    copy = tmp_path / "b" / "baxy_mind"
    shutil.copytree(mind, copy, ignore=shutil.ignore_patterns("__pycache__"))
    assert run_meta.tree_sha256(mind) == run_meta.tree_sha256(copy)
    (copy / "mind.py").write_text("SEED = 1\n", encoding="utf-8")
    assert run_meta.tree_sha256(mind) != run_meta.tree_sha256(copy)
    assert run_meta.tree_sha256(tmp_path / "none") is None
    assert run_meta.git_state(tmp_path) is None  # a copy without git says so


def test_the_confirmation_mode_is_read_where_the_mind_reads_it(tmp_path) -> None:
    owner = tmp_path / "local"
    (owner / "BAXY" / "1").mkdir(parents=True)
    (owner / "BAXY" / "1" / "confirmation-mode").write_text("﻿Bypass\n", encoding="utf-8")
    assert run_meta.confirmation_mode({"LOCALAPPDATA": str(owner)}) == "bypass"
    bench = tmp_path / "bench"
    assert run_meta.confirmation_mode({"LOCALAPPDATA": str(owner), "BAXY_DATA_DIR": str(bench)}) == "normal"
    bench.mkdir()
    (bench / "confirmation-mode").write_text("all", encoding="utf-8")
    assert run_meta.confirmation_mode({"BAXY_DATA_DIR": str(bench)}) == "bypass"


def test_every_baxy_switch_is_recorded_and_nothing_else() -> None:
    seen = run_meta.baxy_env({"BAXY_AYUDAS": "none", "BAXY_S1_VETO": "0.6", "PATH": "x", "baxy_renew_kv": "f16"})
    assert seen == {"BAXY_AYUDAS": "none", "BAXY_S1_VETO": "0.6", "baxy_renew_kv": "f16"}


def test_a_decision_run_says_what_it_measured(tmp_path, monkeypatch) -> None:
    import bench_decision
    catalog, gguf, server = tmp_path / "catalog.json", tmp_path / "qwen.gguf", tmp_path / "llama-server.exe"
    catalog.write_text('{"capabilities": []}', encoding="utf-8")
    gguf.write_bytes(b"gguf")
    server.write_bytes(b"exe")
    laya = tmp_path / "layam.gguf"
    laya.write_bytes(b"laya")
    src = tmp_path / "src"
    (src / "baxy_mind").mkdir(parents=True)
    (src / "baxy_mind" / "mind.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(run_meta, "_cache_path", lambda: None)
    args = SimpleNamespace(src=str(src), catalog=str(catalog), gguf=str(gguf), server=str(server), server_args="-t 4",
                           ctx="53248", temp="0.2")
    environ = {"BAXY_DATA_DIR": str(tmp_path / "datos"), "BAXY_S1_GGUF": str(laya), "BAXY_S1_DOUBT": "0.4"}
    monkeypatch.setenv("BAXY_S1_GGUF", str(laya))
    record = bench_decision.run_record(args, SimpleNamespace(kv=("q8_0", "q8_0")), SimpleNamespace(seed=2), environ)
    assert record["catalog"]["sha256"] == run_meta.sha256_file(catalog)
    assert record["gguf"]["bytes"] == 4 and record["server"]["sha256"] == run_meta.sha256_file(server)
    assert record["s1_gguf"]["sha256"] == run_meta.sha256_file(laya)
    assert record["kv"] == ["q8_0", "q8_0"] and record["ctx"] == 53248 and record["seed"] == 2 and record["temp"] == 0.2
    assert record["mind_sha256"] == run_meta.tree_sha256(src / "baxy_mind")
    assert record["judge_sha256"] == run_meta.sha256_file(Path(bench_decision.__file__))
    assert record["confirmation_mode"] == "normal"
    assert record["env"] == {"BAXY_DATA_DIR": str(tmp_path / "datos"), "BAXY_S1_DOUBT": "0.4",
                             "BAXY_S1_GGUF": str(laya)}


class FakeLaya:
    """System One's server: answers, or not (down, slower than choose's timeout)."""

    def __init__(self, answers, ready=True, exit_code=None):
        self.answers, self.ready = list(answers), ready
        self._process = SimpleNamespace(poll=lambda: exit_code, returncode=exit_code)

    def choose(self, text, history, options, timeout=2.0):
        return self.answers.pop(0)


def test_system_one_counts_what_it_was_asked_and_what_never_came_back() -> None:
    import bench_decision
    laya = bench_decision.CountedSystemOne(FakeLaya([{"choice": "a"}, None, None]))
    two = {"a": "abrir", "b": "cerrar"}
    assert laya.choose("abre", [], two) == {"choice": "a"} and laya.case == "answered"
    laya.case = None
    assert laya.choose("cierra", [], two) is None and laya.case == "unanswered"
    assert laya.choose("cierra", [], {"a": "solo una"}) is None  # one option: the mind does not ask (not counted)
    assert (laya.asked, laya.unanswered, laya.ready) == (2, 1, True)


def test_a_run_with_system_one_waits_for_it_and_stops_when_it_died() -> None:
    import pytest

    import bench_decision
    bench_decision.wait_system_one(FakeLaya([], ready=True), timeout=1)
    with pytest.raises(SystemExit, match="exited"):
        bench_decision.wait_system_one(FakeLaya([], ready=False, exit_code=3), timeout=1, poll=0.01)
    with pytest.raises(SystemExit, match="not up"):
        bench_decision.wait_system_one(FakeLaya([], ready=False), timeout=0.05, poll=0.01)


def _run(folder: Path, name: str, rows: list[dict]) -> Path:
    path = folder / name
    path.write_text("\n".join(json.dumps(r) for r in [{"summary": {}}] + rows) + "\n", encoding="utf-8")
    return path


def test_pareado_leaves_out_e2e_cases_that_never_ran_and_names_server_errors(tmp_path) -> None:
    import pareado
    errors: dict = {}
    run = _run(tmp_path, "e2e.jsonl", [
        {"id": "E1", "ok": True, "status": "ok"}, {"id": "E2", "ok": False, "status": "setup_fallido"},
        {"id": "E3", "ok": False, "status": "void"}, {"id": "E4", "ok": False, "status": "sesion_bloqueada"},
        {"id": "E5", "ok": False, "status": "fallo"}, {"id": "P1", "ok": False, "error": "HTTP 500"}])
    assert pareado.rows(run, "ok", errors) == {"E1": True, "E5": False, "P1": False}
    assert errors == {str(run): 1}


def test_pareado_counts_wrong_actions_as_its_secondary_metric(tmp_path) -> None:
    import pareado
    run = _run(tmp_path, "d.jsonl", [
        {"id": "P1", "ok": False, "kind": "action"}, {"id": "P2", "ok": True, "kind": "action"},
        {"id": "P3", "ok": False, "kind": "clarify"}, {"id": "P4", "ok": False, "kind": "action", "excluded": True}])
    assert pareado.rows(run, "wrong_action") == {"P1": True, "P2": False, "P3": False}


def test_pareado_clusters_dictation_twins_with_their_clean_case() -> None:
    import pareado
    cluster_of = pareado.clusters([{"id": "D1"}, {"id": "D2", "twin": "D1"}, {"id": "D3"}, {"id": "D4"}])
    assert cluster_of == {"D1": "D1", "D2": "D1", "D3": "D3", "D4": "D4"}
    reference = [{"D1": False, "D2": False, "D3": True, "D4": True}]
    arm = [{"D1": True, "D2": True, "D3": True, "D4": False}]
    result = pareado.compare(reference, arm, set(), cluster_of)
    assert result["delta"] == 1 and result["clusters"] == 3
    # Pair sums +2, 0, -1: SE = sqrt(3/2 · ((2-1/3)² + (0-1/3)² + (-1-1/3)²)) = sqrt(7) ≈ 2.65.
    assert result["delta_se_twins"] == 2.65
    assert result["delta_ci95_twins"][0] <= 1 <= result["delta_ci95_twins"][1]
    assert "clusters" not in pareado.compare(reference, arm, set(), None)


def test_the_benchs_product_writes_its_mind_trace_in_the_run(tmp_path, monkeypatch) -> None:
    import bench_e2e
    started = {}

    def popen(command, **options):
        started.update(options)
        return SimpleNamespace()

    monkeypatch.setattr(bench_e2e.subprocess, "Popen", popen)
    monkeypatch.setattr(bench_e2e, "set_aside_notepad_tabs", lambda backup: 0)
    conductor = bench_e2e.Conductor(tmp_path, tmp_path / "perfil")
    assert started["env"]["BAXY_RENEW_TRACE_DIR"] == str(tmp_path / "mente") == str(conductor.mind_dir)
    started["stdout"].close()


def test_system_one_of_an_e2e_arm_is_what_the_launcher_and_the_owners_switch_decide(tmp_path) -> None:
    local = tmp_path / "local"
    (local / "BAXY" / "renew").mkdir(parents=True)
    on = run_meta.system_one_setting({"LOCALAPPDATA": str(local)})
    assert on["on"] and not on["off_file"] and on["setting"]["BAXY_S1_VETO"] == "0.6"
    (local / "BAXY" / "renew" / "system_one.off").write_text("", encoding="utf-8")
    off = run_meta.system_one_setting({"LOCALAPPDATA": str(local)})
    assert off == {"off_file": True, "on": False, "setting": {}}
    # With the owner's switch off, only what the bench itself carries turns it on.
    given = run_meta.system_one_setting({"LOCALAPPDATA": str(local), "BAXY_S1_GGUF": "laya.gguf"})
    assert given["on"] and given["setting"] == {"BAXY_S1_GGUF": "laya.gguf"}


def test_a_product_run_records_its_catalog_seed_and_whether_system_one_started(tmp_path) -> None:
    import time
    local, run = tmp_path / "local", tmp_path / "run"
    (local / "BAXY" / "renew").mkdir(parents=True)
    (run / "mente").mkdir(parents=True)
    (run / "mente" / "catalog.configure.json").write_text("{}", encoding="utf-8")
    started = time.time() - 5
    (local / "BAXY" / "renew" / "system-one.log").write_text("", encoding="utf-8")
    record = run_meta.product_record(tmp_path, run, started, {"LOCALAPPDATA": str(local), "BAXY_RENEW_SEED": "1"})
    assert record["seed"] == "1" and record["catalog"]["sha256"] == run_meta.sha256_file(run / "mente" / "catalog.configure.json")
    assert record["system_one"]["on"] and record["system_one"]["server_started"]
    later = run_meta.product_record(tmp_path, run, time.time() + 60, {"LOCALAPPDATA": str(local)})
    assert later["seed"] == "0 (default)" and not later["system_one"]["server_started"]


def test_an_e2e_score_leaves_out_cases_that_never_ran_and_says_when_the_owners_files_changed() -> None:
    import bench_e2e
    rows = [{"id": "E1", "ok": True, "status": "ok", "profile": {"changed": [r"C:\Users\x\config.ini"]}},
            {"id": "E2", "ok": False, "status": "setup_fallido"}, {"id": "E3", "ok": False, "status": "fallo"}]
    assert bench_e2e.scored(rows) == {"n_scored": 2, "accuracy_scored": 0.5}
    summary = bench_e2e.profile_summary(rows)
    assert summary["contaminated"] and summary["profile_review"] == [r"E1: C:\Users\x\config.ini"]
    assert not bench_e2e.profile_summary(rows[1:])["contaminated"]


def test_the_falsehood_judge_sees_every_field_of_a_long_observation() -> None:
    # A partial read: its content is long, and what says it was partial comes after it.
    import bench_falsedades
    read = json.dumps({"status": "completed", "observed": {"content": "línea\n" * 900, "linesRead": 1904,
                                                           "totalLines": 3000, "truncated": True}})
    assert '"truncated": true' not in read[:1500]  # what the judge read before the audit
    line = bench_falsedades.step_line({"operation": "file.read", "arguments": {"name": "log.txt"},
                                       "status": "completed", "verified": True, "error": None, "observed": read})
    assert '"linesRead":1904' in line and '"truncated":true' in line and "caracteres más" in line
    listing = json.dumps({"entries": [f"archivo{i}.txt" for i in range(200)], "total": 200})
    shown = bench_falsedades.observed_for_judge(listing)
    assert "182 elementos más" in shown and '"total":200' in shown and "archivo199.txt" in shown
    plain = "a" * 1000 + "FIN"
    assert bench_falsedades.observed_for_judge(plain * 3).endswith("FIN")
    assert bench_falsedades.observed_for_judge("corto") == "corto"


def test_the_transcript_keeps_the_whole_observation_for_the_reading_by_hand() -> None:
    import bench_falsedades
    event = {"operation": "file.read", "arguments": {}, "status": "completed", "verified": True,
             "observation": "x" * 5000}
    assert len(bench_falsedades.step_of(event)["observed"]) == 5000
