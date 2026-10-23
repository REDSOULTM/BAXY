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
