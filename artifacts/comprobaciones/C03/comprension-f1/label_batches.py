"""Mix singles and public conversations of A, B and F under opaque ids and cut them into labeler batches.

Writes <ROOT>/label/batch{1,2,3}.jsonl (what the labelers see) and <ROOT>/label/idmap.json (opaque id -> set, kind,
index; no text). Prints counts only.
"""
import json
import os
import pathlib
import random

ROOT = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "comprension-2026-09-25"
STAGE = ROOT / "stage1"
OUT = ROOT / "label"
BATCHES = 3


def main() -> None:
    rng = random.Random(925)
    items = []
    for s in ("A", "B", "F"):
        for i, line in enumerate(open(STAGE / f"singles_{s}.jsonl", encoding="utf-8")):
            row = json.loads(line)
            items.append(({"type": "single", "text": row["text"], "hint": row["source_intent"]},
                          {"set": s, "kind": "single", "index": i}))
        for i, line in enumerate(open(STAGE / f"pubconv_{s}.jsonl", encoding="utf-8")):
            row = json.loads(line)
            turns = [{"user": t["user"], "assistant": t["assistant"]} for t in row["turns"]]
            items.append(({"type": "conversation", "turns": turns},
                          {"set": s, "kind": "pubconv", "index": i}))
    rng.shuffle(items)
    OUT.mkdir(parents=True, exist_ok=True)
    idmap = {}
    sinks = [open(OUT / f"batch{k + 1}.jsonl", "w", encoding="utf-8", newline="\n") for k in range(BATCHES)]
    counts = [[0, 0] for _ in range(BATCHES)]
    for n, (item, where) in enumerate(items):
        opaque = f"L{n + 1:04d}"
        k = n % BATCHES
        sinks[k].write(json.dumps({"id": opaque, **item}, ensure_ascii=False) + "\n")
        idmap[opaque] = where
        counts[k][0 if item["type"] == "single" else 1] += 1
    for sink in sinks:
        sink.close()
    (OUT / "idmap.json").write_text(json.dumps(idmap, indent=0), encoding="utf-8")
    print("batches (singles, conversations):", counts)


if __name__ == "__main__":
    main()
