"""Record the authenticated current Core operation catalogue without model use."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.measure_mind_budget import current_core_catalog_snapshot, discover_core  # noqa: E402


OUTPUT = REPO / "artifacts/development/current_core_catalog_snapshot_r219.json"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build() -> dict[str, Any]:
    capabilities, applications, games = current_core_catalog_snapshot(
        discover_core(None)
    )
    names = [str(row["name"]) for row in capabilities]
    if len(names) != len(set(names)) or not names:
        raise RuntimeError("current Core catalogue has invalid operation identities")
    return {
        "schema": "baxy.current-core-catalog-snapshot.r219.v1",
        "authority": "read_only_authenticated_Core_catalogue_not_model_or_dispatch",
        "constraints": {
            "model_started": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "voice_stt_wake_exercised": False,
        },
        "catalogue": {
            "operations": len(capabilities),
            "operation_names_sha256": hashlib.sha256(
                _canonical_bytes(names)
            ).hexdigest(),
            "capabilities_sha256": hashlib.sha256(
                _canonical_bytes(capabilities)
            ).hexdigest(),
            "applications": len(applications or ()),
            "games": len(games or ()),
            "capabilities": capabilities,
        },
        "identities": {
            "program_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite current Core snapshot: {OUTPUT}")
    OUTPUT.write_bytes(
        (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
