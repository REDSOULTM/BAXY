import sys
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path.cwd()))
from gemma4_agent.agent_core.agent import Gemma4Agent
ag = Gemma4Agent.__new__(Gemma4Agent)  # sin __init__ pesado
class _T:
    def execute(self, name, args):
        return {"ok": True, "status": "dispatched", "chat_opened": True, "sent": False}
ag.tools = _T()
for txt in ["mandale a mama que ya llego", "decile a juan que llego tarde",
            "manda un mensaje por wsp", "respondele que sí"]:
    ev = ag._deterministic_reply(txt)
    if ev is None:
        print(f"{txt!r:38} -> None (cae a flujo normal / LLM pregunta)")
    else:
        print(f"{txt!r:38} -> FIRE contact={ev.result.get('reply_contact')!r} ok={ev.result.get('ok')}")
