"""TraceLogger is DIAGNOSTICS — it must never crash the agent it traces.
event() is called dozens of times per turn; a write failure (full disk, locked
file, unwritable path) or a non-serializable payload must be swallowed, and
construction with a bad path must disable rather than raise out of the agent
constructor."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.tracing import TraceLogger


class TestTracingFailsafe(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_construct_on_unwritable_path_disables(self):
        # Parent is a FILE -> mkdir would raise. Must disable, not crash.
        blocker = self.dir / "blocker"
        blocker.write_text("x")
        t = TraceLogger(path=blocker / "traces.jsonl", enabled=True)
        self.assertFalse(t.enabled)
        # And event() on the disabled logger is a no-op.
        t.event("turn1", "llm_start", foo="bar")  # must not raise

    def test_construct_on_malformed_path_disables(self):
        # A path with an embedded null byte raises ValueError (not OSError) from
        # the OS layer. At the filesystem boundary ANY failure to prepare the
        # path must disable tracing, never crash the agent constructor.
        t = TraceLogger(path=Path("Z:/x\0bad/traces.jsonl"), enabled=True)
        self.assertFalse(t.enabled)
        t.event("turn1", "llm_start", foo="bar")  # must not raise

    def test_event_swallows_write_failure(self):
        t = TraceLogger(path=self.dir / "t.jsonl", enabled=True)
        # Repoint to an unwritable path AFTER construction to force a write fail.
        blocker = self.dir / "blocker2"
        blocker.write_text("x")
        t.path = blocker / "nope.jsonl"
        t.event("turn1", "llm_start", foo="bar")  # must not raise

    def test_event_swallows_nonserializable_payload(self):
        t = TraceLogger(path=self.dir / "t2.jsonl", enabled=True)
        # Even if _json_safe misses something, event() must not raise.
        t.event("turn1", "weird", obj=object(), mixed={1: "a", "b": 2})  # no raise

    def test_healthy_path_still_writes(self):
        p = self.dir / "good.jsonl"
        t = TraceLogger(path=p, enabled=True)
        t.event("turn1", "llm_start", foo="bar")
        self.assertTrue(p.exists())
        self.assertIn("llm_start", p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
