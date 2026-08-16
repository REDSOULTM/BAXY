from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "voice_latency"))
from benchmark_phoneme_teacher_onnx_v1 import (  # noqa: E402
    compress_category_logits_numpy,
    latency_summary,
)
from phoneme_student_vocabulary_v2 import CATEGORY_NAMES  # noqa: E402


def test_numpy_category_compression_is_normalized() -> None:
    logits = np.zeros((1, 3, len(CATEGORY_NAMES)), dtype=np.float32)
    category_ids = {
        name: (index,) for index, name in enumerate(CATEGORY_NAMES)
    }
    result = compress_category_logits_numpy(logits, category_ids)
    assert result.shape == (3, len(CATEGORY_NAMES))
    np.testing.assert_allclose(result.sum(axis=1), 1.0)


def test_latency_summary_reports_exact_median() -> None:
    result = latency_summary([1.0, 2.0, 9.0])
    assert result["median_milliseconds"] == 2.0
    assert result["iterations"] == 3
