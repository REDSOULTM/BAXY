"""A/B paired e2e on the same items: usage pareado_ab.py <A prefix> <B prefix> <seed> [<seed> ...].
One seed: per item ok 0/1; Δ (B-A) with its 95 % CI by paired bootstrap over items, items up/down, exact McNemar.
Several seeds: per item mean over seeds; McNemar on the majority. Also: status counts (anything not ok/fail voids it),
setup_failed, and the gate cases E011/E017/E024 plus E020 and E006 per seed."""
import json, os, random, sys
from math import comb
from pathlib import Path
# The notebook's runs (D:) unless BAXY_RENEW_BANKS says where the banks are, as for the other scripts.
RUNS = Path(os.environ.get("BAXY_RENEW_BANKS", "D:/BAXYeval/renew_v1")) / "runs"
GATE = ("E011", "E017", "E024", "E020", "E006")

def rows(prefix, seed):
    path = RUNS / f"{prefix}-s{seed}-e2e-e2e/results.jsonl"
    out = {}
    for line in path.open(encoding="utf-8"):
        r = json.loads(line)
        if "summary" in r:
            continue
        out[r["id"]] = r
    return out

def mcnemar(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)

def boot(d, n=10000):
    rng = random.Random(0)
    m = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n))
    return m[int(.025 * n)], m[int(.975 * n)]

a_pre, b_pre, seeds = sys.argv[1], sys.argv[2], [int(s) for s in sys.argv[3:]]
A = {s: rows(a_pre, s) for s in seeds}; B = {s: rows(b_pre, s) for s in seeds}
for s in seeds:
    for arm, rr in (("A", A[s]), ("B", B[s])):
        st = {}
        for r in rr.values():
            st[r.get("status")] = st.get(r.get("status"), 0) + 1
        bad = {k: v for k, v in st.items() if k not in ("ok", "fallo")}
        print(f"s{s} {arm}: {sum(1 for r in rr.values() if r['ok'])}/{len(rr)} status {st}{' VOID ' + str(bad) if bad else ''}; "
              + " ".join(f"{g}={'OK' if rr.get(g, {}).get('ok') else 'NO'}" for g in GATE))
items = sorted(set.intersection(*[set(A[s]) & set(B[s]) for s in seeds]))
ma = {i: sum(A[s][i]["ok"] for s in seeds) / len(seeds) for i in items}
mb = {i: sum(B[s][i]["ok"] for s in seeds) / len(seeds) for i in items}
d = [mb[i] - ma[i] for i in items]
lo, hi = boot(d)
up = [i for i in items if mb[i] > .5 >= ma[i]]; down = [i for i in items if ma[i] > .5 >= mb[i]]
print(f"seeds {seeds}: n={len(items)} A {sum(ma.values()):.2f} B {sum(mb.values()):.2f} Δ items {sum(d):+.2f} "
      f"(95% CI [{lo*len(items):+.2f}, {hi*len(items):+.2f}]); up {up} down {down}; McNemar {len(up)}↑/{len(down)}↓ p={mcnemar(len(up), len(down)):.3f}")
