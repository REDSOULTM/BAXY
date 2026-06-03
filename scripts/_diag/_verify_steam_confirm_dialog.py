"""VERIFY (CLAUDE.md §3.5) del auto-confirm del diálogo de Steam, en DOS modos:

  dry   (default): abre el diálogo real, ejecuta TODA la maquinaria de
        _steam_confirm_install_dialog (find dialog -> match botón install por
        embeddings multilingües -> chequea InvokePattern) PERO **no aprieta
        Instalar** (no arranca la descarga de ~80GB). Para verificar selección
        e invocabilidad sin comprometer GB. Cancela el diálogo al final.

  real  (sys.argv[2]=='real'): ejecuta el método REAL -> aprieta Instalar ->
        ARRANCA LA DESCARGA. Solo correr con OK explícito del usuario.

uso:  python _verify_steam_confirm_dialog.py [appid] [dry|real]
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

APPID = sys.argv[1] if len(sys.argv) > 1 else "782330"  # DOOM Eternal (owned)
MODE = (sys.argv[2] if len(sys.argv) > 2 else "dry").lower()

from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.memory_pkg.memory import MemoryStore
from gemma4_agent.memory_pkg.state import AgentState
import tempfile
td = Path(tempfile.mkdtemp())
reg = ToolRegistry(MemoryStore(td / "m.json"), td / "cap", AgentState(td / "s.json"))

print(f"[diag] steam://install/{APPID} (abre el diálogo)... modo={MODE}", flush=True)
os.startfile(f"steam://install/{APPID}")  # type: ignore[attr-defined]

if MODE == "real":
    print("[diag] MODO REAL: voy a apretar INSTALAR (arranca descarga).", flush=True)
    r = reg._steam_confirm_install_dialog(f"appid {APPID}")
    print("[diag] resultado:", r, flush=True)
    sys.exit(0)

# --- DRY: replicar la lógica del método PERO sin Invoke() final ---
import uiautomation as auto
from gemma4_agent.routing.semantic_router import embed

print("[diag] esperando el diálogo (poll 12s)...", flush=True)
dialog = None; buttons = []
deadline = time.monotonic() + 12.0
while time.monotonic() < deadline:
    for w in auto.GetRootControl().GetChildren():
        try:
            if "SDL" not in (w.ClassName or ""):
                continue
        except Exception:
            continue
        bs = reg._steam_collect_dialog_buttons(w)
        if len(bs) >= 2:
            dialog, buttons = w, bs
            break
    if dialog is not None:
        break
    time.sleep(0.5)

if dialog is None:
    print("[diag] FAIL: no apareció el diálogo de instalación.", flush=True)
    sys.exit(1)

names = [( (el.Name or "").strip(), el) for el in buttons]
names = [(n, el) for n, el in names if n]
print(f"[diag] diálogo encontrado. botones: {[n for n,_ in names]}", flush=True)

qv = embed("install")
scored = sorted(((float(sum(a*b for a,b in zip(qv, embed(n)))), n, el) for n, el in names),
                key=lambda x: -x[0])
top_sim, top_name, top_el = scored[0]
second = scored[1][0] if len(scored) > 1 else 0.0
print(f"[diag] match install -> {top_name!r} sim={top_sim:.3f} margin={top_sim-second:.3f}", flush=True)

# ¿el botón elegido es invocable? (chequeo SIN invocar)
has_invoke = False
try:
    has_invoke = top_el.GetInvokePattern() is not None
except Exception as e:
    print(f"[diag] GetInvokePattern err: {e}", flush=True)

passed = (top_sim >= reg._XLING_SIM_MIN and (top_sim - second) >= reg._XLING_MARGIN
          and has_invoke and top_name.lower() not in ("cancelar", "cancel", "abbrechen"))
print(f"[diag] botón invocable={has_invoke} | seleccion_correcta={passed}", flush=True)
print(f"[diag] {'✓ PASS' if passed else '✗ FAIL'}: el método apretaría {top_name!r} por InvokePattern "
      f"(NO lo apreté: dry-run, no arranca descarga).", flush=True)

# cerrar el diálogo (cancelar por UIA) para no dejarlo abierto.
for n, el in names:
    if n.lower() in ("cancelar", "cancel", "abbrechen"):
        try:
            el.GetInvokePattern().Invoke()
            print("[diag] diálogo cerrado (Cancelar) — NADA instalado.", flush=True)
        except Exception:
            print("[diag] no pude cerrar; cerralo vos.", flush=True)
        break
