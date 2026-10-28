"""System One, piece B: a CPU shortlist of the tools a request may want, for Laya to choose among (Laya degrades past
~20 options; the catalog has ~177 tools).

usage: <python with sentence-transformers> -X utf8 scripts/renew/system_one/shortlist.py --train DATADIR --eval s1-<label> [...]
Scores every tool for a request by reciprocal-rank fusion (RRF) of three signals, as the research recommended
(Tool2Vec, arXiv 2409.02141: labelled examples as keys beat descriptions; ToolRet, arXiv 2503.01763; BM25 rescues
names): (1) the nearest labelled TRAINING requests of each tool (max cosine, multilingual-e5-small, «query:»/«passage:»),
(2) the tool's own description, (3) BM25 over the tool's description and examples. Optionally united with Qwen's own
candidates from a qwen_signals.py run. Prints recall@k of the expected tool on each eval run (training texts only are
indexed: evaluation cases are never keys).
"""
import argparse
import collections
import json
import math
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bench_decision as bench  # noqa: E402
from wire_names import current, wire  # noqa: E402

KS = (4, 8, 12, 16, 20)
ASK, ANSWER = "ask_user", "responder_con_palabras"


def words(text):
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9ñ]{2,}", text)


class BM25:
    def __init__(self, docs, k1=1.2, b=0.75):
        self.docs = [collections.Counter(d) for d in docs]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lengths) / max(1, len(self.lengths))
        df = collections.Counter(w for d in self.docs for w in d)
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def scores(self, query):
        out = np.zeros(len(self.docs))
        for i, d in enumerate(self.docs):
            s = 0.0
            for w in set(query):
                if w in d:
                    f = d[w]
                    s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg))
            out[i] = s
        return out


class Shortlist:
    def __init__(self, tools, examples, model):
        """tools: {wire: description}; examples: [(text, wire)] training requests with their tool."""
        self.model = model
        self.wires = list(tools)
        self.index = {w: i for i, w in enumerate(self.wires)}
        self.desc = self._embed([f"passage: {w.replace('_', ' ')}: {tools[w]}" for w in self.wires])
        texts = [t for t, _ in examples]
        self.ex_tool = np.array([self.index[w] for _, w in examples])
        self.ex = self._embed([f"passage: {t}" for t in texts]) if texts else np.zeros((0, self.desc.shape[1]))
        bag = collections.defaultdict(list)
        for t, w in examples:
            bag[w] += words(t)
        self.bm25 = BM25([words(w.replace("_", " ") + " " + tools[w]) + bag[w] for w in self.wires])

    def _embed(self, texts):
        return np.asarray(self.model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False))

    def rank(self, text):
        q = self._embed([f"query: {text}"])[0]
        n = len(self.wires)
        ex_best = np.full(n, -1.0)
        if len(self.ex):
            sims = self.ex @ q
            np.maximum.at(ex_best, self.ex_tool, sims)
        desc = self.desc @ q
        lex = self.bm25.scores(words(text))
        fused = np.zeros(n)
        for signal in (ex_best, desc, lex):
            order = np.argsort(-signal)
            ranks = np.empty(n)
            ranks[order] = np.arange(1, n + 1)
            fused += 1.0 / (60 + ranks)  # RRF, k = 60 (Cormack et al. 2009)
        return [self.wires[i] for i in np.argsort(-fused)]


def gold_of(expect):
    if expect["kind"] == "call":
        op = bench.current(expect["op"])[0]
        return {wire(op)} if op else set()
    if expect["kind"] == "call_any":
        return {wire(o) for o in (bench.current(x)[0] for x in expect["ops"]) if o}
    return set()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True, help="a build_kev_data.py output dir (train.jsonl + train.ids.jsonl)")
    parser.add_argument("--eval", nargs="+", required=True)
    parser.add_argument("--tools", default=r"F:\BAXYeval\s1\agentes\catalogo_actual.json")
    parser.add_argument("--model", default="intfloat/multilingual-e5-small")
    args = parser.parse_args()
    from sentence_transformers import SentenceTransformer
    sys.path.insert(0, str(bench.ROOT / "src"))
    from baxy_mind.system_one import short  # noqa: E402

    catalog = json.loads(Path(args.tools).read_text(encoding="utf-8"))
    tools = {current(t["wire"]): short(t["description"]) for t in catalog if t["wire"] not in (ASK, "confirm_pending")}
    data = Path(args.train)
    examples = []
    for rec, case in zip((json.loads(l) for l in open(data / "train.jsonl", encoding="utf-8")),
                         (json.loads(l) for l in open(data / "train.ids.jsonl", encoding="utf-8"))):
        label = current(rec["questions"]["operacion"]["label"])
        if label in tools:
            examples.append((case["text"][:300], label))
    model = SentenceTransformer(args.model, device="cpu")
    started = time.monotonic()
    sl = Shortlist(tools, examples, model)
    print(f"index: {len(tools)} tools, {len(examples)} training examples, {time.monotonic() - started:.1f}s")
    for label in args.eval:
        rows = [json.loads(l) for l in open(bench.BANKS / "runs" / f"{label}.jsonl", encoding="utf-8")]
        rows = [r for r in rows if not r["excluded"] and gold_of(r["expect"])]
        hits = {k: 0 for k in KS}
        union = {k: 0 for k in KS}
        qwen_only = 0
        times = []
        for r in rows:
            gold = gold_of(r["expect"])
            t0 = time.monotonic()
            ranked = sl.rank(r["text"])
            times.append(time.monotonic() - t0)
            qwen = [current(x["wire"]) for x in r.get("rivals") or []] + ([wire(str(r["operation"]))] if r.get("operation") else [])
            for k in KS:
                hits[k] += bool(gold & set(ranked[:k]))
                union[k] += bool(gold & (set(ranked[:k]) | set(qwen)))
            qwen_only += bool(gold & set(qwen))
        n = len(rows)
        print(f"{label}: {n} cases whose answer is a tool | Qwen's own candidates hold it {qwen_only / n:.1%}")
        print("  recall@k shortlist:     " + "  ".join(f"@{k} {hits[k] / n:.1%}" for k in KS))
        print("  recall@k ∪ Qwen's:      " + "  ".join(f"@{k} {union[k] / n:.1%}" for k in KS))
        print(f"  CPU time per request p50 {sorted(times)[len(times) // 2] * 1000:.0f} ms")


if __name__ == "__main__":
    main()
