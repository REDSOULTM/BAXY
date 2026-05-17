"""Tests for TraceLogger size-based rotation (Sprint 7.3).

Cascade scheme: when traces.jsonl crosses max_size_mb, the file moves
to traces.jsonl.1; any pre-existing .1 → .2 → .3 → discarded.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.tracing import TraceLogger


def _make_logger(tmp: Path, max_size_mb: int = 1, keep_files: int = 3) -> TraceLogger:
    return TraceLogger(
        path=tmp / "traces.jsonl",
        enabled=True,
        max_size_mb=max_size_mb,
        keep_files=keep_files,
    )


def _fill(path: Path, mb: float) -> None:
    """Write ``mb`` megabytes of dummy content to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * int(mb * 1024 * 1024))


class TestRotation(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_trace_rot_"))

    def test_no_rotation_when_under_limit(self) -> None:
        # Small file → rotation is a no-op.
        path = self.tmp / "traces.jsonl"
        path.write_text("{}\n", encoding="utf-8")
        logger = _make_logger(self.tmp, max_size_mb=1)
        # _maybe_rotate ran on construction. Confirm no archives.
        self.assertTrue(path.exists())
        self.assertFalse((self.tmp / "traces.jsonl.1").exists())
        # And an event() call doesn't trigger spurious rotation.
        for _ in range(5):
            logger.event("turn1", "test_event")
        self.assertFalse((self.tmp / "traces.jsonl.1").exists())

    def test_rotates_when_over_limit_no_archives(self) -> None:
        path = self.tmp / "traces.jsonl"
        _fill(path, mb=1.5)  # > max_size_mb=1
        logger = _make_logger(self.tmp, max_size_mb=1)
        # __post_init__ rotates on startup.
        self.assertFalse(path.exists() and path.stat().st_size > 0,
                         "active file should have been rotated away")
        self.assertTrue((self.tmp / "traces.jsonl.1").exists())
        # The next event() recreates the active file fresh.
        logger.event("turn1", "post_rotation")
        self.assertTrue(path.exists())
        self.assertLess(path.stat().st_size, 1024,  # ~1 line
                        "active file should be a fresh, near-empty file")

    def test_cascade_pushes_existing_archives(self) -> None:
        path = self.tmp / "traces.jsonl"
        _fill(path, mb=1.5)
        (self.tmp / "traces.jsonl.1").write_bytes(b"OLD_1")
        (self.tmp / "traces.jsonl.2").write_bytes(b"OLD_2")
        _make_logger(self.tmp, max_size_mb=1, keep_files=3)
        # Existing .1 → .2, existing .2 → .3.
        self.assertTrue((self.tmp / "traces.jsonl.1").exists())
        self.assertEqual((self.tmp / "traces.jsonl.2").read_bytes(), b"OLD_1")
        self.assertEqual((self.tmp / "traces.jsonl.3").read_bytes(), b"OLD_2")

    def test_oldest_archive_discarded(self) -> None:
        path = self.tmp / "traces.jsonl"
        _fill(path, mb=1.5)
        (self.tmp / "traces.jsonl.1").write_bytes(b"NEW_1")
        (self.tmp / "traces.jsonl.2").write_bytes(b"MID_2")
        (self.tmp / "traces.jsonl.3").write_bytes(b"OLDEST_3")
        _make_logger(self.tmp, max_size_mb=1, keep_files=3)
        # .3 is at the cap and gets deleted; the rest cascade.
        self.assertTrue((self.tmp / "traces.jsonl.1").exists())
        self.assertEqual((self.tmp / "traces.jsonl.2").read_bytes(), b"NEW_1")
        self.assertEqual((self.tmp / "traces.jsonl.3").read_bytes(), b"MID_2")
        # No .4 should ever be created.
        self.assertFalse((self.tmp / "traces.jsonl.4").exists())

    def test_io_failure_does_not_raise(self) -> None:
        # If the file is held open by another handle on Windows we can't
        # rename it cleanly. We can't actually trigger that from here
        # portably, so instead we sanity-check the swallowed-exception
        # contract: rotation never raises out of __post_init__ or event.
        path = self.tmp / "traces.jsonl"
        _fill(path, mb=1.5)
        # Even if max_size_mb makes the active file qualify, the logger
        # must be safe to construct and use.
        logger = _make_logger(self.tmp, max_size_mb=1)
        # And events keep working.
        logger.event("turn1", "post_rotation")
        self.assertTrue(path.exists())

    def test_rotation_throttle(self) -> None:
        # The check should only fire every ROTATE_CHECK_EVERY events.
        # We verify by writing one big batch and confirming we don't
        # rotate on every single event() (which would be expensive).
        path = self.tmp / "traces.jsonl"
        logger = _make_logger(self.tmp, max_size_mb=1)
        # Emit a bunch of tiny events (well under the size cap).
        for i in range(250):
            logger.event(f"turn{i}", "tiny")
        # Counter wraps at ROTATE_CHECK_EVERY=100, so we should have
        # called _maybe_rotate exactly twice (at i=100 and i=200) on top
        # of the initial post_init call. The active file is small, so no
        # rotation actually happened — just confirming no crash and that
        # the throttle field exists.
        self.assertTrue(path.exists())
        # Internal counter is reset to 0 after each check.
        self.assertLess(logger._event_counter, 100)


if __name__ == "__main__":
    unittest.main()
