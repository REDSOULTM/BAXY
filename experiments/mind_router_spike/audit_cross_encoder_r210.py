"""Audit the frozen R209 cross-encoder result without changing runtime."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRE = REPO / "artifacts/development/cross_encoder_r208_preregistration.json"
RESULT = REPO / "artifacts/development/cross_encoder_r209_attested.json"
OUT = REPO / "artifacts/audit/cross_encoder_r209_audit_r210.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(preregistration: Path = PRE, result_path: Path = RESULT) -> dict[str, object]:
    prereg = json.loads(preregistration.read_text(encoding="utf8"))
    result = json.loads(result_path.read_text(encoding="utf8"))
    measured = result["result"]
    exact_required = int(prereg["evaluation"]["model_owned_rows"] * prereg["evaluation"]["exact_rate_required"] + 0.999999)
    oos_required = prereg["evaluation"]["oos_zero_candidates_required"]
    accepted = measured["raw_exact"] >= exact_required and measured["oos_zero_candidates"] == oos_required
    return {
        "schema": "baxy.cross-encoder-r209-audit-r210.v1",
        "verdict": "promote_candidate" if accepted else "reject_candidate",
        "reason": {"exact_required": exact_required, "exact_measured": measured["raw_exact"], "oos_zero_candidates_required": oos_required, "oos_zero_candidates_measured": measured["oos_zero_candidates"], "p95_seconds": measured["p95_seconds"]},
        "training": result["training"],
        "identities": {"program_sha256": sha(Path(__file__)), "preregistration_sha256": sha(preregistration), "result_sha256": sha(result_path)},
        "constraints": {"runtime_modified": False, "providers_enabled": False, "external_effects_executed": 0, "opened_v9": False, "no_retriever": True, "no_lexical_gate": True},
    }


def main() -> None:
    OUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


if __name__ == "__main__":
    main()
