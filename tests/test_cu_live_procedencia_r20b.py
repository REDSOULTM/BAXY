"""Ronda 20b, palanca 5: the Explorer window BAXY's app.open opened is the batch's by the journal's provenance, and the
annoyance meter counts the minimum edit distance.

Pasada r18: v3-43 left two Control Panel windows (15601624, 2889276) that BAXY's app.open opened, because the record
saw input during the case; v3-44 then called them the person's (app_cerrada ajena_abierta) and ran anyway, and a later
case typed into one. The meter's difflib gave 115 lost + 116 inserted for one character in v3-62 (57 + 58 in
t-long-3). Pure decisions with plain values and lines shaped like the real journal; nothing touches the desktop.
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


def _powershell(script: str) -> list[str]:
    exe = shutil.which("powershell")
    if exe is None:
        pytest.skip("PowerShell no disponible")
    done = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert done.returncode == 0, done.stderr
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def _decisiones(calls: list[str]) -> list[str]:
    return _powershell(f". '{(ESTADO / 'decisiones_comun.ps1').as_posix()}'\n" + "\n".join(calls))


def _git_bash() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).parents[:3]:
        candidate = root / "bin" / "bash.exe"
        if candidate.exists() and "system32" not in str(candidate).lower():
            return str(candidate)
    return None


def _app_open(seq: int, ts: str, result: dict, phase: str = "completed") -> str:
    # The shape of missions.jsonl (pasada r18, seq 556/584/1178): the message repeats the result with escaped quotes.
    message = json.dumps({"kind": "operation", "operation": "app.open", "observed": result}, separators=(",", ":"))
    payload = {"sequence": seq, "timestampUtc": ts, "phase": phase, "operation": "app.open",
               "response": {"status": phase, "message": message.replace('"', "\\u0022"), "result": result}}
    return json.dumps({"version": 2, "payload": payload}, ensure_ascii=False, separators=(",", ":"))


def _vista(seq: int, ts: str, root: int) -> str:
    observed = {"window": {"title": "Panel de control", "process": "explorer", "processId": 13304, "hwnd": root}}
    payload = {"sequence": seq, "timestampUtc": ts, "phase": "completed", "operation": "input.visible.controls",
               "response": {"status": "completed", "result": observed}}
    return json.dumps({"version": 2, "payload": payload}, ensure_ascii=False, separators=(",", ":"))


def _arr(lines: list[str]) -> str:
    return "@(" + ",".join("'" + ln.replace("'", "''") + "'" for ln in lines) + ")"


FOTO_V343 = "1791527200"  # 2026-10-09T06:26:40Z, before v3-43's app.open records
OPENED_1 = {"appId": "Panel de control", "displayName": "Panel de control", "alreadyRunning": False,
            "processId": 13304, "windowHandle": 15601624}
OPENED_2 = {"appId": "Panel de control", "displayName": "Panel de control", "alreadyRunning": False,
            "processId": 13304, "windowHandle": 2889276, "windowsActivation": True, "frontRestored": True}
# Tramo 3 (seq 1178, 08:08 UTC): a later case's app.open REUSED the leftover window and typed into its search box.
REUSED = {"appId": "Explorador de archivos", "displayName": "Explorador de archivos", "alreadyRunning": True,
          "processId": 13304, "windowHandle": 15601624}


def test_the_windows_baxys_app_open_opened_come_from_completed_records_after_the_photo_only():
    lines = [
        _app_open(400, "2026-10-09T06:20:00+00:00", {**OPENED_1, "windowHandle": 111}),  # before the photo
        _app_open(555, "2026-10-09T06:46:45.9+00:00", {"appId": "Panel de control"}, phase="started"),
        _app_open(556, "2026-10-09T06:46:46.4724097+00:00", OPENED_1),
        _vista(558, "2026-10-09T06:46:53.1673638+00:00", 777777),  # a window BAXY only looked at
        _app_open(584, "2026-10-09T06:47:11.5123656+00:00", OPENED_2),
        _app_open(1178, "2026-10-09T08:08:11.157894+00:00", {**REUSED, "windowHandle": 999}),
        "", "no es json",
    ]
    got = _decisiones([f"(@(Get-VentanasAbiertasPorBaxy {_arr(lines)} {FOTO_V343}) | Sort-Object) -join ','",
                       # Counter-case: no journal, no provenance (fail closed).
                       f"'n=' + @(Get-VentanasAbiertasPorBaxy @() {FOTO_V343}).Count",
                       # A photo taken after both records: they are not this case's.
                       f"'n=' + @(Get-VentanasAbiertasPorBaxy {_arr(lines[:5])} 1791531000).Count"])
    assert got == ["2889276,15601624", "n=0", "n=0"]


def test_v3_43_a_window_baxy_opened_closes_by_provenance_even_with_the_owner_active():
    de_baxy = "@(15601624,2889276)"
    got = _decisiones([
        # v3-43: new, BAXY's app.open opened it, the record said the owner was active: closed by provenance.
        f"Get-DecisionExploradorNuevo 15601624 @(4001) $true $false {de_baxy}",
        f"Get-DecisionExploradorNuevo 2889276 @(4001) $true $false {de_baxy}",
        # Wherever it shows now (BAXY navigated it off the test places): still BAXY's window.
        f"Get-DecisionExploradorNuevo 2889276 @(4001) $false $false {de_baxy}",
        # Counter-cases: the person's Explorer window on a test place with the owner active is never closed ...
        f"Get-DecisionExploradorNuevo 5005 @(4001) $true $false {de_baxy}",
        # ... a window BAXY only adopted or looked at (a view's window.hwnd, not in app.open's list) neither ...
        f"Get-DecisionExploradorNuevo 777777 @(4001) $true $false {de_baxy}",
        # ... one that was in the case photo never, even if BAXY's app.open returned it ...
        f"Get-DecisionExploradorNuevo 15601624 @(4001,15601624) $true $false {de_baxy}",
        # ... and without a journal nothing has provenance: the owner's activity decides (fail closed).
        "Get-DecisionExploradorNuevo 15601624 @(4001) $true $false @()",
        # The ledger's rule stays: a test place with the owner idle is closed; elsewhere it is not ours.
        "Get-DecisionExploradorNuevo 5005 @(4001) $true $true @()",
        "Get-DecisionExploradorNuevo 5005 @(4001) $false $true @()",
    ])
    assert got == ["cerrar_procedencia", "cerrar_procedencia", "cerrar_procedencia", "sin_tocar", "sin_tocar",
                   "previa", "sin_tocar", "cerrar_ventana", "ajena"]


def test_exploradores_closes_by_journal_provenance_and_hands_a_survivor_to_the_batch_ledger():
    src = (ESTADO / "exploradores.ps1").read_text(encoding="utf-8")
    cerrar = src[src.index("if($CerrarNuevos){"):src.index("if($Limpiar){")]
    assert "if(-not $Journal -and $env:CU_JOURNAL){ $Journal=$env:CU_JOURNAL }" in cerrar
    assert "$deBaxy=@(Get-VentanasAbiertasPorBaxy (Read-ColaJournal $Journal) ([double]$foto.hora_epoch))" in cerrar
    assert "$d=Get-DecisionExploradorNuevo $h $previas $lugar $quieto $deBaxy" in cerrar
    assert "if($d -eq 'cerrar_procedencia'){ try{ $w.Quit() }catch{}; $cerradas+=$h; $deProcedencia+=$h; continue }" in cerrar
    assert "if($sobreviven.Count){ [void](Add-VentanasLote $sobreviven) }" in cerrar
    # The provenance check comes after the photo check (a window in -Antes is never closed).
    assert cerrar.index("if($previas -contains $h){ continue }") < cerrar.index("Get-DecisionExploradorNuevo $h")
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert "\"sobreviven\":\\[[0-9]' && { LIMPIO=0;" in batch


def test_a_window_in_the_batch_ledger_is_closed_by_app_cerrada_and_retried_by_sin_restos():
    got = _decisiones([
        "Get-DecisionAjenaApp 15601624 @(15601624,2889276)",
        # Counter-cases: a window the ledger does not name is the person's; nothing without a ledger; hwnd 0.
        "Get-DecisionAjenaApp 5005 @(15601624,2889276)",
        "Get-DecisionAjenaApp 15601624 @()",
        "Get-DecisionAjenaApp 0 @(0)",
    ])
    assert got == ["cerrar_lote", "ajena", "ajena", "ajena"]
    app = (ESTADO / "app_cerrada.ps1").read_text(encoding="utf-8")
    assert "(Get-DecisionAjenaApp ([long]$_.hwnd) $vl) -eq 'cerrar_lote'" in app
    assert '"ventana_lote:$($h):no_cierra"' in app
    # A batch window still there is a failed close, never «ajena_abierta» (a permanent cause for reparar.py).
    assert "$ajenas=@($ajenas | Where-Object { $deLote -notcontains [long]$_.hwnd })" in app
    restos = (ESTADO / "sin_restos.ps1").read_text(encoding="ascii")
    assert "Get-ShellExplorerWindows | Where-Object { (Get-DecisionAjenaApp ([long]$_.HWND) $vl) -eq 'cerrar_lote' }" in restos
    assert restos.index("explorador:$($h):cerrar") < restos.index("if($Arg -eq 'seco'){ Write-Estado")


def test_add_ventanas_lote_merges_into_the_batch_ledger_and_does_nothing_outside_a_batch(tmp_path):
    libro = tmp_path / "libro.json"
    libro.write_text('{"hora_epoch":1.5,"procesos":["1:2"],"ventanas_lote":[10,20]}\n', encoding="utf-8")
    pre = f". '{(ESTADO / 'comun.ps1').as_posix()}'\n. '{(ESTADO / 'apps_comun.ps1').as_posix()}'\n"
    got = _powershell(pre + "\n".join([
        f"$env:CU_LIBRO='{libro}'",
        "Add-VentanasLote @(20,15601624)",
        "Add-VentanasLote @()",
        "$env:CU_LIBRO=''",
        "Add-VentanasLote @(2889276)",
    ]))
    assert got == ["True", "False", "False"]
    data = json.loads(libro.read_text(encoding="utf-8"))
    assert sorted(data["ventanas_lote"]) == [10, 20, 15601624] and data["procesos"] == ["1:2"]
    assert not libro.read_bytes().startswith(b"\xef\xbb\xbf")


def test_a_case_run_on_an_unverified_base_state_is_marked_for_the_judge(tmp_path):
    bash = _git_bash()
    if bash is None:
        pytest.skip("sin Git Bash")
    ev = tmp_path / "ev"
    script = f"""
