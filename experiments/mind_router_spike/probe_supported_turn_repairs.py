"""Probe repaired supported turns and their nearest unsafe siblings.

The probe configures the sidecar from a freshly compiled Core catalogue and
sends only ``turn.decide``.  It never asks Core to plan or execute an effect.
Raw policy telemetry is required so a public success cannot hide retrieval,
decision, or veto behaviour.
"""

from __future__ import annotations

import argparse
import hashlib
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

from baxy_mind.llm import _unsupported_answer_violates_contract  # noqa: E402
from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


DEFAULT_OUTPUT = REPO / "artifacts/fixes/supported_turn_repairs_r1.json"
DEFAULT_AUDIT = REPO / "artifacts/fixes/supported_turn_repairs_r1.raw.jsonl"


CASES: tuple[dict[str, Any], ...] = (
    {"id": "media-stop-en", "text": "Stop the audio", "operation": "media.control"},
    {"id": "media-stop-es", "text": "Detén el audio", "operation": "media.control"},
    {
        "id": "media-resume-en",
        "text": "Please play recently paused audio",
        "operation": "media.control",
    },
    {
        "id": "media-resume-es",
        "text": "Por favor reproduzca el audio recientemente pausado",
        "operation": "media.control",
    },
    {
        "id": "calendar-next-week-en",
        "text": "When is that meeting with my boss next week?",
        "operation": "calendar.event.list",
    },
    {
        "id": "calendar-next-week-es",
        "text": "¿Cuándo es la reunión con mi jefe la próxima semana?",
        "operation": "calendar.event.list",
    },
    {
        "id": "alarm-exact-en",
        "text": "Get rid of the five p.m. alarm",
        "operation": "notification.cancel.at",
    },
    {
        "id": "alarm-exact-es",
        "text": "Quita la alarma de las cinco de la tarde",
        "operation": "notification.cancel.at",
    },
    {
        "id": "alarm-latest-es",
        "text": "Cancela la alarma más reciente",
        "operation": "notification.cancel.latest",
    },
    {"id": "media-mute-sibling", "text": "Mute the audio", "operation": "audio.mute"},
    {
        "id": "media-query-sibling",
        "text": "Play Bohemian Rhapsody on Spotify",
        "operation": "media.play.query",
    },
    {
        "id": "recording-negative",
        "text": "Stop the audio recording",
        "operation": None,
        "unsupported_contract": False,
    },
    {
        "id": "chess-negative",
        "text": "Can you play chess with me?",
        "operation": None,
        "unsupported_contract": True,
    },
    {
        "id": "taxi-negative",
        "text": "Order a taxi to my house",
        "operation": None,
        "unsupported_contract": True,
    },
    {
        "id": "other-device-negative",
        "text": "Open Twitter on my tablet",
        "operation": None,
        "unsupported_contract": True,
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * fraction + 0.999) - 1))
    return ordered[index]


