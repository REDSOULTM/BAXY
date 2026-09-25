"""Owner, closing plan 2026-09-24 (item 3): every reading of the request lives in ``semantic/``.

The inventory (``scripts/inventory_reading_outside_semantic.py``) finds every regex applied to the person's words
outside ``src/baxy_mind/semantic/`` and in the App. A new one fails here until it is moved to its semantic family or
reviewed with the reason it is not a reading (the reply's wording, a literal grounding, speech before a request).
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import inventory_reading_outside_semantic as inventory  # noqa: E402


@lru_cache(maxsize=1)
def _classified() -> tuple[list[inventory.Site], dict[tuple[str, str], tuple[str, str]]]:
    inventory.configure(ROOT)
    sites = inventory.python_sites() + inventory.cs_sites()
    return sites, inventory.classify(sites)


def test_no_pattern_reads_the_person_outside_semantic_without_a_review() -> None:
    sites, classes = _classified()
    unreviewed = sorted("::".join(key) for key, (kind, _) in classes.items() if kind == "UNREVIEWED")
    assert unreviewed == [], "move these readings to semantic/ or review why they are not readings: " + ", ".join(
        unreviewed
    )


def test_the_mind_reads_the_request_only_in_semantic() -> None:
    sites, classes = _classified()
    readers = sorted(
        "::".join(key) for key, (kind, _) in classes.items() if kind == "READING" and key[0].endswith(".py")
    )
    assert readers == []


def test_every_review_names_a_function_that_still_exists() -> None:
    sites, _ = _classified()
    present = {(site.file, site.function) for site in sites}
    stale = sorted("::".join(key) for key in inventory.REVIEWED if key not in present)
    assert stale == [], "a reviewed function no longer applies a pattern: remove its review"
