"""Dry-run tier evals for computer-use compatibility.

Default mode is deliberately non-invasive: it does not move focus, type, click,
start apps, or inspect the real desktop. It validates that the compatibility
matrix is explicit, the planner primitive contract is closed, and layer policy
chooses structured automation before OCR/vision.

Live GUI evals require both ``--live`` and ``GEMMA4_RUN_LIVE_GUI_EVAL=1`` and
are intentionally not implemented here; they should live in a separate harness
with disposable app profiles and per-app reset/verification.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class TierCase:
    tier: int
    app_family: str
    name: str
    goal: str
    ops: tuple[str, ...]
    verifier: str
    expected_primary: str


CASES: tuple[TierCase, ...] = (
    TierCase(
        tier=1,
        app_family="browser",
        name="open_site_and_wait",
        goal="open a known website and wait for a visible heading",
        ops=("open_url", "wait_for"),
        verifier="browser_text_or_title",
        expected_primary="browser_cdp",
    ),
    TierCase(
        tier=1,
        app_family="native_uia",
        name="fill_native_form",
        goal="fill a labeled text field in a native app",
        ops=("fill_field", "wait_for"),
        verifier="uia_value_pattern",
        expected_primary="uia_control_pattern",
    ),
    TierCase(
        tier=1,
        app_family="browser_no_cdp",
        name="browser_without_cdp",
        goal="operate a browser that cannot expose CDP",
        ops=("click", "wait_for"),
        verifier="browser_accessibility_or_uia",
        expected_primary="browser_accessibility",
    ),
    TierCase(
        tier=2,
        app_family="native_uia",
        name="toggle_native_setting",
        goal="set a checkbox or switch to a requested state",
        ops=("toggle", "wait_for"),
        verifier="uia_toggle_pattern",
        expected_primary="uia_control_pattern",
    ),
    TierCase(
        tier=2,
        app_family="electron_degraded",
        name="click_electron_accessible_label",
        goal="click a visible control in an Electron app with weak UIA",
        ops=("click", "wait_for"),
        verifier="ocr_or_vision_state",
        expected_primary="ocr",
    ),
    TierCase(
        tier=3,
        app_family="browser",
        name="browser_form_submit",
        goal="fill a web form and verify a resulting page state",
        ops=("open_url", "fill_field", "click", "wait_for"),
        verifier="cdp_accessibility_tree_and_dom_text",
        expected_primary="browser_cdp",
    ),
    TierCase(
        tier=4,
        app_family="cross_app",
        name="copy_information_between_apps",
        goal="read one app, switch to another, fill a field, verify state",
        ops=("focus_app", "wait_for", "focus_app", "fill_field", "wait_for"),
        verifier="per_step_structural_verifiers",
        expected_primary="app_specialist",
    ),
    TierCase(
        tier=5,
        app_family="no_visual_degraded",
        name="honest_fail_no_layers",
        goal="try a degraded app when no structural or visual layer is available",
        ops=("click",),
        verifier="honest_failure_only",
        expected_primary="honest_fail",
    ),
)


SNAPSHOTS: dict[str, dict[str, Any]] = {
    "browser": {
        "app_kind": "browser",
        "is_browser": True,
        "cdp_candidate": True,
        "vision_fallback_available": True,
    },
    "browser_no_cdp": {
        "app_kind": "browser",
        "is_browser": True,
        "cdp_candidate": False,
        "vision_fallback_available": True,
    },
    "native_uia": {
        "app_kind": "native_or_unknown",
        "uia_available": True,
        "uia_degraded": False,
        "vision_fallback_available": True,
    },
    "electron_degraded": {
        "app_kind": "electron_or_webview",
        "uia_available": True,
        "uia_degraded": True,
        "vision_fallback_available": True,
    },
    "cross_app": {
        "app_kind": "native_or_unknown",
        "uia_available": True,
        "uia_degraded": False,
        "vision_fallback_available": True,
    },
    "no_visual_degraded": {
        "app_kind": "electron_or_webview",
        "uia_available": True,
        "uia_degraded": True,
        "ocr_available": False,
        "vision_fallback_available": False,
    },
}


def _plan_json(case: TierCase) -> str:
    steps = [{"op": op, "arg": "target=value" if op == "fill_field" else "target"} for op in case.ops]
    return json.dumps(steps, ensure_ascii=True)


def run_dry() -> tuple[bool, list[dict[str, Any]]]:
    from gemma4_agent.computer_use_pkg.computer_use import parse_plan
    from gemma4_agent.computer_use_caps.policy import choose_policy
    from gemma4_agent.computer_use_caps.router import CapabilityRouter

    rows: list[dict[str, Any]] = []
    all_ok = True
    for case in CASES:
        plan = parse_plan(_plan_json(case))
        primitive_ok = bool(plan) and all(step["op"] in CapabilityRouter.verified_ops for step in plan)
        snap = SNAPSHOTS[case.app_family]
        policy = choose_policy(snap, case.ops[0])
        policy_ok = policy.primary == case.expected_primary
        verifier_ok = bool(case.verifier and case.verifier != "none")
        ok = primitive_ok and policy_ok and verifier_ok
        all_ok = all_ok and ok
        rows.append({
            "ok": ok,
            "tier": case.tier,
            "case": case.name,
            "app_family": case.app_family,
            "primitive_ok": primitive_ok,
            "policy": policy.primary,
            "expected_policy": case.expected_primary,
            "verifier": case.verifier,
        })
    return all_ok, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true",
                        help="reserved for disposable live GUI harnesses")
    parser.add_argument("--json", action="store_true",
                        help="print machine-readable rows")
    args = parser.parse_args(argv)

    if args.live:
        if os.environ.get("GEMMA4_RUN_LIVE_GUI_EVAL") != "1":
            print("LIVE GUI eval is blocked. Set GEMMA4_RUN_LIVE_GUI_EVAL=1 in a disposable profile.")
            return 2
        print("LIVE GUI eval harness is intentionally separate from this dry-run contract check.")
        return 2

    ok, rows = run_dry()
    if args.json:
        print(json.dumps({"ok": ok, "rows": rows}, ensure_ascii=True, indent=2))
    else:
        print("COMPUTER_USE_TIER_EVAL dry-run")
        for row in rows:
            mark = "PASS" if row["ok"] else "FAIL"
            print(f"[{mark}] T{row['tier']} {row['case']}: policy={row['policy']} verifier={row['verifier']}")
        print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
