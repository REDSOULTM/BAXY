"""ABBA gate for measured near-synonym operation boundaries.

The deterministic recognizer is suspended inside the probe so these canonical
development requests exercise the same model-owned path as an unseen
paraphrase.  The baseline removes only the authenticated-application retrieval
bridge and the five native tool-description suffixes under test.  Both arms
run the same source tree, model, catalog, validators and side-effect-free
``turn.decide`` protocol; no Core operation is dispatched. The corpus also
contains an interactive ``play`` request to prove that clarifying the media
siblings cannot convert a game invitation into media authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from experiments.mind_router_spike import probe_policy_tool_quality as policy_probe
from scripts.baxy_runtime_config import (
    DEFAULT_RUNTIME_MANIFEST,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import write_json_atomic

OUTPUT = REPO / "artifacts" / "fixes" / "sibling_leaf_discrimination_20260801.json"
TELEMETRY = OUTPUT.with_suffix(".raw.jsonl")

CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "volume-absolute",
        "text": "Pon el volumen al 8 por ciento",
        "expected_operations": ["audio.volume"],
        "expected_kind": "action",
    },
    {
        "case_id": "spotify-open",
        "text": "Abre Spotify",
        "expected_operations": ["app.open"],
        "expected_kind": "action",
    },
    {
        "case_id": "spotify-search-play",
        "text": "Busca Beat It en Spotify y reprodúcela",
        "expected_operations": ["media.play.query"],
        "expected_kind": "action",
    },
    {
        "case_id": "interactive-play-unsupported",
        "text": "Can you play a board game with me?",
        "expected_operations": [],
        "expected_kind": "conversation",
    },
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> dict[str, Any]:
    runtime = resolve_runtime(manifest_path=DEFAULT_RUNTIME_MANIFEST)
    TELEMETRY.parent.mkdir(parents=True, exist_ok=True)
    TELEMETRY.unlink(missing_ok=True)
    TELEMETRY.touch()
    rows: list[dict[str, Any]] = []
    order = (
        "sibling_baseline",
        "sibling_candidate",
        "sibling_candidate",
        "sibling_baseline",
    )
    for session, variant in enumerate(order):
        session_rows = policy_probe._run(
            runtime,
            list(CASES),
            TELEMETRY,
            variant,
        )
        for row in session_rows:
            row["session"] = session
        rows.extend(session_rows)

    summaries: dict[str, Any] = {}
    for variant in ("sibling_baseline", "sibling_candidate"):
        selected = [row for row in rows if row["variant"] == variant]
        exact = sum(row.get("outcome") == "exact" for row in selected)
        latencies = sorted(float(row["seconds"]) for row in selected)
        summaries[variant] = {
            "turns": len(selected),
            "exact": exact,
            "accuracy_exact": exact / len(selected),
            "p50_seconds": statistics.median(latencies),
            "p95_seconds": latencies[
                min(len(latencies) - 1, int(0.95 * len(latencies)))
            ],
            "by_case": {
                case["case_id"]: {
                    "turns": sum(
                        row["case_id"] == case["case_id"] for row in selected
                    ),
                    "exact": sum(
                        row["case_id"] == case["case_id"]
                        and row.get("outcome") == "exact"
                        for row in selected
                    ),
                }
                for case in CASES
            },
        }

    baseline = summaries["sibling_baseline"]
    candidate = summaries["sibling_candidate"]
    report = {
        "schema": "baxy.sibling-leaf-discrimination-abba.v2",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": (
            "ABBA whole sidecar sessions; two deterministic repeats per case "
            "per session; recognizer suspended; turn.decide only."
        ),
        "session_order": list(order),
        "cases": list(CASES),
        "arms": summaries,
        "delta_exact": candidate["accuracy_exact"] - baseline["accuracy_exact"],
        "acceptance": {
            "candidate_all_exact": candidate["exact"] == candidate["turns"],
            "no_case_regression": all(
                candidate["by_case"][case["case_id"]]["exact"]
                >= baseline["by_case"][case["case_id"]]["exact"]
                for case in CASES
            ),
            "baseline_defect_reproduced": baseline["exact"] < baseline["turns"],
        },
        "effects_executed": 0,
        "runtime_manifest_changed": False,
        "runtime": public_runtime_identity(runtime),
        "source": {
            "probe_sha256": _sha256(Path(__file__).resolve()),
            "product_probe_sha256": _sha256(Path(policy_probe.__file__).resolve()),
            "mind_sha256": _sha256(REPO / "src" / "baxy_mind" / "__main__.py"),
            "llm_sha256": _sha256(REPO / "src" / "baxy_mind" / "llm.py"),
        },
        "telemetry": {
            "path": str(TELEMETRY.relative_to(REPO)).replace("\\", "/"),
            "sha256": _sha256(TELEMETRY),
        },
        "rows": rows,
    }
    write_json_atomic(OUTPUT, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", action="store_true")
    parser.add_argument("--telemetry", default="")
    parser.add_argument("--variant", default="sibling_candidate")
    args, _ = parser.parse_known_args()
    if args.sidecar:
        return policy_probe._sidecar_main(args.telemetry, args.variant)
    report = run()
    print(
        json.dumps(
            {
                "arms": report["arms"],
                "delta_exact": report["delta_exact"],
                "acceptance": report["acceptance"],
                "effects_executed": report["effects_executed"],
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
