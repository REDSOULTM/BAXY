import os, sys, time
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
sys.path.insert(0, os.path.dirname(__file__))
from eval_set import missions_for_tier
from gemma4_agent.agent import Gemma4Agent
agent = Gemma4Agent()
ms = [m for m in missions_for_tier(1) if "mute" in m.id]
for m in ms:
    m.reset(); time.sleep(0.3)
    res = agent.run_text(m.utterance)
    reply = getattr(res, "content", "") or ""
    dl = time.time() + 4; v = {}; time.sleep(0.3)
    while True:
        v = m.goal_verifier()
        if v.get("pass") is True or time.time() >= dl:
            break
        time.sleep(0.4)
    print(f"{m.id:18} PASS={v.get('pass')} | utt={m.utterance!r} | reply={reply[:55]!r}")
    agent.clear()
