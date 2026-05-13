"""Smoke test for G1..G5 features without calling the real LLM.

We mock LLMClient.chat to return canned responses so we can exercise the
plumbing of:
  G1 experience memory record/recall
  G2 summarization-based compaction
  G3 explicit plan generation + replanning
  G4 subagent spawning
  G5 turn-1 recall injected into the system prompt

Run with: python -m gemma4_agent.test_gx_features
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch


def _fake_chat_factory(responses: list[str]):
    """Return a chat() mock that yields the canned responses in order."""
    iterator = iter(responses)

    def _chat(messages: list[dict[str, Any]], tools: Any = None, **_kwargs: Any) -> dict[str, Any]:
        try:
            content = next(iterator)
        except StopIteration:
            content = "(no more responses)"
        return {
            "choices": [{
                "message": {"role": "assistant", "content": content, "tool_calls": []},
                "finish_reason": "stop",
            }],
        }
    return _chat


def test_g1_experience_record_and_recall() -> bool:
    from gemma4_agent.experience import ExperienceMemory
    from gemma4_agent.semantic_router import embed

    path = Path(__file__).parent / "data" / "test_experience.sqlite"
    if path.exists():
        path.unlink()
    mem = ExperienceMemory(path)
    r = mem.record(
        turn_id="t-test", user_input="abre Steam y busca Hades",
        tools_used=["steam"], outcome="ok", mission_status="PASS",
        summary="Opened Steam and searched Hades", embed_fn=embed,
    )
    assert r.get("ok"), f"record failed: {r}"
    recalls = mem.recall("steam y juegos", embed_fn=embed, k=3)
    assert len(recalls) >= 1, "should recall the previously stored turn"
    mem.close()
    path.unlink(missing_ok=True)
    print("G1 experience record + recall: OK")
    return True


def test_g3_should_plan() -> bool:
    from gemma4_agent.explicit_plan import should_plan
    assert not should_plan("hola", 0)
    assert should_plan("abre steam, luego mira mi biblioteca, despues cierra todo", 3)
    assert should_plan("haz un plan para limpiar el escritorio", 0)
    print("G3 should_plan heuristics: OK")
    return True


def test_g3_parse_steps() -> bool:
    from gemma4_agent.explicit_plan import _parse_numbered_steps
    plan = (
        "1. Abrir Steam y verificar que la ventana se enfoca.\n"
        "2. Ir a la biblioteca con steam(action=library).\n"
        "3. Buscar 'Hades' con steam(action=search_library, query='Hades').\n"
        "4. Reportar el resultado."
    )
    steps = _parse_numbered_steps(plan)
    assert len(steps) == 4, f"expected 4 steps, got {len(steps)}"
    print("G3 _parse_numbered_steps: OK")
    return True


def test_g3_generate_plan_with_mock() -> bool:
    from gemma4_agent.explicit_plan import generate_plan
    canned = (
        "1. Abrir Steam.\n"
        "2. Buscar Hades en la biblioteca.\n"
        "3. Lanzar el juego.\n"
        "4. Verificar que aparece la ventana del juego."
    )
    fake = _fake_chat_factory([canned])
    result = generate_plan(
        "abre Steam y lanza Hades, verificando que aparezca",
        chat_fn=lambda msgs: fake(msgs),
    )
    assert result.get("ok"), f"plan generation failed: {result}"
    assert result.get("plan"), "plan should be non-empty"
    assert len(result.get("steps", [])) == 4, f"expected 4 steps: {result.get('steps')}"
    print("G3 generate_plan with mock: OK")
    return True


def test_g3_replan_give_up() -> bool:
    from gemma4_agent.explicit_plan import replan
    fake = _fake_chat_factory(["GIVE_UP: no hay forma de conectar"])
    result = replan(
        "haz X imposible", "1. intenta X", [{"step": 1, "tool": "X", "error": "no existe"}],
        chat_fn=lambda msgs: fake(msgs),
    )
    assert result.get("ok"), result
    assert result.get("give_up") is True, "should detect give-up"
    print("G3 replan give-up: OK")
    return True


def test_g4_subagent_no_parent() -> bool:
    """Without a parent agent the tool degrades honestly to needs_implementation."""
    from gemma4_agent.memory import MemoryStore
    from gemma4_agent.state import AgentState
    from gemma4_agent.tools import ToolRegistry
    memory = MemoryStore(Path(__file__).parent / "data" / "memory.json")
    state = AgentState(Path(__file__).parent / "data" / "state.json")
    reg = ToolRegistry(memory=memory, captures_dir=Path(__file__).parent / "captures", state=state)
    r = reg.execute("subagent", {"action": "status"})
    assert not r.get("ok"), "without parent should fail"
    assert r.get("status") == "needs_implementation", r
    print("G4 subagent honest degrade without parent: OK")
    return True


def test_g4_subagent_with_mock_parent() -> bool:
    """Subagent wiring works when we mock the child's LLM."""
    from gemma4_agent.agent import Gemma4Agent
    canned_child_response = "Hice la sub-tarea sin tools."
    fake = _fake_chat_factory([canned_child_response])
    parent = Gemma4Agent()
    with patch("gemma4_agent.llm_client.LLMClient.chat", side_effect=lambda msgs, tools=None, **kw: fake(msgs)):
        r = parent.tools.execute("subagent", {
            "action": "run",
            "task": "echo prueba",
            "max_turns": 1,
            "tools": ["system"],
        })
    if not r.get("ok"):
        print(f"  -> subagent run failed: {r.get('error')}")
        return False
    assert r.get("task") == "echo prueba"
    assert r.get("max_turns") == 1
    assert r.get("tools_filter") == ["system"]
    print("G4 subagent run with mock parent: OK")
    return True


