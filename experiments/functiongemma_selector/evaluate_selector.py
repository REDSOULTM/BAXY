"""Evaluate base FunctionGemma or a LoRA adapter as a leaf selector only."""

from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from selector_common import (
    NO_ACTION_OPERATION,
    REPO,
    catalog_by_name,
    family_operations,
    parse_operations,
    read_jsonl,
    selection_tools,
    sha256,
)

DEFAULT_MODEL = Path(r"D:\BAXYRuntime\assets\models\functiongemma-270m-it-hf")
DEFAULT_ORACLE = (
    REPO
    / "experiments"
    / "mind_router_spike"
    / "data"
    / "exact_operation_development.v1.jsonl"
)
DEFAULT_OUTPUT = REPO / "artifacts" / "research" / "functiongemma_audio_base.json"
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _ranked_families(text: str, available: set[str], count: int) -> list[str]:
    import numpy as np
    from scipy.sparse import hstack

    from baxy_mind.family_classifier import FamilyClassifier

    classifier = FamilyClassifier()
    characters, words, classes, coefficients, intercept = classifier._resources
    features = hstack(
        (
            characters.transform([text]),
            words.transform([text]) * 1.5,
        ),
        format="csr",
    )
    scores = np.asarray(features @ coefficients.T + intercept).reshape(-1)
    indexes = [index for index, family in enumerate(classes) if family in available]
    return [
        classes[index]
        for index in sorted(
            indexes, key=lambda index: float(scores[index]), reverse=True
        )[:count]
    ]


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[round((len(ordered) - 1) * probability)], 6)


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this experiment")
    os.environ["HF_HUB_OFFLINE"] = "1"
    catalog = catalog_by_name()
    families = (
        sorted({name.split(".", 1)[0] for name in catalog})
        if args.family == "all"
        else [args.family]
    )
    candidate_by_family = {
        family: family_operations(catalog, family) for family in families
    }
    cases = [
        row
        for row in read_jsonl(args.oracle)
        if len(row.get("expected_operations") or []) == 1
        and (
            args.family == "all"
            or str(row["expected_operations"][0]).split(".", 1)[0] == args.family
        )
    ]
    if not cases:
        raise ValueError(f"oracle has no single-operation {args.family} cases")

    available_families = {name.split(".", 1)[0] for name in catalog}
    case_families: dict[str, list[str]] = {}
    for case in cases:
        expected_family = str(case["expected_operations"][0]).split(".", 1)[0]
        case_families[str(case["case_id"])] = (
            [expected_family]
            if args.candidate_source == "oracle-family"
            else _ranked_families(
                str(case["text"]), available_families, args.family_top_k
            )
        )
    tools_by_signature: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for predicted in case_families.values():
        signatures = (
            [(family,) for family in predicted]
            if args.candidate_source == "classifier-per-family"
            else [tuple(predicted)]
        )
        for signature in signatures:
            operations = [
                operation
                for family in signature
                for operation in candidate_by_family[family]
            ]
            tools_by_signature.setdefault(
                signature,
                selection_tools(catalog, [*operations, NO_ACTION_OPERATION]),
            )

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    started_load = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.bfloat16
    )
    if args.adapter is not None:
        model = PeftModel.from_pretrained(model, args.adapter, local_files_only=True)
    model = model.to("cuda").eval()
    load_seconds = time.perf_counter() - started_load

    rows: list[dict[str, Any]] = []
    # Warmup is deliberately outside latency statistics.
    warm_families = case_families[str(cases[0]["case_id"])]
    warm_signature = (
        (warm_families[0],)
        if args.candidate_source == "classifier-per-family"
        else tuple(warm_families)
    )
    warm = tokenizer.apply_chat_template(
        [{"role": "user", "content": "hola"}],
        tools=tools_by_signature[warm_signature],
        add_generation_prompt=True,
        tokenize=False,
    )
    warm_inputs = tokenizer(warm, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        model.generate(**warm_inputs, max_new_tokens=8, do_sample=False)

    for repeat in range(args.repeats):
        for case in cases:
            case_family = str(case["expected_operations"][0]).split(".", 1)[0]
            predicted_families = case_families[str(case["case_id"])]
            signatures = (
                [(family,) for family in predicted_families]
                if args.candidate_source == "classifier-per-family"
                else [tuple(predicted_families)]
            )
            torch.cuda.synchronize()
            started = time.perf_counter()
            attempts: list[dict[str, Any]] = []
            for signature in signatures:
                prompt = tokenizer.apply_chat_template(
                    [{"role": "user", "content": str(case["text"])}],
                    tools=tools_by_signature[signature],
                    add_generation_prompt=True,
                    tokenize=False,
                )
                inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
                with torch.inference_mode():
                    output = model.generate(
                        **inputs,
                        max_new_tokens=args.max_new_tokens,
                        do_sample=False,
                        use_cache=True,
                        return_dict_in_generate=True,
                        output_scores=True,
                    )
                generated = tokenizer.decode(
                    output.sequences[0, inputs.input_ids.shape[1] :],
                    skip_special_tokens=False,
                )
                observed = parse_operations(generated)
                allowed_operations = {
                    operation
                    for family in signature
                    for operation in candidate_by_family[family]
                } | {NO_ACTION_OPERATION}
                valid = bool(observed) and all(
                    operation in allowed_operations for operation in observed
                )
                transition = model.compute_transition_scores(
                    output.sequences,
                    output.scores,
                    normalize_logits=True,
                )
                confidence = (
                    float(transition[0].mean().detach().cpu())
                    if transition.numel()
                    else float("-inf")
                )
                attempts.append(
                    {
                        "candidate_families": list(signature),
                        "operations": observed,
                        "generated": generated,
                        "mean_log_probability": round(confidence, 8),
                        "valid": valid,
                    }
                )
            torch.cuda.synchronize()
            seconds = time.perf_counter() - started
            best = max(
                attempts,
                key=lambda attempt: (
                    bool(attempt["valid"]),
                    float(attempt["mean_log_probability"]),
                ),
            )
            generated = str(best["generated"])
            observed = list(best["operations"])
            expected = list(case["expected_operations"])
            rows.append(
                {
                    "case_id": case["case_id"],
                    "language": case.get("language"),
                    "family": case_family,
                    "candidate_families": predicted_families,
                    "expected_family_retrieved": case_family in predicted_families,
                    "repeat": repeat,
                    "text": case["text"],
                    "expected_operations": expected,
                    "observed_operations": observed,
                    "exact": observed == expected,
                    "seconds": round(seconds, 6),
                    "generated": generated,
                    "candidate_attempts": attempts,
                }
            )

    latencies = [row["seconds"] for row in rows]
    exact = sum(bool(row["exact"]) for row in rows)
    report = {
        "schema": "baxy.functiongemma-selector-evaluation.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "oracle-family ceiling; expected family supplies the candidate set"
            if args.candidate_source == "oracle-family"
            else "classifier retrieval; expected family does not supply candidates"
        ),
        "candidate_source": args.candidate_source,
        "family_top_k": args.family_top_k if args.candidate_source != "oracle-family" else None,
        "family": args.family,
        "candidate_operations": candidate_by_family,
        "cases_per_repeat": len(cases),
        "repeats": args.repeats,
        "samples": len(rows),
        "exact": exact,
        "exact_accuracy": round(exact / len(rows), 6),
        "by_language": {
            language: {
                "samples": len(group),
                "exact": sum(bool(row["exact"]) for row in group),
                "accuracy": round(
                    sum(bool(row["exact"]) for row in group) / len(group), 6
                ),
            }
            for language, group in sorted(
                (
                    (language, [row for row in rows if row["language"] == language])
                    for language in {row["language"] for row in rows}
                ),
                key=lambda item: str(item[0]),
            )
        },
        "by_family": {
            family: {
                "samples": len(group),
                "exact": sum(bool(row["exact"]) for row in group),
                "accuracy": round(
                    sum(bool(row["exact"]) for row in group) / len(group), 6
                ),
            }
            for family, group in sorted(
                (
                    (family, [row for row in rows if row["family"] == family])
                    for family in {row["family"] for row in rows}
                )
            )
        },
        "confusions": dict(
            collections.Counter(
                f"{','.join(row['expected_operations'])}->{','.join(row['observed_operations']) or 'NONE'}"
                for row in rows
                if not row["exact"]
            )
        ),
        "latency_seconds": {
            "mean": round(statistics.fmean(latencies), 6),
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "maximum": round(max(latencies), 6),
        },
        "load_seconds": round(load_seconds, 6),
        "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1),
        "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 1),
        "base_model": {
            "path": str(args.model),
            "sha256": sha256(args.model / "model.safetensors"),
        },
        "adapter": str(args.adapter) if args.adapter is not None else None,
        "adapter_report": (
            json.loads((args.adapter / "training_report.json").read_text(encoding="utf-8"))
            if args.adapter is not None
            and (args.adapter / "training_report.json").is_file()
            else None
        ),
        "oracle": str(args.oracle),
        "oracle_sha256": sha256(args.oracle),
        "effects_executed": 0,
        "runtime_manifest_changed": False,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--oracle", type=Path, default=DEFAULT_ORACLE)
    parser.add_argument("--family", default="audio")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument(
        "--candidate-source",
        choices=("oracle-family", "classifier-topk", "classifier-per-family"),
        default="oracle-family",
    )
    parser.add_argument("--family-top-k", type=int, default=5)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.model = args.model.resolve(strict=True)
    args.adapter = args.adapter.resolve(strict=True) if args.adapter else None
    args.oracle = args.oracle.resolve(strict=True)
    args.output = args.output.resolve()
    evaluate(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
