"""Harness overhead per live case (scripts/cu_live), measured on pasada r9 + r11 (2026-10-08, 105 cases).

The repair of the base states ran in 85 cases and fixed 0 of 129 failing states; a OneNote leftover cost 15 s each
sin_restos (twice a case); a dead owner-input record made three helpers wait 3 s each; cu_live.sh spent ~10 s in gates
and volume. These tests check the cuts keep every check the harness makes, with fakes: no desktop, no BAXY.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "scripts" / "cu_live"
ESTADO = LIVE / "estado"


def _reparar():
    spec = importlib.util.spec_from_file_location("reparar_cu_live", LIVE / "reparar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git_bash() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).parents[:3]:
        candidate = root / "bin" / "bash.exe"
        if candidate.exists() and "system32" not in str(candidate).lower():
            return str(candidate)
    return None


def _powershell(script: str, env: dict | None = None) -> list[str]:
    exe = shutil.which("powershell")
    if exe is None:
        pytest.skip("PowerShell no disponible")
    done = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, env=env)
    assert done.returncode == 0, done.stderr
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


# Lines as pasada r9 / r11 printed them.
ONENOTE = ('{"estado":"sin_restos","resultado":"no_verificado","verificado":false,"avisos":[],'
           '"cerradas":["ONENOTE:10380:ventana:2295934:cerrada"],"quedan":["ONENOTE:10380:ventana_viva"],"ms":14902}')
OUTLOOK = ('{"estado":"sin_restos","resultado":"no_verificado","verificado":false,"avisos":[],"cerradas":[],'
           '"quedan":["OUTLOOK:34580:ventanas_nuevas"],"ms":1331}')
STEAM_ERROR = '{"estado":"steam_biblioteca","resultado":"error","verificado":false,"error":"No se puede procesar"}'
AJENA = '{"estado":"app_cerrada:Fotos","resultado":"ajena_abierta","verificado":false,"ajenas":[1],"ms":900}'
OSK = '{"estado":"sin_obstaculos","resultado":"obstruido","verificado":false,"dialogos":[],"encima":["osk"],"ms":303}'
NO_ABRE = '{"estado":"app_abierta:Notas rapidas","resultado":"no_abre","verificado":false,"ms":40000}'
OK = '{"estado":"app_cerrada:PowerPoint","resultado":"ok","verificado":true,"ms":801}'


def test_repair_is_skipped_only_when_every_failure_is_permanent():
    r = _reparar()
    # Permanent by kind: a refused leftover, a state that threw, the person's window, the elevated keyboard.
    assert r.decidir([OUTLOOK, STEAM_ERROR, OSK, OK], {})[0] is False
    assert r.decidir([AJENA, OK], {})[0] is False
    # Counter-cases: a close that was tried and failed (only the registry may call it permanent), an app that did not
    # open (slow launch), and any mix with one of them.
    assert r.decidir([ONENOTE, OK], {})[0] is True
    assert r.decidir([NO_ABRE], {})[0] is True
    assert r.decidir([OUTLOOK, NO_ABRE], {})[0] is True
    # Nothing failing: nothing to repair (batch.sh never asks then).
    assert r.decidir([OK], {})[0] is False


def test_a_failure_the_repair_left_as_it_was_is_not_repaired_again_for_ten_minutes():
    r = _reparar()
    reg = r.anotar([ONENOTE, OSK, "@@reparado@@", ONENOTE, OSK], {}, 1000.0)
    assert r.decidir([ONENOTE, OK], reg)[0] is False
    # Counter-cases: the repair changed it (another leftover left), another process, or the registry is old.
    otro = ONENOTE.replace("10380", "222")
    reg2 = r.anotar([ONENOTE, "@@reparado@@", otro], {}, 1000.0)
    assert ONENOTE not in json.dumps(reg2) and r.decidir([ONENOTE], reg2)[0] is True
    assert r.decidir([otro], reg)[0] is True
    assert r.decidir([NO_ABRE], r.anotar([NO_ABRE, "@@reparado@@", NO_ABRE], {}, 1000.0))[0] is False


def test_registry_entries_expire_and_survive_the_process(tmp_path):
    r = _reparar()
    f = tmp_path / "libro.permanentes.json"
    entrada = ONENOTE + "\n@@reparado@@\n" + ONENOTE + "\n"
    cmd = ["py", "-3.12", str(LIVE / "reparar.py")]
    subprocess.run(cmd + ["anotar", "--registro", str(f)], input=entrada, text=True, check=True, timeout=60)
    d = subprocess.run(cmd + ["decidir", "--registro", str(f)], input=ONENOTE + "\n" + OK + "\n", text=True,
                       capture_output=True, check=True, timeout=60)
    assert d.stdout.startswith("permanente sin_restos|no_verificado|ONENOTE:10380:ventana_viva")
    # Ten minutes later it is repaired again (it may close now).
    reg = json.loads(f.read_text(encoding="utf-8"))
    assert r.leer_registro(str(f), list(reg.values())[0] + r.VIGENCIA_S + 1) == {}
    # No registry at all, or an unreadable one: repaired, as before this change.
    (tmp_path / "roto.json").write_text("{", encoding="utf-8")
    d = subprocess.run(cmd + ["decidir", "--registro", str(tmp_path / "roto.json")], input=ONENOTE + "\n", text=True,
                       capture_output=True, check=True, timeout=60)
    assert d.stdout.strip() == "reparar"


def _preparar(tmp_path: Path, pasadas: list[list[str]], reparar_cmd: str = 'py -3.12 "$L/reparar.py"') -> tuple[str, list[str]]:
    """Runs batch.sh's preparar_caso with a fake «ps»: each base pass answers the given restos/estado/obstaculos lines."""
    bash = _git_bash()
    if bash is None or shutil.which("py") is None:
        pytest.skip("sin Git Bash o py")
    text = (LIVE / "batch.sh").read_text(encoding="utf-8")
    ini = text.index("preparar_caso(){")
    fn = text[ini:text.index("\n}\n", ini) + 3]
    fn = fn.replace('py -3.12 "$L/reparar.py"', reparar_cmd)
    for i, p in enumerate(pasadas):
        (tmp_path / f"p{i}.txt").write_text("\n".join(p) + "\n", encoding="utf-8")
    calls = tmp_path / "calls.txt"
    script = f"""
L="{LIVE.as_posix()}"; T="{tmp_path.as_posix()}"; tag=v2-x; id=x; REPARAR_REG="$T/reg.json"; MARCOS_PEND="$T/m.txt"
mkdir -p "$T/logs"; L_LOGS="$T/logs"
t_paso(){{ :; }}; frames(){{ :; }}
echo 0 > "$T/n"
# Called inside $(...): the pass number lives in a file.
ps(){{
  echo "$*" >> "$T/calls.txt"
  local n; n=$(cat "$T/n")
  case "$*" in
    *"-Estados sin_restos"*) sed -n 1p "$T/p$n.txt" ;;
    *"-Caso x"*) sed -n 2p "$T/p$n.txt" ;;
    *"-Estados sin_obstaculos"*) sed -n 3p "$T/p$n.txt"; [ -f "$T/p$((n+1)).txt" ] && echo $((n+1)) > "$T/n" ;;
  esac
}}
{fn.replace('"$L/logs/$tag.estado.jsonl"', '"$T/logs/estado.jsonl"')}
CU_ESTADO_ESTRICTO=0 preparar_caso; echo "RC=$? NOVERIF=[$NOVERIF]"
"""
    done = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    return done.stdout, calls.read_text(encoding="utf-8").splitlines()


