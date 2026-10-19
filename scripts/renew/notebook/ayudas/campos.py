"""Per case of an e2e run: where the model saw a new field of levers 1-4 in a tool result (next, scope/notAvailableYet,
folder baxy_work/sameNameInHome, listedPath(s)/subfoldersEntered) and what it did next (the following steps of the turn
and the start of its reply). Also E011's step chain. Cases are told apart by their turn texts (practice bank).
Usage: py -I campos.py <run dir> <cases.json>"""
import json, sys
run, cases_path = sys.argv[1], sys.argv[2]
cases = json.load(open(cases_path, encoding="utf-8")); cases = cases if isinstance(cases, list) else cases["cases"]
by_text = {t["text"]: c["id"] for c in cases for t in c.get("turns", [])}
WANT = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else {"E011"}
KEYS = ("next", "scope", "notAvailableYet", "sameNameInHome", "listedPath", "listedPaths", "subfoldersEntered")
def walk(o, found):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in KEYS or (k == "folder" and v == "baxy_work"):
                found.append(f"{k}={str(v)[:90]}")
            walk(v, found)
    elif isinstance(o, list):
        for v in o: walk(v, found)
cur, turn = None, []
out = {}
def flush():
    if cur and turn:
        out.setdefault(cur, []).append(list(turn))
for line in open(f"{run}/events.jsonl", encoding="utf-8", errors="replace"):
    try: e = json.loads(line)
    except json.JSONDecodeError: continue
    t = e.get("type")
    if t == "turn.start":
        flush(); turn = []
        txt = (e.get("input") or {}).get("text")
        cur = by_text.get(txt, cur)
    elif t == "step":
        try: obs = json.loads(e.get("observation") or "{}")
        except json.JSONDecodeError: obs = {}
        found = []
        if e.get("status") != "pending": walk(obs, found)
        args = e.get("arguments") or {}
        brief = ",".join(f"{k}={str(v)[:40]}" for k, v in args.items() if k in ("name", "folder", "path", "query", "setting", "value", "text", "expression"))
        turn.append(("step", f"{e.get('operation')}({brief}) {e.get('status')}{' ' + str(e.get('error')) if e.get('error') else ''}", found))
    elif t == "speech.start" and not e.get("notice"):
        turn.append(("say", (e.get("text") or "")[:120], []))
flush()
for cid in sorted(out):
    turns = out[cid]
    hit = any(f for tr in turns for (_, _, f) in tr)
    if not hit and cid not in WANT:
        continue
    print(f"== {cid}")
    for n, tr in enumerate(turns):
        for kind, txt, found in tr:
            print(f"  t{n} {kind}: {txt}" + (f"   <-- NEW {found}" if found else ""))
