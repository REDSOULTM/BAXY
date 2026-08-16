"""Record the corrected read-only runtime preflight after R222's schema fix."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import probe_runtime_manifest_r222 as r222  # noqa: E402


OUTPUT = REPO / "artifacts/audit/runtime_manifest_preflight_r223.json"


def build() -> dict[str, object]:
    report = r222.build()
    return {
        **report,
        "schema": "baxy.runtime-manifest-preflight.r223.v1",
        "authority": "read_only_runtime_identity_preflight_correcting_r222_attribution",
        "correction": {
            "r222_outcome_not_rewritten": True,
            "r222_error_attribution": "obsolete_python_verifier_rejected_per_file_stt_identity",
            "current_per_file_stt_identity_verified": report["outcome"]["resolved"],
        },
        "identities": {
            "program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "r222_program_sha256": r222.sha256(
                r222.REPO
                / "experiments/mind_router_spike/probe_runtime_manifest_r222.py"
            ),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite runtime preflight: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
