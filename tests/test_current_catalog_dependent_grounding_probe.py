from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBE = (
    ROOT
    / "experiments"
    / "mind_router_spike"
    / "probe_current_catalog_dependent_grounding.py"
)
SPEC = importlib.util.spec_from_file_location(
    "probe_current_catalog_dependent_grounding",
    PROBE,
)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_dependent_oracle_covers_every_real_deferred_catalog_plan() -> None:
    backing = json.loads(probe.BACKING.read_text(encoding="utf-8"))

    cases = probe.build_cases(backing)

    assert len(cases) == 17
    assert {case["case_id"] for case in cases} == set(
        probe.DEPENDENT_EXPECTATIONS
    )
    assert {case["operation"] for case in cases} == {
        "app.close",
        "browser.navigate",
        "browser.navigate.named",
        "message.send",
        "ocr.read",
        "vision.describe",
    }
    assert all(
        observation["verified"] is True
        and observation["status"] == "completed"
        for case in cases
        for observation in case["observations"]
    )


def test_dependent_oracle_preserves_message_literals_independently() -> None:
    assert probe.DEPENDENT_EXPECTATIONS["message-00"]["expected"] == {
        "recipientId": "recipient_catalog_00",
        "text": "la amo mucho",
    }
    assert probe.DEPENDENT_EXPECTATIONS["message-05"]["expected"] == {
        "recipientId": "recipient_catalog_05",
        "text": "es una increible persona",
    }


def test_dependent_grounding_probe_never_dispatches_an_effect() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert '"operation.request"' not in source
    assert '"type": "plan"' not in source
    assert '"type": "plan.ground"' in source
    assert "core_or_provider_requests_sent" in source
    assert "effects_executed" in source
