"""Regresión 2026-06-02: la casilla de chat NO debe desbloquearse hasta que el
router semántico esté listo (no solo el warmup del llama-server).

Contexto (reportado por el usuario): al iniciar la UI, la casilla de texto se
desbloqueaba apenas terminaba el warmup del llama-server, PERO el router
(BertModel + embeddings + abstain/tool head + reranker) seguía cargando en un
thread de background sin join → el primer turno caía al fallback léxico o pagaba
la carga del router en el camino crítico.

FIX: AgentRunner expone is_router_ready() (latch _router_ready); _build_agent
joinea el thread del router con timeout antes de publicar ready:True; y los dos
PULL de server.py (/agent/status, WS handshake) suman is_router_ready() al AND
del gate. Estos tests fijan el CONTRATO del latch (no boot real, que es lento).
"""
from __future__ import annotations

import inspect
import unittest


def _runner_cls():
    import gemma4_agent.agent_core.agent_runner as ar
    cls = [v for v in vars(ar).values()
           if inspect.isclass(v) and hasattr(v, "is_router_ready")]
    assert cls, "no se encontró la clase AgentRunner con is_router_ready"
    return cls[0]


class ReadyGateLatchContract(unittest.TestCase):
    def test_runner_exposes_router_latch(self):
        Runner = _runner_cls()
        r = Runner()
        # los atributos del latch existen y arrancan "no listo".
        self.assertTrue(hasattr(r, "_router_ready"))
        self.assertTrue(hasattr(r, "_router_thread"))
        self.assertFalse(r.is_router_ready(),
                         "is_router_ready debe arrancar False (router sin cargar)")
        self.assertFalse(r.is_warmed_up(),
                         "is_warmed_up debe arrancar False")

    def test_timeout_constant_is_sane(self):
        import gemma4_agent.agent_core.agent_runner as ar
        # el timeout del join existe y cubre el peor caso documentado (~20-35s).
        self.assertGreaterEqual(ar.ROUTER_JOIN_TIMEOUT_S, 30.0,
                                "el timeout del join debe cubrir el peor caso del router")

    def test_join_block_present_in_build_agent(self):
        # El gate debe joinear el thread del router ANTES de publicar ready.
        # Verificamos estructuralmente que _build_agent contiene el join con
        # el timeout (mide que la red sigue cableada, no su timing).
        Runner = _runner_cls()
        src = inspect.getsource(Runner._build_agent)
        self.assertIn("ROUTER_JOIN_TIMEOUT_S", src,
                      "_build_agent ya no joinea el router con el timeout")
        self.assertIn("_router_thread", src,
                      "_build_agent no referencia el handle del router")
        # y el latch se prende en un finally del thread (degradado-tolerado).
        self.assertIn("_router_ready", src)

    def test_server_pull_paths_include_router_in_gate(self):
        # Los 2 PULL de server.py deben incluir is_router_ready() en el AND de
        # ready (si no, un cliente tardío / el poll abren la casilla sin router).
        import gemma4_agent.infra.server as server
        src = inspect.getsource(server)
        # debe haber al menos 2 usos de is_router_ready() en el cómputo del gate.
        self.assertGreaterEqual(
            src.count("is_router_ready()"), 2,
            "los PULL de /agent/status y WS handshake deben gatear por el router")
        # y ready ya no se computa solo con warmed and healthy sin el router.
        self.assertNotIn("built and warmed and healthy,", src,
                         "quedó un PULL que computa ready SIN is_router_ready()")


if __name__ == "__main__":
    unittest.main()
