"""Training examples for the decider LoRA (D13), in the exact prompt and output the product decider uses.

Per turn of the clean-room conversations (train/w*-p*.jsonl): the decider's system prompt over a PARTIAL catalog
(the target operations, their family siblings, then random distractors up to N), the last HISTORY_TURNS messages,
the user message, and the target JSON. Partial catalogs teach reading the catalog in front instead of memorising
names, so new operations (computer use) keep working without retraining; they also keep one example inside 6 GB.
Rows whose text normalises to a DEV-A/DEV-B/FINAL text are dropped. Prints counts only.
usage: build_train.py [--n 50] [--holdout 0.05]
"""
import json
import os
import pathlib
import random
import re
import sys
import unicodedata

sys.path.insert(0, r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo/src")
from baxy_mind.semantic import decider  # noqa: E402

ROOT = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY" / "comprension-2026-09-25"
HERE = pathlib.Path(__file__).resolve().parent
CAPS = json.load(open(HERE.parent / "catalog_config.json", encoding="utf-8"))["capabilities"]
TOOLS = {c["name"]: c["description"] for c in CAPS}
PLAIN = decider.plain_descriptions()
INTERNAL = {k for k, v in PLAIN.items() if v.startswith("Paso interno")}


def norm(text):
    text = unicodedata.normalize("NFKD", str(text).casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def main():
    n_ops = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 50
    holdout = float(sys.argv[sys.argv.index("--holdout") + 1]) if "--holdout" in sys.argv else 0.05
    rng = random.Random(1309)
    evaluation = set()
    for name in ("DEV-A", "DEV-B", "FINAL"):
        for line in open(ROOT / "sets" / f"{name}.jsonl", encoding="utf-8"):
            evaluation.add(norm(json.loads(line)["text"]))
    conversations = []
    for path in sorted((ROOT / "train").glob("w*-p*.jsonl")):
        for line in open(path, encoding="utf-8"):
            if line.strip():
                conversations.append(json.loads(line))
    rng.shuffle(conversations)
    cut = int(len(conversations) * holdout)
    out = {"train": [], "holdout": []}
    dropped = {"eval_overlap": 0, "bad_ops": 0, "bad_target": 0}
    families = {}
    for name in TOOLS:
        families.setdefault(name.split(".", 1)[0], []).append(name)
    for index, conv in enumerate(conversations):
        split = "holdout" if index < cut else "train"
        history = []
        for turn in conv.get("turns") or []:
            user = str(turn.get("user") or "").strip()
            target = turn.get("target") or {}
            ops = [op for op in target.get("operations") or []]
            decision = target.get("decision")
            ok = decision in decider.DECISIONS and user
            if not ok:
                dropped["bad_target"] += 1
            elif any(op not in TOOLS or op in INTERNAL for op in ops) or (decision == "action") != bool(ops):
                dropped["bad_ops"] += 1
            elif norm(user) in evaluation:
                dropped["eval_overlap"] += 1
            else:
                chosen = list(dict.fromkeys(ops))
                siblings = [s for op in chosen for s in families[op.split(".", 1)[0]] if s not in chosen and s not in INTERNAL]
                rng.shuffle(siblings)
                subset = chosen + siblings[: max(0, n_ops // 3 - len(chosen))]
                others = [t for t in TOOLS if t not in subset and t not in INTERNAL]
                rng.shuffle(others)
                subset += others[: n_ops - len(subset)]
                system = decider.catalog_prompt([(t, TOOLS[t]) for t in subset])
                messages = decider.messages(system, user, history)
                answer = json.dumps({"request": str(target.get("request") or user), "decision": decision,
                                     "operations": chosen if decision == "action" else [],
                                     "question": str(target.get("question") or "") if decision == "clarify" else ""},
                                    ensure_ascii=False)
                out[split].append({"id": conv.get("id"), "messages": messages, "answer": answer, "decision": decision})
            history.append({"role": "user", "content": user})
            if turn.get("assistant"):
                history.append({"role": "assistant", "content": str(turn["assistant"])})
    target_dir = ROOT / "train_built"
    target_dir.mkdir(exist_ok=True)
    for split, rows in out.items():
        with open(target_dir / f"{split}.jsonl", "w", encoding="utf-8", newline="\n") as sink:
            for row in rows:
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
    counts = {split: len(rows) for split, rows in out.items()}
    by = {}
    for row in out["train"]:
        by[row["decision"]] = by.get(row["decision"], 0) + 1
    print(json.dumps({"conversations": len(conversations), "examples": counts, "train_decisions": by,
                      "dropped": dropped, "catalog_ops_per_example": n_ops}))


if __name__ == "__main__":
    main()
