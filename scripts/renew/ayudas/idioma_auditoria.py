"""Offline audit of the aid «check_language» (rule «language» of answer_check, 2026-10-25): every reply of the c3-*-e2e,
ho6-*-e2e-e2e and ho7-*-s1-e2e runs (events.jsonl: each turn's words as the person said them, its calls with their
results, BAXY's replies), read by the check as the mind reads it, with the turn's calls as its receipts. It prints the
requests it reads as English (each should be English, never Spanglish), the replies it flags (each should be Spanish),
and the replies to English requests it does not flag that hold some Spanish, so each can be read by hand.
usage: py -3.12 -X utf8 idioma_auditoria.py [--runs D:/BAXYeval/renew_v1/runs] [--src src]
"""
import argparse
import json
import re
import sys
from pathlib import Path


def runs(root: Path):
    for path in sorted(root.iterdir()):
        name = path.name
        if "fals" in name or not path.is_dir():  # never a falsehood transcript
            continue
        if (re.fullmatch(r"c3-.*-e2e", name) or re.fullmatch(r"ho6-.*-e2e-e2e", name)
                or re.fullmatch(r"ho7-.*-s1-e2e", name)) and (path / "events.jsonl").is_file():
            yield path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", default="D:/BAXYeval/renew_v1/runs")
    parser.add_argument("--src", default=str(Path(__file__).resolve().parents[3] / "src"))
    args = parser.parse_args()
    sys.path.insert(0, args.src)
    from baxy_mind.answer_check import check, request_is_english  # noqa: PLC0415
    replies = to_english = 0
    english: dict[str, int] = {}
    rows, missed = [], []
    for run in runs(Path(args.runs)):
        case_of = {}
        if (run / "results.jsonl").is_file():
            for line in (run / "results.jsonl").open(encoding="utf-8"):
                row = json.loads(line)
                for reply in row.get("replies") or []:
                    case_of.setdefault((reply.get("text") or "").strip(), row.get("id"))
        turn = None
        case = None
        for line in (run / "events.jsonl").open(encoding="utf-8"):
            event = json.loads(line)
            kind = event["type"]
            if kind == "turn.start":
                turn = {"text": (event.get("input") or {}).get("text") or "", "steps": [], "replies": []}
            elif kind == "step" and turn is not None:
                turn["steps"].append(event)
            elif kind == "message" and event.get("speaker") == "baxy" and turn is not None:
                turn["replies"].append(event.get("body") or "")
            elif kind == "turn.end" and turn is not None:
                receipts = [{"op": s.get("operation"), "tool": str(s.get("operation")).replace(".", "_"),
                             "arguments": s.get("arguments") or {}, "observation": s.get("observation") or "",
                             "outcome": "", "completed": s.get("status") == "completed", "read": False}
                            for s in turn["steps"]]
                is_english = request_is_english(turn["text"])
                for body in turn["replies"]:
                    replies += 1
                    case = case_of.get(body.strip(), case)
                    where = f"{run.name} {case}"
                    if is_english:
                        to_english += 1
                        english[turn["text"]] = english.get(turn["text"], 0) + 1
                    found = [f for f in check(body, turn["text"], receipts, None) if f["rule"] == "language"]
                    if found:
                        rows.append((where, turn["text"], body))
                    elif is_english and re.search(r"[áéíóúñ¿¡]|\b(?:el|la|los|las|que|de|en|con|por)\b", body):
                        missed.append((where, turn["text"], body))
                turn = None
    print(f"{replies} replies; {to_english} to {len(english)} requests read as English; flagged {len(rows)}")
    print("\nRequests read as English (replies):")
    for text, count in sorted(english.items()):
        print(f"  {count:3d}  {text}")
    print(f"\nFlagged: {len(rows)}")
    for where, text, body in rows:
        print(f"FLAG {where} | {text[:60]} || {body[:150]}")
    print(f"\nNot flagged, to English, with some Spanish: {len(missed)}")
    for where, text, body in missed:
        print(f"  -  {where} | {text[:60]} || {body[:150]}")


main()
