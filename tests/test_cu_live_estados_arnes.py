"""Base states that pasada r9 (2026-10-08) did not meet, which left cases that could not be judged.

- v3-49: it leaned on v3-48 leaving 7-Zip in the test folder; v3-48 failed, v3-49 ended NO_CORRIO, and the judge took
  the evidence of its 2026-10-07 run for this one. The harness now writes 7-Zip's last folder and view itself
  (registro_escribe), and a case that does not run leaves no_corrio.json with the old files moved aside.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "scripts" / "cu_live"
ESTADO = LIVE / "estado"


def _powershell(script: str) -> list[str]:
    exe = shutil.which("powershell")
    if exe is None:
        pytest.skip("PowerShell no disponible")
    done = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def _git_bash() -> str | None:
    # Git's bash, never WSL's (WindowsApps\bash.exe or System32): the harness scripts run in Git Bash, and from
    # PowerShell the WSL launcher comes first on PATH (seen 2026-10-08 under the Fast gate).
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


def _casos() -> dict:
    return json.loads((ESTADO / "casos.json").read_text(encoding="utf-8"))


# --- v3-49: 7-Zip's folder and view written by the harness, not left by another case.

def _decision(arg: str) -> dict:
    src = (ESTADO / "decisiones_comun.ps1").as_posix()
    a = arg.replace("'", "''")
    out = _powershell(f". '{src}'\n$d=Get-DecisionRegistroEscribe '{a}' 'D:\\Docs'\n"
                      "[pscustomobject]@{ ok=$d.ok; clave=$d.clave; nombre=$d.nombre; valor=$d.valor; tipo=$d.tipo }"
                      " | ConvertTo-Json -Compress")
    return json.loads(out[-1])


def test_registry_value_the_harness_writes_is_under_hkcu_software_only():
    d = _decision("HKCU\\Software\\7-Zip\\FM|PanelPath0|{Documentos}\\baxy-prueba-v3\\")
    assert d == {"ok": True, "clave": "Software\\7-Zip\\FM", "nombre": "PanelPath0",
                 "valor": "D:\\Docs\\baxy-prueba-v3\\", "tipo": "String"}
    d = _decision("HKCU\\Software\\7-Zip\\FM|ListMode|dword:514")
    assert d["ok"] and d["tipo"] == "DWord" and d["valor"] == 514
    # A DWORD above 2^31 keeps its bits (Set-ItemProperty takes the signed Int32).
    assert _decision("HKCU\\Software\\X|V|dword:4294967295")["valor"] == -1
    # Counter-cases: another hive, HKCU outside Software, a climb out of the key, no name, a DWORD that does not fit.
    for bad in ("HKLM\\Software\\7-Zip\\FM|ListMode|dword:1", "HKCU\\Environment|TEMP|x",
                "HKCU\\Software\\..\\Environment|TEMP|x", "HKCU\\Software\\7-Zip\\FM||x",
                "HKCU\\Software\\7-Zip\\FM|ListMode|dword:4294967296", "HKCU\\Software\\7-Zip\\FM"):
        assert _decision(bad)["ok"] is False, bad


def test_registry_state_writes_reads_back_and_never_invents_a_key():
    key = f"BaxyPruebaArnes-{uuid.uuid4().hex[:8]}"
    script = (ESTADO / "registro_escribe.ps1").as_posix()
    got = _powershell(
        f"New-Item -Path 'HKCU:\\Software\\{key}' -Force | Out-Null\n"
        f"New-ItemProperty -Path 'HKCU:\\Software\\{key}' -Name ListMode -Value 771 -PropertyType DWord | Out-Null\n"
        "try{\n"
        f"& '{script}' -Arg 'HKCU\\Software\\{key}|PanelPath0|{{Documentos}}\\baxy-prueba-v3\\'\n"
        f"& '{script}' -Arg 'HKCU\\Software\\{key}|ListMode|dword:514'\n"
        f"& '{script}' -Arg 'HKCU\\Software\\{key}|ListMode|dword:514'\n"
        f"(Get-ItemProperty 'HKCU:\\Software\\{key}').ListMode\n"
        f"(Get-ItemProperty 'HKCU:\\Software\\{key}').PanelPath0 -eq "
        "(Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'baxy-prueba-v3\\')\n"
        f"& '{script}' -Arg 'HKCU\\Software\\{key}-no-existe|ListMode|dword:1'\n"
        f"& '{script}' -Arg 'HKLM\\Software\\{key}|ListMode|dword:1'\n"
        # The sort column: a word of an existing REG_BINARY; twice is 'ok'; a binary value that is not there is never
        # invented.
        f"New-ItemProperty -Path 'HKCU:\\Software\\{key}' -Name FSFolder -PropertyType Binary "
        f"-Value ([byte[]]@(for($i=0;$i -lt '{FSFOLDER_TRAS_V349}'.Length;$i+=2){{ [Convert]::ToByte('{FSFOLDER_TRAS_V349}'.Substring($i,2),16) }})) | Out-Null\n"
        f"& '{script}' -Arg 'HKCU\\Software\\{key}|FSFolder|bin32@4:4'\n"
        f"& '{script}' -Arg 'HKCU\\Software\\{key}|FSFolder|bin32@4:4'\n"
        f"& '{script}' -Arg 'HKCU\\Software\\{key}|RootFolder|bin32@4:4'\n"
        f"'hex=' + (-join @((Get-ItemProperty 'HKCU:\\Software\\{key}').FSFolder | ForEach-Object {{ $_.ToString('X2') }}))\n"
        f"}}finally{{ Remove-Item -Path 'HKCU:\\Software\\{key}' -Recurse -Force }}")
    lines = [json.loads(x) for x in got if x.startswith("{")]
    assert [x["resultado"] for x in lines] == ["corregido", "corregido", "ok", "sin_clave", "sin_argumento",
                                               "corregido", "ok", "sin_valor"]
    assert [x["verificado"] for x in lines] == [True, True, True, False, False, True, True, False]
    assert "514" in got and "True" in got
    assert "hex=" + FSFOLDER_TRAS_V349[:8] + "04000000" + FSFOLDER_TRAS_V349[16:] in got


def test_v349_starts_from_the_test_folder_in_a_non_details_view_without_leaning_on_v348():
    casos = _casos()
    st = casos["casos"]["v3-49"]
    assert "v3-49" not in casos.get("requiere", {}) and "v3-49" not in casos.get("sin_estado", {})
    cerrada = st.index("app_cerrada:7-Zip File Manager")
    abierta = st.index("app_abierta:7-Zip File Manager")
    escribe = [i for i, s in enumerate(st) if s.startswith("registro_escribe:")]
    # 7-Zip rewrites these values when it exits: written with it closed, before it opens.
    assert escribe and all(cerrada < i < abierta for i in escribe)
    assert any("PanelPath0|{Documentos}\\baxy-prueba-v3" in st[i] for i in escribe)
    assert any("ListMode|dword:514" in st[i] for i in escribe)  # list view in both panels, not Details (3)
    # The sort column too (revision 2026-10-08): a successful v3-49 leaves 7-Zip sorted by size (SortID 7), and the
    # next run would start with half the case done. Name (4), ascending (1), in Columns\FSFolder.
    assert any("7-Zip\\FM\\Columns|FSFolder|bin32@4:4" in st[i] for i in escribe)
    assert any("7-Zip\\FM\\Columns|FSFolder|bin32@8:1" in st[i] for i in escribe)


# 7-Zip's Columns\FSFolder as measured on this PC 2026-10-08 (version 1, SortID, Ascending, then the columns), with
# the sort a successful v3-49 leaves: SortID 7 (size).
FSFOLDER_TRAS_V349 = ("01000000070000000100000004000000"
                      "01000000A00000000700000001000000640000000C00000001000000640000000A000000")


def test_a_32_bit_word_of_an_existing_binary_value_is_patched_and_nothing_else():
    got = _decide("\n".join([
        "$d=Get-DecisionRegistroEscribe 'HKCU\\Software\\7-Zip\\FM\\Columns|FSFolder|bin32@4:4' 'D:\\Docs'",
        "\"$($d.ok) $($d.tipo) $($d.offset) $($d.valor)\"",
        # Counter-cases: an offset not on a word, a value that does not fit, no offset.
        "(Get-DecisionRegistroEscribe 'HKCU\\Software\\X|V|bin32@6:4' '').ok",
        "(Get-DecisionRegistroEscribe 'HKCU\\Software\\X|V|bin32@4:4294967296' '').ok",
        "(Get-DecisionRegistroEscribe 'HKLM\\Software\\X|V|bin32@4:4' '').ok",
        f"$b=[byte[]]@(for($i=0;$i -lt '{FSFOLDER_TRAS_V349}'.Length;$i+=2){{ [Convert]::ToByte('{FSFOLDER_TRAS_V349}'.Substring($i,2),16) }})",
        "$n=Get-DecisionBinarioParcheado $b 4 4",
        "-join @($n | ForEach-Object { $_.ToString('X2') })",
        "-join @($b | ForEach-Object { $_.ToString('X2') })",  # the value read is not changed in place
        "$null -eq (Get-DecisionBinarioParcheado ([byte[]]@(1,0,0,0,7)) 4 4)",  # too short: nothing invented
        "$null -eq (Get-DecisionBinarioParcheado $null 4 4)",
    ]))
    assert got[0] == "True Bin32 4 4" and got[1:4] == ["False", "False", "False"]
    assert got[4] == FSFOLDER_TRAS_V349[:8] + "04000000" + FSFOLDER_TRAS_V349[16:]  # only SortID changed
    assert got[5] == FSFOLDER_TRAS_V349 and got[6:] == ["True", "True"]


# --- A case that does not run cannot be judged on an earlier run's evidence.

def test_a_case_that_did_not_run_leaves_a_marker_and_moves_the_earlier_runs_files_aside(tmp_path):
    ev = tmp_path / "v2-v3-49"
    (ev / "molestia-control").mkdir(parents=True)
    for f in ("after.png", "trace.jsonl", "verificacion-despues.json"):
        (ev / f).write_text("2026-10-07", encoding="utf-8")
    lib = (LIVE / "evidencia_no_corrio.sh").as_posix()
    d = ev.as_posix()
    _bash(f'. "{lib}"; evidencia_no_corrio "{d}" v3-49 \'estado "ausente"\' 1')
    marker = json.loads((ev / "no_corrio.json").read_text(encoding="utf-8"))
    assert marker["caso"] == "v3-49" and marker["no_corrio"] is True and marker["motivo"] == "estado ausente"
    assert sorted(p.name for p in ev.iterdir()) == ["anterior", "no_corrio.json"]
    old = ev / marker["evidencia_anterior"]
    # Subfolders of the earlier run go too (revision 2026-10-08: molestia-control stayed in place).
    assert sorted(p.name for p in old.iterdir()) == ["after.png", "molestia-control", "trace.jsonl",
                                                     "verificacion-despues.json"]
    # A later case that does not run again replaces it: anterior/ folders never pile up.
    (ev / "after.png").write_text("2026-10-08", encoding="utf-8")
    _bash(f'. "{lib}"; evidencia_no_corrio "{d}" v3-49 otra 1')
    assert sorted(p.name for p in ev.iterdir()) == ["anterior", "no_corrio.json"]
    assert sorted(p.name for p in (ev / "anterior").iterdir()) == ["after.png"]
    # Nothing to move: the marker names no earlier evidence (the anterior/ there is older).
    _bash(f'. "{lib}"; evidencia_no_corrio "{d}" v3-49 otra 1')
    assert json.loads((ev / "no_corrio.json").read_text())["evidencia_anterior"] == ""
    # The attempt of this batch is kept (archivar=0), with the marker; when the case runs the marker goes away.
    (ev / "trace.jsonl").write_text("este lote", encoding="utf-8")
    _bash(f'. "{lib}"; evidencia_no_corrio "{d}" v3-49 "sin decisor" 0')
    assert (ev / "trace.jsonl").exists() and json.loads((ev / "no_corrio.json").read_text())["evidencia_anterior"] == ""
    _bash(f'. "{lib}"; evidencia_corre "{d}"')
    # Ronda 23: the trace is kept, in anterior/, so the run about to start appends to an empty one.
    assert not (ev / "no_corrio.json").exists() and not (ev / "trace.jsonl").exists()
    assert (ev / "anterior" / "trace.jsonl").read_text(encoding="utf-8") == "este lote"


def test_batch_marks_every_no_corrio_and_clears_the_marker_before_a_run():
    text = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert '. "$L/evidencia_no_corrio.sh"' in text
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if 'echo "NO_CORRIO:' in line:
            assert any("evidencia_no_corrio" in x for x in lines[i:i + 3]), line
    assert text.index('evidencia_corre "$EVB/$tag"') < text.index('bash "$L/cu_live.sh"')


# --- Elevated windows left before a case (Taskmgr, MMC consoles, Resource Monitor, admin consoles): closed by PID.

def _decide(script: str) -> list[str]:
    src = (ESTADO / "decisiones_comun.ps1").as_posix()
    return _powershell(f". '{src}'\n" + script)


def test_uac_lets_the_harness_elevate_silently_only_for_an_admin_with_no_prompt():
    got = _decide("\n".join([
        "Get-DecisionUacSilencioso 1 0 $true",      # this test PC: UAC on, elevate without prompting
        "Get-DecisionUacSilencioso 0 $null $true",  # UAC off: the harness already has full rights, nothing to raise
        "Get-DecisionUacSilencioso 1 5 $true",      # the default: a prompt would appear
        "Get-DecisionUacSilencioso 1 2 $true",      # secure-desktop prompt
        "Get-DecisionUacSilencioso 1 0 $false",     # a standard user
        "Get-DecisionUacSilencioso $null $null $true",  # unreadable policy
    ]))
    assert got == ["True", "False", "False", "False", "False", "False"]


def test_elevated_windows_closed_are_only_the_batchs_and_never_vscode_terminals_the_harness_chain_or_an_agents_tool():
    got = _decide(r"""