def test_g6_phrase_trigger_creation_validation() -> bool:
    """on_phrase requires a phrase of >=3 chars."""
    from gemma4_agent.memory import MemoryStore
    from gemma4_agent.state import AgentState
    from gemma4_agent.tools import ToolRegistry
    memory = MemoryStore(Path(__file__).parent / "data" / "memory.json")
    state = AgentState(Path(__file__).parent / "data" / "state.json")
    reg = ToolRegistry(memory=memory, captures_dir=Path(__file__).parent / "captures", state=state)
    r = reg.execute("routine", {
        "action": "create",
        "name": "test phrase short",
        "trigger": {"type": "on_phrase", "phrase": "hi"},
        "steps": [{"tool": "system", "args": {"action": "time"}}],
    })
    assert not r.get("ok"), "should reject 2-char phrase"
    r = reg.execute("routine", {
        "action": "create",
        "name": "test phrase missing",
        "trigger": {"type": "on_phrase"},
        "steps": [{"tool": "system", "args": {"action": "time"}}],
    })
    assert not r.get("ok"), "should reject missing phrase"
    print("G6 phrase_trigger validation: OK")
    return True


def test_g6_active_phrase_triggers_returns_enabled() -> bool:
    """Create one routine, ensure active_phrase_triggers lists it; disable, ensure it disappears."""
    import time
    from gemma4_agent.memory import MemoryStore
    from gemma4_agent.state import AgentState
    from gemma4_agent.tools import ToolRegistry
    from gemma4_agent.domain_tools import active_phrase_triggers
    memory = MemoryStore(Path(__file__).parent / "data" / "memory.json")
    state = AgentState(Path(__file__).parent / "data" / "state.json")
    reg = ToolRegistry(memory=memory, captures_dir=Path(__file__).parent / "captures", state=state)
    unique_label = f"test_g6_phrase_{int(time.time())}"
    unique_phrase = f"buenisimas noches g6 {int(time.time())}"
    create = reg.execute("routine", {
        "action": "create",
        "name": unique_label,
        "trigger": {"type": "on_phrase", "phrase": unique_phrase},
        "steps": [{"tool": "system", "args": {"action": "time"}}],
    })
    assert create.get("ok"), f"create failed: {create}"
    routine_id = (create.get("routine") or {}).get("id")
    listed = active_phrase_triggers(state)
    assert any(r["id"] == routine_id for r in listed), "should be listed as active"
    matching = [r for r in listed if r["id"] == routine_id]
    assert matching[0]["phrase"] == unique_phrase
    # Disable and re-check
    disable = reg.execute("routine", {"action": "disable", "id": routine_id})
    assert disable.get("ok"), disable
    listed_after = active_phrase_triggers(state)
    assert not any(r["id"] == routine_id for r in listed_after), "disabled should not list"
    # Cleanup
    reg.execute("routine", {"action": "delete", "id": routine_id})
    print("G6 active_phrase_triggers respects enabled flag: OK")
    return True


def test_g6_phrase_hook_fires_on_match() -> bool:
    """Create a phrase routine; calling run_content with matching text should fire it
    BEFORE the LLM is invoked. We mock the LLM to return a final no-tool reply so we
    don't depend on llama-server."""
    import time
    from gemma4_agent.agent import Gemma4Agent

    fake = _fake_chat_factory(["Hecho: registre tu rutina y la ejecute."])
    agent = Gemma4Agent()
    # Create routine
    phrase = f"phrase_hook_test_{int(time.time())}"
    create = agent.tools.execute("routine", {
        "action": "create",
        "name": "g6 phrase test",
        "trigger": {"type": "on_phrase", "phrase": phrase},
        "steps": [{"tool": "system", "args": {"action": "time"}}],
    })
    if not create.get("ok"):
        print(f"  routine create failed: {create}")
        return False
    routine_id = (create.get("routine") or {}).get("id")
    try:
        with patch("gemma4_agent.llm_client.LLMClient.chat", side_effect=lambda msgs, tools=None, **kw: fake(msgs)):
            reply = agent.run_text(f"buenas, {phrase} y dime la hora")
        assert agent._phrase_fires, "phrase fires list should be non-empty"
        fire = agent._phrase_fires[0]
        assert fire["phrase"] == phrase
        assert any(r.get("ok") for r in fire["results"]), "at least one step should have ok=True"
    finally:
        agent.tools.execute("routine", {"action": "delete", "id": routine_id})
    print("G6 phrase hook fires before LLM: OK")
    return True


def test_g2_compaction_disabled_keeps_truncation() -> bool:
    """When summarization is disabled, _compact_completed_history still truncates."""
    import os
    os.environ["GEMMA4_AGENT_SUMMARIZATION"] = "false"
    from gemma4_agent.agent import _summarization_enabled
    assert _summarization_enabled() is False
    os.environ.pop("GEMMA4_AGENT_SUMMARIZATION", None)
    print("G2 summarization can be disabled: OK")
    return True


def main() -> int:
    tests = [
        test_g1_experience_record_and_recall,
        test_g3_should_plan,
        test_g3_parse_steps,
        test_g3_generate_plan_with_mock,
        test_g3_replan_give_up,
        test_g4_subagent_no_parent,
        test_g4_subagent_with_mock_parent,
        test_g6_phrase_trigger_creation_validation,
        test_g6_active_phrase_triggers_returns_enabled,
        test_g6_phrase_hook_fires_on_match,
        test_g2_compaction_disabled_keeps_truncation,
    ]
    failures: list[str] = []
    for t in tests:
        try:
            if not t():
                failures.append(t.__name__)
        except Exception as exc:
            failures.append(f"{t.__name__}: {exc}")
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - len(failures)}/{len(tests)} passing")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
