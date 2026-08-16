"""Replay predicted-family native proposals through the product turn gates.

The native probe has already produced operation names without executing them.
This harness substitutes those names only for the primary policy result, keeps
the product candidate-free semantic guard, count verification, explicit-effect
contract, domain veto, compound veto, E5 relevance veto and argument-grounding
gate, and records the final side-effect-free ``turn.result``.

No Core operation or provider is invoked.  The installed runtime and manifest
are not changed.
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
OUTPUT = REPO / "artifacts" / "fixes" / "predicted_family_gate_survival_20260801.json"
AUDITED_OUT_OF_SCOPE_CASES = {
    "audio-00",
    "audio-01",
    "audio-04",
    "backup-02",
    "capture-01",
    "media-01",
    "note-03",
}


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return round(ordered[index], 4)


def _load_rows(path: Path) -> tuple[list[dict[str, Any]], Path]:
    report = json.loads(path.read_text(encoding="utf-8"))
    models = report.get("models")
    if not isinstance(models, list) or len(models) != 1:
        raise ValueError("native artifact must contain exactly one model")
    model = models[0].get("model")
    samples = models[0].get("samples")
    if not isinstance(model, dict) or not isinstance(samples, list):
        raise ValueError("native artifact is incomplete")
    rows = [
        row
        for row in samples
        if isinstance(row, dict)
        and row.get("arm") == "native_predicted_family_required"
    ]
    if len(rows) != 147 or len({row.get("case_id") for row in rows}) != 147:
        raise ValueError("native artifact does not contain the frozen required arm")
    model_path = Path(str(model.get("path") or "")).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    return [row for row in rows if row["case_id"] not in AUDITED_OUT_OF_SCOPE_CASES], model_path


def _primary_decision(operations: list[str]) -> dict[str, Any]:
    if not operations:
        return {
            "mode": "conversation",
            "operation": "",
            "question": "",
            "conversation_kind": "knowledge",
            "effect_count": "zero",
            "effect_operations": [],
            "response_language": "es",
        }
    unique = list(dict.fromkeys(operations))
    if len(unique) == 1:
        return {
            "mode": "action",
            "operation": unique[0],
            "question": "",
            "conversation_kind": "",
            "effect_count": "one",
            "effect_operations": unique,
            "response_language": "es",
        }
    return {
        "mode": "plan",
        "operation": "",
        "question": "",
        "conversation_kind": "",
        "effect_count": "multiple",
        "effect_operations": unique,
        "response_language": "es",
    }


def run(source: Path, output: Path) -> dict[str, Any]:
    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.__main__ import configure_tools
    from baxy_mind.llm import LlmRuntime
    from baxy_mind.planner import PlannerCatalog
    from baxy_mind.router import ProcessIntentRouter, RequestBudgetEncoder
    from baxy_mind.turn_evidence import TurnEvidenceService

    source_rows, model_path = _load_rows(source)
    by_text = {str(row["text"]): row for row in source_rows}
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    tools = configure_tools(capabilities)
    tool_by_name = {
        str(tool["function"]["canonical_name"]): tool for tool in tools
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
    router = ProcessIntentRouter()
    evidence = TurnEvidenceService()
    llm: LlmRuntime | None = None
    try:
        if not router.try_ready(180.0):
            raise RuntimeError("E5 router did not become ready")
        encoder = RequestBudgetEncoder(router)
        evidence.start(encoder, lambda: router.try_ready(0.0))
        deadline = time.monotonic() + 185.0
        while evidence.state == "building" and time.monotonic() < deadline:
            time.sleep(0.1)
        if evidence.state != "ready":
            raise RuntimeError("turn evidence did not become ready")
        catalog = PlannerCatalog(tools, encoder=encoder)
        original_shortlist = catalog.shortlist

        def predicted_shortlist(
            objective: str,
            *,
            preferred_families: Any = (),
        ):
            del preferred_families
            row = by_text.get(objective)
            if row is None:
                return original_shortlist(objective)
            predicted = str(row["predicted_family"])
            return tuple(
                tool for tool in catalog.tools if tool.name.split(".", 1)[0] == predicted
            )

        catalog.shortlist = predicted_shortlist  # type: ignore[method-assign]
        llm = LlmRuntime()
        original_schema = llm._post_schema_object
        active: dict[str, str] = {"text": ""}
        fired: dict[str, list[str]] = {}
        decided: dict[str, dict[str, Any]] = {}

        for gate_name in (
            "apply_explicit_effect_contract",
            "apply_operation_domain_grounding_veto",
            "apply_compound_effect_conservation_veto",
            "apply_turn_action_relevance_veto",
            "apply_turn_action_grounding_gate",
            "apply_conversation_effect_presentation",
        ):
            original_gate = getattr(sidecar_module, gate_name)

            def watch_gate(
                decision: dict[str, Any],
                *args: Any,
                _name: str = gate_name,
                _original: Any = original_gate,
                **kwargs: Any,
            ) -> dict[str, Any]:
                before = list((decision or {}).get("effect_operations") or [])
                result = _original(decision, *args, **kwargs)
                after = list((result or {}).get("effect_operations") or [])
                if before and not after:
                    case_id = str(by_text[active["text"]]["case_id"])
                    fired.setdefault(case_id, []).append(_name)
                return result

            setattr(sidecar_module, gate_name, watch_gate)

        def constrained_primary(
            payload: dict[str, Any],
            label: str,
        ) -> dict[str, Any]:
            if label != "la política de turno":
                return original_schema(payload, label)
            row = by_text[active["text"]]
            return _primary_decision(list(row.get("operations") or []))

        llm._post_schema_object = constrained_primary  # type: ignore[method-assign]
        original_decide = llm.decide_turn

        def watch_decide(*args: Any, **kwargs: Any) -> dict[str, Any]:
            result = original_decide(*args, **kwargs)
            case_id = str(by_text[active["text"]]["case_id"])
            decided[case_id] = {
                "mode": result.get("mode"),
                "effect_operations": list(result.get("effect_operations") or []),
                "effect_verification": result.get("effect_verification"),
            }
            return result

        llm.decide_turn = watch_decide  # type: ignore[method-assign]
        results: list[dict[str, Any]] = []
        for index, source_row in enumerate(source_rows, start=1):
            text = str(source_row["text"])
            active["text"] = text
            encoder.begin_request(30.0)
            llm.begin_request(30.0, attempt=1)
            started = time.perf_counter()
            error = ""
            result: dict[str, Any] = {}
            try:
                result = sidecar_module._prepare_turn_result(
                    {
                        "type": "turn.decide",
                        "id": str(source_row["case_id"]),
                        "text": text,
                        "history": [],
                    },
                    llm=llm,
                    planner_catalog=catalog,
                    turn_evidence=evidence,
                    encoder=encoder,
                    tool_by_name=tool_by_name,
                    application_names=(),
                )
            except Exception as exc:  # noqa: BLE001 - measurement boundary
                error = f"{type(exc).__name__}: {exc}"[:300]
            finally:
                llm.end_request()
                encoder.end_request()
            elapsed = time.perf_counter() - started
            final_operations = list(result.get("effectOperations") or [])
            final_families = {
                operation.split(".", 1)[0] for operation in final_operations
            }
            raw_outcome = str(source_row["outcome"])
            final_outcome = (
                "error"
                if error
                else "right_family"
                if str(source_row["family"]) in final_families
                else "no_operation"
                if not final_operations
                else "wrong_family"
            )
            results.append(
                {
                    "case_id": source_row["case_id"],
                    "text": text,
                    "expected_family": source_row["family"],
                    "predicted_family": source_row["predicted_family"],
                    "raw_operations": list(source_row.get("operations") or []),
                    "raw_outcome": raw_outcome,
                    "decide_turn": decided.get(str(source_row["case_id"])),
                    "vetoes": fired.get(str(source_row["case_id"]), []),
                    "final_kind": result.get("kind"),
                    "final_operations": final_operations,
                    "final_outcome": final_outcome,
                    "wrong_raw_proposal_retained_authority": (
                        raw_outcome == "wrong_family" and bool(final_operations)
                    ),
                    "seconds": round(elapsed, 6),
                    "error": error,
                }
            )
            print(
                f"[{index:03d}/{len(source_rows):03d}] "
                f"{source_row['case_id']} raw={raw_outcome} final={final_outcome}",
                flush=True,
            )
    finally:
        if llm is not None:
            llm.close()
        evidence.stop(timeout=5.0)
        router.close()
        _stop_server(process)

    outcomes = collections.Counter(row["final_outcome"] for row in results)
    wrong_retained = [
        row for row in results if row["wrong_raw_proposal_retained_authority"]
    ]
    latencies = [row["seconds"] for row in results]
    report = {
        "schema": "baxy.predicted-family-gate-survival.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source.resolve()),
        "effects_executed": 0,
        "installation_touched": False,
        "runtime_manifest_changed": False,
        "cases": len(results),
        "outcomes": dict(outcomes),
        "right_family_share": round(
            outcomes.get("right_family", 0) / len(results), 4
        ),
        "no_operation_share": round(
            outcomes.get("no_operation", 0) / len(results), 4
        ),
        "wrong_raw_proposals_retaining_authority": len(wrong_retained),
        "seconds_p50": round(statistics.median(latencies), 4),
        "seconds_p95": _percentile(latencies, 0.95),
        "rows": results,
        "method": (
            "The recorded native required-arm operations replace only the primary "
            "policy object. The product semantic guard, count verifier, explicit "
            "contract and every downstream authority veto run against Qwen3 4B."
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
            {
                key: value
                for key, value in report.items()
                if key not in {"rows", "method"}
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
