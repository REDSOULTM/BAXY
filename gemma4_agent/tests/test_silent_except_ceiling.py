"""Guard de observabilidad (Point 2 de la limpieza 2026-06-01).

Hay ~371 `except (Exception|BaseException): pass` que tragan LÓGICA en silencio. Muchos
son best-effort intencional, PERO el patrón esconde bugs reales (caso `_os` NameError que
apagó TODA la validación de reply sin un solo log). No se pueden convertir los 371 a mano
sin riesgo, así que este guard CONGELA el número: si crece, el que sumó un swallow nuevo
debe loguearlo (silent_fallback/trace/logger) en vez de tragarlo — o justificar y subir el
techo acá. Mismo patrón que el techo de lazy-imports.

Inventario reproducible: scripts/_diag/_silent_except_audit.py (AST, distingue
telemetría benigna de lógica peligrosa).
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

# Techo MEDIDO 2026-06-01 sobre el código ESTABLE del agente (el audit excluye
# vision_input/ = subsistema de cámara en desarrollo por otro workstream). NO subir sin
# justificar: si tu cambio agrega un `except ...: pass` alrededor de LÓGICA, logueá el
# error (trace/logger) en vez de tragarlo. La observabilidad atrapó los bugs de esta semana.
SILENT_LOGIC_CEILING = 358


def _load_audit():
    path = (Path(__file__).resolve().parents[2]
            / "scripts" / "_diag" / "_silent_except_audit.py")
    spec = importlib.util.spec_from_file_location("_silent_except_audit", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class SilentExceptCeilingTest(unittest.TestCase):
    def test_silent_logic_swallows_do_not_grow(self):
        mod = _load_audit()
        telemetry, logic, sites = mod.audit()
        self.assertLessEqual(
            logic, SILENT_LOGIC_CEILING,
            f"{logic} `except: pass` tragando LÓGICA en silencio (techo "
            f"{SILENT_LOGIC_CEILING}). Si sumaste uno: logueá el error en vez de "
            f"tragarlo (trace/silent_fallback/logger). Sitios nuevos sospechosos:\n"
            + "\n".join(sites[-8:]),
        )


if __name__ == "__main__":
    unittest.main()
