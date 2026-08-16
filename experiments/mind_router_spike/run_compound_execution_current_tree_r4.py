"""Open the sealed current-tree Cut-C campaign exactly once."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiments.mind_router_spike import (  # noqa: E402
    build_compound_execution_current_tree_r4 as campaign,
)
from scripts import build_compound_execution_holdout_r1 as common  # noqa: E402
from scripts import run_llm_plan_execution_gate as gate  # noqa: E402


def _hashes(paths: tuple[Path, ...]) -> dict[str, str]:
    return {str(path.relative_to(REPO)): common._sha256(path) for path in paths}


def verify_preregistration() -> None:
    manifest = json.loads(campaign.PREREGISTRATION.read_text(encoding="utf-8"))
    if (
        manifest.get("blind_holdout") is not True
        or manifest.get("preregistered_before_measurement") is not True
        or manifest.get("measurement_status") != "unopened"
        or manifest.get("population", {}).get("case_contract_sha256")
        != campaign.case_contract_sha256()
        or manifest.get("sources", {}).get("builder_sha256")
        != common._sha256(Path(campaign.__file__).resolve())
        or manifest.get("sources", {}).get("builder_dependencies_sha256")
        != _hashes(campaign.BUILDER_DEPENDENCIES)
        or manifest.get("sources", {}).get("measurement_sha256")
        != _hashes(campaign.MEASUREMENT_SOURCES)
        or manifest.get("sources", {}).get("policy_sha256")
        != _hashes(campaign.POLICY_SOURCES)
    ):
        raise RuntimeError("current-tree compound R4 preregistration changed")
    if campaign.OUTPUT.exists():
        raise RuntimeError("current-tree compound R4 has already been opened")


def main() -> int:
    verify_preregistration()
    gate.OUTPUT = campaign.OUTPUT
    gate.build_cases = campaign.build_cases
    gate.main()
    report = json.loads(campaign.OUTPUT.read_text(encoding="utf-8"))
    summary = report.get("summary", {})
    if (
        summary.get("status") != "passed"
        or summary.get("total") != 6
        or summary.get("passed") != 6
        or summary.get("verified_steps") != 31
        or summary.get("real_llm_plan_cases") != 6
        or summary.get("real_llm_plan_cases_passed") != 6
        or summary.get("ambiguous_effects") != 0
    ):
        raise RuntimeError("current-tree compound R4 missed its sealed threshold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