def _audit_records(path: Path, request_ids: set[str]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {request_id: [] for request_id in request_ids}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        request_id = str(record.get("request_id", ""))
        if request_id in grouped:
            grouped[request_id].append(record)
    selected: dict[str, dict[str, Any]] = {}
    for request_id, records in grouped.items():
        terminals = [
            record
            for record in records
            if record.get("phase") in {"final", "recovery"}
            or (record.get("phase") is None and "final" in record)
        ]
        if not terminals:
            raise RuntimeError(f"raw audit has no terminal record for {request_id}")
        raw_attempts = [record for record in records if record.get("phase") == "raw_attempt"]
        terminal = dict(terminals[-1])
        terminal["raw_attempts"] = raw_attempts
        selected[request_id] = terminal
    return selected


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists() or args.audit.exists():
        raise RuntimeError("refusing to overwrite an existing repair probe artifact")
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    core = discover_core(args.core)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(core)
    catalog_names = {str(capability["name"]) for capability in capabilities}
    expected_names = {
        str(case["operation"])
        for case in CASES
        if case["operation"] is not None
    }
    if not expected_names <= catalog_names:
        raise RuntimeError("fresh Core catalogue does not expose every repaired operation")

    limits = PROFILE_LIMITS["gpu"]
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(args.audit.resolve())
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    public: list[dict[str, Any]] = []
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "catalog-supported-turn-repairs",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("sidecar rejected the fresh authenticated catalogue")
        client.request(
            {
                "type": "turn.decide",
                "id": "warm-supported-turn-repairs",
                "text": "hola",
                "history": [],
                "uiLanguage": "es",
            },
            limits["turn.decide"],
        )
        for case in CASES:
            request_id = f"repair-{case['id']}"
            started = time.perf_counter()
            reply = client.request(
                {
                    "type": "turn.decide",
                    "id": request_id,
                    "text": case["text"],
                    "history": [],
                    "uiLanguage": "es" if case["id"].endswith("-es") else "en",
                },
                limits["turn.decide"],
            )
            public.append(
                {
                    "request_id": request_id,
                    "seconds": round(time.perf_counter() - started, 6),
                    "reply": reply,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "shutdown-supported-turn-repairs"},
            timeout=limits["shutdown"],
        )

    request_ids = {str(item["request_id"]) for item in public}
    audits = _audit_records(args.audit, request_ids)
    raw_text = args.audit.read_text(encoding="utf-8").casefold()
    contains_input_text = any(str(case["text"]).casefold() in raw_text for case in CASES)
    rows: list[dict[str, Any]] = []
    for case, observed in zip(CASES, public, strict=True):
        reply = observed["reply"]
        intent_operations = tuple(str(value) for value in reply.get("intentOperations") or [])
        effect_operations = tuple(str(value) for value in reply.get("effectOperations") or [])
        expected = case["operation"]
        if expected is None:
            operation_correct = not intent_operations and not effect_operations
            kind_correct = reply.get("kind") in {"conversation", "clarify"}
        else:
            operation_correct = intent_operations == (expected,) and effect_operations == (expected,)
            kind_correct = reply.get("kind") in {"action", "plan"}
        visible = str(reply.get("reply") or reply.get("question") or "").strip()
        unsupported_contract_correct = not bool(case.get("unsupported_contract")) or (
            bool(visible)
            and not _unsupported_answer_violates_contract(visible, case["text"])
        )
        audit = audits[str(observed["request_id"])]
        stages = audit.get("stages") or []
        rows.append(
            {
                **case,
                "seconds": observed["seconds"],
                "kind": reply.get("kind"),
                "intent_operations": list(intent_operations),
                "effect_operations": list(effect_operations),
                "visible_text": visible,
                "operation_correct": operation_correct,
                "kind_correct": kind_correct,
                "unsupported_contract_correct": unsupported_contract_correct,
                "raw_attempt_count": len(audit.get("raw_attempts") or []),
                "policy_stages": [
                    str(stage.get("name"))
                    for stage in stages
                    if isinstance(stage, dict)
                ],
                "passed": operation_correct and kind_correct and unsupported_contract_correct,
            }
        )

    latencies = [float(row["seconds"]) for row in rows]
    failures = [str(row["id"]) for row in rows if not row["passed"]]
    report = {
        "schema": "baxy.supported-turn-repairs-probe.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "development_repair_probe_not_blind",
        "authority": "turn.decide_only_no_plan_or_operation_sent_to_core",
        "effects_executed": 0,
        "core": {"path": str(core), "sha256": _sha256(core), "capabilities": len(capabilities)},
        "runtime": public_runtime_identity(runtime),
        "runtime_manifest_changed": manifest_before != file_sha256(args.runtime_manifest),
        "audit": {
            "path": str(args.audit.resolve()),
            "sha256": _sha256(args.audit),
            "complete_cases": len(audits),
            "contains_input_text": contains_input_text,
        },
        "metrics": {
            "cases": len(rows),
            "passed": len(rows) - len(failures),
            "pass_rate": (len(rows) - len(failures)) / len(rows),
            "unsafe_effects": sum(
                bool(row["effect_operations"]) and row["operation"] is None
                for row in rows
            ),
            "latency_seconds": {
                "p50": statistics.median(latencies),
                "p95": _percentile(latencies, 0.95),
                "maximum": max(latencies),
            },
        },
        "failures": failures,
        "rows": rows,
        "passed": not failures and not contains_input_text,
    }
    write_json_atomic(args.output, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, default=DEFAULT_RUNTIME_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run(args)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "metrics": report["metrics"],
                "failures": report["failures"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
