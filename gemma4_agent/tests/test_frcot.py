"""Tests para FR-CoT (opt-in GEMMA4_FRCOT, dormant por default).

Cubre con MOCKS (sin modelo/GPU) lo verificable:
  - gating de la plantilla en el system prompt segun el flag
  - guarda ESTRUCTURAL anti-filtrado: si el modelo escupe el formato
    INTENT:/TOOL:/ARGS:/GO al reply visible (el bug que rompio media 6/6->3/6),
    sanitize_text/sanitize_assistant_message lo borran PERO preservan los tool_calls
  - caso ideal: el formato dentro de <think> lo saca el strip de thinking existente
  - sin el flag: la guarda es no-op (0 cambio de comportamiento)

Lo que NO se cubre aca (necesita el modelo real, validacion EN VIVO): si el Gemma
de verdad razona breve en el formato y si lo deja en <think> o lo filtra. Ver
documentacion/SPRINT_frcot_latencia_accion.md.
"""
import os
import unittest

from ..agent_core import agent_prompt
from ..support import reasoning


class _FrcotEnv:
    """Context manager para prender/apagar GEMMA4_FRCOT y restaurar el valor previo."""

    def __init__(self, on: bool):
        self.on = on
        self.prev = None

    def __enter__(self):
        self.prev = os.environ.get("GEMMA4_FRCOT")
        if self.on:
            os.environ["GEMMA4_FRCOT"] = "1"
        else:
            os.environ.pop("GEMMA4_FRCOT", None)
        return self

    def __exit__(self, *exc):
        if self.prev is None:
            os.environ.pop("GEMMA4_FRCOT", None)
        else:
            os.environ["GEMMA4_FRCOT"] = self.prev


class TestFrcotGating(unittest.TestCase):
    def test_directive_present_when_on(self):
        with _FrcotEnv(True):
            self.assertTrue(agent_prompt._frcot_enabled())
            core = agent_prompt._core_for_profile()
            self.assertIn("INTENT:", core)
            self.assertIn("BRIEF REASONING", core)

    def test_directive_absent_when_off(self):
        with _FrcotEnv(False):
            self.assertFalse(agent_prompt._frcot_enabled())
            self.assertNotIn("BRIEF REASONING", agent_prompt._core_for_profile())


class TestFrcotLeakGuard(unittest.TestCase):
    LEAKED = "INTENT: open_app\nTOOL: app\nARGS: name=spotify\nGO\nListo, abrí Spotify."

    def test_guard_strips_leak_when_on(self):
        with _FrcotEnv(True):
            out = reasoning.sanitize_text(self.LEAKED)
            self.assertNotIn("INTENT:", out)
            self.assertNotIn("TOOL:", out)
            self.assertNotIn("ARGS:", out)
            self.assertIn("Listo, abrí Spotify.", out)

    def test_guard_noop_when_off(self):
        with _FrcotEnv(False):
            self.assertIn("INTENT:", reasoning.sanitize_text(self.LEAKED))

    def test_guard_preserves_normal_reply(self):
        with _FrcotEnv(True):
            normal = "La capital de Francia es París."
            self.assertEqual(reasoning.sanitize_text(normal), normal)

    def test_guard_no_false_positive_on_casual_intencion(self):
        with _FrcotEnv(True):
            casual = "Mi intención es ayudarte con lo que necesites."
            self.assertEqual(reasoning.sanitize_text(casual), casual)

    def test_guard_strips_truncated_block_no_go(self):
        with _FrcotEnv(True):
            out = reasoning.sanitize_text("INTENT: search\nTOOL: web\nARGS: query=clima")
            self.assertNotIn("INTENT:", out)


class TestFrcotChokepoint(unittest.TestCase):
    """El agente sanitiza el msg del modelo via sanitize_assistant_message
    (agent.py ~2008). Mock del shape del mensaje del LLM."""

    def test_leaked_format_stripped_tool_calls_preserved(self):
        with _FrcotEnv(True):
            raw = {
                "role": "assistant",
                "content": "INTENT: media_control\nTOOL: media\nARGS: action=play\nGO\nListo, puse música.",
                "tool_calls": [{"id": "x", "type": "function",
                                "function": {"name": "media", "arguments": "{}"}}],
            }
            clean = reasoning.sanitize_assistant_message(raw)
            self.assertNotIn("INTENT:", clean["content"])
            self.assertIn("Listo, puse música.", clean["content"])
            self.assertEqual(len(clean["tool_calls"]), 1)
            self.assertEqual(clean["tool_calls"][0]["function"]["name"], "media")

    def test_format_inside_think_block_is_stripped_by_existing_logic(self):
        # Caso IDEAL: el modelo usa bien el canal -> el formato queda en <think> y
        # el strip de thinking existente lo saca, sin depender de la guarda FR-CoT.
        with _FrcotEnv(True):
            raw = {"role": "assistant",
                   "content": "<think>INTENT: open_app\nTOOL: app\nARGS: name=steam\nGO</think>Listo, abrí Steam."}
            clean = reasoning.sanitize_assistant_message(raw)
            self.assertNotIn("INTENT:", clean["content"])
            self.assertEqual(clean["content"], "Listo, abrí Steam.")


if __name__ == "__main__":
    unittest.main()
