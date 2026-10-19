"""Lever 9 (dynamic few-shot), retrieval precomputed for the measurement: for every request text of decision2, the e2e
practice and the falsedades practice, the 1-3 most similar synthetic v2 examples (G1-G6, already leak-checked against
every bank) whose target is a call or a question, by cosine of paraphrase-multilingual-MiniLM-L12-v2 (the embedder of
fuga_emb.py). The product would embed the request live; offline the result is the same. Also measures the embedder's
RAM (USS) and its latency per request on CPU. Prints counts only, never a text.
usage: D:/BAXYft/venv/Scripts/python.exe -X utf8 recuperar_p9.py [--top 3] [--min 0.55]
"""
import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import psutil

OUT = Path(r"F:/BAXYeval/ayudas_v1/palanca9")
POOL = [Path(rf"F:/BAXYeval/ft_v1/datos/G{i}.emb_limpio.jsonl") for i in range(1, 7)]


def queries() -> list[str]:
    texts = [c["text"] for c in json.loads(Path(r"F:/BAXYeval/renew_v1/practica/decision2.json").read_text(encoding="utf-8"))]
    for bank in (r"F:/BAXYeval/renew_v1/e2e/practice.json", r"F:/BAXYeval/renew_v1/falsedades/practice.json"):
        for case in json.loads(Path(bank).read_text(encoding="utf-8")):
            texts += [t["text"] for t in case.get("turns") or [] if t.get("text")]
    return sorted(set(texts))


def shown(example: dict) -> str | None:
    target = example.get("target") or {}
    if target.get("kind") == "call" and target.get("calls"):
        calls = "; ".join(f'{c["op"].replace(".", "_")} {json.dumps(c.get("arguments") or {}, ensure_ascii=False)}'
                          for c in target["calls"])
        return f'«{example["text"]}» → {calls}'
    if target.get("kind") == "ask":
        return f'«{example["text"]}» → ask_user'
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--min", type=float, default=0.55)
    args = ap.parse_args()
    pool = []
    for path in POOL:
        for line in path.read_text(encoding="utf-8").splitlines():
            example = json.loads(line)
            line_shown = shown(example)
            if line_shown:
                pool.append((example["text"], line_shown))
    me = psutil.Process(os.getpid())
    before = me.memory_full_info().uss
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", device="cpu")
    loaded = me.memory_full_info().uss
    pool_vectors = model.encode([t for t, _ in pool], normalize_embeddings=True, batch_size=64)
    qs = queries()
    started = time.perf_counter()
    for q in qs[:50]:
        model.encode([q], normalize_embeddings=True)
    per_query_ms = (time.perf_counter() - started) * 1000 / min(50, len(qs))
    q_vectors = model.encode(qs, normalize_embeddings=True, batch_size=64)
    sims = q_vectors @ pool_vectors.T
    mapping, counts = {}, []
    for i, q in enumerate(qs):
        order = np.argsort(-sims[i])[: args.top]
        chosen = [pool[j][1] for j in order if sims[i, j] >= args.min and pool[j][0] != q]
        counts.append(len(chosen))
        if chosen:
            mapping[q] = chosen
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "recuperados.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8")
    report = {"pool": len(pool), "queries": len(qs), "with_examples": len(mapping),
              "examples_per_query": {str(k): counts.count(k) for k in range(args.top + 1)},
              "embedder_uss_mib": round((loaded - before) / 2**20), "process_uss_mib": round(me.memory_full_info().uss / 2**20),
              "per_query_ms_cpu": round(per_query_ms, 1), "top": args.top, "min_cosine": args.min}
    (OUT / "informe.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
