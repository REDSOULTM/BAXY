"""Tests del gate del VRAM watchdog en agent.run_content (inv 6.1).

Cierra la deuda del fix de proxy zombie 2026-05-28: antes el watchdog solo
logueaba ('VRAMWatchdog usa nvidia-smi pero solo loguea, no bloquea
(pendiente: que actue en 4GB)'). Ahora:

  - critical (free < 400 MiB)  -> bloquea el turno de vision con AgentReply
                                  honesto. Causa raiz del proxy zombie es el
                                  OOM CUDA al cargar mmproj #13085: prevenirlo
                                  es la unica estrategia que evita el reload.
  - degrade  (400-800 MiB)     -> recycla el server (descarga mmproj).
  - warn/ok                    -> solo log/trace, no bloquea.
"""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


from gemma4_agent.agent_core.agent import Gemma4Agent, AgentReply
from gemma4_agent.infra.config import AgentConfig


def _make_agent(*, prose_content: str = "Hola.") -> Gemma4Agent:
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_vram_gate_"))
    cfg = dataclasses.replace(
        AgentConfig.from_env(),
        memory_path=tmp / "m.json", captures_dir=tmp / "cap",
        trace_path=tmp / "t.jsonl", state_path=tmp / "s.json",
        enable_tracing=False, enable_safety=False,
    )
    a = Gemma4Agent(cfg)

    def chat(messages, **kw):
        return {"choices": [{
            "message": {"role": "assistant", "content": prose_content,
                        "tool_calls": []},
            "finish_reason": "stop",
        }]}
    a.client.chat = chat
    return a


def _set_watchdog_level(agent, level: str, free_mib: float = 300.0,
                        available: bool = True):
    """Reemplaza el watchdog del agent con uno que siempre devuelve el level
    indicado. Esto evita el TTL del cache del watchdog real."""
    from gemma4_agent.support.vram_watchdog import VRAMSnapshot
    snap = VRAMSnapshot(free_mib=free_mib, used_mib=6144-free_mib,
                        total_mib=6144, level=level, available=available)
    fake = MagicMock()
    fake.snapshot.return_value = snap
    fake.level.return_value = level
    # vision_safe: critical/degrade -> False, ok -> True
    fake.vision_safe.return_value = level == "ok"
    fake.should_degrade.return_value = level in ("degrade", "critical")
    agent.vram_watchdog = fake
    return fake


class VRAMGateCriticalBlocksVisionTest(unittest.TestCase):
    """Si la VRAM esta en CRITICAL (<400 MiB) y el turno es de vision,
    devolvemos un AgentReply honesto SIN despachar al LLM. Esto previene el
    OOM CUDA que dejaria el server zombie."""

    def test_vision_turn_blocked_when_critical(self):
        a = _make_agent()
        _set_watchdog_level(a, "critical", free_mib=300)
        # Forzar vision_action: mockear choose_mode
        with patch("gemma4_agent.agent.choose_mode") as mock_mode:
            m = MagicMock()
            m.name = "vision_action"
            mock_mode.return_value = m
            # El LLM NO deberia ser llamado
            llm_calls = []
            orig_chat = a.client.chat
            def spy_chat(*args, **kwargs):
                llm_calls.append((args, kwargs))
                return orig_chat(*args, **kwargs)
            a.client.chat = spy_chat
            reply = a.run_content("que ves en la pantalla")

        self.assertIsInstance(reply, AgentReply)
        # No se llamo al LLM (no se gasto el turno con OOM)
        self.assertEqual(len(llm_calls), 0,
                         f"LLM no debia ser llamado en critical, calls={len(llm_calls)}")
        # Mission marcado FAILED con la razon explicita
        self.assertEqual(reply.mission["mission_status"], "FAILED")
        self.assertEqual(reply.mission["reason"], "vram_critical_for_vision")
        # Mensaje al user en castellano y sin jerga tecnica de OOM
        self.assertIn("VRAM", reply.content)

    def test_text_turn_not_blocked_when_critical(self):
        """Solo bloqueamos VISION. Un turno de texto no carga mmproj nuevo,
        asi que NO debe ser bloqueado por critical."""
        a = _make_agent()
        _set_watchdog_level(a, "critical", free_mib=300)
        with patch("gemma4_agent.agent.choose_mode") as mock_mode:
            m = MagicMock()
            m.name = "quick_action"
            mock_mode.return_value = m
            reply = a.run_content("hola")
        # Turno completa normal
        self.assertEqual(reply.content, "Hola.")
        # NO mission failed por vram
        self.assertNotEqual(
            reply.mission.get("reason"), "vram_critical_for_vision")


