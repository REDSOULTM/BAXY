"""ABBA check of the learned-family/native-tool policy against its control."""

from __future__ import annotations

import argparse
import collections
import json
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

from experiments.mind_router_spike.probe_paraphrase_tool_quality import (  # noqa: E402
    _oracle,
)
from experiments.mind_router_spike.probe_presentable_product_oracle import (  # noqa: E402
    AUDITED_OUT_OF_SCOPE,
)
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)

OUTPUT = REPO / "artifacts" / "fixes" / "presentable_policy_abba_20260801.json"
ORDER = ("control", "candidate", "candidate", "control")


def _run_session(
    runtime: Any,
    capabilities: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    arm: str,
    session: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_MIND_NATIVE_TOOL_POLICY"] = (
        "1" if arm == "candidate" else "0"
    )
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    rows: list[dict[str, Any]] = []
    hello: dict[str, Any] = {}
    try:
        hello = client.next_message(limits["handshake"])
        models = hello.get("models") or {}
        classifier_present = "family_classifier" in models
        if (
            hello.get("type") != "hello"
            or classifier_present != (arm == "candidate")
        ):
            raise RuntimeError("the ABBA arm did not activate structurally")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": f"catalog-{arm}-{session}",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("the ABBA catalog was rejected")
        client.request(
            {
                "type": "turn.decide",
                "id": f"warm-{arm}-{session}",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in cases:
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": f"abba-{session}-{arm}-{case['case_id']}",
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": case["language"],
                },
                limits["turn.decide"],
            )
            intent = list(reply.get("intentOperations") or [])
            families = {value.split(".", 1)[0] for value in intent}
            rows.append(
                {
                    **case,
                    "arm": arm,
                    "session": session,
                    "seconds": round(time.perf_counter() - started, 6),
                    "kind": reply.get("kind"),
                    "intent_operations": intent,
                    "right_family": case["family"] in families,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": f"stop-{session}"},
            timeout=limits["shutdown"],
        )
    return rows, hello


def run(args: argparse.Namespace) -> dict[str, Any]:
    registered = resolve_runtime(manifest_path=args.runtime_manifest)
    runtime = resolve_runtime(
        manifest_path=args.runtime_manifest,
        python=registered.python,
        python_path=SRC,
        gguf=args.gguf,
        llama_server=registered.llama_server,
        gpu_layers=args.ngl,
    )
    manifest_before = file_sha256(args.runtime_manifest)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    names = tuple(str(item["name"]) for item in capabilities)
    clean = [
        row for row in _oracle(names) if row["case_id"] not in AUDITED_OUT_OF_SCOPE
    ]
    # One frozen request per represented family makes all four sessions short
    # enough to remain thermally comparable while retaining catalog breadth.
    cases_by_family: dict[str, dict[str, Any]] = {}
    for row in clean:
        cases_by_family.setdefault(str(row["family"]), row)
    cases = list(cases_by_family.values())
    rows: list[dict[str, Any]] = []
    hellos: list[dict[str, Any]] = []
    for session, arm in enumerate(ORDER, start=1):
        session_rows, hello = _run_session(
            runtime,
            capabilities,
            cases,
            arm,
            session,
        )
        rows.extend(session_rows)
        hellos.append(
            {
                "session": session,
                "arm": arm,
                "models": hello.get("models"),
            }
        )
    by_arm: dict[str, Any] = {}
    for arm in ("control", "candidate"):
        mine = [row for row in rows if row["arm"] == arm]
        latencies = [float(row["seconds"]) for row in mine]
        kinds = collections.Counter(str(row["kind"]) for row in mine)
        by_arm[arm] = {
            "turns": len(mine),
            "right_family": sum(bool(row["right_family"]) for row in mine),
            "family_accuracy": sum(bool(row["right_family"]) for row in mine)
            / len(mine),
            "conversation_share": kinds["conversation"] / len(mine),
            "seconds_p50": statistics.median(latencies),
            "kinds": dict(kinds),
        }
    report = {
        "schema": "baxy.presentable-policy-abba.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "turn.decide only; no Core/provider request",
        "effects_executed": 0,
        "installation_touched": False,
        "order": list(ORDER),
        "cases_per_session": len(cases),
        "families": sorted(cases_by_family),
        "arms": by_arm,
        "candidate_minus_control_family_accuracy": (
            by_arm["candidate"]["family_accuracy"]
            - by_arm["control"]["family_accuracy"]
        ),
        "structural_activation": hellos,
        "runtime_manifest_changed": (
            manifest_before != file_sha256(args.runtime_manifest)
        ),
        "samples": rows,
    }
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--gguf", type=Path, required=True)
    parser.add_argument("--ngl", type=int, default=99)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({"order": report["order"], "arms": report["arms"]}, indent=1))
    candidate = report["arms"]["candidate"]
    control = report["arms"]["control"]
    return 0 if candidate["family_accuracy"] > control["family_accuracy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
