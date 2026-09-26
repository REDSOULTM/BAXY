"""Training examples for the decider LoRA (D13), in the exact prompt and output the product decider uses.

Per turn of the clean-room conversations (train/w*-p*.jsonl): the decider's system prompt over the product's whole
catalog (--full of the examples, and the whole holdout) or over whole random families of about N operations (the
target's families always among them), the last HISTORY_TURNS messages, the user message, and the target JSON. Partial
catalogs teach reading the catalog in front instead of memorising names, so new operations (computer use) keep
working without retraining; which families are in view never depends on the answer.
Rows whose text normalises to a DEV-A/DEV-B/FINAL text are dropped. Prints counts only.
Hammer (Lin et al., ICLR 2025): in --mask of the examples every operation name of the catalog (and of the answer) is
replaced by a random name, so the decider reads descriptions, not names; in --irrelevance of the action examples the
target operations are removed from the catalog and the answer becomes a plain limit (never invent an operation).
usage: build_train.py [--n 50] [--holdout 0.05] [--mask 0.33] [--irrelevance 0.15] [--full 0.5]
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
    mask = float(sys.argv[sys.argv.index("--mask") + 1]) if "--mask" in sys.argv else 0.33
    irrelevance = float(sys.argv[sys.argv.index("--irrelevance") + 1]) if "--irrelevance" in sys.argv else 0.15
    full = float(sys.argv[sys.argv.index("--full") + 1]) if "--full" in sys.argv else 0.5
    rng = random.Random(1309)
    evaluation = set()
    for name in ("DEV-A", "DEV-B", "FINAL"):
        for line in open(ROOT / "sets" / f"{name}.jsonl", encoding="utf-8"):
            evaluation.add(norm(json.loads(line)["text"]))
    # The regression gates never train either (D21): the 742, the owner's script and held-out, the real log.
    repo = pathlib.Path(r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo/artifacts/comprobaciones/C03")
    gate_files = [
        (ROOT.parent / "C03-survey-requirements336-private" / "requirements.jsonl", "literal"),
        (repo / "contexto" / "dueno-2026-09-21.turns.jsonl", "text"),
        (repo / "contexto" / "heldout-2026-09-22.turns.jsonl", "text"),
        (HERE.parent / "corpus_A_log.jsonl", "text"),
    ]
    for path, key in gate_files:
        for line in open(path, encoding="utf-8-sig"):
            try:
                row = json.loads(line) if line.strip() else {}
            except json.JSONDecodeError:
                continue  # the scripts carry comment lines
            if isinstance(row, dict) and row.get(key):
                evaluation.add(norm(row[key]))
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
                # The catalog never depends on the answer: the product's whole catalog, or whole random families (the
                # target's families swapped in). A first build padded action examples with the target's siblings and
                # the rest with loose random operations, so "a full family in view" meant "act" (pilot 1, 2026-09-25).
                if split == "holdout" or rng.random() < full:
                    subset = [t for t in TOOLS if t not in INTERNAL]
                else:
                    names = list(families)
                    rng.shuffle(names)
                    picked = []
                    for family in names:
                        if sum(len(families[f]) for f in picked) >= n_ops:
                            break
                        picked.append(family)
                    needed = list(dict.fromkeys(op.split(".", 1)[0] for op in chosen))
                    for family in needed:
                        if family not in picked:
                            free = [i for i, f in enumerate(picked) if f not in needed]
                            picked[rng.choice(free)] = family
                    subset = [t for f in picked for t in families[f] if t not in INTERNAL]
                kind = "full" if len(subset) > n_ops * 2 else "families"
                answer_decision, answer_ops = decision, (chosen if decision == "action" else [])
                if split == "train" and decision == "action" and rng.random() < irrelevance:
                    # Hammer's irrelevance augmentation: what the catalog in front cannot do is a limit. The siblings
                    # stay, so the near miss is in view.
                    subset = [t for t in subset if t not in chosen]
                    answer_decision, answer_ops, kind = "limit", [], kind + "+irrelevance"
                shown = {t: t for t in subset}
                if split == "train" and rng.random() < mask:
                    # Hammer's function masking: names become opaque, descriptions carry the meaning.
                    shown = {t: f"{t.split('.', 1)[0]}.{''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(7))}"
                             for t in subset}
                    kind += "+mask"
                plain_of = {shown[t]: PLAIN.get(t) or TOOLS[t] for t in subset}
                saved = dict(decider.plain_descriptions())
                decider.plain_descriptions().clear()
                decider.plain_descriptions().update(plain_of)
                try:
                    system = decider.catalog_prompt([(shown[t], TOOLS[t]) for t in subset])
                finally:
                    decider.plain_descriptions().clear()
                    decider.plain_descriptions().update(saved)
                messages = decider.messages(system, user, history)
                answer = json.dumps({"request": str(target.get("request") or user), "decision": answer_decision,
                                     "operations": [shown[op] for op in answer_ops],
                                     "question": str(target.get("question") or "") if decision == "clarify" else ""},
                                    ensure_ascii=False)
                out[split].append({"id": conv.get("id"), "messages": messages, "answer": answer,
                                   "decision": answer_decision, "kind": kind})
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
    by, kinds = {}, {}
    for row in out["train"]:
        by[row["decision"]] = by.get(row["decision"], 0) + 1
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    print(json.dumps({"conversations": len(conversations), "examples": counts, "train_decisions": by,
                      "dropped": dropped, "catalog_ops_per_example": n_ops, "kinds": kinds}))


if __name__ == "__main__":
    main()
