from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "voice_latency"
    / "evaluate_baxy_contextual_fusion_development_v4.py"
)
SPEC = importlib.util.spec_from_file_location(
    "evaluate_baxy_contextual_fusion_development_v4", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from baxy_mind import wake_verifier as WAKE  # noqa: E402


def test_contextual_evidence_covers_measured_bounded_renderings() -> None:
    assert MODULE.has_contextual_wake_evidence("Báximan explica", WAKE) is True
    assert MODULE.has_contextual_wake_evidence("del grupo basi roca", WAKE) is True
    assert MODULE.has_contextual_wake_evidence("nuestra caldera paz y roca", WAKE) is True
    assert MODULE.has_contextual_wake_evidence("Отдел сервиса Бакси", WAKE) is True


def test_contextual_evidence_does_not_admit_broad_prefixes() -> None:
    assert MODULE.has_contextual_wake_evidence("the large basin", WAKE) is False
    assert MODULE.has_contextual_wake_evidence("back in the room", WAKE) is False
    assert MODULE.has_contextual_wake_evidence("baximander", WAKE) is False


def test_guard_requires_both_fallback_signals() -> None:
    assert MODULE.guarded_acceptance(
        established_ctc_accepted=True,
        fixed_fusion_accepted=False,
        contextual_lexical_evidence=False,
    ) == (True, "established_ctc")
    assert MODULE.guarded_acceptance(
        established_ctc_accepted=False,
        fixed_fusion_accepted=True,
        contextual_lexical_evidence=True,
    ) == (True, "contextually_guarded_fixed_fusion")
    assert MODULE.guarded_acceptance(
        established_ctc_accepted=False,
        fixed_fusion_accepted=True,
        contextual_lexical_evidence=False,
    ) == (False, "rejected")
    assert MODULE.guarded_acceptance(
        established_ctc_accepted=False,
        fixed_fusion_accepted=False,
        contextual_lexical_evidence=True,
    ) == (False, "rejected")
