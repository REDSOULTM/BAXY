"""Vuelca la tanda APPS1029 caso por caso para que raíz la juzgue: pregunta, respuesta y recibos.

No adjudica: pone delante lo que hace falta para adjudicar. La correlación entre panel y terminales es
posicional y la impone el propio runner, que exige un `session.new` correcto antes de cada turno y
falla si el mapeo turno/terminal queda sin resolver.

Uso:
    python scratchpad/c03-apps1029-dump.py            # transcripción
    python scratchpad/c03-apps1029-dump.py audit      # decisión y operaciones por turno
"""
from __future__ import annotations

import json
import pathlib
import sys

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
RUN = BASE / "C03-apps1029-private/run"
PANEL = BASE / "C03-apps1029-proposal/panel.json"


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def main(argv: list[str]) -> int:
    events = load_jsonl(RUN / "capture/events.jsonl")
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    terminals = [row for row in events if row.get("type") == "terminal"]
    if len(terminals) != len(panel):
        print(f"WARNING: {len(terminals)} terminals for {len(panel)} cases")

    if argv[1:2] == ["audit"]:
        audit = load_jsonl(RUN / "turn-audit.jsonl")
        print(f"turn-audit rows: {len(audit)}")
        keys: set[str] = set()
        for row in audit:
            keys.update(row)
        print("keys:", sorted(keys))
        for row in audit:
            print(json.dumps(row, ensure_ascii=False)[:1400])
            print("-" * 100)
        return 0

    for index, case in enumerate(panel):
        terminal = terminals[index] if index < len(terminals) else {}
        target = case["target"] or "boundary"
        print(f"{index:2} {case['case_id']:22} {target:9} {case['expected_path']:15} "
              f"kind={terminal.get('kind')}")
        print(f"    Q: {case['text']}")
        final = (terminal.get("final") or "").replace("\n", " ")
        print(f"    A: {final[:400]}")
        if terminal.get("diagnostic"):
            print(f"    D: {json.dumps(terminal['diagnostic'], ensure_ascii=False)[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
