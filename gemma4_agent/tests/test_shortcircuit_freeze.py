"""Congela el treadmill de short-circuits deterministas (Point 4, 2026-06-01).

`_decide_turn` tiene 6 short-circuits que bypassean el LLM (arithmetic, calc, app_action,
app_open, deterministic_reply, phrase_trigger). Cada uno nació de un bug medido, pero
acumularlos pelea con CLAUDE.md regla (b) ("el LLM responde"). Este guard exige que un
short-circuit NUEVO venga con medición + suba el techo a propósito. Ver
documentacion/ADR_short_circuits_freeze.md.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

# Techo MEDIDO 2026-06-01. NO subir sin: (1) medición en vivo de que el LLM no lo hace
# fiable, (2) que no lo cubra uno existente, (3) justificación acá. Ver el ADR.
SHORTCIRCUIT_CEILING = 6


def _shortcircuits() -> list[str]:
    src = (Path(__file__).resolve().parents[1] / "agent_core" / "agent.py").read_text(
        encoding="utf-8", errors="replace")
    return sorted(set(re.findall(r'"([a-z_]+_shortcircuit)"', src)))


class ShortCircuitFreezeTest(unittest.TestCase):
    def test_no_new_deterministic_shortcircuits(self):
        sc = _shortcircuits()
        self.assertLessEqual(
            len(sc), SHORTCIRCUIT_CEILING,
            f"{len(sc)} short-circuits deterministas {sc} (techo {SHORTCIRCUIT_CEILING}). "
            "Agregaste uno: el LLM debería responder salvo que MIDAS que no puede. "
            "Ver documentacion/ADR_short_circuits_freeze.md y subí el techo con la "
            "medición si está justificado.",
        )


if __name__ == "__main__":
    unittest.main()
