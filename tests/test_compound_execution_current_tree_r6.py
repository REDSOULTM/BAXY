from __future__ import annotations

import json

from experiments.mind_router_spike import (
    build_compound_execution_current_tree_r5 as r5,
    build_compound_execution_current_tree_r6 as campaign,
)


def test_current_tree_compound_r6_covers_every_dependent_clause_shape() -> None:
    cases = campaign.build_cases("RUNID", "DOCUMENT")
    campaign.validate_cases(cases)
    assert len(campaign.case_contract_sha256()) == 64
    assert len(cases) == 6
    assert sum(len(case["expected"]) for case in cases) == 22
    current = {" ".join(str(case["objective"]).casefold().split()) for case in cases}
    assert current.isdisjoint(campaign._prior_objectives())
    r5_objectives = {
        " ".join(str(case["objective"]).casefold().split())
        for case in r5.build_cases("RUNID", "DOCUMENT")
    }
    assert current.isdisjoint(r5_objectives)


def test_current_tree_compound_r6_is_sealed_unopened() -> None:
    assert campaign.PREREGISTRATION.exists()
    assert not campaign.OUTPUT.exists()
    manifest = json.loads(campaign.PREREGISTRATION.read_text(encoding="utf-8"))
    assert manifest["blind_holdout"] is True
    assert manifest["preregistered_before_measurement"] is True
    assert manifest["measurement_status"] == "unopened"
    assert manifest["supersedes"]["reuse_for_promotion_forbidden"] is True
    assert manifest["population"]["case_contract_sha256"] == (
        campaign.case_contract_sha256()
    )
