"""Open R215 once through the sealed corrected-runtime model path, no dispatch."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import DEFAULT_RUNTIME_MANIFEST  # noqa: E402
from experiments.mind_router_spike import (
    preregister_situated_cut_b_model_path_r224 as campaign,
)  # noqa: E402
from experiments.mind_router_spike import run_situated_cut_b_model_path_r221 as base  # noqa: E402


RESULT = REPO / "artifacts/audit/situated_cut_b_r215_model_path_r225.json"
TELEMETRY = REPO / "artifacts/audit/situated_cut_b_r215_model_path_r225.telemetry.jsonl"
TURN_AUDIT = (
    REPO / "artifacts/audit/situated_cut_b_r215_model_path_r225.turn-audit.jsonl"
)
RAW_REPLIES = (
    REPO / "artifacts/audit/situated_cut_b_r215_model_path_r225.raw-replies.jsonl"
)
RECEIPT = REPO / "artifacts/audit/situated_cut_b_r215_model_path_r225.consumed.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    preregistration = json.loads(campaign.OUTPUT.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in campaign.CORPUS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    identities = preregistration.get("identities", {})
    expected = {
        "corpus_sha256": sha256(campaign.CORPUS),
        "runtime_manifest_sha256": sha256(DEFAULT_RUNTIME_MANIFEST),
        "runtime_resolver_sha256": sha256(campaign.RUNTIME_RESOLVER),
        "runner_sha256": sha256(Path(__file__)),
        "base_runner_sha256": sha256(campaign.BASE_RUNNER),
        "scorer_sha256": sha256(campaign.SCORER),
    }
    if (
        preregistration.get("schema")
        != "baxy.situated-cut-b.model-path.r224-preregistration.v1"
        or len(rows) != 93
        or any(identities.get(key) != value for key, value in expected.items())
    ):
        raise RuntimeError("R224 preregistration identity changed")
    return preregistration, rows


def _configure_base() -> None:
    base.campaign = campaign
    base.RESULT, base.TELEMETRY, base.TURN_AUDIT = RESULT, TELEMETRY, TURN_AUDIT
    base.RAW_REPLIES, base.RECEIPT = RAW_REPLIES, RECEIPT
    base._load = _load


def run_once() -> dict[str, Any]:
    _configure_base()
    base._refuse_reuse()
    telemetry, preregistration, runtime = base.measure()
    result = base.scoring.build_result(telemetry, preregistration)
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
    base._write(TELEMETRY, telemetry, lines=True)
    base._write(RESULT, result)
    base._write(
        RECEIPT,
        {
            "schema": "baxy.situated-cut-b.model-path.r225-consumption.v1",
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
