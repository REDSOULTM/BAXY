"""Semantic replay harness (Fase 3.5): whole conversations with accumulated history, and the literals' decisions.

Two measures, one tool:

``conv``      Runs each ``*.turns.jsonl`` script through the windowless conductor (``run_baxy_conductor.ps1``, the
              same admission/turn/publication path as the UI and the cien), one fresh profile per script, so every
              turn sees the real history, the real pending question and the real result of the turn before. Effects
              are real and reversible: master volume, microphone and brightness are read before and restored after;
              processes the run started (browser, players, Steam, Notepad, Calculator, Paint) are closed; a shutdown
              a script could schedule is aborted. Each script is scored with ``score_context_turns.py`` rules and
              broken down by the turn's ``clase`` (contexto, guarda, parafrasis, familia, efecto_inventado,
              fuera_de_alcance; ``-`` = a turn that already worked).

``literals``  Sends every literal of the private C03 registry to a fresh mind sidecar as an isolated
              ``turn.decide`` (no core operation is ever dispatched) and records kind and operations. ``diff``
              compares two such runs: the literals are the regression net, so every changed decision is listed for
              review. The output stays out of git (the literals are private).

Reviewed verdicts: a turn marked ``manual`` in its script passes the rules only as «revisar». ``--reviews`` points to
a JSON ``{"<stem>": {"<n>": {"verdict": "bien"|"mal", "reply": "<exact final>"}}}``; a review applies only when the
run produced exactly that final, so a changed reply is always reviewed again.

usage:
  semantic_replay.py conv --out DIR [--label L] [--idle S] [--reviews F] TURNS...
  semantic_replay.py summary --out DIR
  semantic_replay.py rescore --out DIR --reviews F
  semantic_replay.py literals --out FILE [--limit N] [--corpus corpus.jsonl --skip-survey]
  semantic_replay.py diff BASE.jsonl NEW.jsonl
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import score_context_turns as scoring  # noqa: E402

STATE_SCRIPT = SCRIPTS / "semantic_replay_state.ps1"
RUN_PROCESSES = (
    "msedge.exe", "mpv.exe", "steam.exe", "steamwebhelper.exe", "potplayermini64.exe",
    "notepad.exe", "calculatorapp.exe", "mspaint.exe", "photos.exe", "spotify.exe",
)
BUSY_PROCESSES = {"baxy.exe", "baxy-core.exe", "llama-server.exe", "testhost.exe", "msbuild.exe", "vbcscompiler.exe"}
CLASSES = ("contexto", "guarda", "parafrasis", "familia", "efecto_inventado", "fuera_de_alcance", "-")
REGISTRY = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "BAXY" / "C03-survey-requirements336-private" / "requirements.jsonl"


# ---------------------------------------------------------------- machine state and gates


def _state(kind: str, mode: str = "get", value: int | None = None) -> dict[str, Any]:
    command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(STATE_SCRIPT), kind, mode]
    if value is not None:
        command.append(str(value))
    output = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    try:
        return json.loads(output.splitlines()[-1]) if output else {}
    except json.JSONDecodeError:
        return {}


def _idle_seconds() -> float:
    class LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    info = LastInputInfo()
    info.cbSize = ctypes.sizeof(LastInputInfo)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
    return (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0


def _busy() -> list[str]:
    import psutil

    me = psutil.Process(os.getpid())
    mine = {me.pid} | {parent.pid for parent in me.parents()} | {child.pid for child in me.children(recursive=True)}
    busy = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        if process.info["pid"] in mine:
            continue
        name = (process.info["name"] or "").lower()
        cmdline = [part.lower() for part in process.info["cmdline"] or []]
        if name in BUSY_PROCESSES:
            busy.append(name)
        elif name == "dotnet.exe" and any(
            part in {"build", "publish", "test", "msbuild"} or "msbuild.dll" in part or "vbcscompiler.dll" in part
            for part in cmdline
        ):
            busy.append(name)
        elif name.startswith("python") and any("pytest" in part for part in cmdline):
            busy.append(name)
    return busy


def _wait_gates(idle: float, log) -> bool:
    import psutil

    deadline = time.time() + 3600
    quiet = 0
    while time.time() < deadline:
        busy = _busy()
        quiet = quiet + 1 if not busy else 0
        free = psutil.virtual_memory().available / 2**30
        if quiet >= 3 and free >= 4.2 and _idle_seconds() >= idle:
            log(f"GATES_OPEN ram_free_gb={free:.2f} idle={_idle_seconds():.0f}s")
            return True
        time.sleep(10)
    log("GATES_TIMEOUT busy=" + ",".join(_busy()))
    return False


GUARD_TITLE = "BAXY semantic replay guard"
_GUARD_FORM = (
    "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object Windows.Forms.Form; "
    f"$f.Text = '{GUARD_TITLE}'; $f.Width = 420; $f.Height = 160; $f.ShowDialog() | Out-Null"
)


def _code_pids() -> set[int]:
    import psutil

    roots = set()
    for process in psutil.process_iter(["pid", "name"]):
        if (process.info["name"] or "").lower() != "code.exe":
            continue
        try:
            parent = process.parent()
        except psutil.Error:
            continue
        if parent is None or parent.name().lower() != "code.exe":
            roots.add(process.info["pid"])  # the editor itself; helpers come and go
    return roots


def _guard_window() -> subprocess.Popen:
    """Put a disposable window of our own in the foreground before a script runs.

    2026-09-22: a replay read «cerralo» as "close the active window" while VS Code was
    in front, and «sí, dale» confirmed it — VS Code (and the agent inside it) closed
    twice. Whatever a script's turns do to "the active window" lands on this window.
    """

    user32 = ctypes.windll.user32
    process = subprocess.Popen(["powershell", "-NoProfile", "-Command", _GUARD_FORM])
    hwnd = 0
    for _ in range(100):
        hwnd = user32.FindWindowW(None, GUARD_TITLE)
        if hwnd:
            break
        time.sleep(0.1)
    if not hwnd:
        process.kill()
        raise RuntimeError("no apareció la ventana guardia")
    for _ in range(20):
        user32.keybd_event(0x12, 0, 0, 0)  # ALT down lets a background process take the foreground
        user32.keybd_event(0x12, 0, 2, 0)
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        if user32.GetForegroundWindow() == hwnd:
            return process
    process.kill()
    raise RuntimeError("la ventana guardia no quedó en primer plano")


def _run_processes() -> set[int]:
    import psutil

    pids = set()
    for process in psutil.process_iter(["pid", "name"]):
        if (process.info["name"] or "").lower() in RUN_PROCESSES:
            pids.add(process.info["pid"])
    return pids


def _close_new_processes(before: set[int]) -> list[str]:
    import psutil

    closed = []
    victims = []
    for process in psutil.process_iter(["pid", "name"]):
        if (process.info["name"] or "").lower() in RUN_PROCESSES and process.info["pid"] not in before:
            try:
                process.terminate()
                victims.append(process)
                closed.append(f"{process.info['pid']}:{process.info['name']}")
            except psutil.Error:
                pass
    psutil.wait_procs(victims, timeout=15)
    return closed


# ---------------------------------------------------------------- conversations


def _load_reviews(path: str | None) -> dict[str, dict[str, dict[str, str]]]:
    if not path or not pathlib.Path(path).is_file():
        return {}
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def score_script(turns_path: pathlib.Path, profile: pathlib.Path, reviews: dict[str, dict[str, str]]) -> dict[str, Any]:
    turns = scoring.load_turns(turns_path)
    pairs = scoring.load_conversation(profile)
    buckets = scoring.attribute(scoring.load_operations(profile), pairs)
    table = []
    for index, turn in enumerate(turns):
        user, reply = pairs[index] if index < len(pairs) else (None, None)
        ops = buckets[index] if index < len(buckets) else []
        ok, reasons = scoring.evaluate(turn, user, reply, ops)
        number = int(turn.get("n") or index + 1)
        final = str((reply or {}).get("text") or "")
        verdict = "bien" if ok else "mal"
        if ok and (turn.get("check") or {}).get("manual"):
            review = reviews.get(str(number))
            verdict = review["verdict"] if review and review.get("reply") == final else "revisar"
        table.append(
            {
                "n": number,
                "clase": str(turn.get("clase") or "-"),
                "text": turn.get("text"),
                "expected": turn.get("expected"),
                "route": (reply or {}).get("route"),
                "latency_ms": (reply or {}).get("latency_ms"),
                "reply": final,
                "ops": [f"{op['operation']}:{op['phase']}" + ("/v" if op.get("verified") else "") for op in ops],
                "verdict": verdict,
                "reasons": reasons,
            }
        )
    good = sum(1 for row in table if row["verdict"] == "bien")
    by_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in table:
        by_class[row["clase"]][1] += 1
        by_class[row["clase"]][0] += row["verdict"] == "bien"
    return {
        "script": turns_path.name,
        "good": good,
        "total": len(table),
        "pending_review": sum(1 for row in table if row["verdict"] == "revisar"),
        "answers": len(pairs),
        "by_class": {name: by_class[name] for name in CLASSES if name in by_class},
        "turns": table,
    }


def render(score: dict[str, Any]) -> str:
    lines = []
    for row in score["turns"]:
        flag = {"bien": "OK ", "mal": "MAL", "revisar": "?? "}[row["verdict"]]
        lines.append(f"{row['n']:02d} {flag} [{row['clase']}] {row['text']}")
        lines.append(f"      → [{row['route']}] {' '.join(row['reply'].split())[:220]}")
        if row["ops"]:
            lines.append(f"      ops: {', '.join(row['ops'])}")
        if row["reasons"]:
            lines.append(f"      por: {'; '.join(row['reasons'])}")
    classes = " · ".join(f"{name} {good}/{total}" for name, (good, total) in score["by_class"].items())
    lines.append("")
    lines.append(
        f"turnos bien {score['good']}/{score['total']}"
        + (f" (+{score['pending_review']} por revisar)" if score["pending_review"] else "")
        + f"; respuestas {score['answers']}; por clase: {classes}"
    )
    return "\n".join(lines) + "\n"


def run_conversation(turns_path: pathlib.Path, out: pathlib.Path, label: str, idle: float, reviews) -> dict[str, Any]:
    stem = turns_path.name.removesuffix(".turns.jsonl")
    work = out / stem
    work.mkdir(parents=True, exist_ok=True)
    log_path = work / "run.log"
    log_path.write_text("", encoding="utf-8")

    def log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
        print(f"[{stem}] {message}", flush=True)

    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--short", "--", "src"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    log(f"HEAD {head}{' +src sucio' if dirty else ''} {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    if not _wait_gates(idle, log):
        return {"script": turns_path.name, "error": "gates"}
    volume, microphone, brightness = _state("volume"), _state("mic"), _state("brightness")
    log(f"PRESET volume={volume} mic={microphone} brightness={brightness}")
    before = _run_processes()
    profile = pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXY" / f"{label}-{stem}"
    shutil.rmtree(profile, ignore_errors=True)
    shutil.rmtree(work / "capture", ignore_errors=True)
    environment = os.environ.copy()
    environment["BAXY_MIND_RAW_REPLY_AUDIT_PATH"] = str(work / "raw-replies.jsonl")
    environment["BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH"] = str(work / "compose-audit.jsonl")
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(work / "turn-audit.jsonl")
    environment["BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT"] = "1"
    for name in ("raw-replies.jsonl", "compose-audit.jsonl", "turn-audit.jsonl"):
        (work / name).unlink(missing_ok=True)
    vscode_before = _code_pids()
    try:
        guard = _guard_window()
    except RuntimeError as error:
        log(f"GUARD_FAILED {error}")
        return {"script": turns_path.name, "error": "guard"}
    log(f"GUARD_FOREGROUND code_pids={len(vscode_before)}")
    with (work / "conductor.log").open("w", encoding="utf-8") as conductor_log:
        exit_code = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(SCRIPTS / "run_baxy_conductor.ps1"), "-TurnsFile", str(turns_path),
                "-Profile", str(profile), "-Capture", str(work / "capture"),
            ],
            cwd=REPO, env=environment, stdout=conductor_log, stderr=subprocess.STDOUT,
        ).returncode
    log(f"conductor_exit={exit_code}")
    guard.kill()
    lost = vscode_before - _code_pids()
    if vscode_before and lost:
        log(f"VSCODE_CLOSED {sorted(lost)} — se aborta la corrida")
        return {"script": turns_path.name, "error": "vscode_closed"}
    if "level" in volume:
        _state("volume", "set", int(volume["level"]))
        _state("volume", "mute", int(bool(volume.get("muted"))))
    if "muted" in microphone:
        _state("mic", "mute", int(bool(microphone.get("muted"))))
    if brightness.get("levels"):
        _state("brightness", "set", int(brightness["levels"][0]))
    subprocess.run(["shutdown", "/a"], capture_output=True)
    log(f"RESTORED volume={_state('volume')} mic={_state('mic')} brightness={_state('brightness')}")
    log(f"CLOSED_RUN_PROCESSES {_close_new_processes(before)}")
    score = score_script(turns_path, profile, reviews.get(stem, {}))
    score["head"] = head
    score["profile"] = str(profile)
    score["turns_path"] = str(turns_path)
    (work / "score.json").write_text(json.dumps(score, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (work / "score.txt").write_text(render(score), encoding="utf-8", newline="\n")
    log(render(score).splitlines()[-1])
    return score


def rescore(out: pathlib.Path, reviews_path: str) -> None:
    reviews = _load_reviews(reviews_path)
    for path in sorted(out.glob("*/score.json")):
        old = json.loads(path.read_text(encoding="utf-8"))
        stem = path.parent.name
        score = score_script(pathlib.Path(old["turns_path"]), pathlib.Path(old["profile"]), reviews.get(stem, {}))
        score.update({key: old[key] for key in ("head", "profile", "turns_path")})
        path.write_text(json.dumps(score, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        (path.parent / "score.txt").write_text(render(score), encoding="utf-8", newline="\n")
    summary(out)


def summary(out: pathlib.Path) -> None:
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(out.glob("*/score.json"))]
    total_good = sum(row["good"] for row in rows)
    total = sum(row["total"] for row in rows)
    pending = sum(row["pending_review"] for row in rows)
    classes: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        print(f"{row['script']:<48} {row['good']:>3}/{row['total']:<3} HEAD {row.get('head')}"
              + (f" (+{row['pending_review']} revisar)" if row["pending_review"] else ""))
        for name, (good, count) in row["by_class"].items():
            classes[name][0] += good
            classes[name][1] += count
    print(f"TOTAL {total_good}/{total}" + (f" (+{pending} revisar)" if pending else ""))
    print("por clase: " + " · ".join(f"{name} {good}/{count}" for name, (good, count) in classes.items()))


# ---------------------------------------------------------------- literals (decision only)


def _decide(client, message: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    """One turn.decide; the early ``turn.signal`` the mind may emit first is not the result."""
    client._process.stdin.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    client._process.stdin.flush()
    deadline = time.monotonic() + timeout
    while True:
        reply = client._next(max(0.1, deadline - time.monotonic()))
        if reply.get("id") != message["id"] or reply.get("type") == "turn.signal":
            continue
        if reply.get("type") != "turn.result":
            raise RuntimeError(f"{reply.get('type')}: {reply.get('code') or ''} {reply.get('message') or ''}")
        return reply


def literals(
    out: pathlib.Path,
    limit: int | None,
    corpus: pathlib.Path | None = None,
    skip_survey: bool = False,
    src: pathlib.Path | None = None,
) -> None:
    import run_turn_policy_gate as gate

    if src is not None:
        # Measure another commit's mind (a worktree of it) against today's core catalog.
        gate.SRC = src.resolve()

    if corpus is None:
        rows = [json.loads(line) for line in REGISTRY.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        # semantic_corpus.py rows: {"id", "text", ...}; survey rows already have their own replay.
        rows = [
            {"case_id": row["id"], "literal": row["text"], "history": row.get("history") or [],
             "pendingObjective": row.get("pendingObjective")}
            for row in map(json.loads, filter(str.strip, corpus.read_text(encoding="utf-8").splitlines()))
            if not (skip_survey and row.get("expect") == "survey")
        ]
    if limit:
        rows = rows[:limit]
    manifest = gate.read_runtime_manifest(pathlib.Path(os.environ["LOCALAPPDATA"]) / "BAXYRuntime" / "mind-runtime-v1.json")
    configuration = gate.core_catalog_configuration(gate.DEFAULT_CORE)
    done = set()
    if out.is_file():
        done = {record["case_id"] for record in map(json.loads, filter(str.strip, out.read_text(encoding="utf-8").splitlines())) if "error" not in record}
    with gate.MindClient(
        configuration["capabilities"],
        application_catalog=configuration["applicationCatalog"],
        game_catalog=configuration["gameCatalog"],
        gguf=pathlib.Path(manifest["gguf"]),
        llama_server=pathlib.Path(manifest["llama_server"]),
        ngl=int(manifest.get("ngl") or 99),
        endpoint=None,
        environment_overrides={},
        startup_timeout=300.0,
    ) as client:
        for row in rows:
            case_id = row["case_id"]
            if case_id in done:
                continue
            started = time.perf_counter()
            record: dict[str, Any] = {"case_id": case_id}
            try:
                reply = _decide(
                    client,
                    {"type": "turn.decide", "id": f"replay-{case_id}", "text": row["literal"],
                     "history": [*row.get("history", []), {"role": "user", "content": row["literal"]}]
                     if row.get("history") else [],
                     "pendingClarification": False, "uiLanguage": "es",
                     **({"pendingObjective": row["pendingObjective"]} if row.get("pendingObjective") else {})},
                )
                record.update(
                    {
                        "kind": reply.get("kind"),
                        "operation": reply.get("operation"),
                        "effects": sorted(reply.get("effectOperations") or []),
                        "intent": sorted(reply.get("intentOperations") or []),
                        "missing": reply.get("missingFields") or [],
                        "conversation_kind": reply.get("conversationKind"),
                        "arguments": reply.get("arguments"),
                        "question": str(reply.get("question") or "")[:300],
                        "reply": str(reply.get("reply") or "")[:300],
                    }
                )
            except Exception as error:  # noqa: BLE001 - a replay records failures
                record["error"] = f"{type(error).__name__}: {error}"[:500]
            record["latency_s"] = round(time.perf_counter() - started, 2)
            with out.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"{case_id} {record.get('kind')} {record.get('operation') or ''} {record.get('effects') or ''} {record['latency_s']}s", flush=True)


def _decision(record: dict[str, Any]) -> tuple:
    return (record.get("kind"), record.get("operation"), tuple(record.get("effects") or ()))


def diff(base_path: pathlib.Path, new_path: pathlib.Path) -> None:
    def load(path: pathlib.Path) -> dict[str, dict[str, Any]]:
        return {json.loads(line)["case_id"]: json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}

    base, new = load(base_path), load(new_path)
    literal = {}
    if REGISTRY.is_file():
        for line in REGISTRY.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                literal[row["case_id"]] = row["literal"]
    changed = [case for case in sorted(base) if case in new and _decision(base[case]) != _decision(new[case])]
    kinds_base = Counter(record.get("kind") for record in base.values())
    kinds_new = Counter(record.get("kind") for record in new.values() if record["case_id"] in base)
    print(f"casos base {len(base)} nuevo {len(new)} comunes {len(set(base) & set(new))}; decisiones distintas {len(changed)}")
    print(f"clases base {dict(kinds_base)}")
    print(f"clases nuevo {dict(kinds_new)}")
    for case in changed:
        print(f"{case} «{literal.get(case, '?')}»\n    antes {_decision(base[case])}\n    ahora {_decision(new[case])}"
              f"\n    q/r: {(new[case].get('question') or new[case].get('reply') or '')[:160]}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    conv = sub.add_parser("conv")
    conv.add_argument("--out", required=True, type=pathlib.Path)
    conv.add_argument("--label", default="semrep")
    conv.add_argument("--idle", type=float, default=60.0)
    conv.add_argument("--reviews")
    conv.add_argument("turns", nargs="+", type=pathlib.Path)
    summ = sub.add_parser("summary")
    summ.add_argument("--out", required=True, type=pathlib.Path)
    resc = sub.add_parser("rescore")
    resc.add_argument("--out", required=True, type=pathlib.Path)
    resc.add_argument("--reviews", required=True)
    lit = sub.add_parser("literals")
    lit.add_argument("--out", required=True, type=pathlib.Path)
    lit.add_argument("--limit", type=int)
    lit.add_argument("--corpus", type=pathlib.Path, help="semantic_corpus.py corpus.jsonl instead of the 742")
    lit.add_argument("--skip-survey", action="store_true")
    lit.add_argument("--src", type=pathlib.Path, help="mind sources to run (e.g. a worktree of the baseline tag)")
    dif = sub.add_parser("diff")
    dif.add_argument("base", type=pathlib.Path)
    dif.add_argument("new", type=pathlib.Path)
    args = parser.parse_args(argv)
    if args.command == "conv":
        args.out.mkdir(parents=True, exist_ok=True)
        reviews = _load_reviews(args.reviews)
        for turns in args.turns:
            score = run_conversation(turns.resolve(), args.out, args.label, args.idle, reviews)
            if "error" in score:
                return 1
        summary(args.out)
    elif args.command == "summary":
        summary(args.out)
    elif args.command == "rescore":
        rescore(args.out, args.reviews)
    elif args.command == "literals":
        literals(args.out, args.limit, args.corpus, args.skip_survey, args.src)
    else:
        diff(args.base, args.new)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
