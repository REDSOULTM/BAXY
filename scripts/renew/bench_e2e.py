"""End-to-end bench: the real product (one conductor for the whole bank) judged by the state of the world.

usage: py -3.12 -X utf8 scripts/renew/bench_e2e.py <label> --cases FILE [--only E001,E002]
Cases and their PowerShell setup/oracle/cleanup follow <banks>/e2e/README.md. Per case: setup, a new conversation, the
turns (a confirmation BAXY asks for is answered with the case's reply as the person's words; a barge-in turn is sent
N ms after the previous answer started to sound), the replies and utterances written for the oracles, the oracles,
then the cleanup. Writes <banks>/runs/<label>-e2e/results.jsonl (summary first) beside the conductor's events.jsonl.
Speed per turn, from its text: first_audio_ms is its first sound, whatever was said first (the notice of a silent turn
counts, it is sound: the goal's «3 s en silencio»); first_response_audio_ms is the first sound of its response. The
notice's utterance is of the bank's kind "progress" (the conductor marks it notice). A turn whose response never
sounded is listed in turns_unanswered (case#turn) and counts as the slowest in first_response_audio_p50_all_turns_ms,
beside the median of the turns that sounded (first_response_audio_p50_ms).
Isolation from the owner (Isolation, with lib/bench.ps1): the run is VOID (exit 3, results.jsonl says why) when a window
of a target app the bench did not open exists, before it starts or before any case; around each case the profile is
snapshot, and the files the case created outside the sandbox are moved to <case>/profile-quarantine (the owner's own
files are only reported: summary profile_review). The owner's saved Notepad tabs are set aside and put back.
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_meta  # noqa: E402

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


# Isolation from the owner (w6-banco, 2026-10-23): the PC e2e of 2026-10-22 typed into the owner's own unsaved Notepad
# tab (an app.open of Notepad reused the owner's window) and benches left files in the owner's home. The bench library
# (<banks>/e2e/lib/bench.ps1, «isolation» section) does the work; the runner calls it around every case, whatever the
# case's own snippets do, so a sealed bank is covered without opening it.
LIB = BANKS / "e2e" / "lib" / "bench.ps1"
VOID_EXIT = 3


def void_reason(code: int, out: str) -> str | None:
    """None when the precondition passed (BENCH-READY), else why the bench is VOID: the foreign windows, or the check
    itself failing (a bench that cannot tell whose windows are open does not start)."""
    lines = [line.strip() for line in out.splitlines() if line.strip().startswith("BENCH-VOID")]
    if lines:
        return "; ".join(lines)
    if code == 0 and "BENCH-READY" in out:
        return None
    return f"precondition_failed (exit {code}): {out.strip()[-300:]}"


def target_windows(out: str) -> set[int]:
    return {int(line.split()[1]) for line in out.splitlines()
            if line.startswith("TARGET-WINDOW ") and len(line.split()) > 1 and line.split()[1].isdigit()}


PROFILE_MARKS = {"PROFILE-REMOVED-DIR": "removed_dirs", "PROFILE-REMOVED": "removed", "PROFILE-LEFT": "left",
                 "PROFILE-NEW-KEPT": "new_kept", "PROFILE-CHANGED": "changed", "PROFILE-MISSING": "missing"}


def profile_report(out: str) -> dict:
    """What Restore-BenchProfile did, by kind: removed (moved to the quarantine) and removed_dirs were the case's;
    new_kept, changed and missing are reported for review and were never touched; left could not be moved."""
    report = {key: [] for key in PROFILE_MARKS.values()}
    for line in out.splitlines():
        mark, _, path = line.strip().partition(" ")
        if mark in PROFILE_MARKS:
            report[PROFILE_MARKS[mark]].append(path)
    report["restored"] = "PROFILE-RESTORED" in out
    return report


def profile_summary(rows: list[dict]) -> dict:
    """Across the cases of a run: what was moved to the quarantine and what a person must review, «id: path»."""
    def listed(*kinds):
        return [f"{row['id']}: {path}" for row in rows for kind in kinds for path in (row.get("profile") or {}).get(kind) or []]
    review = listed("changed", "missing", "new_kept", "left")
    return {"profile_quarantined": listed("removed"), "profile_review": review,
            "target_windows_left": [row["id"] for row in rows if (row.get("profile") or {}).get("target_windows_left")],
            # Audit w8-medir: what the cases changed, removed or left outside the sandbox and the bench did not undo is
            # there for the next case and the next configuration (holdout v4: tareas_hoy.txt, config.ini, q4/notes.txt
            # in the notebook's home, F007 and F036). A contaminated run says so; restore by hand before the next arm.
            "contaminated": bool(review)}


# A case that never ran its turns is not the product's failure (CIERRE_PLAN: «un caso con setup_fallido es VOID»).
NOT_SCORED = ("setup_fallido", "void", "sesion_bloqueada")


def scored(rows: list[dict]) -> dict:
    """The run's score over the cases that ran: ok and n leave out the cases that never ran (n keeps every case)."""
    ran = [row for row in rows if row.get("status") not in NOT_SCORED]
    return {"n_scored": len(ran), "accuracy_scored": round(sum(r["ok"] for r in ran) / max(1, len(ran)), 4)}


