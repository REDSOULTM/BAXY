"""Arguments-only measure: the turns of a set whose decision the run got right and that carry gold arguments; the
mind's arguments step on the run's objective and the turn's history, as comprension_eval does.
usage: args_eval.py GGUF CTX RUN SET OUT"""
import json, os, pathlib, sys
REPO = pathlib.Path(r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo")
sys.path.insert(0, str(REPO / "scripts"))
import comprension_eval as ce  # noqa: E402
import run_turn_policy_gate as gate  # noqa: E402
gguf, ctx, run_path, set_path, out = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], pathlib.Path(sys.argv[5])
rows = [json.loads(line) for line in open(set_path, encoding="utf-8")]
run = {r["id"]: r for r in map(json.loads, open(run_path, encoding="utf-8"))}
manifest = gate.read_runtime_manifest(pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime" / "mind-runtime-v1.json")
configuration = gate.core_catalog_configuration(gate.DEFAULT_CORE)
right = total = 0
with gate.MindClient(configuration["capabilities"], application_catalog=configuration["applicationCatalog"],
                     game_catalog=configuration["gameCatalog"], gguf=gguf,
                     llama_server=pathlib.Path(manifest["llama_server"]), ngl=99, endpoint=None,
                     environment_overrides={"BAXY_MIND_CTX": ctx}, startup_timeout=300.0) as client, \
        out.open("w", encoding="utf-8", newline="\n") as sink:
    for row in rows:
        rec = run.get(row["id"])
        if not rec or not row.get("args") or rec.get("kind") not in {"action", "plan"} or not ce.verdict(row, rec)[0]:
            continue
        wanted = set(row["args"])
        record = dict(rec, arguments={})
        for op in sorted(ce.operations(rec)):
            if not any(ce.label_matches(label, {"kind": "action", "effects": [op]}) for label in wanted):
                continue
            reply = ce._await(client, {"type": "arguments", "id": f"ae-{row['id']}-{op}", "operation": op,
                                       "text": rec.get("objective") or row["text"], "history": row.get("history") or []},
                              "arguments.result", 90.0)
            record["arguments"][op] = reply.get("arguments") or {}
            if reply.get("question"):
                record.setdefault("argument_questions", {})[op] = reply["question"][:160]
        ok = ce.verdict(row, record)[1]
        right += ok
        total += 1
        sink.write(json.dumps({"id": row["id"], "ok": ok, "arguments": record["arguments"],
                               "questions": record.get("argument_questions")}, ensure_ascii=False) + "\n")
print(f"{set_path.rsplit('/', 1)[-1] if '/' in set_path else set_path}: argumentos {right}/{total}")
