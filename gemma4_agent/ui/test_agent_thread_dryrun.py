"""Dry-run for the Qt AgentWorker bridge.

No llama-server, no real Gemma4Agent, no widgets. The goal is to pin that a
finished AgentReply reaches the GUI-facing signals and activity log tags.
"""
from __future__ import annotations

import time
import unittest
from dataclasses import dataclass, field
from typing import Any

from PyQt6.QtCore import QCoreApplication

from gemma4_agent.agent import AgentReply, ToolEvent
from gemma4_agent.ui.agent_thread import AgentWorker


@dataclass
class _FakeAgent:
    calls: list[str] = field(default_factory=list)

    def run_text(self, text: str, *, images=None, audios=None, progress=None) -> AgentReply:
        self.calls.append(text)
        if progress is not None:
            progress("start", {"mode": "fast_action"})
            progress("tool_subset", {"schema_count": 2, "tools": ["filesystem", "office"]})
            progress("tool_start", {"name": "filesystem", "args": {"action": "search"}})
            progress("tool_end", {"name": "filesystem", "ok": True, "status": "ok"})
            progress("final", {})
        return AgentReply(
            content=(
                "Encontre estos archivos:\n"
                "1. a.docx - C:/Users/u/Downloads/a.docx\n"
                "Cual queres abrir? Responde con el numero o el nombre."
            ),
            tool_events=[
                ToolEvent(
                    name="filesystem",
                    args={"action": "search"},
                    result={"ok": True, "action": "search"},
                )
            ],
        )


class _DryAgentWorker(AgentWorker):
    def _build_agent(self) -> None:
        self._agent = _FakeAgent()
        self._config = type("Cfg", (), {"server_url": "mock://llama"})()
        self.connection_changed.emit(True)
        self.state_changed.emit("IDLE")


class AgentWorkerDryRunTest(unittest.TestCase):
    def test_reply_content_progress_and_logs_reach_gui_signals(self) -> None:
        app = QCoreApplication.instance() or QCoreApplication([])
        worker = _DryAgentWorker()
        seen: dict[str, list[Any]] = {
            "logs": [],
            "states": [],
            "progress": [],
            "replies": [],
            "errors": [],
            "connected": [],
        }
        worker.log.connect(lambda text, tag: seen["logs"].append((text, tag)))
        worker.state_changed.connect(lambda state: seen["states"].append(state))
        worker.progress.connect(lambda event, payload: seen["progress"].append((event, dict(payload))))
        worker.reply_ready.connect(lambda content, events: seen["replies"].append((content, list(events))))
        worker.llm_error.connect(lambda msg: seen["errors"].append(msg))
        worker.connection_changed.connect(lambda ok: seen["connected"].append(ok))

        worker.start()
        worker.submit("Abre el primer Word que encuentres en mi carpeta de Descargas")

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not seen["replies"] and not seen["errors"]:
            app.processEvents()
            time.sleep(0.01)
        worker.stop()
        worker.wait(2000)
        app.processEvents()

        self.assertFalse(seen["errors"])
        self.assertEqual(len(seen["replies"]), 1)
        content, events = seen["replies"][0]
        self.assertIn("Cual queres abrir", content)
        self.assertEqual(len(events), 1)
        self.assertIn(True, seen["connected"])
        self.assertIn("SPEAKING", seen["states"])
        self.assertIn("IDLE", seen["states"])
        self.assertIn(("Abre el primer Word que encuentres en mi carpeta de Descargas", "you"), seen["logs"])
        self.assertTrue(any(tag == "tool" and text.startswith("filesystem(") for text, tag in seen["logs"]))
        self.assertIn((content, "ai"), seen["logs"])
        self.assertTrue(any(event == "final" for event, _payload in seen["progress"]))


if __name__ == "__main__":
    unittest.main()
