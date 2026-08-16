"""R277: locate and price the forced tool choice in the primary decision call.

The registered decision call sends ``tool_choice: "required"`` together with a
tool list that contains only executable catalogue operations. That contract
leaves "call no function" undecodable, even though the policy prompt carried in
the same payload names seven turn classes that must not call one.

This program starts no model, enables no provider and executes no effect. It
reads the registered tree with ``ast`` and prices the consequence over the
already-consumed, already-open V8 telemetry. It is an audit, not a repair, and
it carries no runtime authority. It does not establish causation: only a sealed
A/B that changes ``tool_choice`` alone can do that.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "baxy.forced-tool-choice-audit.r277.v1"
DECISION_FUNCTION = "_post_native_tool_selection"
POLICY_PROMPT_NAME = "NATIVE_TOOL_POLICY_PROMPT"
LLM_SOURCE = "src/baxy_mind/llm.py"
V8_TELEMETRY = "artifacts/holdout/veto_reach_v8.telemetry.jsonl"
RESULT_PATH = "artifacts/audit/forced_tool_choice_r277.json"

# The policy prompt names these turn classes as requiring no function call.
NO_FUNCTION_CLASSES = (
    "conversation",
    "stable knowledge",
    "advice",
    "negated requests",
    "hypotheticals",
    "past events",
    "actions aimed at another device",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _module(root: Path) -> ast.Module:
    return ast.parse((root / LLM_SOURCE).read_text(encoding="utf-8"))


def _decision_function(module: ast.Module) -> ast.FunctionDef:
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == DECISION_FUNCTION:
            return node
    raise RuntimeError("decision_function_not_found")


def _decision_payload(module: ast.Module) -> dict[str, Any]:
    """Read the literal decision payload keys that shape the contract."""

    for statement in ast.walk(_decision_function(module)):
        if not isinstance(statement, ast.Assign):
            continue
        targets = [t.id for t in statement.targets if isinstance(t, ast.Name)]
        if "payload" not in targets or not isinstance(statement.value, ast.Dict):
            continue
        found: dict[str, Any] = {}
        for key, value in zip(statement.value.keys, statement.value.values):
            if not isinstance(key, ast.Constant):
                continue
            if isinstance(value, ast.Constant):
                found[str(key.value)] = value.value
            else:
                found[str(key.value)] = f"<{type(value).__name__}>"
        return found
    raise RuntimeError("decision_payload_not_found")


def _policy_prompt(module: ast.Module) -> str:
    for node in ast.walk(module):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if POLICY_PROMPT_NAME not in targets:
            continue
        return str(ast.literal_eval(node.value))
    raise RuntimeError("policy_prompt_not_found")


def _empty_call_branch_exists(module: ast.Module) -> bool:
    """The code handles an empty tool_calls list that `required` cannot produce."""

    return "calls == []" in ast.unparse(_decision_function(module))


def price_open_population(root: Path) -> dict[str, Any]:
    """Price the contract over the already-consumed, already-open V8 telemetry."""

    path = root / V8_TELEMETRY
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    served = [row for row in rows if row.get("role") == "served"]

    expected_absent = 0
    expected_absent_with_effect = 0
    raw_effect_free = 0
    zero_candidate_rows = 0
    contradicted_visible_text = 0
    shortlist_sizes: list[int] = []

    for row in served:
        expected = row.get("expected_operation")
        candidates = row.get("candidate_operations") or []
        shortlist_sizes.append(len(candidates))
        raw_effects = (row.get("raw_proposal") or {}).get("effect_operations") or []
        if not candidates:
            zero_candidate_rows += 1
        if expected and expected not in candidates:
            expected_absent += 1
            if raw_effects:
                expected_absent_with_effect += 1
        if not raw_effects:
            raw_effect_free += 1
        visible = " ".join(row.get("raw_visible_proposals") or []).casefold()
        if raw_effects and ("no puedo" in visible or "cannot" in visible):
            contradicted_visible_text += 1

    shortlist_sizes.sort()
    return {
        "population": "veto_reach_v8 telemetry (already consumed, already open)",
        "rows": len(rows),
        "servedRows": len(served),
        "expectedOperationAbsentFromShortlist": expected_absent,
        "expectedOperationAbsentYetEffectProposed": expected_absent_with_effect,
        "rawProposalsWithoutAnyEffect": raw_effect_free,
        "rowsReachingDecisionWithZeroCandidates": zero_candidate_rows,
        "effectProposedWhileVisibleTextDeclinedTheRequest": contradicted_visible_text,
        "shortlistSizeMinimum": shortlist_sizes[0] if shortlist_sizes else 0,
        "shortlistSizeMedian": (
            shortlist_sizes[len(shortlist_sizes) // 2] if shortlist_sizes else 0
        ),
        "shortlistSizeMaximum": shortlist_sizes[-1] if shortlist_sizes else 0,
    }


def build(root: Path) -> dict[str, Any]:
    module = _module(root)
    payload = _decision_payload(module)
    prompt = _policy_prompt(module)
    declared = [name for name in NO_FUNCTION_CLASSES if name in prompt]
    tool_choice = payload.get("tool_choice")

    contract = {
        "decisionFunction": DECISION_FUNCTION,
        "toolChoice": tool_choice,
        "modelMayDeclineToCall": tool_choice != "required",
        "declaredNoFunctionTurnClasses": declared,
        "declaredNoFunctionTurnClassCount": len(declared),
        "emptyToolCallBranchExistsButIsUnreachable": (
            _empty_call_branch_exists(module) and tool_choice == "required"
        ),
        "promptAndDecoderContradict": bool(declared) and tool_choice == "required",
    }

    return {
        "schema": SCHEMA,
        "authority": "static_contract_audit_not_a_repair_and_not_a_promotion",
        "verdict": (
            "forced_tool_choice_leaves_abstention_undecodable"
            if contract["promptAndDecoderContradict"]
            else "decision_contract_permits_abstention"
        ),
        "contract": contract,
        "openPopulationPricing": price_open_population(root),
        "constraints": {
            "model_started": False,
            "registered_runtime_modified": False,
            "providers_enabled": False,
            "effects_executed": 0,
            "opened_v9": False,
            "r228_opened": False,
            "clinc_opened": False,
            "public_holdout_opened": False,
            "voice_stt_wake_exercised": False,
        },
        "identities": {
            "llm_source_sha256": sha256_file(root / LLM_SOURCE),
            "v8_telemetry_sha256": sha256_file(root / V8_TELEMETRY),
            "policy_prompt_sha256": sha256_text(prompt),
        },
        "next_requirement": (
            "This audit locates a mechanism; it does not prove causation. A "
            "successor must seal an ABBA A/B that changes only tool_choice, run "
            "it on a fresh recogniser-independent population, price the change "
            "against rows that already succeed, and name the population that "
            "could refute it. Do not tune any veto to compensate."
        ),
        "overall_goal_met": False,
        "section_7_met": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="R277 forced tool choice audit")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--write", action="store_true")
    arguments = parser.parse_args()

    root = Path(arguments.repository_root).resolve()
    result = build(root)
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if arguments.write:
        destination = root / RESULT_PATH
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(rendered.encode("utf-8"))
        print(f"wrote {RESULT_PATH}")
        print(f"result_sha256={sha256_text(rendered)}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