def test_batch_repairs_once_a_new_failure_and_not_a_permanent_one(tmp_path):
    # A OneNote close that failed: repaired once (as before), and the failure that stayed goes to the registry.
    out, calls = _preparar(tmp_path, [[ONENOTE, OK, OSK], [ONENOTE, OK, OSK]])
    assert "--- se repara una vez" in out and sum("-Estados sin_restos" in c for c in calls) == 2
    assert "RC=0 NOVERIF=[sin_obstaculos sin_restos]" in out
    reg = json.loads((tmp_path / "reg.json").read_text(encoding="utf-8"))
    assert any("ONENOTE:10380:ventana_viva" in k for k in reg)
    # The next case of the batch with the same leftover: not repaired, same AVISO, same unverified states.
    out, calls = _preparar(tmp_path, [[ONENOTE, OK, OSK]])
    assert "--- no se repara: causa permanente" in out and "--- se repara una vez" not in out
    assert "AVISO: estado base sin verificar para x: sin_obstaculos sin_restos" in out
    assert sum("-Estados sin_restos" in c for c in calls) == 3  # 2 before + 1 now
    assert "RC=0 NOVERIF=[sin_obstaculos sin_restos]" in out


def test_batch_with_strict_states_still_does_not_run_a_case_whose_permanent_failure_stays(tmp_path):
    out, _ = _preparar(tmp_path, [[OUTLOOK, OK, OSK]])
    assert "--- no se repara: causa permanente" in out
    # CU_ESTADO_ESTRICTO=0 in _preparar: it runs flagged. With the default (1) the same NOVERIF returns 2.
    text = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert '[ -n "$NOVERIF" ] && [ "${CU_ESTADO_ESTRICTO:-1}" != 0 ] && return 2' in text