class Isolation:
    """The precondition before the bench and before each case (no target-app window the bench did not open), and the
    profile snapshot around each case (files the case created outside the sandbox go to the case's quarantine)."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.owned: set[int] = set()  # target windows this run's cases opened and left open
        self.before: set[int] = set()

    def env(self, base: dict) -> dict:
        return {**base, "BAXY_BENCH_OWNED_HWNDS": ",".join(str(h) for h in sorted(self.owned))}

    def check(self) -> str | None:
        """Before the conductor starts: None, or why the bench is VOID."""
        script = self.run_dir / "precondition.ps1"
        ps_file(script, [f". '{LIB}'", "Assert-BenchPrecondition"])
        return void_reason(*run_ps(script, self.env(dict(os.environ)), 120))

    def prelude(self, case_id: str) -> list[str]:
        """Lines run before the case's own setup, in the same script."""
        return [f". '{LIB}'", "Assert-BenchPrecondition", "Show-TargetWindows", f"Save-BenchProfile -Name '{case_id}'"]

    def started(self, setup_out: str) -> None:
        self.before = target_windows(setup_out)

    def after(self, case_id: str, case_dir: Path) -> dict:
        """After the case's cleanup: the profile restored, and the target windows the case left open (they are the
        bench's, so the next precondition lets them be)."""
        script = case_dir / "isolation_after.ps1"
        quarantine = case_dir / "profile-quarantine"
        ps_file(script, [f". '{LIB}'", f"Restore-BenchProfile -Name '{case_id}' -Quarantine '{quarantine}'",
                         "Show-TargetWindows"])
        _, out = run_ps(script, dict(os.environ), 300)
        left_open = target_windows(out) - self.before - self.owned
        self.owned |= left_open
        return {**profile_report(out), "target_windows_left": sorted(left_open)}


NOTEPAD_TABS = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages" / "Microsoft.WindowsNotepad_8wekyb3d8bbwe" / \
    "LocalState" / "TabState"


def notepad_running() -> bool:
    import psutil
    return any((p.info["name"] or "").lower() == "notepad.exe" for p in psutil.process_iter(["name"]))


def set_aside_notepad_tabs(backup: Path, tabs: Path = NOTEPAD_TABS) -> int:
    """The Notepad restores its saved tabs: text a previous run typed would pass a later case (practice p13 E012), and
    an app.open of Notepad would bring back the owner's unsaved tabs for a case to type into. Before a bench, with no
    Notepad open, the saved tabs are moved to the run (never deleted) and put back by put_back_notepad_tabs."""
    if notepad_running() or not tabs.is_dir():
        return 0
    moved = 0
    for saved in tabs.iterdir():
        if saved.is_file():
            backup.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(saved), str(backup / saved.name))
                moved += 1
            except OSError:
                pass
    return moved


