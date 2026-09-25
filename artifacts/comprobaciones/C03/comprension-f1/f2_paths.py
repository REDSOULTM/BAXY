"""F2 — who decided each DEV-A turn and whether it was right; where the errors come from.

Inputs: the set, the product run (comprension_eval.py run) with its turn audit, and optionally a free-model run.
Paths (from the mind's audit): early_reader (answered before the reading gate, no final record), reader_effects
(explicit_effects), reader_conversation (explicit_conversation), reader_clarification (*_clarification), model
(native selector + gates), recovery (total recovery after failures). The dialogue slot is reported apart: rearmed by
pattern, by model, or not rearmed.
Error causes: rule_ahead (a reader decided and was wrong while the free model was right), veto (the selector's raw
choice was right and the gates changed it), model (model path wrong, raw choice also wrong), other.
usage: f2_paths.py SET RUN AUDIT [FREE_RUN]
"""
import json
import pathlib
import sys
from collections import Counter, defaultdict

sys.path.insert(0, r"C:/Users/usuario/Desktop/ETC/Programacion/BAXY Definitivo/scripts")
import comprension_eval as ce  # noqa: E402


def load(path):
    return [json.loads(line) for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    rows = load(sys.argv[1])
    run = {r["id"]: r for r in load(sys.argv[2])}
    audit = load(sys.argv[3])
    free = {r["id"]: r for r in load(sys.argv[4])} if len(sys.argv) > 4 else {}
    final, slot, recovery = {}, {}, set()
    for record in audit:
        rid = str(record.get("request_id", ""))
        if not rid.startswith("cn-"):
            continue
        rid = rid[3:]
        if record.get("phase") == "final":
            final[rid] = record
        elif record.get("phase") == "dialogue_slot":
            slot[rid] = record
        elif record.get("phase") == "recovery":
            recovery.add(rid)
    table = defaultdict(lambda: [0, 0])
    causes = Counter()
    slot_table = defaultdict(lambda: [0, 0])
    free_table = defaultdict(lambda: [0, 0])
    detail = []
    for row in rows:
        rid = row["id"]
        if rid not in run:
            continue
        ok = ce.verdict(row, run[rid])[1]
        f = final.get(rid)
        if rid in recovery:
            path = "recovery"
        elif f is None:
            path = "early_reader"
        else:
            path = str(f.get("decision_path"))
            path = {"explicit_effects": "reader_effects", "explicit_conversation": "reader_conversation"}.get(
                path, "reader_clarification" if path.endswith("clarification") else path)
        table[path][0] += ok
        table[path][1] += 1
        if row["kind"] == "conv" and row.get("dep"):
            how = (slot.get(rid) or {}).get("rearmed_by") or "none"
            rearmed = bool((slot.get(rid) or {}).get("rearmed"))
            key = f"{how}:{'rearmed' if rearmed else 'kept'}"
            slot_table[key][0] += ok
            slot_table[key][1] += 1
        free_ok = ce.verdict(row, free[rid])[1] if rid in free else None
        if free_ok is not None:
            free_table["free"][0] += free_ok
            free_table["free"][1] += 1
            free_table[f"product_{'ok' if ok else 'no'}__free_{'ok' if free_ok else 'no'}"][1] += 1
        if not ok:
            cause = "other"
            if path.startswith("reader") or path == "early_reader":
                cause = "rule_ahead" if free_ok else "rule_wrong_free_also"
            elif path == "model":
                raw = (f or {}).get("raw_decision") or {}
                raw_record = {"kind": raw.get("mode"), "effects": raw.get("effect_operations") or [],
                              "conversation_kind": None}
                if raw.get("mode") == "conversation":
                    raw_record["conversation_kind"] = "knowledge"
                raw_ok = ce.verdict({**row, "args": {}}, raw_record)[0] if raw else False
                cause = "veto" if raw_ok else ("model_wrong_free_ok" if free_ok else "model_wrong_free_also")
            elif path == "recovery":
                cause = "recovery"
            causes[cause] += 1
            detail.append((rid, path, cause, row["gold"], ce.got(run[rid]), row["text"][:80]))
    print("camino            bien/n")
    for path, (a, n) in sorted(table.items(), key=lambda kv: -kv[1][1]):
        print(f"  {path:22} {a}/{n} = {100 * a / n:.0f} %")
    print("seguimientos por re-armado:", dict(slot_table))
    print("causas de error:", dict(causes))
    if free_table:
        a, n = free_table["free"]
        print(f"modelo libre: {a}/{n} = {100 * a / n:.1f} %;",
              {k: v[1] for k, v in free_table.items() if k != "free"})
    if "-v" in sys.argv:
        for d in detail:
            print("  ", *d)


if __name__ == "__main__":
    main()
