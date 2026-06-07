import sys, os, time
sys.path.insert(0, os.path.abspath("."))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)
from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent(); agent.run_content("hola")
# llamar al client.chat DIRECTO como lo hace el helper
sys_p = ("You are Baxy, a local Windows voice assistant. An action was just performed "
         "successfully. Reply with ONE very short sentence confirming it was done, in the "
         "SAME language the user wrote their message in. Plain text, no markdown. Just the confirmation.")
usr_p = "User said: open notepad\nAction performed: opened the application notepad\nConfirmation:"
print("=== llamando client.chat directo ===", flush=True)
t0=time.time()
try:
    resp = agent.client.chat([{"role":"system","content":sys_p},{"role":"user","content":usr_p}],
                             tools=None, enable_thinking=False, parallel_tool_calls=False, max_tokens=40, timeout_s=12.0)
    dt=time.time()-t0
    print(f"  dt={dt:.2f}s | type={type(resp).__name__}", flush=True)
    print(f"  resp keys: {list(resp.keys()) if isinstance(resp,dict) else 'NOT DICT'}", flush=True)
    ch=resp.get('choices') if isinstance(resp,dict) else None
    print(f"  choices: {ch}", flush=True)
    if ch: print(f"  content: {(ch[0].get('message') or {}).get('content')!r}", flush=True)
except Exception as e:
    import traceback; print(f"  EXCEPTION {type(e).__name__}: {e}", flush=True); traceback.print_exc()
