"""Un turno: 'abrí gmail.com' con tracing de args/result de cada execute."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile()
apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.tools.apps.find("notepad", limit=1)

orig = agent.tools.execute
def traced(name, args=None):
    t0 = time.monotonic()
    r = orig(name, args)
    print(f"  [exec] {name} args={args} -> ok={r.get('ok')} st={r.get('status')!r} "
          f"err={r.get('error')!r} url={r.get('navigated_url') or r.get('url')!r} "
          f"({time.monotonic()-t0:.1f}s)", flush=True)
    return r
agent.tools.execute = traced

reply = agent.run_content("abrí gmail.com")
print("REPLY:", (reply.content or "")[:140], flush=True)
