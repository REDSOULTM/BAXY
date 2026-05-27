import os, sys, time, json
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE","vram4")
sys.path.insert(0, "scripts/gui_eval")
import gemma4_agent.agent as A
from eval_set import process_running
ag=A.Gemma4Agent()
for utt in ["abrí VLC","open VLC","abre o VLC"]:
    os.system('powershell -NoProfile -Command "Get-Process vlc -EA SilentlyContinue | Stop-Process -Force -EA SilentlyContinue"')
    time.sleep(1.0)
    res=ag.run_text(utt)
    events=list(getattr(res,"tool_events",[]) or [])
    tools=[(getattr(e,"name",None),(getattr(e,"args",{}) or {}).get("action"),(getattr(e,"args",{}) or {}).get("name")) for e in events]
    dl=time.time()+20; ok=False; time.sleep(0.5)
    while True:
        ok=process_running("vlc", exact=False)
        if ok or time.time()>=dl: break
        time.sleep(0.8)
    print(f"utt={utt!r} VLC_running={ok} tools={tools} reply={(getattr(res,'content','') or '')[:70]!r}")
    ag.clear()
