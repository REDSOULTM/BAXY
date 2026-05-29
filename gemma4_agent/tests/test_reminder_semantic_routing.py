"""Anti-regresión del fix de routing reminder/notification (2026-05-29, gap harness).

"recordame [ACCIÓN] [TIEMPO]" (recordame comprar pan a las 5) debe rankear
notification/reminder POR ENCIMA de memory; "recordame que [HECHO/preferencia]"
(recordame que prefiero el café) debe rankear memory por encima de notification.
El discriminador es ACCIÓN+TIEMPO vs HECHO, codificado multilingüemente en las
TOOL_DESCRIPTIONS del semantic_router (mecanismo aprobado CLAUDE.md §3 — NO
keyword-list). Test determinista (encoder fijo, CPU); el efecto en vivo lo valida
scripts/_validate_reminder_routing_live.py.

NOTA medida: el RANKING está arreglado (este test), pero el 4B no-determinista a
veces elige el ruido del subset (session siempre-presente by-design, o browser por
el verbo 'comprar'->tienda). Eso es deuda del planner-subset, no del ranking.
"""
import unittest

from ..routing import semantic_router as sr
from ..routing import planner as pl

# fraseos donde el recordatorio es una ACCIÓN futura con tiempo -> notification/reminder
ACTION_TIME = [
    "recordame comprar pan a las 5",
    "recordame llamar a mamá en una hora",
    "recordame sacar la basura mañana",
]
# fraseos donde "recordame que..." declara un HECHO/preferencia -> memory
FACTS = [
    "recordame que prefiero el café sin azúcar",
    "recordame que mi color favorito es el azul",
]


def _scored(q: str) -> dict[str, float]:
    return dict(sr.suggest_tools_scored(q, k=15, min_score=0.0))


class TestReminderSemanticRanking(unittest.TestCase):
    def test_action_time_ranks_reminder_above_memory(self):
        for q in ACTION_TIME:
            s = _scored(q)
            best_rem = max(s.get("notification", 0.0), s.get("reminder", 0.0))
            self.assertGreater(
                best_rem, s.get("memory", 0.0),
                f"{q!r}: notification/reminder ({best_rem:.2f}) debe superar "
                f"memory ({s.get('memory', 0.0):.2f})")

    def test_action_time_reminder_in_top3(self):
        for q in ACTION_TIME:
            top3 = [n for n, _ in sr.suggest_tools_scored(q, k=3, min_score=0.0)]
            self.assertTrue(
                "notification" in top3 or "reminder" in top3,
                f"{q!r}: ni notification ni reminder en top-3 ({top3})")

    def test_facts_rank_memory_above_notification(self):
        for q in FACTS:
            s = _scored(q)
            self.assertGreater(
                s.get("memory", 0.0), s.get("notification", 0.0),
                f"{q!r}: memory ({s.get('memory', 0.0):.2f}) debe superar "
                f"notification ({s.get('notification', 0.0):.2f})")


class TestReminderInFinalSubset(unittest.TestCase):
    """El subset que recibe el 4B debe CONTENER reminder o notification para
    pedidos de recordatorio-con-tiempo (que la tool correcta esté disponible;
    que el 4B la elija es otra capa, no-determinista)."""
    def test_reminder_or_notification_reaches_the_model(self):
        for q in ACTION_TIME:
            plan = pl.plan_mission(q)
            subset = pl.select_tool_names(q, plan)
            self.assertTrue(
                "reminder" in subset or "notification" in subset,
                f"{q!r}: subset {subset} no ofrece reminder/notification al 4B")


if __name__ == "__main__":
    unittest.main()
