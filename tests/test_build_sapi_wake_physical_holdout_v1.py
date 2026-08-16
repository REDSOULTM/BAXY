from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_sapi_wake_physical_holdout_v1.py"
SPEC = importlib.util.spec_from_file_location("build_sapi_wake_holdout", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_specs_are_deterministic_balanced_and_unique() -> None:
    first = MODULE.build_specs(label="positive", count=96, seed=9701)
    second = MODULE.build_specs(label="positive", count=96, seed=9701)

    assert first == second
    assert len(set(first)) == 96
    assert {item.language for item in first} == {"es", "en"}
    assert {item.rate for item in first} == {-3, -1, 1, 3}
    assert all(item.text.strip() for item in first)


def test_negative_specs_do_not_contain_wake_spellings() -> None:
    specs = MODULE.build_specs(label="negative", count=192, seed=9701)

    assert len(set(specs)) == 192
    for item in specs:
        words = set(re.findall(r"[a-záéíóúñ]+", item.text.casefold()))
        assert words.isdisjoint({"baxy", "baxi", "basi"})


@pytest.mark.parametrize(("label", "count"), [("unknown", 1), ("positive", 0)])
def test_invalid_spec_request_fails_closed(label: str, count: int) -> None:
    with pytest.raises(ValueError, match="sapi_wake_holdout_spec_invalid"):
        MODULE.build_specs(label=label, count=count, seed=1)


def test_population_limit_is_enforced() -> None:
    with pytest.raises(ValueError, match="sapi_wake_holdout_population_insufficient"):
        MODULE.build_specs(label="positive", count=10_000, seed=1)


def test_endpoint_suffix_profile_uses_unseen_commands_and_no_bare_wake() -> None:
    specs = MODULE.build_specs(
        label="positive",
        count=96,
        seed=9701,
        profile="endpoint_suffix_development",
    )

    assert len(specs) == 96
    assert all(len(item.text.split()) > 1 for item in specs)
    assert any("explorador de archivos" in item.text for item in specs)
    assert any("settings window" in item.text for item in specs)


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(ValueError, match="sapi_wake_holdout_profile_invalid"):
        MODULE.build_specs(label="positive", count=1, seed=1, profile="unknown")


def test_endpoint_confusable_profile_contains_command_shaped_negatives() -> None:
    specs = MODULE.build_specs(
        label="negative",
        count=96,
        seed=9701,
        profile="endpoint_confusable_development",
    )

    assert len(specs) == 96
    assert any(item.text == "Basic lower the screen brightness" for item in specs)
    assert any(item.text == "Vas y muestrame los procesos activos" for item in specs)
