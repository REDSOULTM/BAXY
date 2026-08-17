"""R277: the forced tool choice audit regenerates its artifact from the tree."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sealed_evidence import assert_sealed


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/mind_router_spike/audit_forced_tool_choice_r277.py"
ARTIFACT = ROOT / "artifacts/audit/forced_tool_choice_r277.json"
R277_ARTIFACT_SHA256 = (
    "a898809db3ebe0641c79491e6f9a4d57f46d6b9e83b9651674dcc9e83d15ad28"
)


def _module():
    spec = importlib.util.spec_from_file_location("r277", SOURCE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_r277_reads_the_registered_decision_contract() -> None:
    contract = _module().build(ROOT)["contract"]

    assert contract["decisionFunction"] == "_post_native_tool_selection"
    assert contract["toolChoice"] == "required"
    # `required` forbids the abstention the same payload's prompt demands.
    assert contract["modelMayDeclineToCall"] is False
    assert contract["declaredNoFunctionTurnClassCount"] == 7
    assert contract["emptyToolCallBranchExistsButIsUnreachable"] is True
    assert contract["promptAndDecoderContradict"] is True


def test_r277_prices_the_open_population_without_starting_a_model() -> None:
    result = _module().build(ROOT)

    assert result["verdict"] == "forced_tool_choice_leaves_abstention_undecodable"
    pricing = result["openPopulationPricing"]
    assert pricing["servedRows"] == 12
    # No effect-free raw proposal was ever observed under the forced contract.
    assert pricing["rawProposalsWithoutAnyEffect"] == 0
    assert pricing["rowsReachingDecisionWithZeroCandidates"] == 0
    assert pricing["expectedOperationAbsentFromShortlist"] == 9
    assert pricing["expectedOperationAbsentYetEffectProposed"] == 9

    constraints = result["constraints"]
    assert constraints["model_started"] is False
    assert constraints["providers_enabled"] is False
    assert constraints["effects_executed"] == 0
    assert constraints["opened_v9"] is False
    assert constraints["voice_stt_wake_exercised"] is False


def test_r277_audit_is_read_only_over_the_runtime() -> None:
    import ast

    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    # An audit may not reach the runtime, post to it, or dispatch anything.
    assert imported.isdisjoint({"requests", "subprocess", "urllib", "http"})
    assert imported.isdisjoint({"baxy_mind", "torch", "sentence_transformers"})


def test_published_artifact_is_sealed_against_silent_change() -> None:
    """The audit is consumed: it is verified by its seal, not regenerated.

    R277 froze the SHA-256 of ``src/baxy_mind/llm.py`` as part of its identity.
    Goal 03 measured the forced contract on a fresh paraphrase population --
    +3 correct raw decisions of 124 against -8 honest abstentions out of 36 --
    and turned it off, which necessarily moves that file. Regenerating the
    artifact from the present tree would overwrite what the audit recorded
    about the tree it audited, so §7 applies: keep the bytes and verify them.
    """

    assert_sealed(ARTIFACT, R277_ARTIFACT_SHA256)
    published = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    # Everything the audit concluded, independent of the tree it read, still
    # has to be there.
    assert published["verdict"] == (
        "forced_tool_choice_leaves_abstention_undecodable"
    )
    assert published["contract"]["toolChoice"] == "required"
    assert published["contract"]["modelMayDeclineToCall"] is False
