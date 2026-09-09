import ast
from pathlib import Path

path=Path(__file__).resolve().parents[1]/'tests/test_turn_policy.py'
source=path.read_text(encoding='utf-8')
replacements={
'test_native_tool_selection_cannot_bypass_candidate_free_conversation_veto': '''def test_native_positive_read_is_not_erased_by_the_type_classifier() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._post_native_tool_selection = lambda *_args: {
        "mode": "action", "question": "", "conversation_kind": "",
        "effect_operations": ["system.time"], "response_language": "es",
    }
    runtime._verify_semantic_effect_shape = lambda _text: pytest.fail(
        "the retired type classifier erased this measured native read"
    )
    result = runtime.decide_turn(
        "no me molesta, dime la hora",
        [turn_candidate("system.time", "Read the current local time.")],
    )
    assert result["mode"] == "action"
    assert result["effect_operations"] == ["system.time"]
    assert result["intent_operations"] == ["system.time"]
    assert result["effect_verification"] == "primary"
''',
'test_native_verified_recovery_reports_the_recovered_intent_identity': '''def test_native_knowledge_is_not_reclassified_as_an_external_read() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._post_native_tool_selection = lambda *_args: {
        "mode": "conversation", "question": "", "conversation_kind": "knowledge",
        "effect_operations": [], "response_language": "es",
    }
    runtime._verify_semantic_effect_shape = lambda _text: pytest.fail(
        "the retired type classifier converted stable knowledge to external_read"
    )
    result = runtime.decide_turn(
        "El aire es h20?",
        [turn_candidate("web.search", "Search the web.", required=("query",))],
    )
    assert result["mode"] == "conversation"
    assert result["conversation_kind"] == "knowledge"
    assert result["effect_operations"] == []
    assert result["intent_operations"] == []
    assert result["effect_verification"] == "not_applicable"
''',
'test_native_single_effect_agreement_does_not_repeat_model_count': '''def test_native_parameterized_proposal_still_requires_argument_grounding() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    runtime._post_native_tool_selection = lambda *_args: {
        "mode": "action", "question": "", "conversation_kind": "",
        "effect_operations": ["audio.volume"], "response_language": "es",
    }
    runtime._verify_effect_count = lambda _text: pytest.fail(
        "a second count must not override native selection"
    )
    result = runtime.decide_turn(
        "Pon el volumen al 30",
        [turn_candidate("audio.volume", "Set absolute output level.", required=("level",))],
    )
    assert result["mode"] == "action"
    assert result["effect_operations"] == ["audio.volume"]
    assert result["effect_verification"] == "grounding_required"
''',
'test_native_conversation_veto_uses_history_for_contextual_followup': '''def test_native_selector_receives_the_context_for_an_elliptical_followup() -> None:
    runtime = object.__new__(LlmRuntime)
    runtime._native_tool_policy_enabled = True
    history = [
        {"role": "user", "content": "dime la hora"},
        {"role": "assistant", "content": "Son las 12:30."},
    ]
    seen = []
    def native_selection(text, names, contracts, prior):
        seen.append((text, prior))
        return {
            "mode": "action", "question": "", "conversation_kind": "",
            "effect_operations": ["system.time"], "response_language": "es",
        }
    runtime._post_native_tool_selection = native_selection
    result = runtime.decide_turn(
        "y la fecha?", [turn_candidate("system.time", "Read current date and time.")],
        history=history,
    )
    assert seen == [("y la fecha?", history)]
    assert result["effect_operations"] == ["system.time"]
'''
}
lines=source.splitlines(keepends=True)
edits=[]
for node in ast.parse(source).body:
    if isinstance(node,ast.FunctionDef) and node.name in replacements:
        edits.append((node.lineno-1,node.end_lineno,replacements[node.name]))
assert len(edits)==len(replacements)
for start,end,replacement in sorted(edits,reverse=True):lines[start:end]=[replacement]
source=''.join(lines).replace('assert payloads[0]["tool_choice"] == "required"','assert payloads[0]["tool_choice"] == "auto"')
path.write_text(source,encoding='utf-8')
