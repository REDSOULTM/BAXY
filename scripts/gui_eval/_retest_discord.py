import os, sys, time
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
sys.path.insert(0, os.path.dirname(__file__))
from eval_set import missions_for_tier
import gemma4_agent.agent as A
ag=A.Gemma4Agent()
ms=[m for m in missions_for_tier(3) if 'Discord' in m.id]
import subprocess
for m in ms:
    subprocess.run(["powershell","-NoProfile","-Command","Get-Process Discord,Update -EA SilentlyContinue|Stop-Process -Force -EA SilentlyContinue"],capture_output=True)
    m.reset()
    if not m.precheck(): print(f"{m.id} SKIP"); continue
    time.sleep(0.4)
    res=ag.run_text(m.utterance)
    reply=getattr(res,"content","") or ""
    # poll 20s (tier3)
    dl=time.time()+20; v={}; time.sleep(0.4)
    while True:
        v=m.goal_verifier()
        if v.get("pass") is True or time.time()>=dl: break
        time.sleep(0.6)
    # falso-pass detection (igual que run_eval)
    from run_eval import _agent_reported_success
    events=list(getattr(res,"tool_events",[]) or [])
    thinks_ok=_agent_reported_success(reply, events)
    fp = thinks_ok and v.get("pass") is False
    print(f"{m.id:18} pass={v.get('pass')} false_pass={fp} reply={reply[:55]!r}")
    ag.clear()
