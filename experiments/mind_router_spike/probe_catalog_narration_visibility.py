"""Exercise every public Core narration family through message.compose only.

The probe never configures the operation catalog and never sends a plan, Core
request, provider request, or effect. It verifies that the local model can turn
the exact family-level success and failure floors used by Core into acceptable
person-facing Spanish while preserving the required fact and actor.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import unicodedata
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
    current_core_capabilities,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


OUTPUT = REPO / "artifacts/fixes/catalog_narration_visibility_r1.json"
NARRATOR_SOURCE = REPO / "src/Baxy.Core/Operations/ProductOperationNarrator.cs"
APP_POLICY_SOURCE = REPO / "src/Baxy.App/UserMessagePolicy.cs"
MIND_SOURCE = REPO / "src/baxy_mind/llm.py"

FAMILY_SUBJECTS = {
    "app": "app",
    "audio": "audio",
    "backup": "backup",
    "bluetooth": "bluetooth",
    "browser": "browser",
    "calendar": "calendar",
    "capture": "capture",
    "clipboard": "clipboard",
    "email": "email",
    "filesystem": "filesystem",
    "game": "game",
    "input": "input",
    "media": "media",
    "memory": "memory",
    "message": "message",
    "network": "network",
    "note": "note",
    "notification": "notification",
    "ocr": "ocr",
    "office": "office",
    "package": "package",
    "peripheral": "peripheral",
    "reminder": "reminder",
    "routine": "routine",
    "streaming": "streaming",
    "system": "system",
    "task": "task",
    "vision": "vision",
    "web": "web",
    "wifi": "wifi",
    "window": "window",
}
FORBIDDEN_TERMS = (
    "planner",
    "router",
    "tool",
    "catálogo",
    "catalogo",
    "schema",
    "operación",
    "operacion",
    "capacidad interna",
    "grounding",
    "checkpoint",
    "reconciliación",
    "reconciliacion",
    "motor local",
    "core",
    "datos verificables",
    "pasos verificables",
    "identificador interno",
)
GENERIC_FOLLOWUPS = (
    "qué quieres hacer ahora",
    "que quieres hacer ahora",
    "necesitas algo más",
    "necesitas algo mas",
)


def fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value).casefold()
    return "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )


def build_cases(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    families = {str(item["name"]).split(".", 1)[0] for item in capabilities}
    if families != set(FAMILY_SUBJECTS):
        raise RuntimeError(
            "family narration map drifted: "
            f"missing={sorted(families - set(FAMILY_SUBJECTS))} "
            f"stale={sorted(set(FAMILY_SUBJECTS) - families)}"
        )
    cases: list[dict[str, Any]] = []
    for family, subject in FAMILY_SUBJECTS.items():
        cases.append(
            {
                "case_id": f"{family}-success",
                "family": family,
                "intent": "status",
                "subject": subject,
                "source": json.dumps(
                    {
                        "kind": "operation",
                        "operation": f"{family}.probe",
                        "polarity": "success",
                        "verified": True,
                    },
                    ensure_ascii=False,
                ),
                "required_action": "",
                "budget_seconds": 5.0,
            }
        )
        cases.append(
            {
                "case_id": f"{family}-failure",
                "family": family,
                "intent": "error",
                "subject": subject,
                "source": json.dumps(
                    {
                        "kind": "operation",
                        "operation": f"{family}.probe",
                        "polarity": "failure",
                        "verified": False,
                    },
                    ensure_ascii=False,
                ),
                "required_action": "",
                "budget_seconds": 10.0,
            }
        )
    return cases


def validate(case: dict[str, Any], reply: dict[str, Any]) -> list[str]:
    if reply.get("type") != "message.compose.result":
        return ["unexpected_response"]
    text = str(reply.get("text") or "").strip()
    if not text:
        return ["empty_response"]
    folded = fold(text)
    errors: list[str] = []
    if case["intent"] == "error" and "no pude" not in folded and "could not" not in folded and "couldn't" not in folded:
        errors.append("missing_failure_polarity")
    for value in (*FORBIDDEN_TERMS, *GENERIC_FOLLOWUPS):
        if fold(value) in folded:
            errors.append(f"forbidden:{value}")
    return errors


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(quantile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def run(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("refusing to overwrite an existing narration artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    capabilities = current_core_capabilities(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    cases = build_cases(capabilities)
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
        for case in cases:
            facts: dict[str, Any] = {
                "situation": case["source"],
                "mustNotAskFollowUp": True,
                "requiredFacts": [case["subject"]],
                "forbiddenResponseTerms": list(FORBIDDEN_TERMS),
            }
            if case["required_action"]:
                facts.update(
                    {
                        "actor": "BAXY (yo, primera persona)",
                        "mustPreserveFirstPerson": True,
                        "requiredAction": case["required_action"],
                        "requiredActions": [case["required_action"]],
                    }
                )
            else:
                facts["partialMission"] = True
            before = time.perf_counter()
            reply = client.request(
                {
                    "type": "message.compose",
                    "id": f"narration-{case['case_id']}",
                    "userText": "Completa esta solicitud.",
                    "intent": case["intent"],
                    "facts": facts,
                    "budgetSeconds": case["budget_seconds"],
                },
                float(case["budget_seconds"]) + 2.0,
            )
            seconds = round(time.perf_counter() - before, 6)
            errors = validate(case, reply)
            rows.append(
                {
                    **case,
                    "seconds": seconds,
                    "text": reply.get("text"),
                    "passed": not errors,
                    "errors": errors,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "narration-shutdown"},
            timeout=limits["shutdown"],
        )
    latencies = [float(row["seconds"]) for row in rows]
    manifest_after = file_sha256(args.runtime_manifest)
    report = {
        "schema": "baxy.catalog-narration-visibility.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "all_public_operation_families_success_and_failure",
        "authority": "message.compose_only_no_catalog_no_plan_no_core_no_provider",
        "effects_executed": 0,
        "runtime_manifest_changed": manifest_before != manifest_after,
        "runtime": public_runtime_identity(runtime),
        "source": {
            "narrator_sha256": file_sha256(NARRATOR_SOURCE),
            "app_policy_sha256": file_sha256(APP_POLICY_SOURCE),
            "mind_sha256": file_sha256(MIND_SOURCE),
        },
        "metrics": {
            "families": len(FAMILY_SUBJECTS),
            "cases": len(rows),
            "passed": sum(bool(row["passed"]) for row in rows),
            "failed": sum(not bool(row["passed"]) for row in rows),
            "seconds_p50": statistics.median(latencies),
            "seconds_p95": percentile(latencies, 0.95),
            "seconds_maximum": max(latencies),
            "total_seconds": round(time.perf_counter() - started, 3),
        },
        "rows": rows,
    }
    write_json_atomic(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps(report["metrics"], indent=2))
    return 0 if (
        report["metrics"]["failed"] == 0
        and report["runtime_manifest_changed"] is False
        and report["effects_executed"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
