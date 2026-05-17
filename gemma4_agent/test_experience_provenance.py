"""Tests for Bug 2: provenance-tagged RAG (experience.sqlite).

Verifies:
  - New columns (outcome_code, failure_reason_code, args_signature,
    capability_label, grounding_flagged) are created on a fresh DB and
    are idempotent on a migrated DB.
  - record() persists optional provenance fields.
  - format_recall_for_prompt does NOT emit `summary:` lines (the critical
    behavior change — the LLM must not see past reply text it can copy).
  - flag_grounding[/_by_turn] sets the flag and is reflected in recall.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gemma4_agent.experience import (
    ExperienceMemory,
    format_recall_for_prompt,
)


def _fake_embed(text: str):
    """Deterministic toy embedding: 384 floats derived from the hash of text."""
    import hashlib
    h = hashlib.md5(text.encode("utf-8")).digest()
    # Stretch the 16-byte digest into 384 floats deterministically.
    arr = []
    for i in range(384):
        arr.append(((h[i % 16] + i) % 256) / 255.0 - 0.5)
    # L2 normalize so distances are bounded.
    import math
    norm = math.sqrt(sum(x * x for x in arr)) or 1.0
    return [x / norm for x in arr]


class TestSchemaMigration(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "exp.sqlite"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_fresh_db_has_all_columns(self):
        mem = ExperienceMemory(path=self.path)
        # Trigger _open()
        result = mem.record(
            turn_id="t1", user_input="hola",
            tools_used=[], outcome="ok",
            mission_status="PASS", summary="ok",
            embed_fn=_fake_embed,
        )
        if not result.get("ok"):
            self.skipTest(f"sqlite_vec unavailable: {result}")
        conn = sqlite3.connect(self.path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(experiences)")}
        for col in ("outcome_code", "failure_reason_code",
                     "args_signature", "capability_label",
                     "grounding_flagged"):
            self.assertIn(col, cols, f"missing column {col}")

    def test_migration_idempotent_on_legacy_db(self):
        # Simulate a legacy DB (no new columns).
        conn = sqlite3.connect(self.path)
        conn.execute(
            """CREATE TABLE experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                user_input TEXT NOT NULL,
                tools_used TEXT NOT NULL DEFAULT '[]',
                outcome TEXT,
                mission_status TEXT,
                summary TEXT
            )"""
        )
        conn.commit()
        conn.close()
        # First open: applies migrations
        mem1 = ExperienceMemory(path=self.path)
        r1 = mem1.record(
            turn_id="t1", user_input="x",
            tools_used=[], outcome="", mission_status="",
            summary="", embed_fn=_fake_embed,
        )
        if not r1.get("ok"):
            self.skipTest(f"sqlite_vec unavailable: {r1}")
        # Second open: must NOT raise (column already exists).
        mem1.close()
        mem2 = ExperienceMemory(path=self.path)
        r2 = mem2.record(
            turn_id="t2", user_input="y",
            tools_used=[], outcome="", mission_status="",
            summary="", embed_fn=_fake_embed,
        )
        self.assertTrue(r2.get("ok"))


class TestRecordWithProvenance(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "exp.sqlite"
        self.mem = ExperienceMemory(path=self.path)
        # Probe for sqlite_vec availability via the first insert.
        r = self.mem.record(
            turn_id="probe", user_input="probe",
            tools_used=[], outcome="", mission_status="",
            summary="", embed_fn=_fake_embed,
        )
        if not r.get("ok"):
            self.skipTest(f"sqlite_vec unavailable: {r}")

    def tearDown(self):
        self.mem.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_record_with_provenance_fields(self):
        r = self.mem.record(
            turn_id="prov1",
            user_input="quiero ver daredevil",
            tools_used=["media"],
            outcome="abrió Disney+",
            mission_status="PASS",
            summary="abrió Disney+",
            embed_fn=_fake_embed,
            outcome_code="PASS_VERIFIED",
            failure_reason_code=None,
            args_signature={"provider": "disney_plus", "action": "play"},
            capability_label="consumir contenido audiovisual",
        )
        self.assertTrue(r.get("ok"))
        # Recall and verify the fields come back.
        recalls = self.mem.recall("quiero ver daredevil", embed_fn=_fake_embed, k=3)
        self.assertGreater(len(recalls), 0)
        hit = next((x for x in recalls if x["turn_id"] == "prov1"), None)
        self.assertIsNotNone(hit)
        self.assertEqual(hit["outcome_code"], "PASS_VERIFIED")
        self.assertEqual(hit["capability_label"], "consumir contenido audiovisual")
        self.assertEqual(hit["args_signature"], {"provider": "disney_plus", "action": "play"})


class TestFormatRecallForPrompt(unittest.TestCase):
    """The provenance formatter MUST NOT emit reply-like text."""

    def test_empty_recalls_yields_empty(self):
        self.assertEqual(format_recall_for_prompt([]), "")

    def test_does_not_include_summary_text(self):
        recalls = [{
            "id": 1, "turn_id": "x", "ts": "2026", "distance": 0.3,
            "user_input": "quiero ver daredevil born again en disney",
            "tools_used": ["media"],
            "mission_status": "PASS",
            "outcome_code": "PASS_VERIFIED",
            "summary": "Listo, estoy viendo Daredevil Born Again en Disney+.",
            "args_signature": {"provider": "disney_plus"},
            "capability_label": "consumir contenido audiovisual",
            "failure_reason_code": None,
            "grounding_flagged": False,
        }]
        out = format_recall_for_prompt(recalls)
        # The summary text (verb in past tense, claim of success) MUST NOT
        # appear in the prompt — that's exactly what the LLM mimics.
        self.assertNotIn("Listo, estoy viendo", out)
        self.assertNotIn("Daredevil Born Again en Disney+", out)
        # But the policy info MUST be present.
        self.assertIn("media", out)
        self.assertIn("PASS_VERIFIED", out)
        self.assertIn("disney_plus", out)
        self.assertIn("consumir contenido audiovisual", out)

    def test_grounding_flagged_emits_warning(self):
        recalls = [{
            "id": 2, "turn_id": "y", "ts": "2026", "distance": 0.2,
            "user_input": "quiero ver loki",
            "tools_used": ["media"],
            "mission_status": "PASS",
            "outcome_code": "PASS_UNVERIFIED",
            "summary": "Abrí Disney+ y busqué Loki",
            "args_signature": {},
            "capability_label": None,
            "failure_reason_code": "hallucinated_action",
            "grounding_flagged": True,
        }]
        out = format_recall_for_prompt(recalls)
        self.assertIn("WARNING_past_reply_was_hallucinated", out)
        self.assertIn("hallucinated_action", out)
        self.assertNotIn("Abrí Disney+ y busqué Loki", out)

    def test_legacy_row_without_new_fields_still_renders(self):
        # Legacy row: no outcome_code, no capability, no args.
        recalls = [{
            "id": 3, "turn_id": "z", "ts": "2026", "distance": 0.4,
            "user_input": "abre spotify",
            "tools_used": ["media"],
            "mission_status": "PASS",
            "summary": "abrió spotify",
        }]
        out = format_recall_for_prompt(recalls)
        # Should not crash, should fall back to mission_status when
        # outcome_code is missing.
        self.assertIn("PASS", out)
        self.assertIn("abre spotify", out)


class TestFlagGrounding(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.path = Path(self.tmpdir) / "exp.sqlite"
        self.mem = ExperienceMemory(path=self.path)
        r = self.mem.record(
            turn_id="probe", user_input="probe",
            tools_used=[], outcome="", mission_status="",
            summary="", embed_fn=_fake_embed,
        )
        if not r.get("ok"):
            self.skipTest(f"sqlite_vec unavailable: {r}")

    def tearDown(self):
        self.mem.close()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_flag_grounding_by_turn(self):
        r = self.mem.record(
            turn_id="tcase",
            user_input="quiero ver daredevil",
            tools_used=[],
            outcome="lied",
            mission_status="PASS",
            summary="abri disney",
            embed_fn=_fake_embed,
        )
        self.assertTrue(r.get("ok"))
        # Initially not flagged.
        recalls = self.mem.recall("quiero ver daredevil", embed_fn=_fake_embed, k=3)
        hit = next((x for x in recalls if x["turn_id"] == "tcase"), None)
        self.assertIsNotNone(hit)
        self.assertFalse(hit["grounding_flagged"])
        # Flag it.
        flag = self.mem.flag_grounding_by_turn("tcase")
        self.assertTrue(flag.get("ok"))
        # Recall again: flag must be set.
        recalls = self.mem.recall("quiero ver daredevil", embed_fn=_fake_embed, k=3)
        hit = next((x for x in recalls if x["turn_id"] == "tcase"), None)
        self.assertIsNotNone(hit)
        self.assertTrue(hit["grounding_flagged"])
        self.assertEqual(hit["failure_reason_code"], "hallucinated_action")


if __name__ == "__main__":
    unittest.main()
