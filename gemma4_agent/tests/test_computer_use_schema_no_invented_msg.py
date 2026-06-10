"""Regresión del bug "escribile hola inventado" (2026-06-09, reporte del user).

BUG real (en vivo): "Ve a Cotele en Discord" (SOLO navegar) -> el 4B armó goal
"andá a discord al chat de cotele y escribile hola" — inventó el "escribile hola".
Causa: el schema de computer_use tenía como ejemplo ESTRELLA "andá a discord al
chat de juan y escribile hola", contaminando el few-shot: el 4B copiaba el patrón
y pegaba el mensaje aunque el user no lo pidiera.

Fix: el ejemplo principal pasó a navegar-SOLO + instrucción explícita de copiar
solo lo que el user pidió. Este test fija que:
  - el schema instruye NO inventar un mensaje cuando el user solo quiere ir,
  - el ejemplo de navegar-solo (sin 'escribile hola') está presente.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS


def _cu_desc() -> str:
    s = next((t for t in COMPOUND_TOOL_SCHEMAS
              if t.get("function", {}).get("name") == "computer_use"), None)
    assert s is not None, "computer_use schema not found"
    return s["function"]["description"].lower()


class TestComputerUseSchemaNoInventedMessage(unittest.TestCase):
    def test_schema_instructs_not_to_invent_a_message(self):
        desc = _cu_desc()
        # debe instruir copiar SOLO lo que el user pidió / no inventar texto
        # (el schema de tool_schemas está en español: "no inventes/no agregues").
        self.assertTrue(
            "copiá solo lo que el usuario pidió" in desc
            or "no inventes un mensaje" in desc
            or "no agregues" in desc,
            "el schema debe instruir NO inventar un mensaje al solo navegar",
        )

    def test_schema_has_go_only_example_without_hola(self):
        desc = _cu_desc()
        # debe existir un ejemplo de IR a un chat SIN un 'escribile hola' pegado.
        # (el ejemplo 'andá al chat de juan en discord' va solo, sin mensaje.)
        self.assertIn("andá al chat de juan en discord", desc)
        # y la mención de 'escribile hola' solo aparece como lo que NO hay que hacer
        # (en la instrucción negativa), no como ejemplo positivo de navegación.
        self.assertIn("escribile hola", desc)  # presente en la instrucción negativa


if __name__ == "__main__":
    unittest.main()
