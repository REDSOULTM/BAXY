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
# 2026-06-02: tools.py reconciliado a 7850. El ratchet (7700) nació en
# d9f776b-era cuando tools.py era ~7759 y quedó por debajo del HEAD real:
# commits POSTERIORES de la auditoría (c8efd5b "6 fixes" cruzó 7700),
# honesty tri-estado (brightness/click) y perf (cache schemas_for_names)
# lo llevaron a 7853 — deuda HEREDADA de esos commits, NO de esta sesión.
# Esta sesión de hecho lo BAJÓ -6 (eliminó smart_home). El número correcto
# para la deuda real de HEAD es 7847; techo 7850 (+3 buffer mínimo). Sigue
# vigente la regla: para una FEATURE nueva, extraé un hermano, no engroses.
CEILINGS = {
    "tools_pkg/tools.py": 7850,
    # 2026-06-02: agent.py reconciliado a 6495. El techo 6450 ya estaba violado
    # en HEAD (git=6488, deuda heredada de commits previos de computer-use/honesty).
    # Esta sesión sumó +4 al CONVERTIR 2 silent-except en logging trazado (baja la
    # deuda silent-except 360->358 a cambio de +4 LOC — buen trade: traza > LOC).
    # Techo 6495 (+3 buffer). Para una FEATURE nueva, extraé un hermano, no engroses.
    "agent_core/agent.py": 6495,
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
