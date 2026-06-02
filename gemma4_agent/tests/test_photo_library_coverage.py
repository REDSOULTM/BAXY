"""Cobertura dedicada para domain_tools/photo_library.py (added 2026-06-01).

photo_library.py NO tenía test propio (solo el smoke {action:status}). Toca el
FILESYSTEM (scan/copy/move/symlink) -> los tests corren contra dirs tmp reales
con archivos falsos. NO se usa Pillow real: las fechas EXIF se mockean a nivel
de _photo_extract_date para que group_by_date sea determinista y multiplataforma
(no depende de la zona horaria del mtime).

Propiedades afirmadas contra el código fuente:
  - scan filtra por extensión (_PHOTO_EXTS), ignora no-imágenes, respeta limit
  - scan de root inexistente -> ok:False (no crash)
  - group_by_date mode=dry_run NO toca el filesystem (0 archivos creados)
  - group_by_date mode=copy PRESERVA el original y crea la copia agrupada
  - group_by_date agrupa por granularity (year/month/day) correctamente
  - find_by_date filtra por prefijo año/mes
  - status reporta disponibilidad de Pillow honestamente
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ..domain_tools import photo_library
from ..memory_pkg.state import AgentState


def _touch(path: Path, content: bytes = b"img"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class TestPhotoStatus(unittest.TestCase):
    def test_status_reports_pillow(self):
        r = photo_library.photo_library_tool({"action": "status"}, None)
        self.assertTrue(r["ok"])
        self.assertIn("pillow", r)
        self.assertIsInstance(r["pillow"], bool)


class TestPhotoScan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ph_scan_"))

    def test_scan_filters_by_extension(self):
        _touch(self.tmp / "a.jpg")
        _touch(self.tmp / "b.PNG")          # case-insensitive ext
        _touch(self.tmp / "sub" / "c.heic")
        _touch(self.tmp / "notes.txt")      # NO es imagen
        _touch(self.tmp / "video.mp4")      # NO está en _PHOTO_EXTS
        r = photo_library._photo_scan({"root": str(self.tmp)})
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 3)
        names = {p["name"] for p in r["photos"]}
        self.assertEqual(names, {"a.jpg", "b.PNG", "c.heic"})

    def test_scan_respects_limit(self):
        for i in range(5):
            _touch(self.tmp / f"p{i}.jpg")
        r = photo_library._photo_scan({"root": str(self.tmp), "limit": 2})
        self.assertEqual(r["count"], 2)

    def test_scan_missing_root_is_honest_error(self):
        r = photo_library._photo_scan({"root": str(self.tmp / "nope")})
        self.assertFalse(r["ok"])


class TestPhotoGroupByDate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ph_grp_"))
        self.src = self.tmp / "src"
        self.out = self.tmp / "out"
        self.state = AgentState(self.tmp / "s.json")
        _touch(self.src / "jan.jpg")
        _touch(self.src / "feb.jpg")
        # fechas deterministas por archivo (evita depender de mtime/EXIF reales)
        self._dates = {"jan.jpg": "2023-01-15", "feb.jpg": "2023-02-20"}

    def _patched_extract(self, path):
        return self._dates.get(Path(path).name)

    def test_dry_run_touches_nothing(self):
        with patch.object(photo_library, "_photo_extract_date", side_effect=self._patched_extract):
            r = photo_library._photo_group_by_date(
                {"root": str(self.src), "output": str(self.out), "mode": "dry_run", "granularity": "month"},
                self.state,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["processed"], 2)        # el plan cuenta 2
        self.assertEqual(r["total_plan"], 2)
        # pero NINGÚN archivo fue creado bajo out (dry_run)
        created = [p for p in self.out.rglob("*") if p.is_file()]
        self.assertEqual(created, [])

    def test_copy_preserves_original_and_groups_by_month(self):
        with patch.object(photo_library, "_photo_extract_date", side_effect=self._patched_extract):
            r = photo_library._photo_group_by_date(
                {"root": str(self.src), "output": str(self.out), "mode": "copy", "granularity": "month"},
                self.state,
            )
        self.assertTrue(r["ok"])
        self.assertEqual(r["processed"], 2)
        # originales intactos (copy, no move)
        self.assertTrue((self.src / "jan.jpg").is_file())
        self.assertTrue((self.src / "feb.jpg").is_file())
        # agrupados por YYYY-MM
        self.assertTrue((self.out / "2023-01" / "jan.jpg").is_file())
        self.assertTrue((self.out / "2023-02" / "feb.jpg").is_file())

    def test_year_granularity(self):
        with patch.object(photo_library, "_photo_extract_date", side_effect=self._patched_extract):
            photo_library._photo_group_by_date(
                {"root": str(self.src), "output": str(self.out), "mode": "copy", "granularity": "year"},
                self.state,
            )
        self.assertTrue((self.out / "2023" / "jan.jpg").is_file())
        self.assertTrue((self.out / "2023" / "feb.jpg").is_file())

    def test_move_removes_original(self):
        with patch.object(photo_library, "_photo_extract_date", side_effect=self._patched_extract):
            photo_library._photo_group_by_date(
                {"root": str(self.src), "output": str(self.out), "mode": "move", "granularity": "month"},
                self.state,
            )
        # tras move, el original ya no está
        self.assertFalse((self.src / "jan.jpg").is_file())
        self.assertTrue((self.out / "2023-01" / "jan.jpg").is_file())

    def test_undated_file_is_skipped(self):
        _touch(self.src / "mystery.jpg")
        dates = dict(self._dates)  # mystery.jpg ausente -> extract devuelve None
        with patch.object(photo_library, "_photo_extract_date", side_effect=lambda p: dates.get(Path(p).name)):
            r = photo_library._photo_group_by_date(
                {"root": str(self.src), "output": str(self.out), "mode": "copy"},
                self.state,
            )
        self.assertEqual(r["skipped"], 1)

    def test_missing_root_error(self):
        r = photo_library._photo_group_by_date({"output": str(self.out)}, self.state)
        self.assertFalse(r["ok"])


class TestPhotoFindByDate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ph_find_"))
        _touch(self.tmp / "a.jpg")
        _touch(self.tmp / "b.jpg")
        _touch(self.tmp / "c.jpg")
        self._dates = {"a.jpg": "2023-01-10", "b.jpg": "2023-02-10", "c.jpg": "2024-01-10"}

    def test_find_by_year_and_month(self):
        with patch.object(photo_library, "_photo_extract_date", side_effect=lambda p: self._dates.get(Path(p).name)):
            r = photo_library._photo_find_by_date({"root": str(self.tmp), "year": 2023, "month": 1})
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 1)
        self.assertEqual(r["filter"], "2023-01")
        self.assertEqual(Path(r["photos"][0]["path"]).name, "a.jpg")

    def test_find_by_year_only(self):
        with patch.object(photo_library, "_photo_extract_date", side_effect=lambda p: self._dates.get(Path(p).name)):
            r = photo_library._photo_find_by_date({"root": str(self.tmp), "year": 2023})
        self.assertEqual(r["count"], 2)  # a y b

    def test_missing_year(self):
        self.assertFalse(photo_library._photo_find_by_date({"root": str(self.tmp)})["ok"])


if __name__ == "__main__":
    unittest.main()
