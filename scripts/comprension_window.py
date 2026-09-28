"""Comprensión sets through the official window (the headless conductor): Fase 3.5b, 2026-09-28.

``comprension_eval.py run`` asks the mind alone, with the set's fixed history. Here the set runs in the product:
``scripts/run_baxy_conductor.ps1`` drives the same admission, turn and publication as the UI. Every single gets a
session of its own; a conversation runs message after message in one session, so its history is what BAXY really
published in that run. ``score`` of ``comprension_eval.py`` reads the records this writes.

  turns    the conductor's turns file (``session.new`` before each single and each conversation) and the map from
           the ordinal of each ``turn`` command to its row. ``--limit`` counts units (a single or a whole
           conversation); ``--ids`` takes row ids or conversation names and never cuts a conversation.
  records  one record per mapped row from the capture: ``kind``/``operation``/``effects``/``conversation_kind``/
           ``recovery`` from the mind's turn audit (joined to the turn through the shell trace), else ``kind`` from
           the published route; ``question``/``reply`` from the published final; ``latency_s`` from the trace
           (submit to final), else from the activity clock (whole seconds); ``arguments`` only through the
           composition audit with content (what the confirmation or the verified result carried, a proxy of the
           grounded arguments). A turn without a published final is a record with ``error``.
  review   one line per turn for an independent reviewer: the conversation as it was lived in the run, the gold, the
           published answer, and the empty fields ``invented``, ``warning``, ``ok`` and ``note``.

The effects are real: a run opens, closes and plays what the set asks for. Use a profile of its own and a fresh
capture folder per run (the audits and the trace append; the conductor overwrites ``events.jsonl``). The conductor
and the mind inherit the PowerShell environment:

  $cap = "$env:LOCALAPPDATA\\BAXY\\comprension-2026-09-25\\window\\DEV-A-1"
  New-Item -ItemType Directory -Force $cap | Out-Null
  $env:BAXY_APP_TRACE = "$cap\\shell-trace.jsonl"
  $env:BAXY_MIND_TURN_AUDIT_PATH = "$cap\\turn-audit.jsonl"
  $env:BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH = "$cap\\compose-audit.jsonl"
  $env:BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT = "1"
  powershell -ExecutionPolicy Bypass -File scripts\\run_baxy_conductor.ps1 -TurnsFile "$cap\\run.turns.jsonl" `
    -Capture $cap -Profile "$env:LOCALAPPDATA\\BAXY\\comprension-window-profile"

usage:
  comprension_window.py turns --set S.jsonl --out OUT.turns.jsonl --map OUT.map.json [--limit N] [--ids a,b]
  comprension_window.py records --capture DIR --map OUT.map.json --out RUN.jsonl [--audit TURN_AUDIT.jsonl]
                                [--trace SHELL_TRACE.jsonl] [--compose COMPOSE_AUDIT.jsonl]
  comprension_window.py review --run RUN.jsonl --set S.jsonl --map OUT.map.json --out REVIEW.jsonl
(``records`` takes turn-audit.jsonl, shell-trace.jsonl and compose-audit.jsonl from the capture when not given.)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict
from typing import Any

SCRIPTS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import comprension_eval as ce  # noqa: E402
from pair_conductor_turns import _read_jsonl as read_capture, pair  # noqa: E402

# The contextual decider's own words for a conversation; the explicit readers name the kind in their stages.
DECIDER_CONVERSATION = {"limit": "unsupported", "talk": "knowledge"}
# Without the audit only the published route says what kind of turn it was (PublicResponseRoute.cs).
ROUTE_KIND = {
    "clarification": "clarify",
    "conversation": "conversation",
    "welcome": "conversation",
    "confirmation": "action",
    "result": "action",
    "mission-summary": "plan",
}


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------------------------------------ turns


def units(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    ordered: list[list[dict[str, Any]]] = []
    conversations: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["kind"] != "conv":
            ordered.append([row])
            continue
        if row["conv"] not in conversations:
            conversations[row["conv"]] = []
            ordered.append(conversations[row["conv"]])
        conversations[row["conv"]].append(row)
    return [sorted(unit, key=lambda row: row["turn"]) for unit in ordered]


def turns(
    set_path: pathlib.Path,
    out: pathlib.Path,
    map_path: pathlib.Path,
    limit: int | None,
    ids: list[str] | None,
) -> None:
    selected = units(ce.read_jsonl(set_path))
    if ids:
        wanted = set(ids)
        selected = [
            unit
            for unit in selected
            if any(row["id"] in wanted or row.get("conv") in wanted for row in unit)
        ]
    selected = selected[: limit or None]
    commands: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    blocks = 0
    for session, unit in enumerate(selected, start=1):
        if session > 1:
            # A confirmation left pending by the previous conversation (DEV-A window 2026-09-28: «olvida mi memoria»
            # held 113 later turns on «¿confirmas o cancelas?») is cancelled before the next one, as a person who
            # starts another chat would. The conductor writes a «turn» admission for it too: counted in ``block``.
            commands.append({"cmd": "cancel"})
            blocks += 1
        commands.append({"cmd": "session.new"})
        for row in unit:
            text = str(row["text"]).strip()
            if not text:
                raise SystemExit(f"{row['id']}: texto vacío (el conductor lo mandaría como POST /turn sin texto)")
            commands.append({"cmd": "turn", "text": text})
            blocks += 1
            entries.append(
                {"ordinal": len(entries) + 1, "block": blocks, "id": row["id"], "session": session, "text": text}
            )
    write_jsonl(out, commands)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(
        json.dumps({"set": set_path.name, "turns": entries}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(selected)} sesiones, {len(entries)} turnos -> {out}")


# ------------------------------------------------------------------------------------------------ records


def turn_blocks(events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """The capture's lines per ``turn`` command, in order (a ``session.new`` closes the previous one)."""
    blocks: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] | None = None
    for row in events:
        if row.get("type") == "admission":
            current = [row] if row.get("command") == "turn" else None
            if current is not None:
                blocks.append(current)
        elif current is not None:
            current.append(row)
    return blocks


