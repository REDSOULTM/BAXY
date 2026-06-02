"""Anti-primacy ordering del subset de tools del router (2026-06-02).

Idea: los LLMs atienden más a lo que aparece PRIMERO en el prompt (efecto de
primacía; p.ej. Liu et al. 2023 "Lost in the Middle", arXiv:2307.03172). Poner
la tool de DOMINIO de mayor confianza (score de suggest_tools_scored) al frente
del subset sube la probabilidad de que el 4B la elija. El reorden es CONSERVADOR:
solo cambia el ORDEN, nunca el CONJUNTO, y respeta las precondiciones existentes:

  * pending_intent (Hotfix F 2026-05-17) queda SIEMPRE primera.
  * infra (session/safety/state/verify/dependency) queda al FINAL.
  * las de dominio se ordenan por score descendente; empates y no-puntuadas
    preservan su orden original (sort estable) -> set(antes)==set(después).

Estos tests son PUROS (la función _antiprimacy_order no necesita el LLM ni el
encoder). El efecto real en el 4B lo valida el orquestador en vivo.
"""
from __future__ import annotations

import os
import unittest

from ..routing.planner import _antiprimacy_order, _INFRA_TAIL_TOOLS


class TestAntiPrimacyOrder(unittest.TestCase):

    def test_highest_score_domain_tool_goes_first(self):
        tools = ["web", "browser", "media"]
        scored = {"web": 0.30, "browser": 0.55, "media": 0.41}
        out = _antiprimacy_order(tools, scored)
        self.assertEqual(out, ["browser", "media", "web"])

    def test_set_preserved_only_order_changes(self):
        tools = ["web", "browser", "media", "session", "safety"]
        scored = {"web": 0.30, "browser": 0.55, "media": 0.41}
        out = _antiprimacy_order(tools, scored)
        self.assertEqual(set(out), set(tools),
                         "anti-primacy must NOT change the SET, only the order")

    def test_infra_tools_stay_at_the_end(self):
        # session/safety/state/verify/dependency NUNCA son candidatas primarias.
        tools = ["session", "web", "safety", "browser", "state"]
        scored = {"web": 0.30, "browser": 0.55}
        out = _antiprimacy_order(tools, scored)
        # las de dominio (por score) primero, luego la infra en su orden original.
        self.assertEqual(out, ["browser", "web", "session", "safety", "state"])
        # cada infra detrás de TODA tool de dominio.
        last_domain = max(i for i, t in enumerate(out) if t not in _INFRA_TAIL_TOOLS)
        first_infra = min(i for i, t in enumerate(out) if t in _INFRA_TAIL_TOOLS)
        self.assertLess(last_domain, first_infra)

    def test_infra_relative_order_preserved(self):
        # la infra NO se reordena por score: mantiene su orden de aparición.
        tools = ["safety", "session", "state"]
        out = _antiprimacy_order(tools, {})
        self.assertEqual(out, ["safety", "session", "state"])

    def test_pending_intent_pinned_first_even_with_lower_score(self):
        # pin_first (pending_intent) gana al score: queda primera SIEMPRE.
        tools = ["browser", "media", "reminder"]
        scored = {"browser": 0.55, "media": 0.41, "reminder": 0.28}
        out = _antiprimacy_order(tools, scored, pin_first="reminder")
        self.assertEqual(out[0], "reminder")
        # el resto de dominio sí va por score.
        self.assertEqual(out, ["reminder", "browser", "media"])

    def test_pin_first_not_present_is_noop_on_pinning(self):
        # si la pending_intent no está en el subset, no pasa nada raro:
        # solo se ordena el dominio por score (el insert(0) lo hace el caller).
        tools = ["web", "browser"]
        scored = {"web": 0.30, "browser": 0.55}
        out = _antiprimacy_order(tools, scored, pin_first="reminder")
        self.assertEqual(out, ["browser", "web"])

    def test_unscored_tools_kept_after_scored_stable(self):
        # tools sin score (keyword-only / MCP / sin embedding) van DETRÁS de las
        # puntuadas y preservan su orden relativo de aparición (sort estable).
        tools = ["mcp__foo", "web", "mcp__bar", "browser"]
        scored = {"web": 0.30, "browser": 0.55}  # las mcp__ no tienen score
        out = _antiprimacy_order(tools, scored)
        self.assertEqual(out, ["browser", "web", "mcp__foo", "mcp__bar"])

    def test_ties_preserve_original_order(self):
        # empate de score -> orden de aparición original (estable).
        tools = ["alpha", "beta", "gamma"]
        scored = {"alpha": 0.40, "beta": 0.40, "gamma": 0.40}
        out = _antiprimacy_order(tools, scored)
        self.assertEqual(out, ["alpha", "beta", "gamma"])

    def test_empty_subset_is_safe(self):
        self.assertEqual(_antiprimacy_order([], {}), [])

    def test_flag_off_returns_input_unchanged(self):
        tools = ["web", "browser", "media"]
        scored = {"web": 0.30, "browser": 0.55, "media": 0.41}
        prev = os.environ.get("GEMMA4_ANTIPRIMACY")
        os.environ["GEMMA4_ANTIPRIMACY"] = "0"
        try:
            out = _antiprimacy_order(tools, scored)
            self.assertEqual(out, tools, "flag OFF must be a no-op (A/B en vivo)")
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_ANTIPRIMACY", None)
            else:
                os.environ["GEMMA4_ANTIPRIMACY"] = prev

    def test_pinned_and_infra_together(self):
        # caso completo: pending primero, dominio por score, infra al final.
        tools = ["session", "web", "reminder", "browser", "safety"]
        scored = {"web": 0.30, "browser": 0.55, "reminder": 0.28}
        out = _antiprimacy_order(tools, scored, pin_first="reminder")
        self.assertEqual(out, ["reminder", "browser", "web", "session", "safety"])


