"""Guardia: el SEMANTIC ROUTER debe cargar su modelo de embeddings.

Regresión del 2026-05-23: instalar `torchcodec` (para descargar FLEURS audio)
inyectó una dependencia de libtorchcodec/FFmpeg en el import chain de
sentence-transformers. Resultado: semantic_router._ensure_loaded() crasheaba con
'Could not load libtorchcodec', classify_intent devolvía None y suggest_tools
devolvía [], así que CADA query se mis-ruteaba (ej. '¿qué es Mortal Kombat?'
terminó creando un documento en vez de buscar en la web).

Mismo tipo de breakage que optimum/tensorflow (CLAUDE.md: 'NO instalar optimum/
tensorflow en runtime 3.10 — rompe ST->router vacío'). Estos tests fallan si el
router no puede clasificar/rutear, dando una señal temprana.
"""
from __future__ import annotations

import unittest


class RouterLoadHealthTest(unittest.TestCase):
    def test_intent_classifier_works(self):
        # Una pregunta informativa clara debe clasificarse como info, no acción.
        from gemma4_agent.routing.intent_router import classify_intent, wants_knowledge
        isc = classify_intent("¿Qué es el Mortal Kombat?")
        self.assertIsNotNone(
            isc, "classify_intent devolvió None — el modelo de embeddings del "
                 "router no cargó (¿torchcodec/optimum/tensorflow instalado?).")
        self.assertGreater(isc.info, isc.action,
                           "una pregunta '¿qué es X?' debe puntuar info>action")
        self.assertTrue(wants_knowledge("¿Qué es el Mortal Kombat?"))

    def test_semantic_router_returns_tools(self):
        # Una query de acción debe surfacear tools (no lista vacía).
        from gemma4_agent.routing.semantic_router import suggest_tools_scored
        scored = suggest_tools_scored("abre Spotify", k=8)
        self.assertTrue(
            scored, "suggest_tools_scored devolvió [] — el modelo del router no "
                    "cargó. Revisá torchcodec/optimum/tensorflow en el venv.")

    def test_torchcodec_not_installed(self):
        # torchcodec NO debe estar en el runtime: rompe sentence-transformers.
        import importlib.util
        self.assertIsNone(
            importlib.util.find_spec("torchcodec"),
            "torchcodec está instalado y ROMPE el router. Ejecutá: "
            "pip uninstall torchcodec. El downloader de FLEURS usa decode=False "
            "+ soundfile y NO lo necesita.")

    def test_torchvision_version_matches_torch_or_absent(self):
        # torchvision NO se usa en runtime (router es solo texto). Si está
        # presente con versión incompatible con torch, escupe el warning
        # 'Failed to load image Python extension' al arrancar. Debe estar
        # AUSENTE, o alineado con torch. (2026-05-23: 0.16.2+cu121 vs torch
        # 2.10+cpu daba el warning -> desinstalado.)
        import importlib.util
        if importlib.util.find_spec("torchvision") is None:
            return  # ausente: correcto, no se necesita
        import torch, torchvision
        tv_major_minor = ".".join(torchvision.__version__.split("+")[0].split(".")[:2])
        # torchvision 0.16 ~ torch 2.1; 0.21 ~ torch 2.6; etc. Si está, que
        # cargue su extensión sin error (proxy de compatibilidad de ABI).
        try:
            import torchvision.transforms  # noqa: F401
        except Exception as exc:  # pragma: no cover
            self.fail(f"torchvision {torchvision.__version__} incompatible con "
                      f"torch {torch.__version__} ({exc}). Desinstalalo "
                      f"(no se usa) o alinealo: pip install torchvision compatible.")

    def test_router_health_reports_ok(self):
        from gemma4_agent.routing.intent_router import router_health
        ok, detail = router_health()
        self.assertTrue(ok, f"router_health falló: {detail}")


class LexicalGateTest(unittest.TestCase):
    """Gate interrogativo zero-ML + fallback cuando el modelo está caído."""

    def test_questions_detected(self):
        from gemma4_agent.routing.intent_router import is_question_lexical
        for q in ["¿qué es el Mortal Kombat?", "what is python",
                  "quién ganó el mundial", "por qué el cielo es azul"]:
            is_q, conf = is_question_lexical(q)
            self.assertTrue(is_q, f"{q!r} debería ser pregunta")
            self.assertGreaterEqual(conf, 0.55)

    def test_commands_not_questions(self):
        from gemma4_agent.routing.intent_router import is_question_lexical
        # comandos (aun con forma interrogativa) NO son pregunta-info
        for cmd in ["abre Spotify", "pon música", "¿podés abrir Chrome?",
                    "mandale un mensaje a Juan"]:
            is_q, _ = is_question_lexical(cmd)
            self.assertFalse(is_q, f"{cmd!r} es acción, no pregunta")

    def test_fallback_when_model_down(self):
        # Si classify_intent → None (router caído, p.ej. torchcodec),
        # wants_knowledge debe usar el léxico, NO devolver False y mis-rutear.
        import gemma4_agent.routing.intent_router as ir
        orig = ir.classify_intent
        try:
            ir.classify_intent = lambda t: None
            self.assertTrue(ir.wants_knowledge("¿qué es el Mortal Kombat?"))
            self.assertTrue(ir.wants_knowledge("what is python"))
            self.assertFalse(ir.wants_knowledge("abre Spotify"))
        finally:
            ir.classify_intent = orig


if __name__ == "__main__":
    unittest.main()
