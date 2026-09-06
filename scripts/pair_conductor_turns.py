"""Empareja pedidos y respuestas publicadas de una corrida del conductor.

Lee `events.jsonl` de una captura y escribe la tabla que se adjudica: pedido,
estado terminal, texto publicado y estado posterior. Cuando la corrida activó
`BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH`, añade por turno las etapas de
composición (idioma leído, payload, borrador, motivo exacto de rechazo), que es
lo que faltaba para reconstruir un rechazo sin volver a lanzar la campaña.

Uso:
  py -3.12 scripts/pair_conductor_turns.py <captura> [--audit ruta.jsonl]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def pair(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Un turno por admisión: pedido, terminal, publicación y estado."""

    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in events:
        kind = row.get("type")
        if kind == "event":
            event = row.get("event") or {}
            if event.get("type") == "admission":
                current = {
                    "turnId": event.get("turnId"),
                    "request": "",
                    "terminal": "",
                    "final": "",
                    "diagnostic": None,
                    "compositionFailure": None,
                    "status": "",
                }
                turns.append(current)
            elif event.get("type") == "activity" and current is not None:
                entry = event.get("entry") or {}
                if entry.get("src") == "YOU" and not current["request"]:
                    current["request"] = str(entry.get("msg") or "")
            elif event.get("type") == "composition_failed" and current is not None:
                current["compositionFailure"] = event.get("cause")
        elif kind == "terminal" and current is not None:
            current["terminal"] = str(row.get("kind") or "")
            current["final"] = str(row.get("final") or "")
            current["diagnostic"] = row.get("diagnostic")
        elif kind == "posterior" and current is not None:
            current["status"] = str(row.get("statusDescription") or "")
            current["mindReplyRejection"] = row.get("mindReplyRejection")
    return turns


def attach_audit(
    turns: list[dict[str, Any]],
    audit: list[dict[str, Any]],
) -> None:
    by_trace: dict[str, list[dict[str, Any]]] = {}
    for record in audit:
        if record.get("schema") != "baxy.message-compose-diagnostic.v2":
            continue
        by_trace.setdefault(str(record.get("trace") or ""), []).append(record)
    for turn in turns:
        turn["compose"] = by_trace.get(str(turn.get("turnId") or ""), [])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--audit", type=Path, default=None)
    parser.add_argument(
        "--force",
        action="store_true",
        help="sobrescribe una tabla ya existente en la captura",
    )
    parsed = parser.parse_args()

    events = _read_jsonl(parsed.capture / "events.jsonl")
    turns = pair(events)
    audit_path = parsed.audit
    if audit_path is None:
        candidate = parsed.capture / "compose-audit.jsonl"
        audit_path = candidate if candidate.exists() else None
    if audit_path is not None and audit_path.exists():
        attach_audit(turns, _read_jsonl(audit_path))

    published = sum(1 for turn in turns if turn["terminal"] == "published_final")
    lines = [
        f"n={len(turns)} published={published} "
        f"other={len(turns) - published}",
        "",
    ]
    for index, turn in enumerate(turns, start=1):
        lines.append(
            f"{index:03d}\t{turn['turnId']}\t{turn['terminal']}\t"
            f"{turn['request']}\t{turn['final'] or turn['compositionFailure'] or ''}"
        )
    # La consola de Windows es cp1252 y una respuesta con un espacio fino
    # («18 h 21») rompía la impresión y se perdía la evidencia entera antes de
    # escribirla. La captura es lo que importa: la consola se adapta o se calla.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    print("\n".join(lines))
    outputs = {
        parsed.capture / "paired.txt": "\n".join(lines) + "\n",
        parsed.capture / "paired.json": json.dumps(
            turns, ensure_ascii=False, indent=2
        )
        + "\n",
    }
    # Una captura ya adjudicada es evidencia fechada: no se pisa sin decirlo.
    existing = [path.name for path in outputs if path.exists()]
    if existing and not parsed.force:
        print(f"no escribo {', '.join(existing)}: ya existen (usa --force)")
        return 0
    for path, body in outputs.items():
        path.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