def test_batch_marks_a_case_that_runs_on_an_unverified_base_state(tmp_path):
    # Pasada r18, v3-44: app_cerrada said ajena_abierta, CU_ESTADO_ESTRICTO=0 ran it anyway and the judge counted it.
    ajena = ('{"estado":"app_cerrada:Panel de control","resultado":"ajena_abierta","verificado":false,'
             '"ajenas":["Panel de control"],"cerradas":[],"foco":"sin_cambio","ms":2138}')
    restos = '{"estado":"sin_restos","resultado":"ok","verificado":true,"avisos":[],"cerradas":[],"quedan":[],"ms":866}'
    obst = '{"estado":"sin_obstaculos","resultado":"ok","verificado":true,"dialogos":[],"encima":[],"ms":1233}'
    out, _ = _preparar(tmp_path, [[restos, ajena, obst], [restos, ajena, obst]])
    assert "ESTADO_BASE_SUCIO: x corre con el estado base sin verificar: app_cerrada:Panel de control" in out
    assert "RC=0 NOVERIF=[app_cerrada:Panel de control]" in out
    # Counter-case: a clean base state is never marked.
    limpio = tmp_path / "limpio"
    limpio.mkdir()
    out, _ = _preparar(limpio, [[restos, OK, obst]])
    assert "ESTADO_BASE_SUCIO" not in out and "RC=0 NOVERIF=[]" in out


def test_batch_repairs_as_before_when_the_decision_cannot_be_read(tmp_path):
    out, calls = _preparar(tmp_path, [[OUTLOOK, OK, OSK], [OUTLOOK, OK, OSK]], reparar_cmd="false")
    assert "--- se repara una vez" in out and sum("-Estados sin_restos" in c for c in calls) == 2
    # And a clean first pass never asks: no repair, no registry.
    limpio = tmp_path / "limpio"
    limpio.mkdir()
    out, calls = _preparar(limpio, [[OK, OK, OK]])
    assert "se repara" not in out and "RC=0 NOVERIF=[]" in out and not (limpio / "reg.json").exists()


def _decisiones(calls: list[str]) -> list[str]:
    return _powershell(f". '{(ESTADO / 'decisiones_comun.ps1').as_posix()}'\n" + "\n".join(calls))


