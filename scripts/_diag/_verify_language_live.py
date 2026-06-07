"""Verificación EN VIVO del fix de idioma (core.md: espejar el idioma del user).

Inyecta comandos en varios idiomas por run_content (seguro, sin SendInput) y comprueba
que el reply NO sale en español cuando el user escribió en otro idioma. Ejecución
física mockeada (read-only) para no tocar nada.

Uso: python scripts/_diag/_verify_language_live.py
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_AGENT_SAFETY", "0")  # medir idioma sin fricción de gate

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

from gemma4_agent.tools_pkg.tools import ToolRegistry
def _mock(self, n, a):
    return {"ok": True, "status": "ok", "verified": True, "_eval_mock": True}
ToolRegistry.execute = _mock

from gemma4_agent.agent_core.agent import Gemma4Agent
agent = Gemma4Agent()
agent.run_content("hola")  # warm

# (idioma, mensaje, marcadores del idioma esperado, marcadores de ESPAÑOL = mal)
CASES = [
    ("EN", "open notepad", ["opened", "opening", "done", "i ", "notepad", "the "],
     ["listo", "abrí", "abrir"]),
    ("EN", "what time is it", ["it's", "the time", "it is"], ["son las", "hora es"]),
    ("PT", "abra o bloco de notas", ["abri", "bloco", "pronto", "feito", "o "],
     ["listo", "abrí el", "abrir el"]),
    ("FR", "ouvre le bloc-notes", ["ouvert", "j'ai", "fait", "le bloc", "voilà"],
     ["listo", "abrí", "abrir"]),
    ("DE", "öffne den editor", ["geöffnet", "ich habe", "fertig", "editor", "erledigt"],
     ["listo", "abrí", "abrir"]),
    ("IT", "apri il blocco note", ["aperto", "ho ", "fatto", "il blocco"],
     ["listo", "abrì", "aprire"]),
]

print("\n=== VERIFICACIÓN EN VIVO DEL IDIOMA ===\n", flush=True)
ok = 0
for lang, msg, good, bad in CASES:
    try:
        agent.history.clear()
    except Exception:
        pass
    rep = agent.run_content(msg)
    reply = (getattr(rep, "content", "") or "")
    rl = reply.lower()
    has_good = any(g in rl for g in good)
    has_es = any(b in rl for b in bad)
    # veredicto: bien si NO arranca en español (el marcador fuerte es "listo,"/"abrí")
    es_lead = rl.strip().startswith(("listo", "abrí", "abrir", "claro"))
    status = "OK" if (not es_lead and not (has_es and not has_good)) else "ES?"
    if status == "OK":
        ok += 1
    print(f"[{status}] {lang}: {msg!r}")
    print(f"    reply: {reply[:100]!r}\n", flush=True)

print(f"=== RESULTADO: {ok}/{len(CASES)} NO respondieron en español ===", flush=True)
