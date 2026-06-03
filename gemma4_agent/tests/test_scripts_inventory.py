"""Guarda anti-drift del inventario `scripts/INDEX.md`.

Detecta cuando aparecen scripts nuevos sin entrar al INDEX. NO obliga a
documentar diagnoses one-shot (`_diag_*` viven en `_diag/`) pero sí los
del directorio top-level `scripts/`.

Si el conteo crece más allá del techo registrado, el dev debe actualizar
`INDEX.md` o argumentar por qué el script no necesita entrada (típicamente
porque es transitorio y debería mover a `_diag/`).
"""
from __future__ import annotations

import pathlib
import unittest


class TestScriptsInventory(unittest.TestCase):

    def test_index_md_exists(self):
        idx = pathlib.Path(__file__).resolve().parent.parent.parent / "scripts" / "INDEX.md"
        self.assertTrue(idx.exists(), "scripts/INDEX.md no existe — R8 audit")

    def test_diag_scripts_live_in_subdir(self):
        """Los `_diag_*.py` viven en `scripts/_diag/`, no en `scripts/`.
        Si aparece uno nuevo top-level, mover."""
        root = pathlib.Path(__file__).resolve().parent.parent.parent / "scripts"
        top_level_diags = list(root.glob("_diag_*.py"))
        self.assertEqual(
            top_level_diags, [],
            f"Scripts `_diag_*.py` deben vivir en scripts/_diag/, no top-level. "
            f"Encontrados: {[p.name for p in top_level_diags]}",
        )

    def test_index_mentions_all_top_level_scripts(self):
        """Cada `.py` en scripts/ (no `_diag/`) debe estar mencionado por
        nombre en INDEX.md. Permitimos los `_r1_*`/`_r2_*`/`_r3_*`/`_r8_*`
        helpers que ya tienen su entrada agrupada.
        """
        root = pathlib.Path(__file__).resolve().parent.parent.parent / "scripts"
        idx_text = (root / "INDEX.md").read_text(encoding="utf-8")
        missing: list[str] = []
        for p in root.glob("*.py"):
            if p.name in idx_text:
                continue
            missing.append(p.name)
        self.assertEqual(
            missing, [],
            f"Scripts top-level no mencionados en INDEX.md: {missing}",
        )


if __name__ == "__main__":
    unittest.main()