def test_a_leftover_close_that_failed_is_not_tried_again_on_the_same_windows_for_ten_minutes():
    memo = "('{\"1:2\":{\"ventanas\":\"11 12\",\"t\":1000}}' | ConvertFrom-Json)"
    got = _decisiones([
        f"Get-DecisionReintentoResto {memo} '1:2' @(12,11) 1300",
        # Counter-cases: no memo, another process, another window set, ten minutes later, a clock that went back.
        "Get-DecisionReintentoResto $null '1:2' @(11,12) 1300",
        f"Get-DecisionReintentoResto {memo} '1:3' @(11,12) 1300",
        f"Get-DecisionReintentoResto {memo} '1:2' @(11,12,13) 1300",
        f"Get-DecisionReintentoResto {memo} '1:2' @(11,12) 1600",
        f"Get-DecisionReintentoResto {memo} '1:2' @(11,12) 900",
    ])
    assert got == ["sin_reintento", "intentar", "intentar", "intentar", "intentar", "intentar"]


def test_sin_restos_keeps_the_leftover_unverified_when_it_does_not_try_again():
    src = (ESTADO / "sin_restos.ps1").read_text(encoding="ascii")
    rama = src[src.index("'cerrar_ventanas' {"):src.index("'no_cierra:*'")]
    salto = rama[:rama.index("foreach($h in $vent)")]
    # The skip still lists it in quedan (verificado=false) and carries the memo forward; a failed close records it.
    assert "Get-DecisionReintentoResto $memo $p.clave" in salto and '$quedan+="$($p.nombre):$($p.pid):ventana_viva"' in salto
    assert "$memoNuevo[$p.clave]=$memo.($p.clave)" in salto and "break" in salto
    assert rama.count("$memoNuevo[$p.clave]=") == 2
    assert "verificado=($quedan.Count -eq 0)" in src and "sin_reintento=$sinReintento" in src
    # The memo lives next to the batch ledger (none without it: every leftover is tried, as before).
    assert "$env:CU_LIBRO -replace '\\.json$',''" in src and "restos_fallidos.json" in src


def test_a_dead_owner_record_is_returned_at_once_and_still_fails_closed(tmp_path):
    reg = tmp_path / "registro.json"
    ahora = time.time()
    reg.write_text(json.dumps({"version": 1, "cubierto_desde": ahora - 300, "cubierto_hasta": ahora - 60,
                               "intervalos_dueno": []}), encoding="utf-8")
    env = dict(os.environ, CU_REGISTRO=str(reg))
    script = (f". '{(ESTADO / 'comun.ps1').as_posix()}'; . '{(ESTADO / 'apps_comun.ps1').as_posix()}'\n"
              "$t=[Diagnostics.Stopwatch]::StartNew(); $h=Get-EpochAhora; $r=Get-RegistroDueno $h; $ms=$t.ElapsedMilliseconds\n"
              "\"$ms\"; [string](Get-DecisionDuenoQuieto $r ($h-100) $h)")
    ms, quieto = _powershell(script, env)[-2:]
    assert int(ms) < 1500 and quieto == "False"
    # Counter-case: a record 2 s behind (a live recorder writes every 0.5 s) is still waited for, up to 3 s.
    # Integración 20b: the PowerShell writes that record itself, after its start and its Add-Type, so it is 2 s behind
    # when it is read (written from here, a cold start of 8 s or more on a loaded machine made it look dead: flaky).
    fresh = (f". '{(ESTADO / 'comun.ps1').as_posix()}'; . '{(ESTADO / 'apps_comun.ps1').as_posix()}'\n"
             "$c=(Get-EpochAhora)-2; [IO.File]::WriteAllText($env:CU_REGISTRO, [string]::Format("
             "[Globalization.CultureInfo]::InvariantCulture, "
             "'{{\"version\": 1, \"cubierto_desde\": {0}, \"cubierto_hasta\": {1}, \"intervalos_dueno\": []}}', "
             "($c-298), $c))\n"
             "$t=[Diagnostics.Stopwatch]::StartNew(); $h=Get-EpochAhora; $r=Get-RegistroDueno $h; $ms=$t.ElapsedMilliseconds\n"
             "\"$ms\"; [string](Get-DecisionDuenoQuieto $r ($h-100) $h)")
    ms, quieto = _powershell(fresh, env)[-2:]
    assert int(ms) >= 2500 and quieto == "False"