def put_back_notepad_tabs(backup: Path, bench_tabs: Path, tabs: Path = NOTEPAD_TABS) -> list[str]:
    """After the bench: the tabs the bench's Notepads left are moved to bench_tabs, the owner's go back. With a Notepad
    still open nothing moves (it rewrites its tab files); the names left in the backup are returned."""
    if not backup.is_dir():
        return []
    if notepad_running() or not tabs.is_dir():
        return sorted(p.name for p in backup.iterdir())
    for left in tabs.iterdir():
        if left.is_file():
            bench_tabs.mkdir(parents=True, exist_ok=True)
            shutil.move(str(left), str(bench_tabs / left.name))
    for saved in backup.iterdir():
        shutil.move(str(saved), str(tabs / saved.name))
    return sorted(p.name for p in backup.iterdir())


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
        self.tabs_backup, self.bench_tabs = run_dir / "notepad-tabstate-owner", run_dir / "notepad-tabstate-bench"
        if set_aside_notepad_tabs(self.tabs_backup):
            print(f"Notepad tabs set aside in {self.tabs_backup} (put back when the bench closes)", flush=True)
        self.commands = run_dir / "commands"
        self.commands.mkdir(parents=True, exist_ok=True)
        self.sequence = 0
        self.events = Events(run_dir / "events.jsonl")
        # The mind's trace and the catalog it was sent go to the run (audit w8-medir): in the owner's turns.jsonl they
        # mixed bench turns with his real ones and, past its cap, rotated his out.
        self.mind_dir = run_dir / "mente"
        launch = [str(ROOT / "scripts" / "run_renew.cmd"), "--conductor", "--command-dir", str(self.commands),
                  "--capture", str(run_dir), "--profile", str(profile), "--timeout-ms", "300000"]
        # PC-Q (2026-10-25): cmd /c with more than two quotes drops the first and the last, so a checkout whose path had
        # a space never started («C:» is not a command). /s takes the line between the outer quotes as it is; every
        # argument is quoted (a path cannot hold a quote), so neither a space nor a «&» splits it.
        self.process = subprocess.Popen(
            'cmd /s /c "' + " ".join(f'"{part}"' for part in launch) + '"',
            cwd=str(ROOT), stdout=(run_dir / "console.txt").open("w", encoding="utf-8"), stderr=subprocess.STDOUT,
            # Al máximo (notebook, engine_no_answer): the App's own trace goes to the run too, and with it, when the
            # channel to the core is cut, why (core-disconnect.jsonl beside it).
            env={**os.environ, "BAXY_RENEW_TRACE_DIR": str(self.mind_dir), "BAXY_APP_TRACE": str(run_dir / "app-trace.jsonl")})

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
        # The launcher is a cmd wrapper: the product it started (this bench's own, found by its command folder) and the
        # core and mind under it must not outlive the bench.
        import psutil
        for process in psutil.process_iter(["name", "cmdline"]):
            if (process.info["name"] or "").lower() == "baxy.exe" and str(self.commands) in " ".join(
                    process.info["cmdline"] or []):
                for child in process.children(recursive=True) + [process]:
                    try:
                        child.kill()
                    except psutil.Error:
                        pass
        left = put_back_notepad_tabs(self.tabs_backup, self.bench_tabs)
        if left:
            print(f"Notepad was open: the owner's tabs stay in {self.tabs_backup} ({len(left)}); move them back to "
                  f"{NOTEPAD_TABS} with Notepad closed", flush=True)


def _dones(conductor: Conductor) -> list[int]:
    return [i for i, e in enumerate(conductor.events.all) if e["type"] == "command.done"]


