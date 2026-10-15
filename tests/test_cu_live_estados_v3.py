"""Harness map for the v3 live cases (scripts/cu_live/estado/casos.json), checked without touching the desktop.

Every case of cases/v3_manifiesto.json has a state list; every state named there exists as a script; a state with an
argument only uses a script that takes one; texts that bloc_con_texto writes are listed for bloc_vacio; and each
"sin_estado" reason belongs to a real case. The counter-cases check the checks themselves.
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


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _known_states() -> set[str]:
    skip = re.compile(r"^(base|comun|.*_comun|exploradores|apps_del_caso)$")
    return {p.stem for p in ESTADO.glob("*.ps1") if not skip.match(p.stem)}


def _takes_arg(name: str) -> bool:
    return re.search(r"param\(\[string\]\$Arg", (ESTADO / f"{name}.ps1").read_text(encoding="utf-8")) is not None


def _problems(casos: dict, manifest: dict, known: set[str], textos: list[str]) -> list[str]:
    out = []
    for case in manifest:
        if case not in casos["casos"]:
            out.append(f"sin mapa: {case}")
    for case, states in casos["casos"].items():
        for st in states:
            name, sep, arg = st.partition(":")
            if name not in known:
                out.append(f"{case}: estado desconocido {name}")
                continue
            if sep and not _takes_arg(name):
                out.append(f"{case}: {name} no toma argumento")
            if name == "bloc_con_texto" and arg and arg not in textos:
                out.append(f"{case}: texto no listado {arg!r}")
    for case in casos.get("sin_estado", {}):
        if case not in casos["casos"]:
            out.append(f"sin_estado de un caso inexistente: {case}")
    return out


def test_every_v3_case_maps_to_existing_states():
    casos = _load(ESTADO / "casos.json")
    manifest = _load(LIVE / "cases" / "v3_manifiesto.json")
    textos = _load(ESTADO / "textos_de_prueba.json")["textos"]
    assert _problems(casos, manifest, _known_states(), textos) == []


def test_counter_cases_are_caught():
    known = _known_states()
    textos = _load(ESTADO / "textos_de_prueba.json")["textos"]
    manifest = {"v3-x": {}, "v3-y": {}}
    casos = {
        "casos": {
            "v3-x": ["no_existe", "calc_estandar:arg", "bloc_con_texto:texto del dueno"],
        },
        "sin_estado": {"v3-z": "razon"},
    }
    problems = _problems(casos, manifest, known, textos)
    assert "sin mapa: v3-y" in problems
    assert "v3-x: estado desconocido no_existe" in problems
    assert "v3-x: calc_estandar no toma argumento" in problems
    assert "v3-x: texto no listado 'texto del dueno'" in problems
    assert "sin_estado de un caso inexistente: v3-z" in problems


def _section_problems(casos: dict, known: set[str]) -> list[str]:
    out = []
    for case, req in casos.get("requiere", {}).items():
        if case not in casos["casos"]:
            out.append(f"requiere de un caso inexistente: {case}")
        if req.get("tras") and req["tras"] not in casos["casos"]:
            out.append(f"{case}: tras inexistente {req['tras']}")
        if req.get("comprueba") and req["comprueba"].partition(":")[0] not in known:
            out.append(f"{case}: comprueba desconocido")
    for case, pre in casos.get("precondicion", {}).items():
        if case not in casos["casos"]:
            out.append(f"precondicion de un caso inexistente: {case}")
        for key in ("lee", "invierte", "devuelve"):
            if pre.get(key) and pre[key].partition(":")[0] not in known:
                out.append(f"{case}: {key} desconocido")
        # An owner preference is inverted only when it is given back after the case.
        if pre.get("invierte") and not pre.get("devuelve"):
            out.append(f"{case}: invierte sin devuelve")
        if pre.get("invierte") and not pre.get("lee"):
            out.append(f"{case}: invierte sin lee")
    return out


def test_dependent_cases_and_owner_preferences_name_real_cases_and_reversible_states():
    casos = _load(ESTADO / "casos.json")
    assert _section_problems(casos, _known_states()) == []
    # Counter-cases: an inversion with no way back, an unknown check, a dependency on a case that does not exist.
    bad = {"casos": {"a": [], "b": []},
           "requiere": {"a": {"tras": "zz", "comprueba": "no_existe:x"}},
           "precondicion": {"b": {"lee": "obs_audio_escritorio:leer", "invierte": "obs_audio_escritorio:sin_silenciar"}}}
    assert _section_problems(bad, _known_states()) == [
        "a: tras inexistente zz", "a: comprueba desconocido", "b: invierte sin devuelve"]


def _base(tmp_path: Path, mapa: dict, caso: str, logs: Path | None = None) -> list[dict]:
    path = tmp_path / "casos.json"
    path.write_text(json.dumps(mapa), encoding="utf-8")
    env = f"$env:CU_LIBRO=''; $env:CU_LOGS='{logs or tmp_path}'; "
    lines = _powershell(env + f"& '{(ESTADO / 'base.ps1').as_posix()}' -Caso '{caso}' -Mapa '{path.as_posix()}'")
    return [json.loads(line) for line in lines if line.startswith("{")]


def test_dependent_case_does_not_run_without_what_it_needs(tmp_path):
    # Read-only states only: an unknown state in the list proves whether the list was applied.
    mapa = {"casos": {"p": [], "c": ["no_aplicado_x"]}, "requiere": {"c": {"tras": "p"}}}
    got = _base(tmp_path, mapa, "c")
    assert got[0]["resultado"] == "no_corrio:estado_ausente" and got[0]["falta"] == ["no_corrio_antes:p"]
    assert got[0]["depende_de"] == "p" and len(got) == 1
    # The producer's photo is not proof (taken before its states, it exists even when it ended NO_CORRIO): still out.
    (tmp_path / "v2-p.foto.json").write_text("{}", encoding="utf-8")
    assert _base(tmp_path, mapa, "c")[0]["resultado"] == "no_corrio:estado_ausente"
    # Its marker says the conductor failed, or a judge marked it failed: still out.
    hecho = tmp_path / "v2-p.hecho"
    hecho.write_text('{"caso":"p","conductor_exit":1,"veredicto":null}', encoding="utf-8")
    got = _base(tmp_path, mapa, "c")
    assert got[0]["resultado"] == "no_corrio:estado_ausente" and got[0]["falta"] == ["productor_fallo:p"]
    hecho.write_text('{"caso":"p","conductor_exit":0,"veredicto":"fallo"}', encoding="utf-8")
    assert _base(tmp_path, mapa, "c")[0]["resultado"] == "no_corrio:estado_ausente"
    # Counter-case: its mission ran (marker written after it): the states are applied, flagged while unjudged.
    hecho.write_text('{"caso":"p","conductor_exit":0,"veredicto":null}', encoding="utf-8")
    got = _base(tmp_path, mapa, "c")
    assert "resultado" not in got[0] and got[0]["depende_de"] == "p" and got[0]["productor_sin_verificar"] is True
    assert got[1]["estado"] == "no_aplicado_x" and got[1]["resultado"] == "desconocido"
    hecho.write_text('{"caso":"p","conductor_exit":0,"veredicto":"exito"}', encoding="utf-8")
    assert "productor_sin_verificar" not in _base(tmp_path, mapa, "c")[0]
    # A failing read-only check also stops it.
    mapa["requiere"]["c"]["comprueba"] = "valor_registro:HKCU\\Environment|TEMP|zz-no-esta-zz"
    got = _base(tmp_path, mapa, "c")
    assert got[-1]["resultado"] == "no_corrio:estado_ausente"


def test_owner_preference_that_already_fulfils_the_order_makes_the_ya_estaba_variant(tmp_path):
    lee = "valor_registro:HKCU\\Environment|TEMP|temp"
    mapa = {"casos": {"c": []}, "precondicion": {"c": {"lee": lee, "variante": "ya_estaba"}}}
    got = _base(tmp_path, mapa, "c")
    assert got[0]["cumple_orden"] is True
    assert got[1]["precondicion"] == "cumple" and got[1]["variante"] == "ya_estaba"
    # Counter-case: the preference does not fulfil the order: no variant.
    mapa["precondicion"]["c"]["lee"] = "valor_registro:HKCU\\Environment|TEMP|zz-no-esta-zz"
    got = _base(tmp_path, mapa, "c")
    assert got[1]["precondicion"] == "no_cumple" and "variante" not in got[1]
    # Without a reader the line says so and names the variant to judge by.
    mapa["precondicion"]["c"] = {"variante": "ya_estaba"}
    got = _base(tmp_path, mapa, "c")
    assert got[0]["precondicion"] == "no_legible" and got[0]["variante_si_cumple"] == "ya_estaba"


def test_obs_preference_is_inverted_with_a_copy_and_given_back_byte_for_byte(tmp_path):
    # A fake APPDATA/LOCALAPPDATA: the owner's OBS files are never touched by the test.
    scenes = tmp_path / "roaming" / "obs-studio" / "basic" / "scenes"
    scenes.mkdir(parents=True)
    original = json.dumps({"name": "Sin título", "DesktopAudioDevice1": {"id": "wasapi_output_capture", "muted": True},
                           "AuxAudioDevice1": {"id": "wasapi_input_capture", "muted": True}, "sources": []},
                          ensure_ascii=False, indent=4).encode("utf-8")
    (scenes / "Sin título.json").write_bytes(original)
    script = (ESTADO / "obs_audio_escritorio.ps1").as_posix()
    env = f"$env:APPDATA='{tmp_path / 'roaming'}'; $env:LOCALAPPDATA='{tmp_path / 'local'}'; "
    run = lambda arg: json.loads(_powershell(env + f"& '{script}' -Arg {arg}")[-1])  # noqa: E731
    if run("leer")["resultado"] == "silenciado" and _powershell("@(Get-Process obs64,obs32 -EA SilentlyContinue).Count")[-1] != "0":
        pytest.skip("OBS abierto: el estado no escribe")
    assert run("leer")["cumple_orden"] is True
    inv = run("sin_silenciar")
    assert inv["verificado"] and inv["resultado"] == "corregido"
    doc = json.loads((scenes / "Sin título.json").read_text(encoding="utf-8"))
    # Only the desktop audio is unmuted; the microphone keeps the owner's setting.
    assert doc["DesktopAudioDevice1"]["muted"] is False and doc["AuxAudioDevice1"]["muted"] is True
    assert run("leer")["cumple_orden"] is False
    # Counter-case: a second inversion before giving it back keeps the FIRST copy (the owner's original).
    run("sin_silenciar")
    back = run("devolver")
    assert back["verificado"] and (scenes / "Sin título.json").read_bytes() == original
    assert run("devolver")["resultado"] == "ok"


def test_a_pending_copy_the_owner_outdated_is_never_reused_nor_given_back(tmp_path):
    pref = (ESTADO / "preferencias_comun.ps1").as_posix()
    got = _powershell(f". '{pref}'\n" + "\n".join([
        "Get-DecisionRespaldoPendiente 'H1' 'H1' 'B'",
        "Get-DecisionRespaldoPendiente 'B' '' 'B'",
        # Counter-cases: the file changed after the harness's inversion, or after a copy whose inversion never ran.
        "Get-DecisionRespaldoPendiente 'H2' 'H1' 'B'",
        "Get-DecisionRespaldoPendiente 'X' '' 'B'",
    ]))
    assert got == ["reutilizar", "reutilizar", "respaldo_pendiente_obsoleto", "respaldo_pendiente_obsoleto"]

    scenes = tmp_path / "roaming" / "obs-studio" / "basic" / "scenes"
    scenes.mkdir(parents=True)
    doc = lambda name: json.dumps({"name": name, "DesktopAudioDevice1": {"id": "wasapi_output_capture", "muted": True},  # noqa: E731
                                   "sources": []}, ensure_ascii=False, indent=4).encode("utf-8")
    original, owner_new = doc("Original"), doc("Escena nueva del dueno")
    target = scenes / "Original.json"
    target.write_bytes(original)
    script = (ESTADO / "obs_audio_escritorio.ps1").as_posix()
    env = f"$env:APPDATA='{tmp_path / 'roaming'}'; $env:LOCALAPPDATA='{tmp_path / 'local'}'; "
    run = lambda arg: json.loads(_powershell(env + f"& '{script}' -Arg {arg}")[-1])  # noqa: E731
    if _powershell("@(Get-Process obs64,obs32 -EA SilentlyContinue).Count")[-1] != "0":
        pytest.skip("OBS abierto: el estado no escribe")
    assert run("sin_silenciar")["resultado"] == "corregido"
    inverted = target.read_bytes()
    # The case's -Devolver failed (OBS was open): the copy stays pending. The owner then changes the collection.
    target.write_bytes(owner_new)
    again = run("sin_silenciar")
    assert again["resultado"] == "respaldo_pendiente_obsoleto" and again["verificado"] is False
    assert target.read_bytes() == owner_new
    # The retry of a later batch does not put the stale copy over the owner's change either.
    retry = json.loads(_powershell(env + f"& '{(ESTADO / 'base.ps1').as_posix()}' -DevolverPendientes")[-1])
    assert retry["resultado"] == "respaldo_pendiente_obsoleto" and target.read_bytes() == owner_new
    # Counter-case: with the harness's inversion still in place, the retry gives the owner's original back.
    target.write_bytes(inverted)
    retry = json.loads(_powershell(env + f"& '{(ESTADO / 'base.ps1').as_posix()}' -DevolverPendientes")[-1])
    assert retry["verificado"] is True and target.read_bytes() == original


def _powershell(script: str) -> list[str]:
    exe = shutil.which("powershell")
    if exe is None:
        pytest.skip("PowerShell no disponible")
    done = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                          capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert done.returncode == 0, done.stderr
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def _decisiones(calls: list[str]) -> list[str]:
    src = (ESTADO / "decisiones_comun.ps1").as_posix()
    return _powershell(f". '{src}'\n" + "\n".join(calls))


def _cierre(intentado, ventana_viva, proceso_vivo, nuevo, host, del_pid, propias) -> str:
    arr = lambda xs: "@(" + ",".join(str(x) for x in xs) + ")"
    b = lambda v: "$true" if v else "$false"
    return (f"Get-DecisionCierre @{{ intentado={b(intentado)}; ventana_viva={b(ventana_viva)}; "
            f"proceso_vivo={b(proceso_vivo)}; nuevo={b(nuevo)}; host={b(host)}; "
            f"ventanas_del_pid={arr(del_pid)}; propias={arr(propias)} }}")


def test_close_decision_never_kills_a_process_with_someone_elses_window():
    got = _decisiones([
        # Harness window alive: close it normally first.
        _cierre(False, True, True, True, False, [10], [10]),
        # Harness window gone before closing, process still alive (single-instance app now holding the person's
        # documents): never stopped.
        _cierre(False, False, True, True, False, [20], [10]),
        _cierre(False, False, False, True, False, [], [10]),
        # Closed normally and gone: done, the process is left running (mail still syncing) and the result says so.
        _cierre(True, False, True, True, False, [], [10]),
        _cierre(True, False, False, True, False, [], [10]),
        # Still there after the close (save prompt) and every window of the process is the harness's: stopped.
        _cierre(True, True, True, True, False, [10, 11], [10, 11]),
        # Counter-case: the process also holds a window the harness did not open (the person's document).
        _cierre(True, True, True, True, False, [10, 20], [10]),
        # Counter-cases: a process the harness did not start, or a shared shell host.
        _cierre(True, True, True, False, False, [10], [10]),
        _cierre(True, True, True, True, True, [10], [10]),
    ])
    assert got == ["cerrar", "cerrada_proceso_vivo", "ya_cerrada", "cerrada_proceso_vivo", "cerrada", "detener",
                   "no_cierra:ventanas_ajenas", "no_cierra:ventana_viva", "no_cierra:proceso_compartido"]


def test_focus_goes_back_only_while_the_window_windows_activated_is_in_front():
    got = _decisiones([
        "Get-DecisionFoco 500 500",
        # Counter-cases: the person moved to another window meanwhile; no harness window was in front (or nothing
        # was closed, everything was already closed).
        "Get-DecisionFoco 500 700",
        "Get-DecisionFoco 0 700",
    ])
    assert got == ["devolver", "ajeno", "sin_cambio"]


def test_what_hides_the_case_is_an_always_on_top_window_of_another_program_or_a_modal_dialog_of_its_app():
    # Banco r6: the On-Screen Keyboard a case opened sat over every later case, and Excel/Word showed BAXY only the
    # save prompt an earlier tanda left. Both are named before the case; nothing is closed.
    pantalla = "@{ w=1920; h=1080 }"
    excl = "@('explorer','python')"
    v = lambda proc, top, x, y, w, h: f"@{{ proceso='{proc}'; encima=${'true' if top else 'false'}; x={x}; y={y}; w={w}; h={h} }}"
    d = lambda h, dueno, habilitado: f"@{{ hwnd={h}; dueno={dueno}; dueno_habilitado=${'true' if habilitado else 'false'} }}"
    got = _decisiones([
        f"(@(Get-DecisionEncima @({v('osk', True, 92, 128, 1520, 445)}) {pantalla} {excl}) -join ',')",
        # Counter-cases: not on top; on top but small (a clock widget); the shell's taskbar or the harness's window;
        # on top but off the screen.
        f"'[' + (@(Get-DecisionEncima @({v('Spotify', False, 0, 0, 1920, 1080)}) {pantalla} {excl}) -join ',') + ']'",
        f"'[' + (@(Get-DecisionEncima @({v('widget', True, 1700, 0, 200, 100)}) {pantalla} {excl}) -join ',') + ']'",
        f"'[' + (@(Get-DecisionEncima @({v('explorer', True, 0, 1020, 1920, 60)},{v('python', True, 18, 710, 559, 292)}) {pantalla} {excl}) -join ',') + ']'",
        f"'[' + (@(Get-DecisionEncima @({v('osk', True, 3000, 0, 1520, 445)}) {pantalla} {excl}) -join ',') + ']'",
        # A dialog owned by the disabled main window of the same process: modal.
        f"(@(Get-DecisionDialogos @({d(10, 0, False)},{d(11, 10, False)})) -join ',')",
        # Counter-cases: the main window is enabled (a find bar, a tool window); the owner is not one of its windows.
        f"'[' + (@(Get-DecisionDialogos @({d(10, 0, True)},{d(11, 10, True)})) -join ',') + ']'",
        f"'[' + (@(Get-DecisionDialogos @({d(11, 99, False)})) -join ',') + ']'",
    ])
    assert got == ["osk", "[]", "[]", "[]", "[]", "11", "[]", "[]"]


def test_app_identity_by_executable_path():
    w = r"C:\Windows"
    got = _decisiones([
        # The shortcut target itself (case-insensitive).
        rf"Test-RutaDeApp 'C:\WINDOWS\system32\taskmgr.exe' 'C:\Windows\System32\Taskmgr.exe' '{w}'",
        # A launcher stub next to versioned app folders: same file name under the target's own folder.
        r"Test-RutaDeApp 'C:\U\AppData\Local\Gh\app-3.5\Gh.exe' 'C:\U\AppData\Local\Gh\Gh.exe' "
        rf"'{w}'",
        # Counter-cases: another program of the same folder (one Office folder holds every Office app), another
        # tool of System32, a browser for a mail app, and no path at all.
        r"Test-RutaDeApp 'C:\P\Office16\EXCEL.EXE' 'C:\P\Office16\WINWORD.EXE' " + f"'{w}'",
        rf"Test-RutaDeApp 'C:\Windows\System32\sub\mmc.exe' 'C:\Windows\System32\mmc.exe' '{w}'",
        rf"Test-RutaDeApp 'C:\P\Edge\msedge.exe' 'C:\P\Office16\ONENOTE.EXE' '{w}'",
        rf"Test-RutaDeApp '' 'C:\P\Office16\ONENOTE.EXE' '{w}'",
    ])
    assert got == ["True", "True", "False", "False", "False", "False"]


def test_fixtures_are_valid_by_content_not_by_size(tmp_path):
    raiz = tmp_path / "baxy-prueba-v3"
    script = (ESTADO / "fixtures_prueba_v3.ps1").as_posix()
    run = f"& '{script}' -Raiz '{raiz}'"
    # Counter-case: same size and format, other pixels (a grey filter saved in place), and one zip entry changed.
    spoil = "\n".join([
        "Add-Type -AssemblyName System.Drawing,System.IO.Compression,System.IO.Compression.FileSystem",
        "$b=New-Object Drawing.Bitmap 1920,1080; $g=[Drawing.Graphics]::FromImage($b); $g.Clear([Drawing.Color]::Gray)",
        f"$g.Dispose(); $b.Save('{raiz / 'paisaje.jpg'}',[Drawing.Imaging.ImageFormat]::Jpeg); $b.Dispose()",
        f"$z=[IO.Compression.ZipFile]::Open('{raiz / 'prueba.zip'}','Update'); $z.GetEntry('dos.txt').Delete()",
        "$w=New-Object IO.StreamWriter($z.CreateEntry('dos.txt').Open()); $w.Write('otro'); $w.Dispose(); $z.Dispose()",
    ])
    # One process per run, as base.ps1 runs a state.
    first = json.loads(_powershell(run)[-1])
    second = json.loads(_powershell(run)[-1])
    _powershell(spoil)
    third = json.loads(_powershell(run)[-1])
    assert first["verificado"] and first["resultado"] == "corregido"
    # Deterministic generators: an untouched fixture is left as it is.
    assert second["resultado"] == "ok" and second["hechos"] == []
    assert third["verificado"] and sorted(third["hechos"]) == ["escrito:paisaje.jpg", "escrito:prueba.zip"]


def test_state_scripts_are_ascii_lf_without_bom():
    # PowerShell 5.1 reads a BOM-less script as ANSI: non-ASCII literals would be mangled.
    for path in list(ESTADO.glob("*.ps1")) + [LIVE / "verificar.ps1"]:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), path.name
        assert b"\r\n" not in raw, path.name
        if path.stem in {"app_abierta", "app_cerrada", "apps_comun", "archivo_abierto", "bloc_con_texto",
                         "decisiones_comun", "documento_en_blanco", "explorador_en", "paint_con_lienzo",
                         "fixtures_prueba_v3"} \
                or path.name == "verificar.ps1":
            assert raw.isascii(), path.name


def _cierre_lote(intentado, ventana_viva, proceso_vivo, nuevo, host, del_pid, propias, del_lote, lote) -> str:
    base = _cierre(intentado, ventana_viva, proceso_vivo, nuevo, host, del_pid, propias)
    b = lambda v: "$true" if v else "$false"
    arr = "@(" + ",".join(str(x) for x in lote) + ")"
    return base[:-2] + f"; del_lote={b(del_lote)}; ventanas_lote={arr} }}"


def test_batch_ledger_owns_only_what_has_positive_provenance_and_never_the_persons():
    got = _decisiones([
        # Running when the batch started: the person's, whatever else.
        "Get-DecisionPropiedad @('10:1','20:2') '20:2' $null 'arnes' $true",
        # Born after the photo from the harness (or BAXY): the batch's, even right after the person's input.
        "Get-DecisionPropiedad @('10:1','20:2') '20:3' $null 'arnes' $false",
        "Get-DecisionPropiedad @('10:1') '30:5' 1500 'arnes' $false",
        # Started by a shell host with the record covering the 3 s before and no input: the batch's.
        "Get-DecisionPropiedad @('10:1') '30:5' 4000 'shell:100.5' $true",
        # Counter-cases (fail closed): born 1.5 s after the person's input; a shell launch the record does not
        # cover (the waits before the medidor starts, between cases, a tanda without a record); no provenance at all
        # (an updater of the person's app, a terminal of a parallel agent); a chain that reaches the person's process.
        "Get-DecisionPropiedad @('10:1') '30:5' 1500 'shell:100.5' $true",
        "Get-DecisionPropiedad @('10:1') '30:5' $null 'shell:100.5' $false",
        "Get-DecisionPropiedad @('10:1') '30:5' $null 'desconocida' $true",
        "Get-DecisionPropiedad @('10:1') '30:5' $null 'dueno' $true",
        "Get-DecisionPropiedad @('10:1') '30:5' $null",
        # ms from the person's last input before the process started.
        "Get-MsDesdeInputDueno @(,@(100.0,101.0)) 102.5",
        "Get-MsDesdeInputDueno @(@(100.0,101.0),@(102.0,102.2)) 102.5",
        "$null -eq (Get-MsDesdeInputDueno @(,@(110.0,111.0)) 102.5)",
        "$null -eq (Get-MsDesdeInputDueno @() 102.5)",
        "Get-MsDesdeInputDueno @(,@(100.0,105.0)) 102.5",
    ])
    assert got == ["dueno", "lote", "lote", "lote", "dueno_input", "sin_procedencia", "sin_procedencia",
                   "sin_procedencia", "sin_procedencia", "1500", "300", "True", "True", "0"]


def _tabla(rows) -> str:
    return "@(" + ",".join(
        f"[pscustomobject]@{{pid={p};padre={pp};nombre='{n}';nacio={t}}}" for p, pp, n, t in rows) + ")"


def test_provenance_walks_dead_parents_to_the_harness_baxy_a_shell_or_the_person():
    # pid 500 = harness root (lote.sh), 600 = explorer, 700 = the person's app (running before the photo at 100).
    tabla = _tabla([(500, 1, "bash", 50), (600, 1, "explorer", 10), (700, 600, "Discord", 20),
                    (510, 500, "powershell", 101), (520, 510, "POWERPNT", 102),  # a state's powershell, now dead
                    (800, 1, "Baxy", 103), (810, 800, "baxy-core", 104), (820, 810, "mspaint", 105),
                    (830, 600, "Spotify", 106), (840, 830, "Spotify", 106.5),
                    (850, 700, "Update", 107), (860, 999, "WindowsTerminal", 108)])
    call = lambda p, pp, n, t: (f"Get-ProcedenciaProceso {tabla} ([pscustomobject]@{{pid={p};padre={pp};nombre='{n}';"
                                f"nacio={t}}}) @(500) @(600) 100")
    got = _decisiones([
        call(520, 510, "POWERPNT", 102),       # through the dead powershell of a state to the root
        call(820, 810, "mspaint", 105),        # through BAXY
        call(840, 830, "Spotify", 106.5),      # its parent was started by explorer at 106
        # Counter-cases: the person's updater respawned; a parent the record never saw (a parallel agent).
        call(850, 700, "Update", 107),
        call(860, 999, "WindowsTerminal", 108),
        # A pid reused after the parent's birth is not that parent.
        f"Get-ProcedenciaProceso {_tabla([(510, 500, 'powershell', 200)])} "
        "([pscustomobject]@{pid=520;padre=510;nombre='x';nacio=150}) @(500) @(600) 100",
    ])
    assert got == ["arnes", "arnes", "shell:106", "dueno", "desconocida", "desconocida"]


def test_the_person_counts_as_idle_only_where_the_input_record_covers():
    reg = lambda desde, hasta, iv: (f"([pscustomobject]@{{cubierto_desde={desde};cubierto_hasta={hasta};"
                                    f"intervalos_dueno=@({iv})}})")
    got = _decisiones([
        f"Get-DecisionDuenoQuieto {reg(90, 200, '')} 100 150",
        # Counter-cases: no record at all; a record started after the photo (the old molestia.json from t_start);
        # a record that stopped before now (hooks lost); input inside the span, or in the 3 s before it.
        "Get-DecisionDuenoQuieto $null 100 150",
        f"Get-DecisionDuenoQuieto {reg(120, 200, '')} 100 150",
        f"Get-DecisionDuenoQuieto {reg(90, 140, '')} 100 150",
        f"Get-DecisionDuenoQuieto {reg(90, 200, ',@(130.0,131.0)')} 100 150",
        f"Get-DecisionDuenoQuieto {reg(90, 200, ',@(97.5,98.0)')} 100 150",
        f"Get-DecisionDuenoQuieto {reg(90, 200, ',@(160.0,170.0)')} 100 150",
        f"Get-DecisionCobertura {reg(90, 200, '')} 95 200",
        f"Get-DecisionCobertura {reg(96, 200, '')} 95 200",
    ])
    assert got == ["True", "False", "False", "False", "False", "False", "True", "True", "False"]


def test_batch_process_exits_only_when_every_window_is_proven_the_batchs():
    got = _decisiones([
        # The harness window is gone; the batch process's other windows are proven the batch's (ventanas_lote), or it
        # has none left (the untitled PowerPoint frame is not a titled top window): it exits whole.
        _cierre_lote(False, False, True, True, False, [99], [10], True, [99]),
        _cierre_lote(True, False, True, True, False, [], [10], True, []),
        # Counter-cases: a window nobody recorded (the person's .pptx double-clicked into the batch's PowerPoint)
        # keeps it running, with or without a ledger.
        _cierre_lote(False, False, True, True, False, [99], [10], True, []),
        _cierre_lote(True, False, True, True, False, [10, 20], [10], True, [10]),
        _cierre_lote(True, False, True, True, False, [], [10], False, []),
        # A shared host is never the batch's whole.
        _cierre_lote(True, False, True, True, True, [], [10], True, []),
        # Save prompt left: stopped only when its other windows are the harness's or proven the batch's.
        _cierre_lote(True, True, True, True, False, [10, 30], [10], True, [30]),
        _cierre_lote(True, True, True, True, False, [10, 30], [10], True, []),
        # A close is verified only when the process of the batch is gone (v3-02 reported 'cerrada' alive).
        "Get-DecisionVerificado 'cerrada' $true $true",
        "Get-DecisionVerificado 'cerrada' $true $false",
        "Get-DecisionVerificado 'cerrada_proceso_vivo' $false $true",
        "Get-DecisionVerificado 'no_cierra:ventana_viva' $true $false",
    ])
    assert got == ["salir_sin_ventanas", "salir_sin_ventanas", "cerrada_proceso_vivo", "cerrada_proceso_vivo",
                   "cerrada_proceso_vivo", "cerrada_proceso_vivo", "detener", "no_cierra:ventanas_ajenas",
                   "False", "True", "True", "False"]


def test_office_quit_never_discards_a_document_that_is_not_the_harnesss():
    raiz = r"C:\Users\x\Documents\baxy-prueba-v3"
    doc = lambda n, r: f"@{{nombre='{n}';ruta='{r}'}}"
    got = _decisiones([
        f"Get-DecisionDocumentos @() '{raiz}'",
        f"Get-DecisionDocumentos @({doc('Presentacion1', '')}) '{raiz}'",
        f"Get-DecisionDocumentos @({doc('a.pptx', raiz + chr(92) + 'a.pptx')}) '{raiz}'",
        # A new never-saved document in a copy born in the batch is a case's: BAXY's blank «Libro1» of u5 is recorded
        # by no state, and keeping it left Excel open under 50 cases of banco r30.
        f"Get-DecisionDocumentos @({doc('Libro1', '')}) '{raiz}'",
        # Counter-cases: the person's file opened in that instance; a sibling folder with the same prefix; one bad
        # document among good ones.
        f"Get-DecisionDocumentos @({doc('tesis.pptx', r'C:\Users\x\Documents\tesis.pptx')}) '{raiz}'",
        f"Get-DecisionDocumentos @({doc('b.pptx', raiz + '-otro' + chr(92) + 'b.pptx')}) '{raiz}'",
        f"Get-DecisionDocumentos @({doc('Presentacion1', '')},{doc('t.docx', r'D:\t.docx')}) '{raiz}'",
        # A document COM gives with no name and no path (measured on Word) is unreadable, never quit; a readable
        # document of the person beside it still says documento_ajeno (no title fallback may stop that process).
        f"Get-DecisionDocumentos @({doc('', '')}) '{raiz}'",
        f"Get-DecisionDocumentos @({doc('', '')},{doc('tesis.docx', r'C:\Users\x\tesis.docx')}) '{raiz}'",
        # With the person idle the whole life of that copy, everything in it was opened by a case.
        f"Get-DecisionDocumentos @({doc('tesis.docx', r'C:\Users\x\tesis.docx')}) '{raiz}' $true",
        f"Get-DecisionDocumentos @({doc('', '')}) '{raiz}' $true",
    ])
    assert got == ["quit", "quit", "quit", "quit", "no_cierra:documento_ajeno", "no_cierra:documento_ajeno",
                   "no_cierra:documento_ajeno", "no_cierra:office_ilegible", "no_cierra:documento_ajeno",
                   "quit", "quit"]


def test_new_window_in_a_process_of_the_person_closes_only_by_window_and_only_with_the_person_idle():
    got = _decisiones([
        "Get-DecisionVentanaNueva 'lote' $false $false $false",
        "Get-DecisionVentanaNueva 'dueno' $false $false $false",
        # Counter-cases: the person typed during the case (or the record does not cover it: libro_lote.ps1 passes
        # dueno_activo = not fully covered and idle); a process born with their input; one without provenance; a
        # shell host; a protected app (VS Code, Opera).
        "Get-DecisionVentanaNueva 'dueno' $true $false $false",
        "Get-DecisionVentanaNueva 'dueno_input' $false $false $false",
        "Get-DecisionVentanaNueva 'sin_procedencia' $false $false $false",
        "Get-DecisionVentanaNueva 'dueno' $false $true $false",
        "Get-DecisionVentanaNueva 'lote' $false $false $true",
    ])
    assert got == ["con_su_proceso", "cerrar_ventana", "no_tocar", "no_tocar", "no_tocar", "no_tocar", "no_tocar"]


def test_ledger_script_is_ascii_lf_and_never_touches_protected_or_harness_processes():
    raw = (LIVE / "libro_lote.ps1").read_bytes()
    assert raw.isascii() and b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("ascii")
    # Closes by exact PID through Stop-ProcesoDelLote only; never by name.
    assert "Stop-Process -Name" not in text and "taskkill" not in text.lower()
    for name in ("'Baxy'", "'powershell'", "'python'", "'bash'", "'WindowsTerminal'", "'Claude'"):
        assert name in text
    assert "$global:AppsProhibidos -contains $p.nombre" in text
    # The person's browser is only reported; its titles are kept as hashes.
    assert "no se cierra" in text and "Get-Huella" in text
    # Fail closed: the person's idleness comes only from the owner-input record, never from a missing molestia.json;
    # the final sweep never closes windows or moves tab files.
    assert "-Molestia" not in text and "Get-DecisionDuenoQuieto" in text
    assert "$quietoCaso=[bool](-not $barrido" in text and "if(-not $barrido){" in text and "if($quietoCaso -and" in text


def test_every_cerrar_runs_with_an_owner_input_record_started_before_its_photo():
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    lote = (LIVE / "lote.sh").read_text(encoding="utf-8")
    tanda = (ROOT / "scripts" / "uso_real" / "tanda.ps1").read_text(encoding="utf-8")
    assert "-Molestia" not in batch
    for text, foto in ((batch, 'libro_lote.ps1" -Foto'), (lote, 'libro_lote.ps1" -Foto'), (tanda, "-Foto -Libro")):
        assert "registro" in text.lower()
        start = text.index("registro_iniciar" if "registro_iniciar" in text else "registro_dueno.py")
        assert start < text.index(foto)
    # Visible windows leave out cloaked and zero-size ones (background processes are not open apps).
    apps = (ESTADO / "apps_comun.ps1").read_text(encoding="utf-8")
    assert "[EstadoDwm]::Cloaked($h)" in apps and "($r.Right-$r.Left) -gt 0" in apps


def _orden():
    import importlib.util
    spec = importlib.util.spec_from_file_location("orden_lote", LIVE / "orden_lote.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_batch_order_groups_apps_closes_first_puts_producers_first_and_gates_last():
    manifest = {"a1": {"app": "Paint"}, "a2": {"app": "Paint"}, "o1": {"app": "Outlook (classic)"},
                "e1": {"app": "Microsoft Edge"}, "n1": {"app": "OneNote"}, "n2": {"app": "OneNote"},
                "b1": {"app": "Bloc de notas"}, "x1": {"app": "Calculadora + Bloc de notas"}}
    casos = {"casos": {"a1": ["paint_con_lienzo:"], "a2": ["app_cerrada:mspaint"], "n1": ["app_abierta:OneNote"],
                       "n2": ["app_cerrada:OneNote"], "b1": [], "x1": [], "o1": [], "e1": []},
             "requiere": {"n2": {"tras": "b1"}},
             "orden": {"al_final": ["Outlook (classic)"], "aparte": ["Microsoft Edge"]}}
    got = _orden().ordenar(["e1", "o1", "a1", "s01", "n1", "b1", "a2", "n2", "x1"], casos, manifest)
    # s01 is not a v3 case: first. Paint together with its closed case first; OneNote closed first; the gate app and
    # the browser last; n2 needs b1, so it moves after it.
    assert got == ["s01", "a2", "a1", "n1", "b1", "n2", "x1", "o1", "e1"]
    # Counter-case: the order given is kept when nothing applies.
    assert _orden().ordenar(["b1", "x1"], {"casos": {}}, manifest) == ["b1", "x1"]


def test_real_batch_order_keeps_every_case_and_runs_dependents_after_their_producer():
    casos = _load(ESTADO / "casos.json")
    manifest = _load(LIVE / "cases" / "v3_manifiesto.json")
    ids = list(manifest)
    got = _orden().ordenar(ids, casos, manifest)
    assert sorted(got) == sorted(ids)
    for case, req in casos["requiere"].items():
        assert got.index(req["tras"]) < got.index(case), case
    assert got[-1] in {"v3-57", "v3-58", "v3-59"}


# --- Annoyance meter (molestia/medidor.py) without the desktop: cursor, key and foreground classification.

def _medidor_mod():
    import sys
    if sys.platform != "win32":
        pytest.skip("the meter declares user32 functions")
    sys.path.insert(0, str(LIVE / "molestia"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("medidor_r3", LIVE / "molestia" / "medidor.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Pantalla:
    """Front and cursor the meter reads, set by the test."""

    def __init__(self, cursor=(100, 100), frente=True):
        self.cursor, self.frente = cursor, frente


def _medidor(pantalla: _Pantalla):
    mod = _medidor_mod()
    m = mod.Medidor(None)
    m._front_ours = lambda: pantalla.frente
    m._cursor_now = lambda: pantalla.cursor
    m.t_start, m.sim_last, m.sim_pos = 10.0, 9.0, (100, 100)
    m.hwnd = 1
    return mod, m


def test_meter_tags_the_unmarked_uia_key_as_uia_and_still_counts_it_as_baxys():
    mod = _medidor_mod()
    assert mod.key_source(mod.w32.BAXY_MARK, 0x41) == "baxy"
    assert mod.key_source(0, 0xB9) == "uia"
    # Counter-cases: another unmarked key, 0xB9 with some other program's mark, and BAXY's own mark on 0xB9.
    assert mod.key_source(0, 0x41) == "ajeno"
    assert mod.key_source(0x1234, 0xB9) == "ajeno"
    assert mod.key_source(mod.w32.BAXY_MARK, 0xB9) == "baxy"
    pantalla = _Pantalla()
    _, m = _medidor(pantalla)
    m.t_end = 20.0
    m._act(11.0, "tecla_en_ventana_usuario", "uia", vk=0xB9, car=None)
    m._act(11.5, "tecla_en_ventana_usuario", "ajeno", vk=0x41, car="a")
    r = m.report([])
    assert r["teclas_baxy_en_ventana_usuario"] == 2 and r["teclas_baxy_en_ventana_usuario_uia"] == 1
    assert r["teclas_uia"] == 1 and "uia=1" in r["resumen"]


def test_meter_takes_the_simulators_own_move_as_its_own_even_when_the_hook_comes_late():
    pantalla = _Pantalla(cursor=(100, 100))
    _, m = _medidor(pantalla)
    # Under load the hook of the simulator's move has not run yet when the poller sees the cursor at its point: the
    # point noted before SendInput explains it.
    m.sim_sent.append((10.50, (130, 104)))
    assert m._cursor_jump(10.56, 10.55, (100, 100), (131, 104)) == "simulador"
    # Counter-case: a noted point explains one jump only; coming back to it later is someone else's jump.
    assert m._cursor_jump(10.70, 10.69, (400, 400), (130, 104)) == "acto"
    # Counter-case: without a noted or hooked point the jump is foreign.
    assert m._cursor_jump(10.90, 10.89, (130, 104), (600, 300)) == "acto"
    assert [a["tipo"] for a in m.acts] == ["cursor_saltado", "cursor_saltado"]
    # Counter-case: a noted point older than its time to live explains nothing.
    m.sim_sent.append((11.00, (140, 104)))
    assert m._cursor_jump(13.00, 12.99, (600, 300), (140, 104)) == "acto"


def test_meter_counts_the_cursor_going_back_inside_a_burst_as_restoration_not_movement():
    pantalla = _Pantalla(cursor=(100, 100))
    _, m = _medidor(pantalla)
    m.t_end = 20.0
    assert m._cursor_jump(11.00, 10.99, (100, 100), (500, 500)) == "acto"
    assert m._cursor_jump(11.20, 11.19, (500, 500), (100, 100)) == "vuelta"
    m._close_burst(11.5, "simulador_vuelve")
    r = m.report([])
    assert r["movimientos_cursor"] == 1 and r["cursor_vueltas_restauradas"] == 1
    assert r["rafagas"] == 1 and r["rafagas_restauradas"] == 1 and r["rafagas_restauradas_tarde"] == 0
    assert m.bursts[0]["cursor_vuelto"] == 11.2
    # Counter-case: a jump to the user's point with no foreign jump before it is not a restoration (nothing left it).
    _, m2 = _medidor(_Pantalla())
    m2.sim_pos = (300, 300)
    assert m2._cursor_jump(11.0, 10.99, (100, 100), (300, 300)) == "acto"


def test_meter_marks_a_burst_given_back_after_the_simulator_resumed_as_restored_late_with_its_delay():
    pantalla = _Pantalla(cursor=(100, 100), frente=False)
    _, m = _medidor(pantalla)
    m.t_end = 20.0
    m._act(11.00, "robo_foco", "ajeno", titulo="x", proceso="x.exe")
    pantalla.cursor = (500, 500)
    assert m._cursor_jump(11.01, 11.00, (100, 100), (500, 500)) == "acto"
    m._close_burst(11.40, "simulador_vuelve")
    assert m.bursts[0]["restaurada"] is False and m.bursts[0]["restaurada_tarde"] is False
    # The front comes back first: not yet restored (the cursor is still away).
    pantalla.frente = True
    m._check_late(11.80)
    assert m.bursts[0]["restaurada_tarde"] is False
    # Then the cursor: restored late, 600 ms after the evaluation; the way back is not a movement.
    pantalla.cursor = (100, 100)
    assert m._cursor_jump(12.00, 11.99, (500, 500), (100, 100)) == "vuelta"
    r = m.report([])
    assert r["rafagas_restauradas"] == 0 and r["rafagas_restauradas_tarde"] == 1
    assert r["retrasos_restauracion_tarde_ms"] == [600] and r["movimientos_cursor"] == 1
    assert "tarde=1" in r["resumen"]


def test_meter_never_calls_a_burst_restored_late_when_the_user_took_the_cursor_back_himself():
    pantalla = _Pantalla(cursor=(500, 500), frente=True)
    _, m = _medidor(pantalla)
    m.t_end = 20.0
    assert m._cursor_jump(11.00, 10.99, (100, 100), (500, 500)) == "acto"
    m._close_burst(11.40, "simulador_vuelve")
    # The simulator moves on (its hook: the old point is checked first, then it is the user's new point).
    m._check_late(11.50)
    m.sim_pos = (120, 100)
    m._sim_moved()
    # BAXY puts the cursor back where the user had it before: an old point, a movement.
    assert m._cursor_jump(11.70, 11.69, (120, 100), (100, 100)) == "acto"
    r = m.report([])
    assert r["rafagas_restauradas_tarde"] == 0 and r["movimientos_cursor"] == 2


def test_meter_never_credits_baxy_with_a_late_restoration_the_owner_made_by_hand():
    pantalla = _Pantalla(cursor=(500, 500), frente=True)
    _, m = _medidor(pantalla)
    m.t_end = 30.0
    assert m._cursor_jump(11.00, 10.99, (100, 100), (500, 500)) == "acto"
    m._close_burst(11.40, "simulador_vuelve")
    assert m.pending_late
    # The owner moves the mouse back to where the user's cursor was (a real, hooked move): no "vuelta", no late
    # restoration, and the burst stops waiting.
    m._owner(12.0)
    m.points.append((12.0, (100, 100)))
    m.owner_points.append((12.0, (100, 100)))
    pantalla.cursor = (100, 100)
    assert m._cursor_jump(12.02, 12.01, (500, 500), (100, 100)) == "explicado"
    r = m.report([])
    assert r["rafagas_restauradas_tarde"] == 0 and r["cursor_vueltas_restauradas"] == 0
    assert r["rafagas_recuperadas_por_dueno"] == 1 and not m.pending_late and not m.displaced
    # The owner clicks the user's window back while the cursor is already home: the front coming back is not BAXY's.
    pantalla2 = _Pantalla(cursor=(100, 100), frente=False)
    _, m2 = _medidor(pantalla2)
    m2.t_end = 30.0
    m2._act(11.00, "robo_foco", "ajeno", titulo="x", proceso="x.exe")
    m2._close_burst(11.40, "simulador_vuelve")
    m2._owner(14.0)
    pantalla2.frente = True
    m2._check_late(14.1)
    assert m2.bursts[0]["restaurada_tarde"] is False and m2.bursts[0]["recuperada_por_dueno"] is True
    # Counter-case: an owner input long before the burst does not void a restoration BAXY made by itself.
    pantalla3 = _Pantalla(cursor=(100, 100), frente=False)
    _, m3 = _medidor(pantalla3)
    m3.t_end = 30.0
    m3._owner(5.0)
    m3._act(11.00, "robo_foco", "ajeno", titulo="x", proceso="x.exe")
    m3._close_burst(11.40, "simulador_vuelve")
    pantalla3.frente = True
    m3._check_late(12.0)
    assert m3.bursts[0]["restaurada_tarde"] is True and m3.bursts[0]["retraso_ms"] == 600


def test_meter_counts_foreground_notices_without_the_front_apart_from_thefts():
    mod = _medidor_mod()
    # Windows announces a window that never took the front (SetForegroundWindow denied, measured ret=False).
    assert mod.transient_kind(7, 50.0, {}) == "sin_frente"
    assert mod.transient_kind(7, 50.0, {7: 10.0}) == "sin_frente"
    # Counter-case: a queued notice of a window that did hold the front a moment ago.
    assert mod.transient_kind(7, 50.0, {7: 49.7}) == "aviso_tardio"
    pantalla = _Pantalla()
    _, m = _medidor(pantalla)
    m.t_end = 20.0
    m.fg_log = [{"t": 11.0, "transitorio": True, "clase": "sin_frente"},
                {"t": 12.0, "transitorio": True, "clase": "aviso_tardio"}]
    r = m.report([])
    assert r["primer_plano_transitorios"] == 2 and r["primer_plano_sin_frente"] == 1
    assert r["primer_plano_aviso_tardio"] == 1 and r["robos_foco"] == 0 and "transitorios=2" in r["resumen"]


# --- Batch repeat (repetir.py): a case the infrastructure could not run is repeated, a product silence is not.

def _repetir():
    import importlib.util
    spec = importlib.util.spec_from_file_location("repetir", LIVE / "repetir.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.motivo_repeticion


def _ev(*objs) -> list[str]:
    return [json.dumps(o) for o in objs]


def test_batch_repeats_a_case_whose_decider_was_unavailable_like_one_whose_runtime_was_not_ready():
    motivo = _repetir()
    silent = {"type": "terminal", "kind": "filtered", "final": None, "diagnostic": "no_response;recovery:no_response"}
    # s02 r2: 171 s of decision_unavailable, the turn ended with no final.
    assert motivo(_ev(silent, {"type": "posterior", "mindReplyRejection": "decision_unavailable"})) \
        == "decision_unavailable"
    assert motivo(_ev({"type": "terminal", "kind": "blocked_environment", "diagnostic": "runtime_not_ready"})) \
        == "runtime_not_ready"
    # Counter-case: a turn with no final and a decider that answered is the product's silence: it counts.
    assert motivo(_ev(silent, {"type": "posterior", "mindReplyRejection": None})) is None
    # Counter-case: the decider was unavailable but the turn still published a final (the conversation fallback).
    answered = {"type": "terminal", "kind": "reply", "final": "Listo.", "diagnostic": None}
    assert motivo(_ev(answered, {"type": "posterior", "mindReplyRejection": "decision_unavailable"})) is None
    # Counter-case: an ordinary run, and garbage lines, repeat nothing.
    assert motivo(_ev(answered) + ["", "not json"]) is None
    # Two turns (each terminal followed by its own posterior, as in v2-c7): turn 1 lost the decider but answered
    # through the fallback, turn 2 is a product silence with the decider answering. Per turn, nothing to repeat.
    adm = {"type": "admission", "command": "turn", "status": 200}
    unav = {"type": "posterior", "mindReplyRejection": "decision_unavailable"}
    ok = {"type": "posterior", "mindReplyRejection": None}
    assert motivo(_ev(answered, unav, silent, ok)) is None
    assert motivo(_ev(adm, answered, unav, adm, silent, ok, ok)) is None
    # ... while the same two turns with the decider lost in the silent one are repeated.
    assert motivo(_ev(adm, answered, ok, adm, silent, unav, unav)) == "decision_unavailable"
    assert motivo(_ev(answered, ok, silent, unav)) == "decision_unavailable"


def test_batch_repeat_loop_asks_repetir_after_every_run_and_keeps_the_repeated_evidence():
    text = (LIVE / "batch.sh").read_text(encoding="utf-8")
    loop = text[text.index("for intento in 1 2 3"):text.index("done", text.index("for intento in 1 2 3"))]
    assert 'repetir.py" "$EVB/$tag/events.jsonl") || break' in loop
    assert "events.repetido-$intento.jsonl" in loop and "conductor exit=2 " in loop


def test_discord_cases_start_from_a_fixed_dm_reached_only_by_uia_navigation():
    casos = _load(ESTADO / "casos.json")["casos"]
    # In the base s11 passed with 0 steps (Discord was already on Cotele); in r2 it started on @Ron92: the state
    # fixes the start so "go to the Cotele channel" always has to navigate.
    for case in ("s11", "s13", "c7"):
        assert casos[case][0] == "discord_md:Ron92", case
    assert "discord_md" in _known_states() and _takes_arg("discord_md")
    raw = (ESTADO / "discord_md.ps1").read_bytes()
    assert raw.isascii() and b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    src = raw.decode("ascii")
    # Navigation only: no keys, no text, no clicks, no protocol launch, never Discord started.
    for banned in ("keybd_event", "SendKeys", "SendInput", "SetValue", "SetCursorPos", "mouse_event", "Start-Process",
                   "discord://"):
        assert banned not in src, banned
    # Never a voice channel (invoking it joins the call), and the foreground goes back afterwards.
    assert "-notmatch 'voz|voice'" in src and "Restore-Foreground $fg @('Discord')" in src
    # Counter-case: a case that is not about Discord gets no Discord state.
    assert not any(s.startswith("discord_md") for s in casos["s12"])


def test_discord_and_spotify_cases_start_without_what_earlier_runs_left_in_their_searches():
    # Banco c24b/c25: s11, c7 and s13 started with "cotele" in Discord's message search box and its place selector
    # open; y8, u1, v8, u9 and x7 with text in Spotify's search box and its library unfolded (v2 closed Spotify after
    # every case, so it opened clean). Every case whose order is given inside one of those apps gets the state.
    casos = _load(ESTADO / "casos.json")["casos"]
    seen = {"discord": 0, "spotify": 0}
    for path in (LIVE / "cases").glob("*.turns"):
        first = path.read_text(encoding="utf-8").splitlines()[0].lower()
        if re.search(r"\b(en|in|abrí|open) discord\b", first):
            seen["discord"] += 1
            assert "discord_busqueda_vacia" in casos[path.stem], path.stem
        if re.search(r"\b(en|in|abrí|open) spotify\b", first):
            seen["spotify"] += 1
            assert casos[path.stem] == ["spotify_inicio"], path.stem
    assert seen["discord"] >= 5 and seen["spotify"] >= 5
    # The chat is fixed first: the message search box belongs to the chat shown.
    for case in ("s11", "s13", "c7"):
        assert casos[case][:2] == ["discord_md:Ron92", "discord_busqueda_vacia"], case
    # Counter-cases: a case that only says the word (v1 searches the Store for "Spotify") or uses another app.
    assert "spotify_inicio" not in casos.get("v1", []) and "discord_busqueda_vacia" not in casos["s12"]

    src = {}
    for name in ("discord_busqueda_vacia", "spotify_inicio"):
        assert name in _known_states() and not _takes_arg(name)
        raw = (ESTADO / f"{name}.ps1").read_bytes()
        assert raw.isascii() and b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf"), name
        src[name] = raw.decode("ascii")
        # No text, no mouse, no launch, no process stopped; the only key is the guarded Escape of comun.ps1.
        for banned in ("keybd_event", "SendKeys", "SendInput", "SetCursorPos", "mouse_event", "Start-Process",
                       "Stop-Process", ".Kill(", "discord://", "spotify:"):
            assert banned not in src[name], (name, banned)
        assert "Restore-Foreground $fg @(" in src[name], name
    discord, spotify = src["discord_busqueda_vacia"], src["spotify_inicio"]
    # Discord: the only value ever set is the empty one, on the search ComboBox; the composer (an Edit) is never
    # looked up; an Escape only after reading the selector or the drop-down open (the selector, at most three times,
    # each round reading it open again).
    assert re.findall(r"SetValue\(([^)]*)\)", discord) == ["''"]
    assert "ControlType]::Edit" not in discord and "ControlType]::Hyperlink" not in discord
    guarded = r"if\((\$s\.[^)]*)\)\{\s*\$pasos\+=\"\w+:\$\(Send-EscapeEnFrente \$h\)\""
    assert re.findall(guarded, discord) == ["$s.desplegada"]
    looped = r"for\(\$r=0;\$r -lt 3 -and (\$s\.selector\.Count -gt 0);\$r\+\+\)\{\s*\$pasos\+=\"selector:\$\(Send-EscapeEnFrente \$h\)\""
    assert re.findall(looped, discord) == ["$s.selector.Count -gt 0"]
    assert discord.count("Send-EscapeEnFrente $h") == 2
    # Spotify: the only value ever set is the empty one, on the top search box; only the box's own "empty" button,
    # the home button and the one that folds the library are invoked.
    assert re.findall(r"SetValue\(([^)]*)\)", spotify) == ["''"]
    assert re.findall(r"Invoke-Element (\$s\.\w+)\)", spotify) == ["$s.borrar", "$s.inicio", "$s.plegar"]
    assert re.findall(guarded, spotify) == ["$s.abiertos.Count -gt 0"]
    assert spotify.count("Send-EscapeEnFrente $h") == 1
    # The Escape itself: one press, and never unless that exact window is in front.
    comun = (ESTADO / "comun.ps1").read_text(encoding="utf-8")
    body = comun[comun.index("function Send-EscapeEnFrente"):comun.index("function Find-TopWindowByName")]
    assert body.index("GetForegroundWindow() -ne $Hwnd){ return 'sin_frente' }") < body.index("keybd_event(0x1B")
    assert body.count("keybd_event(0x1B,0,0,") == 1


def test_frames_a_case_leaves_are_listed_and_closed_by_exact_hwnd_never_by_one_main_title():
    # ApplicationFrameHost is one process for every packaged app frame: its MainWindowTitle names only one, so a
    # Settings window left next to a Calculator was never seen as new (r4a: Settings over Steam in g1).
    text = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert "$_.MainWindowTitle" not in text and 'close_window.ps1" -Title "$t"' not in text
    assert 'marcos.ps1" -CerrarNuevos -Antes "$FRAMES"' in text and 'marcos.ps1" -Reintentar' in text
    # The retry of a frame an earlier case could not close runs before the case's states.
    assert text.index('marcos.ps1" -Reintentar') < text.index('estado/base.ps1" -Caso "$id"')
    raw = (LIVE / "marcos.ps1").read_bytes()
    assert raw.isascii() and b"\r\n" not in raw and not raw.startswith(b"\xef\xbb\xbf")
    src = raw.decode("ascii")
    # Closed through the shared exact-window close (refuses VS Code, Opera and short titles), never by a title match.
    assert "Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle" in src and "-like" not in src
    # A pending HWND is closed only while it is still a frame (a recycled HWND of another program is never closed).
    assert "$vivas -contains $_" in src
    listed = _powershell(f"& '{(LIVE / 'marcos.ps1').as_posix()}' -Listar")
    assert all(re.fullmatch(r"\d+", h) for line in listed for h in line.split())


def test_a_new_frame_closes_only_under_the_ledgers_rule_for_a_window_in_a_process_of_the_person():
    # ApplicationFrameHost is the person's process: a Calculator or Settings the person opens during a case is theirs.
    # The frame closer follows the ledger (Get-DecisionVentanaNueva), with the owner-input record over the whole case
    # (from the case photo, -Libro) and fail closed: without the photo or the record nothing is closed.
    src = (LIVE / "marcos.ps1").read_text(encoding="ascii")
    assert "apps_comun.ps1" in src and "Get-DecisionDuenoQuieto (Get-RegistroDueno $hasta)" in src
    assert "Get-DecisionVentanaNueva 'dueno' (-not $quieto) $false $false" in src
    assert "$quieto=$false" in src and "Close-Marcos $aCerrar" in src and "sin_tocar=$sinTocar" in src
    # Only what was closed and survived goes to the retry file, never a frame left alone.
    cerrar = src[src.index("if($CerrarNuevos){"):src.index("if($Reintentar){")]
    pend = [ln for ln in cerrar.splitlines() if "Write-Pendientes" in ln]
    assert pend == ["    Write-Pendientes @(@($ya)+@($r.sobreviven) | Select-Object -Unique)"]
    batch = (LIVE / "batch.sh").read_text(encoding="utf-8")
    assert 'marcos.ps1" -CerrarNuevos -Antes "$FRAMES" -Libro "$FOTO"' in batch
    assert batch.count('marcos.ps1" -CerrarNuevos') == 1
    # The rule itself: closed only with the person idle; counter-case: the person active, it is left alone.
    assert _decisiones(["Get-DecisionVentanaNueva 'dueno' $false $false $false",
                        "Get-DecisionVentanaNueva 'dueno' $true $false $false"]) == ["cerrar_ventana", "no_tocar"]


def test_a_case_repeated_after_its_turns_acted_goes_back_to_its_base_state_or_does_not_count():
    # s13: turn 1 goes to the channel, turn 3 loses the decider. Repeating it on that desktop would pass turn 1 with
    # 0 steps (the false success discord_md is there to prevent): before a repeated run, what the attempt opened is
    # closed and the base states are applied again, with the evidence taken before the case retaken.
    text = (LIVE / "batch.sh").read_text(encoding="utf-8")
    prep = text[text.index("preparar_caso(){"):text.index("\n}\n", text.index("preparar_caso(){"))]
    for step in ('marcos.ps1" -Reintentar', 'estado/base.ps1" -Caso "$id"', 'apps_del_caso.ps1" -Listar',
                 'verificar_fase antes', 'exploradores.ps1" -Listar', "FRAMES=$(frames)"):
        assert step in prep, step
    clean = text[text.index("limpiar_caso(){"):text.index("\n}\n", text.index("limpiar_caso(){"))]
    for step in ('libro_lote.ps1" -Cerrar -Libro "$FOTO"', 'marcos.ps1" -CerrarNuevos', 'exploradores.ps1" -CerrarNuevos',
                 'apps_del_caso.ps1" -Caso "$id" -Antes "$APPS"', 'base.ps1" -Caso "$id" -Devolver', "LIMPIO=0"):
        assert step in clean, step
    loop = text[text.index("for intento in 1 2 3"):text.index("\n  done\n", text.index("for intento in 1 2 3"))]
    repeat = loop[loop.index("MOTIVO=$(py"):]
    # The repeated run (MOTIVO set) cleans up, then prepares again: in this order, inside the loop.
    assert repeat.index("limpiar_caso") < repeat.index("preparar_caso")
    # preparar_caso now returns 1 (estado ausente) or 2 (base state not verified after one repair): both stop it.
    assert 'if [ "$LIMPIO" != 1 ]; then NOCORRIO=' in repeat and "preparar_caso; RC=$?" in repeat
    assert 'if [ "$RC" = 1 ]; then NOCORRIO=' in repeat
    assert 'if [ "$RC" = 2 ] || [ -n "$NOVERIF" ]; then NOCORRIO="estado base sin verificar al repetirlo' in repeat
    # Counter-case: another BAXY open (no turn ran) waits and repeats without touching the desktop.
    abort = loop[loop.index("if grep -aqE 'ABORT"):loop.index("MOTIVO=$(py")]
    assert "limpiar_caso" not in abort and "preparar_caso" not in abort and "continue" in abort
    # A case that could not go back to its base state writes no marker, so its dependents do not run on it.
    after = text[text.index('if [ -n "$NOCORRIO" ]; then'):]
    assert after.index("NO_CORRIO: $id $NOCORRIO") < after.index("else") < after.index("$tag.hecho")
    assert after.index("limpiar_caso") > after.index("$tag.hecho")


def test_a_case_starts_only_from_a_verified_base_state_after_leftovers_of_earlier_runs_are_closed():
    # Round 7 (2026-10-08): 23 cases ran on what earlier batches and tandas left (a Reloj in front, a OneNote in its
    # File view, a Word with its save prompt) while their state lines said verificado=false; the batch ran them anyway.
    text = (LIVE / "batch.sh").read_text(encoding="utf-8")
    prep = text[text.index("preparar_caso(){"):text.index("\n}\n", text.index("preparar_caso(){"))]
    # Leftovers first, then the case's states, then the obstacles; repaired once, otherwise return 2.
    assert prep.index("-Estados sin_restos") < prep.index('-Caso "$id"') < prep.index("-Estados sin_obstaculos")
    assert "for rep in 1 2" in prep and "return 2" in prep and "CU_ESTADO_ESTRICTO" in prep
    main = text[text.index('for id in "$@"; do'):]
    noc = main[main.index('if [ "$RC" = 2 ]; then'):main.index("\n  fi\n", main.index('if [ "$RC" = 2 ]; then'))]
    # Not run, does not count against BAXY, what its states opened is closed, and no marker (.hecho) is written.
    assert "NO_CORRIO: $id estado base sin verificar" in noc and "limpiar_caso" in noc and "continue" in noc
    assert "$tag.hecho" not in noc


def _resto(protegida=False, dueno=False, office=False, ventanas=(), libro=(), ajenas=0) -> str:
    v = ",".join(str(x) for x in ventanas) or ""
    lb = ",".join(str(x) for x in libro) or ""
    return (f"Get-DecisionResto @{{ protegida=${str(protegida).lower()}; dueno=${str(dueno).lower()}; "
            f"office=${str(office).lower()}; ventanas=@({v}); libro=@({lb}); ajenas={ajenas} }}")


def test_a_leftover_of_an_earlier_run_closes_only_by_its_recorded_windows_and_never_the_persons():
    got = _decisiones([
        _resto(ventanas=(11, 12), libro=(11, 12, 13)),   # every window it shows was recorded for it: closed
        _resto(ventanas=(11, 99), libro=(11,)),           # counter-case: a window nobody recorded (maybe the person's)
        _resto(ventanas=(), libro=(11,)),                 # nothing on screen: left running, never stopped
        _resto(office=True, ventanas=(11,), libro=()),    # Office: the COM document check decides
        _resto(dueno=True, ventanas=(11,), libro=(11,)),  # counter-case: the batch ledger gave it to the person
        _resto(protegida=True, ventanas=(11,), libro=(11,)),  # counter-case: VS Code, Opera, a terminal, BAXY...
        # Counter-case: a dialog of it owned by the person's window (its owner root is another process's window,
        # recorded with it): closing that root would close the person's window.
        _resto(ventanas=(11,), libro=(11,), ajenas=1),
    ])
    assert got == ["cerrar_ventanas", "no_cierra:ventanas_nuevas", "sin_ventanas", "office", "no_tocar:del_dueno",
                   "no_tocar:protegida", "no_cierra:ventana_de_otro_proceso"]
    restos = (ESTADO / "sin_restos.ps1").read_text(encoding="utf-8")
    assert "GetWindowThreadProcessId" in restos and "ajenas=$ajenas.Count" in restos


def test_the_harness_book_outlives_the_batch_and_only_holds_what_was_proven_the_harnesss():
    libro = (LIVE / "libro_lote.ps1").read_text(encoding="utf-8")
    apps = (ESTADO / "apps_comun.ps1").read_text(encoding="utf-8")
    restos = (ESTADO / "sin_restos.ps1").read_text(encoding="utf-8")
    # Written for what the ledger classed the batch's (aCerrar: positive provenance) and for what a state launched.
    rec = libro[libro.index("$origenLibro="):libro.index("foreach($w in $nuevasDueno)")]
    assert "foreach($p in $aCerrar)" in rec and "Add-ProcesoArnes" in rec
    assert "if($nuevo){" in apps[apps.index("function Add-PropiosApp"):] and "Add-ProcesoArnes" in apps
    # Read by exact key; Office leftovers go through the document check after their save prompt is cancelled.
    stop = apps[apps.index("function Stop-ProcesoDelLote"):apps.index("function Close-ProcesosDelLote")]
    assert stop.index("Close-DialogosModales $ProcessId") < stop.index("GetActiveObject") < stop.index("$dec=Get-DecisionDocumentos")
    assert "$libro.ContainsKey($p.clave)" in restos and "Get-DecisionResto" in restos
    for name in ("'Baxy'", "'WindowsTerminal'", "'Claude'", "AppsProhibidos", "AppsHosts"):
        assert name in restos, name
    # Two Stop-Process: the Office fallback, after the titles proved every document is one a state created in that
    # exact process; and (pasada r9: leftovers kept a dialog up for hours) a non-Office leftover whose windows stay
    # after their close, only when every window it still shows is one recorded for it in the book.
    assert restos.count("Stop-Process") == 2
    office = restos[restos.index("'office' {"):restos.index("'cerrar_ventanas' {")]
    assert office.index("Get-DecisionOfficePorTitulos") < office.index("if($dt -eq 'detener')") < office.index("Stop-Process")
    ventanas = restos[restos.index("'cerrar_ventanas' {"):]
    assert ventanas.index("-notcontains [long]$_ }).Count -eq 0") < ventanas.index("Stop-Process")


def test_an_office_leftover_without_readable_com_stops_only_when_every_title_names_a_document_it_created():
    got = _decisiones([
        "Get-DecisionOfficePorTitulos @('Documento1 - Word') @('Documento1')",
        "Get-DecisionOfficePorTitulos @('Presentacion1 - PowerPoint','Presentacion1 - PowerPoint') @('Presentacion1')",
        # Counter-cases: a document nobody created there (the person's, or one a case made), no titles, no record.
        "Get-DecisionOfficePorTitulos @('Documento1 - Word','Informe ventas - Word') @('Documento1')",
        "Get-DecisionOfficePorTitulos @() @('Documento1')",
        "Get-DecisionOfficePorTitulos @('Documento1 - Word') @()",
    ])
    assert got == ["detener", "detener", "no_cierra:titulo_ajeno", "no_cierra:sin_titulos", "no_cierra:sin_titulos"]
    # The title fallback only follows a COM that read nothing; never a COM that READ a document of someone else.
    restos = (ESTADO / "sin_restos.ps1").read_text(encoding="utf-8")
    office = restos[restos.index("'office' {"):restos.index("'cerrar_ventanas' {")]
    cond = office[office.index("if($r -eq"):office.index("{", office.index("if($r -eq"))]
    assert "office_ilegible" in cond and "office_sin_com" in cond and "documento_ajeno" not in cond


def test_an_office_dialog_is_cancelled_only_over_a_document_of_the_harness():
    got = _decisiones([
        "Get-DecisionDialogoOffice 'Documento1' @('Documento1') @()",
        "Get-DecisionDialogoOffice 'informe.docx' @() @('informe.docx','informe')",
        # Counter-cases: the person's document opened in that same instance (their Save As, their save prompt), a
        # new document no state created there, an owner without a title.
        "Get-DecisionDialogoOffice 'tesis.docx' @('Documento1') @('informe.docx')",
        "Get-DecisionDialogoOffice 'Documento2' @('Documento1') @()",
        "Get-DecisionDialogoOffice '' @('Documento1') @()",
    ])
    assert got == ["cancelar", "cancelar", "no_tocar:documento_ajeno", "no_tocar:documento_ajeno",
                   "no_tocar:documento_ajeno"]
    apps = (ESTADO / "apps_comun.ps1").read_text(encoding="utf-8")
    close = apps[apps.index("function Close-DialogosModales"):apps.index("# Set by Close-AppPropia")]
    assert close.index("Get-DecisionDialogoOffice") < close.index("Close-WindowExact")


def _git_bash() -> str | None:
    # Git's bash, never System32's (WSL): the harness scripts run in Git Bash.
    git = shutil.which("git")
    if git is None:
        return None
    # git.exe lives in Git\cmd or Git\mingw64\bin; bash.exe in Git\bin.
    for root in Path(git).parents[:3]:
        candidate = root / "bin" / "bash.exe"
        if candidate.exists() and "system32" not in str(candidate).lower():
            return str(candidate)
    return None


def _turno(script: str, folder: Path) -> str:
    bash = _git_bash()
    if bash is None:
        pytest.skip("sin Git Bash")
    turno = (LIVE / "turno.sh").as_posix()
    done = subprocess.run([bash, "-c", f'export CU_TURNO_DIR="{folder.as_posix()}"; S="{turno}"; {script}'],
                          capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_desktop_turn_each_side_announces_before_it_looks(tmp_path):
    # The agent: its lock first, then the look at live.lock. With the batch's case running it stays queued (exit 3)
    # with its lock up, so the batch's next case waits for it; with the desktop free it takes the turn.
    out = _turno('echo "s01" > "$CU_TURNO_DIR/live.lock"; bash "$S" tomar a 0 >/dev/null; echo "a=$?";'
                 ' [ -e "$CU_TURNO_DIR/agent-a.lock" ] && echo lock-a;'
                 ' rm "$CU_TURNO_DIR/live.lock"; bash "$S" tomar a 0 >/dev/null; echo "a=$?";'
                 ' bash "$S" tomar b 0 >/dev/null; echo "b=$?"; bash "$S" soltar a >/dev/null;'
                 ' bash "$S" tomar b 0 >/dev/null; echo "b=$?"; bash "$S" soltar b >/dev/null; ls "$CU_TURNO_DIR" | wc -l',
                 tmp_path)
    assert out.split() == ["a=3", "lock-a", "a=0", "b=3", "b=0", "0"]
    # The batch: an agent that announced itself between the batch's wait and its live.lock saw the desktop free, so
    # the batch takes live.lock back and waits again (stubbed look: free, agent, free, free).
    # (The looks run in a subshell: the count lives in a file.)
    out = _turno('. "$S"; C="$CU_TURNO_DIR/../cuenta"; echo 0 > "$C"; turno_agentes_vivos(){ n=$(( $(cat "$C") + 1 ));'
                 ' echo $n > "$C"; [ -e "$CU_TURNO_DIR/live.lock" ] && echo "v$n:live" >&2;'
                 ' [ $n = 2 ] && echo agent-x.lock; return 0; };'
                 ' sleep(){ :; }; turno_lote_tomar c1 2>&1; echo "n=$(cat "$C")"; cut -d" " -f1 "$CU_TURNO_DIR/live.lock"',
                 tmp_path / "turno")
    assert out.split() == ["v2:live", "v4:live", "n=4", "c1"]
    # A lock nobody touched in CU_TURNO_VIEJO_MIN minutes is a dead agent's: reported, never waited for.
    out = _turno('touch -d "2 hours ago" "$CU_TURNO_DIR/agent-muerto.lock"; touch "$CU_TURNO_DIR/agent-vivo.lock";'
                 ' . "$S"; turno_agentes_vivos 2>/dev/null | xargs -n1 basename', tmp_path)
    assert out.split() == ["agent-vivo.lock"]


def test_the_batch_takes_the_desktop_only_through_the_turn():
    lote = (LIVE / "lote.sh").read_text(encoding="utf-8")
    assert 'turno_lote_tomar "$id"' in lote and "turno_lote_soltar" in lote
    # live.lock is written only by turno.sh (announce, then look again).
    assert "live.lock\"" not in lote.replace('"$LOCKS/live.lock"', "")
    assert '> "$LOCKS/live.lock"' not in lote and "agent-*.lock" not in lote.split("\n", 6)[-1]


def test_the_harness_opens_what_windows_would_raise_unasked_with_the_persons_rights():
    # v3 r5a M5: the harness opened the consoles through the shell and they came up as administrator, empty to UIA.
    # It now reads the program's manifest, the same rule as the product (InvokerLaunch.cs): highestAvailable or
    # autoElevate (not requireAdministrator) starts with RunAsInvoker; anything else keeps shell:AppsFolder.
    abierta = (ESTADO / "app_abierta.ps1").read_text(encoding="utf-8")
    assert abierta.index("Start-AppComoPersona $app") < abierta.index("shell:AppsFolder\\{0}")
    apps = (ESTADO / "apps_comun.ps1").read_text(encoding="utf-8")
    assert "requireAdministrator" in apps and "__COMPAT_LAYER" in apps and "RunAsInvoker" in apps
    src = (ESTADO / "comun.ps1").as_posix()
    got = _powershell(
        f". '{src}'; . '{(ESTADO / 'apps_comun.ps1').as_posix()}'\n"
        "$s=@(Get-StartApps | Where-Object { $_.AppID -like '*\\services.msc' })[0]\n"
        "$p=Get-LanzamientoComoPersona $s\n"
        "if($p){ 'plan:' + [IO.Path]::GetFileName($p.exe) + '|' + $p.args }else{ 'shell' }\n"
        "$q=Get-LanzamientoComoPersona ([pscustomobject]@{ Name='x'; AppID='Vendor.App_0123456789abc!App' })\n"
        "if($q){ 'plan' }else{ 'shell' }")
    assert got[-2].lower().startswith("plan:mmc.exe|") and "services.msc" in got[-2].lower()
    # Counter-case: a packaged application is never started this way.
    assert got[-1] == "shell"
