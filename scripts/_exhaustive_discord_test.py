"""Discord/Electron en CONDICIONES REALES: el usuario está usando otra app (foco
en otra ventana), como cuando juega y le pide algo a Gemma4. Mide gui_click_button
sobre Discord SIN que Discord tenga el foreground. Verifica que el camino in-proc
(foreground-safe) encuentra+clickea el control y NO roba el foco (focus_stolen=False).

Requiere Discord abierto. Verificación por estado: ok del click + element name +
focus_stolen. (No verificamos efecto visual porque depende del estado de Discord.)
"""
import sys, time, json, tempfile, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gemma4_agent.tools import ToolRegistry
from gemma4_agent.memory import MemoryStore
from gemma4_agent import gui_safety
import win32gui

tmp = Path(tempfile.mkdtemp())
reg = ToolRegistry(memory=MemoryStore(tmp/"m.json"), captures_dir=tmp)

def discord_open():
    code='import uiautomation as a;print("Y" if any("Discord" in (w.Name or "") for w in a.GetRootControl().GetChildren()) else "N")'
    return subprocess.run(["python","-c",code],capture_output=True,text=True,timeout=15).stdout.strip()=="Y"

if not discord_open():
    print("Discord NO está abierto -> SKIP"); sys.exit(0)

# Asegurar que el FOCO está en OTRA app (simula al usuario activo en VS Code/juego).
# Enfocamos esta consola/cualquier ventana que NO sea Discord como baseline.
def fg_title():
    return win32gui.GetWindowText(win32gui.GetForegroundWindow()) or ""

# Labels VERIFICADOS presentes en Discord ES con el árbol caliente (2026-05-25).
LABELS = ["Buscar", "Bandeja de entrada", "Mensajes directos", "Mensajes fijados",
          "Buscar", "Apps", "Bandeja de entrada", "Buscar", "Mensajes directos", "Apps"]

results=[]; print("=== DISCORD click_button x10 (usuario activo en otra app) ===",flush=True)
for i, label in enumerate(LABELS):
    gui_safety.reset_action_budget()
    gui_safety.set_turn_goal(f"en discord {label}")
    fg_before = fg_title()
    r = reg.gui_click_button({"label": label, "window": "Discord"})
    fg_after = fg_title()
    el = (r.get("element") or r.get("clicked_element") or {}).get("name","") if r else ""
    stole = r.get("focus_stolen")
    discord_grabbed = "Discord" in fg_after and "Discord" not in fg_before
    results.append({"label":label,"ok":r.get("ok"),"grounding":r.get("grounding"),
                    "element":(el or "")[:40],"focus_stolen":stole,
                    "fg_before":fg_before[:25],"fg_after":fg_after[:25]})
    print(f"  [{i}] {label!r}: ok={r.get('ok')} g={r.get('grounding')} "
          f"stole_focus={stole} fg:{fg_before[:18]!r}->{fg_after[:18]!r}",flush=True)
    time.sleep(0.3)

out=ROOT/"scripts"/"gui_eval"/"_exhaustive_discord_results.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
n=sum(1 for r in results if r["ok"])
nofocus=sum(1 for r in results if r["ok"] and not r.get("focus_stolen"))
print(f"\n>> Discord click_button: {n}/{len(results)} ok; {nofocus}/{n} SIN robar foco",flush=True)
print("WROTE",out,flush=True)
