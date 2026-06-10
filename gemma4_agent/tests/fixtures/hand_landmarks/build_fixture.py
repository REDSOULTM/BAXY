"""Regenerate the kinivi hand-landmark gesture fixture from the upstream source.

Reproducibility recipe (never ship an artifact without its recipe).
Downloads kinivi/hand-gesture-recognition-mediapipe keypoint.csv (Apache-2.0) and
writes a balanced subset (N per class, deterministic = first N) used as the
offline validation fixture for the geometric gesture recognizer.

Run:
    python -m gemma4_agent.tests.fixtures.hand_landmarks.build_fixture
"""
from __future__ import annotations

import argparse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/kinivi/hand-gesture-recognition-mediapipe/"
    "main/model/keypoint_classifier/keypoint.csv"
)
SUBSET_PATH = Path(__file__).with_name("kinivi_keypoint_subset.csv")
DEFAULT_PER_CLASS = 250


def build(per_class: int = DEFAULT_PER_CLASS, url: str = SOURCE_URL, out: Path = SUBSET_PATH) -> Path:
    raw = urllib.request.urlopen(url, timeout=60).read().decode("utf-8")
    rows = [line for line in raw.splitlines() if line.strip()]
    by_class: dict[int, list[str]] = defaultdict(list)
    for line in rows:
        by_class[int(line.split(",", 1)[0])].append(line)
    selected: list[str] = []
    for label in sorted(by_class):
        selected.extend(by_class[label][:per_class])
    out.write_text("\n".join(selected) + "\n", encoding="utf-8", newline="")
    counts = Counter(int(line.split(",", 1)[0]) for line in selected)
    print(f"wrote {out} : {len(selected)} rows, per-class {dict(sorted(counts.items()))}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-class", type=int, default=DEFAULT_PER_CLASS)
    args = parser.parse_args()
    build(per_class=args.per_class)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