class VRAMGateDegradeRecyclesServerTest(unittest.TestCase):
    """En DEGRADE (400-800 MiB) NO bloqueamos pero reciclamos el server para
    liberar memoria fragmentada antes del turn de vision."""

    def test_vision_turn_recycles_in_degrade(self):
        a = _make_agent()
        _set_watchdog_level(a, "degrade", free_mib=600)
        mock_mgr = MagicMock()
        mock_mgr.recycle_for_vision_leak.return_value = True
        with patch("gemma4_agent.agent.choose_mode") as mock_mode, \
             patch("gemma4_agent.llama_server.get_shared_manager",
                   return_value=mock_mgr):
            m = MagicMock()
            m.name = "vision_action"
            mock_mode.return_value = m
            reply = a.run_content("describe la pantalla")
        # Recycle fue llamado
        mock_mgr.recycle_for_vision_leak.assert_called_once()
        # Turno NO bloqueado (no AgentReply de bloqueo)
        self.assertNotEqual(
            reply.mission.get("reason"), "vram_critical_for_vision")

    def test_recycle_failure_does_not_break_turn(self):
        a = _make_agent()
        _set_watchdog_level(a, "degrade", free_mib=600)
        mock_mgr = MagicMock()
        mock_mgr.recycle_for_vision_leak.side_effect = RuntimeError("boom")
        with patch("gemma4_agent.agent.choose_mode") as mock_mode, \
             patch("gemma4_agent.llama_server.get_shared_manager",
                   return_value=mock_mgr):
            m = MagicMock()
            m.name = "vision_action"
            mock_mode.return_value = m
            # NO debe propagar la exception del recycle
            reply = a.run_content("describe la pantalla")
        self.assertIsInstance(reply, AgentReply)


class VRAMGateOkPassesThroughTest(unittest.TestCase):
    """En OK no se hace nada especial."""

    def test_ok_does_not_recycle(self):
        a = _make_agent()
        _set_watchdog_level(a, "ok", free_mib=4000)
        mock_mgr = MagicMock()
        with patch("gemma4_agent.agent.choose_mode") as mock_mode, \
             patch("gemma4_agent.llama_server.get_shared_manager",
                   return_value=mock_mgr):
            m = MagicMock()
            m.name = "vision_action"
            mock_mode.return_value = m
            a.run_content("describe")
        mock_mgr.recycle_for_vision_leak.assert_not_called()


class VRAMGateNoGpuTest(unittest.TestCase):
    """Sin GPU NVIDIA detectable: el gate es no-op (no bloquea, no recicla)."""

    def test_no_gpu_passes_through(self):
        a = _make_agent()
        # available=False = sin GPU
        _set_watchdog_level(a, "ok", free_mib=0, available=False)
        mock_mgr = MagicMock()
        with patch("gemma4_agent.agent.choose_mode") as mock_mode, \
             patch("gemma4_agent.llama_server.get_shared_manager",
                   return_value=mock_mgr):
            m = MagicMock()
            m.name = "vision_action"
            mock_mode.return_value = m
            reply = a.run_content("describe")
        # Sin GPU no bloqueamos sin evidencia
        self.assertNotEqual(
            reply.mission.get("reason"), "vram_critical_for_vision")
        mock_mgr.recycle_for_vision_leak.assert_not_called()


if __name__ == "__main__":
    unittest.main()
