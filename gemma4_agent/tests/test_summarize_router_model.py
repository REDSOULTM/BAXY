"""Bug 2026-05-22 (silent_fallback en traces): `_summarize_history_block` llamaba
a `self.client.chat(...)` SIN `model=`, así que en router-mode el cliente mandaba
el alias muerto "gemma-4" y el server respondía 400 ("model 'gemma-4' not found").
La summarization caía silenciosamente a truncado plano (mismo bug que se arregló
en chat_stream / forced-retry, pero este path quedó afuera).

Fix: pasar `model=self._router_model_for(msgs)` — el prompt es solo texto, así que
resuelve al preset -text. Estos tests fijan que el kwarg `model` viaja al cliente."""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.agent_core.agent import Gemma4Agent
from gemma4_agent.infra.config import AgentConfig


def _make_agent(tmp: Path) -> Gemma4Agent:
    cfg = dataclasses.replace(
        AgentConfig.from_env(),
        memory_path=tmp / "m.json", captures_dir=tmp / "cap",
        trace_path=tmp / "t.jsonl", state_path=tmp / "s.json",
        enable_tracing=False, enable_safety=False,
    )
    return Gemma4Agent(cfg)


class TestSummarizeRouterModel(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_summ_"))
        self.agent = _make_agent(self.tmp)
        self.captured: dict = {}

        def _chat(messages, **kw):
            self.captured["kw"] = kw
            return {"choices": [{"message": {"role": "assistant",
                                             "content": "Resumen."}}]}
        self.agent.client.chat = _chat

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_passes_router_model_kwarg(self):
        # Router mode resolves vram4-text; the summarizer must send THAT, never
        # default to the dead "gemma-4" alias.
        with mock.patch.object(self.agent, "_router_model_for",
                               return_value="vram4-text") as rm:
            out = self.agent._summarize_history_block(
                [{"role": "user", "content": "abre la calculadora"},
                 {"role": "assistant", "content": "Listo."}])
        self.assertEqual(out, "Resumen.")
        self.assertIn("model", self.captured["kw"],
                      "summarizer must pass an explicit model= to the client")
        self.assertEqual(self.captured["kw"]["model"], "vram4-text")
        rm.assert_called_once()

    def test_non_router_passes_none(self):
        # Plain (non-router) server: _router_model_for returns None, which lets
        # the client use the configured default. Still an EXPLICIT kwarg.
        with mock.patch.object(self.agent, "_router_model_for", return_value=None):
            self.agent._summarize_history_block(
                [{"role": "user", "content": "hola"}])
        self.assertIn("model", self.captured["kw"])
        self.assertIsNone(self.captured["kw"]["model"])


if __name__ == "__main__":
    unittest.main()
