"""Ronda 23 (t-drag-1, comprobación en vivo r21): a case whose three attempts the infrastructure aborted (another BAXY
open, the GPU busy) was judged on the trace an earlier day left in its evidence folder. Now (a) the three aborted
attempts are NO_CORRIO and what an earlier run left is archived, and (b) before the first attempt the files the App and
the mind append to go to anterior/, so nothing in the folder can pass for this run."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "scripts" / "cu_live"
LIB = (LIVE / "evidencia_no_corrio.sh").as_posix()
APPENDED = ("trace.jsonl", "events.jsonl", "turn_audit.jsonl", "compose_audit.jsonl", "model_calls.jsonl")


def _git_bash() -> str | None:
    # Git's bash, never WSL's: the harness scripts run in Git Bash.
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).parents[:3]:
        candidate = root / "bin" / "bash.exe"
        if candidate.exists() and "system32" not in str(candidate).lower():
            return str(candidate)
    return None


def _bash(script: str) -> str:
    exe = _git_bash()
    if exe is None:
        pytest.skip("bash de Git no disponible")
    done = subprocess.run([exe, "-c", script], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _old_run(ev: Path) -> None:
    (ev / "molestia-control").mkdir(parents=True)
    for name in (*APPENDED, "after.png", "events.repetido-1.jsonl"):
        (ev / name).write_text("2026-10-07", encoding="utf-8")


def test_before_the_first_attempt_the_appended_files_of_an_earlier_run_go_to_anterior(tmp_path):
    ev = tmp_path / "v2-t-drag-1"
    _old_run(ev)
    (ev / "no_corrio.json").write_text("{}", encoding="utf-8")
    _bash(f'. "{LIB}"; evidencia_corre "{ev.as_posix()}"')
    assert sorted(p.name for p in (ev / "anterior").iterdir()) == sorted((*APPENDED, "events.repetido-1.jsonl"))
    # What the run rewrites itself (the photo, the meter's folder) stays; the old marker goes.
    assert sorted(p.name for p in ev.iterdir()) == ["after.png", "anterior", "molestia-control"]
    # Counter-case: a folder with nothing appended keeps an older anterior/ (nothing to replace it with).
    (ev / "anterior" / "marca").write_text("x", encoding="utf-8")
    _bash(f'. "{LIB}"; evidencia_corre "{ev.as_posix()}"')
    assert (ev / "anterior" / "marca").exists() and (ev / "after.png").exists()


def test_no_attempt_run_archives_the_rest_into_the_same_anterior_without_losing_the_trace(tmp_path):
    ev = tmp_path / "v2-t-drag-1"
    _old_run(ev)
    d = ev.as_posix()
    _bash(f'. "{LIB}"; evidencia_corre "{d}"; evidencia_no_corrio "{d}" t-drag-1 "infraestructura: x" 1')
    assert sorted(p.name for p in ev.iterdir()) == ["anterior", "no_corrio.json"]
    assert sorted(p.name for p in (ev / "anterior").iterdir()) == sorted(
        (*APPENDED, "events.repetido-1.jsonl", "after.png", "molestia-control"))
    marker = json.loads((ev / "no_corrio.json").read_text(encoding="utf-8"))
    assert marker["no_corrio"] is True and marker["evidencia_anterior"] == "anterior"
    # Counter-case: another run (a new shell, no anterior/ of its own) still replaces an older anterior/.
    (ev / "after.png").write_text("2026-10-09", encoding="utf-8")
    _bash(f'. "{LIB}"; evidencia_no_corrio "{d}" t-drag-1 otra 1')
    assert sorted(p.name for p in (ev / "anterior").iterdir()) == ["after.png"]


def _loop(tmp_path: Path, salidas: list[str], repetir: str) -> dict[str, str]:
    """Runs batch.sh's attempt loop with the live case and repetir.py stubbed: cu_live.sh prints the n-th line of
    ``salidas``; ``repetir`` is the body of py (print a motive and return 0 to repeat, return 1 to stop)."""

    text = (LIVE / "batch.sh").read_text(encoding="utf-8")
    start = text.index('  NOCORRIO=""; MOTIVO=""; CORRIO=0')
    loop = text[start:text.index("\n  done\n", start) + len("\n  done\n")]
    live = tmp_path / "live"
    (live / "logs").mkdir(parents=True)
    (live / "salidas").write_text("\n".join(salidas) + "\n", encoding="utf-8")
    (live / "cu_live.sh").write_text(
        'n=$(cat "$L/n" 2>/dev/null || echo 0); n=$((n+1)); echo $n > "$L/n"; sed -n "${n}p" "$L/salidas"\n',
        encoding="utf-8", newline="\n")
    script = "\n".join([
        f'export L="{live.as_posix()}"; EVB="{(tmp_path / "ev").as_posix()}"; P="$L"; tag=v2-x; tid=x; id=x',
        't_paso(){ :; }; sleep(){ :; }; limpiar_caso(){ LIMPIO=1; }; preparar_caso(){ NOVERIF=""; return 0; }',
        f"py(){{ {repetir}; }}",
        loop,
        'echo "NOCORRIO=$NOCORRIO"; echo "CORRIO=$CORRIO"; echo "INTENTOS=$(cat "$L/n")"',
    ])
    out = _bash(script)
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line and line.split("=", 1)[0].isupper())


def test_t_drag_1_three_aborted_attempts_are_no_corrio_with_nothing_run(tmp_path):
    got = _loop(tmp_path, ["ABORT: GPU busy", "ABORT: BAXY already running", "conductor exit=2 wall=1s"], "return 1")
    assert got["NOCORRIO"].startswith("infraestructura: ") and got["CORRIO"] == "0" and got["INTENTOS"] == "3"
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert 'evidencia_no_corrio "$EVB/$tag" "$id" "$NOCORRIO ($MOTIVO)" "$(( CORRIO ? 0 : 1 ))"' in batch


def test_three_runs_without_the_decider_are_no_corrio_keeping_this_batchs_attempt(tmp_path):
    got = _loop(tmp_path, ["conductor exit=0"] * 3, "echo decision_unavailable; return 0")
    assert got["NOCORRIO"] == "infraestructura: sin decisor en los 3 intentos" and got["CORRIO"] == "1"


def test_counter_case_an_attempt_that_runs_after_aborts_is_judged(tmp_path):
    got = _loop(tmp_path, ["ABORT: GPU busy", "ABORT: GPU busy", "conductor exit=0"], "return 1")
    assert got["NOCORRIO"] == "" and got["CORRIO"] == "1" and got["INTENTOS"] == "3"
    got = _loop(tmp_path / "b", ["conductor exit=0"], "return 1")
    assert got["NOCORRIO"] == "" and got["INTENTOS"] == "1"
