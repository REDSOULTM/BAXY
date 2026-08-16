"""Open R215 once through the current 174-operation local model path, no dispatch."""

from __future__ import annotations

import collections
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)  # noqa: E402
from scripts.measure_mind_budget import (
    PROFILE_LIMITS,
    JsonLineProcess,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
)  # noqa: E402

from experiments.mind_router_spike import (
    preregister_situated_cut_b_model_path_r220 as campaign,
)  # noqa: E402
from experiments.mind_router_spike import (
    score_situated_cut_b_model_path_r218 as scoring,
)  # noqa: E402


RESULT = REPO / "artifacts/audit/situated_cut_b_r215_model_path_r221.json"
TELEMETRY = REPO / "artifacts/audit/situated_cut_b_r215_model_path_r221.telemetry.jsonl"
TURN_AUDIT = (
    REPO / "artifacts/audit/situated_cut_b_r215_model_path_r221.turn-audit.jsonl"
)
RAW_REPLIES = (
    REPO / "artifacts/audit/situated_cut_b_r215_model_path_r221.raw-replies.jsonl"
)
RECEIPT = REPO / "artifacts/audit/situated_cut_b_r215_model_path_r221.consumed.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object, *, lines: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        if lines:
            for row in value:  # type: ignore[union-attr]
                handle.write(
                    (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n").encode(
                        "utf-8"
                    )
                )
        else:
            handle.write(
                (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            )


def _refuse_reuse() -> None:
    if any(
        path.exists() for path in (RESULT, TELEMETRY, TURN_AUDIT, RAW_REPLIES, RECEIPT)
    ):
        raise RuntimeError(
            "situated Cut B R215 model path R221 has already been opened"
        )


def _load() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    preregistration = json.loads(campaign.OUTPUT.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in campaign.CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    required = preregistration.get("identities", {})
    if (
        preregistration.get("schema")
        != "baxy.situated-cut-b.model-path.r220-preregistration.v1"
        or required.get("corpus_sha256") != sha256(campaign.CORPUS)
        or required.get("runner_sha256") != sha256(Path(__file__))
        or required.get("scorer_sha256") != sha256(campaign.SCORER)
        or len(rows) != 93
    ):
        raise RuntimeError("R220 preregistration identity changed")
    return preregistration, rows


def _environment(runtime: Any) -> dict[str, str]:
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
    environment["BAXY_MIND_TURN_AUDIT_PATH"] = str(TURN_AUDIT.resolve())
    environment["BAXY_MIND_RAW_REPLY_AUDIT_PATH"] = str(RAW_REPLIES.resolve())
    environment["BAXY_VOICE_STREAMING_STT"] = "off"
    return environment


def _audits(expected_ids: set[str]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for line in TURN_AUDIT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            grouped[str(row.get("request_id") or "")].append(row)
    if set(grouped) != expected_ids:
        raise RuntimeError(f"R221 audit incomplete: {len(grouped)}/{len(expected_ids)}")
    selected: dict[str, dict[str, Any]] = {}
    for request_id, records in grouped.items():
        raw = [row for row in records if row.get("phase") == "raw_attempt"]
        final = [row for row in records if row.get("phase") in {"final", "recovery"}]
        if not raw or not final:
            raise RuntimeError(f"R221 audit stages missing: {request_id}")
        audit = dict(final[-1])
        audit["candidate_operations"] = list(raw[-1].get("candidate_operations") or [])
        audit["raw_decision"] = raw[-1].get("raw_decision")
        selected[request_id] = audit
    return selected


def _raw_replies() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = collections.defaultdict(list)
    if RAW_REPLIES.is_file():
        for line in RAW_REPLIES.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                grouped[str(row.get("request_sha256") or "")].append(
                    str(row.get("raw_reply") or "")
                )
    return dict(grouped)


def _proposal(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"available": False, "effect_operations": []}
    return {
        "available": True,
        "mode": value.get("mode"),
        "operation": value.get("operation"),
        "effect_operations": list(value.get("effect_operations") or []),
        "effect_verification": value.get("effect_verification"),
    }


def measure() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    preregistration, rows = _load()
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    capabilities, applications, games = current_core_catalog_snapshot(
        discover_core(None)
    )
    snapshot = json.loads(campaign.SNAPSHOT.read_text(encoding="utf-8"))["catalogue"]
    encoded = json.dumps(
        capabilities, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if (
        len(capabilities) != 174
        or hashlib.sha256(encoded).hexdigest() != snapshot["capabilities_sha256"]
    ):
        raise RuntimeError(
            "current Core catalogue differs from R219 authenticated snapshot"
        )
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=_environment(runtime),
        cwd=REPO,
    )
    replies: dict[str, dict[str, Any]] = {}
    seconds: dict[str, float] = {}
    try:
        if (
            client.next_message(PROFILE_LIMITS["gpu"]["handshake"]).get("type")
            != "hello"
        ):
            raise RuntimeError("R221 sidecar did not greet")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "r221-catalog",
                "capabilities": capabilities,
                "applicationCatalog": applications,
                "gameCatalog": games,
            },
            PROFILE_LIMITS["gpu"]["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("R221 catalogue rejected")
        for row in rows:
            case_id = str(row["case_id"])
            started = time.perf_counter()
            replies[case_id] = client.request(
                {
                    "type": "turn.decide",
                    "id": f"r221-{case_id}",
                    "text": row["text"],
                    "history": [],
                    "uiLanguage": "en" if row["language"] == "en" else "es",
                },
                PROFILE_LIMITS["gpu"]["turn.decide"],
            )
            seconds[case_id] = round(time.perf_counter() - started, 6)
    finally:
        client.close(graceful_message=None, timeout=15.0)
    audits, raw_replies = (
        _audits({f"r221-{row['case_id']}" for row in rows}),
        _raw_replies(),
    )
    telemetry: list[dict[str, Any]] = []
    for row in rows:
        case_id = str(row["case_id"])
        reply, audit = replies[case_id], audits[f"r221-{case_id}"]
        request_hash = hashlib.sha256(str(row["text"]).encode("utf-8")).hexdigest()
        telemetry.append(
            {
                **row,
                "seconds": seconds[case_id],
                "candidate_operations": list(audit.get("candidate_operations") or []),
                "raw_proposal": _proposal(audit.get("raw_decision")),
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
    return telemetry, preregistration, public_runtime_identity(runtime)


def run_once() -> dict[str, Any]:
    _refuse_reuse()
    telemetry, preregistration, runtime = measure()
    result = scoring.build_result(telemetry, preregistration)
    result.update(
        {
            "execution": {
                "mind_sidecar_started": True,
                "providers_enabled": False,
                "effects_executed": 0,
                "opened_v9": False,
                "voice_stt_wake_exercised": False,
            },
            "runtime": runtime,
            "identities": preregistration["identities"],
        }
    )
    _write(TELEMETRY, telemetry, lines=True)
    _write(RESULT, result)
    _write(
        RECEIPT,
        {
            "schema": "baxy.situated-cut-b.model-path.r221-consumption.v1",
            "measurement_status": "consumed",
            "opened_exactly_once": True,
            "retry_allowed": False,
            "status": result["status"],
            "effects_executed": 0,
            "providers_enabled": False,
            "hashes": {
                "corpus_sha256": sha256(campaign.CORPUS),
                "preregistration_sha256": sha256(campaign.OUTPUT),
                "result_sha256": sha256(RESULT),
                "telemetry_sha256": sha256(TELEMETRY),
                "turn_audit_sha256": sha256(TURN_AUDIT),
                "runner_sha256": sha256(Path(__file__)),
            },
        },
    )
    return result


def main() -> int:
    result = run_once()
    print(
        json.dumps(
            {
                "status": result["status"],
                "failed_thresholds": result["failed_thresholds"],
                "diagnostic_summary": result["diagnostic_summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
