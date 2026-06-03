"""Selección preferente de mmproj cuantizado SI existe, con fallback
transparente al F16.

VERIFICADO (medido): el mmproj-Q8_0 NO existe hoy (Unsloth solo publica
F16/F32/BF16; llama-quantize falla con 'unsupported architecture: clip', feature
abierto issue #18881). Por eso esta función NO cambia el comportamiento hoy
(devuelve F16); deja el agente listo para cuando aparezca una variante Q*.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gemma4_agent.infra.profiles import _resolve_mmproj_path


class MmprojResolverTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("GEMMA4_MMPROJ_PREFER_QUANT")
        os.environ.pop("GEMMA4_MMPROJ_PREFER_QUANT", None)

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("GEMMA4_MMPROJ_PREFER_QUANT", None)
        else:
            os.environ["GEMMA4_MMPROJ_PREFER_QUANT"] = self._saved

    def test_only_f16_returns_f16(self):
        # El caso de HOY: solo F16 en disco -> F16 (0 cambio de comportamiento).
        with TemporaryDirectory() as td:
            d = Path(td)
            (d / "mmproj-F16.gguf").write_bytes(b"x")
            self.assertTrue(_resolve_mmproj_path(d).endswith("mmproj-F16.gguf"))

    def test_prefers_q8_when_present(self):
        # Cuando exista un Q8_0 (futuro), se elige sobre el F16.
        with TemporaryDirectory() as td:
            d = Path(td)
            (d / "mmproj-F16.gguf").write_bytes(b"x")
            (d / "mmproj-Q8_0.gguf").write_bytes(b"x")
            self.assertTrue(_resolve_mmproj_path(d).endswith("mmproj-Q8_0.gguf"))

    def test_prefers_smallest_quant_first(self):
        # Q4 (más chico) gana sobre Q8 si ambos existen.
        with TemporaryDirectory() as td:
            d = Path(td)
            for n in ("mmproj-F16.gguf", "mmproj-Q8_0.gguf", "mmproj-Q4_K_M.gguf"):
                (d / n).write_bytes(b"x")
            self.assertTrue(_resolve_mmproj_path(d).endswith("mmproj-Q4_K_M.gguf"))

    def test_bf16_not_preferred(self):
        # BF16 (~987 MiB) es MÁS grande que F16 (~940): NO debe preferirse.
        with TemporaryDirectory() as td:
            d = Path(td)
            (d / "mmproj-F16.gguf").write_bytes(b"x")
            (d / "mmproj-BF16.gguf").write_bytes(b"x")
            self.assertTrue(_resolve_mmproj_path(d).endswith("mmproj-F16.gguf"))

    def test_gate_off_forces_f16(self):
        os.environ["GEMMA4_MMPROJ_PREFER_QUANT"] = "0"
        with TemporaryDirectory() as td:
            d = Path(td)
            (d / "mmproj-F16.gguf").write_bytes(b"x")
            (d / "mmproj-Q8_0.gguf").write_bytes(b"x")
            self.assertTrue(_resolve_mmproj_path(d).endswith("mmproj-F16.gguf"))


if __name__ == "__main__":
    unittest.main()
