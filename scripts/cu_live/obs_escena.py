"""Quita de una colección de escenas de OBS la escena de prueba de un caso (estado obs_sin_escena, arnés en vivo).

v3-51 («agrega una escena nueva que se llame Pruebas») no puede distinguir nada si la escena ya existe: en la pasada r9
seguía ahí desde la r5. Esto la quita con OBS cerrado (OBS reescribe el archivo al salir), y sólo:
  - la escena (id «scene») cuyo nombre es EXACTAMENTE el pedido, sin nada dentro (una escena vacía es la que crea el
    caso; una con fuentes podría ser del dueño: no se toca, «escena_con_contenido»);
  - si ninguna otra escena o grupo la usa como fuente («escena_en_uso»), y si queda otra escena a la que pasar la
    escena actual («unica_escena»).
Copia antes el archivo byte a byte en --respaldo. Imprime una línea JSON: {resultado, ...}.

Uso: py -3.12 -I obs_escena.py --archivo <coleccion.json> --nombre Pruebas --respaldo <carpeta> [--seco]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time


def quitar_escena(doc: dict, nombre: str) -> tuple[str, dict]:
    """(resultado, doc nuevo): 'quitada' | 'no_estaba' | 'escena_con_contenido' | 'escena_en_uso' | 'unica_escena'."""
    fuentes = list(doc.get("sources") or [])
    escenas = [s for s in fuentes if s.get("id") == "scene" and s.get("name") == nombre]
    if not escenas:
        return "no_estaba", doc
    if len(escenas) > 1 or any(((s.get("settings") or {}).get("items") or []) for s in escenas):
        return "escena_con_contenido", doc
    uuid = escenas[0].get("uuid")
    for s in fuentes + list(doc.get("groups") or []):
        if s is escenas[0]:
            continue
        for i in (s.get("settings") or {}).get("items") or []:
            if i.get("name") == nombre or (uuid and i.get("source_uuid") == uuid):
                return "escena_en_uso", doc
    orden = [o for o in doc.get("scene_order") or [] if o.get("name") != nombre]
    otras = [o.get("name") for o in orden if o.get("name")]
    if not otras:
        return "unica_escena", doc
    nuevo = dict(doc)
    nuevo["sources"] = [s for s in fuentes if s is not escenas[0]]
    nuevo["scene_order"] = orden
    for k in ("current_scene", "current_program_scene"):
        if nuevo.get(k) == nombre:
            nuevo[k] = otras[0]
    return "quitada", nuevo


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archivo", required=True)
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--respaldo", required=True)
    ap.add_argument("--seco", action="store_true")
    a = ap.parse_args()
    with open(a.archivo, encoding="utf-8") as f:
        doc = json.load(f)
    r, nuevo = quitar_escena(doc, a.nombre)
    out = {"resultado": r}
    if r == "quitada" and not a.seco:
        os.makedirs(a.respaldo, exist_ok=True)
        dst = os.path.join(a.respaldo, f"{os.path.basename(a.archivo)}-{time.strftime('%Y%m%d-%H%M%S')}")
        shutil.copyfile(a.archivo, dst)
        tmp = a.archivo + ".baxy-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(nuevo, f, ensure_ascii=False, indent=4)
        os.replace(tmp, a.archivo)
        with open(a.archivo, encoding="utf-8") as f:
            r2, _ = quitar_escena(json.load(f), a.nombre)
        out.update({"respaldo": dst, "releido": r2})
    print(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
