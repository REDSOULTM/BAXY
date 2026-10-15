"""Harness overhead between live cases (scripts/cu_live): the persistent PowerShell, hung windows and the time line.

Measured 2026-10-08 on lote r6: the conductor took 45-90 s a case and the case 3.5-4 min. A hung Resource Monitor made
every UIA top-window list wait 10 s (libro -Cerrar 34 s, verificar 13.5 s) and every helper ran in a new powershell.
These tests check the cuts keep what the harness verifies, without touching the desktop.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "scripts" / "cu_live"
ESTADO = LIVE / "estado"


def _git_bash() -> str | None:
    # Git's bash, never System32's (WSL): the harness scripts run in Git Bash.
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).parents[:3]:
        candidate = root / "bin" / "bash.exe"
        if candidate.exists() and "system32" not in str(candidate).lower():
            return str(candidate)
    return None


def _bash(script: str, timeout: int = 120) -> str:
    bash = _git_bash()
    if bash is None or shutil.which("powershell") is None:
        pytest.skip("sin Git Bash o PowerShell")
    done = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _servidores_vivos(marca: str) -> int:
    done = subprocess.run(["powershell", "-NoProfile", "-Command",
                           "@(Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.ProcessId -ne $PID "
                           f"-and $_.CommandLine -like '*servidor_ps.ps1*-Padre*' -and $_.CommandLine -like '*{marca}*' }}).Count"],
                          capture_output=True, text=True, timeout=60)
    return int(done.stdout.strip() or 0)


def test_ascii_lf_without_bom():
    for name in ("servidor_ps.ps1", "volumen_brillo.ps1"):
        raw = (LIVE / name).read_bytes()
        assert raw.isascii() and b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf"), name
    raw = (LIVE / "servidor_ps.sh").read_bytes()
    assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf")


def test_server_runs_helpers_like_a_new_powershell_and_ends_with_its_bash(tmp_path):
    eco = tmp_path / "eco.ps1"
    eco.write_text("param([switch]$Sw,[string]$Txt='',[string]$Otro='x')\n"
                   "\"sw=$Sw txt=[$Txt] otro=[$Otro]\"\n"
                   "if($Txt -eq 'salir'){ 'antes'; exit 3 }\n"
                   "'despues'\n", encoding="ascii", newline="\n")
    llamadas = ('ps "$E" -Sw -Txt "dos palabras" -Otro ""\n'
                'X=$(ps "$E" -Txt salir); echo "sub:$X"\n'
                'ps "$E" -Otro "-1 a"\n')
    base = f'L="{LIVE.as_posix()}"; E="{eco.as_posix()}"; . "$L/servidor_ps.sh"\n'
    con = _bash(base + "servidor_ps_iniciar\n" + 'echo "vivo=${SERVIDOR_PS_VIVO:+si}"\n' + llamadas)
    sin = _bash(base + "CU_SERVIDOR_PS=0 servidor_ps_iniciar\n" + llamadas)
    con_lineas = [ln for ln in con.replace("\r", "").splitlines() if ln]
    assert con_lineas[0] == "vivo=si"
    # Same lines through the server and through one powershell per call; an exit inside a helper ends the helper, not
    # the server (the call after it still answers), and a value that starts with '-' stays a value.
    assert con_lineas[1:] == [ln for ln in sin.replace("\r", "").splitlines() if ln]
    assert con_lineas[1:] == ["sw=True txt=[dos palabras] otro=[]", "despues", "sub:sw=False txt=[salir] otro=[x]",
                              "antes", "sw=False txt=[] otro=[-1 a]", "despues"]
    # The server ends with the bash that started it.
    marca = LIVE.as_posix().split("/")[-3]
    for _ in range(20):
        if _servidores_vivos(marca) == 0:
            break
        time.sleep(0.5)
    assert _servidores_vivos(marca) == 0


def test_a_server_that_does_not_answer_flags_the_call_and_the_batch_falls_back():
    src = (LIVE / "servidor_ps.sh").read_text(encoding="utf-8")
    # The callers grep '"verificado":false': a lost call never reads as a verified state.
    # Every call has a ceiling (CU_PS_TOPE, test_cu_live_arnes_tope.py checks it live).
    assert '"verificado":false' in src and 'read -r -t "$resta"' in src and "SERVIDOR_PS_VIVO=" in src
    assert 'timeout -k 5 "$tope" powershell -NoProfile -ExecutionPolicy Bypass -File "$@" 2>&1' in src


def test_window_lists_skip_hung_windows_before_reading_their_name():
    comun = (ESTADO / "comun.ps1").read_text(encoding="utf-8")
    apps = (ESTADO / "apps_comun.ps1").read_text(encoding="utf-8")
    top = apps[apps.index("function Get-TopWindows"):apps.index("function Find-AppWindows")]
    assert top.index("[EstadoColgada]::IsHungAppWindow($h)") < top.index("$c.Name")
    by_name = comun[comun.index("function Find-TopWindowByName"):comun.index("function Find-ById")]
    # Exact and case-sensitive like the UIA Name condition it replaces; the hung check comes first.
    assert "IsHungAppWindow" in by_name and "-ceq $Name" in by_name and "NameProperty" not in by_name
    assert by_name.index("IsHungAppWindow") < by_name.index("Current.Name")
    # The ledger lists the windows once for both of its uses; nothing is closed in between.
    libro = (LIVE / "libro_lote.ps1").read_text(encoding="ascii")
    assert libro.count("Get-TopWindows)") == 1 and libro.index("$topVentanas=") < libro.index("foreach($w in $topVentanas)")
    assert libro.index("foreach($w in $topVentanas)") < libro.index("Close-WindowExact")
    # The Start menu is read once per script run, never kept from an earlier run.
    assert "$global:AppsMenuInicio=$null" in apps and apps.count("@(Get-StartApps)") == 1 and "Get-StartApps |" not in apps


def test_listed_windows_are_unchanged_by_the_hung_check():
    if shutil.which("powershell") is None:
        pytest.skip("PowerShell no disponible")
    script = (f". '{(ESTADO / 'comun.ps1').as_posix()}'; . '{(ESTADO / 'apps_comun.ps1').as_posix()}'\n"
              "$a=@(Get-TopWindows | ForEach-Object { $_.hwnd }) -join ' '\n"
              "$n=@([Windows.Automation.AutomationElement]::RootElement.FindAll('Children',[Windows.Automation.Condition]::TrueCondition) | "
              "Where-Object { $h=[IntPtr]$_.Current.NativeWindowHandle; $h -ne [IntPtr]::Zero -and -not [EstadoColgada]::IsHungAppWindow($h) "
              "-and [EstadoW32]::IsWindowVisible($h) -and -not [string]::IsNullOrWhiteSpace($_.Current.Name) } | "
              "ForEach-Object { [long]$_.Current.NativeWindowHandle }) -join ' '\n"
              "$a=@($a -split ' ' | Sort-Object) -join ' '; $n=@($n -split ' ' | Sort-Object) -join ' '\n"
              "if($a -eq $n){ 'igual' }else{ \"distinto: $a | $n\" }")
    done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=120)
    assert done.stdout.strip().splitlines()[-1] == "igual", done.stdout + done.stderr


def test_batch_runs_helpers_through_the_server_started_after_the_ledger_and_the_record():
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert 'ps(){ powershell' not in batch and '. "$L/servidor_ps.sh"' in batch
    # The server keeps the environment it starts with: CU_REGISTRO and CU_LIBRO are exported before it.
    inicio = batch.index("\nservidor_ps_iniciar\n")
    assert batch.index('registro_iniciar "$L/logs/registro-') < inicio
    assert batch.index('export CU_LIBRO=') < inicio < batch.index("-DevolverPendientes")
    # Every case ends with its time line, after its cleanup, also when it does not run.
    assert batch.index("  limpiar_caso\n  t_informe\ndone") > 0
    assert 'NO_CORRIO: $id estado ausente (no cuenta contra BAXY)"; t_informe; continue' in batch


def test_time_line_is_ignored_by_the_readers_of_the_batch_output(tmp_path):
    out = tmp_path / "salida.txt"
    out.write_text('=================== v3-99\n"Hecho.", "diagnostic": null}\n"latency_ms":1200 \n'
                   'computer_use.end","detail":"reached.true.steps.2.ms.3000"}\n'
                   'tiempos: caso=40.1s conductor=30s arnes=10.1s | inicio=1.0 foto=0.5\n', encoding="utf-8")
    done = subprocess.run(["py", "-3.12", str(LIVE / "sumbench.py"), str(out)], capture_output=True, timeout=60)
    assert done.stdout.decode("utf-8").strip() == "v3-99 | ['1200'] | reached.true.steps.2.ms.3000 | Hecho. | -"


def test_live_case_reads_and_gives_back_volume_and_brightness_in_one_process_each():
    cu = (LIVE / "cu_live.sh").read_text(encoding="utf-8")
    assert "semantic_replay_state.ps1" not in cu
    assert 'volumen_brillo.ps1" -Leer' in cu and 'volumen_brillo.ps1" -Devolver -Nivel "$lvl" -Silencio "$mut"' in cu
    assert 'echo "state before: $VOL $BRI"' in cu and 'echo "state after restore: ' in cu
    if shutil.which("powershell") is None:
        pytest.skip("PowerShell no disponible")
    done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(LIVE / "volumen_brillo.ps1"),
                           "-Leer"], capture_output=True, text=True, timeout=60)
    assert re.fullmatch(r'\{"level":\d+,"muted":(true|false)\} \{"levels":.*\}', done.stdout.strip()), done.stdout + done.stderr