def test_frames_are_read_back_without_a_fixed_wait():
    src = (LIVE / "marcos.ps1").read_text(encoding="ascii")
    cerrar = src[src.index("function Close-Marcos"):src.index("function Write-Pendientes")]
    assert "Start-Sleep -Milliseconds 600" not in cerrar
    # Still read back: what is alive and visible after the wait is a survivor (written to -Pendientes).
    assert "$sobreviven=@(@($cerradas+$fallos) | Where-Object { [EstadoW32]::IsWindow([IntPtr]$_) -and [EstadoW32]::IsWindowVisible([IntPtr]$_) })" in cerrar


FAKE_PS = r"""#!/usr/bin/env bash
echo "powershell $*" >> "$FAKE_DIR/calls.txt"
case "$*" in
  *idle.ps1*) n=$(cat "$FAKE_DIR/baxy_n" 2>/dev/null || echo 0); echo $((n>0 ? n-1 : 0)) > "$FAKE_DIR/baxy_n"
              echo "{\"idle\":3.0,\"fullscreen\":false,\"battery\":${FAKE_BAT:-90},\"charging\":true,\"baxy\":$((n>0 ? 1 : 0))}" ;;
  *volumen_brillo.ps1*-Leer*) echo '{"level":20,"muted":false} {"levels":[40]}' ;;
  *volumen_brillo.ps1*-Devolver*) echo '{"level":20,"muted":false} {"levels":[40]}' ;;
  *run_baxy_conductor.ps1*) sleep 1; exit 0 ;;
  *) echo "inesperado: $*" >&2; exit 9 ;;
esac
"""
FAKE_SMI = '#!/usr/bin/env bash\necho "nvidia-smi $*" >> "$FAKE_DIR/calls.txt"\necho ${FAKE_VRAM:-900}\n'
FAKE_PY = r"""#!/usr/bin/env bash
echo "py $*" >> "$FAKE_DIR/calls.txt"
case "$*" in
  *medidor.py\ espera*) exit 0 ;;
  *medidor.py\ medir*) ctl=$(cygpath -u "$(echo "$*" | sed 's/.*--control \([^ ]*\) .*/\1/')")
    echo '{"pid": 1, "hwnd": 2, "t": 0, "frente": true}' > "$ctl/listo.json"
    while [ ! -f "$ctl/parar" ]; do sleep 0.1; done; sleep 0.5; echo "molestia: perdidos=0"; exit 0 ;;
esac
"""


def _cu_live(tmp_path: Path, baxy_vivo: int = 0, **env_extra) -> tuple[subprocess.CompletedProcess, list[str]]:
    """cu_live.sh with fake powershell, nvidia-smi and py on PATH: no BAXY, no meter window, no volume change."""
    bash = _git_bash()
    if bash is None:
        pytest.skip("sin Git Bash")
    fake = tmp_path / "fake"
    fake.mkdir()
    for name, body in (("powershell", FAKE_PS), ("nvidia-smi", FAKE_SMI), ("py", FAKE_PY)):
        (fake / name).write_text(body, encoding="utf-8", newline="\n")
    (fake / "baxy_n").write_text(str(baxy_vivo), encoding="utf-8")
    turns = tmp_path / "x.turns"
    turns.write_text('{"text":"hola"}\n', encoding="utf-8")
    ev = tmp_path / "ev"
    env = dict(os.environ, FAKE_DIR=fake.as_posix(), CU_EVIDENCE=ev.as_posix(), **env_extra)
    # PATH in POSIX form (a «C:/...» entry splits at its colon) and every fake checked to win before cu_live.sh runs:
    # the real powershell/py would show the meter window and read the PC's volume.
    script = (f'F=$(cygpath -u "{fake.as_posix()}"); export PATH="$F:$PATH"; chmod +x "$F"/*; hash -r; '
              'for c in powershell py nvidia-smi; do [ "$(command -v $c)" = "$F/$c" ] || { echo "fake perdio: $c"; exit 7; }; done; '
              f'bash "{(LIVE / "cu_live.sh").as_posix()}" caso "{turns.as_posix()}"')
    done = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=120, env=env)
    assert done.returncode != 7, done.stdout
    calls = (fake / "calls.txt").read_text(encoding="utf-8").splitlines()
    return done, calls


