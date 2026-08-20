"""Measure the inherited FunctionGemma router stack on the sealed Goal 03 cut.

This probe treats the previous BAXY checkout as a read-only dependency.  It does
not retrain or tune against the sealed corpus.  The encoder, abstain head and
planner are loaded from their coordinated 2026-06-26 deployment in
``Probando Gemma 4``; their identities are recorded in the result.
"""

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
PROGRAMACION = REPO.parent
INHERITED = PROGRAMACION / "Probando Gemma 4"
PACKAGE = INHERITED / "gemma4_agent"
DATA = PACKAGE / "data"
CORPUS = REPO / "artifacts/development/goal03_fresh_paraphrase_corpus.v1.jsonl"
DEFAULT_SELECTION = (
    REPO
    / "artifacts/development/goal03_qwen3_8b_iq2_think128_official_sampling_s0_v16.json"
)
DEFAULT_OUTPUT = (
    REPO / "artifacts/development/goal03_inherited_router_stack_v18.json"
)
EXPECTED_CORPUS_SHA256 = (
    "761c1bc3b3facbf14a3aaafa09f24c0e5e0baaf8cebdd0edc7c2e648cb87413d"
)
EXPECTED_ENCODER_SHA256 = (
    "987091a86e004caafcbcc9d61148dc5d5851b9cac3d2a5700db810e578e4f026"
)
NON_DOMAIN_TOOLS = frozenset({"session", "safety", "state", "verify"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _latency(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    if not ordered:
        return {"rows": 0, "p50": 0.0, "p90": 0.0, "max": 0.0}
    p90_index = min(len(ordered) - 1, int(0.9 * len(ordered)))
    return {
        "rows": len(ordered),
        "p50": statistics.median(ordered),
        "p90": ordered[p90_index],
        "max": ordered[-1],
    }


def _score_overlay(
    rows: list[dict[str, Any]],
    selection_by_id: dict[str, dict[str, Any]],
    gate_key: str,
) -> dict[str, Any]:
    in_rows = [row for row in rows if row["in_catalog"]]
    out_rows = [row for row in rows if not row["in_catalog"]]

    selected_expected = 0
    honest_abstentions = 0
    gated_positive_rows: list[str] = []
    gated_negative_actions: list[str] = []
    for row in rows:
        source = selection_by_id[row["case_id"]]
        selected = list(source.get("selected_operations") or [])
        if row[gate_key]:
            if selected and row["in_catalog"]:
                gated_positive_rows.append(row["case_id"])
            if selected and not row["in_catalog"]:
                gated_negative_actions.append(row["case_id"])
            selected = []
        if row["in_catalog"]:
            selected_expected += int(bool(set(selected) & set(row["expected_operations"])))
        else:
            honest_abstentions += int(not selected)

    return {
        "gate": gate_key,
        "in_catalog": {
            "selected_expected": selected_expected,
            "rows": len(in_rows),
            "gated_rows_with_prior_action": gated_positive_rows,
        },
        "out_of_catalog": {
            "honest_abstentions": honest_abstentions,
            "rows": len(out_rows),
            "prevented_prior_actions": gated_negative_actions,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    encoder = DATA / "router_encoder_ft/model_int8.onnx"
    identities = {
        "corpus": _sha256(CORPUS),
        "encoder_onnx": _sha256(encoder),
        "abstain_head": _sha256(DATA / "abstain_head.json"),
        "tool_head": _sha256(DATA / "tool_head.json"),
        "tool2vec_centroids": _sha256(DATA / "tool2vec_centroids.npz"),
        "router_exemplars": _sha256(DATA / "router_exemplars.npz"),
        "selection": _sha256(args.selection),
    }
    if identities["corpus"] != EXPECTED_CORPUS_SHA256:
        raise RuntimeError("sealed Goal 03 corpus identity changed")
    if identities["encoder_onnx"] != EXPECTED_ENCODER_SHA256:
        raise RuntimeError("inherited coordinated ONNX encoder identity changed")

    # These are the inherited serving settings.  Set them before importing the
    # previous package because its modules cache configuration at import time.
    os.environ["GEMMA4_ENCODER_ONNX"] = "1"
    os.environ["GEMMA4_LEAN_TOOLS"] = "1"
    os.environ["GEMMA4_SEMANTIC_COLD_LOAD"] = "1"
    sys.path.insert(0, str(INHERITED))

    from gemma4_agent.routing import semantic_router
    from gemma4_agent.routing.deictic_detector import needs_deictic_context
    from gemma4_agent.routing.intent_router import classify_intent
    from gemma4_agent.routing.planner import MissionPlan, select_tool_names
    from gemma4_agent.safety_pkg.abstain_head import build_features, load_model
    from gemma4_agent.tools_pkg.tool_head import load as load_tool_head

    abstain_model = load_model()
    tool_head = load_tool_head()
    if abstain_model is None or tool_head is None:
        raise RuntimeError("the coordinated inherited heads did not load")

    corpus_rows = _load_jsonl(CORPUS)
    selection = json.loads(args.selection.read_text(encoding="utf-8"))
    selection_by_id = {row["case_id"]: row for row in selection["rows"]}
    if set(selection_by_id) != {row["case_id"] for row in corpus_rows}:
        raise RuntimeError("selection and sealed corpus populations differ")

    # Warm every inherited stage once; timings below represent steady-state
    # guard overhead, not model loading.  The end-to-end goal measures cold
    # lifecycle separately.
    warm_text = "warm up the inherited router"
    warm_scores = semantic_router.suggest_tools_scored(warm_text, k=12)
    warm_embedding = semantic_router.embed(warm_text)
    classify_intent(warm_text)
    build_features(
        warm_text, intent=None, scored=warm_scores, keyword_fired=False
    )
    if warm_embedding is not None:
        tool_head.fire(warm_embedding)
    select_tool_names(warm_text, MissionPlan(goal=warm_text, steps=[]))
    needs_deictic_context("open it")

    measured: list[dict[str, Any]] = []
    stage_seconds: dict[str, list[float]] = {
        "semantic_scores": [],
        "served_abstain_head": [],
        "calibrated_intent_and_head": [],
        "tool_head": [],
        "planner": [],
        "deictic_detector": [],
    }
    for source in corpus_rows:
        text = source["text"]

        started = time.perf_counter()
        scored = semantic_router.suggest_tools_scored(text, k=12)
        stage_seconds["semantic_scores"].append(time.perf_counter() - started)

        # Exact planner call-site: intent=None and keyword_fired=False.
        started = time.perf_counter()
        served_features = build_features(
            text, intent=None, scored=scored, keyword_fired=False
        )
        served_p = abstain_model.p_no_tool(served_features)
        served_abstains = abstain_model.should_abstain(served_features)
        stage_seconds["served_abstain_head"].append(time.perf_counter() - started)

        # The inherited evaluation harness also reports the trained intent
        # features.  Keep it diagnostic: it is not substituted into the planner.
        started = time.perf_counter()
        intent = classify_intent(text)
        calibrated_features = build_features(
            text, intent=intent, scored=scored, keyword_fired=False
        )
        calibrated_p = abstain_model.p_no_tool(calibrated_features)
        calibrated_abstains = abstain_model.should_abstain(calibrated_features)
        stage_seconds["calibrated_intent_and_head"].append(
            time.perf_counter() - started
        )

        started = time.perf_counter()
        embedding = semantic_router.embed(text)
        fired = tool_head.fire(embedding) if embedding is not None else []
        stage_seconds["tool_head"].append(time.perf_counter() - started)

        started = time.perf_counter()
        tools = select_tool_names(text, MissionPlan(goal=text, steps=[]))
        stage_seconds["planner"].append(time.perf_counter() - started)
        planner_abstains = not bool(set(tools) - NON_DOMAIN_TOOLS)

        started = time.perf_counter()
        deictic = needs_deictic_context(text)
        stage_seconds["deictic_detector"].append(time.perf_counter() - started)

        measured.append(
            {
                **source,
                "semantic_top_5": [[name, score] for name, score in scored[:5]],
                "served_p_no_tool": served_p,
                "served_head_abstains": served_abstains,
                "calibrated_p_no_tool": calibrated_p,
                "calibrated_head_abstains": calibrated_abstains,
                "tool_head_fired": [[name, margin] for name, margin in fired[:5]],
                "planner_tools": tools,
                "planner_abstains": planner_abstains,
                "deictic": deictic,
            }
        )

    in_rows = [row for row in measured if row["in_catalog"]]
    out_rows = [row for row in measured if not row["in_catalog"]]

    result = {
        "schema": "baxy.goal03-inherited-router-stack.v1",
        "source": {
            "checkout": str(INHERITED),
            "encoder": str(encoder),
            "selection": str(args.selection.relative_to(REPO)),
            "serving_environment": {
                "GEMMA4_ENCODER_ONNX": "1",
                "GEMMA4_LEAN_TOOLS": "1",
                "GEMMA4_SEMANTIC_COLD_LOAD": "1",
            },
            "sha256": identities,
        },
        "population": {
            "rows": len(measured),
            "in_catalog": len(in_rows),
            "out_of_catalog": len(out_rows),
        },
        "intrinsic": {
            "served_head": {
                "kept_in_catalog": sum(not row["served_head_abstains"] for row in in_rows),
                "abstained_out_of_catalog": sum(
                    row["served_head_abstains"] for row in out_rows
                ),
            },
            "calibrated_head_diagnostic": {
                "kept_in_catalog": sum(
                    not row["calibrated_head_abstains"] for row in in_rows
                ),
                "abstained_out_of_catalog": sum(
                    row["calibrated_head_abstains"] for row in out_rows
                ),
            },
            "exact_planner": {
                "kept_in_catalog": sum(not row["planner_abstains"] for row in in_rows),
                "abstained_out_of_catalog": sum(row["planner_abstains"] for row in out_rows),
            },
            "deictic": {
                "in_catalog": [row["case_id"] for row in in_rows if row["deictic"]],
                "out_of_catalog": [row["case_id"] for row in out_rows if row["deictic"]],
            },
        },
        "selection_before_gate": {
            "in_catalog": selection["in_catalog"],
            "out_of_catalog": selection["out_of_catalog"],
        },
        "selection_overlays": [
            _score_overlay(measured, selection_by_id, "served_head_abstains"),
            _score_overlay(measured, selection_by_id, "calibrated_head_abstains"),
            _score_overlay(measured, selection_by_id, "planner_abstains"),
        ],
        "steady_state_stage_seconds": {
            name: _latency(values) for name, values in stage_seconds.items()
        },
        "rows": measured,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: result[key] for key in (
        "population", "intrinsic", "selection_before_gate", "selection_overlays",
        "steady_state_stage_seconds",
    )}, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
