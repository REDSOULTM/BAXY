"""Evaluate Qwen3-Reranker-0.6B as a leaf selector on the sealed synthetic holdout.

This is a different family from the generative function-calling models already
rejected (FunctionGemma, xLAM-2-3B, Qwen3.5-9B native). The cross-encoder
reads (request, operation description) jointly. Instruction and the 0.5 P(yes)
threshold are copied from the model card, not fitted on this holdout.
No provider is reachable from this harness.
"""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from baxy_mind.llm import _native_selection_description  # noqa: E402
from experiments.mind_router_spike.probe_goal03_qwen_binary_scope_holdout import (  # noqa: E402
    MAXIMUM_SYNTHETIC_OOS_ACTIONS,
    MINIMUM_REAL_EXACT,
    MINIMUM_SYNTHETIC_EXACT,
    REAL_VALIDATION,
    TRAIN,
    VALIDATION,
    clean_real_rows,
    percentile,
    read_jsonl,
    sha256,
    summarize,
)
from scripts.measure_mind_budget import (  # noqa: E402
    current_core_catalog_snapshot,
    discover_core,
)


SCHEMA = "baxy.goal03-qwen3-reranker-holdout.v1"
MODEL_DIR = Path(r"D:\BAXYRuntime\candidates\Qwen--Qwen3-Reranker-0.6B")
SYNTHETIC_OUTPUT = REPO / "artifacts/development/goal03_qwen3_reranker_synthetic_v61.json"
REAL_OUTPUT = REPO / "artifacts/development/goal03_qwen3_reranker_real_v62.json"
FRESH_OUTPUT = REPO / "artifacts/development/goal03_qwen3_reranker_fresh_frozen_v63.json"
FRESH_UNION = REPO / "artifacts/development/goal03_qwen3_8b_iq2_think128_union28_v10.json"
FRESH_UNION_SHA256 = "fe1360ece07d618863e35836b8cae2f52bad8e7a85495439c9dbb69a308add91"
INSTRUCTION = (
    "Given a user's request to a local computer assistant, retrieve the catalog "
    "operation whose complete effect matches the request. Partial, related, or "
    "sibling operations are not relevant."
)
THRESHOLD = 0.5
BATCH_SIZE = 8
MAX_LENGTH = 2048
EXPECTED_SHA256 = {
    VALIDATION: "a81a50fc80af209d9c6827ac81e300d2ebcc9f493c473b2708e58aa5b52ddab2",
    TRAIN: "69e8bcde6760258a6e8d750caa3c648fc85695c0cccd7f6ad6926a92935b8bad",
    REAL_VALIDATION: "c42d27e6ccdc03d0ee6dcce20ca26a52b5c1e49e869b8bdfa91db2b88e622300",
}


def frozen_fresh_rows() -> list[dict[str, Any]]:
    report = json.loads(FRESH_UNION.read_text(encoding="utf-8"))
    rows = []
    for raw in report["rows"]:
        in_catalog = bool(raw["in_catalog"])
        expected = list(raw.get("expected_operations") or [])
        rows.append(
            {
                "case_id": raw["case_id"],
                "text": raw["text"],
                "language": raw.get("language") or "unknown",
                "operation": expected[0] if in_catalog and expected else "__no_action__",
                "acceptable_operations": expected,
                "candidate_operations": list(raw["candidate_operations"]),
                "in_catalog": in_catalog,
            }
        )
    if len(rows) != 160:
        raise RuntimeError("unexpected frozen-fresh population")
    return rows


def population(phase: str) -> tuple[list[dict[str, Any]], Path, dict[str, Any]]:
    if phase == "synthetic":
        rows = read_jsonl(VALIDATION)
        positives = sum(row["operation"] != "__no_action__" for row in rows)
        if len(rows) != 784 or positives != 477:
            raise RuntimeError("unexpected synthetic validation population")
        return rows, SYNTHETIC_OUTPUT, {"positive": 477, "no_action": 307}
    if phase == "frozen-fresh":
        return frozen_fresh_rows(), FRESH_OUTPUT, {"positive": 124, "no_action": 36}
    if not SYNTHETIC_OUTPUT.is_file():
        raise RuntimeError("real phase requires the sealed synthetic report")
    prior = json.loads(SYNTHETIC_OUTPUT.read_text(encoding="utf-8"))
    if prior.get("decision") != "accepted_for_real_holdout":
        raise RuntimeError("synthetic gate did not authorize real evaluation")
    rows, excluded = clean_real_rows()
    return rows, REAL_OUTPUT, {"positive": 60, "excluded_overlap": excluded}


