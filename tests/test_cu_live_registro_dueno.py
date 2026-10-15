"""Owner-input record of the live harness (scripts/cu_live/registro_dueno.py): the pure rules, without hooks.

The batch ledger takes the person as idle only where this record covers, so the record itself must fail closed:
unknown injected input counts as the person's, and a hook Windows dropped stops the coverage instead of hiding input.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SIM, BAXY = 0x5349_4D55, 0x4241_5859


def _mod():
    spec = importlib.util.spec_from_file_location("registro_dueno", ROOT / "scripts" / "cu_live" / "registro_dueno.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_real_and_unmarked_injected_input_is_the_persons():
    m = _mod()
    assert m.es_input_dueno(False, 0, SIM, BAXY)
    # Deskflow/Synergy inject the person's real input without a mark: theirs (fail closed).
    assert m.es_input_dueno(True, 0, SIM, BAXY)
    # Counter-cases: the simulated user and BAXY mark their input.
    assert not m.es_input_dueno(True, SIM, SIM, BAXY)
    assert not m.es_input_dueno(True, BAXY, SIM, BAXY)


def test_instants_merge_into_intervals_within_the_grace():
    m = _mod()
    iv: list[list[float]] = []
    for t in (10.0, 10.5, 11.2, 13.0):
        m.agregar_instante(iv, t)
    assert iv == [[10.0, 11.2], [13.0, 13.0]]


def test_coverage_stops_where_the_hooks_stopped_seeing_input():
    m = _mod()
    assert m.cobertura_hasta(100.0, 95.0, 96.0, None) == (100.0, None)
    # The system saw input 4 s after the last one the hooks saw: the hooks were dropped; coverage ends there.
    assert m.cobertura_hasta(100.0, 99.0, 95.0, None) == (95.0, 95.0)
    # Once broken it never extends again.
    assert m.cobertura_hasta(200.0, 199.0, 199.0, 95.0) == (95.0, 95.0)
    # Within the tolerance: still covered.
    assert m.cobertura_hasta(100.0, 96.5, 96.0, None) == (100.0, None)


def test_input_the_hooks_missed_counts_whole_as_the_persons_and_the_hooks_go_back_on():
    m = _mod()
    # Round 7 (2026-10-08): every record broke 2-10 min in and stayed broken, so the ledger took the person as active in
    # almost every case and closed nothing the cases opened. Now the span the hooks missed is the person's input
    # (fail closed: never assumed idle) and coverage goes on once the hooks are back.
    assert m.tramo_no_visto(99.0, 95.0) == [95.0, 99.0]
    iv = [[90.0, 90.5]]
    m.agregar_tramo(iv, [95.0, 99.0])
    assert iv == [[90.0, 90.5], [95.0, 99.0]]
    m.agregar_tramo(iv, [99.5, 101.0])
    assert iv == [[90.0, 90.5], [95.0, 101.0]]
    # Counter-cases: within the tolerance, or without a system reading, nothing was missed.
    assert m.tramo_no_visto(96.5, 96.0) is None
    assert m.tramo_no_visto(None, 96.0) is None
    # A record with that span is never idle over it (the ledger's quiet check reads intervalos_dueno).
    text = (ROOT / "scripts" / "cu_live" / "registro_dueno.py").read_text(encoding="utf-8")
    assert "WM_REPONER" in text and "_poner_ganchos" in text and '"cortes"' in text


def test_recorder_exits_with_its_root_and_has_a_stop_file():
    text = (ROOT / "scripts" / "cu_live" / "registro_dueno.py").read_text(encoding="utf-8")
    assert "_raiz_viva" in text and "--parar" in text
    assert "\r\n" not in text


def test_root_is_dead_only_after_repeated_proof_and_any_other_error_is_retried():
    m = _mod()
    # Pasada r9 (2026-10-08 12:07): one failed psutil read ended the recorder with lote.sh alive; the ledger then took
    # the person as active for 2 h and closed nothing. A doubtful read ('duda') never counts.
    seguidas, fin = 0, False
    for _ in range(50):
        seguidas, fin = m.veredicto_raiz("duda", seguidas)
        assert not fin
    for _ in range(m.RAIZ_SEGUIDAS - 1):
        seguidas, fin = m.veredicto_raiz("muerta", seguidas)
        assert not fin
    # One live read in between starts the count again.
    seguidas, fin = m.veredicto_raiz("viva", seguidas)
    assert (seguidas, fin) == (0, False)
    for _ in range(m.RAIZ_SEGUIDAS):
        seguidas, fin = m.veredicto_raiz("muerta", seguidas)
    assert fin


class _NoSuch(Exception):
    pass


class _Denied(Exception):
    pass


class _Proc:
    def __init__(self, ps, pid):
        if pid == ps.root and ps.root_mode == "gone":
            raise _NoSuch()
        if pid == ps.root and ps.root_mode == "denied":
            raise _Denied()
        self.pid, self.ps = pid, ps

    def create_time(self):
        return self.ps.root_start if self.pid == self.ps.root else 1.0

    def ppid(self):
        return 1

    def name(self):
        return "x.exe"


class _Psutil:
    """psutil stand-in: the root can be fine, denied (AccessDenied-like) or gone; every third pids() call fails."""

    NoSuchProcess = _NoSuch

    def __init__(self, root):
        self.root, self.root_start, self.root_mode, self.calls = root, 100.0, "ok", 0

    def Process(self, pid):  # noqa: N802 — psutil's name
        return _Proc(self, pid)

    def pids(self):
        self.calls += 1
        if self.calls % 3 == 0:
            raise RuntimeError("psutil bajo carga")
        return [self.root]


def _registro(tmp_path, ps):
    m = _mod()
    r = m.Registro.__new__(m.Registro)
    r.psutil, r.raiz, r.parar = ps, ps.root, str(tmp_path / "parar")
    r.salida, r.lock, r.fin = str(tmp_path / "r.json"), threading.Lock(), threading.Event()
    r.intervalos, r.cortes, r.procesos, r.vistos, r.fallos, r.reinicios = [], [], {}, set(), [], []
    r.ultimo_gancho = r.roto = None
    r.desde, r.raiz_seguidas, r.continuar, r.tid = 1.0, 0, False, 0
    r.raiz_inicio = r._inicio_raiz()

    class _User32:
        def PostThreadMessageW(self, *a):  # noqa: N802
            return 1

    r.w32 = type("W", (), {"user32": _User32(), "WM_QUIT": 0x12})()
    r._ultimo_input_sistema = lambda: None
    return m, r


def test_the_recorder_loop_survives_errors_and_doubtful_root_reads(tmp_path, monkeypatch):
    ps = _Psutil(4242)
    m, r = _registro(tmp_path, ps)
    monkeypatch.setattr(m, "SONDEO_PROC_S", 0.01)
    monkeypatch.setattr(m, "ESCRITURA_S", 0.01)
    ps.root_mode = "denied"  # AccessDenied on the root for a while: never taken as dead
    t = threading.Thread(target=r.bucle, daemon=True)
    t.start()
    time.sleep(0.5)
    assert t.is_alive(), "the loop ended on errors that prove nothing"
    doc = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert doc["fallos_bucle"] and "psutil bajo carga" in doc["fallos_bucle"][-1][1]
    assert len(doc["fallos_bucle"]) <= m.FALLOS_GUARDADOS
    # The root really gone: the loop ends by itself after RAIZ_SEGUIDAS proofs.
    ps.root_mode = "gone"
    t.join(5)
    assert not t.is_alive()
    # A pid reused by another process (other start time) is dead too.
    ps2 = _Psutil(77)
    m2, r2 = _registro(tmp_path, ps2)
    ps2.root_start = 555.0
    assert all(r2._raiz_viva() for _ in range(m2.RAIZ_SEGUIDAS - 1)) and not r2._raiz_viva()
    # A first read that failed takes the start on the next good read (never "dead" for lack of it).
    ps3 = _Psutil(78)
    ps3.root_mode = "denied"
    _, r3 = _registro(tmp_path, ps3)
    assert r3.raiz_inicio is None
    ps3.root_mode = "ok"
    assert all(r3._raiz_viva() for _ in range(20)) and r3.raiz_inicio == 100.0


def test_a_restarted_recorder_keeps_the_record_and_counts_the_gap_as_the_persons():
    m = _mod()
    previo = {"raiz": 9, "cubierto_desde": 10.0, "cubierto_hasta": 50.0, "roto": None,
              "intervalos_dueno": [[20.0, 21.0]], "cortes": [],
              "procesos": [{"pid": 5, "padre": 9, "nombre": "a", "nacio": 30.0}]}
    r = m.retomar(previo, 80.0, 9)
    assert r["desde"] == 10.0
    assert r["intervalos"] == [[20.0, 21.0], [50.0, 80.0]]
    assert r["cortes"] == [[50.0, 80.0]] and r["reinicios"] == [[50.0, 80.0]]
    assert r["procesos"][0]["pid"] == 5
    # Counter-cases: another root's record, or nothing readable, starts from zero.
    assert m.retomar(previo, 80.0, 10) is None
    assert m.retomar(None, 80.0, 9) is None


def _git_bash() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).parents[:3]:
        candidate = root / "bin" / "bash.exe"
        if candidate.exists() and "system32" not in str(candidate).lower():
            return str(candidate)
    return None


def test_the_batch_restarts_a_dead_recorder_on_the_same_file_and_says_so(tmp_path):
    bash = _git_bash()
    if bash is None:
        pytest.skip("sin Git Bash")
    fake = tmp_path / "fake_registro.py"
    # A fake recorder (no hooks): writes its arguments, then lives until its stop file appears, or dies at once.
    fake.write_text(
        "import json, os, sys, time\n"
        "a = sys.argv\n"
        "out = a[a.index('--salida') + 1]; parar = a[a.index('--parar') + 1]\n"
        "with open(out, 'w') as f: json.dump({'continuar': '--continuar' in a}, f)\n"
        "if os.environ.get('FAKE_MORIR'): sys.exit(0)\n"
        "while not os.path.exists(parar): time.sleep(0.05)\n", encoding="utf-8")
    reg = (tmp_path / "registro.json").as_posix()
    script = (
        f'export CU_REGISTRO_PY="{fake.as_posix()}"; . "{(ROOT / "scripts" / "cu_live" / "registro.sh").as_posix()}";'
        f' FAKE_MORIR=1 registro_iniciar "{reg}" > /dev/null; sleep 2; touch -d "1 minute ago" "{reg}";'
        f' registro_vigilar; echo "pid_vivo=$(kill -0 $REGISTRO_PID 2>/dev/null && echo si || echo no)";'
        f' cat "{reg}"; echo; registro_vigilar; echo "segunda=$?"; registro_parar'
    )
    done = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", timeout=90)
    assert done.returncode == 0, done.stderr
    out = done.stdout
    assert "AVISO: el registro del dueno murio" in out and "se reinicia sobre el mismo archivo" in out
    assert "pid_vivo=si" in out and '"continuar": true' in out
    # A live recorder is left alone: nothing is said the second time.
    assert out.count("AVISO") == 1 and "segunda=0" in out
    lote = (ROOT / "scripts" / "cu_live" / "lote.sh").read_text(encoding="utf-8")
    assert lote.index("registro_vigilar") < lote.index('bash "$L/batch.sh" "$id"')


def test_the_message_loop_reads_only_fields_a_msg_has() -> None:
    # Live 2026-10-08: «msg.hwnd» (the field is «hWnd») raised AttributeError the first time Windows dropped the hooks
    # and WM_REPONER arrived, so the recorder died at every drop (12:07 in r9, 7 times in r11) and the ledger then took
    # the person as active and closed nothing of the batch.
    import re
    from ctypes import wintypes

    text = (ROOT / "scripts" / "cu_live" / "registro_dueno.py").read_text(encoding="utf-8")
    fields = set(re.findall(r"\bmsg\.([A-Za-z_]+)\b", text))
    assert fields, "the loop reads the message"
    assert all(hasattr(wintypes.MSG(), field) for field in fields), fields
