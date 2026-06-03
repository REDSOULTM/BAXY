"""Verificación END-TO-END en el escritorio normal: el comando del usuario
"escribí X en el bloc de notas" pasa por TODO el pipeline REAL (routing app-action
-> plan determinista focus_app+type -> ejecución física), y saco screenshot para
leerlo. Sin mocks. Texto sin Enter -> riesgo bajo. Cierra el Notepad de prueba."""
from __future__ import annotations
import os, sys, time, subprocess
from pathlib import Path
sys.path.insert(0, ".")
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

CMD = "escribí hola mundo verificado 24680 en el bloc de notas"
SHOT = Path("scripts/_diag/_e2e_proof.png").resolve()
before = set()
try:
    import win32gui, win32process
    def cb0(h,_):
        t=win32gui.GetWindowText(h)
        if "Bloc de notas" in t or "Notepad" in t:
            before.add(win32process.GetWindowThreadProcessId(h)[1])
        return True
    win32gui.EnumWindows(cb0, None)

    print("[1] abriendo Notepad...", flush=True)
    subprocess.Popen(["notepad.exe"]); time.sleep(2.5)

    print(f"[2] run_content REAL: {CMD!r}", flush=True)
    from gemma4_agent.agent_core.agent import Gemma4Agent
    agent = Gemma4Agent()
    reply = agent.run_content(CMD)
    print(f"    reply = {(getattr(reply,'content','') or '')[:90]!r}", flush=True)
    time.sleep(0.8)

    print("[3] screenshot...", flush=True)
    from PIL import ImageGrab
    ImageGrab.grab().save(SHOT)
    print(f"    -> {SHOT}", flush=True)
finally:
    print("[4] cerrando Notepad de prueba...", flush=True)
    try:
        import win32gui, win32process, psutil
        after=set()
        def cb2(h,_):
            t=win32gui.GetWindowText(h)
            if "Bloc de notas" in t or "Notepad" in t:
                after.add(win32process.GetWindowThreadProcessId(h)[1])
            return True
        win32gui.EnumWindows(cb2, None)
        for pid in after:   # vos NO tenías Notepad -> cierro todos los de prueba
            try: psutil.Process(pid).kill()
            except Exception: pass
    except Exception as e:
        print(f"    cleanup err: {e}", flush=True)
    print("[done]", flush=True)
