"""System One: accuracy by language of each System One model's second opinion on decision2 (kev_adjudicate.py runs).

usage: py -3.12 -X utf8 scripts/renew/system_one/compare_lang.py s1kev-<label> [s1kev-<label> ...]
Groups: MASSIVE es-ES, MASSIVE en-US (the same kind of request in both languages), spanglish, and the rest (written in
Spanish for the bank). Per model and group: right choice among the case's own options (reachable cases), right kind of
answer, and Qwen's own accuracy on the same cases for reference.
"""
import json
import sys
from pathlib import Path

BANKS = Path(r"F:\BAXYeval\renew_v1")


def group_of(case):
    source = str(case.get("source") or "")
    if ":es-ES:" in source:
        return "massive_es"
    if ":en-US:" in source:
        return "massive_en"
    if case.get("family") == "B_spanglish":
        return "spanglish"
    return "resto_es"


def main():
    cases = {c["id"]: c for c in json.loads((BANKS / "practica" / "decision2.json").read_text(encoding="utf-8"))}
    groups = ["massive_es", "massive_en", "spanglish", "resto_es"]
    print(f"{'modelo':<28}" + "".join(f"{g:>22}" for g in groups))
    qwen_done = False
    for label in sys.argv[1:]:
        rows = [json.loads(line) for line in open(BANKS / "runs" / f"{label}.jsonl", encoding="utf-8")]
        if not qwen_done:
            line = f"{'qwen (ajustado)':<28}"
            for g in groups:
                sel = [r for r in rows if group_of(cases[r["id"]]) == g and r["reachable"]]
                line += f"{sum(r['qwen_ok'] for r in sel):>12}/{len(sel):<3} {sum(r['qwen_ok'] for r in sel) / max(1, len(sel)):5.0%}"
            print(line)
            qwen_done = True
        line, kinds = f"{label:<28}", f"{'  tipo de respuesta':<28}"
        for g in groups:
            sel = [r for r in rows if group_of(cases[r["id"]]) == g and r["reachable"]]
            every = [r for r in rows if group_of(cases[r["id"]]) == g]
            line += f"{sum(r['kev_ok'] for r in sel):>12}/{len(sel):<3} {sum(r['kev_ok'] for r in sel) / max(1, len(sel)):5.0%}"
            kinds += f"{sum(r['kind_ok'] for r in every):>12}/{len(every):<3} {sum(r['kind_ok'] for r in every) / max(1, len(every)):5.0%}"
        print(line)
        print(kinds)


if __name__ == "__main__":
    main()
