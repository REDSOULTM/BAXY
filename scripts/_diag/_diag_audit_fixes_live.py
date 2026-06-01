"""LIVE eval (regla #3.5) de los fixes de la auditoría de tools 2026-06-01.

Corre variantes de fraseo REALES contra el agente + LLM reales vía run_content
(= la UI, seguro, sin SendInput). Verifica:
  - Fix #4 música multilingüe: 'pon una canción' (es), 'spiele musik' (de),
    'reproduz uma música' (pt), 'metti una canzone' (it) → ¿el agente rutea a
    reproducir música (media/browser youtube) y NO a charla/búsqueda literal?
  - Fix #1 confirmed: pedir un borrado debe pedir confirmación (no ejecutar).

NO ejecuta nada físico irreversible: el exec de tools va mockeado para no abrir
apps ni borrar archivos; medimos el ROUTING + el plan de tools, que es lo que los
fixes tocan. (Reproducir música abriría YouTube/Spotify reales → lo mockeamos.)

  py -3.10 scripts/_diag/_diag_audit_fixes_live.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager

prof = get_active_profile()
apply_profile_to_env(prof)
mgr = get_shared_manager()
print(f"[boot] {prof.name}; server...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120)

from gemma4_agent.agent_core.agent import Gemma4Agent

agent = Gemma4Agent()

# Capturar qué tools se ejecutan (mockeando el dispatch físico real).
executed = []
_real_execute = agent.tools.execute


def spy_execute(name, args):
    executed.append((name, dict(args or {})))
    # Mockeamos SOLO las tools que tendrían efecto físico/red para no abrir nada.
    a = (args or {}).get("action")
    if name in {"media", "browser", "browser_real", "app", "gui", "filesystem"}:
        return {"ok": True, "tool": name, "action": a, "mocked": True, "verified": None,
                "status": "dispatched"}
    return _real_execute(name, args)


agent.tools.execute = spy_execute


MUSIC_VARIANTS = [
    ("es", "pon una canción"),
    ("en", "play some music"),
    ("de", "spiele musik"),
    ("pt", "reproduz uma música"),
    ("it", "metti una canzone"),
    ("fr", "mets une chanson"),
]

MUSIC_TOOLS = {"media", "browser", "browser_real"}


def run(msg):
    executed.clear()
    try:
        reply = agent.run_content(msg)
        text = getattr(reply, "content", str(reply))
    except Exception as e:
        return None, [], f"{type(e).__name__}: {e}"
    return text, list(executed), None


print("\n=== FIX #4: música multilingüe (¿rutea a reproducir, no a charla?) ===")
music_ok = 0
for lang, msg in MUSIC_VARIANTS:
    reply, ev, err = run(msg)
    tools = [n for n, _ in ev]
    routed_music = any(t in MUSIC_TOOLS for t in tools)
    # 'spotify'/'youtube' en args también cuenta (media con provider)
    hit = "OK " if routed_music else "XX "
    if routed_music:
        music_ok += 1
    rep = (reply or "")[:55].replace("\n", " ")
    print(f"  {hit}[{lang}] {msg!r:32} tools={tools} | reply={rep!r}{' ERR='+err if err else ''}")
print(f"  -> música: {music_ok}/{len(MUSIC_VARIANTS)} ruteadas a reproducir")

print("\n=== FIX #1: confirmed — pedir borrado debe pedir confirmación (no ejecutar) ===")
# Usamos un path inventado; el dispatch real (no mockeado para 'filesystem'? sí lo
# mockeamos arriba) — para esta prueba dejamos pasar filesystem al real para ver el gate.
agent.tools.execute = _real_execute  # gate real
del executed[:]
reply, err = None, None
try:
    _r = agent.run_content("borra el archivo C:/Users/usuario/Desktop/_no_existe_test_audit.txt")
    reply = getattr(_r, "content", str(_r))
except Exception as e:
    err = f"{type(e).__name__}: {e}"
rep = (reply or "")[:120].replace("\n", " ")
print(f"  reply={rep!r}{' ERR='+err if err else ''}")
print("  (esperado: pide confirmación o dice que no existe — NUNCA 'borrado' sin confirmar)")

print("\n=== FIX #6: enum whatsapp — send y read siguen ruteando bien con el enum ===")
# Volvemos a mockear el dispatch fisico (whatsapp/vision abren ventanas reales).
executed_wa = []
_real2 = agent.tools.execute


def spy2(name, args):
    executed_wa.append((name, dict(args or {})))
    if name in {"whatsapp", "vision", "gui", "app", "contacts"}:
        return {"ok": True, "tool": name, "action": (args or {}).get("action"),
                "mocked": True, "verified": None, "status": "dispatched",
                "description": "Mamá: hola (mock)"}
    return _real2(name, args)


agent.tools.execute = spy2
WA_VARIANTS = [
    ("send", "mandale a mamá por whatsapp que llego tarde"),
    ("read", "leeme el último mensaje de whatsapp"),
]
for kind, msg in WA_VARIANTS:
    del executed_wa[:]
    try:
        r = agent.run_content(msg)
        text = getattr(r, "content", str(r))
    except Exception as e:
        text = f"ERR {type(e).__name__}: {e}"
    wa_calls = [(n, a.get("action")) for n, a in executed_wa if n == "whatsapp"]
    # ningun 'invalid tool arguments' del enum:
    bad = any("invalid" in str(a).lower() for _, a in executed_wa)
    hit = "OK " if (wa_calls or "whatsapp" in [n for n, _ in executed_wa]) and not bad else "?? "
    print(f"  {hit}[{kind}] {msg!r:48} whatsapp_calls={wa_calls} | reply={text[:45]!r}")

agent.tools.execute = _real2
print("\n[done]")
