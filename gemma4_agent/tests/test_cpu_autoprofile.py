"""Auto-perfil CPU sin GPU NVIDIA.

En una máquina sin NVIDIA usable, el binario vram4 (CUDA-only) no arranca. El
agente debe AUTO-CAER al perfil 'cpu' (E2B-Q4 en CPU, 0 VRAM) en vez de fallar
en el boot. Sin afectar a usuarios con NVIDIA (siguen en vram4).

Tests sin hardware especial: usamos el override GEMMA4_LLAMA_GPU_VENDOR y mocks
de has_usable_cuda_gpu para simular ambos mundos.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gemma4_agent.infra import profiles


class HasUsableCudaGpuTest(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("GEMMA4_LLAMA_GPU_VENDOR")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("GEMMA4_LLAMA_GPU_VENDOR", None)
        else:
            os.environ["GEMMA4_LLAMA_GPU_VENDOR"] = self._saved

    def test_vendor_override_cuda_forces_true(self):
        os.environ["GEMMA4_LLAMA_GPU_VENDOR"] = "cuda"
        self.assertTrue(profiles.has_usable_cuda_gpu())

    def test_vendor_override_cpu_forces_false(self):
        for v in ("cpu", "vulkan", "hip", "rocm", "none"):
            os.environ["GEMMA4_LLAMA_GPU_VENDOR"] = v
            self.assertFalse(profiles.has_usable_cuda_gpu(), v)

    def test_no_nvidia_smi_is_false(self):
        os.environ.pop("GEMMA4_LLAMA_GPU_VENDOR", None)
        with patch("gemma4_agent.infra.profiles.subprocess.run",
                   side_effect=FileNotFoundError):
            self.assertFalse(profiles.has_usable_cuda_gpu())

    def test_nvidia_present_is_true(self):
        os.environ.pop("GEMMA4_LLAMA_GPU_VENDOR", None)
        fake = type("R", (), {"returncode": 0, "stdout": "NVIDIA GeForce RTX 4060 Ti\n"})()
        with patch("gemma4_agent.infra.profiles.subprocess.run", return_value=fake):
            self.assertTrue(profiles.has_usable_cuda_gpu())


class RecommendProfileTest(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in
                       ("GEMMA4_LLAMA_GPU_VENDOR", "GEMMA4_NO_GPU_AUTOCPU")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_nvidia_gets_vram4(self):
        with patch("gemma4_agent.infra.profiles.has_usable_cuda_gpu", return_value=True):
            self.assertEqual(profiles.recommend_profile(None), "vram4")

    def test_no_gpu_gets_cpu(self):
        with patch("gemma4_agent.infra.profiles.has_usable_cuda_gpu", return_value=False):
            self.assertEqual(profiles.recommend_profile(None), "cpu")

    def test_gate_off_keeps_vram4_even_without_gpu(self):
        # GEMMA4_NO_GPU_AUTOCPU=0 -> diagnóstico: vuelve al comportamiento viejo.
        os.environ["GEMMA4_NO_GPU_AUTOCPU"] = "0"
        with patch("gemma4_agent.infra.profiles.has_usable_cuda_gpu", return_value=False):
            self.assertEqual(profiles.recommend_profile(None), "vram4")

    def test_cpu_profile_exists_and_is_gpuless(self):
        # El perfil 'cpu' al que caemos debe existir y NO usar GPU.
        self.assertIn("cpu", profiles.PROFILES)
        self.assertEqual(profiles.PROFILES["cpu"].n_gpu_layers, 0)
        self.assertEqual(profiles.PROFILES["cpu"].est_vram_mb, 0)


if __name__ == "__main__":
    unittest.main()
