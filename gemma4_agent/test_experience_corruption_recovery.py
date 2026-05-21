"""Experience memory must SURVIVE a corrupt DB file. A malformed sqlite image
(power loss / sync conflict mid-write) made every record()/recall() raise
DatabaseError -> memory "worked for a while then broke forever". Now _open
quarantines the bad file and recreates, degrading to "starts fresh".

Skips if sqlite_vec isn't installed (the loader disables cleanly there)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gemma4_agent.experience import ExperienceMemory


def _sqlite_vec_available() -> bool:
    try:
        import sqlite_vec  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_sqlite_vec_available(), "sqlite_vec not installed")
class TestExperienceCorruptionRecovery(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "experiences.db"

    def test_corrupt_db_is_quarantined_and_recreated(self):
        # Malformed file with a plausible sqlite header but garbage pages.
        self.path.write_bytes(b"SQLite format 3\x00" + b"\xde\xad\xbe\xef" * 256)
        mem = ExperienceMemory(path=self.path)
        conn = mem._open()
        self.assertIsNotNone(conn, "must recover, not return None")
        self.assertFalse(mem._disabled, "must not disable on a recoverable corruption")
        quarantined = list(self.dir.glob("*.corrupt-*"))
        self.assertTrue(quarantined, "corrupt file must be quarantined for forensics")

    def test_fresh_db_after_recovery_is_writable(self):
        self.path.write_bytes(b"SQLite format 3\x00" + b"\x00\xff" * 512)
        mem = ExperienceMemory(path=self.path)
        # A real write must succeed against the recreated DB. Stub embedder
        # returns a fixed 384-dim vector (no model needed).
        from gemma4_agent.experience import _EMBED_DIM

        def _embed(_text):
            return [0.0] * _EMBED_DIM

        res = mem.record(
            turn_id="t1", user_input="hola", tools_used=[],
            outcome="ok", mission_status="done", summary="greeting",
            embed_fn=_embed,
        )
        self.assertTrue(res.get("ok"), f"record must succeed after recovery: {res}")

    def test_healthy_db_is_untouched(self):
        # A normal first-run (no file) must NOT create any quarantine file.
        mem = ExperienceMemory(path=self.path)
        conn = mem._open()
        self.assertIsNotNone(conn)
        self.assertEqual(list(self.dir.glob("*.corrupt-*")), [],
                         "a healthy/new DB must never be quarantined")


if __name__ == "__main__":
    unittest.main()
