"""Tests del chaining-nudge (Problema B): empujar a encadenar search→acción.

Bug sesión #847: filesystem.search encontró el .docx pero el modelo (E4B, 4B)
NO encadenó office.open — paró en "ya busqué". El nudge inyecta un [system note]
tras una búsqueda EXITOSA con items para que use el primer resultado.
"""
from __future__ import annotations

import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

from gemma4_agent.agent import Gemma4Agent, ToolEvent
from gemma4_agent.config import AgentConfig


def _nudge(raw_calls, evs):
    ag = Gemma4Agent.__new__(Gemma4Agent)
    return ag._chaining_nudge(raw_calls, evs)


def _clarify(evs, text):
    ag = Gemma4Agent.__new__(Gemma4Agent)
    return ag._filesystem_search_clarification(evs, text)


class ChainingNudgeTest(unittest.TestCase):
    def test_fires_on_search_with_results(self):
        rc = [{"function": {"name": "filesystem"}}]
        ev = [ToolEvent(name="filesystem", args={"action": "search"},
                        result={"ok": True, "action": "search",
                                "paths": ["C:/a.docx"]})]
        self.assertIsNotNone(_nudge(rc, ev))

    def test_silent_on_empty_search(self):
        # vacío -> el honesty guard responde "no encontré nada", sin nudge
        rc = [{"function": {"name": "filesystem"}}]
        ev = [ToolEvent(name="filesystem", args={"action": "search"},
                        result={"ok": True, "action": "search", "paths": []})]
        self.assertIsNone(_nudge(rc, ev))

    def test_silent_on_terminal_tool(self):
        rc = [{"function": {"name": "app"}}]
        ev = [ToolEvent(name="app", args={"action": "open"},
                        result={"ok": True, "action": "open"})]
        self.assertIsNone(_nudge(rc, ev))

    def test_silent_on_failed_search(self):
        rc = [{"function": {"name": "filesystem"}}]
        ev = [ToolEvent(name="filesystem", args={},
                        result={"ok": False, "action": "search"})]
        self.assertIsNone(_nudge(rc, ev))

    def test_fires_on_local_search_matches(self):
        rc = [{"function": {"name": "local_search"}}]
        ev = [ToolEvent(name="local_search", args={"action": "find"},
                        result={"ok": True, "action": "find",
                                "matches": ["song1.mp3"]})]
        self.assertIsNotNone(_nudge(rc, ev))


class FilesystemSearchClarificationTest(unittest.TestCase):
    def test_asks_which_file_to_open_after_search_results(self):
        ev = [ToolEvent(name="filesystem", args={"action": "search"},
                        result={"ok": True, "action": "search",
                                "paths": ["C:/Users/u/Downloads/a.docx",
                                          "C:/Users/u/Downloads/b.docx"]})]
        out = _clarify(ev, "abre el primer Word en Descargas")
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["target_tool"], "office")
        self.assertIn("Cual queres abrir", out["content"])
        self.assertIn("1. a.docx - C:/Users/u/Downloads/a.docx", out["content"])
        self.assertEqual(out["args"]["candidates"][0],
                         "C:/Users/u/Downloads/a.docx")

    def test_relative_paths_are_resolved_against_search_root(self):
        ev = [ToolEvent(name="filesystem", args={"action": "search"},
                        result={"ok": True, "action": "search",
                                "root": "C:/Users/u/Downloads",
                                "matches": [{"path": "sub/a.docx"}]})]
        out = _clarify(ev, "abrir documento")
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("Downloads", out["content"])
        self.assertIn("sub", out["args"]["candidates"][0])

    def test_search_only_request_does_not_ask_to_open(self):
        ev = [ToolEvent(name="filesystem", args={"action": "search"},
                        result={"ok": True, "action": "search",
                                "paths": ["C:/Users/u/Downloads/a.docx"]})]
        self.assertIsNone(_clarify(ev, "busca Word en Descargas"))

    def test_non_filesystem_latest_event_does_not_trigger(self):
        ev = [
            ToolEvent(name="filesystem", args={"action": "search"},
                      result={"ok": True, "action": "search",
                              "paths": ["C:/Users/u/Downloads/a.docx"]}),
            ToolEvent(name="app", args={"action": "open"},
                      result={"ok": True, "action": "open"}),
        ]
        self.assertIsNone(_clarify(ev, "abre el primer Word en Descargas"))


class FilesystemSearchClarificationFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_chain_"))
        cfg = dataclasses.replace(
            AgentConfig.from_env(),
            memory_path=self.tmp / "memory.json",
            captures_dir=self.tmp / "captures",
            trace_path=self.tmp / "trace.jsonl",
            state_path=self.tmp / "state.json",
            enable_tracing=False,
            enable_safety=False,
        )
        self.agent = Gemma4Agent(cfg)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_text_asks_when_model_stops_after_search(self):
        first = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call_search",
                        "type": "function",
                        "function": {
                            "name": "filesystem",
                            "arguments": '{"action":"search","path":"Downloads","pattern":"*.docx"}',
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
        }
        second = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "Ya encontre archivos.",
                    "tool_calls": [],
                },
                "finish_reason": "stop",
            }],
        }
        self.agent.client.chat = MagicMock(side_effect=[first, second])
        self.agent.tools.execute = MagicMock(return_value={
            "ok": True,
            "action": "search",
            "root": "C:/Users/u/Downloads",
            "paths": ["C:/Users/u/Downloads/a.docx"],
        })

        def _fake_select(*_args, **_kwargs):
            return ["filesystem", "office"]
        _fake_select._last_fallback_used = False

        with mock.patch("gemma4_agent.agent.select_tool_names", _fake_select):
            reply = self.agent.run_text("abre el primer Word en Descargas")

        self.assertIn("Cual queres abrir", reply.content)
        self.assertIn("a.docx", reply.content)
        pending = self.agent.state.get_pending_intent(self.agent._turn_counter + 1)
        self.assertIsNotNone(pending)
        assert pending is not None
        self.assertEqual(pending["tool"], "office")
        self.assertEqual(pending["asks_for"], "file_selection")


if __name__ == "__main__":
    unittest.main()
