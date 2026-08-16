"""Reject R252 before model import when its sealed 31-family evaluation is unavailable."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import preregister_bge_m3_prototype_domain_r252 as r252
from experiments.mind_router_spike import run_bge_m3_prototype_domain_r253 as r253


OUTPUT = REPO / "artifacts/audit/bge_m3_prototype_domain_r253_preexecution_rejection.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    preregistration = json.loads(r252.OUTPUT.read_text(encoding="utf-8"))
    if preregistration != r252.build():
        raise RuntimeError("R253 requires the sealed R252 preregistration")
    all_inside, _ = r253.r243._rows()
    r236_inside, r236_outside = r253.r236.sample_rows()
    r243_inside, r243_outside, r243_train = r253.r243._sample_development_rows()
    r246_inside, r246_outside, r246_train = r253.r246.development_rows()
    r250_inside, r250_outside, _ = r253.r248.development_rows()
    reserved = {row["source_id"] for row in [*r236_inside, *r236_outside, *r243_inside, *r243_outside, *r243_train, *r246_inside, *r246_outside, *r246_train, *r250_inside, *r250_outside]}
    available_families = {row["families"][0] for row in all_inside if row["source_id"] not in reserved}
    if len(available_families) >= 31:
        raise RuntimeError("R253 only attests the documented insufficient family population")
    return {"schema": "baxy.bge-m3-prototype-domain.r253-preexecution-rejection.v1", "authority": "read_only_preexecution_attestation_no_model_import_or_training", "verdict": "rejected_preexecution_insufficient_fresh_inside_family_coverage", "reason": "R252 requires a 31-family fresh inside evaluation, but the remaining public PRESTO/MASSIVE rows cover fewer families after every R236/R241/R243/R246/R250 reservation.", "observed": {"available_families": len(available_families), "required_families": 31, "required_inside_rows": r253.INSIDE_COUNT}, "constraints": {"model_started": False, "r228_opened": False, "public_holdout_opened": False, "registered_runtime_modified": False, "providers_enabled": False, "effects_executed": 0, "opened_v9": False, "voice_stt_wake_exercised": False}, "identities": {"r252_sha256": sha256(r252.OUTPUT), "runner_sha256": sha256(Path(r253.__file__)), "program_sha256": sha256(Path(__file__))}, "next_requirement": "Do not run or alter R253. A successor needs a new full-coverage in-catalog development source, separately sealed before model import."}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite attestation: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
