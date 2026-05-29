"""Mata procesos python huerfanos de scripts/_boot_server_for_eval.py.

Estos quedan vivos en su loop `while True: sleep(30)` reteniendo los handles
de logs/llama-server.{err,out}.log (abiertos en modo append por el manager y
heredados) aunque su server hijo haya muerto. Eso BLOQUEA la rotacion del log
y deja basura entre sesiones de eval.

Usa psutil porque Stop-Process / taskkill estan bloqueados por el harness.
No toca la app de escritorio del usuario (matchea solo el script de eval).
"""
import os
import sys

import psutil

SELF = os.getpid()
PATTERN = sys.argv[1] if len(sys.argv) > 1 else "_boot_server_for_eval"

killed = []
for p in psutil.process_iter(["pid", "name", "cmdline"]):
    if p.info["pid"] == SELF:
        continue
    try:
        cl = p.info.get("cmdline") or []
        if any(PATTERN in str(a) for a in cl):
            p.terminate()
            try:
                p.wait(timeout=5)
            except psutil.TimeoutExpired:
                p.kill()
            killed.append(p.info["pid"])
    except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
        print(f"skip pid={p.info.get('pid')}: {exc}")

print(f"killed[{PATTERN}]:", sorted(killed) if killed else "(none)")
