import os, sys, time, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
sys.path.insert(0, os.path.dirname(__file__))
import gemma4_agent.agent as A
from eval_set import _reset_calc_clean, _calc_display_value
ag=A.Gemma4Agent(); tb=ag.tools
_reset_calc_clean()
# usar el macro YA EXISTENTE gui_type_into para teclear la expresión + Enter
r=tb.gui_type_into({"text":"2+2","window":"Calculadora"})
time.sleep(0.3); tb.gui_keypress({"keys":"ENTER"}); time.sleep(0.5)
print("type_into '2+2'+Enter -> display:", _calc_display_value(), "| ok=", r.get("ok"))
