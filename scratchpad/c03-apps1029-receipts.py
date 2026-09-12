"""Extrae, por turno de APPS1029, lo que decide la adjudicación: camino, operaciones y recibo de app.

`turn-audit.jsonl` trae varias filas por turno (intento crudo, recuperación, publicación). Aquí se
agrupan por `request_id` y se conserva lo que importa: el camino de decisión, las operaciones
candidatas, la identidad de app observada (`app_open_identity`), la causa de fallo cuando la hay y la
honestidad declarada. La correlación con el panel es por orden de `request_id`, que el runner ya
verificó turno a turno contra sus controles.

Uso:
    python scratchpad/c03-apps1029-receipts.py
"""
from __future__ import annotations

import json
import pathlib

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
RUN = BASE / "C03-apps1029-private/run"
PANEL = BASE / "C03-apps1029-proposal/panel.json"


def main() -> int:
    audit = [json.loads(line) for line in (RUN / "turn-audit.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    events = [json.loads(line) for line in (RUN / "capture/events.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    terminals = [row for row in events if row.get("type") == "terminal"]
    panel = json.loads(PANEL.read_text(encoding="utf-8"))

    by_request: dict[str, list[dict]] = {}
    for row in audit:
        by_request.setdefault(str(row.get("request_id")), []).append(row)
    order = sorted(by_request, key=lambda value: int(value))
    if len(order) != len(panel):
        print(f"NOTE: {len(order)} audited requests for {len(panel)} cases: {order}")

    for index, case in enumerate(panel):
        rows = by_request.get(order[index], []) if index < len(order) else []
        terminal = terminals[index] if index < len(terminals) else {}
        print(f"== {index:2} {case['case_id']:22} {case['target'] or 'boundary':9} "
              f"expected={case['expected_path']}")
        print(f"   Q: {case['text']}")
        print(f"   A: {(terminal.get('final') or '').replace(chr(10), ' ')[:220]}")
        for row in rows:
            fields = {key: row[key] for key in
                      ("phase", "decision_path", "candidate_operations", "app_open_identity",
                       "failure_kind", "failure_reason", "failure_stage", "error_type", "honesty",
                       "recovery")
                      if row.get(key) not in (None, "", [], {})}
            print(f"   - {json.dumps(fields, ensure_ascii=False)[:900]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
