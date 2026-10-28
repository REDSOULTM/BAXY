"""Offline audit of the aid «check_denial» (rule «denial» of answer_check, 2026-10-25): every reply of the c3-*-e2e and
ho6-*-e2e-e2e runs (events.jsonl: each turn's words, its calls with their results, BAXY's replies), read by the check as
the mind reads it: the turn's calls as its receipts, the run's catalog (mente/catalog.configure.json, with the English
descriptions the model reads; the full catalog of the mind's data when the run kept none) and the session's earlier calls
with the status of their results. It prints the replies it flags, and the replies of turns with no call that deny an act
in any words (a wide net, by hand) that it does not flag, so each can be read as a false denial or a true limit; with the
mind's trace, the decision's p_call of each flagged turn (System One's layer 0 reads it).
usage: py -3.12 -X utf8 niego_auditoria.py [--runs D:/BAXYeval/renew_v1/runs] [--src src]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wire_names import wire  # noqa: E402  (scripts/renew/wire_names.py)

WIDE = re.compile(r"\bno (?:puedo|podria|tengo (?:acceso|permiso|la capacidad|forma|manera|como)|es posible|"
                  r"me es posible|soy capaz|se puede)|\bi (?:can.?t|cannot|don.?t have)|\bno hay (?:forma|manera)"
                  r"|fuera de mi alcance|\bno tengo (?:una )?herramienta")


def runs(root: Path):
    for path in sorted(root.iterdir()):
        name = path.name
        if "fals" in name or not path.is_dir():  # never a falsehood transcript
            continue
        if (re.fullmatch(r"c3-.*-e2e", name) or re.fullmatch(r"ho6-.*-e2e-e2e", name)) \
                and (path / "events.jsonl").is_file():
            yield path


def status(observation: str | None) -> str:
    try:
        facts = json.loads(observation or "")
    except json.JSONDecodeError:
        return "unknown"
    return str(facts.get("status") or "unknown") if isinstance(facts, dict) else "unknown"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", default="D:/BAXYeval/renew_v1/runs")
    parser.add_argument("--src", default=str(Path(__file__).resolve().parents[3] / "src"))
    args = parser.parse_args()
    sys.path.insert(0, args.src)
    from baxy_mind.answer_check import _fold, check  # noqa: PLC0415
    english = json.loads((Path(args.src) / "baxy_mind" / "data" / "tool_descriptions.en.v1.json")
                         .read_text(encoding="utf-8"))["tools"]
    replies = flagged = no_call = 0
    rows, missed = [], []
    for run in runs(Path(args.runs)):
        kept = run / "mente" / "catalog.configure.json"
        names = ([c["name"] for c in json.loads(kept.read_text(encoding="utf-8"))["capabilities"]]
                 if kept.is_file() else list(english))
        catalog = {n: english.get(n, "") for n in names}
        p_calls: dict[str, list[float]] = {}
        trace = run / "mente" / "turns.jsonl"
        if trace.is_file():
            for line in trace.open(encoding="utf-8"):
                row = json.loads(line)
                if row.get("stage") == "turn.decide" and row.get("doubt"):
                    p_calls.setdefault(row.get("text"), []).append(row["doubt"].get("p_call"))
        case_of = {}
        if (run / "results.jsonl").is_file():
            for line in (run / "results.jsonl").open(encoding="utf-8"):
                row = json.loads(line)
                for reply in row.get("replies") or []:
                    case_of.setdefault((reply.get("text") or "").strip(), row.get("id"))
        tries: list[tuple[str, str]] = []
        turn = None
        case = None
        for line in (run / "events.jsonl").open(encoding="utf-8"):
            event = json.loads(line)
            kind = event["type"]
            if kind == "command.done" and event.get("session") == "new":
                tries = []
            elif kind == "turn.start":
                turn = {"text": (event.get("input") or {}).get("text") or "", "steps": [], "replies": []}
            elif kind == "step" and turn is not None:
                turn["steps"].append(event)
            elif kind == "message" and event.get("speaker") == "baxy" and turn is not None:
                turn["replies"].append(event.get("body") or "")
            elif kind == "turn.end" and turn is not None:
                receipts = [{"op": s.get("operation"), "tool": wire(str(s.get("operation"))),
                             "arguments": s.get("arguments") or {}, "observation": s.get("observation") or "",
                             "outcome": "", "completed": s.get("status") == "completed", "read": False}
                            for s in turn["steps"]]
                for body in turn["replies"]:
                    replies += 1
                    case = case_of.get(body.strip(), case)
                    found = [f for f in check(body, turn["text"], receipts, None, catalog=catalog, tries=tries)
                             if f["rule"] == "denial"]
                    where = f"{run.name} {case}"
                    if found:
                        flagged += 1
                        rows.append((where, turn["text"], body, found[0]["fact"][:90], p_calls.get(turn["text"])))
                    elif not receipts and WIDE.search(_fold(body)):
                        missed.append((where, turn["text"], body))
                    no_call += not receipts
                tries += [(s.get("operation"), status(s.get("observation"))) for s in turn["steps"]]
                turn = None
    print(f"{replies} replies, {no_call} of turns with no call; flagged {flagged}")
    for where, text, body, fact, p_call in rows:
        print(f"FLAG {where} | {text[:60]} || {body[:150]} -> {fact} p_call={p_call}")
    print(f"\nNot flagged, no call, denying in some words: {len(missed)}")
    for where, text, body in missed:
        print(f"  -  {where} | {text[:60]} || {body[:150]}")


main()
