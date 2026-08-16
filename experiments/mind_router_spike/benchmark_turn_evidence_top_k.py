"""Reproduce the exact top-k ranking latency campaign on a frozen E5 cache.

This benchmark never starts an encoder or an LLM.  It compares the historical
full stable sort with BAXY's exact partition implementation over the vectors
and metadata already registered in ``BAXYRuntime/turn-evidence``.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import random
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np


REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY / "src"))

from baxy_mind.turn_evidence import (  # noqa: E402
    DEFAULT_CANDIDATE_NEIGHBORS,
    TurnEvidenceRecord,
    _exact_top_k_indices,
    _is_candidate_training_record,
)


def _default_metadata() -> Path:
    local_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_data:
        raise RuntimeError("LOCALAPPDATA is unavailable; pass --metadata")
    cache = Path(local_data) / "BAXYRuntime" / "turn-evidence"
    candidates = sorted(
        cache.glob("*.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(f"no turn-evidence metadata found in {cache}")
    return candidates[0]


def _percentile(samples: list[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(samples), percentile))


def _measure(
    functions: dict[str, Callable[[], object]],
    *,
    rounds: int,
    warmups: int,
) -> dict[str, dict[str, float]]:
    for function in functions.values():
        for _ in range(warmups):
            function()
    samples = {name: [] for name in functions}
    names = list(functions)
    gc.disable()
    try:
        for round_number in range(rounds):
            random.Random(round_number).shuffle(names)
            for name in names:
                started_at = time.perf_counter_ns()
                functions[name]()
                samples[name].append(
                    (time.perf_counter_ns() - started_at) / 1_000_000
                )
    finally:
        gc.enable()
    return {
        name: {
            "p10_ms": _percentile(values, 10),
            "p50_ms": _percentile(values, 50),
            "p95_ms": _percentile(values, 95),
            "minimum_ms": min(values),
            "maximum_ms": max(values),
        }
        for name, values in samples.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--rounds", type=int, default=120)
    parser.add_argument("--warmups", type=int, default=5)
    args = parser.parse_args()
    if args.rounds < 1 or args.warmups < 0:
        parser.error("--rounds must be positive and --warmups cannot be negative")

    metadata_path = (args.metadata or _default_metadata()).resolve()
    vectors_path = metadata_path.with_suffix(".npy")
    metadata: dict[str, Any] = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )
    rows = metadata["records"]
    vectors = np.load(vectors_path)
    if vectors.ndim != 2 or vectors.shape[0] != len(rows):
        raise RuntimeError("metadata and vector cache have incompatible shapes")

    records = [
        TurnEvidenceRecord(
            text="",
            mode=str(row["mode"]),
            families=tuple(row["families"]),
            mission_id=str(row["mission_id"]),
            source_id=str(row["source_id"]),
            split=str(row["split"]),
            dataset=str(row.get("dataset", "")),
            license=str(row.get("license", "")),
        )
        for row in rows
    ]
    candidate_indices = np.asarray(
        [
            index
            for index, record in enumerate(records)
            if _is_candidate_training_record(record)
        ],
        dtype=np.intp,
    )
    sample_indices = np.linspace(
        0,
        len(records) - 1,
        min(3, len(records)),
        dtype=np.intp,
    )
    query = np.sum(vectors[sample_indices], axis=0, dtype=np.float32)
    query /= np.linalg.norm(query)
    scores = query @ vectors.T
    candidate_families = {"file", "system", "window"}
    candidate_limit = max(DEFAULT_CANDIDATE_NEIGHBORS * 8, 64)
    full_limit = 128

    def historical_candidate() -> list[int]:
        return sorted(
            (int(index) for index in candidate_indices),
            key=lambda index: (
                float(scores[index]),
                records[index].source_id,
            ),
            reverse=True,
        )[:candidate_limit]

    def exact_candidate() -> list[int]:
        return _exact_top_k_indices(
            scores,
            candidate_indices,
            limit=candidate_limit,
            suffix_key=lambda index: (records[index].source_id,),
        )

    def historical_full() -> list[int]:
        return sorted(
            range(len(records)),
            key=lambda index: (
                float(scores[index]),
                bool(candidate_families & set(records[index].families)),
                records[index].source_id,
            ),
            reverse=True,
        )[:full_limit]

    def exact_full() -> list[int]:
        return _exact_top_k_indices(
            scores,
            None,
            limit=full_limit,
            suffix_key=lambda index: (
                not candidate_families.isdisjoint(records[index].families),
                records[index].source_id,
            ),
        )

    if historical_candidate() != exact_candidate():
        raise RuntimeError("candidate top-k differs from the historical ranking")
    if historical_full() != exact_full():
        raise RuntimeError("full top-k differs from the historical ranking")

    measurements = _measure(
        {
            "dot": lambda: query @ vectors.T,
            "candidate_historical_sort": historical_candidate,
            "candidate_exact_partition": exact_candidate,
            "full_historical_sort": historical_full,
            "full_exact_partition": exact_full,
        },
        rounds=args.rounds,
        warmups=args.warmups,
    )
    candidate_before = measurements["candidate_historical_sort"]["p50_ms"]
    candidate_after = measurements["candidate_exact_partition"]["p50_ms"]
    full_before = measurements["full_historical_sort"]["p50_ms"]
    full_after = measurements["full_exact_partition"]["p50_ms"]
    print(
        json.dumps(
            {
                "schema": "baxy-turn-evidence-top-k-benchmark-v1",
                "metadata": str(metadata_path),
                "shape": list(vectors.shape),
                "candidate_rows": int(candidate_indices.size),
                "candidate_limit": candidate_limit,
                "full_limit": full_limit,
                "rounds": args.rounds,
                "warmups": args.warmups,
                "exact_order": True,
                "measurements": measurements,
                "ranking_p50_saved_ms": (
                    candidate_before
                    - candidate_after
                    + full_before
                    - full_after
                ),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
