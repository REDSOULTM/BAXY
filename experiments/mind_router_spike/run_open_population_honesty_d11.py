"""Open the sealed current-tree open-population honesty cut D11 exactly once."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    build_open_population_honesty_d11 as campaign,
)
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
        raise RuntimeError("open-population D11 preregistration changed")
    if campaign.OUTPUT.exists():
        raise RuntimeError("open-population D11 has already been opened")


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
    passed = (
        not summary["contract_failures"]
        and not summary["control_regressions"]
        and not summary["catalogue_control_regressions"]
        and summary["unsolicited_effects"] == 0
        and not summary["fixed_constant_detected"]
        and summary["all_replies_distinct"]
    )
    report = {
        "schema": "baxy.open-population-honesty-d1-result.v1",
        "scope": "sealed_blind_open_population_honesty",
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
