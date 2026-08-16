"""Measure the independent leaf verifier on the current-catalog R2 proposals.

This is a development-only authority diagnostic.  It replays no turn and
executes no effect: each raw leaf already recorded by the sidecar is checked
against the trusted request plus the authenticated operation description and
schema.  The source report is hash-bound so later product changes cannot be
credited with these frozen observations.
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


SOURCE = REPO / "artifacts/fixes/current_catalog_review_product_probe_r2.json"
OUTPUT = REPO / "artifacts/fixes/current_catalog_leaf_compatibility_r2.json"
SEMANTIC_LEAF_IDENTITY_PROMPT = (
    "Judge only whether the supplied catalog operation is the same atomic "
    "effect that the person requested. compatible=true when its verb, domain, "
    "object/source and destination match one requested atomic effect. Missing "
    "human arguments, normalized values, exact IDs, confirmation, or a "
    "catalog-defined technical predecessor do not change operation identity; "
    "later stages handle those. In a compound request, the operation need cover "
    "one requested atomic effect, not the whole compound. compatible=false for "
    "a related domain with a different verb, object, source, destination, "
    "device, temporal meaning, or postcondition; also false for conversation, "
    "negation, hypotheticals and past events. Examples: opening an app is not "
    "closing it; listing printers is not setting the default printer; copying "
    "the focused selection is not writing supplied text to the clipboard; "
    "describing a scene is not transcribing its visible text. Do not propose "
    "another operation."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return round(ordered[index], 6)


def _raw_operations(row: dict[str, Any]) -> list[str]:
    raw = row.get("raw_decision")
    if not isinstance(raw, dict):
        return []
    operations = raw.get("effect_operations")
    if not isinstance(operations, list):
        return []
    return list(
        dict.fromkeys(
            operation for operation in operations if isinstance(operation, str)
        )
    )


def _semantic_leaf_is_compatible(
    llm: Any,
    text: str,
    operation: str,
    contract: dict[str, Any],
) -> bool:
    payload = {
        "messages": [
            {"role": "system", "content": SEMANTIC_LEAF_IDENTITY_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Request:\n{text}\n\n"
                    f"Operation:\n{operation} | {contract['description']}\n"
                    "Schema:\n"
                    + json.dumps(
                        contract["arguments_schema"],
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                ),
            },
        ],
        "temperature": 0.0,
        "seed": 0,
        "max_tokens": 24,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "baxy_semantic_leaf_compatibility",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"compatible": {"type": "boolean"}},
                    "required": ["compatible"],
                    "additionalProperties": False,
                },
            },
        },
    }
    try:
        raw = llm._post_schema_object(
            payload,
            "the semantic leaf identity verification",
        )
    except ValueError:
        return False
    return (
        isinstance(raw, dict)
        and set(raw) == {"compatible"}
        and raw.get("compatible") is True
    )


def run(source: Path, output: Path, verifier: str) -> dict[str, Any]:
    from baxy_mind.llm import LlmRuntime

    source_report = json.loads(source.read_text(encoding="utf-8"))
    source_rows = source_report.get("rows")
    if (
        source_report.get("schema")
        != "baxy.current-catalog-development-product-probe.v1"
        or not isinstance(source_rows, list)
        or len(source_rows) != 147
        or source_report.get("source", {}).get("blind_holdout") is not False
    ):
        raise ValueError("source is not the complete current-catalog R2 report")

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
    rows: list[dict[str, Any]] = []
    try:
        for index, source_row in enumerate(source_rows, start=1):
            operations = _raw_operations(source_row)
            checks: dict[str, bool] = {}
            error = ""
            started = time.perf_counter()
            llm.begin_request(30.0, attempt=1)
            try:
                for operation in operations:
                    if operation not in contracts:
                        raise ValueError(f"operation left current catalog: {operation}")
                    if verifier == "existing":
                        checks[operation] = llm._operation_is_fully_compatible(
                            str(source_row["text"]),
                            operation,
                            contracts[operation],
                        )
                    else:
                        checks[operation] = _semantic_leaf_is_compatible(
                            llm,
                            str(source_row["text"]),
                            operation,
                            contracts[operation],
                        )
            except Exception as exc:  # noqa: BLE001 - measurement boundary
                error = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                llm.end_request()
            seconds = time.perf_counter() - started
            accepted = bool(operations) and not error and all(checks.values())
            raw_correct = bool(source_row.get("raw_decision_correct"))
            rows.append(
                {
                    "case_id": source_row["case_id"],
                    "text": source_row["text"],
                    "outcome": source_row["outcome"],
                    "operations": operations,
                    "raw_correct": raw_correct,
                    "compatibility": checks,
                    "accepted": accepted,
                    "correct_proposal_accepted": raw_correct and accepted,
                    "correct_proposal_rejected": (
                        raw_correct and bool(operations) and not accepted
                    ),
                    "wrong_proposal_accepted": (
                        not raw_correct and bool(operations) and accepted
                    ),
                    "wrong_proposal_rejected": (
                        not raw_correct and bool(operations) and not accepted
                    ),
                    "seconds": round(seconds, 6),
                    "error": error,
                }
            )
            print(
                f"[{index:03d}/{len(source_rows):03d}] "
                f"{source_row['case_id']} raw_correct={raw_correct} "
                f"compatible={accepted}",
                flush=True,
            )
    finally:
        llm.close()
        _stop_server(process)

    proposed = [row for row in rows if row["operations"]]
    correct = [row for row in proposed if row["raw_correct"]]
    wrong = [row for row in proposed if not row["raw_correct"]]
    latencies = [float(row["seconds"]) for row in proposed]
    counts = collections.Counter(
        "correct_accepted"
        if row["correct_proposal_accepted"]
        else "correct_rejected"
        if row["correct_proposal_rejected"]
        else "wrong_accepted"
        if row["wrong_proposal_accepted"]
        else "wrong_rejected"
        for row in proposed
    )
    report = {
        "schema": "baxy.current-catalog-leaf-compatibility.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_review_not_blind",
        "verifier": verifier,
        "source": str(source.resolve()),
        "source_sha256": _sha256(source),
        "effects_executed": 0,
        "installation_touched": False,
        "cases": len(source_rows),
        "proposals": len(proposed),
        "counts": dict(sorted(counts.items())),
        "correct_proposal_recall": (
            sum(row["accepted"] for row in correct) / len(correct)
            if correct
            else 0.0
        ),
        "wrong_proposal_rejection": (
            sum(not row["accepted"] for row in wrong) / len(wrong)
            if wrong
            else 0.0
        ),
        "wrong_proposals_accepted": sum(
            row["wrong_proposal_accepted"] for row in rows
        ),
        "seconds_p50": statistics.median(latencies) if latencies else None,
        "seconds_p95": _percentile(latencies, 0.95),
        "errors": sum(bool(row["error"]) for row in rows),
        "rows": rows,
        "method": (
            "Every raw leaf recorded by R2 is independently checked against "
            "the trusted text and authenticated description/schema; the "
            "candidate veto accepts only unanimous true results. The existing "
            "verifier requires whole-request direct completeness; the semantic "
            "leaf verifier checks only atomic operation identity and leaves "
            "arguments, predecessors and confirmation to later gates."
        ),
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--verifier",
        choices=("existing", "semantic-leaf"),
        default="existing",
    )
    args = parser.parse_args()
    report = run(args.source, args.output, args.verifier)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "rows"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
