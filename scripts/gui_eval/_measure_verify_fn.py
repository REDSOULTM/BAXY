"""¿Tiene la verificación actual (dHash + UIA-text-confirm) falsos-negativos en
texto chico? R3 (WinEvents) solo vale si SÍ. Medimos: tras type_into de texto
corto, ¿state_changed reporta True correctamente?"""
import os, sys, time, subprocess
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
sys.path.insert(0, os.path.dirname(__file__))
import gemma4_agent.agent_core.agent as A
from eval_set import _kill_process, _clear_notepad_session, _launch_detached, uia_window_has_text
ag=A.Gemma4Agent(); tb=ag.tools
cases=["a","ok","12","x","si"]  # texto MUY corto (el peor caso para dHash)
fn=0; n=0
for txt in cases:
    _kill_process("notepad.exe"); _clear_notepad_session(); _launch_detached("notepad.exe"); time.sleep(1.0)
    r=tb.gui_type_into({"text":txt,"window":"bloc de notas"})
    time.sleep(0.4)
    landed = bool(uia_window_has_text("notas", txt))  # ground truth: ¿entró?
    sc = r.get("state_changed")  # lo que reportó la verificación
    n+=1
    is_fn = landed and (sc is False)  # entró pero verify dijo que no
    if is_fn: fn+=1
    print(f"txt={txt!r}: landed={landed} state_changed={sc} uia_confirmed={r.get('uia_confirmed')} FALSO_NEG={is_fn}")
print(f"\nfalsos-negativos de verify en texto chico: {fn}/{n}")
print("R3 (WinEvents) justificado solo si fn>0" if fn>0 else "R3 NO necesario: la verificación UIA-text ya cubre texto chico")
