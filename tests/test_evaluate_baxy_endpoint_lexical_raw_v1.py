from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT / "experiments" / "voice_latency" / "evaluate_baxy_endpoint_lexical_raw_v1.py"
)
SPEC = importlib.util.spec_from_file_location("evaluate_endpoint_lexical", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_endpoint_aliases_include_measured_pronunciations() -> None:
    config = SimpleNamespace(
        lexical_aliases=frozenset(("baxy", "baxi", "boxy")),
    )

    assert MODULE.endpoint_aliases(config) == frozenset(
        ("baxy", "baxi", "bakse", "backsy", "boxy")
    )


def test_endpoint_match_does_not_depend_on_command_suffix() -> None:
    matcher = MODULE.match_suffix_independent_endpoint_wake
    aliases = frozenset(("baxy", "baxi", "bakse", "backsy"))

    assert matcher(("Baxy frobnicate the seventh pane",), aliases) is not None
    assert matcher(("Basi frobnicate the seventh pane",), aliases) is None
    assert matcher(("please ask Baxy to open Spotify",), aliases) is None


def test_evaluator_exposes_reproducible_strict_and_bounded_policies() -> None:
    parser = MODULE._parser()
    assert parser.get_default("policy") == "strict_score_gated"
    assert parser.get_default("endpoint_direct_score_gte") is None
    choices = next(
        action.choices for action in parser._actions if action.dest == "policy"
    )
    assert tuple(choices) == (
        "strict_score_gated",
        "strict_endpoint",
        "bounded_development",
    )


def test_score_gated_policy_requires_independent_acoustic_evidence() -> None:
    aliases = frozenset(("baxy", "baxi", "bakse", "backsy", "boxy"))
    common = {
        "policy": "strict_score_gated",
        "phonetic_confusion_score_gte": 4.0,
        "endpoint_direct_score_gte": -1.0,
    }

    assert (
        MODULE.match_endpoint_policy(
            "Baxy open settings", aliases, verifier_score=-1.01, **common
        )
        is None
    )
    assert (
        MODULE.match_endpoint_policy(
            "Baxy open settings", aliases, verifier_score=-1.0, **common
        )
        is not None
    )
