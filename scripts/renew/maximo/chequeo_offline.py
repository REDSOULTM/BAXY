"""Aid «answer_check» measured offline (al máximo, lever 3): the checker read over the stored practice transcripts, no
GPU and no model. Each BAXY line is checked against the results of its turn that came before it, as the mind checks it,
and the session's calls up to it.

Practice only: the falsehood runs F001-F020 and the e2e runs E001-E030 of F:\\BAXYeval\\renew_v1\\runs. Holdout runs
(ho4-*, hv4-*, ho5-*, hv5-*, final-*: F101+/E101+) and the owner's real use are never opened. Labels: the hand
verdicts of pc-t2 (F:\\BAXYeval\\renew_v4\\fals\\juicio_mano.json: clear and doubtful phrases) and the 35B judge's
per-line votes (results.jsonl) where a run has them; every flag is written out for reading by hand.

    py -I scripts/renew/maximo/chequeo_offline.py [--out DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from baxy_mind.answer_check import check  # noqa: E402
from baxy_mind.mind import COMPLETED_OUTCOMES, READ_RISKS, _outcome  # noqa: E402

RUNS = Path("F:/BAXYeval/renew_v1/runs")
HAND = Path("F:/BAXYeval/renew_v4/fals/juicio_mano.json")
CATALOG = Path("F:/BAXYeval/renew_v4/catalog-final.json")
SKIP = ("ho4-", "hv4-", "ho5-", "hv5-", "final-", "uso-real")


def _risks() -> dict[str, str]:
    try:
        return {c["name"]: str(c.get("risk") or "") for c in json.loads(CATALOG.read_text("utf-8"))["capabilities"]}
    except (OSError, KeyError, json.JSONDecodeError):
        return {}


def _normal(step: dict) -> str:
    """The observation as the mind reads it today: an old result without «status» (the schema before 2026-10-17) gets
    the step's own status and verification, so a completed call is not read as failed."""
    raw = step.get("observation") or ""
    try:
        facts = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return json.dumps({"status": step.get("status") or "failed", "error": step.get("error"), "text": raw},
                          ensure_ascii=False)
    if isinstance(facts, dict) and "status" not in facts:
        facts["status"] = step.get("status") or ("completed" if facts.get("succeeded") else "failed")
        if facts["status"] == "completed" and "verification" not in facts:
            facts["verification"] = "readback" if step.get("verified") else "none"
        if step.get("error") and "error" not in facts:
            facts["error"] = step["error"]
        return json.dumps(facts, ensure_ascii=False)
    return raw


def _receipt(step: dict, risks: dict[str, str]) -> dict:
    op = str(step.get("operation") or "?")
    observation = _normal(step)
    outcome = _outcome(observation, read=risks.get(op) in READ_RISKS)
    read = risks.get(op) == "read_only"  # as the mind tells the checker: only a read_only call never acted
    return {"op": op, "tool": op.replace(".", "_"), "arguments": step.get("arguments") or {},
            "observation": observation, "outcome": outcome, "completed": outcome.startswith(COMPLETED_OUTCOMES),
            "read": read}


def _conversations():
    """(bank, run, case, turns) with each turn's person text and its ordered steps and BAXY lines."""
    for d in sorted(glob.glob(str(RUNS / "*falsedades"))):
        name = os.path.basename(d)
        if name.startswith(SKIP) or not os.path.isfile(f"{d}/transcripts.json"):
            continue
        for conv in json.load(open(f"{d}/transcripts.json", encoding="utf-8")):
            if re.fullmatch(r"F0\d\d", conv.get("id", "")):
                yield "fals", name, conv["id"], [{"person": " ".join(t.get("person") or []),
                                                  "ordered": t.get("ordered") or []} for t in conv.get("turns") or []]
    for d in sorted(glob.glob(str(RUNS / "*-e2e"))):
        name = os.path.basename(d)
        if name.startswith(SKIP) or not os.path.isfile(f"{d}/events.jsonl"):
            continue
        ids = []
        if os.path.isfile(f"{d}/results.jsonl"):
            ids = [json.loads(line).get("id") for line in open(f"{d}/results.jsonl", encoding="utf-8")
                   if line.startswith('{"id"')]
        sessions, turn = [], None
        for line in open(f"{d}/events.jsonl", encoding="utf-8", errors="replace"):
            # PC-Q (2026-10-25): a run killed while the conductor wrote ends in half a line; it stopped the whole check.
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e["type"] == "command.done" and e.get("session") == "new":
                sessions.append([])
                turn = None
            elif e["type"] == "turn.start":
                if not sessions:
                    sessions.append([])
                turn = {"person": (e.get("input") or {}).get("text") or "", "ordered": []}
                sessions[-1].append(turn)
            elif turn is not None and e["type"] == "step":
                turn["ordered"].append({"kind": "step", "observed": e.get("observation"),
                                        **{k: e.get(k) for k in ("operation", "arguments", "status", "verified",
                                                                 "error")}})
            elif turn is not None and e["type"] == "message" and e.get("speaker") == "baxy":
                turn["ordered"].append({"kind": "baxy", "text": e.get("body") or "", "route": e.get("route")})
        sessions = [s for s in sessions if s]
        for i, session in enumerate(sessions):
            case = ids[i] if len(ids) == len(sessions) else f"S{i:02d}"
            if re.fullmatch(r"E0\d\d|S\d\d", str(case)):
                yield "e2e", name, case, session


