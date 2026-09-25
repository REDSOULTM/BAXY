"""Offline split simulation (F2): readers keep the turns they decide, the free model decides the rest.

usage: hybrid.py SET BASE_RUN BASE_AUDIT FREE_RUN   (aggregates only; decision-only verdicts)
"""
import json
import sys

sys.path.insert(0, r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo/scripts")
import comprension_eval as ce  # noqa: E402


def load(path):
    return {json.loads(line)["id"]: json.loads(line) for line in open(path, encoding="utf-8") if line.strip()}


rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
base, free = load(sys.argv[2]), load(sys.argv[4])
paths = {}
for line in open(sys.argv[3], encoding="utf-8"):
    record = json.loads(line)
    if record.get("phase") == "final" and str(record.get("request_id", "")).startswith("cn-"):
        paths[record["request_id"][3:]] = record.get("decision_path")
KEEPS = {
    "sólo libre": (),
    "+ lector de conversación": ("explicit_conversation",),
    "+ lectores de conversación y efectos": ("explicit_conversation", "explicit_effects"),
    "+ ... y aclaración explícita": ("explicit_conversation", "explicit_effects", "explicit_clarification"),
}
n = len(rows)
followups = [r for r in rows if r["kind"] == "conv" and r.get("dep")]
singles = [r for r in rows if r["kind"] == "single"]
b = sum(ce.verdict(r, base[r["id"]])[0] for r in rows)
print(f"producto: {b}/{n} = {100 * b / n:.1f} %  seguimientos {sum(ce.verdict(r, base[r['id']])[0] for r in followups)}/{len(followups)}")
for name, keep in KEEPS.items():
    def ok(r):
        source = base if paths.get(r["id"], "recovery") in keep else free
        return ce.verdict(r, source[r["id"]])[0]
    total = sum(ok(r) for r in rows)
    print(f"{name:40} {total}/{n} = {100 * total / n:.1f} %  sueltos {sum(ok(r) for r in singles)}/{len(singles)}"
          f"  seguimientos {sum(ok(r) for r in followups)}/{len(followups)}")
