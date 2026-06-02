"""Cobertura dedicada para domain_tools/backup_sync.py (added 2026-06-01).

backup_sync.py NO tenía test propio (solo el smoke {action:status}).
Este archivo ejercita el ciclo real backup_create -> verify -> restore con
ZIPs reales sobre tmp dirs (sin red, sin subprocess; el filesystem es
seguro porque todo vive en tempfile.mkdtemp y nada se borra del usuario).

Propiedades de seguridad afirmadas contra el código fuente:
  - zip-slip (CC-021): entradas que escapan dst se BLOQUEAN y NO se escriben
  - overwrite (CC-101): restore con conflict=overwrite exige confirmación
  - honestidad: verify reporta corrupted=True en un ZIP roto (no miente)
  - políticas de conflicto skip/rename/overwrite hacen lo que dicen
  - dedupe por SHA-256 agrupa duplicados reales
"""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from ..domain_tools import backup_sync
from ..memory_pkg.state import AgentState


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="backup_cov_"))
        self.state = AgentState(self.tmp / "state.json")

    def _make_zip(self, name: str, entries: dict[str, str]) -> Path:
        p = self.tmp / name
        with zipfile.ZipFile(p, "w") as z:
            for arcname, content in entries.items():
                z.writestr(arcname, content)
        return p


class TestBackupCreateAndVerify(_Base):
    def test_backup_create_missing_source(self):
        r = backup_sync.backup_sync_tool(
            {"action": "backup_create", "src": str(self.tmp / "nope")}, self.state)
        self.assertFalse(r["ok"])

    def test_backup_create_then_verify_roundtrip(self):
        src = self.tmp / "srcdir"
        src.mkdir()
        (src / "a.txt").write_text("hello", encoding="utf-8")
        (src / "b.txt").write_text("world", encoding="utf-8")
        created = backup_sync.backup_sync_tool(
            {"action": "backup_create", "src": str(src)}, self.state)
        self.assertTrue(created["ok"])
        self.assertGreater(created["size"], 0)
        zip_path = created["path"]
        self.assertTrue(Path(zip_path).is_file())

        verified = backup_sync.backup_sync_tool(
            {"action": "verify", "path": zip_path}, self.state)
        self.assertTrue(verified["ok"])
        self.assertTrue(verified["verified"])
        self.assertFalse(verified["corrupted"])
        self.assertGreaterEqual(verified["entries"], 2)

    def test_verify_corrupted_zip_is_honest(self):
        # HONESTIDAD: un archivo que no es ZIP debe reportarse como fallo,
        # nunca como verified=True.
        bad = self.tmp / "broken.zip"
        bad.write_bytes(b"this is not a real zip file")
        r = backup_sync.backup_sync_tool({"action": "verify", "path": str(bad)}, self.state)
        self.assertFalse(r["ok"])

    def test_verify_missing_backup(self):
        r = backup_sync.backup_sync_tool(
            {"action": "verify", "path": str(self.tmp / "ghost.zip")}, self.state)
        self.assertFalse(r["ok"])


class TestRestoreZipSlip(_Base):
    def test_zip_slip_entry_is_blocked_and_not_written(self):
        # CC-021 / T2-backup_sync-zip-slip-021: una entrada con ../ que escapa
        # del dst debe BLOQUEARSE y jamás materializarse en disco.
        evil = self._make_zip("evil.zip", {"../escape.txt": "pwned", "safe.txt": "ok"})
        dst = self.tmp / "restore_out"
        r = backup_sync.backup_sync_tool(
            {"action": "restore", "path": str(evil), "dst": str(dst)}, self.state)
        self.assertFalse(r["ok"])
        self.assertEqual(r["status"], "failed")
        self.assertEqual(len(r["blocked"]), 1)
        # el archivo malicioso NO debe existir fuera del dst
        self.assertFalse((self.tmp / "escape.txt").exists())


