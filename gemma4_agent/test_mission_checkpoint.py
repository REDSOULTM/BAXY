"""Tests del checkpoint de misión multi-paso (Fase 7)."""
from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gemma4_agent import mission_checkpoint as mc


class MissionCheckpointTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("GEMMA4_MISSION_CHECKPOINT", None)
        self._tmp = TemporaryDirectory()
        self.state = Path(self._tmp.name) / "state.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_single_clause_no_checkpoint(self):
        # 1 cláusula = turno atómico, NO es misión -> sin checkpoint
        self.assertIsNone(mc.begin(self.state, ["abrí Notepad"]))
        self.assertIsNone(mc.pending(self.state))

    def test_begin_creates_resumable(self):
        mid = mc.begin(self.state, ["abrí Notepad", "escribí hola", "guardá"])
        self.assertIsNotNone(mid)
        p = mc.pending(self.state)
        self.assertIsNotNone(p)
        self.assertEqual(p["remaining"], ["abrí Notepad", "escribí hola", "guardá"])

    def test_mark_done_advances(self):
        mid = mc.begin(self.state, ["abrí Notepad", "escribí hola", "guardá"])
        mc.mark_done(self.state, mid, 0, "abrí")
        p = mc.pending(self.state)
        self.assertEqual(p["remaining"], ["escribí hola", "guardá"])
        mc.mark_done(self.state, mid, 1, "escribí")
        p = mc.pending(self.state)
        self.assertEqual(p["remaining"], ["guardá"])

    def test_finish_clears(self):
        mid = mc.begin(self.state, ["abrí Notepad", "escribí hola"])
        mc.mark_done(self.state, mid, 0, "abrí")
        mc.finish(self.state, mid)
        self.assertIsNone(mc.pending(self.state))

    def test_all_done_not_pending(self):
        mid = mc.begin(self.state, ["a", "b"])
        mc.mark_done(self.state, mid, 0)
        mc.mark_done(self.state, mid, 1)
        # done_index == len -> nada pendiente aunque no se haya llamado finish
        self.assertIsNone(mc.pending(self.state))

    def test_stale_checkpoint_ignored(self):
        mid = mc.begin(self.state, ["a", "b", "c"])
        # envejecer el checkpoint a >30min
        import json
        data = json.loads(self.state.parent.joinpath("mission_checkpoint.json").read_text(encoding="utf-8"))
        data["created_at"] = time.time() - 4000
        self.state.parent.joinpath("mission_checkpoint.json").write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(mc.pending(self.state))

    def test_gate_off(self):
        os.environ["GEMMA4_MISSION_CHECKPOINT"] = "0"
        self.assertIsNone(mc.begin(self.state, ["a", "b", "c"]))
        self.assertIsNone(mc.pending(self.state))

    def test_interrupted_mission_resumable(self):
        # simula interrupción dura: begin + mark_done parcial, SIN finish
        mid = mc.begin(self.state, ["abrí Word", "escribí informe", "exportá pdf"])
        mc.mark_done(self.state, mid, 0, "abrí Word")
        # (proceso "crashea" aquí — no se llama finish)
        # al reabrir, el checkpoint sigue y ofrece reanudar lo pendiente
        p = mc.pending(self.state)
        self.assertIsNotNone(p)
        self.assertEqual(p["remaining"], ["escribí informe", "exportá pdf"])

    def test_mark_done_wrong_mission_id_noop(self):
        mid = mc.begin(self.state, ["a", "b", "c"])
        mc.mark_done(self.state, "mis_otra", 0)  # otra misión
        p = mc.pending(self.state)
        self.assertEqual(p["remaining"], ["a", "b", "c"])  # sin avanzar


if __name__ == "__main__":
    unittest.main()
