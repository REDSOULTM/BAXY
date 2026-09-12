"""Vuelca transcripción y recibos de una tanda para que raíz adjudique.

Generalización del volcado de APPS1029: por caso, la pregunta sellada, lo publicado y el estado del
terminal; después, los recibos de `app.open` del diario, que son la única autoridad sobre lo que pasó
en el PC. No adjudica.

Uso:
    python scratchpad/c03-batch-dump.py <batch>
"""
from __future__ import annotations

import json
import pathlib
import sys

BASE = pathlib.Path.home() / "AppData/Local/BAXY"


def load_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    batch = argv[1]
    run = BASE / f"C03-{batch}-private/run"
    panel = json.loads((BASE / f"C03-{batch}-proposal/panel.json").read_text(encoding="utf-8"))
    events = load_jsonl(run / "capture/events.jsonl")
    terminals = [row for row in events if row.get("type") == "terminal"]
    print(f"cases {len(panel)}  terminals {len(terminals)}")
    for index, case in enumerate(panel):
        terminal = terminals[index] if index < len(terminals) else {}
        print(f"{index:2} {case['case_id']:24} {case['kind'][:26]:26} "
              f"{case['expected_path']:15} {terminal.get('kind')}")
        print(f"    Q: {case['text']}")
        print(f"    A: {(terminal.get('final') or '').replace(chr(10), ' ')[:280]}")

    journal = BASE / f"C03-{batch}-profile/journal/missions.jsonl"
    if journal.is_file():
        print("\n-- receipts")
        for entry in load_jsonl(journal):
            payload = entry["payload"]
            if payload["phase"] != "completed":
                continue
            response = payload.get("response") or {}
            result = response.get("result") if isinstance(response.get("result"), dict) else {}
            print(f"  seq{payload['sequence']:3} {payload.get('operation'):16} "
                  f"{response.get('status')} verified={response.get('verified')} "
                  f"app={result.get('appId')} already={result.get('alreadyRunning')} "
                  f"pid={result.get('processId')} window={result.get('windowHandle')} "
                  f"error={response.get('errorCode')} inv={payload.get('invocationId')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
