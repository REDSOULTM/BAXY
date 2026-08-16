"""Ground every deferred step from the reviewed catalogue without effects.

The input is the sealed R41 backing report. For each real product plan that has
an ``after_dependencies`` step, this probe supplies one synthetic completed and
verified producer observation, then sends only ``plan.ground``. Exact expected
arguments are manually curated from the user text and opaque test identity.
No plan is dispatched to App, Core, or a provider.
"""

from __future__ import annotations

import argparse
import json
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
    file_sha256,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


BACKING = (
    REPO
    / "artifacts/research/current_catalog_ready_pipeline_r15_argument_fidelity.json"
)
BACKING_SHA256 = "e72a35688f849883de453b40cd34e2def706fab4ed4cf3a3cab215a35cb8e607"
OUTPUT = REPO / "artifacts/fixes/current_catalog_dependent_grounding_r1.json"


DEPENDENT_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "app-01": {
        "producer": "window.active",
        "consumer": "app.close",
        "result": {"windowId": "window_catalog_app_01"},
        "expected": {"windowId": "window_catalog_app_01"},
    },
    "browser-02": {
        "producer": "web.search",
        "consumer": "browser.navigate",
        "result": {"results": [{"url": "https://example.com/marvel-rivals"}]},
        "expected": {"url": "https://example.com/marvel-rivals"},
    },
    "browser-03": {
        "producer": "web.search",
        "consumer": "browser.navigate",
        "result": {"results": [{"url": "https://example.com/python-downloads"}]},
        "expected": {"url": "https://example.com/python-downloads"},
    },
    "browser-04": {
        "producer": "web.search",
        "consumer": "browser.navigate",
        "result": {"results": [{"url": "https://example.com/openai"}]},
        "expected": {"url": "https://example.com/openai"},
    },
    "capture-00": {
        "producer": "capture.screenshot",
        "consumer": "vision.describe",
        "result": {"captureId": "capture_catalog_00"},
        "expected": {"captureId": "capture_catalog_00"},
    },
    "message-00": {
        "producer": "message.recipient.resolve",
        "consumer": "message.send",
        "result": {"recipientId": "recipient_catalog_00"},
        "expected": {
            "recipientId": "recipient_catalog_00",
            "text": "la amo mucho",
        },
    },
    "message-01": {
        "producer": "message.recipient.resolve",
        "consumer": "message.send",
        "result": {"recipientId": "recipient_catalog_01"},
        "expected": {"recipientId": "recipient_catalog_01", "text": "la amo"},
    },
    "message-02": {
        "producer": "message.recipient.resolve",
        "consumer": "message.send",
        "result": {"recipientId": "recipient_catalog_02"},
        "expected": {
            "recipientId": "recipient_catalog_02",
            "text": "la amo demasiado",
        },
    },
    "message-03": {
        "producer": "message.recipient.resolve",
        "consumer": "message.send",
        "result": {"recipientId": "recipient_catalog_03"},
        "expected": {"recipientId": "recipient_catalog_03", "text": "la amo"},
    },
    "message-04": {
        "producer": "message.recipient.resolve",
        "consumer": "message.send",
        "result": {"recipientId": "recipient_catalog_04"},
        "expected": {
            "recipientId": "recipient_catalog_04",
            "text": "la amo muchisimo",
        },
    },
    "message-05": {
        "producer": "message.recipient.resolve",
        "consumer": "message.send",
        "result": {"recipientId": "recipient_catalog_05"},
        "expected": {
            "recipientId": "recipient_catalog_05",
            "text": "es una increible persona",
        },
    },
    "vision-04": {
        "producer": "capture.screenshot",
        "consumer": "ocr.read",
        "result": {"captureId": "capture_catalog_04"},
        "expected": {"captureId": "capture_catalog_04"},
    },
    "vision-05": {
        "producer": "capture.screenshot",
        "consumer": "ocr.read",
        "result": {"captureId": "capture_catalog_05"},
        "expected": {"captureId": "capture_catalog_05"},
    },
    "web-00": {
        "producer": "web.search",
        "consumer": "browser.navigate.named",
        "result": {"results": [{"url": "https://example.com/keyboards"}]},
        "expected": {
            "browser": "opera",
            "url": "https://example.com/keyboards",
        },
    },
    "web-01": {
        "producer": "web.search",
        "consumer": "browser.navigate",
        "result": {"results": [{"url": "https://example.com/alan-turing"}]},
        "expected": {"url": "https://example.com/alan-turing"},
    },
    "web-02": {
        "producer": "web.search",
        "consumer": "browser.navigate.named",
        "result": {"results": [{"url": "https://example.com/flash"}]},
        "expected": {
            "browser": "opera",
            "url": "https://example.com/flash",
        },
    },
    "window-01": {
        "producer": "window.active",
        "consumer": "app.close",
        "result": {"windowId": "window_catalog_active_01"},
        "expected": {"windowId": "window_catalog_active_01"},
    },
}


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


