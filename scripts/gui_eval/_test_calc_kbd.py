import os, sys, time, subprocess, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
sys.path.insert(0, os.path.dirname(__file__))
import gemma4_agent.agent_core.agent as A
from eval_set import _reset_calc_clean, _calc_display_value
ag=A.Gemma4Agent(); tb=ag.tools
def calc(expr_keys, label):
    _reset_calc_clean()
    tb.window_control("focus","Calculadora"); time.sleep(0.5)
    # teclear la expresión carácter por carácter via gui_type (SendKeys)
    tb.gui_type({"text":expr_keys}); time.sleep(0.3)
    tb.gui_keypress({"keys":"ENTER"}); time.sleep(0.5)
    print(f"{label}: '{expr_keys}' -> {_calc_display_value()}")
calc("2+2","suma")
calc("15*3","mult")
calc("100-37","resta")
