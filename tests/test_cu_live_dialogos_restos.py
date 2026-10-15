"""Dialogs the harness leaves or finds over its own windows (scripts/cu_live/estado), checked with fakes only.

Pasada r9 (2026-10-08): Paint's «Cambiar de tamaño y sesgar» (drawn INSIDE the window, so the window stays enabled)
sat in a batch Paint under t-file-3, t-file-4, t-menu-4 and t-long-3, and the harness's own close of a Windows
Terminal with several tabs left «¿Quieres cerrar todas las pestañas?» over v3-46..v3-53.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ESTADO = ROOT / "scripts" / "cu_live" / "estado"


def _powershell(script: str) -> list[str]:
    exe = shutil.which("powershell")
    if exe is None:
        pytest.skip("PowerShell no disponible")
    done = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def _boton(botones: list[str], modo: str) -> str:
    arr = "@(" + ",".join("'" + b.replace("'", "''") + "'" for b in botones) + ")"
    return f"'[' + (Get-DecisionBotonDialogo {arr} '{modo}') + ']'"


def test_the_harness_presses_only_the_button_that_closes_cancels_or_discards_its_own_test_document():
    src = (ESTADO / "decisiones_comun.ps1").as_posix()
    si = "S" + "\\u00ed"
    got = _powershell("[Console]::OutputEncoding=[Text.Encoding]::UTF8\n" + f". '{src}'\n" + "\n".join([
        # Windows Terminal's confirmation after the harness closed its window: the button that closes, es and en.
        _boton(["Cerrar todo", "Cancelar"], "confirmar"),
        _boton(["Cancel", "Close all"], "confirmar"),
        # A classic yes/no close confirmation.
        f"'[' + (Get-DecisionBotonDialogo @([regex]::Unescape('{si}'),'No') 'confirmar') + ']'",
        # Paint's resize dialog a case left: cancelled, never applied (Aceptar is not a close button).
        _boton(["Aceptar", "Cancelar"], "cancelar"),
        _boton(["Aceptar", "Cancelar"], "confirmar"),
        # A save prompt is data, not a confirmation: nothing is pressed unless the caller proved the document the
        # harness's (sin_guardar), then «No guardar» / «Don't save», never «Guardar».
        _boton(["Guardar", "No guardar", "Cancelar"], "confirmar"),
        _boton(["Guardar", "No guardar", "Cancelar"], "sin_guardar"),
        _boton(["Save", "Don't save", "Cancel"], "sin_guardar"),
        # Counter-cases: no known button, an unknown mode.
        _boton(["Reintentar", "Ayuda"], "confirmar"),
        _boton(["Cerrar todo"], "otro"),
    ]))
    assert got == ["[Cerrar todo]", "[Close all]", "[Sí]", "[Cancelar]", "[]", "[]", "[No guardar]",
                   "[Don't save]", "[]", "[]"]


def test_a_dialog_is_answered_through_uia_on_that_window_with_the_decided_button():
    # Fake UIA elements: Close-DialogosDeVentana presses (Invoke) exactly the decided button of each dialog Get-
    # DialogosDeVentana finds, and leaves a dialog with no such button as it is.
    comun = (ESTADO / "comun.ps1").as_posix()
    got = _powershell(f". '{comun}'\n" + r"""
