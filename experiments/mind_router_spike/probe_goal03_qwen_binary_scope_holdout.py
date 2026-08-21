"""Evaluate one preregistered When2Call-style Qwen policy before Goal 03 fresh data.

The policy adds a binary scope decision before leaf selection, but keeps both in
one constrained Qwen inference.  It never executes providers.  Synthetic
validation must pass before the inherited-real phase is allowed to run.
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
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from experiments.mind_router_spike.probe_goal03_minimal_operation_policy import (  # noqa: E402
    NO_OPERATION,
    _ExperimentalLlmRuntime,
    _payload,
)
from experiments.mind_router_spike.train_goal03_real_scope_head import (  # noqa: E402
    exclude_overlaps,
    normalize,
    read_jsonl,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
)


SCHEMA = "baxy.goal03-qwen-binary-scope-holdout.v1"
VALIDATION = Path(
    r"D:\BAXYRuntime\experiments\functiongemma-current-union-v1\validation.jsonl"
)
TRAIN = Path(r"D:\BAXYRuntime\experiments\functiongemma-current-union-v1\train.jsonl")
REAL_VALIDATION = Path(
    r"D:\BAXYRuntime\experiments\functiongemma-real-language-v1\current_union_validation.jsonl"
)
MODEL = Path(r"D:\BAXYRuntime\candidates\qwen3-8b-iq2\Qwen3-8B-UD-IQ2_M.gguf")
SERVER = Path(
    r"C:\Users\usuario\Desktop\ETC\Programacion\BAXY"
    r"\legacy\models\artifacts\llama-b9980\llama-server.exe"
)
SYNTHETIC_OUTPUT = REPO / "artifacts/development/goal03_qwen_binary_scope_synthetic_v48.json"
REAL_OUTPUT = REPO / "artifacts/development/goal03_qwen_binary_scope_real_v49.json"

EXPECTED_SHA256 = {
    VALIDATION: "a81a50fc80af209d9c6827ac81e300d2ebcc9f493c473b2708e58aa5b52ddab2",
    TRAIN: "69e8bcde6760258a6e8d750caa3c648fc85695c0cccd7f6ad6926a92935b8bad",
    REAL_VALIDATION: "c42d27e6ccdc03d0ee6dcce20ca26a52b5c1e49e869b8bdfa91db2b88e622300",
    MODEL: "1dfd67f311a5a82f57ecc1763b54884066ccf1727c45cbe1a619f85ac96368b2",
    SERVER: "38a9d28ea414442590486459a7d1f5e32655db83148b7a114b79cd1ad242946e",
}
MINIMUM_SYNTHETIC_EXACT = 431
MAXIMUM_SYNTHETIC_OOS_ACTIONS = 42
MINIMUM_REAL_EXACT = 55

BINARY_SCOPE_PREFIX = (
    "First decide scope_decision. Classify action only when at least one "
    "authenticated candidate directly fulfills a concrete computer action, "
    "live machine or personal-data read, or external-source lookup explicitly "
    "requested in the current message. Otherwise classify none. When the "
    "decision is none, effect_operations must contain only no_operation. When "
    "the decision is action, effect_operations must contain one or more real "
    "candidate operations and must not contain no_operation. "
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def binary_payload(
    text: str,
    candidate_names: list[str],
    descriptions: dict[str, str],
) -> dict[str, Any]:
    payload = _payload(
        text,
        candidate_names,
        descriptions,
        selection_shape="array",
        enable_thinking=True,
        reasoning_budget=128,
        sampling_profile="qwen-thinking",
        seed=0,
    )
    payload["messages"][0]["content"] = (
        BINARY_SCOPE_PREFIX + str(payload["messages"][0]["content"])
    )
    schema = payload["response_format"]["json_schema"]["schema"]
    schema["properties"] = {
        "scope_decision": {"type": "string", "enum": ["action", "none"]},
        **schema["properties"],
    }
    schema["required"] = ["scope_decision", *schema["required"]]
    return payload


def fail_closed_selection(
    response: dict[str, Any], candidates: Iterable[str]
) -> tuple[str | None, list[str], bool]:
    candidate_set = set(candidates)
    decision = response.get("scope_decision")
    raw_operations = response.get("effect_operations")
    if decision not in {"action", "none"} or not isinstance(raw_operations, list):
        return None, [], False
    if not raw_operations or not all(isinstance(item, str) for item in raw_operations):
        return str(decision), [], False
    wire = [str(item) for item in raw_operations]
    if len(wire) != len(set(wire)):
        return str(decision), [], False
    if any(item != NO_OPERATION and item not in candidate_set for item in wire):
        return str(decision), [], False
    if decision == "none":
        consistent = wire == [NO_OPERATION]
        return "none", [], consistent
    consistent = NO_OPERATION not in wire and bool(wire)
    return "action", wire if consistent else [], consistent


def clean_real_rows() -> tuple[list[dict[str, Any]], list[int]]:
    train = read_jsonl(TRAIN)
    calibration = read_jsonl(VALIDATION)
    real = read_jsonl(REAL_VALIDATION)
    cleaned, excluded = exclude_overlaps(
        real,
        [
            {normalize(str(row["text"])) for row in train},
            {normalize(str(row["text"])) for row in calibration},
        ],
    )
    if len(cleaned) != 60 or excluded != [8, 3]:
        raise RuntimeError("unexpected inherited-real holdout decontamination")
    return cleaned, excluded


def population(phase: str) -> tuple[list[dict[str, Any]], Path, dict[str, Any]]:
    if phase == "synthetic":
        rows = read_jsonl(VALIDATION)
        positives = sum(row["operation"] != "__no_action__" for row in rows)
        if len(rows) != 784 or positives != 477:
            raise RuntimeError("unexpected synthetic validation population")
        return rows, SYNTHETIC_OUTPUT, {"positive": 477, "no_action": 307}
    if not SYNTHETIC_OUTPUT.is_file():
        raise RuntimeError("real phase requires the sealed synthetic report")
    prior = json.loads(SYNTHETIC_OUTPUT.read_text(encoding="utf-8"))
    if prior.get("decision") != "accepted_for_real_holdout":
        raise RuntimeError("synthetic gate did not authorize real evaluation")
    rows, excluded = clean_real_rows()
    return rows, REAL_OUTPUT, {"positive": 60, "excluded_overlap": excluded}


def summarize(rows: list[dict[str, Any]], phase: str) -> dict[str, Any]:
    positives = [row for row in rows if row["expected_operation"] != "__no_action__"]
    negatives = [row for row in rows if row["expected_operation"] == "__no_action__"]
    exact = sum(bool(row["selected_expected"]) for row in positives)
    oos_actions = sum(bool(row["selected_operations"]) for row in negatives)
    inconsistent = sum(not bool(row["schema_consistent"]) for row in rows)
    if phase == "synthetic":
        accepted = (
            exact >= MINIMUM_SYNTHETIC_EXACT
            and oos_actions <= MAXIMUM_SYNTHETIC_OOS_ACTIONS
        )
        decision = "accepted_for_real_holdout" if accepted else "rejected_before_real"
    else:
        accepted = exact >= MINIMUM_REAL_EXACT
        decision = "accepted_for_fresh" if accepted else "rejected_before_fresh"
    return {
        "decision": decision,
        "accepted": accepted,
        "positive": {"rows": len(positives), "selected_expected": exact},
        "no_action": {
            "rows": len(negatives),
            "selected_action_calls": oos_actions,
            "safe_no_action": len(negatives) - oos_actions,
        },
        "schema_inconsistent_rows": inconsistent,
    }


def run(phase: str) -> Path:
    for path, expected in EXPECTED_SHA256.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"source identity mismatch: {path}")
    rows, output, expected_population = population(phase)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {output}")

    capabilities, _, _ = current_core_catalog_snapshot(discover_core(None))
    descriptions = {
        str(item["name"]): str(item["description"]) for item in capabilities
    }
    for row in rows:
        candidates = list(row.get("candidate_operations") or [])
        if not candidates or any(name not in descriptions for name in candidates):
            raise RuntimeError(f"invalid candidates in {row['case_id']}")

    registered = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    environment = sidecar_environment(
        registered,
        gpu_layers=registered.gpu_layers,
        llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
    )
    environment["BAXY_MIND_LLAMA_SERVER"] = str(SERVER)
    environment["BAXY_MIND_LLM_GGUF"] = str(MODEL)
    os.environ.update(environment)

    runtime = _ExperimentalLlmRuntime(reasoning_budget=128)
    results: list[dict[str, Any]] = []
    try:
        warm_names = ["app.open", "system.time", "web.search"]
        runtime._post_schema_object(  # noqa: SLF001 - experiment owns boundary
            binary_payload("open calculator", warm_names, descriptions),
            "binary-scope warmup",
        )
        for index, row in enumerate(rows, 1):
            candidates = list(row["candidate_operations"])
            started = time.perf_counter()
            response = runtime._post_schema_object(  # noqa: SLF001
                binary_payload(str(row["text"]), candidates, descriptions),
                "binary-scope holdout",
            )
            seconds = time.perf_counter() - started
            decision, selected, consistent = fail_closed_selection(response, candidates)
            expected = str(row["operation"])
            results.append(
                {
                    "case_id": str(row["case_id"]),
                    "text": str(row["text"]),
                    "language": str(row.get("language") or "unknown"),
                    "expected_operation": expected,
                    "candidate_operations": candidates,
                    "scope_decision": decision,
                    "selected_operations": selected,
                    "selected_expected": expected in selected,
                    "schema_consistent": consistent,
                    "seconds": seconds,
                }
            )
            if index % 25 == 0 or index == len(rows):
                print(f"{phase}: {index}/{len(rows)}", flush=True)
    finally:
        runtime.close()

    summary = summarize(results, phase)
    durations = [float(row["seconds"]) for row in results]
    report = {
        "schema": SCHEMA,
        "phase": phase,
        "decision": summary.pop("decision"),
        "gates": {
            "synthetic_selected_expected_minimum": MINIMUM_SYNTHETIC_EXACT,
            "synthetic_oos_action_calls_maximum": MAXIMUM_SYNTHETIC_OOS_ACTIONS,
            "real_selected_expected_minimum": MINIMUM_REAL_EXACT,
        },
        "population": expected_population,
        "sources": {
            str(path): {"sha256": digest} for path, digest in EXPECTED_SHA256.items()
        },
        "policy": {
            "single_inference": True,
            "reasoning_budget": 128,
            "sampling_profile": "qwen-thinking",
            "seed": 0,
            "prompt_sha256": hashlib.sha256(
                BINARY_SCOPE_PREFIX.encode("utf-8")
            ).hexdigest(),
            "invalid_response_policy": "fail_closed_no_action",
        },
        "metrics": summary,
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
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("synthetic", "real"), required=True)
    args = parser.parse_args()
    output = run(args.phase)
    report = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({"decision": report["decision"], **report["metrics"]}, indent=2))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
