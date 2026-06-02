"""Ratchet de archivos-dios (Point 3, 2026-06-01).

Los 4 archivos más grandes NO deben crecer: para agregar funcionalidad, extraé un módulo
hermano (patrón R2), no engroses el dios. La serie R1–R8 viene REDUCIÉNDOLOS; este guard
evita la regresión (que vuelvan a crecer). El buffer es para mantenimiento chico
(bugfixes); si lo superás, la respuesta correcta es PARTIR, no subir el techo.

Ver documentacion/MAPA_descomposicion_archivos_dios.md (áreas extraíbles + riesgo).
"""
from __future__ import annotations

import unittest
from pathlib import Path

# LOC MEDIDO 2026-06-01 + buffer de mantenimiento (~1%). Bajar estos números cuando se
# extraiga un área (R-series). NO subirlos para meter una feature nueva: extraé un
# hermano. (tools.py es clase -> mixin; los otros, patrón sibling+shim de R2.)
CEILINGS = {
    "tools_pkg/tools.py": 7700,
    "agent_core/agent.py": 6450,
    # 2026-06-01: WhatsApp (~1311 LOC) extraído a domain_tools/whatsapp.py
    # (patrón R2 sibling+shim) al arreglar C1/C2/H8. El techo baja con la
    # extracción (4560 -> 3370, +1% buffer sobre 3336 medido).
    "domain_tools/__init__.py": 3370,
    "tools_pkg/ops_tools.py": 2300,
}


class GodObjectSizeCeilingTest(unittest.TestCase):
    def test_god_objects_do_not_grow(self):
        root = Path(__file__).resolve().parents[1]
        for rel, ceiling in CEILINGS.items():
            loc = len((root / rel).read_text(encoding="utf-8", errors="replace").splitlines())
            self.assertLessEqual(
                loc, ceiling,
                f"{rel}: {loc} LOC > techo {ceiling}. NO subas el techo para meter una "
                f"feature — extraé un módulo hermano (ver "
                f"documentacion/MAPA_descomposicion_archivos_dios.md). El techo baja "
                f"cuando partís, no sube cuando agregás.",
            )


if __name__ == "__main__":
    unittest.main()