def run_turn(conductor: Conductor, command: dict, timeout: float) -> list[dict]:
    """Sends one turn and returns its own events, up to its command.done (or what came before the timeout). Every
    command but exit ends in one command.done, so the n-th command's is the n-th: after a timeout, the late end of the
    turn before is that turn's, never this one's (ronda final: F119's timeout shifted F120-F124 by one)."""
    start = conductor.send(command)
    n = conductor.sequence
    done = conductor.events.wait(lambda e: len(_dones(conductor)) >= n, timeout)
    conductor.events.poll()
    dones = _dones(conductor)
    begin = start if n == 1 else (dones[n - 2] + 1 if len(dones) >= n - 1 else len(conductor.events.all))
    end = dones[n - 1] + 1 if len(dones) >= n else len(conductor.events.all)
    events = conductor.events.all[max(begin, 0):end]
    if done is None:
        events.append({"type": "bench.timeout"})
    return events


# Audit w8-medir: how long an answer may go on sounding before the next turn or the oracles. It was 30 s; at a usual
# speaking rate (about 14 characters a second) an answer past ~400 characters was still sounding, so the next turn cut
# it (its speech «cancelled») or the oracles read it unfinished, and must_speak failed an answer said whole.
SILENCE_S = 120.0


def wait_silence(conductor: Conductor, timeout: float = SILENCE_S) -> None:
    """Until the last utterance that started has ended (or nothing is sounding)."""
    conductor.events.poll()
    last_start = max((i for i, e in enumerate(conductor.events.all) if e["type"] == "speech.start"), default=None)
    if last_start is not None and not any(e["type"] == "speech.end" for e in conductor.events.all[last_start:]):
        conductor.events.wait(lambda e: e["type"] == "speech.end", timeout)


def session_locked() -> bool:
    """Windows' lock screen is up (LogonUI runs): apps cannot be driven and every later case would be measured wrong.
    BAXY itself locked the PC once (2026-10-15 04:34, «para» → system.power); the bench stops instead of going on."""
    import psutil
    return any((p.info["name"] or "").lower() == "logonui.exe" for p in psutil.process_iter(["name"]))


def norm(text: str) -> str:
    return " ".join((text or "").split())


def utterances(every: list, turn_from: list, replies: list) -> list:
    """Each speech.start of a turn (until the next turn began) with its end; cancelled when the person spoke over it.
    Each kind (progress notice, confirmation question, final answer) carries its own first sound: the final answer that
    follows a confirmation is timed too (it had none, and Test-Spoken read an answer heard for 4 s as not spoken)."""
    speech = []
    bounds = turn_from + [len(every)]
    for number in range(1, len(turn_from) + 1):
        window = range(bounds[number - 1], bounds[number])
        start_at = next((i for i in window if every[i]["type"] == "turn.start"), None)
        turn_start = every[start_at]["t_ms"] if start_at is not None else None
        for i in window:
            event = every[i]
            # Ronda final: the late voice of a turn that timed out arrives before this turn's turn.start: it is not
            # this turn's first sound (it gave negative latencies).
            if event["type"] != "speech.start" or start_at is None or i < start_at:
                continue
            stop = next((e for e in every[i + 1:] if e["type"] == "speech.end"), None)
            stop_ms = stop["t_ms"] if stop else 10**12
            # The person's words that arrived while it sounded cut it; the cut took from them to the audio's end.
            cut_by = next((e for e in every[i + 1:] if e["type"] == "message" and e["speaker"] == "person"
                           and event["t_ms"] <= e["t_ms"] <= stop_ms), None)
            interrupted = cut_by is not None
            asked = replies[number - 1]["confirmation_text"]
            kind = ("progress" if event.get("notice")
                    else "confirmation" if asked and norm(event.get("text")) == norm(asked) else "final")
            # The goal's speed is per order: from its text to the first sound of that turn, whatever was said first.
            # Each kind's first utterance carries its own; the turn's response speed still reads the first non-notice
            # sound (the confirmation question when there was one).
            first = not any(s["turn"] == number and s["kind"] == kind for s in speech)
            speech.append({"turn": number, "kind": kind, "spoken": True, "spoken_text": event.get("text", ""),
                           "first_audio_ms": event["t_ms"] - turn_start if first and turn_start is not None else None,
                           "completed": stop is not None and not interrupted, "cancelled": interrupted,
                           "stop_latency_ms": (stop_ms - cut_by["t_ms"]) if cut_by and stop else None})
    return speech