def clock_seconds(stamp: object) -> int | None:
    try:
        hours, minutes, seconds = (int(part) for part in str(stamp).split(":"))
    except ValueError:
        return None
    return hours * 3600 + minutes * 60 + seconds


def observe(block: list[dict[str, Any]]) -> dict[str, Any]:
    paired = pair(block)
    seen: dict[str, Any] = paired[0] if paired else {"turnId": None, "request": "", "terminal": "", "final": ""}
    if not seen["terminal"]:
        terminal = next((row for row in block if row.get("type") == "terminal"), None)
        if terminal is not None:
            seen.update(terminal=str(terminal.get("kind") or ""), diagnostic=terminal.get("diagnostic"))
    routes: list[str] = []
    stamps: list[int | None] = []
    error_state = False
    for row in block:
        event = (row.get("event") or {}) if row.get("type") == "event" else {}
        if event.get("type") == "state" and event.get("value") == "error":
            error_state = True
        if event.get("type") == "activity":
            entry = event.get("entry") or {}
            stamps.append(clock_seconds(entry.get("ts")))
            if entry.get("src") == "BAXY":
                routes.append(str(entry.get("route") or ""))
    seen.update(routes=routes, error_state=error_state or "error" in routes)
    if len(stamps) >= 2 and stamps[0] is not None and stamps[-1] is not None:
        seen["clock_latency"] = float((stamps[-1] - stamps[0]) % 86400)
    return seen


