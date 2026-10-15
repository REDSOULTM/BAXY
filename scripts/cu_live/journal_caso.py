"""Entradas del journal del perfil de prueba que son de la última corrida de un caso (evidencia independiente).

usage: journal_caso.py <carpeta-evidencia> [--journal <missions.jsonl>] [--salida <archivo.json>]
  Escribe <carpeta>/journal-caso.json (o --salida) e imprime una línea de resumen.

El journal (journal/missions.jsonl del perfil, sellado por el Core) guarda cada vista (input.visible.controls) y
cada recibo de clic, tecla, tipeo o apertura con lo que el Core leyó por UIA después (selected, value, title,
reachedState, surfaceChanged...). No es la frase de BAXY: un revisor lo usa para juzgar el caso sin creerle.
- La corrida es el intervalo de los sellos «t» de events.jsonl (la App los escribe en cada etapa de cada turno),
  con un margen; sin sellos, la hora de events.jsonl menos lo que duró la traza.
- Se leen las líneas del final hacia atrás, también los segmentos sellados (missions.<n>.jsonl) cuando la corrida
  empezó antes que el archivo vivo: el journal pesa decenas de MiB y la corrida está al final.
- Cada entrada se recorta: una vista da su ventana, el control enfocado, cuántos controles vio y los destacados por
  informatividad (estado o valor vivos; un número en el Name o un Name que cambió desde la primera vista; «off» y
  readonly al final) con «destacados_omitidos»; desde la segunda vista de una raíz, sus «cambios» (nombre, estado o
  valor de un mismo control, lo que apareció y lo que desapareció, y el foco). Una ventana sin árbol (≤1 control o
  sólo el marco) da además el texto OCR y las marcas de tinta de la banda superior. Un recibo da sus campos
  escalares. Las operaciones de memoria (cifradas) no se copian.
- «tocadas» son las ventanas de primer nivel en que BAXY leyó o actuó, la última primero: captura_mision.ps1 las
  fotografía y verificar.ps1 las vuelca aunque el caso no tenga app en el manifiesto.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

MARGEN_MS = 5000
MAX_ENTRADAS = 60
MAX_DESTACADOS = 40
MAX_CAMBIOS = 120
MAX_MARCAS = 30
MAX_LINEAS_ZONA = 12
MAX_TEXTO = 160
# Banda superior de la ventana: donde una ventana sin árbol (CEF, SDL) dibuja pestañas, título y contadores.
_ZONAS_ARRIBA = ("TL", "T", "TR")
# Un número suelto en el Name es un dato («Se muestra 100», «25 × 4= 100», «JUEGOS (1/1416)»); pegado a letras
# («b12», «Win32», «h264») es parte de un identificador.
_NUMERO = re.compile(r"(?<![^\W_])\d+(?![^\W_])")
# Estados que sí son estado pero casi nunca informan (los 29 interruptores «off» de una paleta, las ventanas readonly).
_ESTADOS_BAJOS = {"off", "readonly"}
_TS = re.compile(rb'"timestampUtc":\s*"([^"]+)"')
_TS_ISO = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d+))?(Z|[+-]\d\d:\d\d)?$")
# Campos de un recibo que no dicen nada del estado observado o que son material cifrado.
_SIN_VALOR = {"ciphertext", "purpose", "protection", "version", "requestFingerprint", "inputSize", "lastWin32Error",
              "acceptedEvents", "expectedEvents", "cascadeStage"}
_ESTADOS_SIN_VALOR = {"", "collapsed", "normal"}


def ms_de_iso(s: str) -> int | None:
    m = _TS_ISO.match(s.strip())
    if not m:
        return None
    frac = (m.group(2) or "0")[:6].ljust(6, "0")
    tz = m.group(3) or "+00:00"
    if tz == "Z":
        tz = "+00:00"
    try:
        return int(datetime.fromisoformat(f"{m.group(1)}.{frac}{tz}").timestamp() * 1000)
    except ValueError:
        return None


def intervalo(ev: Path) -> tuple[int, int] | None:
    """(inicio, fin) en ms epoch de la última corrida, o None si la carpeta no tiene events.jsonl."""
    p = ev / "events.jsonl"
    if not p.exists():
        return None
    ts: list[int] = []
    for linea in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        for m in re.finditer(r'"t":\s*(\d{12,14})\b', linea):
            ts.append(int(m.group(1)))
    if ts:
        return min(ts) - MARGEN_MS, max(ts) + MARGEN_MS
    fin = int(p.stat().st_mtime * 1000)
    dur = 0.0
    tr = ev / "trace.jsonl"
    if tr.exists():
        for linea in tr.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.search(r'"ms":\s*([0-9.]+)', linea)
            if m:
                dur = max(dur, float(m.group(1)))
    return fin - int(dur) - 2 * MARGEN_MS, fin + MARGEN_MS


def segmentos(journal: Path) -> list[Path]:
    """El archivo vivo y después los sellados, del más nuevo al más viejo."""
    sellados = []
    for p in journal.parent.glob(journal.stem + ".*" + journal.suffix):
        m = re.fullmatch(re.escape(journal.stem) + r"\.(\d+)" + re.escape(journal.suffix), p.name)
        if m:
            sellados.append((int(m.group(1)), p))
    return ([journal] if journal.exists() else []) + [p for _, p in sorted(sellados, reverse=True)]


def _lineas_desde(path: Path, inicio: int, bloque: int = 1 << 20):
    """Líneas (bytes) con sello >= inicio, leyendo el archivo desde el final. Devuelve (líneas, llegó_antes)."""
    out: list[bytes] = []
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        resto = b""
        while pos > 0:
            n = min(bloque, pos)
            pos -= n
            f.seek(pos)
            buf = f.read(n) + resto
            partes = buf.split(b"\n")
            resto = partes[0] if pos > 0 else b""
            completas = partes[1:] if pos > 0 else partes
            for linea in reversed(completas):
                m = _TS.search(linea)
                t = ms_de_iso(m.group(1).decode("ascii", "replace")) if m else None
                if t is None:
                    continue
                if t < inicio:
                    return list(reversed(out)), True
                out.append(linea)
    return list(reversed(out)), False


def _corta(v):
    if isinstance(v, str):
        return v if len(v) <= MAX_TEXTO else v[:MAX_TEXTO] + "..."
    return v


def _escalares(d: dict) -> dict:
    return {k: _corta(v) for k, v in d.items()
            if k not in _SIN_VALOR and v is not None and not isinstance(v, (dict, list))}


def _clave(c: dict) -> tuple:
    """Identidad de un control entre dos vistas de la misma raíz: su id UIA, o (i, kind) cuando no lo trae."""
    return ("id", c["id"]) if c.get("id") else ("i", c.get("i"), c.get("kind"))


def _ficha(c: dict) -> dict:
    x = {"kind": c.get("kind"), "name": _corta(c.get("name"))}
    estado = str(c.get("state") or "")
    if estado not in _ESTADOS_SIN_VALOR:
        x["state"] = estado
    if c.get("value") not in (None, ""):
        x["value"] = _corta(str(c.get("value")))
    return x


def _rango(c: dict, primera: dict | None) -> int | None:
    """Cuánto informa un control: 0 estado o valor vivos, 1 dato en el Name, 2 off/readonly; None no se destaca."""
    fichas = set(str(c.get("state") or "").split()) - _ESTADOS_SIN_VALOR
    valor = c.get("value") not in (None, "")
    nombre = str(c.get("name") or "")
    if fichas - _ESTADOS_BAJOS or (valor and "readonly" not in fichas):
        return 0
    if _NUMERO.search(nombre) or (primera is not None and primera.get(_clave(c), nombre) != nombre):
        return 1
    if fichas or valor:
        return 2
    return None


def _foco(w: dict) -> dict | None:
    foc = w.get("focused")
    if not isinstance(foc, dict):
        return None
    return {k: _corta(foc.get(k)) for k in ("kind", "name", "value") if foc.get(k) not in (None, "")} or None


def cambios(antes: list[dict], ahora: list[dict], foco_antes=None, foco_ahora=None) -> dict:
    """Lo que cambió entre dos vistas de la misma raíz: nombre, estado o valor de un mismo control, lo que apareció y
    lo que desapareció. Un control que sólo cambió de identidad (mismo kind, nombre, estado y valor) no cuenta; uno
    que reaparece con otra identidad y el mismo kind y nombre cuenta como cambio de estado o valor."""
    a = {_clave(c): c for c in antes}
    b = {_clave(c): c for c in ahora}
    cambio: list[dict] = []

    def _dif(x: dict, y: dict) -> None:
        de, a_ = {}, {}
        for f in ("name", "state", "value"):
            vx, vy = x.get(f), y.get(f)
            if (vx if vx is not None else "") != (vy if vy is not None else ""):
                de[f], a_[f] = _corta(vx), _corta(vy)
        if de:
            cambio.append({"kind": y.get("kind"), "name": _corta(y.get("name")), "antes": de, "ahora": a_})

    for k, c in b.items():
        if k in a:
            _dif(a[k], c)
    nuevos = [c for k, c in b.items() if k not in a]
    idos = [c for k, c in a.items() if k not in b]
    # Mismo contenido con otra identidad (la lista se volvió a dibujar): no es un cambio.
    for c in list(nuevos):
        f = _ficha(c)
        par = next((d for d in idos if _ficha(d) == f), None)
        if par is not None:
            idos.remove(par)
            nuevos.remove(c)
    # Mismo kind y nombre con otra identidad: cambio de estado o valor.
    for c in list(nuevos):
        par = next((d for d in idos if d.get("kind") == c.get("kind") and d.get("name") == c.get("name")), None)
        if par is not None:
            idos.remove(par)
            nuevos.remove(c)
            _dif(par, c)
    out: dict = {}
    if foco_antes != foco_ahora:
        out["foco"] = {"antes": foco_antes, "ahora": foco_ahora}
    resto = MAX_CAMBIOS
    omitidos = 0
    for clave, lista in (("cambio", cambio), ("aparecio", [_ficha(c) for c in nuevos]),
                         ("desaparecio", [_ficha(c) for c in idos])):
        if lista:
            out[clave] = lista[:resto]
            omitidos += max(0, len(lista) - resto)
            resto = max(0, resto - len(lista))
    if omitidos:
        out["cambios_omitidos"] = omitidos
    return out


def recorta(pl: dict, previas: dict | None = None, primeras: dict | None = None) -> dict | None:
    """Una entrada del journal recortada a lo observado. previas/primeras (por raíz) los lleva extrae(): la vista
    anterior de la misma raíz da los «cambios» y la primera, los nombres que cambiaron desde entonces."""
    op = pl.get("operation") or ""
    if pl.get("phase") != "completed" or op.startswith("memory."):
        return None
    r = pl.get("response") or {}
    e: dict = {"hora": pl.get("timestampUtc"), "op": op, "estado": r.get("status"), "mision": pl.get("missionId")}
    if r.get("errorCode"):
        e["error"] = r.get("errorCode")
    res = r.get("result")
    if not isinstance(res, dict):
        return e
    if op == "input.visible.controls":
        w = res.get("window") or {}
        v = {k: _corta(w.get(k)) for k in ("title", "process", "processId", "hwnd", "root", "foreground") if k in w}
        foco = _foco(w)
        if isinstance(w.get("focused"), dict):
            v["focused"] = foco or {}
        e["ventana"] = v
        ctl = [c for c in res.get("controls") or [] if isinstance(c, dict)]
        e["controles"] = len(ctl)
        raiz = w.get("root") or w.get("hwnd")
        primera = primeras.get(raiz) if primeras is not None and raiz else None
        # Destacados por informatividad (estado o valor vivos, dato en el Name, off/readonly), en orden UIA dentro de
        # cada rango: en Paint los 29 interruptores «off» ya no tapan «Color 1: Verde» (banco r23, y12).
        rangos = [(r, n, c) for n, c in enumerate(ctl) if (r := _rango(c, primera)) is not None]
        rangos.sort(key=lambda t: (t[0], t[1]))
        e["destacados"] = [_ficha(c) for _, _, c in rangos[:MAX_DESTACADOS]]
        e["destacados_omitidos"] = max(0, len(rangos) - MAX_DESTACADOS)
        if previas is not None and raiz:
            if raiz in previas:
                antes_ctl, antes_foco = previas[raiz]
                e["cambios"] = cambios(antes_ctl, ctl, antes_foco, foco)
            previas[raiz] = (ctl, foco)
        if primeras is not None and raiz and raiz not in primeras:
            primeras[raiz] = {_clave(c): str(c.get("name") or "") for c in ctl}
        # Ventana sin árbol (CEF, SDL: un solo control o sólo el marco): el texto OCR de la banda superior y sus
        # marcas de tinta son la única prueba de qué página o pestaña muestra (banco r23, x10: «JUEGOS (1/1416)»).
        if len(ctl) <= 1 or res.get("frameOnly"):
            texto = res.get("text") if isinstance(res.get("text"), dict) else {}
            arriba = {z: [_corta(str(x)) for x in texto[z][:MAX_LINEAS_ZONA]]
                      for z in _ZONAS_ARRIBA if isinstance(texto.get(z), list) and texto[z]}
            if arriba:
                e["texto_arriba"] = arriba
            marcas = [{k: _corta(m.get(k)) for k in ("text", "zone", "ink") if m.get(k) not in (None, "")}
                      for m in res.get("textMarks") or [] if isinstance(m, dict) and m.get("zone") in _ZONAS_ARRIBA]
            if marcas:
                e["marcas_arriba"] = marcas[:MAX_MARCAS]
        if res.get("error"):
            e["error_lectura"] = _corta(res.get("error"))
        return e
    e["observado"] = _escalares(res)
    for k in ("window", "target", "reachedState"):
        if isinstance(res.get(k), dict):
            e["observado"][k] = _escalares(res[k])
    return e


def _hwnd_de(e: dict) -> list[int]:
    hs = []
    v = e.get("ventana") or {}
    for k in ("root", "hwnd"):
        if isinstance(v.get(k), int) and v[k]:
            hs.append(v[k])
            break
    o = e.get("observado") or {}
    for k in ("windowHandle", "window", "hwnd", "root"):
        if isinstance(o.get(k), int) and o[k]:
            hs.append(o[k])
    return hs


def extrae(ev: Path, journal: Path) -> dict:
    iv = intervalo(ev)
    out: dict = {"journal": str(journal), "entradas": [], "tocadas": []}
    if iv is None:
        out["error"] = "sin events.jsonl"
        return out
    ini, fin = iv
    out["desde_ms"], out["hasta_ms"] = ini, fin
    crudas: list[bytes] = []
    for seg in segmentos(journal):
        lineas, llego = _lineas_desde(seg, ini)
        crudas = lineas + crudas
        if llego:
            break
    entradas = []
    previas: dict = {}
    primeras: dict = {}
    for linea in crudas:
        try:
            pl = json.loads(linea.decode("utf-8", "replace")).get("payload") or {}
        except (ValueError, AttributeError):
            continue
        t = ms_de_iso(str(pl.get("timestampUtc") or ""))
        if t is None or t > fin:
            continue
        e = recorta(pl, previas, primeras)
        if e is not None:
            entradas.append(e)
    out["total"] = len(entradas)
    out["entradas"] = entradas[-MAX_ENTRADAS:]
    tocadas: list[int] = []
    for e in reversed(entradas):
        for h in _hwnd_de(e):
            if h not in tocadas:
                tocadas.append(h)
    out["tocadas"] = tocadas
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ev")
    ap.add_argument("--journal", default=os.environ.get("CU_JOURNAL") or os.path.expandvars(
        r"%LOCALAPPDATA%\BAXY\cu-universal-perfil\journal\missions.jsonl"))
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    ev = Path(a.ev)
    d = extrae(ev, Path(a.journal))
    salida = Path(a.salida) if a.salida else ev / "journal-caso.json"
    salida.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"journal_caso: {len(d['entradas'])} entradas, tocadas={d['tocadas'][:5]} -> {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
