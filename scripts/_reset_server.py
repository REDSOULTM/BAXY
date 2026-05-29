"""Reset completo del server de eval en UN solo proceso.

Mata: (a) python de _boot_server_for_eval / _stress_v22 / _verify_a2, y
(b) cualquier llama-server.exe (router + child, ambos se llaman igual; matar
por nombre los agarra a los dos y evita orphans del child en puerto dinamico).

Un solo proceso psutil porque al terminar otros procesos el harness corta la
ejecucion (exit 15) -> si hicieramos kills en comandos separados solo correria
el primero. Stop-Process/taskkill estan bloqueados por el harness.

NO toca la app de escritorio del usuario (no esta corriendo en sesiones de eval;
matchea solo el server de eval por nombre llama-server.exe + scripts de eval).
"""
import os

import psutil

SELF = os.getpid()
PY_PATTERNS = ("_boot_server_for_eval", "_stress_v22", "_verify_a2")

killed = []
for p in psutil.process_iter(["pid", "name", "cmdline"]):
    if p.info["pid"] == SELF:
        continue
    try:
        name = (p.info.get("name") or "").lower()
        cl = " ".join(p.info.get("cmdline") or [])
        hit = name == "llama-server.exe" or any(pat in cl for pat in PY_PATTERNS)
        if not hit:
            continue
        p.terminate()
        try:
            p.wait(timeout=5)
        except psutil.TimeoutExpired:
            p.kill()
        killed.append((p.info["pid"], name or "python"))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

print("reset killed:", sorted(killed) if killed else "(none)")
