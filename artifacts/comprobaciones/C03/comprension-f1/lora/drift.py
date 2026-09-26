"""Language drift of the decider's restatement: English/Spanish user text restated in the other language.
usage: drift.py SET RUN..."""
import json, sys
sys.path.insert(0, r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo/src")
from baxy_mind import __main__ as m
rows = {r["id"]: r for r in map(json.loads, open(sys.argv[1], encoding="utf-8"))}
for path in sys.argv[2:]:
    n = mis = 0
    for r in map(json.loads, open(path, encoding="utf-8")):
        req = (r.get("raw") or {}).get("request") or r.get("objective")
        if not req or r.get("kind") not in ("action", "plan"):
            continue
        a, b = m._decisive_request_language(rows[r["id"]]["text"]), m._decisive_request_language(req)
        if a in ("es", "en") and b in ("es", "en"):
            n += 1
            mis += a != b
    print(path.rsplit("/", 1)[-1], f"deriva {mis}/{n}")
