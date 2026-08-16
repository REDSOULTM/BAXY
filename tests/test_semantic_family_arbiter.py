from __future__ import annotations

import numpy as np

from baxy_mind.semantic_family_arbiter import (
    EXPECTED_MANIFEST_SHA256,
    MANIFEST,
    SemanticFamilyArbiter,
    _sha256,
)


def test_semantic_family_arbiter_manifest_is_attested() -> None:
    assert _sha256(MANIFEST) == EXPECTED_MANIFEST_SHA256


def test_semantic_family_arbiter_returns_only_available_families() -> None:
    arbiter = SemanticFamilyArbiter()
    _classes, _coefficients, _intercept, dimensions = arbiter._resources

    ranked = arbiter.rank(
        np.zeros(dimensions, dtype=np.float32),
        {"audio", "calendar"},
        count=2,
    )

    assert len(ranked) == 2
    assert {prediction.family for prediction in ranked} == {"audio", "calendar"}


def test_semantic_family_arbiter_abstains_on_invalid_embedding() -> None:
    arbiter = SemanticFamilyArbiter()

    assert arbiter.rank([float("nan")], {"audio"}) == ()
    assert arbiter.rank([], {"audio"}) == ()
