"""Install the frozen semantic-fusion lexicon into an external target."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--wheel-directory", type=Path, required=True)
    arguments = parser.parse_args()
    target = arguments.target.resolve()
    wheels = arguments.wheel_directory.resolve(strict=True)
    requirements = Path(__file__).with_name(
        "wordfreq_semantic_fusion_requirements.txt"
    ).resolve(strict=True)
    if target.exists():
        raise RuntimeError("semantic_fusion_wordfreq_target_exists")
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--no-index",
        "--require-hashes",
        "--find-links",
        str(wheels),
        "--target",
        str(target),
        "--requirement",
        str(requirements),
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        return completed.returncode
    print(
        json.dumps(
            {
                "target": str(target),
                "requirements": str(requirements),
                "wheelDirectory": str(wheels),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