class TestAntiPrimacyIntegration(unittest.TestCase):
    """End-to-end por select_tool_names: el reorden NO debe romper invariantes
    existentes (pending_intent primero, set preservado, session al final)."""

    def _select(self, q: str, **kw):
        from ..routing.planner import select_tool_names, plan_mission
        return select_tool_names(q, plan_mission(q), **kw)

    def test_pending_intent_stays_first_after_reorder(self):
        # Hotfix F: una tool parkeada (needs_user) debe quedar PRIMERA aunque
        # el reorden anti-primacy corra después del cap.
        pi = {"tool": "media", "args": {"action": "play", "provider": "disney"},
              "asks_for": "profile"}
        for q in ["Mi perfil es Ema", "abre el navegador y pon música", "Ema"]:
            subset = self._select(q, safety_enabled=True, pending_intent=pi)
            self.assertEqual(subset[0], "media",
                             f"pending_intent debe quedar primera; q={q!r} -> {subset}")

    def test_session_always_last_when_present(self):
        # session es infra: nunca primera, va al final del subset.
        subset = self._select("abre el navegador", safety_enabled=False)
        self.assertIn("session", subset)
        self.assertNotEqual(subset[0], "session")

    def test_set_identical_flag_on_vs_off(self):
        # MISMO conjunto con la flag ON u OFF: el reorden solo cambia el ORDEN,
        # nunca QUÉ tools entran (el cap decide eso, intacto).
        queries = [
            "abre el navegador y reproducí música",
            "subí el volumen y abrí spotify",
            "qué hora es y mandá un correo",
            "abrí steam",
        ]
        prev = os.environ.get("GEMMA4_ANTIPRIMACY")
        try:
            for q in queries:
                os.environ["GEMMA4_ANTIPRIMACY"] = "1"
                on = self._select(q)
                os.environ["GEMMA4_ANTIPRIMACY"] = "0"
                off = self._select(q)
                self.assertEqual(set(on), set(off),
                                 f"set debe ser idéntico ON vs OFF; q={q!r} "
                                 f"on={on} off={off}")
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_ANTIPRIMACY", None)
            else:
                os.environ["GEMMA4_ANTIPRIMACY"] = prev


if __name__ == "__main__":
    unittest.main()
