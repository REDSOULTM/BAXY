"""System One, piece C: Laya's training file for the first-stage design — choose among the shortlist (piece B) of the
request's own tools, plus asking and answering in words, the way the professor's architecture asks it.

usage: <python with sentence-transformers> -X utf8 scripts/renew/system_one/build_shortlist_data.py DATADIR [--k-min 8 --k-max 16]
Reads DATADIR/{train,calib,dev}.jsonl and .ids.jsonl (build_kev_data.py) and writes DATADIR/sl_{train,calib,dev}.jsonl for
laya-train. Each case's options are the top-k tools of shortlist.py for its words — k drawn per case so the number of
options never tells the answer (v2a learned to count, 2026-10-22) — with the case's own text masked out of the example
index (otherwise it finds itself and the model learns to trust the first option). A case whose tool the shortlist missed
is left out (at run time the decision then falls to Qwen). Option texts are short: the options share Laya's head budget.
"""
import argparse
import collections
import json
import random
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from shortlist import ANSWER, ASK, Shortlist  # noqa: E402
import bench_decision as bench  # noqa: E402

OPTION_CHARS = 70


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("datadir")
    parser.add_argument("--k-min", type=int, default=8)
    parser.add_argument("--k-max", type=int, default=16)
    parser.add_argument("--tools", default=r"F:\BAXYeval\s1\agentes\catalogo_actual.json")
    parser.add_argument("--model", default="intfloat/multilingual-e5-small")
    args = parser.parse_args()
    from sentence_transformers import SentenceTransformer
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.system_one import OPTION_TEXT, QUESTION, short, state_text  # noqa: E402

    catalog = json.loads(Path(args.tools).read_text(encoding="utf-8"))
    tools = {t["wire"]: short(t["description"]) for t in catalog if t["wire"] not in (ASK, "confirm_pending")}
    option_text = {w: short(d, OPTION_CHARS) for w, d in tools.items()}
    option_text.update(OPTION_TEXT)
    data = Path(args.datadir)
    split_rows = {}
    for split in ("train", "calib", "dev"):
        recs = [json.loads(l) for l in open(data / f"{split}.jsonl", encoding="utf-8")]
        cases = [json.loads(l) for l in open(data / f"{split}.ids.jsonl", encoding="utf-8")]
        split_rows[split] = list(zip(recs, cases))
    examples = [(c["text"][:300], r["questions"]["operacion"]["label"]) for r, c in split_rows["train"]
                if r["questions"]["operacion"]["label"] in tools]
    model = SentenceTransformer(args.model, device="cpu")
    sl = Shortlist(tools, examples, model)
    example_index = {}
    for i, (text, _) in enumerate(examples):
        example_index.setdefault(text, []).append(i)
    rng = random.Random(20261022)
    stats = collections.Counter()
    for split, rows in split_rows.items():
        with open(data / f"sl_{split}.jsonl", "w", encoding="utf-8", newline="\n") as out:
            for rec, case in rows:
                label = rec["questions"]["operacion"]["label"]
                masked = example_index.get(case["text"][:300], []) if split == "train" else []
                saved = sl.ex_tool[masked].copy() if masked else None
                if masked:
                    sl.ex_tool[masked] = -1  # this case cannot find itself
                    keep = sl.ex_tool >= 0
                    ex, ex_tool = sl.ex, sl.ex_tool
                    sl.ex, sl.ex_tool = ex[keep], ex_tool[keep]
                ranked = sl.rank(case["text"][:300])
                if masked:
                    sl.ex, sl.ex_tool = ex, ex_tool
                    sl.ex_tool[masked] = saved
                k = rng.randint(args.k_min, args.k_max)
                options = ranked[:k]
                if label in tools and label not in options:
                    stats[f"{split}:gold_missed"] += 1
                    continue
                options = options + [ASK, ANSWER]
                rng.shuffle(options)
                out.write(json.dumps({"state": state_text(case["text"], case["history"]),
                                      "questions": {"operacion": {"type": "choice", "instructions": QUESTION,
                                                                  "criteria": {o: option_text[o] for o in options}}},
                                      "expected": {"operacion": label},
                                      "_case": case["id"]}, ensure_ascii=False) + "\n")
                stats[split] += 1
    print(json.dumps(dict(stats)))


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
