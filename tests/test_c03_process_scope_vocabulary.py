"""Narrator descriptors are paraphrasable; observed literals remain protected."""

import copy

import pytest

from baxy_mind import llm


@pytest.mark.parametrize("descriptor,word", [
    ("completeness", "complete"),
    ("helpfulness", "helpful"),
    ("carefulness", "careful"),
    ("brightness", "bright"),
])
@pytest.mark.parametrize("field", ["observationScope", "unit"])
@pytest.mark.parametrize("shape", ["direct", "nested_dict", "nested_sequence"])
def test_narrator_descriptors_do_not_supply_literal_truncation_vocabulary(
    descriptor: str, word: str, field: str, shape: str,
) -> None:
    facts = {field: descriptor}
    if shape == "nested_dict":
        facts = {"seen": {"quantity": facts}}
    elif shape == "nested_sequence":
        facts = {"seen": {"rows": [({"quantity": facts},)]}}
    original = copy.deepcopy(facts)

    assert not llm._truncated_fact_word(word, facts)
    assert facts == original


@pytest.mark.parametrize("literal,word", [
    ("completeness", "complete"),
    ("selectivity", "select"),
    ("AtlasHelper", "Atlas"),
    ("enfocar", "enfoc"),
])
@pytest.mark.parametrize("field", ["name", "processName", "title", "process_identity", "literal", "can"])
def test_literal_values_still_supply_truncation_vocabulary(
    literal: str, word: str, field: str,
) -> None:
    facts = {"seen": {"rows": [{field: [literal]}]}}
    original = copy.deepcopy(facts)

    assert llm._truncated_fact_word(word, facts)
    assert facts == original


def test_descriptors_cannot_mask_a_truncated_observed_name() -> None:
    facts = {"seen": {
        "observationScope": "complete",
        "observedProcessCount": {"value": 2, "unit": "complete"},
        "processes": [{"name": "completeness"}],
    }}
    original = copy.deepcopy(facts)

    assert llm._truncated_fact_word("complete", facts)
    assert facts == original


def test_nested_keys_are_still_excluded_and_short_literal_names_still_count() -> None:
    facts = {"seen": {"observation": [{"name": "AtlasHelper", "title": "Atlas"}]}}
    original = copy.deepcopy(facts)

    assert not llm._truncated_fact_word("observa Atlas", facts)
    assert facts == original
