"""Score a contextual conductor run (a whole conversation) against its per-turn expectations.

The turns file (``artifacts/comprobaciones/C03/contexto/*.turns.jsonl``) carries, besides the ``cmd``/``text``
the conductor reads, a ``check`` object per turn:

    route:          admissible routes of the reply (conversation, result, mission-summary, clarification,
                    confirmation, error, welcome)
    ops:            "none" (no non-memory operation may complete), "any", "none_or_read" (no effect verbs),
                    "none_or_verified" (a claim of effect needs a verified operation) or a list of operation
                    prefixes of which at least one must complete
    not:            substrings that must not appear in the final (accent- and case-insensitive)
    any:            substrings of which at least one must appear
    max_latency_ms: upper bound for the turn's latency
    manual:         the rules are necessary, not sufficient: the verdict is reviewed by hand (``--verdicts``)

Evidence comes from the run's profile: ``conversation/conversation.v1.jsonl`` (route, latency, reply) and
``journal/missions.jsonl`` (operations, attributed to a turn by timestamp).

usage: score_context_turns.py <turns.jsonl> <profile dir> [--verdicts overrides.json] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import unicodedata

EFFECT_VERBS = ("set", "mute", "close", "open", "play", "stop", "search", "send", "install", "launch", "click")


def fold(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(ch) != "Mn"
    )


def read_jsonl(path: pathlib.Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def load_turns(path: pathlib.Path) -> list[dict]:
    return [row for row in read_jsonl(path) if row.get("cmd", "turn") == "turn"]


def load_conversation(profile: pathlib.Path) -> list[tuple[dict, dict | None]]:
    rows = read_jsonl(profile / "conversation" / "conversation.v1.jsonl")
    pairs: list[tuple[dict, dict | None]] = []
    for index, row in enumerate(rows):
        if row.get("role") != "user":
            continue
        reply = rows[index + 1] if index + 1 < len(rows) and rows[index + 1].get("role") == "assistant" else None
        pairs.append((row, reply))
    return pairs


def load_operations(profile: pathlib.Path) -> list[dict]:
    ops = []
    for row in read_jsonl(profile / "journal" / "missions.jsonl"):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
        operation = payload.get("operation")
        if not operation or str(operation).startswith("memory."):
            continue
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        ops.append(
            {
                "utc": str(payload.get("timestampUtc") or ""),
                "operation": str(operation),
                "phase": str(payload.get("phase") or ""),
                "status": response.get("status"),
                "verified": response.get("verified"),
            }
        )
    return ops


def attribute(ops: list[dict], pairs: list[tuple[dict, dict | None]]) -> list[list[dict]]:
    starts = [pair[0].get("utc") or "" for pair in pairs]
    buckets: list[list[dict]] = [[] for _ in pairs]
    for op in ops:
        owner = None
        for index, start in enumerate(starts):
            if start and op["utc"] >= start:
                owner = index
        if owner is not None:
            buckets[owner].append(op)
    return buckets


def completed(ops: list[dict]) -> list[dict]:
    return [op for op in ops if op["phase"] == "completed"]


def evaluate(turn: dict, user: dict | None, reply: dict | None, ops: list[dict]) -> tuple[bool, list[str]]:
    check = turn.get("check") or {}
    reasons: list[str] = []
    if reply is None:
        return False, ["sin respuesta"]
    text = fold(str(reply.get("text") or ""))
    route = str(reply.get("route") or "")
    done = completed(ops)
    names = [op["operation"] for op in done]
    if check.get("route") and route not in check["route"]:
        reasons.append(f"ruta {route}")
    rule = check.get("ops", "any")
    if rule == "none" and names:
        reasons.append("operaciones " + ",".join(names))
    elif rule == "none_or_read":
        effects = [name for name in names if any(verb in name.split(".")[-1] for verb in EFFECT_VERBS)]
        if effects:
            reasons.append("efecto " + ",".join(effects))
    elif isinstance(rule, list):
        if not any(name.startswith(prefix) for name in names for prefix in rule):
            reasons.append("falta operación " + "|".join(rule) + (" (hubo " + ",".join(names) + ")" if names else ""))
    verified_effect = any(op.get("verified") for op in done if not op["operation"].startswith("memory."))
    claim_exempt = rule == "none_or_verified" and verified_effect
    for forbidden in check.get("not") or []:
        if fold(forbidden) in text and not claim_exempt:
            reasons.append(f"dice «{forbidden}»")
    if check.get("any") and not any(fold(needed) in text for needed in check["any"]):
        reasons.append("no dice " + "|".join(check["any"]))
    latency = reply.get("latency_ms")
    if check.get("max_latency_ms") and latency is not None:
        try:
            if int(latency) > int(check["max_latency_ms"]):
                reasons.append(f"latencia {latency} ms")
        except ValueError:
            pass
    return not reasons, reasons


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("turns")
    parser.add_argument("profile")
    parser.add_argument("--verdicts", help="JSON {turn number: 'bien'|'mal'} overriding the reviewed turns")
    parser.add_argument("--json", help="write the per-turn table here")
    args = parser.parse_args(argv)

    turns = load_turns(pathlib.Path(args.turns))
    profile = pathlib.Path(args.profile)
    pairs = load_conversation(profile)
    buckets = attribute(load_operations(profile), pairs)
    overrides: dict[str, str] = {}
    if args.verdicts:
        overrides = json.loads(pathlib.Path(args.verdicts).read_text(encoding="utf-8"))

    table = []
    good = 0
    reviewed = 0
    for index, turn in enumerate(turns):
        user, reply = pairs[index] if index < len(pairs) else (None, None)
        ops = buckets[index] if index < len(buckets) else []
        ok, reasons = evaluate(turn, user, reply, ops)
        number = int(turn.get("n") or index + 1)
        verdict = "bien" if ok else "mal"
        source = "reglas"
        if str(number) in overrides:
            verdict = overrides[str(number)]
            source = "revisión"
        elif (turn.get("check") or {}).get("manual") and ok:
            verdict = "revisar"
        if verdict == "bien":
            good += 1
        if verdict == "revisar":
            reviewed += 1
        entry = {
            "n": number,
            "cls": turn.get("cls"),
            "text": turn.get("text"),
            "expected": turn.get("expected"),
            "route": (reply or {}).get("route"),
            "latency_ms": (reply or {}).get("latency_ms"),
            "reply": (reply or {}).get("text"),
            "ops": [f"{op['operation']}:{op['phase']}" + ("/v" if op.get("verified") else "") for op in ops],
            "verdict": verdict,
            "source": source,
            "reasons": reasons,
        }
        table.append(entry)
        flag = {"bien": "OK ", "mal": "MAL", "revisar": "?? "}[verdict]
        print(f"{number:02d} {flag} [{entry['cls']}] {turn.get('text')}")
        print(f"      → [{entry['route']}] {' '.join(str(entry['reply']).split())[:220]}")
        if entry["ops"]:
            print(f"      ops: {', '.join(entry['ops'])}")
        if reasons:
            print(f"      por: {'; '.join(reasons)}")
    print(f"\nturnos bien {good}/{len(turns)}" + (f" (+{reviewed} por revisar)" if reviewed else "") + f"; respuestas {len(pairs)}")
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps({"good": good, "total": len(turns), "pending_review": reviewed, "turns": table}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
