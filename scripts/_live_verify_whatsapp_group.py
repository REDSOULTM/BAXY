"""Verificación EN VIVO (regla #3.5) de la cura del bug 'mamá -> grupo Música'.

Corre el agente REAL contra el LLM en :8080, con un store que tiene:
  - "mamá": contacto individual (is_group=False), SIN teléfono
  - "Música": grupo (is_group=True)

Inyecta varios fraseos de "mandale a mamá ..." vía agent.run_content (= la UI,
seguro, sin SendInput). Verifica que NINGUNA tool-call de whatsapp resuelva al
grupo "Música" como destinatario. NO envía nada real (mockeamos el dispatch
físico de WhatsApp: solo nos importa el ENRUTAMIENTO del destinatario).

Uso: python scripts/_live_verify_whatsapp_group.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

# vram4 default + tracing off para no ensuciar.
os.environ.setdefault("GEMMA4_DEFAULT_PROFILE", "vram4")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gemma4_agent.agent_core.agent import Gemma4Agent  # noqa: E402
from gemma4_agent.infra.config import AgentConfig  # noqa: E402
from gemma4_agent.domain_tools import contacts_tool  # noqa: E402


PHRASINGS = [
    "mandale a mamá por whatsapp que llego tarde",
    "decile a mamá en wsp que la quiero",
    "envíale un whatsapp a mamá: ya salgo",
    "mandá un mensaje de whatsapp a mamá diciendo hola",
]


def main() -> int:
    agent = Gemma4Agent(AgentConfig.from_env())
    # Sembrar el store: mamá (individuo) + Música (grupo).
    contacts_tool({"action": "create", "name": "mamá"}, agent.state)
    contacts_tool({"action": "create", "name": "Música", "is_group": True}, agent.state)

    # Mock SOLO del dispatch físico de WhatsApp: nos interesa A QUIÉN resuelve,
    # no abrir la app de verdad. Interceptamos _find_whatsapp_app para que el
    # tool tome el path deeplink/gui_search sin tocar el SO.
    failures: list[str] = []
    for phrase in PHRASINGS:
        agent.clear()
        contacts_tool({"action": "create", "name": "mamá"}, agent.state)
        contacts_tool({"action": "create", "name": "Música", "is_group": True}, agent.state)
        with patch("gemma4_agent.domain_tools._find_whatsapp_app",
                   return_value={"kind": None, "launch_target": None}):
            reply = agent.run_content(phrase)
        # Inspeccionar las tool-calls del turno.
        offending = []
        for ev in getattr(reply, "tool_events", []) or []:
            name = getattr(ev, "name", "") or (ev.get("name") if isinstance(ev, dict) else "")
            args = getattr(ev, "args", None) or (ev.get("args") if isinstance(ev, dict) else {}) or {}
            result = getattr(ev, "result", None) or (ev.get("result") if isinstance(ev, dict) else {}) or {}
            blob = f"{name} {args} {result}".lower()
            # FALLA si una tool de whatsapp tocó al grupo "música" como destino.
            touched_group = ("música" in blob) or ("musica" in blob)
            if "whatsapp" in str(name).lower() and touched_group:
                offending.append(f"{name}({args}) -> {result}")
        verdict = "OK" if not offending else "FALLA"
        if offending:
            failures.append(f"[{phrase}] resolvió a grupo: {offending}")
        print(f"  {verdict}  {phrase!r}")
        print(f"        reply: {str(getattr(reply, 'content', ''))[:120]!r}")

    print()
    if failures:
        print(f"RESULTADO: {len(failures)}/{len(PHRASINGS)} FALLARON (resolvieron a grupo):")
        for f in failures:
            print("  -", f)
        return 1
    print(f"RESULTADO: {len(PHRASINGS)}/{len(PHRASINGS)} OK — ningún fraseo resolvió al grupo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
