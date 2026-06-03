"""Verifica el fix chain-messaging: "abrí WhatsApp y mandale a X Y" -> clause2 rutea
al tool WHATSAPP (no email). MOCKEADO: whatsapp execute mockeado -> NO envía nada.
+ regresiones (poné rock->media, andá al canal->cu nav)."""
from __future__ import annotations
import os, sys, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.computer_use_pkg import computer_use as cu
from gemma4_agent.agent_core.agent import Gemma4Agent

cap = {"dispatch": [], "plans": []}
_real = ToolRegistry.execute
# whatsapp/email/media/app TODOS mockeados (NO side-effects); cu pasa para ver el plan.
ToolRegistry.execute = lambda self, n, a: (cap["dispatch"].append((n, dict(a or {}))) or
    (_real(self, n, a) if n == "computer_use" else {"ok": True, "_mock": True}))
cu.PlanExecutor.execute = lambda self, plan, *a, **k: (cap["plans"].append(plan) or
    {"ok": True, "verified": True, "steps": [{"op": p.get("op"), "arg": p.get("arg")} for p in (plan or [])]})
_OPEN = {"whatsapp", "spotify", "discord", "navegador", "chrome"}
Gemma4Agent._window_title_in_text = lambda self, t: ("App - " + t) if (
    {w for w in re.findall(r"\w+", (t or "").lower()) if len(w) >= 4} & _OPEN) else None

def run(msg):
    a = Gemma4Agent(); cap["dispatch"].clear(); cap["plans"].clear()
    r = a.run_content(msg)
    return [n for n, _ in cap["dispatch"]], list(cap["dispatch"]), (getattr(r, "content", "") or "").strip()

print("\n##### CHAIN-WHATSAPP (clause2 -> whatsapp, NO email) #####")
WSP = [
    ("abrí WhatsApp y mandale a Letras hola", "whatsapp"),
    ("abrí WhatsApp y mandale a Música buenas noches", "whatsapp"),
    ("abrí WhatsApp y decile a Letras que ya voy", "whatsapp"),
]
for u, want in WSP:
    tools, disp, rep = run(u)
    hit = want in tools and "email" not in tools
    # mostrar args del whatsapp para ver contacto/texto
    wa = [a for n, a in disp if n == "whatsapp"]
    print(f"  [{'OK' if hit else 'XX'}] {u!r:48} tools={tools}")
    if wa: print(f"        whatsapp args: contact={wa[0].get('contact')!r} text={wa[0].get('text')!r}")
    print(f"        reply={rep[:70]!r}")

print("\n##### REGRESIÓN #####")
REG = [
    ("abrí Spotify y poné rock", "media (no whatsapp)"),
    ("abrí Discord y andá al canal general", "cu nav"),
    ("abrí WhatsApp y subí el volumen", "audio (clause2 no es msg)"),
]
for u, note in REG:
    tools, disp, rep = run(u)
    ops = [(p.get("op")) for pl in cap["plans"] for p in (pl or [])]
    print(f"  {u!r:46} [{note}] tools={tools}")
print("[done]")
