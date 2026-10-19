"""After an e2e seed: the app.open asked in front that ended behind another window, by the program holding the front.
Prints "frente: <n> de <m> app.open al frente quedaron detrás {holder: count}" and exits 1 when one ended behind
GameInputSvc (the seed ran on a dirty desktop and its figure does not count)."""
import collections
import json
import sys

path = sys.argv[1]
total, behind = 0, collections.Counter()
for line in open(path, encoding="utf-8", errors="replace"):
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
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
        behind[(observed.get("foregroundHeldBy") or {}).get("process") or "?"] += 1
print(f"frente: {sum(behind.values())} de {total} app.open al frente quedaron detrás {dict(behind)}")
sys.exit(1 if behind.get("GameInputSvc") else 0)
