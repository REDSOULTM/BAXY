"""Bug medido (2026-05-27): un `pending_intent` se PERSISTE en state.json, pero
se evalúa contra `_turn_counter`, que vuelve a 0 en cada proceso nuevo. Una
aclaración aparcada en una sesión vieja (p.ej. computer_use sin args, nunca
resuelta) sobrevivía al reinicio y el primer turno (counter=1) la veía "fresca"
para siempre, secuestrando preguntas nuevas como "¿quién eres?" (forzaba
computer_use + toda la unión semántica; en modo movilidad terminaba en
screenshot+OCR para responder identidad — absurdo).

FIX (raíz): el agente limpia cualquier pending_intent al ARRANCAR. Una aclaración
es una señal de continuidad DENTRO de la sesión; persistida entre procesos está
abandonada. Las aclaraciones legítimas (preguntar→responder) viven y mueren en el
mismo proceso, donde el TTL por turnos sí aplica (cubierto por test_pending_intent).

Estos tests NO ejercen GUI ni el LLM: construyen el agente con un state.json
temporal (env GEMMA4_AGENT_STATE) y verifican el contrato de arranque."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class PendingIntentBootClearTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, name = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.tmp = Path(name)
        # state con un pending_intent ABANDONADO de una "sesión anterior"
        self.tmp.write_text(json.dumps({
            "resources": {}, "checkpoints": {}, "notes": [], "confirmations": {},
            "_pending_intent": {
                "tool": "computer_use", "args": {},
                "asks_for": "user_clarification",
                "created_turn": 1, "ttl_turns": 2,
            },
        }), encoding="utf-8")
        self._prev_env = os.environ.get("GEMMA4_AGENT_STATE")
        os.environ["GEMMA4_AGENT_STATE"] = str(self.tmp)

    def tearDown(self) -> None:
        if self._prev_env is None:
            os.environ.pop("GEMMA4_AGENT_STATE", None)
        else:
            os.environ["GEMMA4_AGENT_STATE"] = self._prev_env
        try:
            self.tmp.unlink()
        except Exception:
            pass

    def _build_agent(self):
        from gemma4_agent.agent_core.agent import Gemma4Agent
        from gemma4_agent.infra.config import AgentConfig
        return Gemma4Agent(AgentConfig.from_env())

    def test_stale_pending_intent_cleared_on_boot(self) -> None:
        # precondición: el slot está en disco antes de arrancar
        self.assertIsNotNone(
            json.loads(self.tmp.read_text(encoding="utf-8")).get("_pending_intent"))
        ag = self._build_agent()
        self.assertEqual(ag.config.state_path, self.tmp, "no usó el state temporal")
        # tras el boot, el slot quedó limpio en disco y en lectura
        on_disk = json.loads(self.tmp.read_text(encoding="utf-8")).get("_pending_intent")
        self.assertIsNone(on_disk, f"el boot no limpió el slot: {on_disk}")
        self.assertIsNone(ag.state.get_pending_intent(current_turn=1))

    def test_first_turn_does_not_inherit_stale_tool(self) -> None:
        # el primer turno (counter -> 1) NO debe ver el computer_use aparcado:
        # antes del fix, get_pending_intent(1) lo devolvía (1-1=0 <= ttl 2).
        ag = self._build_agent()
        captured = {}
        orig = ag.trace.event

        def _ev(tid, kind, **f):
            if kind == "tool_subset":
                captured["tools"] = f.get("tools") or []
            return orig(tid, kind, **f)

        ag.trace.event = _ev
        fake = {"choices": [{"message": {"content": "Soy Gemma."}}]}
        with mock.patch.object(ag.client, "chat", return_value=fake):
            ag.run_content("Quien eres?")
        tools = captured.get("tools", [])
        self.assertNotIn("computer_use", tools,
                         f"el primer turno heredó el intent abandonado: {tools}")

    def test_legit_pending_intent_within_session_still_works(self) -> None:
        # Anti-regresión: el clear es SOLO al boot. Un pending_intent puesto
        # DURANTE la sesión (mismo proceso) debe seguir vivo y rescatar la
        # respuesta corta del usuario en el turno siguiente.
        ag = self._build_agent()  # esto limpia el stale del setUp
        ag._turn_counter = 5
        ag.state.set_pending_intent(
            tool="media", args={"action": "play", "provider": "disney"},
            asks_for="profile", current_turn=5, ttl_turns=3,
        )
        pi = ag.state.get_pending_intent(current_turn=6)
        self.assertIsNotNone(pi, "el slot intra-sesión no sobrevivió")
        self.assertEqual(pi["tool"], "media")


if __name__ == "__main__":
    unittest.main()
