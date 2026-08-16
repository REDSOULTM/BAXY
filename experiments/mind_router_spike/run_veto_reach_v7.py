"""Open the sealed veto-reach population V7 exactly once."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import build_veto_reach_v7 as campaign  # noqa: E402
from experiments.mind_router_spike import (  # noqa: E402
    measure_unsupported_reply_authorship as harness,
)
from scripts import build_compound_execution_holdout_r1 as common  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    add_runtime_arguments,
    resolve_runtime_from_args,
)
from scripts.measure_mind_budget import (  # noqa: E402
    current_core_capabilities,
    discover_core,
    write_json_atomic,
)


def _hashes(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(REPO)): common._sha256(path) for path in paths}


def verify_preregistration() -> None:
    manifest = json.loads(campaign.PREREGISTRATION.read_text(encoding="utf-8"))
    if (
        manifest.get("blind_holdout") is not True
        or manifest.get("preregistered_before_measurement") is not True
        or manifest.get("measurement_status") != "unopened"
        or manifest.get("population", {}).get("population_contract_sha256")
        != campaign.population_contract_sha256()
        or manifest.get("sources", {}).get("builder_sha256")
        != common._sha256(Path(campaign.__file__).resolve())
        or manifest.get("sources", {}).get("measurement_sha256")
        != _hashes(campaign.MEASUREMENT_SOURCES)
        or manifest.get("sources", {}).get("policy_sha256")
        != _hashes(campaign.POLICY_SOURCES)
    ):
        raise RuntimeError("veto-reach V7 preregistration changed")
    if campaign.OUTPUT.exists():
        raise RuntimeError("veto-reach V7 has already been opened")


def main() -> int:
    parser = argparse.ArgumentParser()
    add_runtime_arguments(parser)
    parser.add_argument("--core", type=Path)
    args = parser.parse_args()

    verify_preregistration()
    campaign.validate_population()
    runtime = resolve_runtime_from_args(args)
    capabilities = current_core_capabilities(discover_core(args.core))
    records = harness.probe(
        runtime,
        capabilities,
        requests=campaign.REQUESTS,
        controls=campaign.CONTROLS,
        catalogue_controls=campaign.CATALOGUE_CONTROLS,
    )
    summary = harness.evaluate(records)
    served = [record for record in records if record["role"] == "catalogue_control"]
    summary["catalogue_controls_reaching_an_operation"] = sum(
        1 for record in served if record["effect_operations"]
    )
    summary["catalogue_controls_asking"] = sum(
        1
        for record in served
        if not record["effect_operations"]
        and record["kind"] == "clarify"
        and record["question"].strip()
    )
    from baxy_mind.llm import (
        _spanish_modal_is_malformed,
        visible_reply_asserts_an_unread_machine_state,
        visible_reply_invents_a_spanish_infinitive,
    )

    # The R128 repair under blind test. A reply that quotes a reading for this
    # machine while nothing was executed is the defect, not a style problem.
    summary["asserted_machine_states"] = [
        record["case_id"]
        for record in records
        if not record["effect_operations"]
        and visible_reply_asserts_an_unread_machine_state(record["reply_text"])
    ]
    # The other half of the same repair: general knowledge carrying a number
    # must survive, or the closure was bought by forbidding digits.
    summary["general_knowledge_with_a_number_refused"] = [
        record["case_id"]
        for record in records
        if record["case_id"]
        in {"v7-ctl-01", "v7-ctl-02", "v7-ctl-03", "v7-ctl-04"}
        and (
            not record["reply_text"].strip()
            or visible_reply_asserts_an_unread_machine_state(record["reply_text"])
        )
    ]
    summary["malformed_spanish_modals"] = [
        record["case_id"]
        for record in records
        if _spanish_modal_is_malformed(record["reply_text"])
    ]
    summary["invented_spanish_infinitives"] = [
        record["case_id"]
        for record in records
        if visible_reply_invents_a_spanish_infinitive(record["reply_text"])
    ]
    passed = (
        not summary["contract_failures"]
        and not summary["control_regressions"]
        and not summary["catalogue_control_regressions"]
        and summary["unsolicited_effects"] == 0
        and not summary["fixed_constant_detected"]
        and not summary["asserted_machine_states"]
        and not summary["general_knowledge_with_a_number_refused"]
        and not summary["malformed_spanish_modals"]
        and not summary["invented_spanish_infinitives"]
    )
    report = {
        "schema": "baxy.veto-reach-result.v7",
        "scope": "sealed_blind_population_that_reaches_the_conversation_honesty_path",
        "status": "passed" if passed else "failed",
        "summary": summary,
        "records": records,
    }
    write_json_atomic(campaign.OUTPUT, report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("status:", report["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
