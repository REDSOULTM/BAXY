"""Price an independent-verification floor for operations no rule reaches.

R122 proposed moving the safety decision to the point where the turn kind is
chosen. ``measure_turn_kind_safety_boundary`` priced all four concrete forms of
that move against every consumed population and the green physical missions, and
all four were rejected: the two that stop both leaks break 11 and 20 of the 20
legitimate actions, and the two that break only 6 stop just one leak. There is
no discriminator at the turn-kind point.

What remains is the hole the second leak actually fell through. ``reminder.create``
carries no curated domain rule, and the independent contract-aware compatibility
verifier -- which already exists and already guards the compound path -- is
skipped on exactly two structural conditions:

* ``_primary_action_compatibility_target`` returns ``None`` when the operation
  declares no required arguments, so identity is never verified for it;
* a single-operation ``plan`` reached through cardinality disagreement carries
  no compound contract, so ``apply_compound_effect_conservation_veto`` returns
  unchanged.

A floor on the uncovered path would ask that verifier where today nothing is
asked. Whether that is affordable is an empirical question with a known trap:
on the R2 catalogue review the strict verifier rejected 38 of 48 correct
proposals (recall 0.208) while rejecting 82 of 84 wrong ones, and the semantic
leaf verifier inverted that (recall 0.958, wrong-rejection 0.25). Neither is
free, so the cost is measured **before** anything is written, on precisely the
rows a floor would touch.

Development diagnostic over already-consumed populations. It executes no
operation, drives no turn, and promotes nothing: a claim needs a fresh sealed V6.
"""

from __future__ import annotations

import argparse
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
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

from experiments.mind_router_spike.probe_native_tool_contract_ceiling import (  # noqa: E402
    _start_server,
    _stop_server,
)
from experiments.mind_router_spike.probe_current_catalog_leaf_compatibility import (  # noqa: E402
    _semantic_leaf_is_compatible,
)
from experiments.mind_router_spike import (  # noqa: E402
    measure_turn_kind_safety_boundary as boundary,
)


DEFAULT_SOURCE = REPO / "artifacts/development/turn_kind_safety_boundary_20260812.json"
DEFAULT_OUTPUT = REPO / "artifacts/development/uncovered_operation_floor_20260812.json"


def _rows_a_floor_would_touch(source: Path) -> list[dict[str, Any]]:
    """Select every consumed row where the proposed floor would fire.

    The floor is one-sided and last-resort: it applies only where the request
    was not proved by the deterministic recogniser **and** no curated domain
    rule reaches the proposed operation, which is exactly the state that let
    ``reminder.create`` through. Rows outside that state are carried anyway, so
    the report shows what the verifier would have said had the floor been wider.
    """

    report = json.loads(source.read_text(encoding="utf-8"))
    if report.get("schema") != "baxy.turn-kind-safety-boundary.v1":
        raise ValueError("source is not the turn-kind boundary diagnostic")
    rows = []
    for row in report["rows"]:
        if not row["effect_operations"]:
            continue
        row["floor_fires"] = bool(
            not row["resolved"] and row["domain"]["any_uncovered"]
        )
        row["is_leak"] = row["role"] == "request"
        rows.append(row)
    return rows


def run(source: Path, output: Path) -> dict[str, Any]:
    from baxy_mind.llm import LlmRuntime

    rows = _rows_a_floor_would_touch(source)
    capabilities, _, _ = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    contracts = {
        str(item["name"]): {
            "description": str(item["description"]),
            "arguments_schema": item["argumentsSchema"],
        }
        for item in capabilities
    }
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
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
    measured: list[dict[str, Any]] = []
    try:
        for index, row in enumerate(rows, start=1):
            strict: dict[str, bool] = {}
            semantic: dict[str, bool] = {}
            error = ""
            started = time.perf_counter()
            llm.begin_request(60.0, attempt=1)
            try:
                for operation in row["effect_operations"]:
                    contract = contracts.get(operation)
                    if contract is None:
                        raise ValueError(f"operation left the catalogue: {operation}")
                    strict[operation] = llm._operation_is_fully_compatible(
                        row["request_text"],
                        operation,
                        contract,
                    )
                    semantic[operation] = _semantic_leaf_is_compatible(
                        llm,
                        row["request_text"],
                        operation,
                        contract,
                    )
            except Exception as exc:  # noqa: BLE001 - measurement boundary
                error = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                llm.end_request()
            measured.append(
                {
                    **{
                        key: row[key]
                        for key in (
                            "population",
                            "case_id",
                            "role",
                            "request_text",
                            "kind",
                            "effect_operations",
                            "resolved",
                            "mute",
                            "floor_fires",
                            "is_leak",
                        )
                    },
                    "uncovered": row["domain"]["any_uncovered"],
                    "strict_compatible": strict,
                    "semantic_compatible": semantic,
                    "strict_accepts": bool(strict) and all(strict.values()),
                    "semantic_accepts": bool(semantic) and all(semantic.values()),
                    "seconds": round(time.perf_counter() - started, 6),
                    "error": error,
                }
            )
            print(
                f"[{index:03d}/{len(rows):03d}] {row['case_id']} "
                f"leak={row['is_leak']} floor={row['floor_fires']} "
                f"strict={measured[-1]['strict_accepts']} "
                f"semantic={measured[-1]['semantic_accepts']}",
                flush=True,
            )
    finally:
        llm.close()
        _stop_server(process)

    report = {
        "schema": "baxy.uncovered-operation-floor.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": (
            "development diagnostic over consumed populations; executes nothing "
            "and promotes nothing. A claim requires a fresh sealed V6."
        ),
        "effects_executed": 0,
        "source": str(source.resolve()),
        "summary": _summarise(measured),
        "rows": measured,
    }
    write_json_atomic(output, report)
    return report


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def _bucket(subset: list[dict[str, Any]], verifier: str) -> dict[str, Any]:
        leaks = [row for row in subset if row["is_leak"]]
        legitimate = [row for row in subset if not row["is_leak"]]
        key = f"{verifier}_accepts"
        return {
            "leaks": len(leaks),
            "leaks_stopped": sum(1 for row in leaks if not row[key]),
            "leaks_still_leaking": [
                row["case_id"] for row in leaks if row[key]
            ],
            "legitimate": len(legitimate),
            "legitimate_broken": sum(1 for row in legitimate if not row[key]),
            "broken": [
                {
                    "population": row["population"],
                    "case_id": row["case_id"],
                    "request_text": row["request_text"],
                    "operations": row["effect_operations"],
                }
                for row in legitimate
                if not row[key]
            ],
        }

    firing = [row for row in rows if row["floor_fires"]]
    latencies = [row["seconds"] for row in rows if not row["error"]]
    return {
        "rows_with_an_effect": len(rows),
        "rows_the_floor_touches": len(firing),
        "where_the_floor_fires": {
            verifier: _bucket(firing, verifier) for verifier in ("strict", "semantic")
        },
        "if_applied_to_every_effect": {
            verifier: _bucket(rows, verifier) for verifier in ("strict", "semantic")
        },
        "seconds_p50": round(statistics.median(latencies), 6) if latencies else None,
        "errors": sum(1 for row in rows if row["error"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not args.source.is_file():
        raise SystemExit(
            f"run {boundary.__name__} first: {args.source} is missing"
        )
    report = run(args.source, args.output)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
