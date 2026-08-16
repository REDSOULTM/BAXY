from __future__ import annotations

import copy
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBE = (
    ROOT
    / "experiments"
    / "mind_router_spike"
    / "probe_current_catalog_argument_fidelity.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_current_catalog_argument_fidelity",
    PROBE,
)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def _synthetic_backing() -> dict:
    rows = []
    for case_id, expected in probe.EXACT_LITERAL_ARGUMENTS.items():
        steps = [
            {
                "id": f"step_{index}",
                "operation": operation,
                "arguments": copy.deepcopy(arguments),
                "argumentsMode": "literal",
                "dependsOn": [],
            }
            for index, (operation, arguments) in enumerate(expected.items(), 1)
        ]
        rows.append(
            {
                "case_id": case_id,
                "family": "fixture",
                "text": case_id,
                "observed_outcome": "ready",
                "presentable_expected_outcomes": ["ready"],
                "downstream": {"type": "plan.result", "steps": steps},
            }
        )
    started = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    for case_id, spec in probe.TEMPORAL_ARGUMENTS.items():
        due = (
            started + timedelta(seconds=spec["offset_seconds"])
            if "offset_seconds" in spec
            else (started.astimezone() + timedelta(days=1)).replace(
                hour=spec["tomorrow_local_hour"],
                minute=0,
                second=0,
                microsecond=0,
            ).astimezone(timezone.utc)
        )
        arguments = {**spec["arguments"], "dueUtc": due.isoformat()}
        rows.append(
            {
                "case_id": case_id,
                "family": "fixture",
                "text": case_id,
                "observed_outcome": "ready",
                "presentable_expected_outcomes": ["ready"],
                "started_at_utc": started.isoformat(),
                "finished_at_utc": (started + timedelta(seconds=1)).isoformat(),
                "downstream": {
                    "type": "arguments.result",
                    "operation": spec["operation"],
                    "arguments": arguments,
                },
            }
        )
    return {"rows": rows}


def test_argument_oracle_covers_every_presentable_action_in_review() -> None:
    cases, _ = probe.ready.review._load_inputs()
    reviewed_actions = {
        str(case["case_id"])
        for case in cases
        if case["outcome"] == "action"
    }

    assert len(reviewed_actions) == 71
    assert reviewed_actions - {"game-02"} == (
        set(probe.EXACT_LITERAL_ARGUMENTS) | set(probe.TEMPORAL_ARGUMENTS)
    )
    assert len(probe.EXACT_LITERAL_ARGUMENTS) == 61
    assert len(probe.TEMPORAL_ARGUMENTS) == 9


def test_argument_oracle_accepts_exact_literals_and_temporal_windows() -> None:
    rows, failures = probe.evaluate(_synthetic_backing())

    assert len(rows) == 70
    assert failures == []


def test_argument_oracle_rejects_one_changed_literal() -> None:
    backing = _synthetic_backing()
    changed = next(row for row in backing["rows"] if row["case_id"] == "vision-02")
    changed["downstream"]["steps"][0]["arguments"]["text"] = "Escribe Batman"

    _, failures = probe.evaluate(copy.deepcopy(backing))

    assert [failure["case_id"] for failure in failures] == ["vision-02"]
    assert failures[0]["errors"] == ["literal_arguments_mismatch"]


def test_argument_fidelity_probe_never_requests_an_effect() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert '"operation.request"' not in source
    assert '"plan.ground"' not in source
    assert "core_or_provider_requests_sent" in source
    assert "effects_executed" in source
