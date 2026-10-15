"""Ceiling of the harness helper calls (scripts/cu_live), measured 2026-10-09 05:10-05:21 on the live batch.

In case t-menu-1 «--- verify» (verificar.ps1 through servidor_ps) waited 11 minutes on a secondary explorer.exe
(«baxy-prueba-v3 - Explorador de archivos») that stopped answering behind an application error dialog: the batch stood
still until that process was killed by hand. These tests check the general fix without touching the desktop: every
helper call has a ceiling and the batch goes on, the verification is never left reading as complete, the UIA and Shell
reads skip a window whose process does not answer, and the ledger stops a hung process born in the case by its exact
PID, never the shell's explorer, VS Code or Opera.
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


def _git_bash() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).parents[:3]:
        candidate = root / "bin" / "bash.exe"
        if candidate.exists() and "system32" not in str(candidate).lower():
            return str(candidate)
    return None


def _bash(script: str, timeout: int = 180) -> subprocess.CompletedProcess:
    bash = _git_bash()
    if bash is None or shutil.which("powershell") is None:
        pytest.skip("sin Git Bash o PowerShell")
    return subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", timeout=timeout)


def _ps(script: str, timeout: int = 120) -> str:
    if shutil.which("powershell") is None:
        pytest.skip("PowerShell no disponible")
    done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=timeout)
    return done.stdout + done.stderr


def _dormilon(tmp_path: Path) -> Path:
    d = tmp_path / "dormir.ps1"
    d.write_text("param([int]$S=0)\nif($S){ Start-Sleep -Seconds $S }\n\"ok $S\"\n", encoding="ascii", newline="\n")
    return d


def test_a_call_past_its_ceiling_is_cut_flagged_and_the_server_comes_back(tmp_path):
    dormir = _dormilon(tmp_path)
    script = (f'L="{LIVE.as_posix()}"; E="{dormir.as_posix()}"; . "$L/servidor_ps.sh"; servidor_ps_iniciar\n'
              'ps "$E"; A=$SERVIDOR_PS_VIVO\n'
              # Inside $(...) (how batch.sh reads most helpers): cut at the ceiling, flagged as not verified.
              't=$SECONDS; X=$(PS_TOPE=3 ps "$E" -S 120); echo "sub=[$X] $((SECONDS-t))"\n'
              # The next call from the batch's shell starts a new server and is answered by it.
              'ps "$E" -S 1; B=$SERVIDOR_PS_VIVO; [ -n "$B" ] && [ "$A" != "$B" ] && echo nuevo_servidor\n'
              # At the top level too, and the server after it answers again.
              't=$SECONDS; PS_TOPE=3 ps "$E" -S 120; echo "rc=$? $((SECONDS-t))"\n'
              'ps "$E" -S 2; [ -n "$SERVIDOR_PS_VIVO" ] && [ "$SERVIDOR_PS_VIVO" != "$B" ] && echo otro_servidor\n'
              # Without the server: the same ceiling on the powershell of the call.
              'CU_SERVIDOR_PS=0; SERVIDOR_PS_VIVO=; t=$SECONDS; PS_TOPE=3 ps "$E" -S 120; echo "sin=$? $((SECONDS-t))"\n')
    done = _bash(script)
    out = [ln for ln in done.stdout.replace("\r", "").splitlines() if ln]
    assert out[0] == "ok 0", done.stdout + done.stderr
    sub = out[1]
    assert '"resultado":"sin_respuesta","verificado":false,"script":"dormir.ps1","tope_s":3' in sub
    assert int(sub.rsplit(" ", 1)[1]) < 20
    assert out[2] == "ok 1" and out[3] == "nuevo_servidor"
    assert '"resultado":"sin_respuesta"' in out[4] and out[5].startswith("rc=1 ") and int(out[5].split()[1]) < 20
    assert out[6] == "ok 2" and out[7] == "otro_servidor"
    assert '"resultado":"sin_respuesta"' in out[8] and out[9].startswith("sin=1 ") and int(out[9].split()[1]) < 20
    # The batch output (stderr goes there) names the cut call.
    assert done.stderr.count("AVISO: dormir sin respuesta tras 3s") == 3
    assert "AVISO: servidor PowerShell del arnes reiniciado (1)" in done.stderr


def test_batch_gives_verify_its_own_ceiling_and_marks_the_verification_incomplete():
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert "CU_TOPE_VERIFY:-60" in batch
    # Both verify calls (before and after the case) go through the same ceiling.
    assert "verificar_fase antes\n" in batch and "verificar_fase despues\n" in batch
    assert 'ps "$L/verificar.ps1"' not in batch.replace(
        'PS_TOPE=$TOPE_VERIFY ps "$L/verificar.ps1"', "")
    assert "AVISO: verify sin respuesta (" in batch and "-Incompleta" in batch
    raw = (LIVE / "batch.sh").read_bytes() + (LIVE / "servidor_ps.sh").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    for name in ("verificar.ps1", "colgadas.ps1", "libro_lote.ps1"):
        data = (LIVE / name).read_bytes()
        assert b"\r\n" not in data and not data.startswith(b"\xef\xbb\xbf"), name
    for name in ("colgadas.ps1", "libro_lote.ps1"):
        assert (LIVE / name).read_bytes().isascii(), name


def test_verificar_starts_incomplete_and_skips_windows_that_do_not_answer():
    src = (LIVE / "verificar.ps1").read_text(encoding="utf-8")
    # A verification cut by the ceiling never reads as complete: the file says «en_curso» until the very end.
    assert src.index("motivo='en_curso'") < src.index("$dump['ventanas']=")
    assert src.index("Get-VentanasColgadas") < src.index("function Get-Dump")
    dump = src[src.index("function Get-Dump"):src.index("$dump=[ordered]")]
    assert dump.index("Test-VentanaResponde") < dump.index("FromHandle")
    assert "colgada=$true" in dump
    assert "$dump['colgadas']=" in src and "$dump['completa']=" in src
    expl = (ESTADO / "explorador_comun.ps1").read_text(encoding="utf-8")
    shell = expl[expl.index("function Get-ShellExplorerWindows"):expl.index("function Get-ShellPath")]
    assert "Get-VentanasColgadas" in shell and "Get-IndicesShellQueResponden" in shell


def test_hung_check_answers_for_live_windows_and_names_the_hung_ones(tmp_path):
    # On the desktop as it is now: every listed window that is not hung answers WM_NULL, and the hung list is JSON.
    out = _ps(f". '{(ESTADO / 'comun.ps1').as_posix()}'; . '{(ESTADO / 'apps_comun.ps1').as_posix()}'\n"
              "$c=@(Get-VentanasColgadas); $t=@(Get-TopWindows)\n"
              "$malas=@($t | Where-Object { $h=$_.hwnd; -not (Test-VentanaResponde ([IntPtr][long]$h)) -and -not ($c | Where-Object { $_.hwnd -eq $h }) })\n"
              "\"top=$($t.Count) colgadas=$($c.Count) incoherentes=$($malas.Count)\"")
    linea = [ln for ln in out.splitlines() if ln.startswith("top=")][-1]
    assert linea.endswith("incoherentes=0"), out
    salida = _ps(f"& '{(LIVE / 'colgadas.ps1').as_posix()}'")
    fila = json.loads([ln for ln in salida.splitlines() if ln.startswith("{")][-1])
    assert fila["estado"] == "colgadas" and isinstance(fila["colgadas"], list) and "resumen" in fila


def test_colgadas_marks_a_verification_file_incomplete(tmp_path):
    destino = tmp_path / "verificacion-despues.json"
    destino.write_text('{"caso":"x","completa":true}\n', encoding="utf-8")
    _ps(f"& '{(LIVE / 'colgadas.ps1').as_posix()}' -Incompleta '{destino}' -Caso 't-menu-1' -Fase despues -Tope 60")
    datos = json.loads(destino.read_text(encoding="utf-8"))
    assert datos["completa"] is False and datos["motivo"] == "sin_respuesta" and datos["tope_s"] == 60
    assert datos["caso"] == "t-menu-1" and datos["fase"] == "despues" and isinstance(datos["colgadas"], list)


def test_ledger_stops_a_hung_process_of_the_case_by_pid_never_the_shell_or_protected_apps():
    libro = (LIVE / "libro_lote.ps1").read_text(encoding="ascii")
    bloque = libro[libro.index("# Hung processes born in the case"):libro.index("$res=@()")]
    assert "Get-VentanasColgadas" in bloque and "Get-PidShell" in bloque
    lazo = libro[libro.index("if($pidsColgados -contains [int]$p.pid)"):]
    lazo = lazo[:lazo.index("continue\n  }") + 1]
    # Decided before any other rule (no UIA or COM on it), and never after the person's own processes are skipped.
    assert libro.index("if($prop -eq 'dueno'){ continue }") < libro.index("if($pidsColgados -contains [int]$p.pid)")
    assert "Get-DecisionColgado $prop" in lazo and "$aColgados+=$p" in lazo and "colgado:" in lazo
    decision = (ESTADO / "decisiones_comun.ps1").read_text(encoding="utf-8")
    assert "function Get-DecisionColgado" in decision
    cierre = libro[libro.index("foreach($p in $aColgados)"):]
    assert "Stop-Process -Id $p.pid -Force" in cierre and "procedencia=" in cierre
    # The decision on its own (pure function).
    out = _ps(f". '{(ESTADO / 'decisiones_comun.ps1').as_posix()}'\n"
              "$c=@(\n"
              " (Get-DecisionColgado 'lote' 'explorer' 10 20 $true $false),\n"   # secondary explorer of the case
              " (Get-DecisionColgado 'lote' 'explorer' 20 20 $true $false),\n"   # the shell's explorer (taskbar)
              " (Get-DecisionColgado 'lote' 'Code' 10 20 $true $false),\n"
              " (Get-DecisionColgado 'lote' 'opera' 10 20 $true $false),\n"
              " (Get-DecisionColgado 'dueno' 'mspaint' 10 20 $true $false),\n"
              " (Get-DecisionColgado 'sin_procedencia' 'mspaint' 10 20 $true $false),\n"
              " (Get-DecisionColgado 'lote' 'mspaint' 10 20 $false $false),\n"  # the person used the PC during its life
              " (Get-DecisionColgado 'lote' 'mspaint' 10 20 $true $false),\n"
              " (Get-DecisionColgado 'lote' 'explorer' 10 20 $false $false),\n"
              " (Get-DecisionColgado 'lote' 'WindowsTerminal' 10 20 $true $false),\n"
              " (Get-DecisionColgado 'lote' 'svchost' 10 20 $true $false),\n"
              " (Get-DecisionColgado 'lote' 'mspaint' 10 20 $true $true))\n"     # a protected (harness) process
              "$c -join ','")
    assert out.strip().splitlines()[-1] == ",".join([
        "detener", "no_tocar:shell", "no_tocar:protegida", "no_tocar:protegida", "no_tocar:no_es_del_lote",
        "no_tocar:no_es_del_lote", "no_tocar:dueno_no_quieto", "detener", "detener", "no_tocar:protegida",
        "no_tocar:protegida", "no_tocar:protegida"])


def test_readme_documents_the_ceiling():
    readme = (LIVE / "README.md").read_text(encoding="utf-8")
    assert "CU_PS_TOPE" in readme and "CU_TOPE_VERIFY" in readme and "colgadas.ps1" in readme
