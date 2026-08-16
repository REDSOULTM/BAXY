"""Adjudicate and probe the residual errors in opened MTOP R4 development.

MTOP measures annotated semantic intent.  BAXY additionally needs enough
literal evidence and authenticated capability support to prepare an operation
without inventing authority.  This audit keeps both views: the official label
is never rewritten, while a separately named product adjudication records
whether the standalone utterance is executable, needs clarification, or must
remain conversational.

Only the opened development partition is read.  The probe sends
``catalog.configure`` and ``turn.decide`` to the production mind; it never
sends an operation or plan to Core and therefore cannot execute an effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
SCRIPTS = REPO / "scripts"
for path in (REPO, SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import measure_turn_policy_v52_mtop_validation as mtop  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
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


CONSENSUS = REPO / "artifacts/research/verified_consensus_mtop_validation_r2.json"
OUTPUT = REPO / "artifacts/research/mtop_r4_residual_adjudication_r1.json"
NO_ACTION = "__none__"

# These decisions are deliberately explicit and reviewable.  They apply only
# to the nine residual source identities in the already-open R4 population;
# they are not training labels and are not a runtime lookup table.
ADJUDICATIONS: dict[str, dict[str, str]] = {
    "mtop-official-v2:es:3132353731363536": {
        "product_outcome": "action",
        "product_operation": "media.control",
        "representability": "supported_executable",
        "reason": "The imperative asks to skip the current artist; media.control can ground action=next without naming a new artist.",
    },
    "mtop-official-v2:es:3139393833363831": {
        "product_outcome": "action",
        "product_operation": "web.search",
        "representability": "benchmark_label_mismatch",
        "reason": "The standalone text asks for places to go; calendar.event.list would invent a personal-calendar request.",
    },
    "mtop-official-v2:en:3231323233383637": {
        "product_outcome": "action",
        "product_operation": "reminder.resolve.exact",
        "representability": "supported_executable",
        "reason": "The noun phrase is a read-only lookup with the literal title birthdays, not authority to create a reminder.",
    },
    "mtop-official-v2:es:3231323233383637": {
        "product_outcome": "action",
        "product_operation": "reminder.resolve.exact",
        "representability": "supported_executable",
        "reason": "The noun phrase is a read-only lookup with the literal title cumpleaños, not authority to create a reminder.",
    },
    "mtop-official-v2:en:3231353938383134": {
        "product_outcome": "clarify",
        "product_operation": "notification.cancel.at",
        "representability": "supported_clarification",
        "reason": "An already-set alarm without a time or explicit latest cue needs identity clarification before cancellation.",
    },
    "mtop-official-v2:es:3231363336363935": {
        "product_outcome": "action",
        "product_operation": "notification.dismiss",
        "representability": "supported_executable",
        "reason": "Para is an imperative stop command here and the authenticated predecessor resolves the due notification before dismissal.",
    },
    "mtop-official-v2:en:3231363336383839": {
        "product_outcome": "conversation",
        "product_operation": NO_ACTION,
        "representability": "implicit_context_only",
        "reason": "Without an audible-alarm or dialogue-state observation, the sentence grants no standalone authority to dismiss anything.",
    },
    "mtop-official-v2:es:3231363336383839": {
        "product_outcome": "conversation",
        "product_operation": NO_ACTION,
        "representability": "implicit_context_only",
        "reason": "Without an audible-alarm or dialogue-state observation, the sentence grants no standalone authority to dismiss anything.",
    },
    "mtop-official-v2:es:3232323830393133": {
        "product_outcome": "action",
        "product_operation": "media.play.query",
        "representability": "supported_executable",
        "reason": "The play imperative contains an artist and genre, which fully ground a provider query.",
    },
}

PRIMARY_REFERENCES = [
    {
        "title": "MTOP: A Comprehensive Multilingual Task-Oriented Semantic Parsing Benchmark",
        "url": "https://aclanthology.org/2021.eacl-main.257/",
        "applied_principle": "Keep official intent accuracy distinct from product execution readiness.",
    },
    {
        "title": "Selective Classification for Deep Neural Networks",
        "url": "https://papers.neurips.cc/paper/7073-selective-classification-for-deep-neural-networks",
        "applied_principle": "Prefer abstention when accepting a prediction would exceed the selected risk boundary.",
    },
    {
        "title": "Conformal Risk Control",
        "url": "https://proceedings.iclr.cc/paper_files/paper/2024/hash/f3549ef9b5ff520a7e41ff3cc306ab2b-Abstract-Conference.html",
        "applied_principle": "Measure risk and coverage separately instead of treating forced coverage as quality.",
    },
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _selected_reply(reply: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": reply.get("type"),
        "kind": reply.get("kind"),
        "intent_operations": list(reply.get("intentOperations") or []),
        "effect_operations": list(reply.get("effectOperations") or []),
        "missing": list(reply.get("missing") or []),
    }


def _product_exact(adjudication: dict[str, str], reply: dict[str, Any]) -> bool:
    expected_outcome = adjudication["product_outcome"]
    expected_operation = adjudication["product_operation"]
    if expected_outcome == "conversation":
        return (
            reply.get("kind") == "conversation"
            and not reply.get("intentOperations")
            and not reply.get("effectOperations")
        )
    if expected_outcome == "clarify":
        return (
            reply.get("kind") == "clarify"
            and expected_operation in list(reply.get("intentOperations") or [])
            and not reply.get("effectOperations")
        )
    return (
        reply.get("kind") in {"action", "plan"}
        and list(reply.get("intentOperations") or []) == [expected_operation]
        and list(reply.get("effectOperations") or []) == [expected_operation]
    )


def _downstream_ready(
    adjudication: dict[str, str],
    turn: dict[str, Any],
    downstream: dict[str, Any] | None,
) -> bool:
    if adjudication["product_outcome"] in {"conversation", "clarify"}:
        return _product_exact(adjudication, turn)
    if not _product_exact(adjudication, turn) or downstream is None:
        return False
    expected = adjudication["product_operation"]
    if turn.get("kind") == "action":
        return (
            downstream.get("type") == "arguments.result"
            and downstream.get("ok") is True
            and isinstance(downstream.get("arguments"), dict)
        )
    steps = downstream.get("steps")
    return (
        downstream.get("type") == "plan.result"
        and downstream.get("kind") == "plan"
        and isinstance(steps, list)
        and any(
            isinstance(step, dict)
            and step.get("operation") == expected
            and (
                isinstance(step.get("arguments"), dict)
                or (
                    step.get("argumentsMode") == "after_dependencies"
                    and isinstance(step.get("dependsOn"), list)
                    and bool(step["dependsOn"])
                )
            )
            for step in steps
        )
    )


def run(*, consensus_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite report: {output}")
    development, manifest, development_identity = mtop._load_development(
        mtop.DEVELOPMENT_CORPUS,
        mtop.MANIFEST,
    )
    by_id = {str(row["source_id"]): row for row in development}
    consensus = json.loads(consensus_path.read_text(encoding="utf-8"))
    residuals = [
        row
        for row in consensus["records"]
        if row["in_r4"] and not row["final_correct"]
    ]
    residual_ids = {str(row["source_id"]) for row in residuals}
    if residual_ids != set(ADJUDICATIONS):
        raise RuntimeError("R4 residual identities escaped the prereviewed audit set")
    if any(source_id not in by_id for source_id in residual_ids):
        raise RuntimeError("R4 residual is absent from opened development")

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
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    probed: dict[str, dict[str, Any]] = {}
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("mind sidecar did not publish hello")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "mtop-r4-residual-audit-catalog",
                "capabilities": capabilities,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("mind sidecar rejected the authenticated catalog")
        client.request(
            {
                "type": "turn.decide",
                "id": "mtop-r4-residual-audit-warmup",
                "text": "hola, responde brevemente",
                "history": [],
            },
            limits["turn.decide"],
        )
        for index, residual in enumerate(residuals):
            source_id = str(residual["source_id"])
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": f"mtop-r4-residual-audit-{index}",
                    "text": str(by_id[source_id]["text"]),
                    "history": [],
                },
                limits["turn.decide"],
            )
            turn_seconds = time.perf_counter() - started
            adjudication = ADJUDICATIONS[source_id]
            turn_exact = _product_exact(adjudication, reply)
            downstream: dict[str, Any] | None = None
            if turn_exact and adjudication["product_outcome"] == "action":
                if reply.get("kind") == "action":
                    downstream = client.request(
                        {
                            "type": "arguments",
                            "id": f"mtop-r4-residual-audit-arguments-{index}",
                            "operation": adjudication["product_operation"],
                            "text": str(by_id[source_id]["text"]),
                        },
                        limits["arguments"],
                    )
                elif reply.get("kind") == "plan":
                    downstream = client.request(
                        {
                            "type": "plan",
                            "id": f"mtop-r4-residual-audit-plan-{index}",
                            "text": str(by_id[source_id]["text"]),
                            "history": [],
                            "expectedOperations": [
                                adjudication["product_operation"]
                            ],
                        },
                        60.0,
                    )
            probed[source_id] = {
                "turn_seconds": round(turn_seconds, 6),
                "total_seconds": round(time.perf_counter() - started, 6),
                "reply": _selected_reply(reply),
                "turn_exact": turn_exact,
                "downstream": downstream,
                "ready_exact": _downstream_ready(
                    adjudication,
                    reply,
                    downstream,
                ),
            }
    finally:
        client.close(
            graceful_message={
                "type": "shutdown",
                "id": "mtop-r4-residual-audit-shutdown",
            },
            timeout=limits["shutdown"],
        )

    records = []
    adjusted_residual_exact = 0
    product_turn_exact = 0
    product_ready_exact = 0
    for residual in residuals:
        source_id = str(residual["source_id"])
        adjudication = ADJUDICATIONS[source_id]
        selector_exact = residual["chosen"] == adjudication["product_operation"]
        adjusted_residual_exact += int(selector_exact)
        product_turn_exact += int(probed[source_id]["turn_exact"])
        product_ready_exact += int(probed[source_id]["ready_exact"])
        row = by_id[source_id]
        records.append(
            {
                "source_id": source_id,
                "locale": row["locale"],
                "text": row["text"],
                "semantic": row["semantic"],
                "projection": row["projection"],
                "official_expected_operation": residual["expected"],
                "consensus_chosen_operation": residual["chosen"],
                "product_adjudication": adjudication,
                "adjusted_selector_exact": selector_exact,
                "production_probe": probed[source_id],
            }
        )

    r4_cases = int(consensus["r4_subset"]["cases"])
    official_correct = int(consensus["r4_subset"]["final_correct"])
    adjusted_correct = official_correct + adjusted_residual_exact
    result = {
        "schema": "baxy.mtop-r4-residual-adjudication.development.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "opened_mtop_development_r4_only",
        "authority": "turn_decision_only_no_core_plan_or_provider",
        "effects_executed": 0,
        "blind_reserve_opened": False,
        "policy": {
            "official_labels_preserved": True,
            "execution_readiness_is_separate": True,
            "standalone_text_must_ground_effect_authority": True,
            "unsupported_or_context_only_effects_abstain": True,
        },
        "primary_references": PRIMARY_REFERENCES,
        "sources": {
            "consensus": {
                "path": str(consensus_path.relative_to(REPO)),
                "sha256": _sha256(consensus_path),
            },
            "development": {
                "path": str(mtop.DEVELOPMENT_CORPUS),
                "sha256": _sha256(mtop.DEVELOPMENT_CORPUS),
                "identity": {
                    "corpus_sha256": development_identity.corpus.sha256,
                    "manifest_sha256": development_identity.manifest.sha256,
                    "map_sha256": manifest["source"]["map_sha256"],
                },
            },
            "runtime": public_runtime_identity(runtime),
        },
        "summary": {
            "r4_cases": r4_cases,
            "official_consensus_correct": official_correct,
            "official_consensus_accuracy": round(official_correct / r4_cases, 6),
            "residual_cases": len(records),
            "representability": {
                category: sum(
                    record["product_adjudication"]["representability"] == category
                    for record in records
                )
                for category in sorted(
                    {
                        record["product_adjudication"]["representability"]
                        for record in records
                    }
                )
            },
            "adjusted_selector_correct": adjusted_correct,
            "adjusted_selector_accuracy": round(adjusted_correct / r4_cases, 6),
            "production_residual_turn_exact": product_turn_exact,
            "production_residual_turn_accuracy": round(
                product_turn_exact / len(records),
                6,
            ),
            "production_residual_ready_exact": product_ready_exact,
            "production_residual_ready_accuracy": round(
                product_ready_exact / len(records),
                6,
            ),
        },
        "records": records,
    }
    write_json_atomic(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--consensus", type=Path, default=CONSENSUS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = run(consensus_path=args.consensus, output=args.output)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
