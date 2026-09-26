"""Decision-only fixed/broken between two runs of the isolated decider. usage: cmp_dec.py SET BASE RUN"""
import json, sys, collections
sys.path.insert(0, r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo/scripts")
import comprension_eval as ce
rows = {r["id"]: r for r in map(json.loads, open(sys.argv[1], encoding="utf-8"))}
def load(p): return {r["id"]: r for r in map(json.loads, open(p, encoding="utf-8"))}
base, run = load(sys.argv[2]), load(sys.argv[3])
def g(r): return r.get("kind") + ":" + (r.get("operation") or r.get("conversation_kind") or "")
fixed = broken = 0
kinds = collections.Counter()
for i, row in rows.items():
    a, b = ce.verdict(row, base[i])[0], ce.verdict(row, run[i])[0]
    if a != b:
        tag = "ARREGLA" if b else "ROMPE"
        fixed += b; broken += a
        gold = row.get("gold") or row.get("labels")
        kinds[(tag, g(base[i]).split(":")[0], g(run[i]).split(":")[0])] += 1
        print(tag, i, gold, g(base[i]), "->", g(run[i]), "|", row["text"][:80])
print("fixed", fixed, "broken", broken)
for k, v in kinds.most_common(): print(v, k)
