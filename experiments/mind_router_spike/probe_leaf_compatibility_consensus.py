"""Measure independent leaf compatibility for predicted-family proposals.

Each operation recorded by the native required-arm probe is checked by the
existing product ``_operation_is_fully_compatible`` contract against the full
trusted request and authenticated capability description/schema.  A proposal
is accepted only when every proposed leaf returns true.  No operation is
executed and no installation state is changed.
"""

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

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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

SOURCE = REPO / "artifacts" / "fixes" / "native_predicted_family_qwen3_20260801.json"
OUTPUT = REPO / "artifacts" / "fixes" / "leaf_compatibility_consensus_20260801.json"


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return round(ordered[index], 4)


def _load(path: Path) -> tuple[list[dict[str, Any]], Path]:
    report = json.loads(path.read_text(encoding="utf-8"))
    models = report.get("models")
    if not isinstance(models, list) or len(models) != 1:
        raise ValueError("source must contain one measured model")
    rows = [
        row
        for row in models[0].get("samples") or []
        if isinstance(row, dict)
        and row.get("arm") == "native_predicted_family_required"
    ]
    if len(rows) != 147:
        raise ValueError("source does not contain the 147-case required arm")
    model = Path(str((models[0].get("model") or {}).get("path") or "")).resolve()
    if not model.is_file():
        raise FileNotFoundError(model)
    return rows, model


def run(source: Path, output: Path) -> dict[str, Any]:
    from baxy_mind.llm import LlmRuntime

    source_rows, model_path = _load(source)
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
    process, port = _start_server(runtime, model_path)
    os.environ["BAXY_MIND_LLM_ENDPOINT"] = f"http://127.0.0.1:{port}"
    llm = LlmRuntime()
    rows: list[dict[str, Any]] = []
    try:
        for index, source_row in enumerate(source_rows, start=1):
            operations = list(dict.fromkeys(source_row.get("operations") or []))
            checks: dict[str, bool] = {}
            started = time.perf_counter()
            error = ""
            llm.begin_request(30.0, attempt=1)
            try:
                for operation in operations:
                    checks[operation] = llm._operation_is_fully_compatible(
                        str(source_row["text"]),
                        operation,
                        contracts[operation],
                    )
            except Exception as exc:  # noqa: BLE001 - measurement boundary
                error = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                llm.end_request()
            elapsed = time.perf_counter() - started
            accepted = bool(operations) and not error and all(checks.values())
            accepted_families = (
                {operation.split(".", 1)[0] for operation in operations}
                if accepted
                else set()
            )
            outcome = (
                "error"
                if error
                else "right_family"
                if str(source_row["family"]) in accepted_families
                else "no_operation"
                if not accepted
                else "wrong_family"
            )
            rows.append(
                {
                    "case_id": source_row["case_id"],
                    "text": source_row["text"],
                    "expected_family": source_row["family"],
                    "predicted_family": source_row["predicted_family"],
                    "raw_outcome": source_row["outcome"],
                    "operations": operations,
                    "compatibility": checks,
                    "accepted": accepted,
                    "outcome": outcome,
                    "wrong_raw_proposal_accepted": (
                        source_row["outcome"] == "wrong_family" and accepted
                    ),
                    "seconds": round(elapsed, 6),
                    "error": error,
                }
            )
            print(
                f"[{index:03d}/{len(source_rows):03d}] {source_row['case_id']} "
                f"raw={source_row['outcome']} compatible={accepted} -> {outcome}",
                flush=True,
            )
    finally:
        llm.close()
        _stop_server(process)

    outcomes = collections.Counter(row["outcome"] for row in rows)
    latencies = [row["seconds"] for row in rows]
    report = {
        "schema": "baxy.leaf-compatibility-consensus.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source.resolve()),
        "effects_executed": 0,
        "installation_touched": False,
        "runtime_manifest_changed": False,
        "cases": len(rows),
        "outcomes": dict(outcomes),
        "right_family_share": round(
            outcomes.get("right_family", 0) / len(rows), 4
        ),
        "no_operation_share": round(
            outcomes.get("no_operation", 0) / len(rows), 4
        ),
        "wrong_raw_proposals_accepted": sum(
            row["wrong_raw_proposal_accepted"] for row in rows
        ),
        "seconds_p50": round(statistics.median(latencies), 4),
        "seconds_p95": _percentile(latencies, 0.95),
        "rows": rows,
        "method": (
            "Every recorded leaf must independently pass the existing product "
            "compatibility schema against the trusted text and authenticated "
            "capability contract. Empty, partial or failed verification abstains."
        ),
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(args.source, args.output)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "rows"},
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
