"""Measure how long the turn-evidence index takes to become ready.

Drives the real product sidecar, polls ``turn.evidence.status`` once per
second after ``catalog.configure`` and records the state transitions.  When
``--variant wait-index`` is passed, every ``turn.decide`` in the child
sidecar first waits (bounded) until the evidence index leaves ``building``,
which makes the P prompt composition independent of request arrival time.
No Core operation is dispatched; nothing productive changes.
"""

from __future__ import annotations

import argparse
import json
import os
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
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    build_workload,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    validate_reply,
    write_json_atomic,
)

DEFAULT_OUTPUT = (
    REPO / "artifacts" / "fixes" / "evidence_index_build_time_20260730.json"
)


def _run_wait_index_sidecar(max_wait_seconds: float) -> int:
    """Sidecar entry: bounded wait for evidence readiness inside turn.decide."""

    from baxy_mind import __main__ as sidecar_module
    from baxy_mind.turn_evidence import TurnEvidenceService

    original_families = TurnEvidenceService.candidate_families
    original_retrieve = TurnEvidenceService.retrieve

    def _wait_ready(service: TurnEvidenceService) -> None:
        deadline = time.monotonic() + max_wait_seconds
        while time.monotonic() < deadline:
            if service.state != "building":
                return
            time.sleep(0.05)

    def waiting_families(self: TurnEvidenceService, text: str, encoder: Any):
        _wait_ready(self)
        return original_families(self, text, encoder)

    def waiting_retrieve(self: TurnEvidenceService, *args: Any, **kwargs: Any):
        _wait_ready(self)
        return original_retrieve(self, *args, **kwargs)

    TurnEvidenceService.candidate_families = waiting_families  # type: ignore[method-assign]
    TurnEvidenceService.retrieve = waiting_retrieve  # type: ignore[method-assign]
    try:
        return sidecar_module.main()
    finally:
        TurnEvidenceService.candidate_families = original_families  # type: ignore[method-assign]
        TurnEvidenceService.retrieve = original_retrieve  # type: ignore[method-assign]


def run(
    output: Path,
    *,
    variant: str,
    case_ids: tuple[str, ...],
    max_wait_seconds: float,
    post_ready_margin_seconds: float = 0.0,
    cases_before_ready: bool = False,
) -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    router_delay = os.environ.get("BAXY_PROBE_ROUTER_START_DELAY", "").strip()
    if router_delay:
        environment["BAXY_MIND_ROUTER_START_DELAY"] = router_delay
    command = [str(runtime.python), "-u", "-X", "utf8"]
    if variant == "wait-index":
        command.extend(
            [
                str(Path(__file__).resolve()),
                "--sidecar-wait-index",
                "--max-wait-seconds",
                str(max_wait_seconds),
            ]
        )
    else:
        command.extend(["-m", "baxy_mind"])
    client = JsonLineProcess(command, environment=environment, cwd=REPO)
    status_timeline: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar hello rejected")
        catalog_started = time.perf_counter()
        catalog = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-evidence-build",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        catalog_done = time.perf_counter()
        catalog_seconds = round(catalog_done - catalog_started, 3)
        if catalog.get("type") != "catalog.ready":
            raise RuntimeError("catalog handshake rejected")
        early_cases: list[dict[str, Any]] = []
        if cases_before_ready:
            for item in build_workload():
                if (
                    item.request_type != "turn.decide"
                    or item.case_id not in case_ids
                ):
                    continue
                begin = time.perf_counter()
                reply = client.request(item.message, limits["turn.decide"])
                early_cases.append(
                    {
                        "case_id": item.case_id,
                        "seconds_after_catalog": round(
                            begin - catalog_done, 2
                        ),
                        "elapsed_seconds": round(
                            time.perf_counter() - begin, 4
                        ),
                        "kind": reply.get("kind"),
                        "turn_attempts": reply.get("turn_attempts"),
                        "validation_error": validate_reply(item, reply)
                        or None,
                    }
                )
        ready_at: float | None = None
        for _ in range(300):
            status = client.request(
                {"type": "turn.evidence.status", "id": "evidence-status"},
                10.0,
            )
            elapsed = time.perf_counter() - catalog_done
            state = status.get("state")
            if not status_timeline or status_timeline[-1]["state"] != state:
                status_timeline.append(
                    {"state": state, "seconds_after_catalog": round(elapsed, 2)}
                )
            if state in {"ready", "failed", "disabled"}:
                ready_at = elapsed
                break
            time.sleep(1.0)
        del ready_at
        if post_ready_margin_seconds > 0.0:
            time.sleep(post_ready_margin_seconds)
        for item in [] if cases_before_ready else build_workload():
            if item.request_type != "turn.decide" or item.case_id not in case_ids:
                continue
            begin = time.perf_counter()
            reply = client.request(item.message, limits["turn.decide"])
            cases.append(
                {
                    "case_id": item.case_id,
                    "elapsed_seconds": round(time.perf_counter() - begin, 4),
                    "kind": reply.get("kind"),
                    "turn_attempts": reply.get("turn_attempts"),
                    "validation_error": validate_reply(item, reply) or None,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-evidence-build"},
            timeout=limits["shutdown"],
        )
    report = {
        "schema": "baxy.evidence-index-build-time.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": public_runtime_identity(runtime),
        "variant": variant,
        "router_start_delay_env": os.environ.get(
            "BAXY_PROBE_ROUTER_START_DELAY", ""
        ),
        "catalog_configure_seconds": catalog_seconds,
        "early_cases": early_cases,
        "status_timeline": status_timeline,
        "index_ready_seconds_after_catalog": (
            status_timeline[-1]["seconds_after_catalog"]
            if status_timeline
            else None
        ),
        "cases_after_ready": cases,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--variant", choices=("baseline", "wait-index"), default="baseline")
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--max-wait-seconds", type=float, default=120.0)
    parser.add_argument("--post-ready-margin-seconds", type=float, default=0.0)
    parser.add_argument("--cases-before-ready", action="store_true")
    parser.add_argument("--sidecar-wait-index", action="store_true")
    args = parser.parse_args()
    if args.sidecar_wait_index:
        return _run_wait_index_sidecar(args.max_wait_seconds)
    case_ids = tuple(args.case_ids) if args.case_ids else ()
    report = run(
        args.output,
        variant=args.variant,
        case_ids=case_ids,
        max_wait_seconds=args.max_wait_seconds,
        post_ready_margin_seconds=args.post_ready_margin_seconds,
        cases_before_ready=args.cases_before_ready,
    )
    print(
        json.dumps(
            {
                "catalog_seconds": report["catalog_configure_seconds"],
                "timeline": report["status_timeline"],
                "early_cases": report["early_cases"],
                "cases": report["cases_after_ready"],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