def candidate_contracts() -> dict[str, dict[str, Any]]:
    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    return {
        str(item["name"]): {
            "name": str(item["name"]),
            "description": str(item["description"]),
            "arguments_schema": item["argumentsSchema"],
        }
        for item in capabilities
    }


def operation_document(name: str, description: str) -> str:
    return f"{name}. {_native_selection_description(name, description)}"


def decide(
    names: list[str],
    scores: list[float],
    *,
    threshold: float = THRESHOLD,
) -> tuple[tuple[str, ...], bool, dict[str, Any]]:
    if len(names) != len(scores) or not names:
        raise ValueError("reranker scores do not match candidates")
    ranked = sorted(zip(scores, names), key=lambda item: item[0], reverse=True)
    top_score, top_name = ranked[0]
    second = ranked[1][0] if len(ranked) > 1 else None
    detail = {
        "top_name": top_name,
        "top_score": top_score,
        "second_score": second,
        "margin": None if second is None else top_score - second,
    }
    if top_score >= threshold:
        return (top_name,), False, detail
    return (), True, detail


def load_reranker(model_dir: Path) -> Any:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("Qwen3-Reranker probe requires CUDA")
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_dir),
        padding_side="left",
        local_files_only=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        str(model_dir),
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    ).to("cuda").eval()
    prefix = (
        "<|im_start|>system\nJudge whether the Document meets the requirements "
        "based on the Query and the Instruct provided. Note that the answer can "
        'only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
    )
    suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    return {
        "model": model,
        "tokenizer": tokenizer,
        "true_id": tokenizer.convert_tokens_to_ids("yes"),
        "false_id": tokenizer.convert_tokens_to_ids("no"),
        "prefix_tokens": tokenizer.encode(prefix, add_special_tokens=False),
        "suffix_tokens": tokenizer.encode(suffix, add_special_tokens=False),
        "torch": torch,
    }


def score_pairs(bundle: dict[str, Any], pairs: list[tuple[str, str]]) -> list[float]:
    torch = bundle["torch"]
    tokenizer = bundle["tokenizer"]
    model = bundle["model"]
    formatted = [
        (
            "<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}"
        ).format(instruction=INSTRUCTION, query=query, doc=document)
        for query, document in pairs
    ]
    scores: list[float] = []
    max_body = MAX_LENGTH - len(bundle["prefix_tokens"]) - len(bundle["suffix_tokens"])
    with torch.inference_mode():
        for start in range(0, len(formatted), BATCH_SIZE):
            batch = formatted[start : start + BATCH_SIZE]
            encoded = tokenizer(
                batch,
                padding=False,
                truncation="longest_first",
                return_attention_mask=False,
                max_length=max_body,
            )
            input_ids = [
                bundle["prefix_tokens"] + ids + bundle["suffix_tokens"]
                for ids in encoded["input_ids"]
            ]
            padded = tokenizer.pad(
                {"input_ids": input_ids},
                padding=True,
                return_tensors="pt",
            )
            padded = {key: value.to(model.device) for key, value in padded.items()}
            logits = model(**padded).logits[:, -1, :]
            yes = logits[:, bundle["true_id"]]
            no = logits[:, bundle["false_id"]]
            stacked = torch.stack([no, yes], dim=1)
            scores.extend(torch.nn.functional.log_softmax(stacked, dim=1)[:, 1].exp().tolist())
    return scores


