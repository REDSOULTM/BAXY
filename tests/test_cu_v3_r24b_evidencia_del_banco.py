"""Ronda 24b, «evidencia del banco legible» (banco r23, 2026-10-09). Tres casos hechos bien o plausibles que el juez
no pudo ver: (y12) en Paint los 29 interruptores «off» llenaban los 25 destacados y «Color 1: Verde» era el n.º 32;
(e1) «Se muestra 100» y el ListItem «25 × 4= 100» no tienen estado ni valor y se descartaban; (x10) en Steam (CEF, un
solo control) el texto OCR y las marcas de tinta («JUEGOS (1/1416)», BIBLIOTECA ink=blue) eran la única prueba y no se
copiaban. Además Get-SteamOrReport devolvía Object[] (línea + $null) y el estado base de x10 reventó en
Read-SteamPage([IntPtr]) en lugar de decir steam_sin_ventana."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from baxy_mind import turn_audit as turn_audit_module
from baxy_mind import computer_use_finals
from baxy_mind import llm_audit
from baxy_mind import llm_compose


# Every mind module whose code writes a composition stage: the audit is patched in each one.
_COMPOSE_STAGE_WRITERS = (computer_use_finals, llm_audit, llm_compose)

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "scripts" / "cu_live"
ESTADO = LIVE / "estado"


def _modulo():
    spec = importlib.util.spec_from_file_location("journal_caso_r24b", LIVE / "journal_caso.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


jc = _modulo()


def _vista(controles: list[dict], root: int = 500, focused: dict | None = None, **extra) -> dict:
    res = {"version": 2, "ok": True, "error": "",
           "window": {"title": "Ventana", "process": "prueba", "hwnd": root, "root": root, "focused": focused},
           "controls": controles}
    res.update(extra)
    return {"phase": "completed", "operation": "input.visible.controls", "timestampUtc": "2026-10-09T23:06:56Z",
            "missionId": "m", "response": {"status": "completed", "result": res}}


def _c(i: int, kind: str, name: str, state: str = "", value=None, id_: str | None = None) -> dict:
    return {"i": i, "kind": kind, "name": name, "id": id_ if id_ is not None else f"42.{i}", "state": state,
            "value": value, "zone": "C"}


def _paint(color: str, foco_verde: bool = False) -> list[dict]:
    # 29 interruptores «off» de la cinta antes que la paleta, como en el journal (línea 6270).
    ctl = [_c(i, "Button", f"Herramienta {chr(65 + i % 26)}", "off") for i in range(29)]
    ctl += [_c(29 + i, "Button", f"Pincel {chr(65 + i)}") for i in range(5)]
    ctl.append(_c(40, "ListItem", "Negro"))
    ctl.append(_c(41, "ListItem", "Verde", "focused" if foco_verde else ""))
    ctl.append(_c(60, "Button", f"Color 1: {color}", "selected"))
    return ctl


def test_y12_el_estado_vivo_va_antes_que_los_off():
    e = jc.recorta(_vista(_paint("Verde")))
    nombres = [d["name"] for d in e["destacados"]]
    assert nombres[0] == "Color 1: Verde"
    # «off» al final, todos dentro del cupo; ninguno omitido.
    assert all(d.get("state") == "off" for d in e["destacados"][1:])
    assert e["destacados_omitidos"] == 0


def test_el_cupo_cuenta_lo_omitido():
    ctl = [_c(i, "ToggleButton", f"Opcion {chr(65 + i % 26)}{chr(65 + i // 26)}", "off") for i in range(jc.MAX_DESTACADOS + 7)]
    e = jc.recorta(_vista(ctl))
    assert len(e["destacados"]) == jc.MAX_DESTACADOS and e["destacados_omitidos"] == 7


def test_e1_el_dato_en_el_name_se_conserva_y_un_identificador_no():
    ctl = [_c(0, "Button", "Es igual a"), _c(1, "Text", "Se muestra 100"), _c(2, "ListItem", "25 × 4= 100"),
           _c(3, "Button", "b12"), _c(4, "Text", "Win32"), _c(5, "Text", "Calculadora")]
    nombres = [d["name"] for d in jc.recorta(_vista(ctl))["destacados"]]
    assert nombres == ["Se muestra 100", "25 × 4= 100"]


def _extrae(tmp_path: Path, vistas: list[dict]) -> list[dict]:
    """Corre extrae() sobre un journal con estas vistas, una por segundo dentro de la corrida."""
    t0 = 1_791_582_241_000
    ev = tmp_path / "v2-caso"
    ev.mkdir()
    (ev / "events.jsonl").write_text(json.dumps({"event": {"t": t0}}) + "\n" + json.dumps({"event": {"t": t0 + 60_000}})
                                     + "\n", encoding="utf-8")
    from datetime import datetime, timezone
    lineas = []
    for n, v in enumerate(vistas):
        d = datetime.fromtimestamp((t0 + 1000 * (n + 1)) / 1000, tz=timezone.utc)
        v = dict(v, timestampUtc=d.strftime("%Y-%m-%dT%H:%M:%S.%f0+00:00"), sequence=n + 1)
        lineas.append(json.dumps({"version": 2, "payload": v}, ensure_ascii=False))
    (tmp_path / "missions.jsonl").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return jc.extrae(ev, tmp_path / "missions.jsonl")["entradas"]


def test_y12_cambios_entre_vistas_de_la_misma_raiz(tmp_path):
    antes, despues = _extrae(tmp_path, [_vista(_paint("Negro")), _vista(_paint("Verde"))])
    assert "cambios" not in antes
    c = despues["cambios"]
    assert c["cambio"] == [{"kind": "Button", "name": "Color 1: Verde", "antes": {"name": "Color 1: Negro"},
                            "ahora": {"name": "Color 1: Verde"}}]
    assert "aparecio" not in c and "desaparecio" not in c and "foco" not in c


def test_y12_contracaso_clic_sin_efecto_solo_trae_el_foco(tmp_path):
    foco = {"kind": "ListItem", "name": "Verde", "value": None}
    _, despues = _extrae(tmp_path, [_vista(_paint("Negro")), _vista(_paint("Negro", foco_verde=True), focused=foco)])
    c = despues["cambios"]
    assert c["foco"] == {"antes": None, "ahora": {"kind": "ListItem", "name": "Verde"}}
    assert c["cambio"] == [{"kind": "ListItem", "name": "Verde", "antes": {"state": ""}, "ahora": {"state": "focused"}}]
    # El diff no inventa pruebas: nada de Color 1.
    assert "Color 1" not in json.dumps(c, ensure_ascii=False)


def test_e1_contracaso_un_enter_que_no_evalua(tmp_path):
    calc = [_c(0, "Button", "Es igual a"), _c(1, "Text", "Se muestra 4"),
            _c(2, "Text", "No hay historial todavía")]
    antes, despues = _extrae(tmp_path, [_vista(calc), _vista([dict(c) for c in calc])])
    assert [d["name"] for d in despues["destacados"]] == ["Se muestra 4"]
    assert despues["cambios"] == {}
    assert "100" not in json.dumps([despues["destacados"], despues["cambios"]], ensure_ascii=False)


def test_e1_el_historial_que_aparece_y_el_display_que_cambia(tmp_path):
    a = [_c(0, "Text", "Se muestra 0"), _c(1, "Text", "No hay historial todavía")]
    b = [_c(0, "Text", "Se muestra 100"), _c(2, "ListItem", "25 × 4= 100")]
    _, despues = _extrae(tmp_path, [_vista(a), _vista(b)])
    c = despues["cambios"]
    assert c["cambio"][0]["ahora"] == {"name": "Se muestra 100"}
    assert c["aparecio"] == [{"kind": "ListItem", "name": "25 × 4= 100"}]
    assert c["desaparecio"] == [{"kind": "Text", "name": "No hay historial todavía"}]


def test_configuracion_un_cambio_al_final_de_40_interruptores_on(tmp_path):
    a = [_c(i, "Button", f"Interruptor {chr(65 + i % 26)}{chr(65 + i // 26)}", "on") for i in range(40)]
    a.append(_c(40, "Button", "Ahorro de bateria", "off"))
    b = [dict(c) for c in a]
    b[-1] = dict(b[-1], state="on")
    _, despues = _extrae(tmp_path, [_vista(a), _vista(b)])
    # Los 40 «on» llenan el cupo de destacados; el cambio está en «cambios» igual.
    assert despues["destacados_omitidos"] == 1
    assert despues["cambios"]["cambio"] == [{"kind": "Button", "name": "Ahorro de bateria", "antes": {"state": "off"},
                                             "ahora": {"state": "on"}}]


def test_otra_identidad_con_el_mismo_contenido_no_es_un_cambio(tmp_path):
    a = [_c(0, "ListItem", "Documentos", id_="42.1"), _c(1, "ListItem", "Musica", "selected", id_="42.2")]
    b = [_c(0, "ListItem", "Documentos", id_="42.7"), _c(1, "ListItem", "Musica", id_="42.8")]
    _, despues = _extrae(tmp_path, [_vista(a), _vista(b)])
    assert despues["cambios"] == {"cambio": [{"kind": "ListItem", "name": "Musica", "antes": {"state": "selected"},
                                              "ahora": {"state": ""}}]}


def test_el_name_que_cambio_desde_la_primera_vista_se_conserva(tmp_path):
    v1 = [_c(0, "Text", "Sin conexion")]
    v2 = [_c(0, "Text", "Conectado")]
    *_, ultima = _extrae(tmp_path, [_vista(v1), _vista(v2), _vista([dict(c) for c in v2])])
    assert ultima["destacados"] == [{"kind": "Text", "name": "Conectado"}]


def _steam(**extra) -> dict:
    return _vista([_c(0, "Pane", "Steam")], **extra)


def test_x10_ventana_sin_arbol_conserva_texto_y_marcas_de_arriba():
    texto = {"TL": ["TIENDA BIBLIOTECA COMUNIDAD"], "T": ["JUEGOS (1/1416)"], "C": ["Contenido privado"]}
    marcas = [{"text": "BIBLIOTECA", "zone": "TL", "ink": "blue", "inkV": 200, "rect": {"x": 1}},
              {"text": "TIENDA", "zone": "TL", "ink": "grey"}, {"text": "Abajo", "zone": "B", "ink": "white"}]
    e = jc.recorta(_steam(text=texto, textMarks=marcas))
    assert e["texto_arriba"] == {"TL": ["TIENDA BIBLIOTECA COMUNIDAD"], "T": ["JUEGOS (1/1416)"]}
    assert e["marcas_arriba"] == [{"text": "BIBLIOTECA", "zone": "TL", "ink": "blue"},
                                  {"text": "TIENDA", "zone": "TL", "ink": "grey"}]
    assert "Contenido privado" not in json.dumps(e)


def test_x10_contracaso_una_ventana_con_arbol_no_copia_el_ocr():
    e = jc.recorta(_vista(_paint("Verde"), text={"TL": ["Archivo"]}, textMarks=[{"text": "Archivo", "zone": "TL"}]))
    assert "texto_arriba" not in e and "marcas_arriba" not in e
    # Sólo el marco (frameOnly) también es una ventana sin árbol.
    e = jc.recorta(_vista([_c(0, "TitleBar", "x"), _c(1, "Button", "Cerrar")], frameOnly=True, text={"T": ["Hola"]}))
    assert e["texto_arriba"] == {"T": ["Hola"]}


def test_steam_or_report_devuelve_la_linea_sin_null_y_los_llamadores_comprueban_intptr():
    s = (ESTADO / "steam_comun.ps1").read_text(encoding="utf-8")
    cuerpo = "\n".join(l for l in s[s.index("function Get-SteamOrReport"):].splitlines() if not l.lstrip().startswith("#"))
    assert "return $null" not in cuerpo
    assert cuerpo.count("Write-Output (Write-Estado") == 2
    usos = 0
    for p in ESTADO.glob("*.ps1"):
        t = p.read_text(encoding="utf-8")
        for m in re.finditer(r"(\$\w+)=Get-\w+OrReport\b[^\n]*", t):
            if "function" in m.group(0):
                continue
            usos += 1
            assert f"if({m.group(1)} -isnot [IntPtr]){{ {m.group(1)}; return }}" in m.group(0), p.name
    assert usos >= 3


def _powershell() -> str | None:
    if os.name != "nt":
        return None
    return shutil.which("powershell") or shutil.which("powershell.exe")


@pytest.mark.parametrize("procesos,esperado,abre", [("@([pscustomobject]@{Id=987654321})", "steam_sin_ventana", True),
                                                    ("@()", "steam_no_abierto", False)])
def test_x10_steam_sin_ventana_da_su_linea_y_no_el_error_de_top(procesos, esperado, abre):
    ps = _powershell()
    if ps is None:
        pytest.skip("PowerShell de Windows no disponible")
    # Get-Process simulado: Steam corre (o no) con un PID que no tiene ninguna ventana. Start-Process simulado: con
    # Steam en la bandeja el estado pide su ventana por su protocolo (banco r30, g1/x10) y, si no llega, da su línea.
    cmd = ("function Get-Process { [CmdletBinding()] param([Parameter(Position=0)][string[]]$Name) " + procesos + " }; "
           "function Start-Process { param([Parameter(Position=0)][string]$FilePath) Write-Host ('ABRE:'+$FilePath) }; "
           f"& '{ESTADO / 'steam_tienda.ps1'}'")
    r = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    salida = r.stdout + r.stderr
    lineas = [l for l in r.stdout.splitlines() if l.startswith('{"estado"')]
    assert len(lineas) == 1, salida
    d = json.loads(lineas[0])
    assert d["estado"] == "steam_tienda" and d["resultado"] == esperado and d["verificado"] is False
    assert "IntPtr" not in salida and "Object[]" not in salida
    assert ("ABRE:steam://open/main" in r.stdout) is abre


# Revisión 1 de la r24b (B4): el testigo medido llega al turn audit y el final dicho desde los hechos, al compose audit.
def _mision_calculo(testigo: dict | None) -> dict:
    observado = {
        "goal": "calcular 25*4", "application": "Calculadora", "reached": True, "satisfiedBy": "result:25*4",
        "steps": [{"step": 1, "operation": "app.open", "appId": "Calculadora", "ok": True, "changed": True},
                  {"step": 2, "operation": "input.text.type", "text": "25*4", "ok": True, "changed": True},
                  {"step": 3, "operation": "input.key.press", "key": "enter", "ok": True, "changed": True}],
        "window": {"title": "Calculadora", "process": "ApplicationFrameHost"}, "joined": False,
        "screen": {"title": "Calculadora", "numbers": ["La expresión es 25 × 4=", "Se muestra 100"]},
    }
    if testigo is not None:
        observado["witness"] = testigo
    return {"kind": "operation", "operation": "mission.computer.use", "polarity": "success", "verified": True,
            "succeeded": True, "observed": observado}


_TESTIGO = {"atom": "result:25*4", "via": "uia.Text", "shown": "Se muestra 100", "read": "6216088e115d4372b379b40d79a47452"}


def test_b4_el_turn_audit_lleva_el_testigo_de_la_mision():

    registro = turn_audit_module._computer_use_witness_audit("t-1", _mision_calculo(_TESTIGO))
    assert registro is not None
    assert registro["phase"] == "computer_use_final" and registro["request_id"] == "t-1"
    assert registro["satisfied_by"] == "result:25*4" and registro["witness"] == _TESTIGO
    # Contracaso: un turno que no cuenta una misión no deja registro.
    assert turn_audit_module._computer_use_witness_audit("t-2", {"kind": "operation", "operation": "app.open"}) is None


def test_b4_el_turn_audit_se_escribe_al_componer(monkeypatch, tmp_path):

    destino = tmp_path / "turn_audit.jsonl"
    monkeypatch.setenv(turn_audit_module.TURN_AUDIT_ENV, str(destino))
    turn_audit_module._append_turn_audit(turn_audit_module._computer_use_witness_audit("t-1", _mision_calculo(_TESTIGO)))
    fila = json.loads(destino.read_text(encoding="utf-8").splitlines()[-1])
    assert fila["witness"]["shown"] == "Se muestra 100" and fila["witness"]["read"] == _TESTIGO["read"]
    # El cableado: el manejador de message.compose lo agrega tras leer la situación.
    fuente = (ROOT / "src" / "baxy_mind" / "__main__.py").read_text(encoding="utf-8")
    assert "witnessed = _computer_use_witness_audit(message.get(\"id\"), situation)" in fuente


def test_b4_el_final_dicho_desde_los_hechos_queda_en_el_compose_audit(monkeypatch, tmp_path):
    destino = tmp_path / "compose_audit.jsonl"
    monkeypatch.setenv("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH", str(destino))
    monkeypatch.setenv("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_CONTENT", "1")
    situacion = _mision_calculo(_TESTIGO)
    final = computer_use_finals._computer_use_floor_first(situacion, "es")
    assert final == "Listo: 25 × 4 = 100."
    computer_use_finals._capture_floor_first("traza", "operation", "es", situacion, final)
    fila = json.loads(destino.read_text(encoding="utf-8").splitlines()[-1])
    assert fila["stage"] == "floor_first" and fila["published"] is True and fila["draft"] == final
    assert fila["payload"]["witness"] == _TESTIGO
    assert "Se muestra 100" in fila["payload"]["numbers"]
    assert {"numbers", "seen", "witness"} <= set(fila["payload_keys"])
    # El cableado: el final dicho desde los hechos se registra antes de devolverse.
    fuente = (ROOT / "src" / "baxy_mind" / "llm_compose.py").read_text(encoding="utf-8")
    assert "_capture_floor_first(trace_id, intent, response_language, situation, floor_first)\n            return floor_first" in fuente


def test_b4_contracaso_sin_ruta_de_audit_no_se_escribe_nada(monkeypatch, tmp_path):
    monkeypatch.delenv("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH", raising=False)
    llamadas: list[dict] = []
    for module in _COMPOSE_STAGE_WRITERS:
        monkeypatch.setattr(module, "_capture_compose_stage", lambda **fila: llamadas.append(fila))
    computer_use_finals._capture_floor_first("traza", "operation", "es", _mision_calculo(_TESTIGO), "Listo: 25 × 4 = 100.")
    assert llamadas == []
