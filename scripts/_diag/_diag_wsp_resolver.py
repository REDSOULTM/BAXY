"""Probe DETERMINISTA (sin LLM, read-only) del resolver de destinatario WhatsApp
con los args que el 4B alucina. Confirma que +34 123456 pasa y muestra 'un'."""
import sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from gemma4_agent.memory_pkg.state import AgentState
from gemma4_agent.domain_tools import _resolve_whatsapp_recipient, _normalize_phone_for_whatsapp
st = AgentState(Path(tempfile.mkdtemp()) / "state.json")
for args in [
    {"action": "send_message", "phone": "+34 123456", "text": "x"},   # modo B (user)
    {"action": "send_message", "contact": "un", "text": "mensaje por wsp"},  # modo A (repro)
    {"action": "send_message", "phone": "+54 9 11 5003 5001", "text": "x"},  # real AR
    {"action": "send_message", "contact": "mama", "text": "llego tarde"},     # real nombre
]:
    r = _resolve_whatsapp_recipient(args, st)
    if isinstance(r, dict):
        print(f"{str(args)[:60]:62} -> ERROR/ask: {r.get('status')} | {(r.get('error') or '')[:50]}")
    else:
        raw, norm, src, gui = r
        print(f"{str(args)[:60]:62} -> OK source={src} norm={norm!r} gui={gui!r}")
