"""Re-run FINAL de los 6162 casos con TODOS los fixes de la cacería activos.

Corre las 6 tandas SECUENCIALMENTE (un solo server/GPU) llamando al harness
_diag_hunt_tanda.py con GEMMA4_HUNT_PREFIX=_rerun_tanda_ para NO pisar los hunts
originales pre-fix. Cada tanda arranca su propio server compartido (el harness lo
hace) y lo libera al terminar.

Objetivo (pedido del user): confirmar que con los fixes los 6162 corren limpios —
en particular media_fab≈0 y destr≈0 tras los guards + inline-repair.

Uso: python scripts/_diag/_rerun_all_6162.py
Salida: scripts/_diag/_rerun_tanda_{0,1000,2000,3000,4000,5000}.jsonl
Tiempo estimado: ~3.5 s/caso × 6162 ≈ 6 h. Background.
"""
from __future__ import annotations
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HARNESS = ROOT / "scripts" / "_diag" / "_diag_hunt_tanda.py"
# (offset, limit) — la última tanda toma la cola completa (1162 para llegar a 6162).
TANDAS = [(0, 1000), (1000, 1000), (2000, 1000), (3000, 1000), (4000, 1000), (5000, 1200)]

env = dict(os.environ)
env["GEMMA4_HUNT_PREFIX"] = "_rerun_tanda_"

t0 = time.time()
print(f"[rerun] FINAL 6162 con fixes activos -> prefijo _rerun_tanda_", flush=True)
for i, (off, lim) in enumerate(TANDAS):
    print(f"[rerun] tanda {i+1}/6: offset={off} limit={lim} ...", flush=True)
    tt = time.time()
    r = subprocess.run([sys.executable, str(HARNESS), str(off), str(lim)],
                       cwd=str(ROOT), env=env)
    el = (time.time() - tt) / 60
    print(f"[rerun] tanda {i+1}/6 DONE rc={r.returncode} en {el:.1f}min", flush=True)
    if r.returncode != 0:
        print(f"[rerun] ABORT: tanda {i+1} falló (rc={r.returncode})", flush=True)
        sys.exit(1)

print(f"[rerun] COMPLETO: 6162 casos en {(time.time()-t0)/60:.1f}min", flush=True)
