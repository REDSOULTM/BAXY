"""Remove three exact, inactive roots created by this audit's early probes."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


NAMES = (
    "audit-catalog-line-measure",
    "audit-core-start-manual",
    "audit-schema-read",
)


def main() -> int:
    parent = (Path(os.environ["LOCALAPPDATA"]) / "BAXY").resolve(strict=True)
    removed: list[str] = []
    for name in NAMES:
        candidate = (parent / name).resolve(strict=True)
        if candidate.parent != parent or candidate.name != name:
            raise RuntimeError("audit cleanup target escaped its exact parent")
        shutil.rmtree(candidate)
        if candidate.exists():
            raise RuntimeError(f"audit cleanup target remained: {name}")
        removed.append(name)
    active_soaks = sorted(
        path.name
        for path in parent.iterdir()
        if path.is_dir()
        and path.name.startswith("audit-")
        and "soak-" in path.name
    )
    print(
        json.dumps(
            {
                "removed": removed,
                "active_soak_roots": active_soaks,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