def run_setup(case: dict, case_dir: Path, env: dict, isolation: Isolation) -> tuple[int, str, str | None]:
    """The case's setup after the isolation prelude, in one script: (exit code, output, why the bench is VOID or None).
    A VOID setup stopped before the case's own lines: neither its cleanup nor the profile restore may run (its state
    file would be an older run's)."""
    setup = case_dir / "setup.ps1"
    ps_file(setup, isolation.prelude(case["id"]) + (case.get("setup") or []))
    code, out = run_ps(setup, isolation.env(env), 300)
    void = None if "BENCH-READY" in out else void_reason(code, out)
    if void is None:
        isolation.started(out)
    return code, out, void


def judge_case(case: dict, conductor: Conductor, case_dir: Path, env_base: dict, isolation: Isolation) -> dict:
    lib_env = dict(env_base)
    started = time.monotonic()
    budget = float(case.get("timeout_s") or 90)
    code, out, void = run_setup(case, case_dir, lib_env, isolation)
    if void:
        return {"id": case["id"], "area": case.get("area"), "kind": case.get("kind"), "ok": False, "status": "void",
                "detail": void}
    if code != 0:
        result = {"id": case["id"], "area": case.get("area"), "kind": case.get("kind"), "ok": False,
                  "status": "setup_fallido", "detail": out[-800:]}
        cleanup = case_dir / "cleanup.ps1"
        ps_file(cleanup, case.get("cleanup") or [])
        run_ps(cleanup, lib_env, 300)
        result["profile"] = isolation.after(case["id"], case_dir)
        return result

    # PC-Q (2026-10-25): a case that broke under its turns or oracles (an exception, a Ctrl+C) still runs its cleanup and
    # the profile restore (as falsedades, R12.6): the files it created outside the sandbox stayed for the next case.
    stage = "turns"
    try:
        run_turn(conductor, {"session": "new"}, 30)
        replies, speech, turn_events, turn_from = [], [], [], []
        turns = case.get("turns") or []
        for number, turn in enumerate(turns, start=1):
            if number > 1 and turn.get("barge_in_after_ms") is None:
                wait_silence(conductor)
            turn_from.append(len(conductor.events.all))
            if turn.get("barge_in_after_ms") is not None:
                # Sent N ms after the previous answer started to sound (not its notice); the previous turn must have sounded.
                prior = next((e for e in reversed(conductor.events.all)
                              if e["type"] == "speech.start" and not e.get("notice")), None)
                if prior is None:
                    conductor.events.wait(lambda e: e["type"] == "speech.start" and not e.get("notice"), 15)
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
        wait_silence(conductor)
        conductor.events.poll()

        speech = utterances(conductor.events.all, turn_from, replies)

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
        stage = "cleanup"
        cleanup = case_dir / "cleanup.ps1"
        ps_file(cleanup, case.get("cleanup") or [])
        _, cleanup_out = run_ps(cleanup, lib_env, 300)
        leftovers = [line for line in cleanup_out.splitlines() if line.startswith("LEFTOVER")]
        stage = "profile"
        profile = isolation.after(case["id"], case_dir)
        stage = "done"
    finally:
        if stage == "turns":
            cleanup = case_dir / "cleanup.ps1"
            ps_file(cleanup, case.get("cleanup") or [])
            run_ps(cleanup, lib_env, 300)
        if stage in ("turns", "cleanup"):
            isolation.after(case["id"], case_dir)
    ok = bool(oracles) and all(o["ok"] for o in oracles) and spoken_ok  # a case with no oracle checks nothing
    first_audio, first_response_audio, unanswered = [], [], []
    for number in range(1, len(turn_from) + 1):
        sounds = [s for s in speech if s["turn"] == number and s["first_audio_ms"] is not None]
        if sounds:
            first_audio.append(min(s["first_audio_ms"] for s in sounds))
        response = [s["first_audio_ms"] for s in sounds if s["kind"] != "progress"]
        if response:
            first_response_audio.append(response[0])
        else:
            unanswered.append(number)  # its response never sounded (a notice alone does not answer)
    return {"id": case["id"], "area": case.get("area"), "kind": case.get("kind"), "ok": ok,
            "status": "ok" if ok else "fallo", "spoken_ok": spoken_ok, "oracles": oracles, "replies": replies,
            "first_audio_ms": first_audio, "first_response_audio_ms": first_response_audio,
            "turns": len(turn_from), "turns_unanswered": unanswered,
            "notices": sum(s["kind"] == "progress" for s in speech), "leftovers": leftovers, "profile": profile,
            "steps": [{"op": e["operation"], "status": e["status"], "verified": e["verified"]}
                      for events in turn_events for e in events if e["type"] == "step"],
            "seconds": round(time.monotonic() - started, 1)}


