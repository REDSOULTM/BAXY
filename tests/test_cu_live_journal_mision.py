"""BANCO_72 r23 (2026-10-09, usuario simulado): (1) los 72 verificacion-despues.json salieron con «ventanas: []»
porque verificar.ps1 sólo volcaba las apps del manifiesto v3; (2) after.png se tomaba después de devolverle el frente
a la persona y mostraba su ventana encima del resultado; (3) el paquete del revisor no traía las lecturas UIA del Core.
Ahora cu_live.sh, al terminar el conductor y antes de parar el medidor, saca las entradas del journal de la corrida
(journal_caso.py) y fotografía la última ventana tocada (captura_mision.ps1); verificar.ps1 vuelca las ventanas
tocadas, la del frente y las nacidas en el caso aunque el caso no tenga manifiesto."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "scripts" / "cu_live"


def _modulo():
    spec = importlib.util.spec_from_file_location("journal_caso", LIVE / "journal_caso.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


jc = _modulo()
T0 = 1_791_582_241_000  # ms epoch del primer sello «t» de la corrida


def _iso(ms: int) -> str:
    # El Core escribe 7 decimales y la zona: «2026-10-09T21:44:04.3430555+00:00».
    d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%S.") + f"{d.microsecond:06d}0+00:00"


def _linea(seq: int, ms: int, op: str, phase: str = "completed", result=None, status="completed", error=None) -> str:
    resp = None
    if phase == "completed":
        resp = {"type": "operation.response", "status": status, "message": "{}", "result": result, "errorCode": error}
    pl = {"sequence": seq, "timestampUtc": _iso(ms), "phase": phase, "requestId": f"r{seq}", "missionId": f"m{seq}",
          "invocationId": f"i{seq}", "operation": op, "requestFingerprint": "x" * 64, "response": resp}
    return json.dumps({"version": 2, "authentication": "hmac-sha256", "payload": pl, "previousTag": "a", "tag": "b"})


def _controles(hwnd: int, n: int, seleccionado: str) -> dict:
    ctl = [{"i": i, "kind": "Button", "name": f"b{i}", "state": "", "value": None} for i in range(n)]
    ctl.append({"i": n, "kind": "ListItem", "name": seleccionado, "state": "selected", "value": None})
    ctl.append({"i": n + 1, "kind": "Edit", "name": "campo", "state": "", "value": "hola"})
    ctl.append({"i": n + 2, "kind": "MenuItem", "name": "Sistema", "state": "collapsed", "value": None})
    return {"version": 2, "ok": True, "error": "",
            "window": {"title": "App de prueba", "process": "prueba", "processId": 7, "hwnd": hwnd + 1, "root": hwnd,
                       "foreground": False, "focused": {"kind": "Edit", "name": "campo", "value": "hola"}},
            "controls": ctl}


def _evidencia(tmp: Path, con_t: bool = True) -> Path:
    ev = tmp / "v2-s03"
    ev.mkdir()
    lineas = ['{"type":"runtime","ready":true}']
    if con_t:
        lineas += [json.dumps({"type": "event", "event": {"type": "boot_stage", "t": T0}}),
                   json.dumps({"type": "event", "event": {"type": "boot_stage", "t": T0 + 20_000}})]
    (ev / "events.jsonl").write_text("﻿" + "\n".join(lineas) + "\n", encoding="utf-8")
    return ev


def _journal(tmp: Path) -> Path:
    d = tmp / "journal"
    d.mkdir()
    antes = [_linea(1, T0 - 60_000, "input.visible.click", result={"name": "de otro caso", "selected": True})]
    corrida = [
        _linea(2, T0 + 1_000, "memory.status", result={"ciphertext": "SECRETO", "protection": "dpapi"}),
        _linea(3, T0 + 2_000, "app.open", phase="started"),
        _linea(4, T0 + 2_500, "app.open", result={"appId": "Prueba", "alreadyRunning": False, "windowHandle": 500}),
        _linea(5, T0 + 3_000, "input.visible.controls", result=_controles(500, 80, "Inicio")),
        _linea(6, T0 + 4_000, "input.visible.click",
               result={"name": "Bluetooth", "kind": "ListItem", "selected": True, "surfaceChanged": True,
                       "reachedState": {"title": "Bluetooth y dispositivos", "selected": True}, "cascadeStage": "uia"}),
        _linea(7, T0 + 5_000, "input.text.type", result={"textLength": 4, "window": 900, "windowTitle": "Bloc"}),
        _linea(8, T0 + 6_000, "input.visible.click", status="failed", error="visible_button_not_found"),
    ]
    despues = [_linea(9, T0 + 120_000, "input.visible.click", result={"name": "del caso siguiente"})]
    # Un segmento sellado con el comienzo de la corrida y el archivo vivo con el resto (JOURNAL_ROTACION.md).
    (d / "missions.3.jsonl").write_text("\n".join(antes + corrida[:3]) + "\n", encoding="utf-8")
    (d / "missions.2.jsonl").write_text(_linea(0, T0 - 600_000, "input.visible.click") + "\n", encoding="utf-8")
    (d / "missions.jsonl").write_text("\n".join(corrida[3:] + despues) + "\n", encoding="utf-8")
    return d / "missions.jsonl"


def test_las_entradas_son_las_de_la_corrida_aun_con_el_journal_sellado(tmp_path):
    ev, journal = _evidencia(tmp_path), _journal(tmp_path)
    d = jc.extrae(ev, journal)
    ops = [e["op"] for e in d["entradas"]]
    # Sin la memoria (cifrada), sin las fases «started», sin los casos de antes y después.
    assert ops == ["app.open", "input.visible.controls", "input.visible.click", "input.text.type", "input.visible.click"]
    assert "SECRETO" not in json.dumps(d)
    assert "de otro caso" not in json.dumps(d) and "del caso siguiente" not in json.dumps(d)
    # La última ventana tocada primero; la vista cuenta por su raíz de primer nivel.
    assert d["tocadas"] == [900, 500]


def test_cada_entrada_se_recorta_a_lo_observado(tmp_path):
    d = jc.extrae(_evidencia(tmp_path), _journal(tmp_path))
    vista = next(e for e in d["entradas"] if e["op"] == "input.visible.controls")
    assert vista["controles"] == 83 and vista["ventana"]["root"] == 500
    assert vista["ventana"]["focused"] == {"kind": "Edit", "name": "campo", "value": "hola"}
    # Sólo los controles con estado o valor; «collapsed» no dice nada.
    assert vista["destacados"] == [{"kind": "ListItem", "name": "Inicio", "state": "selected"},
                                   {"kind": "Edit", "name": "campo", "value": "hola"}]
    clic = next(e for e in d["entradas"] if e["op"] == "input.visible.click" and e["estado"] == "completed")
    assert clic["observado"]["selected"] is True and clic["observado"]["surfaceChanged"] is True
    assert clic["observado"]["reachedState"] == {"title": "Bluetooth y dispositivos", "selected": True}
    assert "cascadeStage" not in clic["observado"]
    fallo = [e for e in d["entradas"] if e.get("error")]
    assert fallo and fallo[0]["estado"] == "failed" and fallo[0]["error"] == "visible_button_not_found"


def test_sin_sellos_t_la_corrida_sale_de_la_hora_de_events_y_la_traza(tmp_path):
    ev = _evidencia(tmp_path, con_t=False)
    (ev / "trace.jsonl").write_text('{"seq":1,"ms":0.3}\n{"seq":9,"ms":30000.5}\n', encoding="utf-8")
    ini, fin = jc.intervalo(ev)
    mt = int((ev / "events.jsonl").stat().st_mtime * 1000)
    assert fin == mt + jc.MARGEN_MS and ini == mt - 30_000 - 2 * jc.MARGEN_MS
    assert jc.intervalo(tmp_path / "no-existe") is None


def test_el_cli_escribe_journal_caso_json(tmp_path):
    ev, journal = _evidencia(tmp_path), _journal(tmp_path)
    assert jc.main([str(ev), "--journal", str(journal)]) == 0
    d = json.loads((ev / "journal-caso.json").read_text(encoding="utf-8"))
    assert d["tocadas"] == [900, 500] and d["total"] == 5


def test_cu_live_captura_la_mision_antes_de_devolver_el_frente():
    s = (LIVE / "cu_live.sh").read_text(encoding="utf-8")
    jcaso, foto = s.index('journal_caso.py"'), s.index('captura_mision.ps1"')
    assert s.index("CODE=$?") < jcaso < foto < s.index('touch "$CTL/parar"')
    # También sin medidor (CU_MOLESTIA=0): antes de devolver volumen y brillo.
    assert foto < s.index("RESTO=$(devolver)")
    # La ventana del usuario simulado nunca es la fotografiada.
    assert '-Excluir "$EXCL"' in s and "listo.json" in s[s.index("EXCL="):foto]


def test_captura_mision_no_toma_foco_ni_nombra_apps():
    s = (LIVE / "captura_mision.ps1").read_text(encoding="utf-8")
    codigo = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    for robo in ("SetForegroundWindow", "SwitchToThisWindow", "ShowWindow", "keybd_event", "SetFocus"):
        assert robo not in codigo
    assert "Get-WindowBitmap" in codigo and "AppsProhibidos" in codigo
    assert not re.search(r"'(Discord|Spotify|notepad|Calculator)'", codigo, re.I)


def test_verificar_vuelca_tocadas_frente_y_nacidas_sin_manifiesto():
    s = (LIVE / "verificar.ps1").read_text(encoding="utf-8")
    bloque = s[s.index("if($Fase -eq 'despues'){"):s.index("$propiasH=")]
    for clave in ("journal-caso.json", "after-mision.json", "tocada_por_baxy", "primer_plano_mision",
                  "nacida_en_el_caso", "$previos -notcontains"):
        assert clave in bloque
    # Se lee como ASCII en PowerShell 5.1 (sin BOM): nada fuera de ASCII en el script.
    assert all(ord(c) < 128 for c in s)
    # Un caso del banco da sus turnos (cases/<id>.turns).
    assert "cases\\$tid.turns" in s and "$dump['turnos']=$turnosCaso" in s


def _git_bash() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    for root in Path(git).parents[:3]:
        c = root / "bin" / "bash.exe"
        if c.exists() and "system32" not in str(c).lower():
            return str(c)
    return None


def test_evidencia_corre_aparta_la_foto_y_el_journal_de_otra_corrida(tmp_path):
    exe = _git_bash()
    if exe is None:
        pytest.skip("bash de Git no disponible")
    ev = tmp_path / "v2-s03"
    ev.mkdir()
    for n in ("journal-caso.json", "after-mision.png", "after-mision.json", "after.png"):
        (ev / n).write_text("vieja", encoding="utf-8")
    lib = (LIVE / "evidencia_no_corrio.sh").as_posix()
    r = subprocess.run([exe, "-c", f'. "{lib}"; evidencia_corre "{ev.as_posix()}"'], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in (ev / "anterior").iterdir()) == ["after-mision.json", "after-mision.png",
                                                                   "journal-caso.json"]
