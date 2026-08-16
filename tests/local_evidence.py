"""Prerequisites the repository leaves outside itself on purpose.

A clean clone does not have these, so a test that needs one is reporting a
missing prerequisite, not a regression. Both exclusions are deliberate and
predate goal 02, which found them by running the gate on a fresh clone.

`tests/data/turn_evidence_runtime.v1.jsonl`
    A runtime corpus that combines `historical_messages.jsonl`.
    `tests/data/TURN_EVIDENCE_DATA_NOTICE.md` classifies it as private local
    project data that must not be published as a dataset, and `.gitignore`
    excludes it by name — not by pattern. Its public counterparts
    (`turn_evidence_public_holdout.v1.jsonl` and the manifest) are versioned and
    stay checked on every machine.

The repositories of the earlier BAXY attempts
    `scripts/build_historical_corpus.py` reads them as siblings of this one
    (`Programacion/FunctionGemma`, `Programacion/Probando Gemma 4`, ...). They
    are separate checkouts, not content of this tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RUNTIME_TURN_EVIDENCE = Path("tests/data/turn_evidence_runtime.v1.jsonl")


def require_runtime_turn_evidence(root: Path) -> Path:
    """Return the private runtime corpus, or skip naming it as environment."""
    path = root / RUNTIME_TURN_EVIDENCE
    if not path.is_file():
        pytest.skip(
            "environment: "
            f"{RUNTIME_TURN_EVIDENCE.as_posix()} is private local data that the "
            "tree excludes on purpose (TURN_EVIDENCE_DATA_NOTICE.md)"
        )
    return path


def require_inherited_repository(path: Path) -> Path:
    """Return an earlier attempt's checkout, or skip naming it as environment."""
    if not path.is_dir():
        pytest.skip(
            f"environment: the inherited repository {path.name} is not beside "
            "this one, so the historical corpus cannot be rebuilt here"
        )
    return path
