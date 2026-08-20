"""Measure the coordinated inherited KVA guard on the sealed Goal 03 cut.

The guard and ONNX encoder are loaded read-only from the previous BAXY
checkout.  Their threshold was calibrated together before this corpus existed;
this probe never fits or changes either artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
DEFAULT_OUTPUT = REPO / "artifacts/development/goal03_inherited_kva_gate_v22.json"
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
    p90_index = min(len(ordered) - 1, int(0.9 * len(ordered)))
    return {
        "rows": len(ordered),
        "p50": statistics.median(ordered),
        "p90": ordered[p90_index],
        "max": ordered[-1],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    encoder = DATA / "router_encoder_ft/model_int8.onnx"
    gate_path = DATA / "fg/kva_gate.json"
    caller = INHERITED / "gemma4_agent/routing/fg_router.py"
    identities = {
        "corpus": _sha256(CORPUS),
        "encoder_onnx": _sha256(encoder),
        "kva_gate": _sha256(gate_path),
        "caller": _sha256(caller),
        "selection": _sha256(args.selection),
    }
    if identities["corpus"] != EXPECTED_CORPUS_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")
    if identities["encoder_onnx"] != EXPECTED_ENCODER_SHA256:
        raise RuntimeError("coordinated inherited ONNX encoder identity changed")

    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    coef = [float(value) for value in gate["coef"]]
    intercept = float(gate["intercept"])
    threshold = float(gate["threshold_p_knowledge"])
    if len(coef) != 384:
        raise RuntimeError("unexpected KVA coefficient dimension")

    os.environ["GEMMA4_ENCODER_ONNX"] = "1"
    os.environ["GEMMA4_LEAN_TOOLS"] = "1"
    os.environ["GEMMA4_SEMANTIC_COLD_LOAD"] = "1"
    sys.path.insert(0, str(INHERITED))
    from gemma4_agent.routing import semantic_router

    corpus = _jsonl(CORPUS)
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    selected_by_id = {row["case_id"]: row for row in selection["rows"]}
    if set(selected_by_id) != {row["case_id"] for row in corpus}:
        raise RuntimeError("selection and sealed corpus populations differ")

    semantic_router.embed("warm up coordinated KVA encoder")
    rows: list[dict[str, Any]] = []
    embed_seconds: list[float] = []
    head_seconds: list[float] = []
    for source in corpus:
        started = time.perf_counter()
        embedding = semantic_router.embed(source["text"])
        embed_seconds.append(time.perf_counter() - started)
        if embedding is None or len(embedding) != len(coef):
            raise RuntimeError(f"invalid embedding for {source['case_id']}")

        started = time.perf_counter()
        logit = sum(w * float(x) for w, x in zip(coef, embedding)) + intercept
        p_knowledge = 1.0 / (1.0 + math.exp(logit))
        gated = p_knowledge >= threshold
        head_seconds.append(time.perf_counter() - started)

        prior = list(selected_by_id[source["case_id"]].get("selected_operations") or [])
        after = [] if gated else prior
        rows.append(
            {
                **source,
                "p_knowledge": p_knowledge,
                "gated": gated,
                "prior_selected_operations": prior,
                "selected_operations_after_gate": after,
                "selected_expected_after_gate": bool(
                    set(after) & set(source.get("expected_operations") or [])
                ),
            }
        )

    inside = [row for row in rows if row["in_catalog"]]
    outside = [row for row in rows if not row["in_catalog"]]
    result = {
        "schema": "baxy.goal03-inherited-kva-gate.v1",
        "source": {
            "checkout": str(INHERITED),
            "gate": str(gate_path),
            "encoder": str(encoder),
            "selection": str(args.selection.relative_to(REPO)),
            "threshold_p_knowledge": threshold,
            "sha256": identities,
        },
        "population": {
            "rows": len(rows),
            "in_catalog": len(inside),
            "out_of_catalog": len(outside),
        },
        "intrinsic": {
            "kept_in_catalog": sum(not row["gated"] for row in inside),
            "gated_in_catalog": [row["case_id"] for row in inside if row["gated"]],
            "gated_out_of_catalog": [row["case_id"] for row in outside if row["gated"]],
        },
        "selection_before_gate": {
            "in_catalog": selection["in_catalog"],
            "out_of_catalog": selection["out_of_catalog"],
        },
        "selection_after_gate": {
            "in_catalog": {
                "selected_expected": sum(row["selected_expected_after_gate"] for row in inside),
                "rows": len(inside),
            },
            "out_of_catalog": {
                "honest_abstentions": sum(
                    not row["selected_operations_after_gate"] for row in outside
                ),
                "rows": len(outside),
                "prevented_prior_actions": [
                    row["case_id"]
                    for row in outside
                    if row["gated"] and row["prior_selected_operations"]
                ],
            },
        },
        "steady_state_seconds": {
            "encoder": _latency(embed_seconds),
            "kva_head": _latency(head_seconds),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "population",
                    "intrinsic",
                    "selection_before_gate",
                    "selection_after_gate",
                    "steady_state_seconds",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
