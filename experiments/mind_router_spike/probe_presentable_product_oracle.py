"""Measure the complete candidate product on the cleaned real-request oracle.

The probe starts the real JSONL mind sidecar with an explicitly selected GGUF,
configures the authenticated production catalog, and sends each frozen request
through ``turn.decide``. It never sends a plan to Core and therefore cannot
execute an effect.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
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

OUTPUT = (
    REPO
    / "artifacts"
    / "fixes"
    / "presentable_product_oracle_qwen3_20260801.json"
)
FROZEN_SAMPLE_ARTIFACT = (
    REPO / "artifacts" / "fixes" / "native_predicted_family_qwen3_20260801.json"
)
FROZEN_SAMPLE_SHA256 = "c8db6a7b32f2ec607edfefd731a59ffb38dc918be3705f2e2fcaeaca0bce3feb"
AUDITED_OUT_OF_SCOPE = frozenset(
    {
        "audio-00",
        "audio-01",
        "audio-04",
        "backup-02",
        "capture-01",
        "media-01",
        "note-03",
    }
)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot take a percentile of an empty population")
    rank = max(0, min(len(ordered) - 1, int(percentile * len(ordered) + 0.999) - 1))
    return ordered[rank]


def _load_frozen_oracle(catalog_names: tuple[str, ...]) -> list[dict[str, Any]]:
    """Load the hash-bound 147-case population, independent of recognizer drift."""

    if (
        not FROZEN_SAMPLE_ARTIFACT.is_file()
        or FROZEN_SAMPLE_ARTIFACT.stat().st_size > 2 * 1024 * 1024
    ):
        raise RuntimeError("the frozen product oracle artifact is unavailable")
    report = json.loads(FROZEN_SAMPLE_ARTIFACT.read_text(encoding="utf-8"))
    sample = report.get("frozen_sample")
    if not isinstance(sample, list):
        raise RuntimeError("the frozen product oracle has no sample")
    identity = hashlib.sha256(
        json.dumps(
            sample,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    required_keys = {"case_id", "family", "label", "language", "text"}
    available_families = {name.split(".", 1)[0] for name in catalog_names}
    if (
        len(sample) != 147
        or identity != FROZEN_SAMPLE_SHA256
        or len({row.get("case_id") for row in sample if isinstance(row, dict)})
        != len(sample)
        or any(
            not isinstance(row, dict)
            or set(row) != required_keys
            or row.get("family") not in available_families
            or row.get("language") not in {"es", "en"}
            or not isinstance(row.get("text"), str)
            for row in sample
        )
    ):
        raise RuntimeError("the frozen product oracle identity is invalid")
    return [dict(row) for row in sample]


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
    catalog_names = tuple(str(item["name"]) for item in capabilities)
    all_cases = _load_frozen_oracle(catalog_names)
    cases = [
        case for case in all_cases if case["case_id"] not in AUDITED_OUT_OF_SCOPE
    ]
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    rows: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("the candidate sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-presentable-candidate",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("the candidate sidecar rejected the catalog")
        client.request(
            {
                "type": "turn.decide",
                "id": "warm-presentable-candidate",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for index, case in enumerate(cases, start=1):
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": f"presentable-{case['case_id']}",
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": case["language"],
                },
                limits["turn.decide"],
            )
            elapsed = time.perf_counter() - started
            intent = list(reply.get("intentOperations") or [])
            effects = list(reply.get("effectOperations") or [])
            intent_families = {name.split(".", 1)[0] for name in intent}
            effect_families = {name.split(".", 1)[0] for name in effects}
            rows.append(
                {
                    **case,
                    "index": index,
                    "seconds": round(elapsed, 6),
                    "kind": reply.get("kind"),
                    "intent_operations": intent,
                    "effect_operations": effects,
                    "intent_outcome": (
                        "right_family"
                        if case["family"] in intent_families
                        else "no_operation"
                        if not intent
                        else "wrong_family"
                    ),
                    "effect_outcome": (
                        "right_family"
                        if case["family"] in effect_families
                        else "no_operation"
                        if not effects
                        else "wrong_family"
                    ),
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-presentable"},
            timeout=limits["shutdown"],
        )

    manifest_after = file_sha256(args.runtime_manifest)
    latencies = [float(row["seconds"]) for row in rows]
    intents = collections.Counter(str(row["intent_outcome"]) for row in rows)
    effects = collections.Counter(str(row["effect_outcome"]) for row in rows)
    kinds = collections.Counter(str(row["kind"]) for row in rows)
    report = {
        "schema": "baxy.presentable-product-oracle.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "turn.decide only; no plan was sent to Core or a provider",
        "effects_executed": 0,
        "installation_touched": False,
        "runtime_manifest_changed": manifest_before != manifest_after,
        "runtime_manifest_sha256_before": manifest_before,
        "runtime_manifest_sha256_after": manifest_after,
        "runtime": public_runtime_identity(runtime),
        "population": {
            "frozen_sample_sha256": FROZEN_SAMPLE_SHA256,
            "original_cases": len(all_cases),
            "excluded_audited_out_of_scope": sorted(AUDITED_OUT_OF_SCOPE),
            "clean_cases": len(cases),
        },
        "metrics": {
            "intent_family_accuracy": intents["right_family"] / len(rows),
            "intent_outcomes": dict(intents),
            "effect_family_accuracy": effects["right_family"] / len(rows),
            "effect_outcomes": dict(effects),
            "action_answered_as_conversation_share": kinds["conversation"]
            / len(rows),
            "kinds": dict(kinds),
            "turn_decide_seconds_p50": statistics.median(latencies),
            "turn_decide_seconds_p95": _percentile(latencies, 0.95),
        },
        "targets": {
            "intent_family_accuracy_at_least_0_70": (
                intents["right_family"] / len(rows) >= 0.70
            ),
            "action_answered_as_conversation_at_most_0_10": (
                kinds["conversation"] / len(rows) <= 0.10
            ),
            "turn_decide_p50_at_most_1_5": statistics.median(latencies) <= 1.5,
            "turn_decide_p95_at_most_5": _percentile(latencies, 0.95) <= 5.0,
            "unasked_effects_executed_zero": True,
            "frozen_population_is_exactly_140": len(cases) == 140,
        },
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
    print(json.dumps({"metrics": report["metrics"], "targets": report["targets"]}, indent=1))
    return 0 if all(report["targets"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
