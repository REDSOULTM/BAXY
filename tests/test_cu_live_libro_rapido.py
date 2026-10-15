"""Batch ledger cost per case (scripts/cu_live/libro_lote.ps1 and estado/apps_comun.ps1), 2026-10-09.

Measured on pasada r15b: libro_cerrar median 14.6 s, p90 53 s, max 230 s, growing over the batch. The owner-input record
of a long batch holds ~55 000 processes (4 MB): ConvertFrom-Json of it took 2.8 s per read, and the provenance walk
scanned the whole table per parent (1.3 s a parent, ~4 s a new process; a stale photo took the dry run to 573 s).
Win32_Process took 2-3 s per list and ~2 s per single-process lookup. These tests check that the faster reads give the
same keys, parents, names and provenance answers, so every guarantee of the ledger stays as it was.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "scripts" / "cu_live"
ESTADO = LIVE / "estado"


def _powershell(script: str, env: dict | None = None) -> list[str]:
    exe = shutil.which("powershell")
    if exe is None:
        pytest.skip("PowerShell no disponible")
    import os
    e = dict(os.environ)
    if env:
        e.update(env)
    done = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240, env=e)
    assert done.returncode == 0, done.stderr
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def _apps(calls: str) -> list[str]:
    return _powershell(f". '{(ESTADO / 'comun.ps1').as_posix()}'\n. '{(ESTADO / 'apps_comun.ps1').as_posix()}'\n"
                       "$ErrorActionPreference='Continue'\n" + calls)


def test_process_snapshot_gives_the_cim_keys_parents_and_names():
    out = _apps(
        "$env:CU_PROCESOS_CIM='1'; $cim=@(Get-ProcesosCim); $env:CU_PROCESOS_CIM=''\n"
        "$nt=@(Get-ProcesosCim); $h=@{}; foreach($c in $cim){ $h[$c.pid]=$c }\n"
        "$ok=0; $mal=0; foreach($n in $nt){ $c=$h[$n.pid]; if(-not $c){ continue }\n"
        "  if($c.clave -eq $n.clave -and $c.padre -eq $n.padre -and $c.nombre -eq $n.nombre -and [Math]::Abs($c.nacio-$n.nacio) -lt 0.0015){ $ok++ }else{ $mal++; \"MAL $($c.clave) $($n.clave) $($c.nombre) $($n.nombre)\" } }\n"
        "\"ok=$ok mal=$mal\"\n"
        "$a=Get-NacioProceso $PID; $env:CU_PROCESOS_CIM='1'; $b=Get-NacioProceso $PID; $env:CU_PROCESOS_CIM=''\n"
        "\"pid $($a.clave -eq $b.clave) $($a.nacio -eq $b.nacio)\"\n"
        "\"muerto $($null -eq (Get-NacioProceso 999999))\"")
    resumen = [x for x in out if x.startswith("ok=")][0]
    ok, mal = (int(p.split("=")[1]) for p in resumen.split())
    # A process may start or exit between the two reads; a key that differs for one that both saw would not.
    assert ok > 50 and mal == 0, out
    assert "pid True True" in out and "muerto True" in out


def test_dcomlaunch_pid_from_the_service_manager_matches_cim():
    out = _apps("\"$(Get-PidServicio 'DcomLaunch')|$((Get-CimInstance Win32_Service -Filter \"Name='DcomLaunch'\").ProcessId)\"\n"
                "\"[$(@(Get-PidServicio 'BaxyNoExiste').Count)]\"")
    a, b = out[0].split("|")
    assert a == b and int(a) > 0
    assert out[1] == "[0]"


def test_record_without_its_process_list_parses_the_same_and_the_index_keeps_every_row(tmp_path):
    # Names with brackets, braces, quotes and a non-ASCII letter (json.dump ensure_ascii, as registro_dueno.py writes).
    procesos = [{"pid": 10, "padre": 4, "nombre": "a]b", "nacio": 100.5},
                {"pid": 10, "padre": 4, "nombre": "x\"}{[", "nacio": 200.25},
                {"pid": 11, "padre": 10, "nombre": "ñandú", "nacio": 201.0}]
    doc = {"version": 1, "raiz": 42, "cubierto_desde": 1.5, "cubierto_hasta": 9.5, "roto": None,
           "cortes": [[2.0, 3.0]], "fallos_bucle": [], "reinicios": [], "intervalos_dueno": [[4.0, 5.0]],
           "procesos": procesos}
    ruta = tmp_path / "registro.json"
    ruta.write_text(json.dumps(doc, ensure_ascii=True), encoding="utf-8")
    # The same with the list in the middle of the record: everything after it is kept.
    doc2 = {"procesos": procesos, "raiz": 7, "intervalos_dueno": [[1.0, 2.0]]}
    ruta2 = tmp_path / "registro2.json"
    ruta2.write_text(json.dumps(doc2, ensure_ascii=True), encoding="utf-8")
    out = _apps(
        f"$r=Read-RegistroDueno '{ruta}'\n"
        "\"liviano $($r.raiz) $($r.cubierto_hasta) $(@($r.procesos).Count) $(@($r.intervalos_dueno).Count) $([bool]$r.PSObject.Properties['indice_procesos'])\"\n"
        f"$r=Read-RegistroDueno '{ruta}' -ConProcesos; $i=$r.indice_procesos\n"
        "\"indice $($i.Count) $(@($i[10]).Count) $(@($i[11]).Count) $(@($i[10])[1].nombre) $(@($i[11])[0].padre) $(@($i[10])[0].nacio)\"\n"
        "\"nombre11 $([int][char](@($i[11])[0].nombre[0]))\"\n"
        f"$r=Read-RegistroDueno '{ruta2}' -ConProcesos\n"
        "\"medio $($r.raiz) $(@($r.intervalos_dueno).Count) $($r.indice_procesos.Count)\"\n"
        f"$env:CU_REGISTRO='{ruta}'; $r=Get-RegistroDueno; \"get $($r.raiz) $(@($r.procesos).Count)\"")
    assert "liviano 42 9.5 0 1 False" in out or "liviano 42 9,5 0 1 False" in out
    assert out[1].startswith("indice 2 2 1 x\"}{[ 10 100")
    assert out[2] == "nombre11 241"
    assert out[3] == "medio 7 1 2"
    assert out[4] == "get 42 0"


def _tabla(filas) -> str:
    return "@(" + ",".join(f"[pscustomobject]@{{pid={p};padre={pp};nombre='{n}';nacio={t}}}" for p, pp, n, t in filas) + ")"


def test_provenance_walk_on_the_index_answers_like_the_table():
    from itertools import product
    filas = [(500, 1, "explorer", 50), (510, 500, "powershell", 200), (520, 510, "notepad", 205),
             (510, 999, "viejo", 10),  # an older owner of pid 510
             (600, 300, "Baxy", 150), (610, 600, "calc", 210), (700, 77, "persona", 20), (710, 700, "word", 220),
             (800, 12345, "huerfano", 230)]
    tabla = _tabla(filas)
    procesos = [(520, 510, "notepad", 205), (610, 600, "calc", 210), (710, 700, "word", 220), (800, 12345, "huerfano", 230),
                (511, 510, "hijo_temprano", 15)]
    calls = [f"$t={tabla}; $i=Get-IndiceProcesos $t"]
    for (p, pp, n, t), raices in product(procesos, ("@()", "@(510)")):
        proc = f"([pscustomobject]@{{pid={p};padre={pp};nombre='{n}';nacio={t}}})"
        calls.append(f"\"$(Get-ProcedenciaProceso $t {proc} {raices} @(500) 100)|$(Get-ProcedenciaProceso $i {proc} {raices} @(500) 100)\"")
    out = _apps("\n".join(calls))
    assert len(out) == 10
    for linea in out:
        lista, indice = linea.split("|")
        assert lista == indice, out
    # The answers themselves: a shell start after the photo, BAXY, the person's process, a parent never seen, and a
    # child older than the pid's current owner (the earlier owner 'viejo' was running before the photo).
    assert [x.split("|")[0] for x in out[::2]] == ["shell:200", "arnes", "dueno", "desconocida", "dueno"]
