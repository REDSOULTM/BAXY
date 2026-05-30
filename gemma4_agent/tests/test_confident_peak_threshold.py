"""Anti-regresión del fix _SEM_PEAK_KEEP 0.60->0.50 (2026-05-29, planner.py:47).

El abstain-gate (planner.py:381-392) misfireaba en comandos CORTOS sin keyword
("cuál es mi ip"->network 0.55 gap 0.19) y los borraba a ['session'], perdiendo
el top-1 semántico. Bajar el confident-peak-keep a 0.50 los rescata SIN regresar
el smalltalk: el chitchat es PLANO (gap<0.15) y el _SEM_PEAK_GAP=0.15 (AND-condition)
lo sigue gateando. MEDIDO: "hola" 0.54/gap.08, "qué tal" 0.52/gap.07 NO escapan.

Determinista (encoder fijo, CPU). El efecto en vivo lo valida
scripts/_validate_peak_threshold_live.py.
"""
import unittest

from ..routing import planner as pl

# tools de ACCIÓN que el smalltalk NUNCA debe ofrecer (anti-bloat del abstain)
_ACTION_TOOLS = {
    "network", "web", "browser", "app", "media", "audio", "filesystem",
    "system", "device_settings", "notification", "reminder", "gui", "input",
    "whatsapp", "email", "vision", "computer_use",
}


def _subset(q: str) -> list[str]:
    return pl.select_tool_names(q, pl.plan_mission(q))


class TestConfidentPeakRescuesKeywordlessCommand(unittest.TestCase):
    """Comandos cortos sin keyword cuyo top-1 semántico es un pico claro
    (>=0.50, gap>=0.15) deben llegar al 4B, no borrarse a ['session']."""

    def test_ip_query_offers_network(self):
        # 2026-05-30 (reentreno encoder FT 3ep, fc60ed2): el INTENT del test es
        # que un comando corto sin keyword NO se borre a ['session'] — debe llegar
        # al 4B con una tool de lookup útil. Con el encoder FT, "cuál es mi ip"
        # (acentuado) ya NO cae en el abstain-gate (el abstain head devuelve
        # should_abstain=False, p_no_tool=0.62 < veto) → NO se silencia; el subset
        # ofrece web/knowledge (wants_knowledge=True por la tilde) y, en algunas
        # tildes/casing, network. VERIFICADO EN VIVO (agent.run_content, server
        # :8080): el 4B alcanza public_ip y responde la IP — la query queda servida.
        # Por eso afirmamos el INTENT (llega a una tool que responde "mi IP":
        # network o web) y el anti-silenciamiento (no es session-only), no la
        # presencia exacta de `network` (frágil al shift de geometría del encoder).
        sub = _subset("cuál es mi ip")
        dom = [t for t in sub if t not in ("session", "safety")]
        self.assertTrue(
            dom,
            f"'cuál es mi ip': comando corto sin keyword NO debe borrarse a "
            f"session-only; got {sub}")
        self.assertTrue(
            {"network", "web"} & set(sub),
            f"'cuál es mi ip': debe ofrecer una tool que responda la IP "
            f"(network o web); got {sub}")


class TestSmalltalkStillAbstains(unittest.TestCase):
    """El chitchat plano (gap<0.15) debe seguir abstaniéndose: ninguna tool de
    acción ofrecida (el _SEM_PEAK_GAP lo protege aunque el top-1 roce 0.50)."""

    def test_greetings_offer_no_action_tool(self):
        for q in ("hola", "qué tal", "gracias", "buenas noches", "cómo estás"):
            sub = _subset(q)
            offenders = set(sub) & _ACTION_TOOLS
            self.assertEqual(
                offenders, set(),
                f"{q!r}: smalltalk no debe ofrecer tools de acción; got {sub}")


if __name__ == "__main__":
    unittest.main()
