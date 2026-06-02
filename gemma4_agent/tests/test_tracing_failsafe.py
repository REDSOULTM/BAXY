"""TraceLogger is DIAGNOSTICS — it must never crash the agent it traces.
event() is called dozens of times per turn; a write failure (full disk, locked
file, unwritable path) or a non-serializable payload must be swallowed, and
construction with a bad path must disable rather than raise out of the agent
constructor."""
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.infra.tracing import TraceLogger


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


class TestPersistentHandle(unittest.TestCase):
    """Latency fix (2026-06-02): event() holds a persistent append handle
    instead of open/write/close per call. These guard the new behavior:
    the handle is reused, flushed (so reads see lines immediately), reopened
    when .path changes or after rotation, and recovered if it goes bad."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_handle_is_reused_not_reopened_per_event(self):
        # The whole point of the fix: open() must NOT be called per event().
        p = self.dir / "reuse.jsonl"
        t = TraceLogger(path=p, enabled=True)
        real_open = Path.open
        calls = {"n": 0}

        def counting_open(self_path, *a, **k):
            # Count only opens of the active trace file.
            if Path(self_path) == p:
                calls["n"] += 1
            return real_open(self_path, *a, **k)

        with mock.patch.object(Path, "open", counting_open):
            for i in range(50):
                t.event(f"turn{i}", "tiny")
        # 50 events -> exactly ONE open of the active file (lazy, first event).
        self.assertEqual(calls["n"], 1)
        # All 50 lines are durable (flush per event).
        self.assertEqual(len(p.read_text(encoding="utf-8").splitlines()), 50)

    def test_lines_are_flushed_and_visible_immediately(self):
        p = self.dir / "flush.jsonl"
        t = TraceLogger(path=p, enabled=True)
        t.event("turn1", "first")
        # No close() yet — must still be on disk thanks to flush.
        self.assertIn("first", p.read_text(encoding="utf-8"))
        t.event("turn1", "second")
        self.assertIn("second", p.read_text(encoding="utf-8"))

    def test_handle_reopens_when_path_repointed(self):
        # Tests/callers mutate .path directly; the held handle must follow it.
        p1 = self.dir / "one.jsonl"
        p2 = self.dir / "two.jsonl"
        t = TraceLogger(path=p1, enabled=True)
        t.event("turn1", "to_one")
        t.path = p2
        t.event("turn1", "to_two")
        self.assertIn("to_one", p1.read_text(encoding="utf-8"))
        self.assertIn("to_two", p2.read_text(encoding="utf-8"))
        # The first file must NOT have received the second event.
        self.assertNotIn("to_two", p1.read_text(encoding="utf-8"))

    def test_recovers_after_held_handle_goes_bad(self):
        # Simulate the held handle failing mid-session (e.g. transient IO):
        # event() must swallow, drop the handle, and the NEXT event() reopens.
        p = self.dir / "recover.jsonl"
        t = TraceLogger(path=p, enabled=True)
        t.event("turn1", "ok_before")
        # Replace the live handle with one whose write() raises.
        bad = mock.Mock()
        bad.write.side_effect = OSError("disk gone")
        t._fh = bad
        t.event("turn1", "fails")  # must not raise, drops the bad handle
        self.assertIsNone(t._fh)
        # Next event reopens the real file and succeeds.
        t.event("turn1", "ok_after")
        text = p.read_text(encoding="utf-8")
        self.assertIn("ok_before", text)
        self.assertIn("ok_after", text)
        self.assertNotIn("fails", text)

    def test_close_is_idempotent_and_safe(self):
        p = self.dir / "close.jsonl"
        t = TraceLogger(path=p, enabled=True)
        t.event("turn1", "x")
        t.close()
        t.close()  # idempotent, no raise
        # After close, event() transparently reopens.
        t.event("turn1", "y")
        self.assertIn("y", p.read_text(encoding="utf-8"))

    def test_concurrent_events_no_corruption(self):
        # event() runs single-threaded in prod, but the lock must guarantee
        # that IF two threads emit, lines never interleave/corrupt and none
        # are lost. 8 threads x 200 events = 1600 well-formed JSON lines.
        import json

        p = self.dir / "concurrent.jsonl"
        t = TraceLogger(path=p, enabled=True)
        n_threads, per_thread = 8, 200

        def worker(tid):
            for i in range(per_thread):
                t.event(f"t{tid}", "evt", i=i, tid=tid)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(n_threads)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        t.close()
        lines = p.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), n_threads * per_thread)
        # Every line must be intact, parseable JSON (no torn writes).
        for ln in lines:
            rec = json.loads(ln)
            self.assertEqual(rec["kind"], "evt")


if __name__ == "__main__":
    unittest.main()
