"""Tests for the fail-loud schema check in experience.sqlite.

If the ALTER TABLE block in ExperienceMemory._open is silently
swallowing failures (e.g. because the DB file is locked by antivirus
or a sync client during cold start), the per-row reads later in the
session crash with confusing 'no such column' errors deep inside
format_recall_for_prompt. The schema check is fail-loud at open
time so the user sees a clean error with a remediation hint.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Skip the whole suite if sqlite_vec isn't installed — _open creates a
# vec0 virtual table that requires the extension.
try:
    import sqlite_vec  # noqa: F401
    _HAS_VEC = True
except ImportError:
    _HAS_VEC = False


@unittest.skipUnless(_HAS_VEC, "sqlite_vec extension not available")
class TestSchemaDrift(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="gemma4_exp_drift_"))
        self.path = self.tmp / "experience.sqlite"

    def test_fresh_db_has_all_expected_columns(self) -> None:
        # On a fresh open, the CREATE TABLE establishes the base 7
        # columns and the ALTER block adds the 5 provenance columns.
        # The fail-loud check at the end of _open must pass.
        from gemma4_agent.memory_pkg.experience import ExperienceMemory
        mem = ExperienceMemory(self.path)
        conn = mem._open()
        self.assertIsNotNone(conn)
        cur = conn.execute("PRAGMA table_info(experiences)")
        cols = {row[1] for row in cur.fetchall()}
        for expected in ("outcome_code", "failure_reason_code",
                         "args_signature", "capability_label",
                         "grounding_flagged"):
            self.assertIn(expected, cols)
        mem.close()

    def test_existing_pre_migration_db_gets_columns_added(self) -> None:
        # Simulate a pre-migration DB: just the 7 base columns.
        conn = sqlite3.connect(self.path)
        conn.execute("""
            CREATE TABLE experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id TEXT NOT NULL,
                ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_input TEXT,
                tools_used TEXT NOT NULL DEFAULT '[]',
                outcome TEXT,
                mission_status TEXT,
                summary TEXT
            )""")
        conn.commit()
        conn.close()
        # Opening should run the ALTERs successfully and pass the check.
        from gemma4_agent.memory_pkg.experience import ExperienceMemory
        mem = ExperienceMemory(self.path)
        c = mem._open()
        cur = c.execute("PRAGMA table_info(experiences)")
        cols = {row[1] for row in cur.fetchall()}
        for expected in ("outcome_code", "failure_reason_code",
                         "args_signature", "capability_label",
                         "grounding_flagged"):
            self.assertIn(expected, cols)
        mem.close()

    def test_fails_loud_when_alter_swallowed_silently(self) -> None:
        # Simulate the bug case directly: hand-craft a DB that already
        # has `experiences` with the 7 base columns but is then opened
        # via a Connection whose `execute` swallows the ALTERs (the
        # production code's try/except). We can't monkeypatch
        # sqlite3.Connection (it's an immutable C type), so we
        # construct the DB to the pre-migration state and patch the
        # module-level sqlite3.connect to return a wrapper Connection
        # that intercepts ALTER calls.

        # Pre-migration shape.
        conn = sqlite3.connect(self.path)
        conn.execute("""
            CREATE TABLE experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id TEXT NOT NULL,
                ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_input TEXT,
                tools_used TEXT NOT NULL DEFAULT '[]',
                outcome TEXT,
                mission_status TEXT,
                summary TEXT
            )""")
        conn.commit()
        conn.close()

        # Wrapper: forwards everything except ALTER, which raises.
        real_connect = sqlite3.connect

        class _AlterSwallowingConn:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, *args, **kwargs):
                if sql.lstrip().upper().startswith("ALTER TABLE"):
                    raise sqlite3.OperationalError("simulated lock during ALTER")
                return self._inner.execute(sql, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        def _wrapped_connect(*args, **kwargs):
            return _AlterSwallowingConn(real_connect(*args, **kwargs))

        from gemma4_agent.memory_pkg.experience import ExperienceMemory
        mem = ExperienceMemory(self.path)
        with patch("gemma4_agent.experience.sqlite3.connect", _wrapped_connect):
            with self.assertRaises(RuntimeError) as cm:
                mem._open()
        msg = str(cm.exception)
        # The error message must mention the remediation cause + path.
        self.assertIn("missing columns", msg)
        self.assertIn("antivirus", msg.lower())
        self.assertIn(str(self.path), msg)


if __name__ == "__main__":
    unittest.main()
