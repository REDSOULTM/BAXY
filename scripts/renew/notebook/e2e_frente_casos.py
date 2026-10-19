"""After an e2e run: per case, the app.open asked in front that ended behind another window, by the program holding the
front. Cases are told apart by their turn texts (read from the cases file and matched, never printed: phase 4 runs a
sealed holdout). Prints the case ids with a front left behind and exits 1 when one was behind GameInputSvc.
Usage: py -I e2e_frente_casos.py <events.jsonl> <cases.json>"""
import collections
import json
import sys

events_path, cases_path = sys.argv[1], sys.argv[2]
cases = json.load(open(cases_path, encoding="utf-8"))
cases = cases if isinstance(cases, list) else cases["cases"]
by_text = {turn["text"]: case["id"] for case in cases for turn in case.get("turns", [])}
current, total, behind = None, 0, collections.defaultdict(collections.Counter)
for line in open(events_path, encoding="utf-8", errors="replace"):
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        continue
    if event.get("type") == "turn.start":
        current = by_text.get((event.get("input") or {}).get("text"), current)
        continue
    if event.get("type") != "step" or event.get("operation") != "app.open" or event.get("status") != "completed":
        continue
    if not (event.get("arguments") or {}).get("foreground"):
        continue
    try:
        observed = json.loads(event.get("observation") or "{}").get("observed") or {}
    except json.JSONDecodeError:
        observed = {}
    total += 1
    if observed.get("foreground") is False:
        behind[current or "?"][(observed.get("foregroundHeldBy") or {}).get("process") or "?"] += 1
dirty = sorted(case for case, holders in behind.items() if holders.get("GameInputSvc"))
print(f"frente por caso: {sum(sum(h.values()) for h in behind.values())} de {total} app.open al frente quedaron detrás; "
      f"casos {dict((case, dict(holders)) for case, holders in sorted(behind.items()))}; con GameInputSvc: {dirty}")
sys.exit(1 if dirty else 0)