def test_live_case_gates_take_one_powershell_and_keep_every_check(tmp_path):
    done, calls = _cu_live(tmp_path, CU_MOLESTIA="1")
    assert done.returncode == 0, done.stdout + done.stderr
    ps = [c for c in calls if c.startswith("powershell")]
    # One look (BAXY processes, fullscreen, battery), the VRAM, the volume read, the conductor, the volume given back.
    assert sum("idle.ps1" in c for c in ps) == 1 and not any("Get-Process" in c for c in ps)
    assert any(c.startswith("nvidia-smi") for c in calls)
    at = {k: next(i for i, c in enumerate(calls) if k in c) for k in
          ("idle.ps1", "nvidia-smi", "medidor.py medir", "-Leer", "run_baxy_conductor.ps1", "-Devolver")}
    # The meter and the volume read run side by side, both after the gates and before the conductor.
    assert at["idle.ps1"] < at["nvidia-smi"] < min(at["medidor.py medir"], at["-Leer"])
    assert max(at["medidor.py medir"], at["-Leer"]) < at["run_baxy_conductor.ps1"] < at["-Devolver"]
    out = done.stdout
    assert "state before: " in out and "state after restore: " in out and "conductor exit=0 wall=" in out
    assert out.index("molestia: perdidos=0") < out.index("state after restore: ") < out.index("conductor exit=")
    assert "tiempos_cu_live: puertas=" in out


def test_live_case_still_waits_for_a_baxy_that_is_closing_and_reads_every_gate_again(tmp_path):
    done, calls = _cu_live(tmp_path, baxy_vivo=1, CU_MOLESTIA="0")
    assert done.returncode == 0, done.stdout + done.stderr
    looks = [i for i, c in enumerate(calls) if "idle.ps1" in c]
    assert len(looks) == 2
    # VRAM is only read once no BAXY is alive (a closing Core still holds it).
    assert calls.index(next(c for c in calls if c.startswith("nvidia-smi"))) > looks[1]
    assert any("medidor.py espera" in c for c in calls) and "state before: " in done.stdout


def test_live_case_aborts_as_before_on_low_battery_codes_unchanged():
    cu = (LIVE / "cu_live.sh").read_text(encoding="utf-8")
    for msg, code in (("ABORT: BAXY already running", 3), ("ABORT: GPU busy", 5), ("ABORT: fullscreen or low battery", 4)):
        assert f'echo "{msg}"; exit {code}' in cu
    assert "[ $nb -ge 15 ]" in cu and "[ $nv -ge 30 ]" in cu and "[ $ni -ge 80 ]" in cu
    # Unreadable look: BAXY taken as alive (fail closed).
    assert 'if [ "${baxy:-1}" != 0 ]; then' in cu


def test_new_scripts_are_lf_without_bom():
    for p in (LIVE / "reparar.py", LIVE / "cu_live.sh", LIVE / "batch.sh", LIVE / "idle.ps1", LIVE / "marcos.ps1",
              ESTADO / "sin_restos.ps1", ESTADO / "apps_comun.ps1", ESTADO / "decisiones_comun.ps1"):
        raw = p.read_bytes()
        assert b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf"), p.name
    for p in (LIVE / "idle.ps1", LIVE / "marcos.ps1", ESTADO / "sin_restos.ps1", ESTADO / "apps_comun.ps1",
              ESTADO / "decisiones_comun.ps1"):
        assert p.read_bytes().isascii(), p.name
