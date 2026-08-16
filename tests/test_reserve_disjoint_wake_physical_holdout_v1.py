from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reserve_disjoint_wake_physical_holdout_v1.py"
SPEC = importlib.util.spec_from_file_location("reserve_disjoint_wake_holdout", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_select_disjoint_is_deterministic_and_excludes_opened_hashes() -> None:
    records = [(Path(f"clip_{index:06d}.wav"), f"{index:064x}") for index in range(20)]
    excluded = {f"{index:064x}" for index in range(8)}

    first = MODULE.select_disjoint(records, excluded_hashes=excluded, limit=10, seed=7)
    second = MODULE.select_disjoint(records, excluded_hashes=excluded, limit=10, seed=7)

    assert first == second
    assert len(first) == 10
    assert not ({digest for _, digest in first} & excluded)


def test_merge_opened_hashes_unions_multiple_progress_files(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "progress.v1.jsonl").write_text(
        '{"recordId":"positive/0","sourceSha256":"' + "1" * 64 + '"}\n'
        '{"recordId":"negative/0","sourceSha256":"' + "2" * 64 + '"}\n',
        encoding="utf-8",
    )
    (second / "progress.v1.jsonl").write_text(
        '{"recordId":"positive/0","sourceSha256":"' + "3" * 64 + '"}\n'
        '{"recordId":"negative/0","sourceSha256":"' + "4" * 64 + '"}\n',
        encoding="utf-8",
    )

    merged = MODULE._merge_opened_hashes((first, second))

    assert merged["positive"] == {"1" * 64, "3" * 64}
    assert merged["negative"] == {"2" * 64, "4" * 64}


@pytest.mark.parametrize("limit", [0, 13])
def test_select_disjoint_rejects_invalid_or_insufficient_population(limit: int) -> None:
    records = [(Path(f"clip_{index:06d}.wav"), f"{index:064x}") for index in range(12)]

    with pytest.raises(ValueError, match="disjoint_wake_holdout_population_insufficient"):
        MODULE.select_disjoint(records, excluded_hashes=set(), limit=limit, seed=1)