def say_profile(profile: Path) -> None:
    """Where the run's own profile stayed and how big it is (PC-Q, 2026-10-25): nothing removes it, and each run left
    one more under %LOCALAPPDATA%\\BAXY. Said, never deleted: a person moves it (its private store has NTFS permissions
    of its own: what cannot be read is not counted)."""
    files = size = 0
    for folder, _, names in os.walk(profile):
        for name in names:
            try:
                size += (Path(folder) / name).stat().st_size
                files += 1
            except OSError:
                pass
    print(f"profile of this run: {profile} ({files} files, {size} bytes)" if profile.is_dir()
          else f"profile of this run: {profile} (not created)", flush=True)


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
    isolation = Isolation(run_dir)
    void = isolation.check()
    if void:
        # Nothing ran: the run is VOID, never a score (w6-banco).
        summary = {"label": args.label, "cases": args.cases, "void": void, "ok": 0, "n": len(cases)}
        (run_dir / "results.jsonl").write_text(json.dumps({"summary": summary}, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
        print(f"VOID: {void}\nClose those windows (or run on a machine the owner is not using) and start again.",
              flush=True)
        sys.exit(VOID_EXIT)
    launched = time.time()
    conductor = Conductor(run_dir, profile)
    ready = conductor.events.wait(lambda e: e["type"] in {"runtime", "terminal"}, 300)
    if not ready or not ready.get("mindReady"):
        print(json.dumps({"error": "conductor_not_ready", "event": ready}), flush=True)
        conductor.close()
        sys.exit(2)
    env_base = dict(os.environ)
    rows = []
    stopped_before = None
    # PC-Q (2026-10-25): whatever stops the cases (an exception, a Ctrl+C), the product closes and the owner's Notepad
    # tabs go back; it stayed running, typing into nothing, with its mind and llama-server holding the GPU.
    try:
        record = run_meta.product_record(ROOT, run_dir, launched)  # after configure: the catalog is in the run
        for index, case in enumerate(cases):
            if session_locked():
                # The cases left count as failures (the session was locked: nothing more could run), so the bank is
                # never silently shorter than its cases (round B).
                stopped_before = case["id"]
                print(json.dumps({"error": "sesion_bloqueada", "before": case["id"]}), flush=True)
                rows += [{"id": left["id"], "area": left.get("area"), "kind": left.get("kind"), "ok": False,
                          "status": "sesion_bloqueada", "oracles": [], "replies": [], "steps": []}
                         for left in cases[index:]]
                break
            case_dir = run_dir / case["id"]
            case_dir.mkdir(exist_ok=True)
            row = judge_case(case, conductor, case_dir, env_base, isolation)
            if row["status"] == "void":
                # A window the bench did not open appeared: nothing more runs, and the cases left count as VOID.
                void, stopped_before = row["detail"], case["id"]
                print(f"VOID before {case['id']}: {void}", flush=True)
                rows += [{"id": left["id"], "area": left.get("area"), "kind": left.get("kind"), "ok": False,
                          "status": "void", "oracles": [], "replies": [], "steps": []} for left in cases[index:]]
                break
            rows.append(row)
            removed = (row.get("profile") or {}).get("removed") or []
            print(f"{row['id']} {row['area']:<12} {'ok ' if row['ok'] else 'BAD'} {row['status']} {row.get('seconds')}s "
                  f"{[o['ok'] for o in row.get('oracles', [])]} voz={row.get('spoken_ok')}"
                  + (f" fuera del sandbox: {len(removed)} a cuarentena" if removed else ""), flush=True)
    finally:
        conductor.close()
        say_profile(profile)
    by_area: dict[str, list[int]] = {}
    for row in rows:
        tally = by_area.setdefault(str(row["area"]), [0, 0])
        tally[0] += row["ok"]
        tally[1] += 1
    audio = [ms for row in rows for ms in row.get("first_audio_ms") or []]
    response_audio = [ms for row in rows for ms in row.get("first_response_audio_ms") or []]
    unanswered = [f"{row['id']}#{number}" for row in rows for number in row.get("turns_unanswered") or []]
    turns = sum(row.get("turns") or 0 for row in rows)
    # Every turn counts: one whose response never sounded is later than any that did (round A/B: the median of the
    # sounded turns alone left them out). None when the middle turn is one that never sounded.
    every = sorted(response_audio) + [float("inf")] * len(unanswered)
    every_p50 = statistics.median(every) if every else None
    summary = {"label": args.label, "cases": args.cases, "ok": sum(r["ok"] for r in rows), "n": len(rows),
               "stopped_before": stopped_before,
               "accuracy": round(sum(r["ok"] for r in rows) / max(1, len(rows)), 4), **scored(rows),
               "areas": by_area,
               # The turn's first sound (the notice's when it came first) and its response's, each with the turns that
               # sounded later than 3 s.
               "first_audio_p50_ms": statistics.median(audio) if audio else None,
               "first_audio_over_3s": sum(ms > 3000 for ms in audio),
               "first_response_audio_p50_ms": statistics.median(response_audio) if response_audio else None,
               "first_response_audio_over_3s": sum(ms > 3000 for ms in response_audio),
               "turns_sounded": len(audio),
               "turns": turns, "turns_unanswered": unanswered,
               "first_response_audio_p50_all_turns_ms": None if every_p50 in (None, float("inf")) else every_p50,
               "setup_failed": [r["id"] for r in rows if r["status"] == "setup_fallido"],
               # w6-banco: a VOID run is not a score; the files cases left outside the sandbox (moved to each case's
               # profile-quarantine) and the owner's files a case changed or removed (reported, never touched).
               "void": void, **profile_summary(rows), "run": record}
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as out:
        out.write(json.dumps({"summary": summary}, ensure_ascii=False) + "\n")
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False))
    if summary["contaminated"]:
        print(f"WARNING: the cases changed files outside the sandbox the bench did not undo (profile_review, "
              f"{len(summary['profile_review'])}): put them back before the next configuration runs", flush=True)
    if record["system_one"]["on"] != record["system_one"]["server_started"]:
        print(f"WARNING: System One was {'on' if record['system_one']['on'] else 'off'} for the launcher but its server "
              f"{'did' if record['system_one']['server_started'] else 'did not'} start", flush=True)
    if void:
        sys.exit(VOID_EXIT)


if __name__ == "__main__":
    main()
