"""Fact-extraction (opt-in via GEMMA4_AGENT_FACT_EXTRACTION) runs a 2nd LLM call
(~200 tok) that does NOT contribute to the user's reply. It used to run SYNCHRONOUS
before `return AgentReply`, adding its decode to the latency the user waits for.
Now it runs in a daemon thread — the reply returns immediately.

EJE del norte rector: LATENCIA (saca un LLM call del camino crítico del reply)
SIN tocar FIABILIDAD: la persistencia (memory.auto_save) tiene su propio lock; un
fallo en el thread se traza, no rompe el turno (que ya retornó). Pin: con
fact-extraction ON, run_text retorna ANTES de que el call de extracción termine."""
from __future__ import annotations

import dataclasses
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

from gemma4_agent.agent_core.agent import AgentReply, Gemma4Agent
from gemma4_agent.infra.config import AgentConfig


class TestFactExtractionOffPath(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_ft_"))
        cfg = dataclasses.replace(
            AgentConfig.from_env(),
            memory_path=self.tmp / "m.json", captures_dir=self.tmp / "cap",
            trace_path=self.tmp / "t.jsonl", state_path=self.tmp / "s.json",
            enable_tracing=False, enable_safety=False,
        )
        self.agent = Gemma4Agent(cfg)
        self._prev = os.environ.get("GEMMA4_AGENT_FACT_EXTRACTION")
        os.environ["GEMMA4_AGENT_FACT_EXTRACTION"] = "true"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("GEMMA4_AGENT_FACT_EXTRACTION", None)
        else:
            os.environ["GEMMA4_AGENT_FACT_EXTRACTION"] = self._prev
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reply_returns_before_extraction_finishes(self):
        # The main reply chat() is instant; the fact-extraction chat() blocks on
        # an event we control. If extraction were on the critical path, run_text
        # would block on it; with the daemon thread it returns immediately.
        gate = threading.Event()
        extract_started = threading.Event()

        def _chat(messages, **kw):
            # Detect the fact-extraction call by its distinctive prompt; block it
            # so we can prove the reply doesn't wait for it. All OTHER calls
            # (the turn itself) return instantly.
            is_extract = any("Extrae 0 a 3 hechos" in str(m.get("content") or "")
                             for m in messages)
            if is_extract:
                extract_started.set()
                gate.wait(timeout=5)
                return {"choices": [{"message": {"role": "assistant",
                        "content": "[]", "tool_calls": []}, "finish_reason": "stop"}]}
            return {"choices": [{"message": {"role": "assistant",
                    "content": "Tu color favorito es el azul, anotado.",
                    "tool_calls": []}, "finish_reason": "stop"}]}

        self.agent.client.chat = _chat
        # Warm: the FIRST turn pays the one-shot router/encoder load (~6-8s),
        # unrelated to fact-extraction. "hola" is <5 words so it never triggers
        # extraction (the guard skips short turns) — clean warm.
        self.agent.run_text("hola")
        self.assertFalse(extract_started.is_set(), "warm turn must not extract")
        t0 = time.time()
        reply = self.agent.run_text("mi color favorito es el azul y vivo en Madrid")
        elapsed = time.time() - t0
        # Reply must come back fast — NOT blocked on the 5s extraction gate.
        self.assertIsInstance(reply, AgentReply)
        self.assertIn("azul", reply.content)
        self.assertLess(elapsed, 2.0, "reply must not wait for fact-extraction")
        # The extraction DID start in the background (best-effort; allow a beat).
        started = extract_started.wait(timeout=3)
        gate.set()  # release the bg thread so it doesn't linger
        self.assertTrue(started, "fact-extraction should run in the background")


if __name__ == "__main__":
    unittest.main()
