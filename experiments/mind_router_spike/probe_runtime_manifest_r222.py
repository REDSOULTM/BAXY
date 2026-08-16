"""Attest only the registered runtime preflight; never start an inference process."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import DEFAULT_RUNTIME_MANIFEST, resolve_runtime  # noqa: E402


OUTPUT = REPO / "artifacts/audit/runtime_manifest_preflight_r222.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, object]:
    manifest = json.loads(DEFAULT_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    try:
        resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    except (FileNotFoundError, ValueError) as error:
        outcome = {"resolved": False, "error": str(error)}
    else:
        outcome = {"resolved": True, "error": ""}
    return {
        "schema": "baxy.runtime-manifest-preflight.r222.v1",
        "authority": "read_only_runtime_identity_preflight_not_model_start",
        "manifest": {
            "schema": manifest.get("schema"),
            "keys": sorted(manifest),
            "sha256": sha256(DEFAULT_RUNTIME_MANIFEST),
        },
        "outcome": outcome,
        "constraints": {
            "model_started": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {"program_sha256": sha256(Path(__file__))},
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
