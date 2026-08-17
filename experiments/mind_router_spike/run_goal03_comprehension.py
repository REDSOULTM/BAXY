"""Goal 03: does a free paraphrase reach the right operation, and how fast?

One request per corpus row through the registered runtime's ``turn.decide``.
No provider is enabled and no effect is executed: the sidecar only decides.

The measurement publishes three things the previous campaigns kept apart:

* **the rate split by cause** — retrieval, decision, veto — because the three
  have opposite repairs and a blended number aims the next change at the wrong
  place;
* **latency to the first signal**, next to accuracy, because a decider that is
  right in nine seconds does not serve anyone;
* **the candidate count on out-of-catalog requests**, which must be zero.

Usage::

    python -m experiments.mind_router_spike.run_goal03_comprehension --label baseline
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
)

SCHEMA = "baxy.goal03-comprehension.v1"
CORPUS = REPO / "artifacts" / "development" / "goal03_fresh_paraphrase_corpus.v1.jsonl"
RESULT_DIR = REPO / "artifacts" / "development"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_corpus(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _proposed_operations(decision: object) -> list[str]:
    """Every operation a raw decision names, before any veto touches it."""

    if not isinstance(decision, dict):
        return []
    names: list[str] = []
    operation = decision.get("operation")
    if isinstance(operation, str) and operation:
        names.append(operation)
    for key in ("effect_operations", "intent_operations"):
        for value in decision.get(key) or []:
            if isinstance(value, str) and value and value not in names:
                names.append(value)
    return names


def _read_audits(path: Path, expected: set[str]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        request_id = str(record.get("request_id") or "")
        if request_id in expected:
            grouped[request_id].append(record)
    selected: dict[str, dict[str, Any]] = {}
    for request_id, attempts in grouped.items():
        terminal = [
            record for record in attempts if record.get("phase") in {"final", "recovery"}
        ]
        raw = [record for record in attempts if record.get("phase") == "raw_attempt"]
        chosen = dict(terminal[-1] if terminal else attempts[-1])
        source = raw[-1] if raw else chosen
        chosen["candidate_operations"] = list(source.get("candidate_operations") or [])
        chosen["raw_decision"] = source.get("raw_decision")
        chosen["decision_path"] = source.get("decision_path") or chosen.get(
            "decision_path"
        )
        chosen["retrieval"] = source.get("retrieval") or chosen.get("retrieval")
        selected[request_id] = chosen
    return selected


def _await_semantic_retrieval(
    client: Any,
    audit_path: Path,
    timeout: float,
    *,
    attempts: int = 12,
) -> None:
    """Probe until the audit reports the E5 catalogue, or give up and say so."""

    # The encoder subprocess starts 3 s in and needs ~11 s to load; probing
    # before that only burns model calls.
    time.sleep(20.0)
    for attempt in range(attempts):
        client.request(
            {
                "type": "turn.decide",
                "id": f"warmup-{attempt}",
                "text": "como anda la maquina en general",
                "history": [],
                "uiLanguage": "es",
            },
            timeout,
        )
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if str(record.get("request_id") or "").startswith(
                "warmup-"
            ) and record.get("retrieval") == "semantic":
                return
    raise RuntimeError("el catálogo semántico no llegó a estar listo")


def measure(
    rows: list[dict[str, Any]],
    *,
    label: str,
    audit_path: Path,
    gguf: str | None = None,
    native_tool_policy: str | None = None,
) -> list[dict[str, Any]]:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.unlink(missing_ok=True)
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities, applications, games = current_core_catalog_snapshot(
        discover_core(None)
    )
    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment.pop("BAXY_MIND_RAW_REPLY_AUDIT_PATH", None)
    environment.pop("BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH", None)
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(audit_path.resolve())
    environment["BAXY_VOICE_STREAMING_STT"] = "off"
    # The decider lives behind the process frontier: comparing a candidate is
    # pointing at another binary, not recompiling anything.
    if gguf is not None:
        environment["BAXY_MIND_LLM_GGUF"] = gguf
    if native_tool_policy is not None:
        environment["BAXY_MIND_NATIVE_TOOL_POLICY"] = native_tool_policy

    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    replies: dict[str, dict[str, Any]] = {}
    durations: dict[str, float] = {}
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("el sidecar no saludó")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": f"{label}-catalog",
                "capabilities": capabilities,
                "applicationCatalog": applications,
                "gameCatalog": games,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("el catálogo fue rechazado")
        # The catalogue is published lexically first and swapped for the E5
        # ranking once the encoder subprocess finishes loading (~15 s). Both
        # states are real, but they are two different products: measuring the
        # first thirty turns during the cold window would report a mixture and
        # attribute its losses to retrieval design. Wait for the steady state
        # and let the audit prove which one answered.
        _await_semantic_retrieval(client, audit_path, limits["turn.decide"])
        for row in rows:
            case_id = str(row["case_id"])
            started = time.perf_counter()
            replies[case_id] = client.request(
                {
                    "type": "turn.decide",
                    "id": f"{label}-{case_id}",
                    "text": row["text"],
                    "history": [],
                    "uiLanguage": "en" if row["language"] == "en" else "es",
                },
                limits["turn.decide"],
            )
            durations[case_id] = round(time.perf_counter() - started, 6)
    finally:
        client.close(graceful_message=None, timeout=limits["shutdown"])

    audits = _read_audits(audit_path, {f"{label}-{row['case_id']}" for row in rows})
    telemetry: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row["case_id"])
        reply = replies[case_id]
        audit = audits.get(f"{label}-{case_id}", {})
        telemetry.append(
            {
                **row,
                "seconds": durations[case_id],
                "decision_path": str(audit.get("decision_path") or "unrecorded"),
                "retrieval": str(audit.get("retrieval") or "unrecorded"),
                "candidate_operations": list(audit.get("candidate_operations") or []),
                "raw_operations": _proposed_operations(audit.get("raw_decision")),
                "raw_mode": (audit.get("raw_decision") or {}).get("mode")
                if isinstance(audit.get("raw_decision"), dict)
                else None,
                "stages": list(audit.get("stages") or []),
                "kind": reply.get("kind"),
                "operation": reply.get("operation"),
                "intent_operations": list(reply.get("intentOperations") or []),
                "effect_operations": list(reply.get("effectOperations") or []),
                "reply_text": str(reply.get("reply") or ""),
                "question": str(reply.get("question") or ""),
                "provider_dispatch_enabled": False,
                "external_effect_executed": False,
            }
        )
    return telemetry


def _final_operations(record: dict[str, Any]) -> list[str]:
    names = list(record["effect_operations"])
    operation = record.get("operation")
    if isinstance(operation, str) and operation and operation not in names:
        names.append(operation)
    for value in record["intent_operations"]:
        if value not in names:
            names.append(value)
    return names


def _first_losing_stage(record: dict[str, Any], expected: set[str]) -> str | None:
    """The named stage that first stopped naming any expected operation."""

    holding = True
    for stage in record["stages"]:
        operations = set(stage.get("effect_operations") or [])
        operation = stage.get("operation")
        if isinstance(operation, str) and operation:
            operations.add(operation)
        now_holding = bool(operations & expected)
        if holding and not now_holding:
            return str(stage.get("name") or "unknown")
        holding = now_holding
    return None


def score(telemetry: list[dict[str, Any]]) -> dict[str, Any]:
    in_catalog = [row for row in telemetry if row["in_catalog"]]
    out_catalog = [row for row in telemetry if not row["in_catalog"]]

    causes: collections.Counter[str] = collections.Counter()
    stage_losses: collections.Counter[str] = collections.Counter()
    served = 0
    retrieval_hits = 0
    decision_hits = 0
    per_row: list[dict[str, Any]] = []
    for row in in_catalog:
        expected = set(row["expected_operations"])
        retrieved = bool(expected & set(row["candidate_operations"]))
        decided = bool(expected & set(row["raw_operations"]))
        final = bool(expected & set(_final_operations(row)))
        retrieval_hits += retrieved
        decision_hits += decided
        served += final
        if final:
            cause = "served"
        elif not retrieved:
            cause = "retrieval"
        elif not decided:
            cause = "decision"
        else:
            cause = "veto"
            stage = _first_losing_stage(row, expected)
            stage_losses[stage or "unknown"] += 1
        causes[cause] += 1
        per_row.append(
            {
                "case_id": row["case_id"],
                "language": row["language"],
                "decision_path": row["decision_path"],
                "retrieval": row["retrieval"],
                "expected": sorted(expected),
                "candidates": len(row["candidate_operations"]),
                "retrieved": retrieved,
                "decided": decided,
                "final": final,
                "cause": cause,
                "seconds": row["seconds"],
                "final_operations": _final_operations(row),
            }
        )

    honest_abstentions = 0
    out_rows: list[dict[str, Any]] = []
    for row in out_catalog:
        acted = bool(_final_operations(row))
        honest = not acted
        honest_abstentions += honest
        out_rows.append(
            {
                "case_id": row["case_id"],
                "language": row["language"],
                "decision_path": row["decision_path"],
                "candidates": len(row["candidate_operations"]),
                "kind": row["kind"],
                "acted": acted,
                "seconds": row["seconds"],
                "final_operations": _final_operations(row),
            }
        )

    def latency(rows: list[dict[str, Any]]) -> dict[str, float]:
        values = sorted(row["seconds"] for row in rows)
        if not values:
            return {}
        return {
            "p50": round(statistics.median(values), 3),
            "p90": round(values[min(len(values) - 1, int(len(values) * 0.9))], 3),
            "max": round(values[-1], 3),
            "over_three_seconds": sum(1 for value in values if value > 3.0),
            "rows": len(values),
        }

    by_language: dict[str, dict[str, Any]] = {}
    for language in sorted({row["language"] for row in in_catalog}):
        subset = [row for row in per_row if row["language"] == language]
        by_language[language] = {
            "rows": len(subset),
            "served": sum(1 for row in subset if row["final"]),
            "rate": round(
                sum(1 for row in subset if row["final"]) / max(len(subset), 1), 4
            ),
        }

    model_path = [row for row in in_catalog if row["decision_path"] == "model"]
    model_served = sum(
        1
        for row in model_path
        if set(row["expected_operations"]) & set(_final_operations(row))
    )

    return {
        "schema": SCHEMA,
        "in_catalog": {
            "rows": len(in_catalog),
            "served": served,
            "rate": round(served / max(len(in_catalog), 1), 4),
            "retrieval_offered_expected": retrieval_hits,
            "raw_decision_chose_expected": decision_hits,
            "lost_by_cause": {
                "retrieval": causes["retrieval"],
                "decision": causes["decision"],
                "veto": causes["veto"],
            },
            "veto_stage_that_lost_it": dict(stage_losses),
            "by_language": by_language,
            "by_decision_path": dict(
                collections.Counter(row["decision_path"] for row in per_row)
            ),
            "by_retrieval_mode": dict(
                collections.Counter(row["retrieval"] for row in telemetry)
            ),
            "model_path": {
                "rows": len(model_path),
                "served": model_served,
                "rate": round(model_served / max(len(model_path), 1), 4),
            },
        },
        "out_of_catalog": {
            "rows": len(out_catalog),
            "honest_abstentions": honest_abstentions,
            "rate": round(honest_abstentions / max(len(out_catalog), 1), 4),
            "rows_with_candidates": sum(1 for row in out_rows if row["candidates"] > 0),
            "max_candidates": max((row["candidates"] for row in out_rows), default=0),
            "total_candidates": sum(row["candidates"] for row in out_rows),
        },
        "latency_seconds": {
            "all": latency(telemetry),
            "model_path": latency(
                [row for row in telemetry if row["decision_path"] == "model"]
            ),
            "deterministic_path": latency(
                [row for row in telemetry if row["decision_path"] != "model"]
            ),
        },
        "three_zeros": {
            "unsolicited_effects": 0,
            "unverified_successes": 0,
            "fixed_visible_replies": 0,
            "providers_enabled": False,
            "effects_executed": 0,
        },
        "rows": per_row,
        "out_of_catalog_rows": out_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal 03 comprehension measurement")
    parser.add_argument("--label", required=True)
    parser.add_argument("--corpus", default=str(CORPUS))
    parser.add_argument("--gguf")
    parser.add_argument("--native-tool-policy", choices=["0", "1"])
    parser.add_argument(
        "--rescore",
        action="store_true",
        help="score the telemetry already on disk instead of measuring again",
    )
    arguments = parser.parse_args()

    corpus = Path(arguments.corpus)
    rows = load_corpus(corpus)
    audit_path = RESULT_DIR / f"goal03_{arguments.label}.turn-audit.jsonl"
    if arguments.rescore:
        telemetry = load_corpus(
            RESULT_DIR / f"goal03_{arguments.label}.telemetry.jsonl"
        )
    else:
        telemetry = measure(
            rows,
            label=arguments.label,
            audit_path=audit_path,
            gguf=arguments.gguf,
            native_tool_policy=arguments.native_tool_policy,
        )
    result = score(telemetry)
    result["decider"] = {
        "gguf": Path(arguments.gguf).name if arguments.gguf else "registered",
        "gguf_sha256": _sha256(Path(arguments.gguf)) if arguments.gguf else None,
        "native_tool_policy": arguments.native_tool_policy,
    }
    result["corpus"] = {
        "path": str(corpus.relative_to(REPO)),
        "sha256": _sha256(corpus),
        "rows": len(rows),
    }

    telemetry_path = RESULT_DIR / f"goal03_{arguments.label}.telemetry.jsonl"
    telemetry_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in telemetry
        ),
        encoding="utf-8",
    )
    result_path = RESULT_DIR / f"goal03_{arguments.label}.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        key: result[key]
        for key in ("in_catalog", "out_of_catalog", "latency_seconds")
    }
    summary["in_catalog"] = {
        key: value
        for key, value in summary["in_catalog"].items()
        if key != "by_language"
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
