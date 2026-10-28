"""The harness cleans up after itself (PC-Q, 2026-10-25): what a run started dies with it, whatever stopped it; a path
with spaces starts the product. Doubles only: no product, no model, no GPU."""
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "renew"))

import bench_e2e  # noqa: E402
import bench_falsedades  # noqa: E402


class FakeConductor:
    instances: list = []

    def __init__(self, run_dir, profile):
        self.events = self
        self.closed = False
        FakeConductor.instances.append(self)

    def wait(self, predicate, timeout):
        return {"type": "runtime", "mindReady": True}

    def close(self):
        self.closed = True


class ReadyIsolation:
    def __init__(self, run_dir):
        pass

    def check(self):
        return None


def test_an_e2e_run_that_breaks_mid_bank_still_closes_the_product(tmp_path, monkeypatch):
    # A case that raised (an events.jsonl line cut, a Ctrl+C) left BAXY, its mind and llama-server running, and the
    # owner's Notepad tabs set aside (they are put back by Conductor.close).
    FakeConductor.instances.clear()
    monkeypatch.setattr(bench_e2e, "BANKS", tmp_path)
    monkeypatch.setattr(bench_e2e, "Isolation", ReadyIsolation)
    monkeypatch.setattr(bench_e2e, "Conductor", FakeConductor)
    monkeypatch.setattr(bench_e2e, "session_locked", lambda: False)
    monkeypatch.setattr(bench_e2e.run_meta, "product_record", lambda *a: {})

    def broken(*args):
        raise RuntimeError("events.jsonl: a line cut halfway")

    monkeypatch.setattr(bench_e2e, "judge_case", broken)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps([{"id": "E001"}]), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bench_e2e.py", "x", "--cases", str(cases)])
    with pytest.raises(RuntimeError):
        bench_e2e.main()
    assert FakeConductor.instances and FakeConductor.instances[0].closed


def _falsedades_doubles(monkeypatch, tmp_path):
    FakeConductor.instances.clear()
    for module in (bench_falsedades, bench_e2e):
        monkeypatch.setattr(module, "ps_file", lambda path, lines: None)
        monkeypatch.setattr(module, "run_ps", lambda path, env, timeout: (0, "BENCH-READY"))
    monkeypatch.setattr(bench_falsedades, "Conductor", FakeConductor)
    monkeypatch.setattr(bench_falsedades.run_meta, "product_record", lambda *a: {})
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))


def test_a_falsehood_run_stopped_by_the_lock_screen_closes_the_product(tmp_path, monkeypatch):
    _falsedades_doubles(monkeypatch, tmp_path)
    monkeypatch.setattr(bench_falsedades, "session_locked", lambda: True)
    with pytest.raises(SystemExit, match="sesion_bloqueada"):
        bench_falsedades.run_conversations([{"id": "F001", "turns": []}], tmp_path)
    assert FakeConductor.instances[0].closed


def test_a_falsehood_run_whose_conversation_broke_closes_the_product(tmp_path, monkeypatch):
    _falsedades_doubles(monkeypatch, tmp_path)
    monkeypatch.setattr(bench_falsedades, "session_locked", lambda: False)

    def broken(conductor, case):
        raise KeyboardInterrupt

    monkeypatch.setattr(bench_falsedades, "converse", broken)
    with pytest.raises(KeyboardInterrupt):
        bench_falsedades.run_conversations([{"id": "F001", "turns": [{"text": "hola"}]}], tmp_path)
    assert FakeConductor.instances[0].closed


