"""Open the sealed veto-reach V8 population exactly once, without dispatch."""

from __future__ import annotations

import collections
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
for import_root in (REPO, REPO / "src"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.baxy_runtime_config import (
    DEFAULT_RUNTIME_MANIFEST,
    resolve_runtime,
)
from scripts.measure_mind_budget import (
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
)

from experiments.mind_router_spike import build_veto_reach_v8 as campaign
from experiments.mind_router_spike import score_veto_reach_v8 as scoring


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_exclusive(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _write_jsonl_exclusive(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        for row in rows:
            stream.write(
                (
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")
            )
        stream.flush()
        os.fsync(stream.fileno())


def refuse_reuse() -> None:
    if any(
        path.exists()
        for path in (
            campaign.OUTPUT,
            campaign.TELEMETRY,
            campaign.CONSUMED,
            campaign.TURN_AUDIT,
            campaign.RAW_REPLY_AUDIT,
        )
    ):
        raise RuntimeError("veto-reach V8 has already been opened")


def _load_preregistration() -> dict[str, Any]:
    manifest = json.loads(campaign.PREREGISTRATION.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in campaign.CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if (
        manifest.get("schema") != "baxy.veto-reach.preregistration.v8"
        or manifest.get("blind_holdout") is not True
        or manifest.get("measurement_status") != "unopened"
        or manifest.get("reuse_prohibited") is not True
        or manifest.get("retry_prohibited") is not True
        or manifest.get("population", {}).get("corpus_sha256")
        != _sha256(campaign.CORPUS)
        or manifest.get("population", {}).get("population_contract_sha256")
        != campaign.population_contract_sha256(rows)
        or manifest.get("thresholds") != scoring.DEFAULT_THRESHOLDS
        or manifest.get("prediction")
        != {
            "outcome": "fail",
            "statement": (
                "V8 will fail one or more preregistered binary thresholds."
            ),
        }
    ):
        raise RuntimeError("veto-reach V8 preregistration changed")
    identities = campaign.collect_identities()
    if manifest.get("identities") != identities:
        raise RuntimeError("veto-reach V8 frozen program identity changed")
    return manifest


def _read_turn_audits(expected_ids: set[str]) -> dict[str, dict[str, Any]]:
    records = [
        json.loads(line)
        for line in campaign.TURN_AUDIT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        request_id = str(record.get("request_id") or "")
        if request_id in expected_ids:
            grouped[request_id].append(record)
    if set(grouped) != expected_ids:
        raise RuntimeError(
            f"veto-reach V8 audit incomplete: {len(grouped)}/{len(expected_ids)}"
        )
    selected: dict[str, dict[str, Any]] = {}
    for request_id, attempts in grouped.items():
        terminal = [
            record
            for record in attempts
            if record.get("phase") in {"final", "recovery"}
        ]
        raw = [record for record in attempts if record.get("phase") == "raw_attempt"]
        if not terminal:
            raise RuntimeError(f"veto-reach V8 audit stages missing: {request_id}")
        chosen = dict(terminal[-1])
        raw_record = raw[-1] if raw else chosen
        chosen["candidate_operations"] = list(
            raw_record.get("candidate_operations") or []
        )
        chosen["raw_decision"] = raw_record.get("raw_decision")
        chosen["attempt_records"] = attempts
        selected[request_id] = chosen
    return selected


def _read_raw_replies() -> dict[str, list[str]]:
    if not campaign.RAW_REPLY_AUDIT.is_file():
        return {}
    grouped: dict[str, list[str]] = collections.defaultdict(list)
    for line in campaign.RAW_REPLY_AUDIT.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        grouped[str(record.get("request_sha256") or "")].append(
            str(record.get("raw_reply") or "")
        )
    return dict(grouped)


def _raw_proposal(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "available": False,
            "effect_operations": [],
            "effect_verification": "not_applicable",
        }
    return {
        "available": True,
        "mode": value.get("mode"),
        "operation": value.get("operation"),
        "effect_operations": list(value.get("effect_operations") or []),
        "effect_verification": value.get("effect_verification"),
    }


def _measurement_environment(runtime: Any) -> dict[str, str]:
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=PROFILE_LIMITS["gpu"]["llm_http"],
    )
    for name in (
        "BAXY_MIND_TURN_AUDIT_PATH",
        "BAXY_MIND_RAW_REPLY_AUDIT_PATH",
        "BAXY_MIND_MESSAGE_COMPOSE_AUDIT_PATH",
        "BAXY_MIND_INVALID_REPLY_DIR",
    ):
        environment.pop(name, None)
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(campaign.TURN_AUDIT.resolve())
    environment["BAXY_MIND_RAW_REPLY_AUDIT_PATH"] = str(
        campaign.RAW_REPLY_AUDIT.resolve()
    )
    environment["BAXY_VOICE_STREAMING_STT"] = "off"
    return environment


def measure() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    preregistration = _load_preregistration()
    rows = [
        json.loads(line)
        for line in campaign.CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities, applications, games = current_core_catalog_snapshot(
        discover_core(None)
    )
    environment = _measurement_environment(runtime)
    limits = PROFILE_LIMITS["gpu"]
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=campaign.REPO,
    )
    replies: dict[str, dict[str, Any]] = {}
    durations: dict[str, float] = {}
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("veto-reach V8 sidecar did not greet")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "v8-catalog",
                "capabilities": capabilities,
                "applicationCatalog": applications,
                "gameCatalog": games,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("veto-reach V8 catalogue rejected")
        for row in rows:
            case_id = str(row["case_id"])
            request_id = f"v8-{case_id}"
            started = time.perf_counter()
            replies[case_id] = client.request(
                {
                    "type": "turn.decide",
                    "id": request_id,
                    "text": row["text"],
                    "history": [],
                    "uiLanguage": (
                        "en" if row["language"] == "en" else "es"
                    ),
                },
                limits["turn.decide"],
            )
            durations[case_id] = round(time.perf_counter() - started, 6)
    finally:
        client.close(graceful_message=None, timeout=15.0)
    expected_ids = {f"v8-{row['case_id']}" for row in rows}
    audits = _read_turn_audits(expected_ids)
    raw_replies = _read_raw_replies()
    telemetry: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row["case_id"])
        reply = replies[case_id]
        audit = audits[f"v8-{case_id}"]
        request_hash = hashlib.sha256(str(row["text"]).encode("utf-8")).hexdigest()
        telemetry.append(
            {
                **row,
                "request_text": row["text"],
                "seconds": durations[case_id],
                "candidate_operations": list(
                    audit.get("candidate_operations") or []
                ),
                "raw_proposal": _raw_proposal(audit.get("raw_decision")),
                "stages": list(audit.get("stages") or []),
                "kind": reply.get("kind"),
                "operation": reply.get("operation"),
                "intent_operations": list(reply.get("intentOperations") or []),
                "effect_operations": list(reply.get("effectOperations") or []),
                "reply_text": str(reply.get("reply") or ""),
                "question": str(reply.get("question") or ""),
                "raw_visible_proposals": raw_replies.get(request_hash, []),
                "provider_dispatch_enabled": False,
                "external_effect_executed": False,
            }
        )
    return telemetry, preregistration


def _consumption_receipt(
    *,
    result: dict[str, Any],
    preregistration: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "baxy.veto-reach-consumption.v8",
        "measurement_status": "consumed",
        "opened_exactly_once": True,
        "retry_allowed": False,
        "status": result["status"],
        "verdict": result["verdict"],
        "failed_thresholds": result.get("failed_thresholds", []),
        "effects_executed": 0,
        "providers_enabled": False,
        "voice_stt_wake_exercised": False,
        "hashes": {
            "corpus_sha256": _sha256(campaign.CORPUS),
            "preregistration_sha256": _sha256(campaign.PREREGISTRATION),
            "result_sha256": _sha256(campaign.OUTPUT),
            "telemetry_sha256": _sha256(campaign.TELEMETRY),
            "turn_audit_sha256": _sha256(campaign.TURN_AUDIT),
            "raw_reply_audit_sha256": (
                _sha256(campaign.RAW_REPLY_AUDIT)
                if campaign.RAW_REPLY_AUDIT.is_file()
                else None
            ),
            "program_sha256": preregistration["identities"]["program_sha256"],
            "model_sha256": preregistration["identities"]["model_sha256"],
            "catalog_sha256": preregistration["identities"]["catalog_sha256"],
            "tree_sha256": preregistration["identities"]["tree_sha256"],
        },
    }


def run_once() -> dict[str, Any]:
    refuse_reuse()
    telemetry, preregistration = measure()
    result = scoring.build_result(
        telemetry,
        thresholds=preregistration["thresholds"],
        identities=preregistration["identities"],
        external_effects_executed=0,
    )
    _write_jsonl_exclusive(campaign.TELEMETRY, telemetry)
    _write_exclusive(campaign.OUTPUT, result)
    receipt = _consumption_receipt(
        result=result,
        preregistration=preregistration,
    )
    _write_exclusive(campaign.CONSUMED, receipt)
    return result


def main() -> int:
    try:
        result = run_once()
    except Exception as error:
        if campaign.PREREGISTRATION.is_file() and not campaign.OUTPUT.exists():
            preregistration = json.loads(
                campaign.PREREGISTRATION.read_text(encoding="utf-8")
            )
            failure = {
                "schema": "baxy.veto-reach-result.v8",
                "measurement_status": "consumed",
                "status": "failed",
                "verdict": "fail",
                "failed_thresholds": ["measurement_completed"],
                "failure_causes": {
                    "measurement_error": type(error).__name__,
                    "stable_message": str(error)[:256],
                },
                "identities": preregistration.get("identities", {}),
            }
            if not campaign.TELEMETRY.exists():
                _write_jsonl_exclusive(campaign.TELEMETRY, [])
            _write_exclusive(campaign.OUTPUT, failure)
            receipt = _consumption_receipt(
                result=failure,
                preregistration=preregistration,
            )
            _write_exclusive(campaign.CONSUMED, receipt)
        print(f"veto-reach V8 failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": result["status"],
                "failed_thresholds": result["failed_thresholds"],
                "rows": result["scoring"]["counts"]["rows"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
