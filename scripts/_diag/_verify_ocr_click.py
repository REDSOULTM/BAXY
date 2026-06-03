"""Verificación FÍSICA del path OCR->click, UIA-GUARDED (máxima seguridad).

Trae Calc al frente (AttachThreadInput + restaurar de maximizado para que NO tape
VS Code), y para cada dígito: OCR localiza candidatos dentro de Calc; antes de
clickear, le pregunta al SO (ControlFromPoint) si el topmost EN ESA COORD es el
botón de Calc (AutomationId num{d}Button). Clickea SOLO si el SO lo confirma — así
es imposible pegarle a VS Code (si devolviera otra cosa, saltea). Verifica el efecto
leyendo el display por UIA + screenshot. Click por ctypes mouse_event (no SendInput).
"""
from __future__ import annotations
import sys, time, subprocess, ctypes
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
import win32gui, win32process, win32con
from PIL import ImageGrab
import uiautomation as auto
from gemma4_agent.tools_pkg.ops_tools import ocr_find_text

OUT = Path("scripts/_diag/_ocr_click"); OUT.mkdir(parents=True, exist_ok=True)
u32 = ctypes.windll.user32

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

def activate(hwnd):
    """Trae hwnd al frente de forma robusta (AttachThreadInput sortea el foreground
    lock) y lo RESTAURA de maximizado para que no tape VS Code."""
    try:
        fg = u32.GetForegroundWindow()
        t_fg = win32process.GetWindowThreadProcessId(fg)[0]
        t_tg = win32process.GetWindowThreadProcessId(hwnd)[0]
        if t_fg != t_tg: u32.AttachThreadInput(t_fg, t_tg, True)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)  # botones grandes = OCR-friendly
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        if t_fg != t_tg: u32.AttachThreadInput(t_fg, t_tg, False)
    except Exception as e:
        print(f"  (activate err {type(e).__name__}: {e})", flush=True)
    time.sleep(0.6)

# usar Calc existente o abrir una
calc = find_windows(["Calcul"])
if not calc:
    subprocess.Popen("start calc", shell=True)
    for _ in range(20):
        time.sleep(0.4); calc = find_windows(["Calcul"])
        if calc: break
if not calc:
    print("[ABORT] no hay Calculadora"); sys.exit(1)
hcalc, _r0, calc_title = calc[0]
activate(hcalc)
calc_rect = win32gui.GetWindowRect(hcalc)
print(f"[calc] '{calc_title}' rect={calc_rect}  foreground={u32.GetForegroundWindow()==hcalc}", flush=True)
try: auto.SetGlobalSearchTimeout(2.0)
except Exception: pass

def read_display():
    try:
        r = auto.TextControl(AutomationId="CalculatorResults", searchDepth=14)
        if r.Exists(0.6, 0): return r.Name
    except Exception as e:
        return f"(uia err {type(e).__name__})"
    return None

def uia_guarded_click(digit):
    activate(hcalc)
    rect = win32gui.GetWindowRect(hcalc)
    p = (OUT / f"click_{digit}.png").resolve()
    ImageGrab.grab().convert("RGB").save(str(p))
    f = ocr_find_text(p, digit)
    cands = [m for m in (f.get("matches", []) if f.get("ok") else [])
             if inside((m["center_x"], m["center_y"]), rect)]
    seen = []
    for m in cands:
        sx, sy = int(m["center_x"]), int(m["center_y"])
        try:
            ctrl = auto.ControlFromPoint(sx, sy)
            aid = str(ctrl.AutomationId) if ctrl else ""
        except Exception:
            aid = ""
        seen.append((sx, sy, aid))
        if f"num{digit}button" in aid.lower():
            u32.SetCursorPos(sx, sy)
            u32.mouse_event(0x0002, 0, 0, 0, 0)  # left down
            u32.mouse_event(0x0004, 0, 0, 0, 0)  # left up
            time.sleep(0.45)
            return (sx, sy), aid, seen
    return None, "ningún candidato cayó sobre el botón", seen

print(f"[display inicial] {read_display()!r}", flush=True)
print("\n[click físico UIA-guarded]", flush=True)
for d in ["7", "9"]:
    pt, info, seen = uia_guarded_click(d)
    print(f"  '{d}': click={pt}  ({info})  candidatos_vistos={seen[:4]}", flush=True)
    print(f"       display -> {read_display()!r}", flush=True)

time.sleep(0.4)
ImageGrab.grab().convert("RGB").save(str((OUT / "click_final.png").resolve()))
print(f"\n[display final] {read_display()!r}  (esperado: contiene 79)", flush=True)

# cleanup: cerrar la Calc de prueba
try:
    pid = win32process.GetWindowThreadProcessId(hcalc)[1]
    win32gui.PostMessage(hcalc, win32con.WM_CLOSE, 0, 0)
    time.sleep(0.6)
    if find_windows(["Calcul"]):
        k = ctypes.windll.kernel32; hp = k.OpenProcess(0x0001, False, pid)
        if hp: k.TerminateProcess(hp, 0); k.CloseHandle(hp)
    print("[cleanup] Calc de prueba cerrada", flush=True)
except Exception as e:
    print(f"[cleanup] no pude cerrar Calc: {e}", flush=True)
print("[done]", flush=True)
