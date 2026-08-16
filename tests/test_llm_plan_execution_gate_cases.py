from __future__ import annotations

import pytest

from scripts.run_llm_plan_execution_gate import build_physical_voice_case


@pytest.mark.parametrize("operation", ["audio.status", "system.status"])
def test_physical_voice_case_accepts_only_bounded_read_only_operations(
    operation: str,
) -> None:
    case = build_physical_voice_case("Baxy, dime el estado", operation)
    assert case["expected"] == [operation]
    assert case["confirm"] == set()


@pytest.mark.parametrize(
    ("text", "operation"),
    [("", "system.status"), ("Baxy, abre Chrome", "app.open")],
)
def test_physical_voice_case_rejects_unbounded_or_effectful_requests(
    text: str, operation: str
) -> None:
    with pytest.raises(ValueError, match="bounded read-only"):
        build_physical_voice_case(text, operation)
