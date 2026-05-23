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
        from gemma4_agent.intent_router import classify_intent, wants_knowledge
        isc = classify_intent("¿Qué es el Mortal Kombat?")
        self.assertIsNotNone(
            isc, "classify_intent devolvió None — el modelo de embeddings del "
                 "router no cargó (¿torchcodec/optimum/tensorflow instalado?).")
        self.assertGreater(isc.info, isc.action,
                           "una pregunta '¿qué es X?' debe puntuar info>action")
        self.assertTrue(wants_knowledge("¿Qué es el Mortal Kombat?"))

    def test_semantic_router_returns_tools(self):
        # Una query de acción debe surfacear tools (no lista vacía).
        from gemma4_agent.semantic_router import suggest_tools_scored
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


if __name__ == "__main__":
    unittest.main()
