"""Classes of the goal «ayudas» holdout, as in the FT goal (fase4_clases.py of ft_v1): each case counts once.
OK = decided well on both GPUs and, if executed, executed well; ELIGE_MAL = decided badly on some GPU; EJECUTA_MAL =
decided well and executed badly (EJECUTA_MAL, RESPUESTA_MAL or another operation in the execution). Counts only, by
family and kind; no text of the holdout is read or printed (the ids are shuffled).
usage: py -3.12 -X utf8 fase4_clases.py
"""
import json
from collections import Counter, defaultdict

R = "F:/BAXYeval/ayudas_v1/runs"


def rows(path):
    return {r["id"]: r for r in map(json.loads, open(path, encoding="utf-8")) if "id" in r}


pc, nb = rows(f"{R}/pc-fase4-dec-lote.jsonl"), rows(f"{R}/nb-ayh-lote-dec.jsonl")
ex = rows("F:/BAXYeval/ayudas_v1/fase4/nb-fase4-ay-lote-judged.jsonl")
classes, by_family, by_kind = Counter(), defaultdict(Counter), defaultdict(Counter)
exec_kinds = Counter()
for cid, row in pc.items():
    if row.get("excluded"):
        continue
    decided = row["ok"] and nb[cid]["ok"]
    if not decided:
        cls = "ELIGE_MAL"
    elif cid in ex and ex[cid]["exec"] != "OK":
        cls = "EJECUTA_MAL"
        exec_kinds[ex[cid]["exec"]] += 1
    else:
        cls = "OK"
    classes[cls] += 1
    by_family[row["family"]][cls] += 1
    if cid in ex:
        by_kind[ex[cid]["kind"]][cls] += 1
n = sum(classes.values())
print("casos", n, {k: f"{v} ({100 * v / n:.1f} %)" for k, v in classes.most_common()})
print("ejecutados", len(ex), "de los decididos bien y ejecutados mal, por juicio:", dict(exec_kinds))
for fam, c in sorted(by_family.items()):
    print(" ", fam, dict(c))
print("por tipo (ejecutados):", {k: dict(v) for k, v in by_kind.items()})
print("marcados para revisar falsedad:", sum(1 for r in ex.values() if r.get("revisar_falsedad")))