$v=@(
  [pscustomobject]@{ pid=10; hwnd=100; proceso='Taskmgr'; elevada=$true },
  [pscustomobject]@{ pid=10; hwnd=101; proceso='Taskmgr'; elevada=$true },
  [pscustomobject]@{ pid=11; hwnd=110; proceso='perfmon'; elevada=$true },
  [pscustomobject]@{ pid=12; hwnd=120; proceso='cmd'; elevada=$true },
  [pscustomobject]@{ pid=13; hwnd=130; proceso='Code'; elevada=$true },
  [pscustomobject]@{ pid=14; hwnd=140; proceso='powershell'; elevada=$true },
  [pscustomobject]@{ pid=15; hwnd=150; proceso='mmc'; elevada=$true },
  [pscustomobject]@{ pid=15; hwnd=151; proceso='mmc'; elevada=$true },
  [pscustomobject]@{ pid=16; hwnd=160; proceso='WindowsTerminal'; elevada=$true },
  [pscustomobject]@{ pid=17; hwnd=170; proceso='notepad'; elevada=$false },
  [pscustomobject]@{ pid=18; hwnd=180; proceso='osk'; elevada=$null }
)
# 13 VS Code; 14 the harness's own chain; 16 started by an agent's VS Code; 15 the app the state opened (hwnd 151).
# Every elevated one is proven the batch's ($lote), with the script's real protected list.
$lote=@(10,11,12,13,14,15,16,18)
$prot=@(Get-ProtegidosElevadas)
'[' + ((@(Get-DecisionElevadas $v $prot @([long]151) @(14,1) @(16) $lote) | ForEach-Object { "$($_.proceso):$($_.pid)" }) -join ',') + ']'
# Only 10 proven the batch's: the rest, elevated and unprotected, is somebody else's and stays.
'[' + ((@(Get-DecisionElevadas $v $prot @() @() @() @(10)) | ForEach-Object { "$($_.proceso):$($_.pid)" }) -join ',') + ']'
# The harness elevated itself (UAC off): nothing.
'[' + ((@(Get-DecisionElevadas $v $prot @() @() @() $lote $true) | ForEach-Object { "$($_.proceso):$($_.pid)" }) -join ',') + ']'
# The review's dry run (2026-10-08): the person's Taskmgr, Resource Monitors and MMC, none of the batch: none chosen;
# an elevated Windows Terminal or console of the person neither.
$r=@(
  [pscustomobject]@{ pid=39728; hwnd=1; proceso='Taskmgr'; elevada=$true },
  [pscustomobject]@{ pid=37128; hwnd=2; proceso='perfmon'; elevada=$true },
  [pscustomobject]@{ pid=36900; hwnd=3; proceso='perfmon'; elevada=$true },
  [pscustomobject]@{ pid=47400; hwnd=4; proceso='mmc'; elevada=$true },
  [pscustomobject]@{ pid=37460; hwnd=5; proceso='perfmon'; elevada=$true },
  [pscustomobject]@{ pid=500; hwnd=6; proceso='WindowsTerminal'; elevada=$true },
  [pscustomobject]@{ pid=501; hwnd=7; proceso='cmd'; elevada=$true }
)
'[' + ((@(Get-DecisionElevadas $r $prot @() @() @() @()) | ForEach-Object { "$($_.proceso):$($_.pid)" }) -join ',') + ']'
'[' + ((@(Get-DecisionElevadas $r $prot @() @() @() @(500,501)) | ForEach-Object { "$($_.proceso):$($_.pid)" }) -join ',') + ']'
""")
    # cmd (12), powershell (14), WindowsTerminal (16) and VS Code are protected even when the batch started them.
    assert got == ["[Taskmgr:10,perfmon:11]", "[Taskmgr:10]", "[]", "[]", "[]"]


def test_sin_obstaculos_asks_the_batch_ledger_and_protects_what_it_never_acts_on():
    text = (ESTADO / "sin_obstaculos.ps1").read_text(encoding="utf-8")
    assert "$excluidos=@(Get-ExcluidosObstaculos)" in text and "$protegidosElev=@(Get-ProtegidosElevadas)" in text
    assert "Test-ProcesoDelLote ([int]$x)" in text and "$libroElev.ContainsKey(" in text
    assert "$delLote ((Test-Elevada $PID) -eq $true)" in text
    prot = _decide("(@(Get-ProtegidosElevadas) | Sort-Object) -join ','")[0].split(",")
    for name in ("WindowsTerminal", "powershell", "pwsh", "cmd", "conhost", "OpenConsole", "python", "pythonw",
                 "Code", "Claude", "Baxy", "explorer"):
        assert name in prot, name


def test_ancestors_follow_parents_born_before_and_stop_at_a_reused_pid_or_a_loop():
    got = _decide(r"""
