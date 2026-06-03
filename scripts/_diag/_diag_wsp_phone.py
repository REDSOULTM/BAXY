"""LIVE end-to-end: el fix completo de 'manda un mensaje por wsp'.
Deja correr la cadena REAL (planner+4B+t_whatsapp/guarda) pero mockea
whatsapp_tool (físico: deeplink/GUI) -> CERO acciones reales."""
from __future__ import annotations
import os, sys
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")
from gemma4_agent.infra.profiles import get_active_profile, apply_profile_to_env
from gemma4_agent.infra.llama_server import get_shared_manager
prof = get_active_profile(); apply_profile_to_env(prof)
mgr = get_shared_manager(); print("[boot]...", flush=True)
mgr.start(prof, wait_health=True, timeout_s=120); print("[boot] OK", flush=True)

wa_calls = []
from gemma4_agent.domain_tools import _resolve_whatsapp_recipient
def _fake_whatsapp_tool(args, state, executor=None):
    """Corre el resolver REAL (read-only) para reflejar needs_user honestamente;
    solo saltea el deeplink/GUI físico cuando SÍ resolvió un destinatario."""
    wa_calls.append(dict(args or {}))
    if str(args.get("action") or "send_message").casefold() in {
            "send_message", "send", "open_chat"}:
        resolved = _resolve_whatsapp_recipient(args, state)
        if isinstance(resolved, dict):           # _err / needs_user honesto
            return resolved
    return {"ok": True, "status": "dispatched", "sent": False, "_mock": True}

from gemma4_agent.tools_pkg.tools import ToolRegistry
for _m in ["gui_type", "gui_keypress", "_send_text_via_sendinput"]:
    if hasattr(ToolRegistry, _m):
        setattr(ToolRegistry, _m, lambda *a, **k: {"ok": True})
from gemma4_agent.agent_core.agent import Gemma4Agent

def run(msg, n=1):
    agent = Gemma4Agent()
    rows = []
    for _ in range(n):
        try: agent.history.clear()
        except Exception: pass
        wa_calls.clear()
        with mock.patch("gemma4_agent.tools_pkg.tools.whatsapp_tool",
                        side_effect=_fake_whatsapp_tool):
            reply = agent.run_content(msg)
        rep = (getattr(reply, "content", "") or "").strip()
        plumbed = getattr(agent.tools, "_current_user_text", "<UNSET>")
        rows.append((list(wa_calls), rep, plumbed))
    return rows

def show(title, msg, n=1):
    print(f"\n##### {title}: {msg!r} x{n} #####")
    for i, (calls, rep, plumbed) in enumerate(run(msg, n=n), 1):
        if not calls:
            tag = "NO wa_tool (asked / guard / no-recipient)"
        else:
            tag = f"wa_tool -> {calls}"
        print(f" [{i}] plumbed={plumbed!r}")
        print(f"     {tag}")
        print(f"     reply={rep[:120]!r}")

show("A) BUG reportado (sin destinatario)", "manda un mensaje por wsp", n=6)
show("B) legítimo nombre", "mandale a mama que ya llego", n=2)
show("C) legítimo número dictado", "mandale al +54 9 11 5003 5001 que ya voy", n=1)
