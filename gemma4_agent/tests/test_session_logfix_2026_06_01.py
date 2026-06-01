"""Fixes nacidos de revisar la sesión en vivo 22:56-23:00 (2026-05-31/06-01).

#1 knowledge vacío: "¿Cuántos segundos hay en un minuto?" -> el forced_tool_retry forzó
   knowledge.search (base personal) -> 0 resultados -> content_verified=False -> el
   pipeline lo trató como tool-fallido -> el 4B dijo "No pude encontrar". Fix: una
   búsqueda vacía NO es un fallo de verificación; no marcamos content_verified=False y
   guiamos al LLM con una nota para que responda de su conocimiento general.
   (Verificado EN VIVO: 3/3 -> "Hay sesenta segundos en un minuto".)

#3 media spotify: "pon una canción en Spotify" sin username -> play GLOBAL por tecla de
   media (sin deeplink/auto_play_info) -> caía al catch-all del verifier (confirmed=False)
   -> "No pude verificar la reproducción". Fix: una tecla de media dispatcheada es
   confirmed=None ("dispatched", como pause/next o el deeplink de YouTube), no un fallo.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.memory_pkg.knowledge import KnowledgeStore
from gemma4_agent.tools_pkg.tools import _has_unverified_signal
from gemma4_agent.safety_pkg.verifiers import verify_media


class KnowledgeEmptyNotFailureTest(unittest.TestCase):
    def test_empty_search_is_not_flagged_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            store = KnowledgeStore(path=Path(d) / "knowledge.db")
            r = store.search("cuantos segundos hay en un minuto", rerank=False)
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 0)
        # NO debe marcarse content_verified=False (eso lo hacía parecer tool-fallido)
        self.assertNotEqual(r.get("content_verified"), False)
        # debe guiar al LLM a responder de su conocimiento general
        self.assertIn("note", r)
        # CLAVE: el pipeline NO lo trata como no-verificado (no -> needs_verification)
        self.assertFalse(_has_unverified_signal(r))

    def test_nonempty_keeps_content_verified(self):
        with tempfile.TemporaryDirectory() as d:
            store = KnowledgeStore(path=Path(d) / "knowledge.db")
            store.ingest_text("Un minuto tiene sesenta segundos exactos.",
                              source="t", title="t")
            r = store.search("segundos minuto", rerank=False)
        self.assertGreaterEqual(r["count"], 1)
        self.assertTrue(r.get("content_verified"))


class VerifyMediaGlobalPlayKeyTest(unittest.TestCase):
    def test_global_play_key_is_dispatched_not_failed(self):
        # play GLOBAL por tecla de media (sin deeplink) -> confirmed=None (dispatched)
        out = verify_media(
            {"action": "play", "provider": "spotify"},
            {"ok": True, "action": "play", "provider": "spotify",
             "mode": "global_play_key", "played": True},
        )
        self.assertIsNone(out.confirmed, f"esperaba confirmed=None, fue {out}")

    def test_play_with_no_evidence_still_unconfirmed(self):
        # sin played ni deeplink ni auto_play -> sigue siendo no confirmable (None),
        # NO un éxito falso
        out = verify_media({"action": "play"}, {"ok": True, "action": "play"})
        self.assertIsNone(out.confirmed)


if __name__ == "__main__":
    unittest.main()
