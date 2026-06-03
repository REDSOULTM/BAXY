"""Verificación READ-ONLY del path OCR->click SIN input sintético (tus deny rules
lo permiten): cross-check de la coordenada OCR contra el hit-test del SO (UIA
ControlFromPoint). Si en la coord que devuelve ocr_find_text para "7" el SO
responde el botón "7" (AutomationId num7Button), la coordenada queda PROBADA
sin clickear nada.

NO hace mouse_event, NO cierra procesos. Abre Calc (descartable) y la deja abierta
(no puedo cerrarla: WM_CLOSE/TerminateProcess están en tus deny rules).
"""
from __future__ import annotations
import sys, time, subprocess
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import win32gui
from PIL import ImageGrab
import uiautomation as auto
from gemma4_agent.tools_pkg.ops_tools import ocr_find_text

OUT = Path("scripts/_diag/_ocr_click"); OUT.mkdir(parents=True, exist_ok=True)

def find_windows(subs):
    res = []
    def cb(h, _):
        if win32gui.IsWindowVisible(h):
            t = win32gui.GetWindowText(h)
            if t and any(s.lower() in t.lower() for s in subs):
                res.append((h, win32gui.GetWindowRect(h), t))
        return True
    win32gui.EnumWindows(cb, None)
    return res

def inside(pt, rect):
    x, y = pt; l, t, r, b = rect
    return l <= x <= r and t <= y <= b

before = {h for h, _, _ in find_windows(["Calcul"])}
subprocess.Popen("start calc", shell=True)
hcalc = None
for _ in range(20):
    time.sleep(0.4)
    new = [(h, r, t) for h, r, t in find_windows(["Calcul"]) if h not in before]
    if new:
        hcalc, calc_rect, calc_title = new[0]; break
if not hcalc:
    print("[ABORT] no encontré la Calculadora"); sys.exit(1)
print(f"[calc] '{calc_title}' rect={calc_rect}", flush=True)
time.sleep(1.0)

shot = ImageGrab.grab().convert("RGB")
sp = (OUT / "uia_shot.png").resolve(); shot.save(str(sp))

try: auto.SetGlobalSearchTimeout(2)
except Exception: pass

print("\n[cross-check ESTRICTO: coord del OCR -> el SO confirma num{d}Button ahí]", flush=True)
ok = tot = 0
for d in ["7", "8", "9", "5", "3"]:
    f = ocr_find_text(sp, d)
    in_calc = [m for m in (f.get("matches", []) if f.get("ok") else [])
               if inside((m["center_x"], m["center_y"]), calc_rect)]
    if not in_calc:
        print(f"  '{d}': el OCR no lo hallo dentro de Calc", flush=True); continue
    tot += 1
    hit = None; last = None
    for m in in_calc:
        sx, sy = int(m["center_x"]), int(m["center_y"])
        try:
            ctrl = auto.ControlFromPoint(sx, sy)
            name = ctrl.Name if ctrl else None
            aid = str(ctrl.AutomationId) if ctrl else ""
        except Exception as e:
            last = f"UIA error {type(e).__name__}"; continue
        last = f"({sx},{sy}) name={name!r} autoId={aid!r}"
        # match ESTRICTO: el botón de dígito de Calc tiene AutomationId num{d}Button
        if f"num{d}button" in aid.lower():
            hit = (sx, sy, name, aid); break
    if hit:
        ok += 1
        print(f"  '{d}'  OCR=({hit[0]},{hit[1]})  ->  boton {hit[3]} ('{hit[2]}')   OK MATCH", flush=True)
    else:
        print(f"  '{d}'  ningun match OCR cayo sobre num{d}Button. ultimo visto: {last}", flush=True)

print(f"\n[resumen] {ok}/{tot} coords del OCR caen EXACTO sobre el boton de su digito (num{{d}}Button, hit-test del SO).", flush=True)
print("[nota] dejo la Calc de prueba ABIERTA -- cerrala vos (mis deny rules bloquean cerrarla).", flush=True)
print("[done]", flush=True)
