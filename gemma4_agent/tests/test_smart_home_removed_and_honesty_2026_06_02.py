"""Regresión 2026-06-02: smart_home ELIMINADA (pedido del usuario) + la guarda
anti-mentira-física que la validación EN VIVO destapó.

Contexto (cazado por validación en vivo, regla #3.5):
  BUG A — tras borrar la tool smart_home (schema/handler/dataset/router-data),
    quedó un keyword rule HARDCODEADO en planner.py que TODAVÍA la ofrecía
    ("prendé las luces" -> ['smart_home']). El router no debe ofrecer una tool
    que no existe.
  BUG B — sin smart_home, el 4B ruteaba "bajá el termostato" a source_manager
    (read-only, devuelve ok=True / verified=None sin cambiar nada) y FABRICABA
    "Listo, bajé la temperatura" — MENTIRA. La guarda guard_unverified_final
    eximía TODO verified=None, así que el claim de efecto físico pasaba.

Estos tests fijan ambos contratos (mide la FORMA, no frases por idioma).
"""
from __future__ import annotations

import unittest


class SmartHomeFullyRemovedFromRouter(unittest.TestCase):
    """El router NUNCA debe ofrecer 'smart_home' (la tool ya no existe)."""

    def test_home_automation_phrases_do_not_offer_smart_home(self):
        from gemma4_agent.routing.planner import select_tool_names, plan_mission
        phrases = [
            "prendé las luces de la sala",
            "apagá todas las luces de la casa",
            "bajá la temperatura del termostato",
            "turn on the living room lights",
            "encendé el aire acondicionado",
            "activá el modo cine",
            "cerrá la cerradura de la entrada",
        ]
        for q in phrases:
            tools = select_tool_names(q, plan_mission(q), safety_enabled=True)
            self.assertNotIn(
                "smart_home", tools,
                f"{q!r} no debe ofrecer la tool eliminada smart_home; got {tools}")

    def test_smart_home_not_in_any_router_structure(self):
        # planner: ni _PRIMARY_TOOLS ni _related_tools deben mencionarla.
        from gemma4_agent.routing import planner
        primary = getattr(planner, "_PRIMARY_TOOLS", set())
        self.assertNotIn("smart_home", primary, "smart_home sigue en _PRIMARY_TOOLS")
        self.assertEqual(planner._related_tools("smart_home", "prendé las luces"), [],
                         "smart_home aún tiene deps en _related_tools")


class GuardBlocksPhysicalEffectClaimOnReadOnlyTool(unittest.TestCase):
    """guard_unverified_final NO debe eximir un reply que afirma un EFECTO FÍSICO
    cuando la única tool que corrió fue read-only (verified=None, no cambió estado).
    Esa era la grieta por la que "bajé el termostato" mentía."""

    def _event(self, result):
        class _E:
            def __init__(self, r):
                self.result = r
        return _E(result)

    def test_readonly_ok_true_does_not_back_a_physical_effect_claim(self):
        from gemma4_agent.agent_core.agent_guards import guard_unverified_final
        # source_manager status: ok=True, verified ausente (=None), no cambió nada.
        events = [self._event({"ok": True, "local_state": True, "source_count": 0})]
        # reply que AFIRMA efecto físico (lo que el 4B fabricaba).
        lying = "Listo, bajé la temperatura del termostato al 20 por ciento."
        out = guard_unverified_final(lying, events)
        # Debe AÑADIR una nota honesta (no dejar el claim de éxito intacto).
        self.assertNotEqual(
            out, lying,
            "la guarda dejó pasar un claim de efecto físico sobre una tool read-only")

    def test_readonly_does_not_break_honest_lookup_reply(self):
        # Un reply de BÚSQUEDA legítimo (no afirma efecto físico) sobre una tool
        # read-only NO debe ser penalizado: el camino feliz queda intacto.
        from gemma4_agent.agent_core.agent_guards import guard_unverified_final
        events = [self._event({"ok": True, "results": ["a", "b"]})]
        honest = "Encontré dos resultados sobre pytest; el primero es la doc oficial."
        out = guard_unverified_final(honest, events)
        self.assertEqual(
            out, honest,
            "un reply de lookup honesto NO debe recibir la nota de no-confirmación")

    def test_verified_true_still_passes(self):
        # El camino feliz absoluto: tool verificada -> reply de éxito intacto.
        from gemma4_agent.agent_core.agent_guards import guard_unverified_final
        events = [self._event({"ok": True, "verified": True})]
        ok = "Listo, silencié el audio."
        self.assertEqual(guard_unverified_final(ok, events), ok)


if __name__ == "__main__":
    unittest.main()