$global:pulsados=@()
function New-Boton([string]$n){
  $b=[pscustomobject]@{ Current=[pscustomobject]@{ Name=$n } }
  $b | Add-Member ScriptMethod TryGetCurrentPattern { param($pat,[ref]$out)
    $nm=$this.Current.Name; $p=[pscustomobject]@{}; $p | Add-Member ScriptMethod Invoke ([scriptblock]::Create("`$global:pulsados+='$nm'")); $out.Value=$p; $true }
  $b
}
function New-Dialogo([string]$t,[string[]]$botones){
  $d=[pscustomobject]@{ Current=[pscustomobject]@{ Name=$t }; Botones=@($botones | ForEach-Object { New-Boton $_ }) }
  $d | Add-Member ScriptMethod FindAll { param($s,$c) $this.Botones }
  $d
}
function Get-DialogosDeVentana([long]$Hwnd){
  if($Hwnd -eq 1){ New-Dialogo 'Windows Terminal' @('Cerrar todo','Cancelar') }
  if($Hwnd -eq 2){ New-Dialogo 'Cambiar de tamano y sesgar' @('Aceptar','Cancelar') }
  if($Hwnd -eq 3){ New-Dialogo 'Paint' @('Guardar','No guardar','Cancelar') }
}
function Start-Sleep { }
(@(Close-DialogosDeVentana 1 'confirmar') -join ';')
(@(Close-DialogosDeVentana 2 'cancelar') -join ';')
(@(Close-DialogosDeVentana 3 'confirmar') -join ';')
(@(Close-DialogosDeVentana 3 'sin_guardar') -join ';')
($global:pulsados -join ',')
""")
    assert got == ["dialogo:Windows Terminal:Cerrar todo", "dialogo:Cambiar de tamano y sesgar:Cancelar",
                   "dialogo:Paint:sin_boton_confirmar", "dialogo:Paint:No guardar", "Cerrar todo,Cancelar,No guardar"]


def test_every_harness_close_answers_its_own_confirmation_and_never_leaves_a_dialog_up():
    comun = (ESTADO / "comun.ps1").read_text(encoding="utf-8")
    cerrar = comun[comun.index("function Close-WindowExact"):]
    # The close first, then (window still there) its own confirmation through UIA on that same window.
    assert cerrar.index(".Close()") < cerrar.index("Close-DialogosDeVentana $h")
    # The answer is chosen by Get-DecisionModoTrasCerrar: sin_guardar with -SinGuardar, else confirmar, and cancelar
    # only for a window that is not the harness's (-SinConfirmar; test_cu_live_estados_arnes runs the decision).
    assert "Close-DialogosDeVentana $h (Get-DecisionModoTrasCerrar ([bool]$SinGuardar) ([bool]$SinConfirmar))" in cerrar
    dec = (ESTADO / "decisiones_comun.ps1").read_text(encoding="utf-8")
    modo = dec[dec.index("function Get-DecisionModoTrasCerrar"):]
    modo = modo[:modo.index("\n}\n")]
    assert "if($SinGuardar){ return 'sin_guardar' }" in modo and modo.rstrip().endswith("'confirmar'")
    # In-window dialogs (XAML) are found too, not only Win32 owned ones.
    dialogos = comun[comun.index("function Get-DialogosDeVentana"):comun.index("function Close-DialogosDeVentana")]
    assert "IsModal" in dialogos and "ContentDialog" in dialogos and "[EstadoDialogo]::Owned" in dialogos
    apps = (ESTADO / "apps_comun.ps1").read_text(encoding="utf-8")
    propia = apps[apps.index("function Close-AppPropia"):apps.index("function Complete-SalidaDelLote")]
    # A dialog a case left is cancelled before the close; a window possibly shared with the person keeps its save
    # prompt (sin_detener), the harness's own test document is discarded.
    assert propia.index("'cancelar')") < propia.index("try{ Close-WindowExact")
    assert "-SinGuardar:(-not $I.sin_detener)" in propia
    lote = apps[apps.index("function Stop-ProcesoDelLote"):apps.index("function Close-ProcesosDelLote")]
    assert lote.index("Close-DialogosDeVentana") < lote.index("CloseMainWindow")
    restos = (ESTADO / "sin_restos.ps1").read_text(encoding="utf-8")
    restos = restos[restos.index("'cerrar_ventanas' {"):]
    assert restos.index("'cancelar'") < restos.index("-SinGuardar") < restos.index("Stop-Process -Id $p.pid")


def test_paint_states_close_the_batchs_paint_even_with_a_dialog_and_start_a_new_process():
    for name in ("paint_base", "paint_con_lienzo"):
        text = (ESTADO / f"{name}.ps1").read_text(encoding="utf-8")
        assert "Close-AppsPropias 'mspaint'" in text and "Close-ProcesosDelLote 'mspaint'" in text, name
        assert "Get-DialogosDeVentana" in text, name
    lienzo = (ESTADO / "paint_con_lienzo.ps1").read_text(encoding="utf-8")
    # The person's Paint is never touched: the new canvas comes only from a new process.
    assert lienzo.index("Close-ProcesosDelLote") < lienzo.index("'ajena_abierta'") < lienzo.index("Start-Process mspaint")
    assert "lienzo=$lienzo" in lienzo


def _obs_mod():
    import importlib.util

    spec = importlib.util.spec_from_file_location("obs_escena", ROOT / "scripts" / "cu_live" / "obs_escena.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _coleccion(items_pruebas=(), nested=False, solo=False):
    escena = lambda n, items: {"id": "scene", "name": n, "uuid": f"u-{n}", "settings": {"items": list(items)}}  # noqa: E731
    otras = [] if solo else [escena("Escena", [{"name": "Captura de pantalla"}] + ([{"name": "Pruebas", "source_uuid": "u-Pruebas"}] if nested else []))]
    return {"name": "Sin_Título", "current_scene": "Pruebas", "current_program_scene": "Pruebas",
            "scene_order": ([] if solo else [{"name": "Escena"}]) + [{"name": "Pruebas"}],
            "sources": otras + [escena("Pruebas", items_pruebas), {"id": "wasapi_output_capture", "name": "Audio del escritorio"}],
            "groups": []}


def test_obs_test_scene_is_removed_only_when_it_is_exactly_that_empty_unused_scene(tmp_path):
    m = _obs_mod()
    # Pasada r9: v3-51's «Pruebas» was still there from r5. Removed: the scene, its order entry, and the current scene
    # moves to another one; everything else stays.
    r, doc = m.quitar_escena(_coleccion(), "Pruebas")
    assert r == "quitada"
    assert [s["name"] for s in doc["sources"]] == ["Escena", "Audio del escritorio"]
    assert doc["scene_order"] == [{"name": "Escena"}] and doc["current_scene"] == doc["current_program_scene"] == "Escena"
    # Counter-cases: not there; another name (exact match only); a scene with sources (maybe the owner's); used inside
    # another scene; the only scene.
    assert m.quitar_escena(doc, "Pruebas")[0] == "no_estaba"
    assert m.quitar_escena(_coleccion(), "pruebas")[0] == "no_estaba"
    assert m.quitar_escena(_coleccion(items_pruebas=[{"name": "Camara"}]), "Pruebas")[0] == "escena_con_contenido"
    assert m.quitar_escena(_coleccion(nested=True), "Pruebas")[0] == "escena_en_uso"
    assert m.quitar_escena(_coleccion(solo=True), "Pruebas")[0] == "unica_escena"
    # End to end on a copy (never the owner's file): a byte-for-byte backup first, the file read back after.
    f = tmp_path / "Sin_Título.json"
    f.write_text(json.dumps(_coleccion(), ensure_ascii=False), encoding="utf-8")
    original = f.read_bytes()
    exe = shutil.which("py")
    if exe is None:
        pytest.skip("sin py")
    done = subprocess.run([exe, "-3.12", "-I", str(ROOT / "scripts" / "cu_live" / "obs_escena.py"), "--archivo", str(f),
                           "--nombre", "Pruebas", "--respaldo", str(tmp_path / "resp")],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["resultado"] == "quitada" and out["releido"] == "no_estaba"
    assert Path(out["respaldo"]).read_bytes() == original
    assert '"Pruebas"' not in f.read_text(encoding="utf-8")


def test_obs_cases_start_without_the_test_scene_and_keep_the_preference_chain():
    casos = json.loads((ESTADO / "casos.json").read_text(encoding="utf-8"))["casos"]
    assert casos["v3-51"] == ["app_cerrada:OBS Studio", "obs_sin_escena:Pruebas"]
    for c in ("v3-52", "v3-53"):
        assert casos[c].index("obs_sin_escena:Pruebas") < casos[c].index("app_abierta:OBS Studio"), c
    text = (ESTADO / "obs_sin_escena.ps1").read_text(encoding="utf-8")
    assert text.isascii() and "\r\n" not in text
    # The person's OBS is never closed (only the harness's or the batch's copy), and nothing is written with OBS open.
    assert text.index("Close-ProcesosDelLote 'obs64'") < text.index("'obs_abierto'") < text.index("& py -3.12 -I $py")
    assert "Stop-Process" not in text
    # v3-53's pending owner preference (same file) follows the harness's own edit.
    assert "$_.invertido -eq $hashAntes" in text


def test_obstacle_check_repairs_dialogs_only_in_the_batchs_or_harnesss_windows():
    text = (ESTADO / "sin_obstaculos.ps1").read_text(encoding="utf-8")
    bloque = text[text.index("$reparados=@()"):]
    assert "Test-ProcesoDelLote" in bloque and "Get-ProcesosArnes" in text and "Get-Propios" in bloque
    assert bloque.index("continue") < bloque.index("Close-DialogosDeVentana")
    assert "'cancelar'" in bloque and "Close-WindowExact" not in bloque and "Stop-Process" not in bloque