def trace_segments(trace: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per bridge turn id: the turn.decide request ids, the shell's turn ids and submit/final times."""
    segments: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for record in sorted(trace, key=lambda record: record.get("seq", 0)):
        scope, stage, turn_id = record.get("scope"), record.get("stage"), str(record.get("id"))
        if scope == "bridge" and stage == "submit.received":
            current = segments[turn_id] = {"decides": [], "ids": {turn_id}, "start": record.get("ms")}
        elif scope == "bridge" and stage == "response.final" and turn_id in segments:
            segments[turn_id]["end"] = record.get("ms")
        elif scope == "turn" and current is not None:
            current["ids"].add(turn_id)
            detail = str(record.get("detail") or "")
            if stage == "mind.request.start" and detail.startswith("turn.decide.id."):
                current["decides"].append(detail.split(".")[3])
    return segments


def audit_finals(audit: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    finals: dict[str, dict[str, Any]] = {}
    for record in audit:
        if record.get("phase") in {"final", "recovery"} and record.get("final"):
            finals[str(record.get("request_id"))] = record
    return finals


def decided(record: dict[str, Any]) -> dict[str, Any]:
    final = record["final"]
    kind = final.get("kind")
    stages = record.get("stages") or []
    raw = record.get("raw_decision") if isinstance(record.get("raw_decision"), dict) else {}
    operation = None
    effects: list[str] = []
    conversation_kind = None
    if kind in {"action", "plan"}:
        effects = sorted(final.get("effect_operations") or [])
        operation = next((stage["operation"] for stage in reversed(stages) if stage.get("operation")), None)
        if operation is None and kind == "action" and len(effects) == 1:
            operation = effects[0]
    elif kind == "conversation":
        if record.get("decision_path") == "context_decider":
            conversation_kind = DECIDER_CONVERSATION.get(str(raw.get("mode")))
        else:
            conversation_kind = next(
                (stage["conversation_kind"] for stage in reversed(stages) if stage.get("conversation_kind")),
                raw.get("conversation_kind"),
            )
    return {
        "kind": kind,
        "operation": operation,
        "effects": effects,
        "conversation_kind": conversation_kind,
        "recovery": (record.get("recovery") or {}).get("kind"),
        "decision_path": record.get("decision_path") or record.get("phase"),
    }


def operation_nodes(node: object, found: dict[str, list[Any]]) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("operation"), str) and node["operation"]:
            found.setdefault(node["operation"], []).append(node)
        for value in node.values():
            operation_nodes(value, found)
    elif isinstance(node, list):
        for value in node:
            operation_nodes(value, found)


def composed_arguments(compose: list[dict[str, Any]], trace_ids: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, list[Any]] = {}
    for record in compose:
        if str(record.get("trace")) not in trace_ids:
            continue
        situation = record.get("situation")
        try:
            situation = json.loads(situation) if isinstance(situation, str) else situation
        except json.JSONDecodeError:
            situation = None
        operation_nodes([record.get("payload"), situation], found)
    return {operation: {"seen": nodes} for operation, nodes in found.items()}


def optional(path: pathlib.Path | None, default: pathlib.Path) -> list[dict[str, Any]]:
    path = path or default
    return read_capture(path) if path.is_file() else []


def records(
    capture: pathlib.Path,
    map_path: pathlib.Path,
    out: pathlib.Path,
    audit_path: pathlib.Path | None,
    trace_path: pathlib.Path | None,
    compose_path: pathlib.Path | None,
) -> None:
    mapping = json.loads(map_path.read_text(encoding="utf-8"))
    blocks = turn_blocks(read_capture(capture / "events.jsonl"))
    segments = trace_segments(optional(trace_path, capture / "shell-trace.jsonl"))
    finals = audit_finals(optional(audit_path, capture / "turn-audit.jsonl"))
    compose = optional(compose_path, capture / "compose-audit.jsonl")
    if finals and not segments:
        print("auditoría sin traza del shell (BAXY_APP_TRACE): no se puede ligar a los turnos, se ignora")
    if len(blocks) != len(mapping["turns"]):
        print(f"la captura tiene {len(blocks)} turnos y el mapa {len(mapping['turns'])}")
    written: list[dict[str, Any]] = []
    for entry in mapping["turns"]:
        record: dict[str, Any] = {"id": entry["id"], "ordinal": entry["ordinal"], "session": entry["session"]}
        position = entry.get("block", entry["ordinal"])
        if position > len(blocks):
            record["error"] = "no_turn_in_capture"
            written.append(record)
            continue
        seen = observe(blocks[position - 1])
        record.update(
            turn_id=seen["turnId"],
            terminal=seen["terminal"],
            routes=seen["routes"],
            error_state=seen["error_state"],
        )
        if seen["request"] and seen["request"] != entry["text"]:
            record["request_seen"] = seen["request"]
        segment = segments.get(str(seen["turnId"]))
        final = next(
            (finals[request] for request in reversed(segment["decides"]) if request in finals),
            None,
        ) if segment else None
        if final is not None:
            record.update(decided(final), decision_from="audit")
        else:
            route = seen["routes"][-1] if seen["routes"] else ""
            record.update(
                kind=ROUTE_KIND.get(route),
                operation=None,
                effects=[],
                conversation_kind=None,
                decision_from="capture",
            )
        published = seen["final"] if seen["terminal"] == "published_final" else ""
        record["question"] = published if record["kind"] == "clarify" else ""
        record["reply"] = "" if record["kind"] == "clarify" else published
        if segment and segment.get("end") is not None and segment.get("start") is not None:
            record["latency_s"] = round((segment["end"] - segment["start"]) / 1000, 2)
            record["latency_from"] = "trace"
        elif "clock_latency" in seen:
            record["latency_s"] = seen["clock_latency"]
            record["latency_from"] = "clock"
        if compose and segment:
            arguments = composed_arguments(compose, segment["ids"])
            if arguments:
                record["arguments"] = arguments
                record["arguments_from"] = "compose"
        if seen["terminal"] != "published_final":
            cause = seen.get("diagnostic") or seen.get("compositionFailure") or ""
            record["error"] = f"{seen['terminal'] or 'no_terminal'}: {cause}".strip().rstrip(":")
        written.append(record)
    write_jsonl(out, written)
    print(
        f"{len(written)} registros -> {out}: publicados {sum('error' not in r for r in written)}, "
        f"decisión por auditoría {sum(r.get('decision_from') == 'audit' for r in written)}, "
        f"errores {sum('error' in r for r in written)}"
    )


# ------------------------------------------------------------------------------------------------ review


def review(run_path: pathlib.Path, set_path: pathlib.Path, map_path: pathlib.Path, out: pathlib.Path) -> None:
    rows = {row["id"]: row for row in ce.read_jsonl(set_path)}
    run = {record["id"]: record for record in ce.read_jsonl(run_path)}
    mapping = json.loads(map_path.read_text(encoding="utf-8"))
    lived: dict[int, list[dict[str, str]]] = defaultdict(list)
    packet: list[dict[str, Any]] = []
    for entry in mapping["turns"]:
        row = rows[entry["id"]]
        record = run.get(entry["id"]) or {"error": "sin registro"}
        published = record.get("question") or record.get("reply") or ""
        packet.append(
            {
                "id": row["id"],
                "session": entry["session"],
                "conv": row.get("conv"),
                "turn": row.get("turn"),
                "source": row.get("source"),
                "text": row["text"],
                "lived": list(lived[entry["session"]]),
                "gold": row["gold"],
                "args": row.get("args") or {},
                "gold_history": row.get("history") or [],
                "published": published or None,
                "error": record.get("error"),
                "decision": ce.got(record),
                "routes": record.get("routes") or [],
                "warning_hint": bool(record.get("error_state")),
                "invented": None,
                "warning": None,
                "ok": None,
                "note": "",
            }
        )
        lived[entry["session"]] += [
            {"role": "user", "content": row["text"]},
            {"role": "assistant", "content": published or f"[sin respuesta publicada: {record.get('error')}]"},
        ]
    write_jsonl(out, packet)
    print(f"{len(packet)} turnos para revisar -> {out}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    maker = sub.add_parser("turns")
    maker.add_argument("--set", required=True, type=pathlib.Path)
    maker.add_argument("--out", required=True, type=pathlib.Path)
    maker.add_argument("--map", required=True, type=pathlib.Path)
    maker.add_argument("--limit", type=int, help="units: a single or a whole conversation")
    maker.add_argument("--ids", help="row ids or conversation names, comma separated")
    reader = sub.add_parser("records")
    reader.add_argument("--capture", required=True, type=pathlib.Path)
    reader.add_argument("--map", required=True, type=pathlib.Path)
    reader.add_argument("--out", required=True, type=pathlib.Path)
    reader.add_argument("--audit", type=pathlib.Path, help="BAXY_MIND_TURN_AUDIT_PATH of the run")
    reader.add_argument("--trace", type=pathlib.Path, help="BAXY_APP_TRACE of the run")
    reader.add_argument("--compose", type=pathlib.Path, help="BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH of the run")
    packer = sub.add_parser("review")
    packer.add_argument("--run", required=True, type=pathlib.Path)
    packer.add_argument("--set", required=True, type=pathlib.Path)
    packer.add_argument("--map", required=True, type=pathlib.Path)
    packer.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.command == "turns":
        ids = [part.strip() for part in args.ids.split(",") if part.strip()] if args.ids else None
        turns(args.set, args.out, args.map, args.limit, ids)
    elif args.command == "records":
        records(args.capture, args.map, args.out, args.audit, args.trace, args.compose)
    else:
        review(args.run, args.set, args.map, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
