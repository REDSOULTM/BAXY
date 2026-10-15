"""One summary of a renew_check run: each bench's first line, and with --holdout the final holdout's accuracy.

usage: py -3.12 -X utf8 scripts/renew/summarize.py <label> [--holdout]
The final holdout is the sealed decision bank, the sealed end-to-end bank and the heartbeat's sealed scenes, counted
case by case together (≥ 85 % is the goal).
"""
import json
import os
import sys
from pathlib import Path

RUNS = Path(os.environ.get("BAXY_RENEW_BANKS", r"F:\BAXYeval\renew_v1")) / "runs"


def first(path: Path) -> dict | None:
    if not path.is_file():
        return None
    line = path.read_text(encoding="utf-8").splitlines()[0]
    data = json.loads(line)
    return data.get("summary", data)


def main() -> None:
    label = sys.argv[1]
    holdout = "--holdout" in sys.argv
    parts = {
        "decision": first(RUNS / f"{label}-decision.jsonl"),
        "escenas": first(RUNS / f"{label}-escenas.jsonl"),
        "latido": first(RUNS / f"{label}-latido-escenas.jsonl"),
        "e2e": first(RUNS / f"{label}-e2e" / "results.jsonl"),
        "falsedades": first(RUNS / f"{label}-falsedades" / "results.jsonl"),
        "recursos": json.loads((RUNS / f"{label}-recursos.json").read_text(encoding="utf-8"))
        if (RUNS / f"{label}-recursos.json").is_file() else None,
    }
    summary = {"label": label, "parts": parts}
    if holdout:
        counted = [parts[name] for name in ("decision", "e2e", "latido") if parts[name]]
        ok = sum(part["ok"] for part in counted)
        n = sum(part["n"] for part in counted)
        summary["holdout_final"] = {"ok": ok, "n": n, "accuracy": round(ok / n, 4) if n else None}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    (RUNS / f"{label}-resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