$t=@{
  1=[pscustomobject]@{ padre=0; nacio=1.0 }
  2=[pscustomobject]@{ padre=1; nacio=2.0 }
  3=[pscustomobject]@{ padre=2; nacio=3.0 }
  4=[pscustomobject]@{ padre=9; nacio=4.0 }
  9=[pscustomobject]@{ padre=1; nacio=5.0 }
  6=[pscustomobject]@{ padre=7; nacio=6.0 }
  7=[pscustomobject]@{ padre=6; nacio=5.0 }
}
(@(Get-AncestrosProceso $t 3) -join ',')
'[' + (@(Get-AncestrosProceso $t 4) -join ',') + ']'
(@(Get-AncestrosProceso $t 6) -join ',')
""")
    # 4's parent 9 was born after it (a reused pid): no ancestors. 6 -> 7 -> 6 is a loop: only 7.
    assert got == ["2,1", "[]", "7"]


def test_an_elevated_process_is_stopped_by_its_exact_pid_where_uac_does_not_ask():
    comun = (ESTADO / "comun.ps1").as_posix()
    apps = (ESTADO / "apps_comun.ps1").as_posix()
    if _powershell(f". '{comun}'; . '{apps}'; Test-UacSilencioso")[-1] != "True":
        pytest.skip("UAC pregunta en este PC: el arnés no eleva")
    got = _powershell(f". '{comun}'; . '{apps}'\n" + r"""
