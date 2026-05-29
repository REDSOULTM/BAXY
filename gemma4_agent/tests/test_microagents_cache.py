"""load_microagents() runs every turn (build_microagents_section in
_system_message). It used to re-read+parse all *.md from disk each turn
(~1.13ms/turn, >50% of the prompt-assembly cost). Now it caches by a stat-only
directory signature.

EJE del norte rector: LATENCIA (quita ~0.95ms/turno del hot-path de armado del
prompt) SIN romper FIABILIDAD: el live-edit debe seguir funcionando — agregar,
editar o borrar un microagent se refleja al siguiente turno (la firma mtime/size
cambia y se relee). Estos tests pinean ambos lados."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from gemma4_agent.memory_pkg import microagents as ma



_FIXTURE = """---
name: test_agent
triggers: ["foobar"]
priority: medium
---
Cuerpo del microagent de prueba.
"""


class TestMicroagentCache(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        ma._MICROAGENT_CACHE.clear()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.dir, ignore_errors=True)
        ma._MICROAGENT_CACHE.clear()

    def _write(self, name: str, body: str):
        (self.dir / name).write_text(body, encoding="utf-8")

    def test_second_call_is_cached_no_reread(self):
        self._write("a.md", _FIXTURE)
        first = ma.load_microagents(self.dir)
        self.assertEqual(len(first), 1)
        # Patch read_text to detect any re-read on the cached path.
        reads = {"n": 0}
        orig = Path.read_text

        def _counting(self, *a, **k):
            reads["n"] += 1
            return orig(self, *a, **k)

        with mock.patch.object(Path, "read_text", _counting):
            second = ma.load_microagents(self.dir)
        self.assertEqual(reads["n"], 0, "cached call must NOT read any file")
        self.assertIs(second, first, "cached call returns the same list object")

    def test_edit_invalidates_cache(self):
        self._write("a.md", _FIXTURE)
        first = ma.load_microagents(self.dir)
        self.assertEqual(first[0].content, "Cuerpo del microagent de prueba.")
        # Edit the body. Bump mtime explicitly so the test is robust on fast FS.
        time.sleep(0.01)
        edited = _FIXTURE.replace("Cuerpo del microagent de prueba.", "NUEVO cuerpo.")
        self._write("a.md", edited)
        os.utime(self.dir / "a.md", None)  # ensure mtime moves
        second = ma.load_microagents(self.dir)
        self.assertEqual(second[0].content, "NUEVO cuerpo.",
                         "an edited microagent must be re-read next turn")

    def test_add_and_remove_invalidate_cache(self):
        self._write("a.md", _FIXTURE)
        self.assertEqual(len(ma.load_microagents(self.dir)), 1)
        # Add a second microagent.
        self._write("b.md", _FIXTURE.replace("test_agent", "second").replace("foobar", "bazqux"))
        self.assertEqual(len(ma.load_microagents(self.dir)), 2,
                         "a newly added microagent must appear next turn")
        # Remove one.
        (self.dir / "b.md").unlink()
        self.assertEqual(len(ma.load_microagents(self.dir)), 1,
                         "a removed microagent must disappear next turn")

    def test_empty_dir_returns_empty(self):
        self.assertEqual(ma.load_microagents(self.dir), [])


if __name__ == "__main__":
    unittest.main()
