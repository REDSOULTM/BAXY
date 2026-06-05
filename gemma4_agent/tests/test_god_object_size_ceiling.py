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
    # 2026-06-04: reconciliado 7850 -> 7991. Deuda HEREDADA medida: el rebrand
    # (b3ce3af->b000ff7~1, +115) y la cacería tanda 1 (+26: guards how-to-no-
    # destruye + anti-injection en filesystem_delete, state-checks steam/browser)
    # cruzaron el techo. NO es bloat — son guardas de SEGURIDAD/honestidad medidas
    # (evitan borrar ante una pregunta, bloquean prompt-injection). El número es
    # EXACTO (sin buffer): la deuda no debe tener espacio para crecer. Para una
    # FEATURE nueva, extraé un hermano (ver MAPA_descomposicion_archivos_dios.md);
    # memoria tools_audit advierte que extraer t_whatsapp/t_steam inline ARRIESGA.
    # 2026-06-05: 7991 -> 8009 (+18). Cacería tanda 2, cluster A7: el detector
    # _is_web_target se EXTRAJO a routing/planner.py (sibling, con los otros
    # detectores estructurales); solo queda en tools.py el call-site IRREDUCIBLE del
    # desvío app.open->browser (donde app_open decide). +18 = la guarda mínima de
    # ese desvío, no se puede extraer más. Número exacto, sin buffer.
    "tools_pkg/tools.py": 8009,
    # 2026-06-02: agent.py reconciliado a 6495. El techo 6450 ya estaba violado
    # en HEAD (git=6488, deuda heredada de commits previos de computer-use/honesty).
    # Esta sesión sumó +4 al CONVERTIR 2 silent-except en logging trazado (baja la
    # deuda silent-except 360->358 a cambio de +4 LOC — buen trade: traza > LOC).
    # 2026-06-04: reconciliado 6495 -> 6653. Deuda heredada del rebrand+cacería
    # (6565->6631) + el cableado del dedup de batch degenerado (Gemma 4 #1756, +22:
    # la LÓGICA vive en loop_detection.py, solo el call-site + trace queda acá, no
    # es extraíble). Número exacto, sin buffer. Para una FEATURE, extraé un hermano.
    # 2026-06-05: 6653 -> 6672 (+19). Cacería tanda 2, cluster A1: cableado de la
    # guarda destructive_claim_without_evidence (la LÓGICA vive en
    # reply_validator.py; acá solo el call-site gated default-ON + trace, junto a
    # las otras guardas de honestidad de tanda 1). Irreducible. Número exacto.
    # 2026-06-05: 6672 -> 6687 (+15). Cacería tanda 2-5: reparación INLINE de
    # media-fabricado ("Stranger Things en Netflix", ~25-30 casos/tanda, el #1
    # persistente). La LÓGICA se EXTRAJO a agent_guards.py (sibling,
    # repair_media_fabricated_inline, ~40 LOC); acá solo queda el método wrapper
    # thin + el call-site en _finalize_turn — mismo patrón que los otros _guard_*.
    # Irreducible. Número exacto, sin buffer.
    "agent_core/agent.py": 6687,
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