class ExitedServer:
    """A llama-server that could not start (its GGUF missing, its port taken): it exited at once."""

    def __init__(self, *args, **kwargs):
        self.pid = 0

    def poll(self):
        return 1

    def terminate(self):
        pass

    def kill(self):
        pass

    def wait(self, timeout=None):
        return 1


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_the_judge_does_not_wait_fifteen_minutes_for_a_server_that_exited(tmp_path, monkeypatch):
    clock = {"now": 0.0, "asked": 0}

    def urlopen(*args, **kwargs):
        clock["asked"] += 1
        raise urllib.error.URLError("refused")

    def sleep(seconds):
        clock["now"] += seconds

    monkeypatch.setattr(bench_falsedades.subprocess, "Popen", ExitedServer)
    monkeypatch.setattr(bench_falsedades.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(bench_falsedades.time, "sleep", sleep)
    monkeypatch.setattr(bench_falsedades.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(bench_falsedades, "JUDGE_PORT", _free_port())
    with pytest.raises(SystemExit, match="judge"):
        bench_falsedades.judge([[]], tmp_path)
    assert clock["asked"] <= 1 and clock["now"] < 5


class Healthy(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server's name
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


def test_a_server_left_on_the_judges_port_never_judges_in_its_place(tmp_path, monkeypatch):
    # A judge server orphaned by a run that was killed holds the port: the new one cannot bind and exits, and the
    # orphan (whatever model it loaded) answered the health check and every line.
    foreign = HTTPServer(("127.0.0.1", 0), Healthy)
    threading.Thread(target=foreign.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(bench_falsedades, "JUDGE_PORT", foreign.server_address[1])
        monkeypatch.setattr(bench_falsedades.subprocess, "Popen", ExitedServer)
        with pytest.raises(SystemExit, match="in use"):
            bench_falsedades.judge([[]], tmp_path)
    finally:
        foreign.shutdown()
        foreign.server_close()


PARENT = r"""
import subprocess, sys, time
sys.path.insert(0, sys.argv[1])
import limpieza
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
held = limpieza.die_with_this_process(child) if sys.argv[2] == "job" else False
print(child.pid, held, flush=True)
time.sleep(120)
"""


def _child_left_after_killing_its_bench(tmp_path, mode: str, wait: float) -> tuple[bool, bool]:
    import psutil
    script = tmp_path / "bench.py"
    script.write_text(PARENT, encoding="utf-8")
    parent = subprocess.Popen([sys.executable, str(script), str(Path(bench_e2e.__file__).parent), mode],
                              stdout=subprocess.PIPE, text=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    pid, held = parent.stdout.readline().split()
    parent.kill()  # TerminateProcess: no finally runs, as when a run is killed from outside
    parent.wait(10)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline and psutil.pid_exists(int(pid)):
        time.sleep(0.1)
    alive = psutil.pid_exists(int(pid))
    if alive:
        psutil.Process(int(pid)).kill()
    return alive, held == "True"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows jobs")
def test_a_server_handed_to_the_job_dies_when_its_bench_is_killed(tmp_path):
    assert _child_left_after_killing_its_bench(tmp_path, "job", 10) == (False, True)
    # Without it, what the killed bench started stays (the orphaned llama-servers of 2026-10-25).
    assert _child_left_after_killing_its_bench(tmp_path, "plain", 2) == (True, False)


class HealthyServer(ExitedServer):
    def poll(self):
        return None


class Ok:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_the_judge_server_dies_with_its_bench(monkeypatch):
    held = []
    monkeypatch.setattr(bench_falsedades.subprocess, "Popen", HealthyServer)
    monkeypatch.setattr(bench_falsedades.urllib.request, "urlopen", lambda *a, **k: Ok())
    monkeypatch.setattr(bench_falsedades.limpieza, "die_with_this_process", held.append)
    monkeypatch.setitem(bench_falsedades._JUDGE, "log", None)
    assert bench_falsedades.start_judge_server()
    assert held == [bench_falsedades._JUDGE["server"]]


@pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe")
def test_the_product_starts_from_a_checkout_whose_path_has_spaces(tmp_path, monkeypatch):
    # cmd /c with more than two quotes strips the first and the last: «C:\a b\scripts\run_renew.cmd» became «C:\a» and
    # the conductor never started (the bench then waited 300 s for it and said conductor_not_ready).
    root = tmp_path / "check out"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "run_renew.cmd").write_text(
        '@echo off\r\n(for %%A in (%*) do @echo %%~A) > "%~dp0args.txt"\r\n', encoding="ascii")
    run_dir = tmp_path / "run dir"
    run_dir.mkdir()
    started = {}

    def popen(command, **options):
        started["command"] = command
        started["stdout"] = options["stdout"]
        return SimpleNamespace()

    real_popen = subprocess.Popen
    monkeypatch.setattr(bench_e2e, "ROOT", root)
    monkeypatch.setattr(bench_e2e.subprocess, "Popen", popen)
    monkeypatch.setattr(bench_e2e, "set_aside_notepad_tabs", lambda backup: 0)
    bench_e2e.Conductor(run_dir, tmp_path / "per fil")
    started["stdout"].close()
    monkeypatch.setattr(subprocess, "Popen", real_popen)
    done = subprocess.run(started["command"], cwd=str(root), capture_output=True, text=True,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert done.returncode == 0, done.stdout + done.stderr
    assert (root / "scripts" / "args.txt").read_text().split("\n")[:8] == [
        "--conductor", "--command-dir", str(run_dir / "commands"), "--capture", str(run_dir), "--profile",
        str(tmp_path / "per fil"), "--timeout-ms"]


def test_a_falsehood_run_says_which_judge_judged_it(tmp_path, monkeypatch):
    # The judge's GGUF is BAXY_RENEW_JUDGE_GGUF's, and a --judge-only reads transcripts made long before: the summary
    # named the product that talked (run.json) and nothing of the model that judged it.
    model, server = tmp_path / "juez.gguf", tmp_path / "llama-server.exe"
    model.write_bytes(b"35B")
    server.write_bytes(b"exe")
    run_dir = tmp_path / "runs" / "lbl-falsedades"
    run_dir.mkdir(parents=True)
    (run_dir / "transcripts.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(bench_falsedades, "BANKS", tmp_path)
    monkeypatch.setattr(bench_falsedades, "JUDGE_GGUF", str(model))
    monkeypatch.setattr(bench_falsedades, "LLAMA_SERVER", str(server))
    monkeypatch.setattr(bench_falsedades, "judge", lambda replicas, log_dir: [[] for _ in replicas])
    monkeypatch.setattr(bench_falsedades.run_meta, "_cache_path", lambda: None)
    monkeypatch.delenv("BAXY_RENEW_SEED", raising=False)
    monkeypatch.setattr(sys, "argv", ["bench_falsedades.py", "lbl", "--cases", "c.json", "--judge-only",
                                      "--judge", "local"])
    bench_falsedades.main()
    summary = json.loads((run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()[0])["summary"]
    judge = summary["judge"]
    assert judge["gguf"] == bench_falsedades.run_meta.fingerprint(model)
    assert judge["server"]["sha256"] == bench_falsedades.run_meta.sha256_file(server)
    assert judge["seeds"] == list(bench_falsedades.JUDGE_SEEDS)
    assert judge["script_sha256"] == bench_falsedades.run_meta.sha256_file(Path(bench_falsedades.__file__))


def test_an_e2e_case_that_breaks_mid_turn_still_runs_its_cleanup_and_restores_the_profile(tmp_path, monkeypatch):
    # The files a case created outside the sandbox go to its quarantine and its own cleanup runs (as in falsedades,
    # R12.6), also when a turn raised: they stayed for the next case and the next arm.
    ran = []

    def run_ps(path, env, timeout):
        ran.append(Path(path).name)
        return 0, "BENCH-READY"

    def broken(*args):
        raise KeyboardInterrupt

    monkeypatch.setattr(bench_e2e, "ps_file", lambda path, lines: None)
    monkeypatch.setattr(bench_e2e, "run_ps", run_ps)
    monkeypatch.setattr(bench_e2e, "run_turn", broken)
    case = {"id": "E001", "setup": [], "cleanup": ["Remove-Item x"], "turns": [{"text": "abre el bloc"}],
            "oracle": [{"ps": "x", "expect_regex": "x"}]}
    with pytest.raises(KeyboardInterrupt):
        bench_e2e.judge_case(case, SimpleNamespace(), tmp_path, {}, bench_e2e.Isolation(tmp_path))
    assert ran == ["setup.ps1", "cleanup.ps1", "isolation_after.ps1"]


class ProfileConductor(FakeConductor):
    """The product writes its notes and memory in the bench's own profile."""

    def __init__(self, run_dir, profile):
        super().__init__(run_dir, profile)
        (profile / "notes").mkdir(parents=True)
        (profile / "notes" / "n.json").write_bytes(b"x" * 1500)
        (profile / "memory.db").write_bytes(b"y" * 600)


def test_an_e2e_run_says_where_its_profile_stayed_and_how_big_it_is(tmp_path, monkeypatch, capsys):
    # The profile (LOCALAPPDATA\BAXY\bench-<label>-<ts>) is never removed: the run says where it is, so it can be
    # moved by hand; nothing is deleted.
    monkeypatch.setattr(bench_e2e, "BANKS", tmp_path / "bancos")
    monkeypatch.setattr(bench_e2e, "Isolation", ReadyIsolation)
    monkeypatch.setattr(bench_e2e, "Conductor", ProfileConductor)
    monkeypatch.setattr(bench_e2e, "session_locked", lambda: False)
    monkeypatch.setattr(bench_e2e.run_meta, "product_record", lambda *a: {"system_one": {"on": False,
                                                                                         "server_started": False}})
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    cases = tmp_path / "cases.json"
    cases.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["bench_e2e.py", "x", "--cases", str(cases)])
    bench_e2e.main()
    profile = next((tmp_path / "BAXY").glob("bench-x-*"))
    assert f"profile of this run: {profile} (2 files, 2100 bytes)" in capsys.readouterr().out
    assert (profile / "memory.db").is_file()


def test_a_falsehood_replica_says_where_its_profile_stayed(tmp_path, monkeypatch, capsys):
    _falsedades_doubles(monkeypatch, tmp_path)
    monkeypatch.setattr(bench_falsedades, "Conductor", ProfileConductor)
    monkeypatch.setattr(bench_falsedades, "session_locked", lambda: False)
    bench_falsedades.run_conversations([], tmp_path)
    profile = next((tmp_path / "BAXY").glob("bench-*"))
    assert f"profile of this run: {profile} (2 files, 2100 bytes)" in capsys.readouterr().out


def test_the_judges_hash_is_taken_before_the_lines_are_judged(tmp_path, monkeypatch):
    # Hashing the 35B GGUF with no cache takes minutes: after judge(), every verdict lived only in memory meanwhile,
    # and a run killed then lost them.
    order = []
    run_dir = tmp_path / "runs" / "lbl-falsedades"
    run_dir.mkdir(parents=True)
    (run_dir / "transcripts.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(bench_falsedades, "BANKS", tmp_path)
    monkeypatch.setattr(bench_falsedades, "judge", lambda replicas, log_dir: order.append("judge") or [[]])
    monkeypatch.setattr(bench_falsedades, "judge_record", lambda: order.append("record") or {})
    monkeypatch.delenv("BAXY_RENEW_SEED", raising=False)
    monkeypatch.setattr(sys, "argv", ["bench_falsedades.py", "lbl", "--cases", "c.json", "--judge-only",
                                      "--judge", "local"])
    bench_falsedades.main()
    assert order == ["record", "judge"]


# R8-NB-2 (2026-10-28): repeated with a label already used, the e2e bench read the earlier run's events.jsonl as its
# own and stopped at once on that run's «conductor_not_ready», before the new App had emptied the file; the new App
# would also have replayed the earlier commands/ from 00001 on. A used folder is refused and left as it was.
EARLIER = (b'{"type": "meta", "t_ms": 339}\n'
           b'{"type": "runtime", "ready": true, "mindReady": false, "t_ms": 189123}\n')


def earlier_run(run_dir: Path, events: bool = True) -> dict:
    (run_dir / "commands").mkdir(parents=True)
    (run_dir / "commands" / "00001.json").write_bytes(b'{"exit": true}')
    (run_dir / "results.jsonl").write_bytes(b'{"summary": {"ok": 3}}\n')
    if events:
        (run_dir / "events.jsonl").write_bytes(EARLIER)
    return {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}


def launches(monkeypatch) -> list:
    launched = []
    monkeypatch.setattr(bench_e2e.subprocess, "Popen", lambda *_, **options: launched.append(options) or
                        SimpleNamespace())
    monkeypatch.setattr(bench_e2e, "set_aside_notepad_tabs", lambda _: 0)
    return launched


@pytest.mark.parametrize("events", [True, False])
def test_a_folder_an_earlier_conductor_wrote_is_refused_and_kept(tmp_path, monkeypatch, events) -> None:
    run_dir = tmp_path / "r-e2e"
    before = earlier_run(run_dir, events)
    launched = launches(monkeypatch)
    with pytest.raises(SystemExit, match="new label"):
        bench_e2e.Conductor(run_dir, tmp_path / "perfil")
    assert not launched and {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()} == before


def test_the_e2e_bench_refuses_a_used_label_before_the_desktop_is_looked_at(tmp_path, monkeypatch) -> None:
    before = earlier_run(tmp_path / "runs" / "r-e2e")
    cases = tmp_path / "cases.json"
    cases.write_bytes(b'[{"id": "C1"}]')
    monkeypatch.setattr(bench_e2e, "BANKS", tmp_path)
    monkeypatch.setattr(bench_e2e, "Isolation", lambda _: pytest.fail("the isolation check ran"))
    monkeypatch.setattr(sys, "argv", ["bench_e2e.py", "r", "--cases", str(cases)])
    with pytest.raises(SystemExit, match="new label"):
        bench_e2e.main()
    assert {p: p.read_bytes() for p in (tmp_path / "runs" / "r-e2e").rglob("*") if p.is_file()} == before


def test_a_run_void_before_its_conductor_starts_again_in_its_folder(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "r-e2e"
    (run_dir / "commands").mkdir(parents=True)
    (run_dir / "results.jsonl").write_bytes(b'{"summary": {"void": "x"}}\n')
    launched = launches(monkeypatch)
    conductor = bench_e2e.Conductor(run_dir, tmp_path / "perfil")
    assert len(launched) == 1 and conductor.events.wait(lambda _: True, 0.2) is None
    launched[0]["stdout"].close()


def test_the_falsehood_bench_refuses_every_used_replica_before_one_runs(tmp_path, monkeypatch) -> None:
    before = earlier_run(tmp_path / "runs" / "r-s1-falsedades")
    (tmp_path / "runs" / "r-s1-falsedades" / "transcripts.json").write_bytes(b"[]")
    cases = tmp_path / "cases.json"
    cases.write_bytes(b"[]")
    monkeypatch.setattr(bench_falsedades, "BANKS", tmp_path)
    monkeypatch.setattr(bench_falsedades, "run_conversations", lambda *_: pytest.fail("a replica ran"))
    monkeypatch.setattr(sys, "argv", ["bench_falsedades.py", "r", "--cases", str(cases), "--seeds", "0,1"])
    with pytest.raises(SystemExit, match="new label"):
        bench_falsedades.main()
    assert (tmp_path / "runs" / "r-s1-falsedades" / "transcripts.json").read_bytes() == b"[]"
    assert all(p.read_bytes() == data for p, data in before.items())
