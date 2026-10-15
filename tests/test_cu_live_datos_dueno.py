"""Review r10a (2026-10-08), the owner's data and PC: the harness only closes or changes what it opened.

Each finding has its rule (a pure decision in scripts/cu_live/estado/decisiones_comun.ps1, checked with plain values)
and its counter-case, plus the wiring that makes the scripts use it. Nothing here touches the desktop.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "scripts" / "cu_live"
ESTADO = LIVE / "estado"


def _powershell(script: str, check: bool = True) -> list[str]:
    exe = shutil.which("powershell")
    if exe is None:
        pytest.skip("PowerShell no disponible")
    done = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if check:
        assert done.returncode == 0, done.stderr
    return [line.strip() for line in done.stdout.splitlines() if line.strip()] + (
        [] if check else [f"exit={done.returncode}", done.stderr])


def _decisiones(calls: list[str]) -> list[str]:
    return _powershell(f". '{(ESTADO / 'decisiones_comun.ps1').as_posix()}'\n" + "\n".join(calls))


def _b(v: bool) -> str:
    return "$true" if v else "$false"


def _arr(xs) -> str:
    return "@(" + ",".join(str(x) for x in xs) + ")"


def _cierre(intentado, ventana_viva, proceso_vivo, del_pid, propias, sin_detener=None, del_lote=False) -> str:
    extra = "" if sin_detener is None else f"; sin_detener={_b(sin_detener)}"
    return (f"Get-DecisionCierre @{{ intentado={_b(intentado)}; ventana_viva={_b(ventana_viva)}; "
            f"proceso_vivo={_b(proceso_vivo)}; nuevo=$true; host=$false; ventanas_del_pid={_arr(del_pid)}; "
            f"propias={_arr(propias)}; del_lote={_b(del_lote)}; ventanas_lote=@(){extra} }}")


# --- 1. apps_del_caso.ps1 never kills an app the person opened during the case -----------------------------------

def test_a_case_app_closes_only_with_positive_provenance_and_stops_only_with_the_person_idle_all_its_life():
    got = _decisiones([
        # The reviewer's scenario: Word was not open, the person opens it during the case and types (the ledger gives
        # it no positive provenance): never touched, whatever the person did, even a window BAXY looked at.
        "Get-DecisionAppDelCaso $false $false $true $false",
        "Get-DecisionAppDelCaso $false $false $false $false",
        "Get-DecisionAppDelCaso $false $false $false $true",
        # BAXY opened Word (ledger 'lote') and the person, active meanwhile, double-clicked a document of theirs: it
        # opens inside that same WINWORD (review r10b). The window BAXY opened closes normally; the other never.
        "Get-DecisionAppDelCaso $true $false $false $true",
        "Get-DecisionAppDelCaso $true $false $false $false",
        # A terminal or the Claude app with positive provenance: a parallel agent's window joins that process with no
        # input of the person, so only the window BAXY opened closes, normally, even with the person idle.
        "Get-DecisionAppDelCaso $true $true $true $true",
        "Get-DecisionAppDelCaso $true $true $true $false",
        # Counter-case: proven the batch's and the person idle all its life: the full close (Get-DecisionCierre).
        "Get-DecisionAppDelCaso $true $false $true $false",
    ])
    assert got == ["no_tocar:sin_procedencia", "no_tocar:sin_procedencia", "no_tocar:sin_procedencia",
                   "cerrar_sin_detener", "no_tocar:ventana_ajena", "cerrar_sin_detener", "no_tocar:ventana_ajena",
                   "cerrar"]


def test_a_window_closed_without_stopping_never_reaches_stop_process():
    got = _decisiones([
        # The save prompt stays and every window is the harness's: stopped only without sin_detener.
        _cierre(True, True, True, [10], [10], sin_detener=True),
        _cierre(True, True, True, [10], [10], sin_detener=False),
        _cierre(True, True, True, [10], [10]),
        # Window gone, a batch process with no window of the person: it exits only without sin_detener.
        _cierre(True, False, True, [], [10], sin_detener=True, del_lote=True),
        _cierre(True, False, True, [], [10], sin_detener=False, del_lote=True),
    ])
    assert got == ["no_cierra:sin_detener", "detener", "detener", "cerrada_proceso_vivo", "salir_sin_ventanas"]


def test_apps_del_caso_asks_the_ledger_and_passes_sin_detener_to_the_close():
    src = (ESTADO / "apps_del_caso.ps1").read_text(encoding="utf-8")
    assert "Test-ProcesoDelLote ([int]$w.app_pid) -ConProtegidos" in src
    assert "$protegida=($NoDetener -contains [string]$w.app_proceso)" in src
    assert "Get-DecisionAppDelCaso $delLote $protegida $quieto $deBaxy" in src
    # The window attribution is by exact hwnd from BAXY's journal since the process was born.
    assert "Read-ColaJournal $env:CU_JOURNAL" in src
    assert "(Get-ProcesosDeBaxy $lineasJournal $n.nacio).hwnds) -contains [long]$w.hwnd" in src
    assert "Test-QuietoDesde $n.nacio" in src
    assert "if($d -like 'no_tocar*'){" in src and "sin_detener=($d -eq 'cerrar_sin_detener')" in src
    assert "$NoDetener=@('WindowsTerminal','Claude')" in src
    # The decision reaches Close-AppPropia through Get-EstadoCierre.
    apps = (ESTADO / "apps_comun.ps1").read_text(encoding="utf-8")
    assert "sin_detener=[bool]$I.sin_detener" in apps
    assert "procesos_lote_protegidos" in apps
    # The ledger records a protected process with positive provenance (it never closes it itself).
    libro = (LIVE / "libro_lote.ps1").read_text(encoding="ascii")
    assert "$protegidasLote+=$p.clave" in libro and "$lote.procesos_lote_protegidos=" in libro
    # batch.sh reports what it left alone.
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert 'APPSC=$(ps "$L/estado/apps_del_caso.ps1" -Caso "$id" -Antes "$APPS"' in batch
    assert batch.index('libro_lote.ps1" -Cerrar -Libro "$FOTO"') < batch.index('apps_del_caso.ps1" -Caso "$id"')


# --- 2. no close by a part of a title ---------------------------------------------------------------------------

def test_the_batch_never_closes_by_a_title_and_close_window_wants_the_exact_title_of_a_new_window():
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert "close_window.ps1" not in batch
    src = (LIVE / "close_window.ps1").read_text(encoding="utf-8")
    assert "-like" not in src and "$n -ne $Title" in src and "$previas -contains $h" in src
    assert "Close-WindowExact $w" in src
    # Without knowing what was open before the case it refuses (counter-case: a title alone is not enough).
    script = (LIVE / "close_window.ps1").as_posix()
    refused = _powershell(f"& '{script}' -Title 'Descargas'", check=False)
    assert "exit=0" not in refused and "-Antes or -Libro" in refused[-1]
    # A title nobody has, with the windows before: nothing closed.
    assert _powershell(f"& '{script}' -Title 'baxy-r10a-sin-ventana' -Antes '0'") == []


# --- 3. new Explorer windows only with the person idle -----------------------------------------------------------

def test_new_explorer_windows_close_only_under_the_ledgers_rule_and_otherwise_are_reported():
    src = (ESTADO / "exploradores.ps1").read_text(encoding="utf-8")
    cerrar = src[src.index("if($CerrarNuevos){"):src.index("if($Limpiar){")]
    assert "Get-DecisionDuenoQuieto (Get-RegistroDueno $hasta)" in cerrar
    assert "Get-DecisionVentanaNueva 'dueno' (-not $quieto) $false $false" in cerrar
    assert "$quieto=$false" in cerrar
    assert "if($decision -eq 'cerrar_ventana'){ $w.Quit(); $cerradas+=$h }else{ $sinTocar+=$h }" in cerrar
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert 'exploradores.ps1" -CerrarNuevos -Antes "$EXPL" -Libro "$FOTO"' in batch
    # The rule: closed with the person idle; counter-case: active, left alone.
    assert _decisiones(["Get-DecisionVentanaNueva 'dueno' $false $false $false",
                        "Get-DecisionVentanaNueva 'dueno' $true $false $false"]) == ["cerrar_ventana", "no_tocar"]


# --- 4. the person's Calculator is never reset --------------------------------------------------------------------

def test_an_open_calculator_is_reset_only_when_it_is_the_harnesss():
    got = _decisiones([
        "Get-DecisionVentanaPrevia 500 @(500) @()",
        "Get-DecisionVentanaPrevia 500 @() @(500)",
        # Counter-cases: a window nobody recorded (the person's, half-done in Programmer mode); no window id.
        "Get-DecisionVentanaPrevia 500 @(600) @(700)",
        "Get-DecisionVentanaPrevia 500 @() @()",
        "Get-DecisionVentanaPrevia 0 @(0) @(0)",
    ])
    assert got == ["del_arnes", "del_arnes", "ajena", "ajena", "ajena"]
    src = (ESTADO / "calc_estandar.ps1").read_text(encoding="utf-8")
    check = src.index("Get-DecisionVentanaPrevia $h")
    assert check < src.index("$modoAntes=Get-CalcMode $w") and check < src.index("Set-CalcMode $w 'Standard'")
    assert "'ajena_abierta'" in src


# --- 5. a window an app of the person raised by itself is never closed -------------------------------------------

def _linea(ts: str, op: str, result: dict) -> str:
    return json.dumps({"payload": {"timestampUtc": ts, "operation": op, "phase": "completed",
                                   "response": {"result": result}}}, ensure_ascii=False, separators=(",", ":"))


def test_baxys_processes_come_from_its_journal_after_the_case_photo_only():
    desde = "1791472500"  # 2026-10-08T15:15:00Z
    lines = [
        # Before the photo: not this case.
        _linea("2026-10-08T15:14:04.39+00:00", "input.visible.controls",
               {"window": {"title": "Antes", "process": "OUTLOOK", "processId": 111, "hwnd": 1110}}),
        # A view after the photo, with a title holding an escaped quote: its exact process id.
        _linea("2026-10-08T15:16:00.5+00:00", "input.visible.controls",
               {"window": {"title": 'Doc "x" - Word', "process": "WINWORD", "processId": 222, "hwnd": 2220}}),
        # An older record without an id: the process name only.
        _linea("2026-10-08T15:16:30+00:00", "input.visible.controls",
               {"window": {"title": "Reloj", "process": "Time"}}),
        # A process BAXY opened.
        _linea("2026-10-08T15:17:00+00:00", "app.open", {"appId": "Fotos", "processId": 333, "windowHandle": 3330}),
        # A processId outside app.open and outside a window is nothing.
        _linea("2026-10-08T15:17:30+00:00", "input.visible.click", {"processId": 444, "windowHandle": 4440}),
        "", "no es json",
    ]
    arr = "@(" + ",".join("'" + ln.replace("'", "''") + "'" for ln in lines) + ")"
    got = _decisiones([f"$r=Get-ProcesosDeBaxy {arr} {desde}",
                       "($r.pids | Sort-Object) -join ','", "($r.procesos | Sort-Object) -join ','",
                       "($r.hwnds | Sort-Object) -join ','"])
    # Windows: the viewed one and the one app.open returned; never one before the photo or outside app.open.
    assert got == ["222,333", "Time", "2220,3330"]


def test_a_new_window_of_the_persons_process_closes_only_where_baxy_worked():
    de_baxy = "@{ procesos=@('Time'); pids=@(222,333) }"
    got = _decisiones([
        f"Test-AtribuidaABaxy @{{ pid=222; proceso='WINWORD'; app_pid=222; app_proceso='WINWORD' }} {de_baxy}",
        f"Test-AtribuidaABaxy @{{ pid=9; proceso='ApplicationFrameHost'; app_pid=333; app_proceso='Photos' }} {de_baxy}",
        f"Test-AtribuidaABaxy @{{ pid=55; proceso='Time'; app_pid=55; app_proceso='Time' }} {de_baxy}",
        # Counter-cases: an Outlook reminder or a Teams call in a process BAXY never touched; no journal at all.
        f"Test-AtribuidaABaxy @{{ pid=111; proceso='OUTLOOK'; app_pid=111; app_proceso='OUTLOOK' }} {de_baxy}",
        f"Test-AtribuidaABaxy @{{ pid=777; proceso='ms-teams'; app_pid=777; app_proceso='ms-teams' }} {de_baxy}",
        "Test-AtribuidaABaxy @{ pid=222; proceso='WINWORD'; app_pid=222; app_proceso='WINWORD' } @{ procesos=@(); pids=@() }",
    ])
    assert got == ["True", "True", "True", "False", "False", "False"]
    libro = (LIVE / "libro_lote.ps1").read_text(encoding="ascii")
    assert "$deBaxy=Get-ProcesosDeBaxy (Read-ColaJournal $Journal) $fotoHora" in libro
    assert "if(Test-AtribuidaABaxy $w $deBaxy){ $nuevasDueno+=$w }else{" in libro
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert "export CU_JOURNAL=" in batch and batch.index("export CU_JOURNAL=") < batch.index("servidor_ps_iniciar\n")
    tanda = (ROOT / "scripts" / "uso_real" / "tanda.ps1").read_text(encoding="utf-8")
    assert "-Journal (Join-Path $profileRoot 'journal\\missions.jsonl')" in tanda


def test_a_process_baxys_app_open_started_is_the_batchs_even_when_its_parent_chain_breaks():
    # Pasada r15b, v3-22: BAXY opened the Task Manager with the person's rights; the launcher exited within 0.4 s and
    # the elevated copy it relaunched (Taskmgr:48780) had a parent the 0.3 s recorder never saw, so the ledger called it
    # 'sin_procedencia' and it stayed on top of the next five cases. BAXY's journal names that process: app.open
    # completed after the photo, not a reused copy.
    desde = "1791472500"  # 2026-10-08T15:15:00Z
    opened = {"appId": "Administrador de tareas", "displayName": "Administrador de tareas",
              "alreadyRunning": False, "processId": 48780, "windowHandle": 13766422}
    reused = {"appId": "Bloc de notas", "alreadyRunning": True, "processId": 555, "windowHandle": 5550}
    before = {"appId": "Monitor de recursos", "alreadyRunning": False, "processId": 666, "windowHandle": 6660}
    started = json.dumps({"payload": {"timestampUtc": "2026-10-08T15:16:00+00:00", "operation": "app.open",
                                      "phase": "started", "arguments": {"processId": 777}}}, separators=(",", ":"))
    lines = [
        _linea("2026-10-08T15:14:00+00:00", "app.open", before),
        _linea("2026-10-08T15:16:01+00:00", "app.open", opened),
        # Counter-cases: a copy of the person's that BAXY reused; a record that is not a completed app.open.
        _linea("2026-10-08T15:16:02+00:00", "app.open", reused),
        started,
        _linea("2026-10-08T15:16:03+00:00", "input.visible.click", {"alreadyRunning": False, "processId": 888}),
    ]
    arr = "@(" + ",".join("'" + ln.replace("'", "''") + "'" for ln in lines) + ")"
    got = _decisiones([
        f"(Get-AbiertosPorBaxy {arr} {desde}) -join ','",
        # Born after the photo with no parent the record saw: the batch's when BAXY's journal opened it ...
        "Get-DecisionPropiedad @('10:1') '48780:5' $null 'desconocida' $false $true",
        # ... even born right after the person's input (BAXY's own record, not a guess) ...
        "Get-DecisionPropiedad @('10:1') '48780:5' 1500 'desconocida' $false $true",
        # ... never a process running before the photo, and without the journal's word it stays unproven.
        "Get-DecisionPropiedad @('48780:5') '48780:5' $null 'desconocida' $false $true",
        "Get-DecisionPropiedad @('10:1') '48780:5' $null 'desconocida' $false $false",
    ])
    assert got == ["48780", "lote", "lote", "dueno", "sin_procedencia"]
    libro = (LIVE / "libro_lote.ps1").read_text(encoding="ascii")
    assert "$abiertosBaxy=@(if(-not $barrido){ Get-AbiertosPorBaxy (Read-ColaJournal $Journal) $fotoHora })" in libro
    assert "$prop=Get-DecisionPropiedad $fotoProc $p.clave $ms $proc $cub ($abiertosBaxy -contains [int]$p.pid)" in libro


def test_the_journal_tail_is_read_whole_lines_only_and_nothing_without_a_journal(tmp_path):
    journal = tmp_path / "missions.jsonl"
    journal.write_text('{"a":1}\n{"b":22}\n{"c":333}\n', encoding="utf-8", newline="\n")
    pre = (f". '{(ESTADO / 'comun.ps1').as_posix()}'\n. '{(ESTADO / 'apps_comun.ps1').as_posix()}'\n")
    got = _powershell(pre + "\n".join([
        f"(Read-ColaJournal '{journal.as_posix()}') -join '|'",
        # Only the last bytes: the line cut in the middle is dropped, never read as a record.
        f"(Read-ColaJournal '{journal.as_posix()}' 14) -join '|'",
        f"'n=' + @(Read-ColaJournal '{(tmp_path / 'no-existe.jsonl').as_posix()}').Count",
        "'n=' + @(Read-ColaJournal '').Count",
    ]))
    assert got == ['{"a":1}|{"b":22}|{"c":333}', '{"c":333}', "n=0", "n=0"]


# --- 6. Notepad: one process, many windows -------------------------------------------------------------------------

def test_a_notepad_tab_is_emptied_only_when_untitled_and_made_of_test_texts():
    textos = json.loads((ESTADO / "textos_de_prueba.json").read_text(encoding="utf-8"))["textos"]
    t = textos[0].replace("'", "''")
    arr = "@(" + ",".join("'" + x.replace("'", "''") + "'" for x in textos) + ")"
    got = _decisiones([
        f"Get-DecisionPestanaBloc $true '' {arr}",
        f"Get-DecisionPestanaBloc $true '{t}' {arr}",
        f"Get-DecisionPestanaBloc $true '  {t.upper()}.  ' {arr}",
        # Counter-cases: the person's text, a test text plus the person's words, a file tab, only spaces.
        f"Get-DecisionPestanaBloc $true 'lista de compras del dueno' {arr}",
        f"Get-DecisionPestanaBloc $true '{t} y mi clave' {arr}",
        f"Get-DecisionPestanaBloc $false '{t}' {arr}",
        f"Get-DecisionPestanaBloc $true '   ' {arr}",
    ])
    assert got == ["vacia", "vaciar", "vaciar", "ajena", "ajena", "ajena", "ajena"]
    src = (LIVE / "clear_notepad.ps1").read_text(encoding="utf-8")
    assert "Where-Object { [int]$_.pid -eq $ProcessId -and [long]$_.hwnd -ne 0 }" in src
    assert "if($mias -notcontains $h){" in src and "Get-DecisionPestanaBloc $sin (Get-Value $d) $textos" in src
    assert "if($ajenas -gt 0){" in src and "Close-WindowExact $w" in src


# --- 8. a tanda never asks to close an app it did not open --------------------------------------------------------

CLOSE = re.compile(r"\b(cierra\w*|cerr[aá]\w*|ci[eé]rr\w*|close|kill|mata)\b", re.I)
OPEN = re.compile(r"\b(abr[eií]\w*|open|lanza|inicia)\b", re.I)


def _cierres_sin_abrir(conversations: list[dict]) -> list[str]:
    out = []
    for conv in conversations:
        opened = False
        for turn in conv["turns"]:
            if CLOSE.search(turn["text"]) and not opened:
                out.append(f"{conv['id']}: {turn['text']}")
            if OPEN.search(turn["text"]):
                opened = True
    return out


def test_every_close_in_a_tanda_follows_an_open_in_the_same_conversation():
    # A tanda runs on the owner's PC: «cierra chrome» closed the owner's browser and session (t2-c03, review r10a).
    # What a tanda closes is what an earlier turn of the same conversation opened.
    bad = []
    for path in sorted((ROOT / "scripts" / "uso_real" / "tandas").glob("*.json")):
        bad += _cierres_sin_abrir(json.loads(path.read_text(encoding="utf-8")).get("conversations", []))
    assert bad == []


def test_the_tanda_close_check_catches_a_close_with_nothing_opened_before():
    convs = [{"id": "x1", "turns": [{"text": "cierra chrome que me laggea"}]},
             {"id": "x2", "turns": [{"text": "close spotify"}, {"text": "open spotify"}]},
             {"id": "x3", "turns": [{"text": "abre configuracion"}, {"text": "ya ciérrala"}]}]
    assert _cierres_sin_abrir(convs) == ["x1: cierra chrome que me laggea", "x2: close spotify"]


def test_changed_harness_scripts_stay_lf_without_bom():
    for path in [LIVE / "close_window.ps1", LIVE / "clear_notepad.ps1", LIVE / "libro_lote.ps1",
                 ESTADO / "apps_del_caso.ps1", ESTADO / "exploradores.ps1", ESTADO / "calc_estandar.ps1"]:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw, path.name
    # The scripts rewritten here hold no non-ASCII literal (PowerShell 5.1 reads them as ANSI).
    for path in [LIVE / "close_window.ps1", LIVE / "clear_notepad.ps1", ESTADO / "apps_del_caso.ps1"]:
        assert path.read_bytes().isascii(), path.name
