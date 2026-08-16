"""Attest restoration of the ignored canonical turn-evidence corpus."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO / "tests/data/turn_evidence_runtime.v1.jsonl"
POLICY = REPO / "src/baxy_mind/data/turn_evidence_abstention_policy.v1.json"
PUBLIC_HOLDOUT = REPO / "tests/data/turn_evidence_public_holdout.v1.jsonl"
MANIFEST = REPO / "tests/data/turn_evidence_public_manifest.v1.json"
OUTPUT = REPO / "artifacts/audit/turn_evidence_restoration_r234.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for line in handle if line.strip())


def is_git_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", str(path.relative_to(REPO))],
        cwd=REPO,
        check=False,
    )
    return result.returncode == 0


def build() -> dict[str, object]:
    if not RUNTIME.is_file():
        raise RuntimeError("canonical turn-evidence runtime corpus is absent")
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    runtime_hash = sha256(RUNTIME)
    public_hash = sha256(PUBLIC_HOLDOUT)
    if runtime_hash != policy["runtime_source_sha256"]:
        raise RuntimeError("restored runtime corpus does not match its policy")
    if line_count(RUNTIME) != 25_156:
        raise RuntimeError("restored runtime corpus row count changed")
    if not is_git_ignored(RUNTIME):
        raise RuntimeError("restored runtime corpus must remain ignored")
    if public_hash != "e1ee1746a3cb110799997367490def6199e09fa3bc9f900b2d2dd99dc9c174be":
        raise RuntimeError("public turn-evidence holdout identity changed")
    return {
        "schema": "baxy.turn-evidence-restoration.r234.v1",
        "authority": "canonical_input_restoration_not_a_model_or_product_measurement",
        "runtime_corpus": {
            "path": str(RUNTIME.relative_to(REPO)),
            "rows": 25_156,
            "sha256": runtime_hash,
            "git_ignored": True,
        },
        "public_holdout": {
            "path": str(PUBLIC_HOLDOUT.relative_to(REPO)),
            "rows": 9_172,
            "sha256": public_hash,
            "used_for_calibration": False,
        },
        "sources": {
            "manifest_sha256": sha256(MANIFEST),
            "policy_sha256": sha256(POLICY),
            "policy_runtime_source_sha256": policy["runtime_source_sha256"],
        },
        "constraints": {
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "next_requirement": (
            "Preregister an independently calibrated semantic abstention candidate; "
            "R228 and the public holdout remain unopened for that purpose."
        ),
        "identities": {"program_sha256": sha256(Path(__file__))},
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite attestation: {OUTPUT}")
    OUTPUT.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
