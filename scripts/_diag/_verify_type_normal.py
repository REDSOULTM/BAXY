"""Verificación FÍSICA en el escritorio NORMAL (tu insight): el agente tipea en
Notepad con su path REAL (gui_type_into: enfoca primero, se niega si no puede,
texto SIN Enter -> riesgo bajo), e inmediatamente saco un screenshot (el escritorio
normal SÍ captura bien) para LEERLO y confirmar. Cierra el Notepad de prueba al final."""
from __future__ import annotations
import sys, time, tempfile, subprocess
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

TEXT = "HOLA MUNDO desde Gemma4 - prueba 12345"
SHOT = Path("scripts/_diag/_type_proof.png").resolve()
proc = None
new_pid = None
try:
    import win32gui, win32process
    # PIDs de Notepad TUYOS antes (preservar)
    before = set()
    def cb0(h,_):
        t=win32gui.GetWindowText(h)
        if "Bloc de notas" in t or "Notepad" in t:
            before.add(win32process.GetWindowThreadProcessId(h)[1])
        return True
    win32gui.EnumWindows(cb0, None)

    print("[1] abriendo Notepad de prueba...", flush=True)
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(2.5)

    from gemma4_agent.memory_pkg.memory import MemoryStore
    from gemma4_agent.memory_pkg.state import AgentState
    from gemma4_agent.tools_pkg.tools import ToolRegistry
    tmp = Path(tempfile.mkdtemp())
    reg = ToolRegistry(MemoryStore(tmp/"m.json"), tmp/"c", state=AgentState(tmp/"d"/"s.json"))

    print("[2] el agente tipea (gui_type_into, path REAL)...", flush=True)
    r = reg.gui_type_into({"text": TEXT, "window": "Bloc de notas"})
    print(f"    -> ok={r.get('ok')} verified={r.get('verified')} method={r.get('method')} "
          f"err={str(r.get('error'))[:60]}", flush=True)
    time.sleep(0.6)

    print("[3] screenshot del escritorio normal...", flush=True)
    try:
        from PIL import ImageGrab
        ImageGrab.grab().save(SHOT)
        print(f"    -> {SHOT}", flush=True)
    except Exception as e:
        print(f"    screenshot err: {e}", flush=True)

    # leer el título del Notepad (Win11 pone la 1ra línea ahí) como verificación extra
    titles=[]
    def cb1(h,_):
        t=win32gui.GetWindowText(h)
        if "Bloc de notas" in t or "Notepad" in t: titles.append(t)
        return True
    win32gui.EnumWindows(cb1, None)
    print(f"[4] título(s) Notepad ahora: {titles}", flush=True)
    print(f"    texto en el título? {'98765' in ''.join(titles) or '12345' in ''.join(titles)}", flush=True)
finally:
    print("[5] cerrando el Notepad de prueba (forzado, sin diálogo)...", flush=True)
    try:
        import win32gui, win32process, psutil
        after=set()
        def cb2(h,_):
            t=win32gui.GetWindowText(h)
            if "Bloc de notas" in t or "Notepad" in t:
                after.add(win32process.GetWindowThreadProcessId(h)[1])
            return True
        win32gui.EnumWindows(cb2, None)
        for pid in (after - before):     # solo el/los que YO abrí
            try: psutil.Process(pid).kill(); print(f"    matado pid={pid}", flush=True)
            except Exception as e: print(f"    no maté {pid}: {e}", flush=True)
    except Exception as e:
        print(f"    cleanup err: {e}", flush=True)
    print("[done]", flush=True)
