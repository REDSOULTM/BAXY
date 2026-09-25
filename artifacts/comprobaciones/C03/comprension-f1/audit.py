"""Gold audit (F1): a blind second labeler on a 10 % stratified sample; agreement is computed here.

  sample   writes <ROOT>/audit/batch.jsonl (what the auditor sees: text + history, no gold) and keys.json.
  compare  reads the auditor's gold_audit.jsonl; agreement = the two golds accept a common decision. Prints the
           agreement per set; disagreements are written to audit/disagree_{A,B,F}.jsonl (A is printed; B and F are
           only counted: their adjudication goes to a subagent).
"""
import json
import os
import pathlib
import random
import sys

ROOT = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "comprension-2026-09-25"
SETS = {"A": "DEV-A", "B": "DEV-B", "F": "FINAL"}
WEB = {"op:web.search", "op:weather.current", "op:web.news.headlines"}


def rows(s):
    return [json.loads(line) for line in open(ROOT / "sets" / f"{SETS[s]}.jsonl", encoding="utf-8") if line.strip()]


def sample() -> None:
    rng = random.Random(31337)
    out = ROOT / "audit"
    out.mkdir(exist_ok=True)
    picked = []
    for s in SETS:
        data = rows(s)
        for kind in ("single", "conv"):
            pool = [r for r in data if r["kind"] == kind]
            picked += [(s, r) for r in rng.sample(pool, max(1, round(len(pool) * 0.10)))]
    rng.shuffle(picked)
    keys = {}
    with open(out / "batch.jsonl", "w", encoding="utf-8", newline="\n") as sink:
        for n, (s, r) in enumerate(picked, 1):
            key = f"Q{n:03d}"
            keys[key] = {"set": s, "id": r["id"]}
            item = {"key": key, "type": "single" if r["kind"] == "single" else "turn", "text": r["text"]}
            if r["kind"] == "conv":
                item["history"] = r["history"]
            sink.write(json.dumps(item, ensure_ascii=False) + "\n")
    (out / "keys.json").write_text(json.dumps(keys, indent=0), encoding="utf-8")
    print("audit sample:", {s: sum(1 for v in keys.values() if v["set"] == s) for s in SETS})


def compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    for x, y in ((a, b), (b, a)):
        if x == "web" and (y in WEB or y.startswith("op:web") or y.startswith("op:weather")):
            return True
        if x.startswith("op:") and x.endswith("*") and y.startswith("op:") and y[3:].startswith(x[3:-1]):
            return True
        if x.startswith("plan:") and y.startswith("op:") and y[3:] in x[5:].split("+"):
            return True
    return False


def compare() -> None:
    keys = json.loads((ROOT / "audit" / "keys.json").read_text(encoding="utf-8"))
    audit = {}
    for line in open(ROOT / "audit" / "gold_audit.jsonl", encoding="utf-8"):
        if line.strip():
            row = json.loads(line)
            audit[row["key"]] = row
    by_id = {s: {r["id"]: r for r in rows(s)} for s in SETS}
    tally = {s: [0, 0] for s in SETS}
    sinks = {s: open(ROOT / "audit" / f"disagree_{s}.jsonl", "w", encoding="utf-8", newline="\n") for s in SETS}
    for key, where in keys.items():
        s, row = where["set"], by_id[where["set"]][where["id"]]
        mine = audit.get(key, {}).get("gold") or []
        agree = any(compatible(a, b) for a in row["gold"] for b in mine)
        tally[s][0] += agree
        tally[s][1] += 1
        if not agree:
            record = {"key": key, "id": row["id"], "label_id": row.get("label_id"), "text": row["text"],
                      "history": row["history"], "gold": row["gold"], "audit_gold": mine,
                      "audit_note": audit.get(key, {}).get("note", "")}
            sinks[s].write(json.dumps(record, ensure_ascii=False) + "\n")
            if s == "A":
                print(f"A {row['id']} | {row['text'][:90]} | oro {row['gold']} | auditor {mine}")
    for sink in sinks.values():
        sink.close()
    for s, (a, n) in tally.items():
        print(f"{SETS[s]}: acuerdo {a}/{n} = {100 * a / max(1, n):.0f} %")


if __name__ == "__main__":
    {"sample": sample, "compare": compare}[sys.argv[1]]()
