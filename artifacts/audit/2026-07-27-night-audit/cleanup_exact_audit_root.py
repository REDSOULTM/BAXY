"""Remove one exact inactive audit root after validating its parent and prefix."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    if not args.name.startswith("audit-") or Path(args.name).name != args.name:
        raise SystemExit("only one leaf audit-* name is accepted")
    parent = (Path(os.environ["LOCALAPPDATA"]) / "BAXY").resolve(strict=True)
    candidate = (parent / args.name).resolve(strict=True)
    if candidate.parent != parent or candidate.name != args.name:
        raise RuntimeError("audit cleanup target escaped its exact parent")
    shutil.rmtree(candidate)
    print(
        json.dumps(
            {"removed": args.name, "existsAfter": candidate.exists()},
            ensure_ascii=False,
        )
    )
    return 0 if not candidate.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