. "{(LIVE / 'evidencia_no_corrio.sh').as_posix()}"
evidencia_estado_sucio "{ev.as_posix()}" v3-44 'app_cerrada:Panel de control'
cat "{ev.as_posix()}/estado_base_sucio.json"
evidencia_corre "{ev.as_posix()}"
[ -e "{ev.as_posix()}/estado_base_sucio.json" ] && echo queda || echo borrado
"""
    done = subprocess.run([bash, "-c", script], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    marca = json.loads(lines[0])
    assert marca["caso"] == "v3-44" and marca["estado_base_sucio"] is True
    assert marca["estados"] == "app_cerrada:Panel de control" and lines[-1] == "borrado"
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    fn = batch[batch.index("preparar_caso(){"):batch.index("limpiar_caso(){")]
    assert fn.index("&& return 2") < fn.index('[ -n "$NOVERIF" ] && echo "ESTADO_BASE_SUCIO: $id')
    after = batch[batch.index("CEX=$(grep"):]
    assert "\"$SUCIO\" > \"$L/logs/$tag.hecho\"" in after
    assert '[ -n "$NOVERIF" ] && evidencia_estado_sucio "$EVB/$tag" "$id" "$NOVERIF"' in after


# --- The meter: minimum edit distance, and a key the hook never saw counts as delivered if it is in the window ----

def _medidor_mod():
    import importlib.util
    import sys
    if sys.platform != "win32":
        pytest.skip("the meter declares user32 functions")
    sys.path.insert(0, str(LIVE / "molestia"))
    spec = importlib.util.spec_from_file_location("medidor_r20b", LIVE / "molestia" / "medidor.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_v3_62_one_character_the_hook_missed_is_no_loss_and_no_insertion():
    mod = _medidor_mod()
    sent = mod.typed_text(297)
    # Pasada r18, v3-62: the window holds all 297 keys; the hook logged 296 (the «q» of «tranquilo», index 139).
    delivered = sent[:139] + sent[140:]
    assert sent[139] == "q" and delivered[132:147] == "be tranuilo mie"
    assert mod.text_loss(delivered, sent, sent, 1) == (0, 0, 1)
    # Without the unseen key the same window is 1 inserted, never 115 lost + 116 inserted.
    assert mod.text_loss(delivered, sent) == (0, 1, 0)
    # t-long-3: the «l» of «tranquilo» at index 84, 57/58 before.
    sent3 = mod.typed_text(266)
    assert mod.text_loss(sent3[:84] + sent3[85:], sent3, sent3, 1) == (0, 0, 1)


def test_meter_edit_distance_counter_cases():
    mod = _medidor_mod()
    sent = mod.typed_text(300)
    # A real loss of 50 characters in a row still counts 50; one lost character counts 1.
    assert mod.text_loss(sent, sent[:100] + sent[150:]) == (50, 0, 0)
    assert mod.text_loss(sent, sent[:139] + sent[140:]) == (1, 0, 0)
    # Foreign text BAXY wrote in the person's window is inserted, even with a key the hook did not see.
    assert mod.text_loss(sent[:200], sent[:120] + "XYZ" + sent[120:200], sent[:201], 1) == (0, 3, 0)
    # A replaced character is one lost and one inserted.
    assert mod.text_loss("hola mundo", "hola nundo") == (1, 1, 0)
    assert mod.common_len("", "abc") == 0


def test_meter_report_keeps_swallowed_keys_and_recovers_the_unseen_one():
    mod = _medidor_mod()
    m = mod.Medidor(None)
    m.t_start, m.t_end, m.hwnd = 10.0, 20.0, 1
    # v3-40: 158 keys swallowed with the window stolen, and one delivered key missing from the window: 159, as before.
    sent = mod.typed_text(210)
    m.typed, m.swallowed = 210, 158
    m.delivered = list(sent[:52])
    m.text = sent[:51]
    r = m.report([])
    assert r["perdidos"] == 159 and r["perdidos_tragados"] == 158 and r["insertados"] == 0
    assert r["simulador"]["no_vistos_por_gancho"] == 0 and r["entregados_sin_gancho"] == 0
    # v3-62 through the report: 297 typed, 296 logged, 297 in the window.
    m2 = mod.Medidor(None)
    m2.t_start, m2.t_end, m2.hwnd = 10.0, 20.0, 1
    sent = mod.typed_text(297)
    m2.typed, m2.delivered, m2.text = 297, list(sent[:139] + sent[140:]), sent
    r2 = m2.report([])
    assert (r2["perdidos"], r2["insertados"], r2["entregados_sin_gancho"]) == (0, 0, 1)
    assert r2["simulador"]["no_vistos_por_gancho"] == 1


def test_changed_scripts_stay_lf_without_bom():
    for p in (ESTADO / "exploradores.ps1", ESTADO / "app_cerrada.ps1", ESTADO / "sin_restos.ps1",
              ESTADO / "apps_comun.ps1", ESTADO / "decisiones_comun.ps1", LIVE / "batch.sh",
              LIVE / "evidencia_no_corrio.sh", LIVE / "molestia" / "medidor.py"):
        raw = p.read_bytes()
        assert b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf"), p.name
    for p in (ESTADO / "app_cerrada.ps1", ESTADO / "sin_restos.ps1", ESTADO / "apps_comun.ps1",
              ESTADO / "decisiones_comun.ps1"):
        assert p.read_bytes().isascii(), p.name
