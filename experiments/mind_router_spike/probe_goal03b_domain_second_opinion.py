"""Goal 03B: price the ternary domain verdict before it reaches the product.

The curated domain gate is binary today: it either leaves the authority alone or
deletes it and answers ``unsupported`` -- "I cannot turn off the bluetooth" about
a capability BAXY has. Goal 03 measured the two one-sided guards separately and
published the trade, but never the composition that keeps execution under the
strictest of them while letting the disagreement ask instead of deny:

* both guards ground it  -> act, exactly as today;
* the curated gate refuses and the independent contract verifier accepts -> ask
  the person to confirm the exact invocation. Nothing is executed, so the
  invariant the gate exists for is untouched, and BAXY stops denying what he can
  do;
* both refuse -> ``unsupported``, which is now the honest word for it.

This replays no turn. It reads the raw proposals the sidecar already recorded in
a goal 03 telemetry file and asks the two guards about each one, so the trade can
be priced before a line of product code moves.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)
from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)
from experiments.mind_router_spike.probe_current_catalog_leaf_compatibility import (  # noqa: E402
    SEMANTIC_LEAF_IDENTITY_PROMPT,
)

SCHEMA = "baxy.goal03b-domain-second-opinion.v1"
RESULT_DIR = REPO / "artifacts" / "development"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03B ternary domain verdict")
    parser.add_argument("--source", required=True, help="goal03 telemetry jsonl label")
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--verifier",
        default="strict",
        choices=["strict", "semantic_leaf"],
        help="which inherited one-sided verifier gives the second opinion",
    )
    arguments = parser.parse_args()

    from baxy_mind import effect_intent, llm as llm_module
    from baxy_mind.llm import LlmRuntime

    source = RESULT_DIR / f"goal03_{arguments.source}.telemetry.jsonl"
    rows = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    contracts = {
        str(item["name"]): {
            "description": str(item["description"]),
            "arguments_schema": item["argumentsSchema"],
        }
        for item in capabilities
    }
    os.environ.update(
        sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
        )
    )
    process, port = _start_server(runtime, runtime.gguf)
    os.environ["BAXY_MIND_LLM_ENDPOINT"] = f"http://127.0.0.1:{port}"
    llm = LlmRuntime()
    prompt = (
        SEMANTIC_LEAF_IDENTITY_PROMPT
        if arguments.verifier == "semantic_leaf"
        else llm_module.OPERATION_COMPATIBILITY_PROMPT
    )
    seconds: list[float] = []
    report_rows: list[dict[str, Any]] = []
    try:
        for row in rows:
            text = str(row["text"])
            operations = [
                operation
                for operation in dict.fromkeys(row.get("raw_operations") or [])
                if operation in contracts
            ][:8]
            gate: dict[str, object] = {}
            verifier: dict[str, object] = {}
            llm.begin_request(45.0, attempt=1)
            for operation in operations:
                gate[operation] = effect_intent.operation_domain_is_grounded(
                    text,
                    operation,
                )
                started = time.perf_counter()
                verifier[operation] = llm._operation_is_fully_compatible(
                    text,
                    operation,
                    contracts[operation],
                    _system_prompt=prompt,
                )
                seconds.append(time.perf_counter() - started)
            report_rows.append(
                {
                    "case_id": row["case_id"],
                    "language": row["language"],
                    "in_catalog": bool(row["in_catalog"]),
                    "expected_operations": list(row.get("expected_operations") or []),
                    "raw_operations": operations,
                    "gate": gate,
                    "verifier": verifier,
                    "text": text,
                }
            )
    finally:
        _stop_server(process)

    # The product gate refuses the turn when any proposed operation is
    # explicitly ungrounded; ``None`` means no curated rule spoke and leaves the
    # authority alone. The second opinion only ever revives what the first
    # refused, and only when it accepts every refused operation.
    counters: collections.Counter[str] = collections.Counter()
    for row in report_rows:
        refused = [
            operation
            for operation, verdict in row["gate"].items()
            if verdict is False
        ]
        row["gate_refuses"] = bool(refused)
        row["verifier_revives"] = bool(refused) and all(
            row["verifier"].get(operation) is True for operation in refused
        )
        bucket = "in_catalog" if row["in_catalog"] else "out_of_catalog"
        if not row["raw_operations"]:
            counters[f"{bucket}.no_proposal"] += 1
        elif not refused:
            counters[f"{bucket}.gate_allows"] += 1
        elif row["verifier_revives"]:
            counters[f"{bucket}.would_confirm"] += 1
        else:
            counters[f"{bucket}.stays_unsupported"] += 1
        if row["in_catalog"] and row["verifier_revives"]:
            expected = set(row["expected_operations"])
            counters[
                "in_catalog.would_confirm_the_expected_operation"
                if expected & set(row["raw_operations"])
                else "in_catalog.would_confirm_another_operation"
            ] += 1

    report = {
        "schema": SCHEMA,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verifier": arguments.verifier,
        "source": {
            "telemetry": str(source.relative_to(REPO)),
            "sha256": _sha256(source),
            "rows": len(rows),
        },
        "verifier_seconds": {
            "calls": len(seconds),
            "p50": round(statistics.median(seconds), 4) if seconds else None,
            "p90": round(sorted(seconds)[min(len(seconds) - 1, int(len(seconds) * 0.9))], 4)
            if seconds
            else None,
            "max": round(max(seconds), 4) if seconds else None,
        },
        "counts": dict(sorted(counters.items())),
        "rows": report_rows,
    }
    destination = RESULT_DIR / f"goal03b_domain_second_opinion_{arguments.label}.json"
    write_json_atomic(destination, report)
    print(json.dumps({k: report[k] for k in ("counts", "verifier_seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