def _labels() -> tuple[dict, dict]:
    hand: dict[tuple[str, str], dict] = {}
    if HAND.is_file():
        for conv in json.loads(HAND.read_text("utf-8")).get("conversaciones") or []:
            hand[(conv["corrida"], conv["caso"])] = conv
    judge: dict[tuple[str, str, str], bool] = {}
    for f in glob.glob(str(RUNS / "*falsedades" / "results.jsonl")):
        run = os.path.basename(os.path.dirname(f))
        if run.startswith(SKIP):
            continue
        for line in open(f, encoding="utf-8"):
            row = json.loads(line)
            if "id" in row and isinstance(row.get("line"), str):
                judge[(run, row["id"], row["line"].strip())] = bool(row.get("falsedad"))
    return hand, judge


def _same(a: str, b: str) -> bool:
    def fold(s: str) -> str:
        return re.sub(r"\W+", " ", s.lower()).strip()
    a, b = fold(a), fold(b)
    return bool(a) and bool(b) and (a in b or b in a)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    risks = _risks()
    hand, judge = _labels()
    rows, timings = [], []
    for bank, run, case, turns in _conversations():
        session: list[tuple[str, bool, bool]] = []
        for index, turn in enumerate(turns):
            receipts = []
            for item in turn["ordered"]:
                if item.get("kind") == "step":
                    receipt = _receipt({**item, "observation": item.get("observed")}, risks)
                    receipts.append(receipt)
                    session.append((receipt["op"], receipt["completed"], receipt["read"]))
                elif item.get("kind") == "baxy" and (item.get("text") or "").strip():
                    started = time.perf_counter()
                    found = check(item["text"], turn["person"], list(receipts), list(session))
                    timings.append((time.perf_counter() - started) * 1000)
                    label = None
                    conv = hand.get((run, case))
                    if conv is not None:
                        label = ("clara" if any(_same(c["frase"], item["text"]) for c in conv["claras"])
                                 else "dudosa" if any(_same(c["frase"], item["text"]) for c in conv["dudosas"])
                                 else "limpia")
                    rows.append({"bank": bank, "run": run, "case": case, "turn": index, "person": turn["person"],
                                 "line": item["text"], "hand": label,
                                 "judge": judge.get((run, case, item["text"].strip())), "flags": found,
                                 "steps": [f"{r['tool']} → {r['outcome']}" for r in receipts]})
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "chequeo_lineas.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
    flagged = [r for r in rows if r["flags"]]
    print(f"líneas {len(rows)} (fals {sum(r['bank'] == 'fals' for r in rows)}, "
          f"e2e {sum(r['bank'] == 'e2e' for r in rows)}); marcadas {len(flagged)} "
          f"({100 * len(flagged) / max(1, len(rows)):.1f} %)")
    print("por regla:", dict(Counter(f["rule"] for r in flagged for f in r["flags"])))
    gold = [r for r in rows if r["hand"]]
    for label in ("clara", "dudosa", "limpia"):
        group = [r for r in gold if r["hand"] == label]
        print(f"a mano pc-t2 {label}: {sum(bool(r['flags']) for r in group)}/{len(group)} marcadas")
    judged = [r for r in rows if r["judge"] is not None]
    print(f"juez 35B falsa: {sum(bool(r['flags']) for r in judged if r['judge'])}/{sum(r['judge'] for r in judged)}; "
          f"juez no falsa marcadas: {sum(bool(r['flags']) for r in judged if not r['judge'])}/"
          f"{sum(not r['judge'] for r in judged)}")
    timings.sort()
    if not timings:  # PC-Q: no run to read (the notebook, or a folder with none) failed here with IndexError
        print("ms por línea: ninguna línea leída")
        return 0
    print(f"ms por línea: p50 {timings[len(timings) // 2]:.2f}, p99 {timings[int(len(timings) * 0.99)]:.2f}, "
          f"max {timings[-1]:.2f}")
    by_line = defaultdict(list)
    for r in flagged:
        by_line[(r["case"], r["line"])].append(r["run"])
    print(f"líneas marcadas distintas: {len(by_line)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
