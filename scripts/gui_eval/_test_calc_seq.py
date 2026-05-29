import os, sys, time, subprocess, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
sys.path.insert(0, os.path.dirname(__file__))
import gemma4_agent.agent_core.agent as A
from eval_set import _reset_calc_clean, _calc_display_value
ag=A.Gemma4Agent(); tb=ag.tools
_reset_calc_clean()
# secuencia 2 + 2 = clickeando botones por NOMBRE (UIA names de la calc ES)
seq=["Dos","Más","Dos","Es igual a"]
for label in seq:
    r=tb.gui_click_button({"label":label,"window":"Calculadora"})
    time.sleep(0.35)
print("display tras 2+2= :", _calc_display_value())
