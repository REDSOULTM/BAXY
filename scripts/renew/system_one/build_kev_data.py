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
from kev_adjudicate import ANSWER, KINDS, OPTION_TEXT, qwen_choice, short, state_text  # noqa: E402

CANT = {"sint_no_lo_hago", "sint_modo_no_disponible"}


def group_of(row):
    if row["id"].startswith("R"):
        return row["id"].split(".")[0]  # one real mission
    return f'{row["family"]}:{(row["expect"].get("op") or row["expect"]["kind"])}'


def split_of(group):
    bucket = int(hashlib.sha256(group.encode("utf-8")).hexdigest(), 16) % 10
    return "calib" if bucket == 0 else "dev" if bucket == 1 else "train"


def confusion_map(rows):
    """For each expected tool, the other tools Qwen chose or nearly chose for it across the runs, most frequent first."""
    pairs = collections.defaultdict(collections.Counter)
    for row in rows:
        expect = row["expect"]
        if expect["kind"] != "call":
            continue
        gold = (bench.current(expect["op"])[0] or "").replace(".", "_")
        if not gold:
            continue
        for name in [qwen_choice(row)] + [r["wire"] for r in row["rivals"] if r.get("known")]:
            if name not in (gold, "ask_user", ANSWER):
                pairs[gold][name] += 1
    return {gold: [name for name, _ in counter.most_common()] for gold, counter in pairs.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("outdir")
    parser.add_argument("--signals", nargs="+", required=True)
    parser.add_argument("--confusers", type=int, default=0, help="training only: add up to N look-alike tools per case")
    parser.add_argument("--catalog", default=str(Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "renew" / "catalog.configure.json"))
    args = parser.parse_args()
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.mind import Mind  # noqa: E402

    mind = Mind(None, Path(args.outdir) / "configure.trace.jsonl")
    Path(args.outdir).mkdir(parents=True, exist_ok=True)
    mind.configure(json.loads(Path(args.catalog).read_text(encoding="utf-8")))
    described = {t["function"]["name"]: short(t["function"]["description"]) for t in mind.tools}
    described.update(OPTION_TEXT)
    rng = random.Random(20261021)
    files = {name: open(Path(args.outdir) / f"{name}.jsonl", "w", encoding="utf-8", newline="\n")
             for name in ("train", "calib", "dev")}
    # The same records for laya-train, which reads the labels from an `expected` object instead of each question.
    laya_files = {name: open(Path(args.outdir) / f"laya_{name}.jsonl", "w", encoding="utf-8", newline="\n")
                  for name in ("train", "calib", "dev")}
    stats = collections.Counter()
    seen = set()  # shards that met in the middle repeat cases: the first one read counts
    rows = []
    for label in args.signals:
        for line in open(bench.BANKS / "runs" / f"{label}.jsonl", encoding="utf-8"):
            row = json.loads(line)
            if row["excluded"] or not row.get("signals") or row["id"] in seen:
                stats["skipped"] += 1
                continue
            seen.add(row["id"])
            rows.append(row)
    confusers = confusion_map(rows) if args.confusers else {}
    gold_tools = collections.Counter((bench.current(r["expect"]["op"])[0] or "").replace(".", "_") for r in rows
                                     if r["expect"]["kind"] == "call")
    common = [t for t, _ in gold_tools.most_common(60) if t in described]
    ids = {name: open(Path(args.outdir) / f"{name}.ids.jsonl", "w", encoding="utf-8", newline="\n")
           for name in ("train", "calib", "dev")}
    for row in rows:
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
            split = split_of(group_of(row))
            anchor = gold[0] if gold else options[0]
            if split == "train" and confusers and anchor in confusers and rng.random() < 0.5:
                # Hard negatives (training only): the tools Qwen took for this one elsewhere in the runs, so the small
                # model learns the catalog's look-alikes (alarm/calendar, app/game, search/weather). On half the cases
                # whatever their answer: added only to «act» cases (v2a, 2026-10-22), the number of tools told the answer
                # (one tool → «answer in words»: decision2 230 → 196).
                extra = [c for c in confusers[anchor] if c not in options and c in described]
                options += extra[:args.confusers]
                stats["confusers_added"] += len(extra[:args.confusers])
            tools = [o for o in options if o not in ("ask_user", ANSWER)]
            if split == "train" and confusers and not tools and rng.random() < 0.7:
                # In BAXY the decision model is asked only about a tool Qwen proposed: a case whose right answer is words
                # or a question also gets one or two common tools, so «no tool offered» never tells the answer.
                options += rng.sample(common, rng.choice((1, 2)))
                stats["distractors_added"] += 1
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
            files[split].write(json.dumps(record, ensure_ascii=False) + "\n")
            ids[split].write(json.dumps({"id": row["id"], "group": group_of(row), "family": row["family"],
                                         "text": row["text"], "history": row["history"]}, ensure_ascii=False) + "\n")
            laya = {"state": record["state"],
                    "questions": {q: {k: v for k, v in body.items() if k != "label"}
                                  for q, body in record["questions"].items()},
                    "expected": {q: body["label"] for q, body in record["questions"].items()}}
            laya_files[split].write(json.dumps(laya, ensure_ascii=False) + "\n")
            stats[split] += 1
            stats[f"{split}:{kind}"] += 1
            stats[f"qwen_{'ok' if row['ok'] else 'wrong'}"] += 1
    for f in [*files.values(), *laya_files.values(), *ids.values()]:
        f.close()
    (Path(args.outdir) / "stats.json").write_text(json.dumps(dict(stats), ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(stats), ensure_ascii=False))


if __name__ == "__main__":
    main()