def run(phase: str) -> Path:
    required = dict(EXPECTED_SHA256)
    if phase == "frozen-fresh":
        required = {FRESH_UNION: FRESH_UNION_SHA256}
    for path, expected in required.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"source identity mismatch: {path}")
    if not MODEL_DIR.is_dir():
        raise RuntimeError(f"missing reranker weights: {MODEL_DIR}")
    rows, output, expected_population = population(phase)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {output}")
    by_name = candidate_contracts()
    for row in rows:
        candidates = list(row.get("candidate_operations") or [])
        if not candidates or any(name not in by_name for name in candidates):
            raise RuntimeError(f"invalid candidates in {row['case_id']}")

    bundle = load_reranker(MODEL_DIR)
    results: list[dict[str, Any]] = []
    started_all = time.perf_counter()
    try:
        for index, row in enumerate(rows, 1):
            names = list(row["candidate_operations"])
            documents = [
                operation_document(name, by_name[name]["description"]) for name in names
            ]
            started = time.perf_counter()
            scores = score_pairs(bundle, [(str(row["text"]), document) for document in documents])
            selected, no_match, detail = decide(names, scores)
            seconds = time.perf_counter() - started
            expected = str(row["operation"])
            acceptable = list(row.get("acceptable_operations") or [expected])
            if expected == "__no_action__":
                acceptable = []
            results.append(
                {
                    "case_id": str(row["case_id"]),
                    "text": str(row["text"]),
                    "language": str(row.get("language") or "unknown"),
                    "expected_operation": expected,
                    "acceptable_operations": acceptable,
                    "candidate_operations": names,
                    "scores": scores,
                    "selected_no_match": bool(no_match),
                    "selected_operations": list(selected),
                    "selected_expected": any(name in selected for name in acceptable),
                    "unthresholded_top": detail["top_name"],
                    "unthresholded_expected": detail["top_name"] in acceptable,
                    "top_score": detail["top_score"],
                    "second_score": detail["second_score"],
                    "schema_consistent": True,
                    "native_error": None,
                    "seconds": seconds,
                }
            )
            if index % 25 == 0 or index == len(rows):
                print(f"{phase}: {index}/{len(rows)}", flush=True)
    finally:
        del bundle
        gc.collect()
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass

    summary = summarize(results, "synthetic" if phase == "frozen-fresh" else phase)
    if phase == "frozen-fresh":
        exact = int(summary["positive"]["selected_expected"])
        oos = int(summary["no_action"]["selected_action_calls"])
        summary["decision"] = (
            "accepted_for_product_probe" if exact >= 112 and oos <= 5 else "rejected_before_product"
        )
        summary["accepted"] = summary["decision"] == "accepted_for_product_probe"
    unthresholded = sum(
        bool(row["unthresholded_expected"])
        for row in results
        if row["expected_operation"] != "__no_action__"
    )
    durations = [float(row["seconds"]) for row in results]
    report = {
        "schema": SCHEMA,
        "phase": phase,
        "decision": summary.pop("decision"),
        "gates": {
            "synthetic_selected_expected_minimum": MINIMUM_SYNTHETIC_EXACT,
            "synthetic_oos_action_calls_maximum": MAXIMUM_SYNTHETIC_OOS_ACTIONS,
            "real_selected_expected_minimum": MINIMUM_REAL_EXACT,
            "threshold": THRESHOLD,
            "instruction": INSTRUCTION,
        },
        "population": expected_population,
        "sources": {
            str(path): {"sha256": digest} for path, digest in EXPECTED_SHA256.items()
        },
        "policy": {
            "model": "Qwen/Qwen3-Reranker-0.6B",
            "threshold": THRESHOLD,
            "instruction_source": "preregistered_english_task_instruction",
            "batch_size": BATCH_SIZE,
        },
        "metrics": {
            **summary,
            "unthresholded_positive_top1": unthresholded,
            "elapsed_seconds": time.perf_counter() - started_all,
        },
        "latency_seconds": {
            "p50": statistics.median(durations),
            "p90": percentile(durations, 0.9),
            "maximum": max(durations),
        },
        "authority": {
            "providers_enabled": False,
            "effects_executed": 0,
            "runtime_manifest_changed": False,
            "fresh_corpus_rows_used": 0,
        },
        "rows": results,
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("synthetic", "real", "frozen-fresh"),
        required=True,
    )
    args = parser.parse_args()
    output = run(args.phase)
    report = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({"decision": report["decision"], **report["metrics"]}, indent=2))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
