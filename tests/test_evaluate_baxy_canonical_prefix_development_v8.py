from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = (
    ROOT
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_canonical_prefix_development_v8.py"
)
SPEC = importlib.util.spec_from_file_location("baxy_canonical_prefix", PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Wake:
    @staticmethod
    def lexical_words(value: str) -> list[str]:
        return value.casefold().replace(".", "").split()


def test_canonical_prefix_accepts_bounded_measured_variants() -> None:
    assert MODULE.canonical_prefix_evidence("Baxy abre esto", Wake)
    assert MODULE.canonical_prefix_evidence("Baximan abre esto", Wake)


def test_canonical_prefix_rejects_observed_false_shapes() -> None:
    assert not MODULE.canonical_prefix_evidence("basi ends as that", Wake)
    assert not MODULE.canonical_prefix_evidence("these doors can be baxy", Wake)
    assert not MODULE.canonical_prefix_evidence("baximania abre esto", Wake)