class TestRestoreConflictPolicies(_Base):
    def _restore(self, zip_path: Path, dst: Path, **extra):
        args = {"action": "restore", "path": str(zip_path), "dst": str(dst)}
        args.update(extra)
        return backup_sync.backup_sync_tool(args, self.state)

    def test_invalid_conflict_policy_rejected(self):
        z = self._make_zip("z.zip", {"f.txt": "v1"})
        r = self._restore(z, self.tmp / "d", conflict="merge")
        self.assertFalse(r["ok"])

    def test_skip_policy_leaves_existing_untouched(self):
        z = self._make_zip("z.zip", {"f.txt": "v2"})
        dst = self.tmp / "dst_skip"
        dst.mkdir()
        (dst / "f.txt").write_text("original", encoding="utf-8")
        r = self._restore(z, dst, conflict="skip")
        self.assertTrue(r["ok"])
        self.assertEqual(r["skipped_count"], 1)
        # el original NO fue tocado
        self.assertEqual((dst / "f.txt").read_text(encoding="utf-8"), "original")

    def test_rename_policy_keeps_both(self):
        z = self._make_zip("z.zip", {"f.txt": "v2"})
        dst = self.tmp / "dst_rename"
        dst.mkdir()
        (dst / "f.txt").write_text("original", encoding="utf-8")
        r = self._restore(z, dst, conflict="rename")
        self.assertTrue(r["ok"])
        self.assertEqual(r["renamed_count"], 1)
        self.assertEqual((dst / "f.txt").read_text(encoding="utf-8"), "original")
        # debe existir un f_1.txt con el contenido nuevo
        self.assertTrue((dst / "f_1.txt").exists())
        self.assertEqual((dst / "f_1.txt").read_text(encoding="utf-8"), "v2")

    def test_overwrite_requires_confirmation_then_proceeds(self):
        # CC-101: overwrite es destructivo -> hard_gate exige confirmación.
        z = self._make_zip("z.zip", {"f.txt": "v2"})
        dst = self.tmp / "dst_ow"
        dst.mkdir()
        (dst / "f.txt").write_text("original", encoding="utf-8")

        gated = self._restore(z, dst, conflict="overwrite")
        self.assertFalse(gated["ok"])
        self.assertEqual(gated["status"], "needs_confirmation")
        # NO debe haber sobrescrito todavía
        self.assertEqual((dst / "f.txt").read_text(encoding="utf-8"), "original")

        confirmed = self._restore(z, dst, conflict="overwrite", confirmed=True)
        self.assertTrue(confirmed["ok"])
        self.assertEqual(confirmed["overwritten_count"], 1)
        self.assertEqual((dst / "f.txt").read_text(encoding="utf-8"), "v2")

    def test_overwrite_preview_does_not_gate_or_write(self):
        # preview no es destructivo -> no debe gatear ni escribir.
        z = self._make_zip("z.zip", {"f.txt": "v2"})
        dst = self.tmp / "dst_prev"
        dst.mkdir()
        (dst / "f.txt").write_text("original", encoding="utf-8")
        r = self._restore(z, dst, conflict="overwrite", preview=True)
        self.assertTrue(r["ok"])
        self.assertTrue(r["preview"])
        self.assertEqual((dst / "f.txt").read_text(encoding="utf-8"), "original")

    def test_restore_not_a_zip_suffix(self):
        notzip = self.tmp / "data.tar"
        notzip.write_bytes(b"x")
        r = self._restore(notzip, self.tmp / "d")
        self.assertFalse(r["ok"])

    def test_restore_missing_backup(self):
        r = backup_sync.backup_sync_tool(
            {"action": "restore", "path": str(self.tmp / "nope.zip"), "dst": str(self.tmp / "d")},
            self.state)
        self.assertFalse(r["ok"])


class TestBackupDedupe(_Base):
    def test_dedupe_requires_existing_dir(self):
        self.assertFalse(backup_sync._backup_dedupe({})["ok"])
        self.assertFalse(
            backup_sync._backup_dedupe({"path": str(self.tmp / "ghost")})["ok"])

    def test_dedupe_groups_identical_content(self):
        root = self.tmp / "dups"
        root.mkdir()
        (root / "one.txt").write_text("same content here", encoding="utf-8")
        (root / "two.txt").write_text("same content here", encoding="utf-8")
        (root / "unique.txt").write_text("different", encoding="utf-8")
        r = backup_sync._backup_dedupe({"path": str(root)})
        self.assertTrue(r["ok"])
        self.assertEqual(r["scanned"], 3)
        self.assertEqual(r["duplicate_groups"], 1)
        self.assertEqual(r["duplicate_files"], 1)  # 2 idénticos -> 1 redundante


class TestNextAvailablePath(_Base):
    def test_returns_same_when_free(self):
        p = self.tmp / "free.txt"
        self.assertEqual(backup_sync._next_available_path(p), p)

    def test_increments_when_taken(self):
        p = self.tmp / "taken.txt"
        p.write_text("x", encoding="utf-8")
        nxt = backup_sync._next_available_path(p)
        self.assertNotEqual(nxt, p)
        self.assertEqual(nxt.name, "taken_1.txt")


if __name__ == "__main__":
    unittest.main()