$p=Start-Process -FilePath (Join-Path $env:windir 'System32\PING.EXE') -ArgumentList '-t','127.0.0.1' -Verb RunAs -WindowStyle Hidden -PassThru
Start-Sleep -Milliseconds 800
"elevada=$(Test-Elevada $p.Id)"
try{ Stop-Process -Id $p.Id -Force -ErrorAction Stop; 'normal=detenida' }catch{ 'normal=denegada' }
"nombre_ajeno=$(Stop-ProcesoElevado $p.Id 'otro')"
"elevado=$(Stop-ProcesoElevado $p.Id 'PING')"
"vivo=$([bool](Get-Process -Id $p.Id -ErrorAction SilentlyContinue))"
""")
    # The elevated NORMAL close comes first (taskkill without /F) and is enough for a console: nothing forced.
    assert got == ["elevada=True", "normal=denegada", "nombre_ajeno=salio", "elevado=cerrada_elevada", "vivo=False"]


def test_new_state_scripts_are_ascii_lf_without_bom():
    for name in ("registro_escribe", "github_repo_prueba", "repo_prueba_comun", "notas_sin_cuenta", "outlook_listo",
                 "sin_obstaculos", "decisiones_comun", "apps_comun"):
        raw = (ESTADO / f"{name}.ps1").read_bytes()
        assert raw.isascii() and b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf"), name


# --- GitHub Desktop (v3-54/55/56): the harness's test repo as the current repository, light theme for v3-56.

def test_test_repo_is_valid_only_exactly_as_built():
    msgs = "@('Primer commit de prueba','Agrega notas','Actualiza notas')"
    ok = "@{ existe=$true; rama='main'; limpio=$true; commits=@('Actualiza notas','Agrega notas','Primer commit de prueba'); ramas=@('prueba-rama','main') }"
    got = _decide("\n".join([
        f"Get-DecisionRepoPrueba {ok} {msgs} 'prueba-rama'",
        # Counter-cases: another branch checked out, a dirty tree, a commit more, a branch missing, no repo.
        f"$s={ok}; $s.rama='prueba-rama'; Get-DecisionRepoPrueba $s {msgs} 'prueba-rama'",
        f"$s={ok}; $s.limpio=$false; Get-DecisionRepoPrueba $s {msgs} 'prueba-rama'",
        f"$s={ok}; $s.commits=@('otro')+$s.commits; Get-DecisionRepoPrueba $s {msgs} 'prueba-rama'",
        f"$s={ok}; $s.ramas=@('main'); Get-DecisionRepoPrueba $s {msgs} 'prueba-rama'",
        f"Get-DecisionRepoPrueba @{{ existe=$false }} {msgs} 'prueba-rama'",
    ]))
    assert got == ["True", "False", "False", "False", "False", "False"]


def test_test_repo_is_built_with_three_commits_a_branch_and_the_same_hashes(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git no disponible")
    dec = (ESTADO / "decisiones_comun.ps1").as_posix()
    repo = (ESTADO / "repo_prueba_comun.ps1").as_posix()
    raiz = (tmp_path / "baxy-repo-prueba").as_posix()
    got = _powershell(f". '{dec}'; . '{repo}'; $global:RepoPruebaRaiz='{raiz}'\n"
                      "\"nuevo=$(New-RepoPrueba)\"\n"
                      "(Invoke-GitPrueba @('rev-parse','HEAD')).out\n"
                      "[IO.File]::WriteAllText((Join-Path $global:RepoPruebaRaiz 'notas.txt'),'cambio')\n"
                      "\"sucio=$(Test-RepoPruebaValido (Get-RepoPruebaEstado))\"\n"
                      "\"rehecho=$(New-RepoPrueba)\"\n"
                      "(Invoke-GitPrueba @('rev-parse','HEAD')).out\n"
                      "(Invoke-GitPrueba @('rev-parse','prueba-rama~0')).out -eq (Invoke-GitPrueba @('rev-parse','main~1')).out")
    assert got[0] == "nuevo=True" and got[2] == "sucio=False" and got[3] == "rehecho=True"
    assert got[1] == got[4] and len(got[1]) == 40  # fixed author and dates: the same commit every time
    assert got[5] == "True"  # prueba-rama at the second commit


def test_test_repo_folder_is_emptied_only_when_proven_the_harnesss(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git no disponible")
    dec = (ESTADO / "decisiones_comun.ps1").as_posix()
    repo = (ESTADO / "repo_prueba_comun.ps1").as_posix()
    got = _decide("\n".join([
        "Get-DecisionRepoDelArnes @{ existe=$false }",
        "Get-DecisionRepoDelArnes @{ existe=$true; vacia=$true }",
        "Get-DecisionRepoDelArnes @{ existe=$true; vacia=$false; git_ok=$true; autores=@('prueba@baxy.invalid','prueba@baxy.invalid') }",
        # Counter-cases: one commit of somebody else, a folder with no git, a git that failed, a repo with no commit.
        "Get-DecisionRepoDelArnes @{ existe=$true; vacia=$false; git_ok=$true; autores=@('prueba@baxy.invalid','dueno@x.cl') }",
        "Get-DecisionRepoDelArnes @{ existe=$true; vacia=$false; git_ok=$false }",
        "Get-DecisionRepoDelArnes @{ existe=$true; vacia=$false; git_ok=$false; autores=@('prueba@baxy.invalid') }",
        "Get-DecisionRepoDelArnes @{ existe=$true; vacia=$false; git_ok=$true; autores=@() }",
    ]))
    assert got == ["True", "True", "True", "False", "False", "False", "False"]
    # Live: a repository of somebody else and a plain folder in its place are never touched.
    raiz = tmp_path / "baxy-repo-prueba"
    raiz.mkdir()
    (raiz / "tesis.docx").write_text("del dueno", encoding="utf-8")
    pre = f". '{dec}'; . '{repo}'; $global:RepoPruebaRaiz='{raiz.as_posix()}'\n"
    out = _powershell(pre + "\"nuevo=$(New-RepoPrueba) motivo=$global:RepoPruebaMotivo\"")
    assert out[-1] == "nuevo=False motivo=ajeno" and (raiz / "tesis.docx").read_text(encoding="utf-8") == "del dueno"
    (raiz / "tesis.docx").unlink()
    subprocess.run(["git", "-C", str(raiz), "init", "-q", "-b", "main"], check=True)
    (raiz / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(raiz), "add", "a.txt"], check=True)
    subprocess.run(["git", "-C", str(raiz), "-c", "user.name=Dueno", "-c", "user.email=dueno@x.cl", "-c",
                    "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "suyo"], check=True)
    out = _powershell(pre + "\"nuevo=$(New-RepoPrueba) motivo=$global:RepoPruebaMotivo\"")
    assert out[-1] == "nuevo=False motivo=ajeno" and (raiz / "a.txt").exists()
    # An empty folder (GitHub Desktop may hold it open) is built in place.
    shutil.rmtree(raiz, onerror=lambda f, p, e: (Path(p).chmod(0o700), f(p)))
    raiz.mkdir()
    out = _powershell(pre + "\"nuevo=$(New-RepoPrueba)\"")
    assert out[-1] == "nuevo=True"


def test_github_options_left_open_is_detected_and_makes_the_state_unverified():
    got = _decide("\n".join([
        "Get-DecisionOpcionesAbiertas @('Options','Accounts','Integrations','Git','Appearance','Light','Dark','Save','Cancel')",
        "Get-DecisionOpcionesAbiertas @('Current repository baxy-repo-prueba','History','Changes')",
        "Get-DecisionOpcionesAbiertas @('Appearance')",
    ]))
    assert got == ["True", "False", "False"]
    text = (ESTADO / "github_repo_prueba.ps1").read_text(encoding="utf-8")
    assert "$ok=($actual -and -not $opciones -and" in text and "$n -ceq 'Cancel'" in text


def test_github_desktop_shows_the_test_repo_only_without_cant_find():
    got = _decide("\n".join([
        "Get-DecisionGithubRepo @('File','Current repository baxy-repo-prueba','Current branch main') 'baxy-repo-prueba'",
        # r9: the owner's missing repo.
        "Get-DecisionGithubRepo @('Current repository RicardoYMontiel','Can''t find \"','RicardoYMontiel') 'baxy-repo-prueba'",
        "Get-DecisionGithubRepo @('Current repository baxy-repo-prueba','Can''t find \"') 'baxy-repo-prueba'",
        "Get-DecisionGithubRepo @('Current repository baxy-repo-prueba-2') 'baxy-repo-prueba'",
        "Get-DecisionTemaClaro 229", "Get-DecisionTemaClaro 35", "Get-DecisionTemaClaro $null",
    ]))
    assert got == ["True", "False", "False", "False", "True", "False", "False"]


def test_github_state_uses_only_uia_patterns_and_records_the_window_for_app_cerrada():
    text = (ESTADO / "github_repo_prueba.ps1").read_text(encoding="utf-8")
    assert "app_abierta.ps1" in text and "Get-Propios" in text  # app_abierta records it; app_cerrada closes it
    assert "SendKeys" not in text and "keybd_event" not in text and "SetCursorPos" not in text
    assert "'Add repository'" in text and "'Light'" in text and "'Save'" in text


# --- Sticky Notes (v3-34/35/36, t-drag-3): used without an account, with the harness's notes in its store.

def _plum(path: Path) -> None:
    import sqlite3
    con = sqlite3.connect(path)
    con.execute('create table "Note" ("Text" varchar, "WindowPosition" varchar, "IsOpen" integer, "IsAlwaysOnTop" '
                'integer, "CreationNoteIdAnchor" varchar, "Theme" varchar, "IsFutureNote" integer, "RemoteId" varchar, '
                '"ChangeKey" varchar, "LastServerVersion" varchar, "RemoteSchemaVersion" integer, "IsRemoteDataInvalid" '
                'integer, "PendingInsightsScan" integer, "Type" varchar, "Id" varchar primary key not null, "ParentId" '
                'varchar, "CreatedAt" bigint, "DeletedAt" bigint, "UpdatedAt" bigint)')
    con.execute('create table "User" ("Type" varchar, "Id" varchar primary key not null, "ParentId" varchar, '
                '"CreatedAt" bigint, "DeletedAt" bigint, "UpdatedAt" bigint)')
    con.execute("insert into User (Id) values ('usuario-1')")
    dev = "ManagedPosition=DeviceId:\\\\?\\DISPLAY#X;Position=1172,110;Size=400,400"
    con.execute("insert into Note (Text, WindowPosition, IsOpen, Theme, Id, ParentId) values ('', ?, 1, 'Yellow', 'vacia', 'usuario-1')", (dev,))
    con.execute("insert into Note (Text, WindowPosition, IsOpen, Theme, Id, ParentId) values ('\\id=11111111-1111-1111-1111-111111111111 del dueno', ?, 1, 'Blue', 'ajena', 'usuario-1')", (dev,))
    con.commit()
    con.close()


def _notas(db: Path, *args: str) -> dict:
    done = subprocess.run(["py", "-3.12", "-I", str(LIVE / "notas_prueba.py"), "--db", str(db), *args],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def test_harness_notes_are_written_once_with_fixed_ids_and_nobody_elses_note_changes(tmp_path):
    import sqlite3
    if shutil.which("py") is None:
        pytest.skip("py no disponible")
    db = tmp_path / "plum.sqlite"
    _plum(db)
    r = _notas(db, "--texto", "cita con el dentista el jueves", "--abierta", "baxy prueba", "--pantalla", "1920x1080",
               "--cerrar-demas", "--cerrar-vacias")
    assert r["verificado"] is True and "creada:baxy prueba" in r["hechos"] and "vacia_cerrada" in r["hechos"]
    con = sqlite3.connect(db)
    rows = {row[0]: row[1:] for row in con.execute("select Id, Text, IsOpen, WindowPosition from Note")}
    textos = {t: (o, wp) for _, (t, o, wp) in rows.items()}
    baxy = [v for t, v in textos.items() if t.endswith(" baxy prueba")][0]
    dent = [v for t, v in textos.items() if t.endswith(" cita con el dentista el jueves")][0]
    # The open note at the centre of the screen (400x400), on the display the store already knows; the other closed.
    assert baxy[0] == 1 and baxy[1].endswith("Position=760,340;Size=400,400") and "DeviceId:" in baxy[1]
    assert dent[0] == 0
    assert rows["vacia"][1] == 0  # an empty note closed, never deleted
    assert rows["ajena"][:2] == ("\\id=11111111-1111-1111-1111-111111111111 del dueno", 1)  # untouched
    con.close()
    # Again: no duplicate (fixed ids), the open note re-centred; then closed when another run opens none.
    _notas(db, "--texto", "cita con el dentista el jueves", "--abierta", "baxy prueba")
    _notas(db, "--texto", "cita con el dentista el jueves", "--texto", "baxy prueba", "--cerrar-demas")
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from Note").fetchone()[0] == 4
    assert con.execute("select count(*) from Note where IsOpen=1").fetchone()[0] == 1  # only the person's
    con.close()


def _plum_completo(path: Path) -> None:
    import sqlite3
    _plum(path)
    con = sqlite3.connect(path)
    con.execute('create table "SyncState" ("OutboundQueueJson" varchar, "Id" varchar primary key not null)')
    con.execute('create table "Media" ("LocalFileRelativePath" varchar, "Id" varchar primary key not null, '
                '"ParentId" varchar, "DeletedAt" bigint)')
    con.execute('create table "Stroke" ("Data" blob, "Id" varchar primary key not null, "ParentId" varchar, '
                '"DeletedAt" bigint)')
    g = "\\id=22222222-2222-2222-2222-222222222222 "
    for nid, text, is_open in (("v334", g + "Llamar al dentista el martes.", 1),       # v3-34's earlier attempt
                               ("v334b", g + "llamar al dentista el martes", 0),
                               ("mas", g + "llamar al dentista el martes y al banco", 1),  # more text: the person's
                               ("v335", g + "pagar la luz", 1),
                               ("imagen", "\\id=33333333-3333-3333-3333-333333333333", 1),
                               ("imagen2", g + "pagar la luz", 1)):
        con.execute("insert into Note (Text, IsOpen, Theme, Id, ParentId) values (?, ?, 'Purple', ?, 'usuario-1')",
                    (text, is_open, nid))
    con.execute("insert into Media (LocalFileRelativePath, Id, ParentId) values ('a.png', 'm1', 'imagen')")
    con.execute("insert into Media (LocalFileRelativePath, Id, ParentId) values ('b.png', 'm2', 'imagen2')")
    con.commit()
    con.close()


def test_a_cases_earlier_note_is_removed_and_nothing_with_an_image_or_more_text(tmp_path):
    import sqlite3
    if shutil.which("py") is None:
        pytest.skip("py no disponible")
    db = tmp_path / "plum.sqlite"
    _plum_completo(db)
    r = _notas(db, "--texto", "cita con el dentista el jueves", "--cerrar-vacias", "--quitar",
               "llamar al dentista el martes")
    assert r["verificado"] is True
    assert sorted(h for h in r["hechos"] if h.startswith("quitada:")) == ["quitada:llamar al dentista el martes"] * 2
    con = sqlite3.connect(db)
    ids = {row[0]: row[1] for row in con.execute("select Id, IsOpen from Note")}
    con.close()
    assert "v334" not in ids and "v334b" not in ids
    assert ids["mas"] == 1 and ids["v335"] == 1 and ids["ajena"] == 1  # other texts untouched
    assert ids["imagen"] == 1  # an "empty" note with an image is content: not closed by --cerrar-vacias
    assert ids["vacia"] == 0
    r = _notas(db, "--texto", "cita con el dentista el jueves", "--quitar", "Pagar la luz")
    con = sqlite3.connect(db)
    ids = {row[0] for row in con.execute("select Id from Note")}
    con.close()
    assert r["verificado"] is True and "v335" not in ids and "imagen2" in ids  # the one with an image stays


def test_nothing_is_written_while_sticky_notes_holds_an_account(tmp_path):
    import sqlite3
    if shutil.which("py") is None:
        pytest.skip("py no disponible")
    for how in ("sync", "remote"):
        db = tmp_path / f"plum-{how}.sqlite"
        _plum_completo(db)
        con = sqlite3.connect(db)
        if how == "sync":
            con.execute("insert into SyncState (Id) values ('s1')")
        else:
            con.execute("update Note set RemoteId='r-1' where Id='ajena'")
        con.commit()
        antes = con.execute("select count(*), sum(IsOpen) from Note").fetchone()
        con.close()
        r = _notas(db, "--texto", "cita con el dentista el jueves", "--abierta", "baxy prueba", "--cerrar-vacias",
                   "--quitar", "pagar la luz")
        assert r == {"resultado": "con_cuenta", "verificado": False, "hechos": []}, how
        con = sqlite3.connect(db)
        assert con.execute("select count(*), sum(IsOpen) from Note").fetchone() == antes, how
        con.close()


def test_v334_and_v335_start_without_the_note_an_earlier_run_left():
    c = _casos()["casos"]
    assert c["v3-34"][0] == "notas_sin_cuenta:sin=llamar al dentista el martes"
    assert c["v3-35"][0] == "notas_sin_cuenta:sin=pagar la luz"
    text = (ESTADO / "notas_sin_cuenta.ps1").read_text(encoding="utf-8")
    assert "if($Arg -like 'sin=*'){ $quitar=$Arg.Substring(4); $abierta='' }" in text
    assert "$pyArgs+=@('--quitar',$quitar)" in text and "'con_cuenta'" in text
    # An account window is closed only when the batch ledger proves its process, and never confirmed.
    assert "if(-not (Test-ProcesoDelLote ([int]$p.Id))){ continue }" in text


def test_sticky_notes_account_prompt_is_dismissed_without_signing_in():
    o = "[char]0xF3"
    got = _decide("\n".join([
        f"Get-DecisionPideCuenta @('Notas r', ('Iniciando sesi'+{o}+'n...'))",
        "Get-DecisionPideCuenta @('Let''s get you signed in')",
        "Get-DecisionPideCuenta @('Amarillo ventana de nota. baxy prueba','Nueva nota','Cerrar nota')",
        "'[' + (Get-DecisionBotonSinCuenta @('Iniciar sesion','Ahora no','Cancelar')) + ']'",
        "'[' + (Get-DecisionBotonSinCuenta @('Sign in','Cancel')) + ']'",
        "'[' + (Get-DecisionBotonSinCuenta @('Iniciar sesion','Cerrar nota','Cerrar')) + ']'",
        "Get-DecisionNotaVisible @('Amarillo ventana de nota. baxy prueba') 'baxy prueba'",
        "Get-DecisionNotaVisible @('Yellow note window. baxy prueba') 'baxy prueba'",
        "Get-DecisionNotaVisible @('Amarillo ventana de nota. ') 'baxy prueba'",
        "Get-DecisionNotaVisible @('Amarillo ventana de nota. otra baxy prueba x') 'baxy prueba'",
        # A note whose text says "sign in" is no prompt (revision 2026-10-08); a prompt beside it still is.
        "Get-DecisionPideCuenta @('Amarillo ventana de nota. sign in to the bank','Yellow note window. iniciar sesion')",
        "Get-DecisionPideCuenta @('Amarillo ventana de nota. sign in to the bank','Sign in')",
    ]))
    assert got == ["True", "True", "False", "[Ahora no]", "[Cancel]", "[]", "True", "True", "False", "False",
                   "False", "True"]


# --- Outlook (v3-05/06/07): profile loaded, on the inbox, nothing over it.

def test_outlook_windows_are_classed_and_the_inbox_means_the_mail_module():
    o, e = "[char]0xF3", "[char]0xF3"
    got = _decide("\n".join([
        "Get-DecisionVentanaOutlook 'Bandeja de entrada - e.x@uni.edu - Outlook' 'rctrl_renwnd32'",
        "Get-DecisionVentanaOutlook 'Abriendo - Microsoft Outlook' 'rctrl_renwnd32'",
        "Get-DecisionVentanaOutlook 'Cargando perfil' '#32770'",
        f"Get-DecisionVentanaOutlook ('Configuraci'+{o}+'n de cuenta de correo electr'+{e}+'nico') '#32770'",
        "Get-DecisionVentanaOutlook '86 aviso(s)' '#32770'",
        "Get-DecisionVentanaOutlook '3 Reminders' '#32770'",
        "Get-DecisionVentanaOutlook 'Calendario - e.x@uni.edu - Outlook' 'rctrl_renwnd32'",
        "Get-DecisionVentanaOutlook 'Mensaje (HTML)' 'rctrl_renwnd32'",
        "Get-DecisionOutlookEnCorreo 'Bandeja de entrada - e.x@uni.edu - Outlook'",
        "Get-DecisionOutlookEnCorreo 'Calendario - e.x@uni.edu - Outlook'",
    ]))
    assert got == ["principal", "cargando", "cargando", "cuenta", "avisos", "avisos", "principal", "otra", "True",
                   "False"]


def test_outlook_reminders_are_closed_never_dismissed():
    # A window that is not the harness's is closed with -SinConfirmar: a dialog its close raised is CANCELLED (the
    # mode wins over -SinGuardar), and in that mode no button that says yes, closes all or dismisses is ever chosen.
    got = _decide("\n".join([
        "Get-DecisionModoTrasCerrar $false $true", "Get-DecisionModoTrasCerrar $true $true",
        "Get-DecisionModoTrasCerrar $true $false", "Get-DecisionModoTrasCerrar $false $false",
        "'[' + (Get-DecisionBotonDialogo @('S' + [char]0xED,'No') 'cancelar') + ']'",
        "'[' + (Get-DecisionBotonDialogo @('Descartar todo','Descartar','Posponer','Cancelar') 'cancelar') + ']'",
        "'[' + (Get-DecisionBotonDialogo @('Yes','No') 'confirmar') + ']'",
    ]))
    assert got == ["cancelar", "cancelar", "sin_guardar", "confirmar", "[]", "[Cancelar]", "[Yes]"]
    comun = (ESTADO / "comun.ps1").read_text(encoding="utf-8")
    assert "Close-DialogosDeVentana $h (Get-DecisionModoTrasCerrar ([bool]$SinGuardar) ([bool]$SinConfirmar))" in comun
    for name in ("outlook_listo", "notas_sin_cuenta"):
        lines = [x for x in (ESTADO / f"{name}.ps1").read_text(encoding="utf-8").splitlines()
                 if "Close-WindowExact (" in x]
        assert lines and all("-SinConfirmar" in x for x in lines), name
    assert "Invoke-Element" not in (ESTADO / "outlook_listo.ps1").read_text(encoding="utf-8")


def test_r9_cases_start_from_their_new_states_and_lean_on_no_other_case():
    casos = _casos()
    c = casos["casos"]
    assert c["v3-05"] == ["outlook_listo"] and c["v3-06"] == ["outlook_listo"]
    assert c["v3-07"] == ["outlook_listo", "app_cerrada:Outlook (classic)"]
    assert c["v3-34"][0].startswith("notas_sin_cuenta") and c["v3-34"][-1].startswith("app_cerrada:")
    assert c["v3-36"] == ["notas_sin_cuenta"] and c["t-drag-3"] == ["notas_sin_cuenta:baxy prueba"]
    assert c["v3-54"] == ["github_repo_prueba", "app_cerrada:GitHub Desktop"]
    assert c["v3-55"] == ["github_repo_prueba"] and c["v3-56"] == ["github_repo_prueba:claro"]
    for case in ("v3-36", "t-drag-3", "v3-49"):
        assert case not in casos["requiere"], case
    for case in ("v3-05", "v3-06", "v3-36", "t-drag-3", "v3-49", "v3-54", "v3-56"):
        assert case not in casos["sin_estado"], case


def test_sin_obstaculos_stops_elevated_windows_before_reading_what_covers_the_case():
    text = (ESTADO / "sin_obstaculos.ps1").read_text(encoding="utf-8")
    assert text.index("Get-DecisionElevadas") < text.index("$vis=@(Get-VentanasVisibles)")
    assert "elevadas_quedan=$elevadasQuedan" in text and "$elevadasQuedan.Count -gt 0" in text
    apps = (ESTADO / "apps_comun.ps1").read_text(encoding="utf-8")
    # A batch or harness process that refuses Stop-Process because it is elevated goes through the elevated stop.
    assert apps.count("Stop-ProcesoElevado $ProcessId $Nombre }else{") == 1
    assert "Stop-ProcesoElevado ([int]$I.pid) ([string]$I.proceso)" in apps
