"""System One: Kev's training file from qwen_signals.py runs (each case's own expectation and Qwen's real rivals).

usage: py -3.12 -X utf8 scripts/renew/system_one/build_kev_data.py OUTDIR --signals s1-<label> [s1-<label> ...]
Per case two questions, as kev_adjudicate.py asks them at run time: `operacion` (Qwen's choice, its rivals, asking,
answering in words — plus the expected tool when Qwen never thought of it, so every record has its answer) and `tipo`
(act / ask / answer / out of what BAXY does). Options are shuffled per record (option order moves these models' answers).
Groups (a mission, or a synthetic example's operation and family) never cross splits: train 80 %, calib 10 % (the
temperature), dev 10 %. Writes OUTDIR/train.jsonl, calib.jsonl, dev.jsonl in kev.train's format (an API request with a
`label` on each question) and OUTDIR/stats.json.
"""
import argparse
import collections
import hashlib
import json
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import bench_decision as bench  # noqa: E402
from kev_adjudicate import ANSWER, KINDS, qwen_choice, short, state_text  # noqa: E402

CANT = {"sint_no_lo_hago", "sint_modo_no_disponible"}


def group_of(row):
    if row["id"].startswith("R"):
        return row["id"].split(".")[0]  # one real mission
    return f'{row["family"]}:{(row["expect"].get("op") or row["expect"]["kind"])}'


def split_of(group):
    bucket = int(hashlib.sha256(group.encode("utf-8")).hexdigest(), 16) % 10
    return "calib" if bucket == 0 else "dev" if bucket == 1 else "train"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    parser.add_argument("--signals", nargs="+", required=True)
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    args = parser.parse_args()
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.mind import Mind  # noqa: E402

    mind = Mind(None, Path(args.outdir) / "configure.trace.jsonl")
    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    described = {t["function"]["name"]: short(t["function"]["description"]) for t in mind.tools}
    described[ANSWER] = "contestar con palabras, sin usar herramientas"
    described["ask_user"] = "preguntar a la persona lo que falta o lo que no está claro"
    rng = random.Random(20261021)
    files = {name: open(Path(args.outdir) / f"{name}.jsonl", "w", encoding="utf-8", newline="\n")
             for name in ("train", "calib", "dev")}
    stats = collections.Counter()
    for label in args.signals:
        for line in open(bench.BANKS / "runs" / f"{label}.jsonl", encoding="utf-8"):
            row = json.loads(line)
            if row["excluded"] or not row.get("signals"):
                stats["skipped"] += 1
                continue
            expect = row["expect"]
            if expect["kind"] == "call":
                gold = [bench.current(expect["op"])[0]]
            elif expect["kind"] == "call_any":
                gold = [bench.current(o)[0] for o in expect["ops"]]
            else:
                gold = []
            gold = [g.replace(".", "_") for g in gold if g]
            if expect["kind"] in ("call", "call_any") and not any(g in described for g in gold):
                stats["gold_not_in_catalog"] += 1
                continue
            options = [qwen_choice(row)] + [r["wire"] for r in row["rivals"] if r.get("known")]
            if expect["kind"] in ("call", "call_any") and not any(g in options for g in gold):
                options.append(next(g for g in gold if g in described))
                stats["gold_added"] += 1
            options = [o for o in dict.fromkeys(options + ["ask_user", ANSWER]) if o in described]
            rng.shuffle(options)
            if expect["kind"] == "ask":
                answer, kind = "ask_user", "preguntar"
            elif expect["kind"] == "text":
                answer, kind = ANSWER, ("no_se_puede" if row["family"] in CANT else "responder")
            else:
                answer, kind = next(g for g in gold if g in options), "actuar"
            kinds = list(KINDS.items())
            rng.shuffle(kinds)
            record = {"state": state_text(row["text"], row["history"]),
                      "questions": {
                          "operacion": {"type": "choice", "instructions": "¿Qué debe hacer el asistente con este pedido?",
                                        "criteria": {o: described[o] for o in options}, "label": answer},
                          "tipo": {"type": "choice", "instructions": "¿Qué tipo de respuesta pide este mensaje?",
                                   "criteria": dict(kinds), "label": kind}}}
            split = split_of(group_of(row))
            files[split].write(json.dumps(record, ensure_ascii=False) + "\n")
            stats[split] += 1
            stats[f"{split}:{kind}"] += 1
            stats[f"qwen_{'ok' if row['ok'] else 'wrong'}"] += 1
    for f in files.values():
        f.close()
    (Path(args.outdir) / "stats.json").write_text(json.dumps(dict(stats), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(stats), ensure_ascii=False))


if __name__ == "__main__":
    main()
