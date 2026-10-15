"""End-to-end bench: the real product (one conductor for the whole bank) judged by the state of the world.

usage: py -3.12 -X utf8 scripts/renew/bench_e2e.py <label> --cases FILE [--only E001,E002]
Cases and their PowerShell setup/oracle/cleanup follow <banks>/e2e/README.md. Per case: setup, a new conversation, the
turns (a confirmation BAXY asks for is answered with the case's reply as the person's words; a barge-in turn is sent
N ms after the previous answer started to sound), the replies and utterances written for the oracles, the oracles,
then the cleanup. Writes <banks>/runs/<label>-e2e/results.jsonl (summary first) beside the conductor's events.jsonl.
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANKS = Path(os.environ.get("BAXY_RENEW_BANKS", r"F:\BAXYeval\renew_v1"))


def ps_file(path: Path, lines: list[str]) -> None:
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8-sig")


def run_ps(path: Path, env: dict, timeout: float) -> tuple[int, str]:
    try:
        done = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                              timeout=timeout)
        return done.returncode, (done.stdout or "") + ("\n" + done.stderr if done.stderr.strip() else "")
    except subprocess.TimeoutExpired:
        return 124, "timeout"


class Events:
    """Reads the conductor's events.jsonl as it grows."""

    def __init__(self, path: Path) -> None:
        self.path, self.offset, self.all = path, 0, []

    def poll(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            data = handle.read()
        end = data.rfind(b"\n")
        if end < 0:
            return []
        self.offset += end + 1
        fresh = [json.loads(line) for line in data[:end].decode("utf-8").splitlines() if line.strip()]
        self.all.extend(fresh)
        return fresh

    def wait(self, predicate, timeout: float) -> dict | None:
        deadline = time.monotonic() + timeout
        seen = len(self.all)
        while time.monotonic() < deadline:
            self.poll()
            for event in self.all[seen:]:
                if predicate(event):
                    return event
            seen = len(self.all)
            time.sleep(0.05)
        return None


class Conductor:
    def __init__(self, run_dir: Path, profile: Path) -> None:
        self.commands = run_dir / "commands"
        self.commands.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
        self.events = Events(run_dir / "events.jsonl")
        self.process = subprocess.Popen(
            ["cmd", "/c", str(ROOT / "scripts" / "run_renew.cmd"), "--conductor", "--command-dir", str(self.commands),
             "--capture", str(run_dir), "--profile", str(profile), "--timeout-ms", "300000"],
            cwd=str(ROOT), stdout=(run_dir / "console.txt").open("w", encoding="utf-8"), stderr=subprocess.STDOUT)

    def send(self, command: dict) -> int:
        self.sequence += 1
        target = self.commands / f"{self.sequence:05d}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(command, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)
        return len(self.events.all)

    def close(self) -> None:
        self.send({"exit": True})
        try:
            self.process.wait(120)
        except subprocess.TimeoutExpired:
            self.process.kill()


def run_turn(conductor: Conductor, command: dict, timeout: float) -> list[dict]:
    """Sends one turn and returns its events up to its command.done (or what came before the timeout)."""
    start = conductor.send(command)
    done = conductor.events.wait(lambda e: e["type"] == "command.done", timeout)
    conductor.events.poll()
    events = conductor.events.all[start:]
    if done is None:
        events.append({"type": "bench.timeout"})
    return events


def norm(text: str) -> str:
    return " ".join((text or "").split())


def judge_case(case: dict, conductor: Conductor, case_dir: Path, env_base: dict) -> dict:
    lib_env = dict(env_base)
    started = time.monotonic()
    budget = float(case.get("timeout_s") or 90)
    setup = case_dir / "setup.ps1"
    ps_file(setup, case.get("setup") or [])
    code, out = run_ps(setup, lib_env, 300)
    if code != 0:
        result = {"id": case["id"], "area": case.get("area"), "kind": case.get("kind"), "ok": False,
                  "status": "setup_fallido", "detail": out[-800:]}
        cleanup = case_dir / "cleanup.ps1"
        ps_file(cleanup, case.get("cleanup") or [])
        run_ps(cleanup, lib_env, 300)
        return result

    run_turn(conductor, {"session": "new"}, 30)
    replies, speech, turn_events, turn_from = [], [], [], []
    for number, turn in enumerate(case.get("turns") or [], start=1):
        turn_from.append(len(conductor.events.all))
        if turn.get("barge_in_after_ms") is not None:
            # Sent N ms after the previous answer started to sound; the previous turn must have sounded.
            prior = next((e for e in reversed(conductor.events.all) if e["type"] == "speech.start"), None)
            if prior is None:
                conductor.events.wait(lambda e: e["type"] == "speech.start", 15)
            time.sleep(float(turn["barge_in_after_ms"]) / 1000)
        left = max(5.0, budget - (time.monotonic() - started))
        events = run_turn(conductor, {"text": turn["text"]}, left)
        end = next((e for e in events if e["type"] == "turn.end"), {})
        asked = bool(end.get("pendingConfirmation"))
        confirmation_text = ""
        if asked:
            confirmation_text = next((e["body"] for e in reversed(events)
                                      if e["type"] == "message" and e["speaker"] == "baxy"), "")
        answered = turn.get("reply_if_confirmation") if asked else None
        if asked and answered:
            left = max(5.0, budget - (time.monotonic() - started))
            events += run_turn(conductor, {"text": answered}, left)
        finals = [e["body"] for e in events if e["type"] == "message" and e["speaker"] == "baxy"]
        final = finals[-1] if finals and (not asked or answered) else ("" if asked and not answered else
                                                                      (finals[-1] if finals else ""))
        replies.append({"turn": number, "text": final, "asked_confirmation": asked,
                        "confirmation_text": confirmation_text, "answered": answered})
        turn_events.append(events)

    # Let the last answer finish sounding before the voice rule and the oracles read the world.
    last_start = max((i for i, e in enumerate(conductor.events.all) if e["type"] == "speech.start"), default=None)
    if last_start is not None and not any(e["type"] == "speech.end" for e in conductor.events.all[last_start:]):
        conductor.events.wait(lambda e: e["type"] == "speech.end", 30)
    conductor.events.poll()

    # Utterances: each speech.start of a turn (until the next turn began) with its end; cancelled when the person
    # spoke over it.
    every = conductor.events.all
    bounds = turn_from + [len(every)]
    for number in range(1, len(turn_from) + 1):
        window = range(bounds[number - 1], bounds[number])
        turn_start = next((every[i]["t_ms"] for i in window if every[i]["type"] == "turn.start"), None)
        for i in window:
            event = every[i]
            if event["type"] != "speech.start":
                continue
            stop = next((e for e in every[i + 1:] if e["type"] == "speech.end"), None)
            stop_ms = stop["t_ms"] if stop else 10**12
            interrupted = any(e["type"] == "message" and e["speaker"] == "person" and event["t_ms"] <= e["t_ms"] <= stop_ms
                              for e in every[i + 1:])
            asked = replies[number - 1]["confirmation_text"]
            kind = "confirmation" if asked and norm(event.get("text")) == norm(asked) else "final"
            speech.append({"turn": number, "kind": kind, "spoken": True, "spoken_text": event.get("text", ""),
                           "first_audio_ms": event["t_ms"] - turn_start if turn_start is not None else None,
                           "completed": stop is not None and not interrupted, "cancelled": interrupted,
                           "stop_latency_ms": None})

    (case_dir / "replies.json").write_text(json.dumps(replies, ensure_ascii=False), encoding="utf-8")
    (case_dir / "speech.json").write_text(json.dumps(speech, ensure_ascii=False), encoding="utf-8")
    lib_env["BAXY_E2E_REPLIES"] = str(case_dir / "replies.json")
    lib_env["BAXY_E2E_SPEECH"] = str(case_dir / "speech.json")
    oracles = []
    for index, oracle in enumerate(case.get("oracle") or []):
        script = case_dir / f"oracle{index}.ps1"
        ps_file(script, [oracle["ps"]])
        code, out = run_ps(script, lib_env, 240)
        matched = code == 0 and re.search(oracle["expect_regex"], out.strip()) is not None
        oracles.append({"expect": oracle["expect_regex"], "ok": matched, "out": out.strip()[:400]})

    spoken_ok = True
    if case.get("must_speak"):
        for reply in replies:
            if not reply["text"]:
                continue
            said = [s for s in speech if s["turn"] == reply["turn"] and norm(s["spoken_text"]) == norm(reply["text"])]
            barged = any(t.get("barge_in_after_ms") is not None for t in (case.get("turns") or [])[reply["turn"]:])
            spoken_ok &= bool(said) and (barged or any(s["completed"] for s in said))
    cleanup = case_dir / "cleanup.ps1"
    ps_file(cleanup, case.get("cleanup") or [])
    _, cleanup_out = run_ps(cleanup, lib_env, 300)
    leftovers = [line for line in cleanup_out.splitlines() if line.startswith("LEFTOVER")]
    ok = all(o["ok"] for o in oracles) and spoken_ok
    first_audio = [s["first_audio_ms"] for s in speech if s["kind"] == "final" and s["first_audio_ms"] is not None]
    return {"id": case["id"], "area": case.get("area"), "kind": case.get("kind"), "ok": ok,
            "status": "ok" if ok else "fallo", "spoken_ok": spoken_ok, "oracles": oracles, "replies": replies,
            "first_audio_ms": first_audio, "leftovers": leftovers,
            "steps": [{"op": e["operation"], "status": e["status"], "verified": e["verified"]}
                      for events in turn_events for e in events if e["type"] == "step"],
            "seconds": round(time.monotonic() - started, 1)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("label")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    run_dir = BANKS / "runs" / f"{args.label}-e2e"
    run_dir.mkdir(parents=True, exist_ok=True)
    # A profile of its own, empty at the start of the run (notes, memory and todo list are disposable); on C: because
    # the private store needs NTFS permissions.
    profile = Path(os.environ["LOCALAPPDATA"]) / "BAXY" / f"bench-{args.label}-{int(time.time())}"
    conductor = Conductor(run_dir, profile)
    ready = conductor.events.wait(lambda e: e["type"] in {"runtime", "terminal"}, 300)
    if not ready or not ready.get("mindReady"):
        print(json.dumps({"error": "conductor_not_ready", "event": ready}), flush=True)
        conductor.close()
        sys.exit(2)
    env_base = dict(os.environ)
    rows = []
    for case in cases:
        case_dir = run_dir / case["id"]
        case_dir.mkdir(exist_ok=True)
        row = judge_case(case, conductor, case_dir, env_base)
        rows.append(row)
        print(f"{row['id']} {row['area']:<12} {'ok ' if row['ok'] else 'BAD'} {row['status']} {row.get('seconds')}s "
              f"{[o['ok'] for o in row.get('oracles', [])]} voz={row.get('spoken_ok')}", flush=True)
    conductor.close()
    by_area: dict[str, list[int]] = {}
    for row in rows:
        tally = by_area.setdefault(str(row["area"]), [0, 0])
        tally[0] += row["ok"]
        tally[1] += 1
    audio = [ms for row in rows for ms in row.get("first_audio_ms") or []]
    summary = {"label": args.label, "cases": args.cases, "ok": sum(r["ok"] for r in rows), "n": len(rows),
               "accuracy": round(sum(r["ok"] for r in rows) / max(1, len(rows)), 4), "areas": by_area,
               "first_audio_p50_ms": statistics.median(audio) if audio else None,
               "setup_failed": [r["id"] for r in rows if r["status"] == "setup_fallido"]}
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as out:
        out.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
