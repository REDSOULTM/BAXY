"""Medir el desglose de latencia de un turno GUI: ¿cuánto es LLM vs UIA vs OCR vs
verify? Si el LLM domina, R5 (cache UIA) NO mueve la aguja -> no construir."""
import os, sys, time, subprocess
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
sys.path.insert(0, os.path.dirname(__file__))
import gemma4_agent.agent as A
from eval_set import _reset_calc_clean
ag=A.Gemma4Agent(); tb=ag.tools
# instrumentar: medir tiempo de cada _uia_run y del turno completo
uia_times=[]
real=tb._uia_run
def wrap(args,action):
    t=time.time(); r=real(args,action); uia_times.append((action,time.time()-t)); return r
tb._uia_run=wrap
for utt in ["hacé clic en el botón nueve","clic en el botón cinco"]:
    _reset_calc_clean()
    uia_times.clear()
    t0=time.time(); res=ag.run_text(utt); turn=time.time()-t0
    uia_total=sum(d for _,d in uia_times)
    print(f"utt={utt!r}: turno={turn:.2f}s  uia_total={uia_total:.2f}s ({len(uia_times)} calls)  resto(LLM+otros)={turn-uia_total:.2f}s")
    for a,d in uia_times: print(f"    uia.{a}: {d:.2f}s")
    ag.clear()
