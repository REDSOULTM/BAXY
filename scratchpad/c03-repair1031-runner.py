"""Deriva el runner de REPAIR1031 del de REPAIR1030: mismos conteos y case_id, otro sello.

El subconjunto y los controles son idénticos —es la misma reparación medida otra vez con la instrucción
arreglada—, así que lo único que cambia son las rutas, el sello del panel y el SHA del registro. Falla
si algún ancla no aparece, para que ninguna guarda desaparezca en un reemplazo silencioso.
"""
from __future__ import annotations

import hashlib
import pathlib

BASE = pathlib.Path.home() / "AppData/Local/BAXY"
SOURCE = BASE / "C03-repair1030-proposal/runner.py"
TARGET = BASE / "C03-repair1031-proposal/runner.py"

PAIRS = [
    ("repair1030", "repair1031"),
    ("REPAIR1030", "REPAIR1031"),
    ("b206137d30efc43be04f2f63aece0a74b0ce1387acfb798bd15f887e8d8a057b",
     "a84fc0b050881939f9d6f1565065e80c48a8e34a24c0816fc79449f8fa970251"),
    ("3a5593f9948eb8ab260ce015750d4d801b0b2e288bfc03e0889ee62c4eb73f73",
     "1d8bc7f935243f5fd8e2e35397b517da98416133a37125a1222873825bf9f879"),
]


def main() -> int:
    text = SOURCE.read_text(encoding="utf-8")
    for old, new in PAIRS:
        if old not in text:
            raise SystemExit(f"missing anchor: {old}")
        text = text.replace(old, new)
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"runner: {TARGET}")
    print(f"sha256: {hashlib.sha256(TARGET.read_bytes()).hexdigest()}")
    print(f"lines: {len(text.splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
