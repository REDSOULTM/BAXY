import os, sys, time
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
sys.path.insert(0, os.path.dirname(__file__))
from eval_set import missions_for_tier
from gemma4_agent.agent import Gemma4Agent
agent = Gemma4Agent()
ms = [m for m in missions_for_tier(1) if m.id.startswith("t1_write_")]
for m in ms:
    m.reset(); time.sleep(0.4)
    res = agent.run_text(m.utterance)
    reply = getattr(res, "content", "") or ""
    events = list(getattr(res, "tool_events", []) or [])
    tools = [(getattr(e, "name", None), (getattr(e, "args", {}) or {}).get("action")) for e in events]
    dl = time.time() + 6; v = {}; time.sleep(0.5)
    while True:
        v = m.goal_verifier()
        if v.get("pass") is True or time.time() >= dl:
            break
        time.sleep(0.5)
    print(f"{m.id:14} PASS={v.get('pass')} | {v.get('evidence')} | tools={tools} | reply={reply[:50]!r}")
    agent.clear()
