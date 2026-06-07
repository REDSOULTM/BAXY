"""LIVE verify (CLAUDE.md §3.5) del fix steam(install): "instalame doom eternal"
debe disparar steam://install/<appid> (diálogo de instalación NATIVO de Steam),
NO solo abrir la página de la tienda.

SEGURIDAD: NUNCA lanzamos Steam ni instalamos nada de verdad. Patcheamos
os.startfile -> CAPTURA la URI sin ejecutarla. Patcheamos la resolución de AppID
(red) a un valor conocido para que sea determinista y offline. El resto del agente
(router + 4B + handler t_steam REAL) corre de verdad. Cero SendInput.

Probamos varias frasings porque el 4B es no-determinista y puede rutear el mismo
pedido a tools distintas (steam.install vs steam.store_page vs app vs browser).
"""
from __future__ import annotations
import os, sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
os.environ.setdefault("GEMMA4_DIAG", "1")  # no contaminar la DB de Jarvis en pruebas

from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
get_shared_manager().start(prof, wait_health=True, timeout_s=120)
print("[boot] OK", flush=True)

import gemma4_agent.tools_pkg.tools as tools_mod
from gemma4_agent.tools_pkg.tools import ToolRegistry
from gemma4_agent.agent_core.agent import Gemma4Agent

# Captura de TODO os.startfile (la única vía por la que el handler lanza la URI),
# y de los dispatches de tools (para ver qué tool/action eligió el 4B).
cap = {"startfile": [], "dispatch": []}

def _fake_startfile(target, *a, **k):
    cap["startfile"].append(str(target))
    # NO ejecutar: no abrimos Steam ni instalamos nada.
    return None

_real_exec = ToolRegistry.execute
def _exec(self, name, args):
    cap["dispatch"].append((name, dict(args or {})))
    return _real_exec(self, name, args)
ToolRegistry.execute = _exec

# AppID determinista y offline: DOOM Eternal = 782330 (su AppID real en Steam).
# source='steam' = ALTA confianza -> el handler intentará AUTO-CONFIRMAR el diálogo.
def _fake_resolve(self, query):
    if not query:
        return None
    return {"appid": "782330", "match": {"name": "DOOM Eternal"},
            "source": "steam"}
ToolRegistry._resolve_steam_appid = _fake_resolve

# STUB del confirmador: NO abrimos/apretamos el diálogo real en esta prueba (ya
# se verificó por separado con Terraria, confirmed=True). Acá medimos que el
# AGENTE rutea install + llama al confirmador en alta confianza.
cap["confirm_calls"] = []
def _fake_confirm(self, game_name, **k):
    cap["confirm_calls"].append(game_name)
    return {"confirmed": True, "button": "Instalar",
            "reason": "dialog_closed_after_invoke", "_stubbed": True}
ToolRegistry._steam_confirm_install_dialog = _fake_confirm


def run(msg):
    a = Gemma4Agent()
    cap["startfile"].clear(); cap["dispatch"].clear()
    r = a.run_content(msg)
    return list(cap["dispatch"]), list(cap["startfile"]), (getattr(r, "content", "") or "").strip()


PHRASINGS = [
    "instalame doom eternal en steam",          # la frase EXACTA de la captura
    "instala doom eternal en steam",
    "descargame doom eternal de steam",
    "bajá doom eternal en steam",
    "install doom eternal on steam",
    "quiero instalar doom eternal en steam",
]

print("\n##### STEAM INSTALL — debe disparar steam://install/ + AUTO-CONFIRMAR #####")
ok_install = 0
ok_confirm = 0
with mock.patch("os.startfile", _fake_startfile):
    for u in PHRASINGS:
        cap["confirm_calls"].clear()
        disp, started, rep = run(u)
        install_uri = next((s for s in started if s.startswith("steam://install/")), None)
        route = " -> ".join(f"{n}({a.get('action','')})" for n, a in disp) or "nada"
        hit = install_uri is not None
        confirmed = len(cap["confirm_calls"]) > 0
        ok_install += hit
        ok_confirm += confirmed
        mark = ("✓ INSTALL+CONFIRM" if (hit and confirmed)
                else "✓ INSTALL" if hit else ("~ " + (started[0] if started else "—")))
        print(f"  {mark:34} | {u!r}")
        print(f"       route: {route}")
        if started:
            print(f"       startfile: {started}")
        print(f"       auto-confirm llamado: {confirmed} {cap['confirm_calls']}")
        print(f"       reply: {rep[:90]!r}")

print(f"\n  => {ok_install}/{len(PHRASINGS)} dispararon steam://install/")
print(f"  => {ok_confirm}/{len(PHRASINGS)} llamaron al auto-confirmador (alta confianza)")
print("  (NADA se instaló acá: startfile y el confirmador están stubbeados. El")
print("   confirmador REAL ya se probó por separado con Terraria -> confirmed=True,")
print("   descarga real al 99%.)")
