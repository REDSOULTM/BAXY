"""Vuelca el diagnóstico de composición de una tanda: intención, situación y borrador publicado.

Sirve para adjudicar con la causa a la vista, sin adivinar por qué una frase salió así.

Uso:
    python scratchpad/c03-compose-dump.py <batch> [filtro]
"""
from __future__ import annotations

import json
import pathlib
import sys

BASE = pathlib.Path.home() / "AppData/Local/BAXY"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    batch = argv[1]
    needle = argv[2].casefold() if len(argv) > 2 else None
    path = BASE / f"C03-{batch}-private/run/compose-audit.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]
    shown = 0
    for row in rows:
        if not row.get("published"):
            continue
        draft = (row.get("draft") or "").replace("\n", " ")
        if needle and needle not in draft.casefold():
            continue
        shown += 1
        print(f"trace={row.get('trace')} intent={row.get('intent')} stage={row.get('stage')} "
              f"lang={row.get('language')} reason={row.get('reason')!r}")
        situation = row.get("situation")
        if isinstance(situation, str) and situation:
            print(f"   situation: {situation[:260]}")
        if row.get("payload"):
            print(f"   payload:   {json.dumps(row['payload'], ensure_ascii=False)[:260]}")
        print(f"   draft:     {draft[:200]}")
    print(f"\npublished rows shown: {shown} of {len(rows)} audit rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
