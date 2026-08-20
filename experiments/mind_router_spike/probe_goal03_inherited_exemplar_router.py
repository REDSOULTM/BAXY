"""Measure the inherited exemplar router as an isolated Goal 03 guard."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
INHERITED = REPO.parent / "Probando Gemma 4"
DATA = INHERITED / "gemma4_agent/data"
CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
DEFAULT_SELECTION = (
    REPO
    / "artifacts/development/goal03_qwen3_8b_iq2_think128_official_sampling_s0_v16.json"
)
DEFAULT_OUTPUT = REPO / "artifacts/development/goal03_inherited_exemplar_router_v25.json"
EXPECTED_CORPUS_SHA256 = (
    "761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d"
)
EXPECTED_ENCODER_SHA256 = (
    "987091a86e004caafcbcc9d61148dc5d5851b9cac3d2a5700db810e578e4f026"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _latency(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {
        "rows": len(ordered),
        "p50": statistics.median(ordered),
        "p90": ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))],
        "max": ordered[-1],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    encoder = DATA / "router_encoder_ft/model_int8.onnx"
    store = DATA / "router_exemplars.npz"
    source = INHERITED / "gemma4_agent/routing/exemplar_router.py"
    identities = {
        "corpus": _sha256(CORPUS),
        "encoder_onnx": _sha256(encoder),
        "exemplar_store": _sha256(store),
        "implementation": _sha256(source),
        "selection": _sha256(args.selection),
    }
    if identities["corpus"] != EXPECTED_CORPUS_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")
    if identities["encoder_onnx"] != EXPECTED_ENCODER_SHA256:
        raise RuntimeError("coordinated inherited ONNX encoder identity changed")

    os.environ["GEMMA4_ENCODER_ONNX"] = "1"
    os.environ["GEMMA4_LEAN_TOOLS"] = "1"
    os.environ["GEMMA4_SEMANTIC_COLD_LOAD"] = "1"
    sys.path.insert(0, str(INHERITED))
    from gemma4_agent.routing.exemplar_router import match

    corpus = _jsonl(CORPUS)
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    selected_by_id = {row["case_id"]: row for row in selection["rows"]}
    if set(selected_by_id) != {row["case_id"] for row in corpus}:
        raise RuntimeError("selection and sealed corpus populations differ")

    match("warm up inherited exemplar router")
    rows: list[dict[str, Any]] = []
    durations: list[float] = []
    for row in corpus:
        started = time.perf_counter()
        result = match(str(row["text"]))
        durations.append(time.perf_counter() - started)
        abstain = bool(result is not None and result.abstain)
        prior = list(selected_by_id[row["case_id"]].get("selected_operations") or [])
        after = [] if abstain else prior
        expected = set(row.get("expected_operations") or [])
        rows.append(
            {
                **row,
                "matched": result is not None,
                "source": result.source if result is not None else None,
                "score": result.score if result is not None else None,
                "inherited_families": list(result.tools) if result is not None else [],
                "exemplar_abstains": abstain,
                "prior_selected_operations": prior,
                "selected_operations_after_guard": after,
                "selected_expected_after_guard": bool(expected & set(after)),
            }
        )

    inside = [row for row in rows if row["in_catalog"]]
    outside = [row for row in rows if not row["in_catalog"]]
    result = {
        "schema": "baxy.goal03-inherited-exemplar-router.v1",
        "source": {
            "checkout": str(INHERITED),
            "settings": {
                "top_k": 5,
                "min_score": 0.92,
                "conflict_score": 0.975,
                "abstain_margin": 0.05,
                "abstain_near_band": 0.15,
            },
            "sha256": identities,
        },
        "population": {
            "rows": len(rows),
            "in_catalog": len(inside),
            "out_of_catalog": len(outside),
        },
        "intrinsic": {
            "matched_in_catalog": sum(row["matched"] for row in inside),
            "matched_out_of_catalog": sum(row["matched"] for row in outside),
            "abstained_in_catalog": [
                row["case_id"] for row in inside if row["exemplar_abstains"]
            ],
            "abstained_out_of_catalog": [
                row["case_id"] for row in outside if row["exemplar_abstains"]
            ],
            "family_outputs_in_catalog": sum(
                bool(row["inherited_families"]) for row in inside
            ),
            "family_outputs_out_of_catalog": sum(
                bool(row["inherited_families"]) for row in outside
            ),
        },
        "selection_before_guard": {
            "in_catalog": selection["in_catalog"],
            "out_of_catalog": selection["out_of_catalog"],
        },
        "selection_after_guard": {
            "in_catalog": {
                "selected_expected": sum(
                    row["selected_expected_after_guard"] for row in inside
                ),
                "rows": len(inside),
            },
            "out_of_catalog": {
                "honest_abstentions": sum(
                    not row["selected_operations_after_guard"] for row in outside
                ),
                "rows": len(outside),
            },
        },
        "steady_state_seconds": _latency(durations),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: result[key] for key in (
        "population", "intrinsic", "selection_before_guard",
        "selection_after_guard", "steady_state_seconds"
    )}, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
