import os, sys, time
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
sys.path.insert(0, os.path.dirname(__file__))
from eval_set import missions_for_tier
import gemma4_agent.agent_core.agent as A
ag=A.Gemma4Agent()
ms=[m for m in missions_for_tier(None) if 't3_cef' in m.id]
p=0
for m in ms:
    m.reset()
    if not m.precheck(): print(f"{m.id} SKIP precheck (fixture no abrió)"); continue
    res=ag.run_text(m.utterance)
    ev=[(getattr(e,"name",None),(getattr(e,"args",{}) or {}).get("action"),(getattr(e,"result",{}) or {}).get("grounding")) for e in (getattr(res,"tool_events",[]) or [])]
    dl=time.time()+6; v={}; time.sleep(0.6)
    while True:
        v=m.goal_verifier()
        if v.get("pass") is True or time.time()>=dl: break
        time.sleep(0.6)
    ok=v.get("pass"); p+=1 if ok else 0
    print(f"{m.id:20} PASS={ok} tools={ev} | {v.get('evidence')}")
    ag.clear()
print(f"\nCEF/OCR cascade SR: {p}/{len(ms)}")
