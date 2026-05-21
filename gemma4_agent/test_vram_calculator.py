"""Regression guard for the VRAM calculator + every profile's fit.

The calculator predicts per-profile VRAM from GGUF metadata + the llama.cpp KV
formula, WITHOUT a GPU. It is only trustworthy if it reproduces real
measurements — so we pin the exact server-log KV numbers here. If a future
profile change (model/ctx/vision) would OOM on 16 GB, `test_all_profiles_fit`
fails. If the formula drifts from reality, the anchor tests fail.

Skips gracefully if the model GGUFs aren't present (CI without weights)."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_CALC_PATH = _ROOT / "scripts" / "vram_calculator.py"

# Import the calculator module by path (it lives in scripts/, not the package).
_spec = importlib.util.spec_from_file_location("vram_calculator", _CALC_PATH)
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)

_26B = _ROOT / "models" / "26B-A4B" / "gemma-4-26B-A4B-it-UD-Q2_K_XL.gguf"


class TestKvFormulaMatchesMeasured(unittest.TestCase):
    """The formula must reproduce the real server-log KV cache sizes to the MiB.

    These anchors come from gemma4_agent/logs/llama-server.out.log (the 26B-A4B
    at two context sizes). If these pass, the calculator's predictions for other
    configs are trustworthy."""

    @unittest.skipUnless(_26B.is_file(), "26B GGUF not present")
    def test_26b_kv_at_16k(self):
        meta = vc.read_gguf_metadata(_26B)
        full, swa = vc.kv_cache_mib(meta, 16384, swa_full=True)
        self.assertEqual(round(full), 320, "non-SWA KV @16K (measured 320 MiB)")
        self.assertEqual(round(swa), 3200, "SWA KV @16K (measured 3200 MiB)")

    @unittest.skipUnless(_26B.is_file(), "26B GGUF not present")
    def test_26b_kv_at_8k(self):
        meta = vc.read_gguf_metadata(_26B)
        full, swa = vc.kv_cache_mib(meta, 8192, swa_full=True)
        self.assertEqual(round(full), 160, "non-SWA KV @8K (measured 160 MiB)")
        self.assertEqual(round(swa), 1600, "SWA KV @8K (measured 1600 MiB)")

    @unittest.skipUnless(_26B.is_file(), "26B GGUF not present")
    def test_kv_scales_linearly_with_ctx(self):
        meta = vc.read_gguf_metadata(_26B)
        f8, s8 = vc.kv_cache_mib(meta, 8192)
        f16, s16 = vc.kv_cache_mib(meta, 16384)
        self.assertAlmostEqual((f16 + s16) / (f8 + s8), 2.0, places=2)


class TestAllProfilesFit(unittest.TestCase):
    """Every server profile must be predicted to fit in 16 GB with margin.

    This is the guard that would have caught the 26B-Q2 @ctx16K OOM (15828 >
    15580). If someone bumps a profile to a model/ctx that won't fit, this
    turns red before it ever reaches the GPU."""

    GPU_TOTAL = 16380  # RTX 4060 Ti (dev/target ceiling)

    def test_all_profiles_fit(self):
        from gemma4_agent.profiles import PROFILES
        failures = []
        checked = 0
        for name, prof in PROFILES.items():
            if not prof.server_running or not prof.model_path:
                continue
            if not Path(prof.model_path).is_file():
                continue  # weights absent in this env
            checked += 1
            r = vc.predict_profile(name, self.GPU_TOTAL)
            if not r["ok"]:
                failures.append(f"{name}: {r['reason']}")
        if checked == 0:
            self.skipTest("no profile GGUFs present")
        self.assertEqual(failures, [], "profiles predicted to OOM: " + "; ".join(failures))

    def test_26b_default_would_not_fit_documents_the_decision(self):
        # Pin WHY vram12/16 are not the 26B: prove the 26B @ctx16K+vision OOMs.
        # If a future llama.cpp build shrinks the KV enough that this flips,
        # this test fails and we re-evaluate using the 26B again (good signal).
        if not _26B.is_file():
            self.skipTest("26B GGUF not present")
        meta = vc.read_gguf_metadata(_26B)
        weights = _26B.stat().st_size / vc.MIB
        full, swa = vc.kv_cache_mib(meta, 16384)
        total = (weights + full + swa + vc.COMPUTE_BUFFER_MIB
                 + vc.VISION_MMPROJ_MIB + vc.FORMULA_MARGIN_MIB)
        budget = self.GPU_TOTAL - vc.WDDM_RESERVE_MIB
        self.assertGreater(total, budget,
                           "26B-Q2 @ctx16K+vision should still exceed the 16GB "
                           "budget (justifies E4B-Q6 for vram12/16)")


if __name__ == "__main__":
    unittest.main()
