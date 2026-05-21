"""Telemetry must auto-rotate so its tables don't grow UNBOUNDED for an
always-on assistant. rotate() existed but was never called — dead code. Now it
fires once per process on first init. Best-effort: a rotate failure must never
disable telemetry or break a record_* call."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.telemetry import ROTATION_DAYS, TelemetryStore, _now_epoch_ms


class TestTelemetryAutoRotate(unittest.TestCase):
    def _store(self):
        d = Path(tempfile.mkdtemp())
        t = TelemetryStore(d / "tel.db")
        t._enabled = True
        return t

    def _count(self, t, table="turns"):
        with t._connect() as c:
            return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_init_rotates_once(self):
        t = self._store()
        self.assertTrue(t._ensure_initialized())
        self.assertTrue(t._rotated_this_process)

    def test_old_rows_pruned_fresh_kept(self):
        t = self._store()
        t._ensure_initialized()
        with t._connect() as c:
            old = _now_epoch_ms() - (ROTATION_DAYS + 5) * 24 * 3600 * 1000
            c.execute("INSERT INTO turns (ts, ts_ms) VALUES (?,?)", ("old", old))
            c.execute("INSERT INTO turns (ts, ts_ms) VALUES (?,?)", ("fresh", _now_epoch_ms()))
        deleted = t.rotate()
        self.assertEqual(deleted, 1)
        self.assertEqual(self._count(t), 1)

    def test_rotate_runs_only_once_per_process(self):
        t = self._store()
        t._ensure_initialized()
        # Insert an old row AFTER the first auto-rotate; a second init must NOT
        # rotate it away (once-per-process).
        with t._connect() as c:
            old = _now_epoch_ms() - (ROTATION_DAYS + 5) * 24 * 3600 * 1000
            c.execute("INSERT INTO turns (ts, ts_ms) VALUES (?,?)", ("old", old))
        t._ensure_initialized()  # re-init: must be a no-op for rotation
        self.assertEqual(self._count(t), 1, "second init must not re-rotate")

    def test_record_turn_still_works_after_autorotate(self):
        t = self._store()
        # record_turn calls _ensure_initialized internally -> triggers rotate.
        t.record_turn(ttft_ms=100, tokens_completion=20, extra={"ok": True})
        self.assertGreaterEqual(self._count(t), 1, "the recorded turn must persist")


if __name__ == "__main__":
    unittest.main()