def build_cases(backing: dict[str, Any]) -> list[dict[str, Any]]:
    rows = backing.get("rows")
    if not isinstance(rows, list):
        raise ValueError("backing report has no rows")
    dependent_rows = {
        str(row["case_id"]): row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("downstream"), dict)
        and any(
            isinstance(step, dict)
            and step.get("argumentsMode") == "after_dependencies"
            for step in row["downstream"].get("steps", [])
        )
    }
    if set(dependent_rows) != set(DEPENDENT_EXPECTATIONS):
        raise ValueError(
            "dependent oracle coverage mismatch: "
            f"missing={sorted(set(dependent_rows) - set(DEPENDENT_EXPECTATIONS))}, "
            f"stale={sorted(set(DEPENDENT_EXPECTATIONS) - set(dependent_rows))}"
        )

    cases: list[dict[str, Any]] = []
    for case_id, spec in DEPENDENT_EXPECTATIONS.items():
        row = dependent_rows[case_id]
        steps = row["downstream"]["steps"]
        consumer = next(
            step
            for step in steps
            if step.get("argumentsMode") == "after_dependencies"
        )
        dependencies = consumer.get("dependsOn")
        if not isinstance(dependencies, list) or len(dependencies) != 1:
            raise ValueError(f"{case_id} has an invalid dependent step")
        producer = next(step for step in steps if step.get("id") == dependencies[0])
        if (
            producer.get("operation") != spec["producer"]
            or consumer.get("operation") != spec["consumer"]
        ):
            raise ValueError(f"{case_id} producer/consumer contract drifted")
        observation = {
            "stepId": producer["id"],
            "operation": producer["operation"],
            "verified": True,
            "status": "completed",
            "result": spec["result"],
        }
        cases.append(
            {
                "case_id": case_id,
                "objective": row["text"],
                "purpose": consumer["purpose"],
                "operation": consumer["operation"],
                "producer": producer["operation"],
                "observations": [observation],
                "expected": spec["expected"],
            }
        )
    return cases


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists():
        raise RuntimeError("refusing to overwrite a dependent-grounding artifact")
    if file_sha256(args.backing) != args.backing_sha256:
        raise RuntimeError("dependent-grounding backing identity changed")
    backing = json.loads(args.backing.read_text(encoding="utf-8"))
    cases = build_cases(backing)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    available = {str(item["name"]) for item in capabilities}
    required = {
        str(case[key])
        for case in cases
        for key in ("operation", "producer")
    }
    if not required <= available:
        raise RuntimeError(f"authenticated catalogue lacks {sorted(required - available)}")

    limits = PROFILE_LIMITS["gpu"]
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=sidecar_environment(
            runtime,
            gpu_layers=runtime.gpu_layers,
            llm_http_timeout=limits["llm_http"],
        ),
        cwd=REPO,
    )
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        configured = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-dependent-grounding",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if configured.get("type") != "catalog.ready":
            raise RuntimeError("sidecar rejected the authenticated catalogue")
        for case in cases:
            before = time.perf_counter()
            reply = client.request(
                {
                    "type": "plan.ground",
                    "id": f"catalog-ground-{case['case_id']}",
                    "objective": case["objective"],
                    "operation": case["operation"],
                    "purpose": case["purpose"],
                    "observations": case["observations"],
                },
                35.0,
            )
            arguments = reply.get("arguments")
            exact = (
                reply.get("type") == "plan.ground.result"
                and reply.get("operation") == case["operation"]
                and arguments == case["expected"]
            )
            rows.append(
                {
                    **case,
                    "response_type": reply.get("type"),
                    "response_code": reply.get("code"),
                    "arguments": arguments,
                    "seconds": round(time.perf_counter() - before, 6),
                    "exact": exact,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "catalog-ground-shutdown"},
            timeout=limits["shutdown"],
        )

    latencies = [float(row["seconds"]) for row in rows]
    report = {
        "schema": "baxy.current-catalog-dependent-grounding.development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "reviewed_catalog_real_plans_synthetic_verified_observations",
        "authority": "plan_ground_only_no_core_no_provider_no_effect",
        "runtime": public_runtime_identity(runtime),
        "effects_executed": 0,
        "core_or_provider_requests_sent": 0,
        "total_seconds": round(time.perf_counter() - started, 3),
        "metrics": {
            "exact": sum(bool(row["exact"]) for row in rows),
            "total": len(rows),
            "seconds_p50": statistics.median(latencies),
            "seconds_p95": _p95(latencies),
        },
        "acceptance": {
            "all_exact": all(bool(row["exact"]) for row in rows),
            "backing_identity_unchanged": file_sha256(args.backing)
            == args.backing_sha256,
            "runtime_manifest_unchanged": manifest_before
            == file_sha256(args.runtime_manifest),
            "zero_effects": True,
        },
        "source": {
            "probe_sha256": file_sha256(Path(__file__).resolve()),
            "backing": str(args.backing),
            "backing_sha256": args.backing_sha256,
        },
        "failures": [row for row in rows if not row["exact"]],
        "rows": rows,
    }
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--backing", type=Path, default=BACKING)
    parser.add_argument("--backing-sha256", default=BACKING_SHA256)
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    args = parser.parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "metrics": report["metrics"],
                "acceptance": report["acceptance"],
                "failures": report["failures"],
                "effects_executed": report["effects_executed"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
