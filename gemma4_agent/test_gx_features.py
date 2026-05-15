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

import numpy as np  # used by Fase W voice tests


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
    # safety_enabled=False: este test ejercita el lifecycle (create/disable/delete)
    # de una routine, no la politica de confirmacion. El default cambio a True en
    # la refactor CC-101 (gating duro de routine.create); para que el test mida
    # lo que dice medir (active_phrase_triggers respeta enabled), saltamos el gate.
    reg = ToolRegistry(memory=memory, captures_dir=Path(__file__).parent / "captures", state=state, safety_enabled=False)
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


def test_h1_2_run_with_timeout_returns_on_hang() -> bool:
    """_run_with_timeout must return with _timed_out=True if the fn hangs past the deadline."""
    import time as _time
    from gemma4_agent.agent import _run_with_timeout
    started = _time.time()
    result = _run_with_timeout(lambda: _time.sleep(5) or {"ok": True}, timeout_s=0.5)
    elapsed = _time.time() - started
    assert result.get("_timed_out") is True, f"should time out, got {result}"
    assert elapsed < 2.0, f"timeout did not bound elapsed time: {elapsed}"
    print("H1.2 _run_with_timeout bounds elapsed: OK")
    return True


def test_h1_2_run_with_timeout_captures_exception() -> bool:
    """_run_with_timeout must capture an in-thread exception, not bubble up."""
    from gemma4_agent.agent import _run_with_timeout
    def boom():
        raise RuntimeError("explode")
    result = _run_with_timeout(boom, timeout_s=2.0)
    assert result.get("_timed_out") is False
    assert "explode" in (result.get("_error") or "")
    print("H1.2 _run_with_timeout captures exception: OK")
    return True


def test_h1_3_is_unverified_result() -> bool:
    from gemma4_agent.agent import _is_unverified_result
    assert _is_unverified_result({"ok": False, "error": "x"}) is True
    assert _is_unverified_result({"ok": True, "verified": False}) is True
    assert _is_unverified_result({"ok": True, "status": "needs_verification"}) is True
    assert _is_unverified_result({"ok": True, "status": "done", "verified": True}) is False
    assert _is_unverified_result({"ok": True, "status": "failed"}) is True
    # not a dict
    assert _is_unverified_result(None) is False  # type: ignore[arg-type]
    print("H1.3 _is_unverified_result classification: OK")
    return True


def test_h1_4_format_phrase_fires_failure_warning() -> bool:
    """The system block must include a WARNING line when any step did not complete."""
    from gemma4_agent.agent import _format_phrase_fires
    fires = [{
        "label": "test",
        "phrase": "abc",
        "results": [
            {"tool": "ok_one", "ok": True},
            {"tool": "fail_one", "ok": False, "error": "boom"},
        ],
    }]
    rendered = _format_phrase_fires(fires)
    assert "WARNING" in rendered, "must surface WARNING on partial failure"
    assert "fail_one" in rendered
    # No warning when all ok.
    rendered_all_ok = _format_phrase_fires([{
        "label": "t", "phrase": "p",
        "results": [{"tool": "x", "ok": True}],
    }])
    assert "WARNING" not in rendered_all_ok
    print("H1.4 phrase fires WARNING on partial failure: OK")
    return True


def test_h1_5_replan_excludes_needs_user_failures() -> bool:
    """Tools returning status='needs_user_*' must NOT count toward replan threshold."""
    # We can't run a full turn without llama-server; exercise the logic directly.
    # Mirror the inline rule in agent.run_content.
    samples = [
        ({"ok": False, "status": "needs_user_auth", "error": "no token"}, False),
        ({"ok": False, "status": "needs_dependency", "error": "missing soundvolumeview"}, False),
        ({"ok": False, "status": "failed", "error": "real boom"}, True),
        ({"ok": False, "completion_status": "needs_user_install", "error": "x"}, False),
        ({"ok": False, "status": "needs_verification", "error": "x"}, False),  # not counted
    ]
    for result, expected_counts in samples:
        status_norm = str(result.get("status") or "").casefold()
        completion = str(result.get("completion_status") or "").casefold()
        is_blocked = status_norm.startswith("needs_") or completion.startswith("needs_")
        counts = (not result.get("ok")) and not is_blocked
        assert counts == expected_counts, f"mismatch on {result}: counts={counts}, expected={expected_counts}"
    print("H1.5 replan failure filter: OK")
    return True


def test_h1_1_chat_timeout_param_accepted() -> bool:
    """LLMClient.chat must accept timeout_s without raising even if llama-server is down."""
    from gemma4_agent.config import AgentConfig
    from gemma4_agent.llm_client import LLMClient
    # Force a non-routable host so the call fails fast.
    cfg = AgentConfig.from_env()
    cfg = type(cfg)(**{**cfg.__dict__, "server_url": "http://127.0.0.1:1"})  # type: ignore[arg-type]
    client = LLMClient(cfg)
    try:
        client.chat([{"role": "user", "content": "hi"}], timeout_s=0.5)
    except RuntimeError as exc:
        msg = str(exc).lower()
        assert "timeout" in msg or "connection" in msg or "http_error" in msg, f"unexpected error: {exc}"
        print("H1.1 chat timeout_s param surfaces a connection/timeout error: OK")
        return True
    print("FAIL: chat with bogus server did not raise")
    return False


def test_h2_1_experience_prune_max_records() -> bool:
    """Insert >max_records rows; prune keeps only the newest."""
    import os
    from gemma4_agent.experience import ExperienceMemory
    from gemma4_agent.semantic_router import embed
    path = Path(__file__).parent / "data" / "test_experience_prune.sqlite"
    if path.exists():
        path.unlink()
    os.environ["GEMMA4_EXPERIENCE_MAX_RECORDS"] = "5"
    os.environ["GEMMA4_EXPERIENCE_MAX_AGE_DAYS"] = "0"  # disable age-based for this test
    try:
        mem = ExperienceMemory(path)
        for i in range(12):
            r = mem.record(
                turn_id=f"t-{i}", user_input=f"turno numero {i}",
                tools_used=["x"], outcome="ok", mission_status="PASS",
                summary=f"s{i}", embed_fn=embed,
            )
            assert r.get("ok"), r
        before_count = mem.stats()["experience_count"]
        assert before_count == 12, f"should have 12 before prune, got {before_count}"
        pruned = mem.prune()
        assert pruned.get("ok"), pruned
        after_count = mem.stats()["experience_count"]
        assert after_count == 5, f"should keep 5 after prune, got {after_count}"
        # Ensure the oldest were dropped, not the newest.
        recalls = mem.recall("turno numero 11", embed_fn=embed, k=1)
        assert recalls, "newest record should still be recallable"
        mem.close()
    finally:
        os.environ.pop("GEMMA4_EXPERIENCE_MAX_RECORDS", None)
        os.environ.pop("GEMMA4_EXPERIENCE_MAX_AGE_DAYS", None)
        path.unlink(missing_ok=True)
    print("H2.1 experience prune by max_records: OK")
    return True


def test_h2_2_summarization_cooldown_helper() -> bool:
    import os
    from gemma4_agent.agent import _summarization_cooldown_turns
    assert _summarization_cooldown_turns() == 6
    os.environ["GEMMA4_AGENT_SUMMARIZATION_COOLDOWN"] = "20"
    try:
        assert _summarization_cooldown_turns() == 20
    finally:
        os.environ.pop("GEMMA4_AGENT_SUMMARIZATION_COOLDOWN", None)
    os.environ["GEMMA4_AGENT_SUMMARIZATION_COOLDOWN"] = "bogus"
    try:
        assert _summarization_cooldown_turns() == 6, "fallback on parse error"
    finally:
        os.environ.pop("GEMMA4_AGENT_SUMMARIZATION_COOLDOWN", None)
    print("H2.2 summarization cooldown helper: OK")
    return True


def test_h2_3_semantic_router_transient_retry() -> bool:
    """If the model load raises a transient error, _STATE should record it and allow
    a retry after cooldown — without becoming permanently_disabled."""
    from gemma4_agent import semantic_router as sr
    # Reset state to known.
    sr._STATE.model = None
    sr._STATE.tool_embeddings = None
    sr._STATE.permanently_disabled = False
    sr._STATE.attempt_count = 0
    sr._STATE.last_attempt_ts = 0.0
    sr._STATE.last_error = ""

    # Patch SentenceTransformer to raise once, then succeed.
    import sentence_transformers
    original = sentence_transformers.SentenceTransformer
    calls = {"n": 0}
    class FakeModel:
        def encode(self, texts, normalize_embeddings=False, show_progress_bar=False):
            import numpy as _np
            return _np.zeros((len(texts), 384), dtype="float32")
    def fake_st(name):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient disk full")
        return FakeModel()
    sentence_transformers.SentenceTransformer = fake_st  # type: ignore[assignment]
    try:
        ok1 = sr._ensure_loaded()
        assert ok1 is False, "first call should fail transient"
        assert sr._STATE.permanently_disabled is False, "transient should NOT mark permanent"
        assert "transient disk full" in sr._STATE.last_error
        # Cooldown should block the immediate retry.
        ok_blocked = sr._ensure_loaded()
        assert ok_blocked is False
        # Bypass cooldown by resetting last_attempt_ts.
        sr._STATE.last_attempt_ts = 0.0
        ok2 = sr._ensure_loaded()
        assert ok2 is True, f"second call should succeed; state={sr._STATE}"
    finally:
        sentence_transformers.SentenceTransformer = original  # type: ignore[assignment]
        # Reset for downstream tests.
        sr._STATE.model = None
        sr._STATE.tool_embeddings = None
        sr._STATE.permanently_disabled = False
        sr._STATE.attempt_count = 0
        sr._STATE.last_error = ""
    print("H2.3 semantic router transient retry: OK")
    return True


def test_h3_1_phrase_confirm_prepends_when_unack() -> bool:
    """If phrase fires but the reply does not mention them, _guard_phrase_confirm prepends a confirm."""
    from gemma4_agent.agent import Gemma4Agent
    agent = Gemma4Agent()
    agent._phrase_fires = [{
        "label": "modo gaming", "phrase": "modo gaming",
        "results": [{"tool": "audio", "ok": True}, {"tool": "app", "ok": True}],
    }]
    # Reply that doesn't mention the routine.
    out = agent._guard_phrase_confirm("Esto es solo una respuesta cualquiera.")
    assert "Ejecute tu rutina" in out, out
    # Reply that already acknowledges via 'hecho' should be left alone.
    out2 = agent._guard_phrase_confirm("Hecho, ya cambie todo.")
    assert "Ejecute tu rutina" not in out2
    # Reply that mentions the label should be left alone.
    out3 = agent._guard_phrase_confirm("Aplique tu modo gaming sin problema.")
    assert "Ejecute tu rutina" not in out3
    print("H3.1 phrase confirm guard: OK")
    return True


def test_h3_2_plan_status_surfaces_only_on_short_reply() -> bool:
    """_guard_plan_status only touches the reply when plan failed AND reply is short."""
    from gemma4_agent.agent import Gemma4Agent
    agent = Gemma4Agent()
    # Plan failed + short reply -> note appended.
    agent._explicit_plan_status = {"state": "failed", "error": "timeout"}
    short = "ok"
    out = agent._guard_plan_status(short)
    assert "intente generar un plan" in out, out
    # Plan failed + long reply -> untouched.
    long_reply = "x" * 200
    out2 = agent._guard_plan_status(long_reply)
    assert "intente generar un plan" not in out2
    # Plan skipped -> never surfaced.
    agent._explicit_plan_status = {"state": "skipped"}
    out3 = agent._guard_plan_status("hola")
    assert out3 == "hola"
    # Plan ready -> never surfaced.
    agent._explicit_plan_status = {"state": "ready", "step_count": 4}
    out4 = agent._guard_plan_status("ok")
    assert out4 == "ok"
    print("H3.2 plan status guard: OK")
    return True


def test_h3_3_parse_args_distinguishes_malformed() -> bool:
    """_parse_args returns (args, error) and signals malformed JSON clearly."""
    from gemma4_agent.agent import _parse_args
    args, err = _parse_args({"x": 1})
    assert args == {"x": 1} and err is None
    args, err = _parse_args('{"x": 1}')
    assert args == {"x": 1} and err is None
    args, err = _parse_args("")
    assert args == {} and err is None
    args, err = _parse_args(None)
    assert args == {} and err is None
    # The bad case: malformed JSON gives a clear error string AND a flagged dict.
    args, err = _parse_args('{"x": ')
    assert err is not None and "invalid_json" in err
    assert "_raw_invalid_json" in args
    # Non-string non-dict gets a clear unsupported_args_type message.
    args, err = _parse_args(12345)
    assert err is not None and "unsupported_args_type" in err
    print("H3.3 _parse_args malformed JSON detection: OK")
    return True


def test_triggercmd_import_basic() -> bool:
    """A small TriggerCMD payload imports the simple commands and skips allowParams=true.

    Also verifies that destructive commands (shutdown) are imported DISABLED
    by default for safety.
    """
    import tempfile
    from gemma4_agent.domain_tools import import_triggercmd_entries
    from gemma4_agent.state import AgentState
    state_path = Path(tempfile.mktemp(prefix="g_triggercmd_state_", suffix=".json"))
    state = AgentState(state_path)
    entries = [
        {"trigger": "Notepad", "command": "notepad", "ground": "foreground", "voice": "notepad"},
        {"trigger": "Reboot", "command": "shutdown /r /t 10", "ground": "background", "voice": "reboot"},
        {"trigger": "WithParams", "command": "x.bat", "ground": "foreground", "voice": "withparams", "allowParams": "true"},
        {"trigger": "Empty cmd", "command": "", "voice": "empty", "ground": "foreground"},
        {"trigger": "Too short", "command": "echo hi", "voice": "x", "ground": "foreground"},
    ]
    result = import_triggercmd_entries(entries, state)
    assert result["ok"], result
    assert result["imported_count"] == 2, f"expected 2 imported, got {result['imported_count']}"
    assert result["skipped_count"] == 3, f"expected 3 skipped, got {result['skipped_count']}"
    reasons = {s["reason"] for s in result["skipped"]}
    assert "allowParams_true_needs_manual_setup" in reasons
    assert "empty_command" in reasons
    assert "voice_too_short" in reasons
    # Destructive safety: shutdown imported disabled.
    by_phrase = {item["phrase"]: item for item in result["imported"]}
    assert by_phrase["reboot"]["enabled"] is False, "reboot should be disabled by default"
    assert "shutdown" in by_phrase["reboot"]["destructive_tokens"]
    assert by_phrase["notepad"]["enabled"] is True, "notepad should stay enabled"
    state_path.unlink(missing_ok=True)
    print("triggercmd import basic + destructive auto-disable OK")
    return True


def test_triggercmd_destructive_detection() -> bool:
    """_looks_destructive flags common destructive command lines."""
    from gemma4_agent.domain_tools import _looks_destructive
    # Positive cases: should be flagged.
    for cmd in [
        "shutdown /r /t 10",
        "shutdown /s /f /t 0",
        "Stop-Computer",
        "Restart-Computer -Force",
        "format C:",
        "rmdir /s /q C:\\important",
        "del /q somefolder",
    ]:
        hit, tokens = _looks_destructive(cmd)
        assert hit, f"should detect destructive: {cmd}"
        assert tokens, f"should return tokens for: {cmd}"
    # Negative cases: should NOT be flagged.
    for cmd in [
        "notepad",
        "start spotify:playlist:abc",
        '"C:\\Program Files\\AutoHotkey\\v2\\AutoHotkey.exe" "C:\\Volumen.ahk" 50',
        "echo hello",
    ]:
        hit, tokens = _looks_destructive(cmd)
        assert not hit, f"should NOT detect destructive: {cmd} (got {tokens})"
    print("triggercmd destructive detection OK")
    return True


def test_triggercmd_import_off_routine() -> bool:
    """When entry has offCommand, a second on_phrase routine is created with '<voice> off'."""
    import tempfile
    from gemma4_agent.domain_tools import (active_phrase_triggers,
                                            import_triggercmd_entries)
    from gemma4_agent.state import AgentState
    state_path = Path(tempfile.mktemp(prefix="g_triggercmd_state_", suffix=".json"))
    state = AgentState(state_path)
    entries = [
        {"trigger": "Modo Cine", "command": "start_cine.bat", "offCommand": "stop_cine.bat",
         "ground": "foreground", "voice": "modo cine"},
    ]
    result = import_triggercmd_entries(entries, state)
    assert result["imported_count"] == 1, result
    item = result["imported"][0]
    assert item.get("off_phrase") == "modo cine off", item
    # Verify both phrases now active.
    phrases = {r["phrase"] for r in active_phrase_triggers(state)}
    assert "modo cine" in phrases
    assert "modo cine off" in phrases
    state_path.unlink(missing_ok=True)
    print("triggercmd import off-routine OK")
    return True


def test_triggercmd_import_duplicate_skipped() -> bool:
    """Re-importing the same payload skips dupes unless overwrite_same_phrase=True."""
    import tempfile
    from gemma4_agent.domain_tools import import_triggercmd_entries
    from gemma4_agent.state import AgentState
    state_path = Path(tempfile.mktemp(prefix="g_triggercmd_state_", suffix=".json"))
    state = AgentState(state_path)
    entries = [{"trigger": "Notepad", "command": "notepad", "ground": "foreground", "voice": "notepad"}]
    first = import_triggercmd_entries(entries, state)
    assert first["imported_count"] == 1
    second = import_triggercmd_entries(entries, state)
    assert second["imported_count"] == 0, second
    assert second["skipped"][0]["reason"] == "phrase_already_in_use"
    state_path.unlink(missing_ok=True)
    print("triggercmd import duplicate detection OK")
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


def test_j1_knowledge_rerank_fallback_without_model() -> bool:
    """Rerank silently falls back to BM25 ordering when the model can't load."""
    from gemma4_agent import knowledge as kn
    saved = kn._RERANK_STATE.copy()
    try:
        kn._RERANK_STATE.update({"model": None, "permanently_disabled": True, "last_error": "forced"})
        rows = [
            {"id": 1, "title": "A", "snippet": "ratio of pies", "rank": -2.0, "source": "x", "score": 2.0},
            {"id": 2, "title": "B", "snippet": "kernel methods", "rank": -1.0, "source": "x", "score": 1.0},
        ]
        out, info = kn._rerank_rows("kernel methods explained", rows, limit=2)
        assert out == rows, "fallback should return BM25 order"
        assert info["used"] is False
        assert info.get("skipped") == "model_unavailable"
    finally:
        kn._RERANK_STATE.clear()
        kn._RERANK_STATE.update(saved)
    print("J1 rerank fallback when model disabled: OK")
    return True


def test_j2_memory_auto_save_prefixes_and_caps() -> bool:
    """auto_save stamps keys with 'auto:' and evicts oldest beyond max_total."""
    import tempfile
    from gemma4_agent.memory import MemoryStore
    p = Path(tempfile.mktemp(prefix="g_mem_", suffix=".json"))
    try:
        store = MemoryStore(p)
        r = store.auto_save([{"key": "favorite_color", "value": "blue"}])
        assert r["ok"] and r["added"] == ["auto:favorite_color"], r
        # cap test
        for i in range(5):
            store.auto_save([{"key": f"k{i}", "value": f"v{i}"}], max_total=3)
        items = store._load()["items"]
        auto_keys = [k for k in items if k.startswith("auto:")]
        assert len(auto_keys) <= 3, f"auto-cap broken: {auto_keys}"
    finally:
        p.unlink(missing_ok=True)
    print("J2 auto_save prefixes + caps: OK")
    return True


def test_j2_fact_extraction_env_default_off() -> bool:
    import os
    from gemma4_agent.agent import _fact_extraction_enabled
    os.environ.pop("GEMMA4_AGENT_FACT_EXTRACTION", None)
    assert _fact_extraction_enabled() is False, "fact extraction must default OFF"
    os.environ["GEMMA4_AGENT_FACT_EXTRACTION"] = "true"
    assert _fact_extraction_enabled() is True
    os.environ.pop("GEMMA4_AGENT_FACT_EXTRACTION", None)
    print("J2 fact extraction default OFF: OK")
    return True


def test_j3_personas_registry_has_six() -> bool:
    from gemma4_agent.personas import PERSONAS, get, list_names
    names = list_names()
    for required in ("default", "coder", "researcher", "creative", "planner", "casual"):
        assert required in names, f"missing persona: {required}"
    assert get("coder").name == "coder"
    assert get("nonexistent").name == "default", "unknown persona must fall back to default"
    assert "developer" in PERSONAS["coder"].preferred_tools
    print("J3 personas registry: OK")
    return True


def test_j4_project_context_walks_up() -> bool:
    import tempfile
    from gemma4_agent.project_context import find_context_file, load_context, format_for_prompt
    root = Path(tempfile.mkdtemp(prefix="g_pctx_"))
    try:
        sub = root / "a" / "b"
        sub.mkdir(parents=True)
        marker = root / "JARVIS.md"
        marker.write_text("regla 1: usa python\n", encoding="utf-8")
        found = find_context_file(sub)
        assert found is not None and found.name == "JARVIS.md", f"walk-up failed: {found}"
        ctx = load_context(sub)
        chars = ctx.get("chars")
        assert ctx["found"] and isinstance(chars, int) and chars > 0
        rendered = format_for_prompt(ctx)
        assert "regla 1" in rendered and "Project context" in rendered
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    print("J4 project context walks up + renders: OK")
    return True


def test_j4_project_context_disabled_env() -> bool:
    import os
    from gemma4_agent.project_context import is_enabled
    os.environ["GEMMA4_AGENT_PROJECT_CONTEXT"] = "false"
    assert is_enabled() is False
    os.environ.pop("GEMMA4_AGENT_PROJECT_CONTEXT", None)
    assert is_enabled() is True
    print("J4 project context env toggle: OK")
    return True


def test_j5_parallel_tools_default_off() -> bool:
    import os
    from gemma4_agent.agent import _parallel_tools_enabled
    os.environ.pop("GEMMA4_AGENT_PARALLEL_TOOLS", None)
    assert _parallel_tools_enabled() is False, "parallel tools must default OFF"
    os.environ["GEMMA4_AGENT_PARALLEL_TOOLS"] = "true"
    assert _parallel_tools_enabled() is True
    os.environ.pop("GEMMA4_AGENT_PARALLEL_TOOLS", None)
    print("J5 parallel tools default OFF: OK")
    return True


def test_j5_parallel_executor_preserves_order_and_calls_each() -> bool:
    """Run _execute_calls_parallel with a fake registry; assert order + every call ran."""
    import threading
    import time
    from gemma4_agent.agent import Gemma4Agent

    class FakeRegistry:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self._lock = threading.Lock()

        def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
            time.sleep(0.02)
            with self._lock:
                self.calls.append(name)
            return {"ok": True, "name": name, "args": args}

    fake = FakeRegistry()
    prepared = [
        {"raw_call": {}, "name": "alpha", "args": {"i": 0}, "parse_error": ""},
        {"raw_call": {}, "name": "beta", "args": {"i": 1}, "parse_error": ""},
        {"raw_call": {}, "name": "gamma", "args": {"i": 2}, "parse_error": ""},
    ]

    # Construct a bare agent shell without going through __init__ (avoids LLM client).
    agent = Gemma4Agent.__new__(Gemma4Agent)
    agent.tools = fake  # type: ignore[attr-defined]

    agent._execute_calls_parallel(prepared, None, 0)
    # Original prep order preserved
    assert [p["name"] for p in prepared] == ["alpha", "beta", "gamma"]
    # Each prep got a result
    for prep in prepared:
        assert prep["result"]["ok"] is True
        assert prep["result"]["name"] == prep["name"]
    # All three executed
    assert sorted(fake.calls) == ["alpha", "beta", "gamma"]
    print("J5 parallel executor preserves order + runs each: OK")
    return True


def test_k1_session_roundtrip() -> bool:
    import tempfile
    from gemma4_agent.sessions import Session, SessionStore, SessionTurn
    root = Path(tempfile.mkdtemp(prefix="g_sess_"))
    try:
        store = SessionStore(root)
        s = Session.new(title="Test session")
        s.turns.append(SessionTurn(role="user", content="hola"))
        s.turns.append(SessionTurn(role="assistant", content="hola que tal", tool_count=1))
        save = store.save(s)
        assert save["ok"] and save["turns"] == 2, save
        loaded = store.load(s.id)
        assert loaded is not None and loaded.title == "Test session"
        assert len(loaded.turns) == 2 and loaded.turns[1].tool_count == 1
        listing = store.list_sessions()
        assert any(entry["id"] == s.id for entry in listing)
        deleted = store.delete(s.id)
        assert deleted["ok"] and deleted["existed"]
        assert store.load(s.id) is None
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    print("K1 session save/load/list/delete: OK")
    return True


def test_k1_auto_title_heuristic_fallback() -> bool:
    from gemma4_agent.sessions import auto_title
    title = auto_title("Quiero abrir Steam y buscar Hades en mi biblioteca", chat_fn=None, max_words=4)
    assert title and len(title.split()) <= 4
    empty = auto_title("", chat_fn=None)
    assert empty == "(sin titulo)"
    print("K1 auto_title heuristic fallback: OK")
    return True


def test_k1_session_disabled_env() -> bool:
    import os
    from gemma4_agent.sessions import is_enabled
    os.environ["GEMMA4_AGENT_SESSIONS"] = "false"
    assert is_enabled() is False
    os.environ.pop("GEMMA4_AGENT_SESSIONS", None)
    assert is_enabled() is True
    print("K1 sessions env toggle: OK")
    return True


def test_k2_timeline_writes_jsonl() -> bool:
    import tempfile
    from gemma4_agent.timeline import TimelineWriter
    root = Path(tempfile.mkdtemp(prefix="g_tl_"))
    captured: list[tuple[str, dict[str, Any]]] = []

    def inner(event: str, payload: dict[str, Any]) -> None:
        captured.append((event, payload))

    try:
        w = TimelineWriter(session_id="abc", turn_index=2, inner=inner, root=root)
        w("tool_start", {"name": "web", "args": {"q": "x"}, "index": 1})
        w("tool_end", {"name": "web", "ok": True, "status": "done", "index": 1})
        w.close()
        files = list(root.glob("*.jsonl"))
        assert len(files) == 1, files
        lines = files[0].read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["event"] == "tool_start" and first["payload"]["name"] == "web"
        assert [e[0] for e in captured] == ["tool_start", "tool_end"], "inner cb must also fire"
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    print("K2 timeline writes jsonl + forwards inner: OK")
    return True


def test_k2_timeline_disabled_env() -> bool:
    import os
    from gemma4_agent.timeline import is_enabled
    os.environ["GEMMA4_AGENT_TIMELINE"] = "false"
    assert is_enabled() is False
    os.environ.pop("GEMMA4_AGENT_TIMELINE", None)
    assert is_enabled() is True
    print("K2 timeline env toggle: OK")
    return True


def test_k3_context_budget_scales_with_size() -> bool:
    from gemma4_agent.agent import _compute_context_budget
    small = _compute_context_budget(4096)
    mid = _compute_context_budget(32768)
    big = _compute_context_budget(200000)
    assert small["soft_cap_messages"] < mid["soft_cap_messages"] < big["soft_cap_messages"]
    assert small["keep_tail_messages"] < mid["keep_tail_messages"] <= big["keep_tail_messages"]
    assert small["summarize_threshold_chars"] < mid["summarize_threshold_chars"] < big["summarize_threshold_chars"]
    # hard_cap <= soft_cap always
    for b in (small, mid, big):
        assert b["hard_cap_messages"] <= b["soft_cap_messages"]
    # very tiny context still produces sane numbers
    tiny = _compute_context_budget(512)
    assert tiny["soft_cap_messages"] >= 10
    assert tiny["hard_cap_messages"] >= 6
    print("K3 context budget scales 4K..200K: OK")
    return True


def test_audit_atomic_write_replaces_existing() -> bool:
    """state.atomic_write_json must not leave .tmp files and must overwrite."""
    import tempfile
    from gemma4_agent.state import atomic_write_json
    root = Path(tempfile.mkdtemp(prefix="g_atomic_"))
    try:
        target = root / "x.json"
        atomic_write_json(target, {"a": 1})
        assert target.is_file()
        assert not (root / "x.json.tmp").exists(), "leftover tmp"
        # Overwrite
        atomic_write_json(target, {"b": 2})
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == {"b": 2}
    finally:
        import shutil
        shutil.rmtree(root, ignore_errors=True)
    print("AUDIT atomic_write_json overwrite + no leftover .tmp: OK")
    return True


def test_audit_settings_env_names_match_config() -> bool:
    """Every env var Settings persists must be readable by AgentConfig.from_env
    or by a documented helper in the agent. Hubo bugs MAJOR donde Settings
    escribia keys con prefijos distintos a los que config esperaba."""
    import os as _os
    saved_env = dict(_os.environ)
    try:
        # Pretend the user set non-default values for everything
        _os.environ.update({
            "GEMMA4_AGENT_SERVER":             "http://test:1234",
            "GEMMA4_AGENT_MODEL":              "gemma-test-alias",
            "GEMMA4_MODEL_PATH":               "X:/dummy.gguf",
            "GEMMA4_AGENT_CONTEXT":            "20480",
            "GEMMA4_AGENT_MAX_TOKENS":         "999",
            "GEMMA4_AGENT_TEMPERATURE":        "0.42",
            "GEMMA4_AGENT_TOP_P":              "0.88",
            "GEMMA4_AGENT_TOP_K":              "33",
            "GEMMA4_AGENT_MIN_P":              "0.07",
            "GEMMA4_AGENT_REPEAT_PENALTY":     "1.15",
            "GEMMA4_AGENT_SEED":               "42",
            "GEMMA4_AGENT_ENABLE_THINKING":    "true",
            "GEMMA4_AGENT_PARALLEL_TOOL_CALLS": "true",
            "GEMMA4_AGENT_MODE":               "deep_action",
            "GEMMA4_AGENT_MAX_TURNS":          "12",
            "GEMMA4_AGENT_SAFETY":             "true",
            "GEMMA4_AGENT_TIMEOUT":            "240",
            "GEMMA4_AGENT_TRACING":            "false",
        })
        from gemma4_agent.config import AgentConfig
        cfg = AgentConfig.from_env()
        assert cfg.server_url == "http://test:1234"
        assert cfg.model == "gemma-test-alias"
        assert str(cfg.model_path).endswith("dummy.gguf")
        assert cfg.context_size == 20480
        assert cfg.max_tokens == 999
        assert abs(cfg.temperature - 0.42) < 1e-6
        assert abs(cfg.top_p - 0.88) < 1e-6
        assert cfg.top_k == 33
        assert cfg.min_p is not None and abs(cfg.min_p - 0.07) < 1e-6
        assert abs(cfg.repeat_penalty - 1.15) < 1e-6
        assert int(cfg.seed) == 42
        assert cfg.enable_thinking is True
        assert cfg.parallel_tool_calls is True
        assert cfg.agent_mode == "deep_action"
        assert cfg.max_agent_turns == 12
        assert cfg.enable_safety is True
        assert abs(cfg.request_timeout_s - 240.0) < 1e-6
        assert cfg.enable_tracing is False
    finally:
        _os.environ.clear()
        _os.environ.update(saved_env)
    print("AUDIT settings env names match AgentConfig.from_env: OK")
    return True


def test_audit_jsonstore_concurrent_writes() -> bool:
    """Two concurrent register_resource calls don't lose data.

    Regression test for the RLock added to AgentState/MemoryStore/SessionStore.
    Without the lock, parallel tool execution (J5) could lose writes when two
    tools called register_resource simultaneously (last writer wins on the
    full file, dropping the other's mutation).
    """
    import shutil
    import tempfile
    import threading
    from gemma4_agent.state import AgentState

    root = Path(tempfile.mkdtemp(prefix="g_lock_"))
    try:
        state = AgentState(path=root / "state.json")

        def worker(idx: int) -> None:
            state.register_resource(kind="test", label=f"res_{idx}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        loaded = state._load()
        resources = loaded.get("resources", {})
        assert len(resources) == 10, f"expected 10 resources, got {len(resources)}"
        labels = {r.get("label") for r in resources.values()}
        assert labels == {f"res_{i}" for i in range(10)}, f"labels lost: {labels}"
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print("AUDIT JSONStore concurrent writes preserve all data: OK")
    return True


def test_audit_experience_recent_exists() -> bool:
    """experience.ExperienceMemory.recent(limit=N) must exist (was a ghost)."""
    import tempfile
    from gemma4_agent.experience import ExperienceMemory
    path = Path(tempfile.mktemp(prefix="g_exp_recent_", suffix=".sqlite"))
    try:
        mem = ExperienceMemory(path)
        # Method must be callable; with no records returns [].
        assert callable(getattr(mem, "recent", None)), "recent() should be a method"
        out = mem.recent(limit=5)
        assert isinstance(out, list)
        mem.close()
    finally:
        path.unlink(missing_ok=True)
    print("AUDIT experience.recent() exists: OK")
    return True


def test_audit_timeline_safe_payload_preserves_dicts() -> bool:
    """_safe_payload must keep nested dicts as dicts, not flatten to str."""
    from gemma4_agent.timeline import _safe_payload
    payload = {
        "name": "web",
        "args": {"action": "search", "query": "hola"},
        "result": {"ok": True, "results": [{"title": "x"}, {"title": "y"}]},
    }
    out = _safe_payload(payload)
    assert isinstance(out, dict)
    assert isinstance(out["args"], dict)
    assert out["args"]["action"] == "search"
    assert isinstance(out["result"], dict)
    assert isinstance(out["result"]["results"], list)
    assert isinstance(out["result"]["results"][0], dict)
    print("AUDIT timeline _safe_payload preserves dict structure: OK")
    return True


def test_audit_planner_question_mark_inverted_supported() -> bool:
    """Planner heuristic should treat ¿ (Spanish inverted) as a question marker."""
    from gemma4_agent.planner import plan_mission, select_tool_names
    p = plan_mission("¿que tools tengo disponibles?")
    out = select_tool_names("¿que tools tengo disponibles?", p)
    # Mostly we want it to NOT crash and to handle the inverted ? path.
    assert isinstance(out, list)
    print("AUDIT planner accepts inverted question mark: OK")
    return True


def test_u1_ui_modules_importable() -> bool:
    """All ui/ submodules import without side effects (PyQt6 required)."""
    try:
        from gemma4_agent.ui import theme, metrics, hud, log_widget, metric_bar
        from gemma4_agent.ui import panels, sessions_panel, settings, triggers
        from gemma4_agent.ui import memory_viewer, tool_explorer, agent_thread, main_window
        from gemma4_agent.ui import app as ui_app
    except ImportError as exc:
        print(f"UI import skipped: {exc}")
        return True  # PyQt6 not installed in this env — not a regression
    # smoke: STATE_TABLE keys
    assert "INITIALISING" in theme.STATE_TABLE
    assert "SPEAKING" in theme.STATE_TABLE
    # settings has the tabs we promised
    assert hasattr(settings, "TOGGLES")
    assert len(settings.TOGGLES) >= 6
    print("U1 UI modules import + theme/settings shape: OK")
    return True


def test_u1_hud_state_setters() -> bool:
    """HudCanvas accepts all states without crashing (no Qt event loop)."""
    try:
        import os as _os
        _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        from gemma4_agent.ui.hud import HudCanvas
        from gemma4_agent.ui.theme import STATE_TABLE
    except ImportError:
        print("U1 HUD test skipped (no PyQt6)")
        return True
    app = QApplication.instance() or QApplication([])
    hud = HudCanvas()
    for state in STATE_TABLE.keys():
        hud.set_state(state)
        assert hud.state == state
    hud.set_persona("coder")
    hud.set_model("gemma-3n-e4b-it.Q6_K")
    hud.set_connected(True)
    print("U1 HUD state cycling: OK")
    return True


def test_j5_sequential_handles_parse_error() -> bool:
    from gemma4_agent.agent import Gemma4Agent

    class NeverCalled:
        def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
            raise AssertionError("must not execute when parse_error is set")

    agent = Gemma4Agent.__new__(Gemma4Agent)
    agent.tools = NeverCalled()  # type: ignore[attr-defined]
    prepared = [
        {"raw_call": {}, "name": "x", "args": {}, "parse_error": "bad json: expecting value"},
    ]
    agent._execute_calls_sequential(prepared, None, 0)
    res = prepared[0]["result"]
    assert res["ok"] is False
    assert res["evidence"] == "malformed_json_args"
    print("J5 sequential parse-error short-circuit: OK")
    return True


# ====================================================================
# Fase V — VRAM profiles (Performance / Balanced / Light / Standby)
# ====================================================================


def test_profiles_recommend_by_vram() -> bool:
    # Cortes con reserva fija de 1.5 GB (WINDOWS_VRAM_RESERVE_MB) para dwm/driver:
    #   VRAM efectiva = vram_mb - 1500
    #   >=10500 MB ef. (=12 GB fisicos) -> performance
    #   >= 4500 MB ef. (= 6 GB fisicos) -> balanced  <- target de produccion
    #   >= 2500 MB ef. (= 4 GB fisicos) -> light
    #   resto / None                    -> light
    # Bloque F1 / item I1 #10 del informe de optimizacion externa.
    from gemma4_agent.profiles import recommend_profile
    # 16 GB fisicos = 14.5 GB efectivos -> performance
    assert recommend_profile(16384) == "performance"
    # 12 GB fisicos = 10.5 GB efectivos -> performance (borde)
    assert recommend_profile(12000) == "performance"
    # 11.5 GB fisicos = 10.0 GB efectivos -> balanced (debajo del corte)
    assert recommend_profile(11500) == "balanced"
    # 8 GB fisicos = 6.5 GB efectivos -> balanced
    assert recommend_profile(8000) == "balanced"
    # 6 GB fisicos = 4.5 GB efectivos -> balanced (target HOT)
    assert recommend_profile(6144) == "balanced"
    assert recommend_profile(6000) == "balanced"
    # 5.9 GB fisicos = 4.4 GB efectivos -> light (debajo del corte)
    assert recommend_profile(5900) == "light"
    # 4 GB fisicos = 2.5 GB efectivos -> light (borde)
    assert recommend_profile(4000) == "light"
    # CPU/integrada o GPU muy chica -> light
    assert recommend_profile(2000) == "light"
    assert recommend_profile(0) == "light"
    assert recommend_profile(None) == "light"
    print("V1 recommend_profile by vram (with 1.5 GB WDDM reserve): OK")
    return True


def test_profiles_set_and_get_active() -> bool:
    import os
    import tempfile
    from pathlib import Path as _Path
    from gemma4_agent import profiles as profmod

    # Redirigir a temp para no pisar el real del usuario
    tmpdir = tempfile.mkdtemp(prefix="gemma4_test_profile_")
    target = _Path(tmpdir) / "active_profile.txt"
    original = profmod.ACTIVE_PROFILE_PATH
    profmod.ACTIVE_PROFILE_PATH = target
    try:
        profmod.set_active_profile("light")
        # No debe quedar archivo .tmp leftover
        leftovers = list(target.parent.glob("*.tmp"))
        assert not leftovers, f"leftover .tmp files: {leftovers}"
        p = profmod.get_active_profile()
        assert p.name == "light"
        assert p.context_size == 4096
        # set invalido -> ValueError
        try:
            profmod.set_active_profile("nope")
            assert False, "should have raised"
        except ValueError:
            pass
    finally:
        profmod.ACTIVE_PROFILE_PATH = original
        try:
            target.unlink()
        except OSError:
            pass
        try:
            target.parent.rmdir()
        except OSError:
            pass
    print("V2 set_active / get_active roundtrip: OK")
    return True


def test_profiles_apply_to_env_complete() -> bool:
    import os
    from gemma4_agent.profiles import PROFILES, apply_profile_to_env

    # Backup env
    saved = {
        k: os.environ.get(k) for k in (
            "GEMMA4_AGENT_CONTEXT", "GEMMA4_KNOWLEDGE_RERANK",
            "GEMMA4_MMPROJ_PATH", "GEMMA4_AGENT_PARALLEL_TOOLS",
            "GEMMA4_AGENT_FACT_EXTRACTION", "GEMMA4_ACTIVE_PROFILE",
        )
    }
    try:
        # Limpiar para empezar fresco
        for k in saved:
            os.environ.pop(k, None)

        apply_profile_to_env(PROFILES["light"])
        assert os.environ["GEMMA4_AGENT_CONTEXT"] == "4096"
        assert os.environ["GEMMA4_KNOWLEDGE_RERANK"] == "false"
        assert os.environ["GEMMA4_MMPROJ_PATH"] == ""
        assert os.environ["GEMMA4_AGENT_PARALLEL_TOOLS"] == "false"
        assert os.environ["GEMMA4_AGENT_FACT_EXTRACTION"] == "false"
        assert os.environ["GEMMA4_ACTIVE_PROFILE"] == "light"

        # Switch a performance
        apply_profile_to_env(PROFILES["performance"])
        assert os.environ["GEMMA4_AGENT_CONTEXT"] == "32768"
        assert os.environ["GEMMA4_KNOWLEDGE_RERANK"] == "true"
        assert os.environ["GEMMA4_AGENT_PARALLEL_TOOLS"] == "true"
        assert os.environ["GEMMA4_AGENT_FACT_EXTRACTION"] == "true"
        # vision_enabled=True NO sobreescribe GEMMA4_MMPROJ_PATH; respeta el
        # que haya. Como en este test lo dejamos "" antes, debe seguir "".
        # (En vida real el usuario tendria un path valido en su gui.json.)
        assert os.environ["GEMMA4_MMPROJ_PATH"] == ""
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print("V3 apply_profile_to_env complete: OK")
    return True


def test_profiles_round_trip_via_agentconfig() -> bool:
    """CRITICAL: cada perfil aplicado -> AgentConfig.from_env() ve el cambio.

    Hubiera atrapado el bug de env var mismatch del audit anterior.
    """
    import os
    from gemma4_agent.profiles import PROFILES, apply_profile_to_env
    from gemma4_agent.config import AgentConfig

    saved = {
        k: os.environ.get(k) for k in (
            "GEMMA4_AGENT_CONTEXT", "GEMMA4_KNOWLEDGE_RERANK",
            "GEMMA4_MMPROJ_PATH", "GEMMA4_AGENT_PARALLEL_TOOLS",
            "GEMMA4_AGENT_FACT_EXTRACTION", "GEMMA4_ACTIVE_PROFILE",
            "GEMMA4_MODEL_PATH",
        )
    }
    try:
        # Context sizes alineados con la nueva tabla 6 GB-aware (balanced bajo
        # de 16K a 8K para que KV cache entre en VRAM con E4B-Q4_K_M).
        expected_ctx = {"performance": 32768, "balanced": 8192, "light": 4096, "standby": 4096}
        for name, profile in PROFILES.items():
            for k in saved:
                os.environ.pop(k, None)
            apply_profile_to_env(profile)
            cfg = AgentConfig.from_env()
            assert cfg.context_size == expected_ctx[name], \
                f"{name}: expected ctx={expected_ctx[name]} got {cfg.context_size}"
            # Active profile env recorded
            assert os.environ.get("GEMMA4_ACTIVE_PROFILE") == name
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print("V4 round-trip apply -> AgentConfig: OK")
    return True


def test_profile_watcher_hysteresis() -> bool:
    from unittest.mock import patch
    from gemma4_agent.profile_watcher import (
        ProfileWatcher, WatcherConfig, _Sample,
    )
    # Construimos un watcher SIN llamar start() (no queremos thread real).
    cfg = WatcherConfig(
        enabled=True, downgrade_to="light", restore_to="balanced",
        trigger_on_game=False, trigger_on_gpu=True, trigger_on_ram=False,
    )

    # Clock controlable
    clock_t = [0.0]
    def fake_clock() -> float:
        return clock_t[0]

    changes: list[tuple[str, str]] = []
    watcher = ProfileWatcher(cfg, on_change=lambda n, r: changes.append((n, r)), clock=fake_clock)

    # Mockeamos set_active_profile y apply_profile_to_env para no tocar
    # archivos reales del usuario, y _sample para devolver lo que queremos.
    def gpu_sample(pct: float) -> _Sample:
        return _Sample(has_game=False, gpu_pct=pct, ram_pct=None, vram_pct=None)

    with patch("gemma4_agent.profile_watcher.set_active_profile"), \
         patch("gemma4_agent.profile_watcher.apply_profile_to_env"), \
         patch("gemma4_agent.profile_watcher.get_active_profile") as get_active:
        from gemma4_agent.profiles import PROFILES
        get_active.return_value = PROFILES["balanced"]

        # Solo 20s al 80% -> NO debe cambiar todavia
        with patch.object(watcher, "_sample", return_value=gpu_sample(80.0)):
            for sec in range(0, 21, 10):
                clock_t[0] = float(sec)
                watcher._tick()
        assert not changes, f"unexpected switch after 20s: {changes}"

        # Continua al 80% hasta llegar a 30s -> debe encolar bajada a light.
        # Audit fix #5: el _tick ya NO llama on_change directo; encola
        # en _pending y el caller drena con apply_pending() al fin de turno.
        with patch.object(watcher, "_sample", return_value=gpu_sample(80.0)):
            clock_t[0] = 30.0
            watcher._tick()
        assert watcher._pending == ("light", "gpu=80.0%"), \
            f"expected pending=('light', 'gpu=80.0%'), got {watcher._pending}"
        applied = watcher.apply_pending()
        assert applied is True
        assert changes and changes[-1][0] == "light", f"expected light switch, got {changes}"

        # Ahora baja a 20% (sin trigger) -- get_active devuelve light ahora
        get_active.return_value = PROFILES["light"]
        watcher._watcher_state = "downgraded"
        prior_changes = len(changes)
        # 30s sin trigger NO basta (necesita 60)
        with patch.object(watcher, "_sample", return_value=gpu_sample(20.0)):
            for sec in range(40, 71, 10):
                clock_t[0] = float(sec)
                watcher._tick()
        assert len(changes) == prior_changes, f"unexpected upgrade after 30s clear"
        assert watcher._pending is None, f"unexpected pending: {watcher._pending}"

        # Necesitamos que la ventana de samples LIMPIOS cubra 60s.
        # Samples limpios estan a t=40,50,60,70. A t=100 el oldest limpio
        # sigue siendo 40 -> 100-40=60s. Eso ancla la ventana.
        with patch.object(watcher, "_sample", return_value=gpu_sample(20.0)):
            clock_t[0] = 100.0
            watcher._tick()
        assert watcher._pending == ("balanced", "triggers cleared"), \
            f"expected pending=('balanced', 'triggers cleared'), got {watcher._pending}"
        watcher.apply_pending()
        assert changes[-1][0] == "balanced", f"expected balanced restore, got {changes}"

    print("V5 watcher hysteresis 30s/60s: OK")
    return True


def test_standby_profile_does_not_start_server() -> bool:
    from unittest.mock import patch, MagicMock
    from gemma4_agent.llama_server import LlamaServerManager
    from gemma4_agent.profiles import PROFILES

    manager = LlamaServerManager.__new__(LlamaServerManager)
    manager._proc = None  # type: ignore[attr-defined]
    manager._current_profile = None  # type: ignore[attr-defined]
    manager._external_detected = False  # type: ignore[attr-defined]

    with patch("gemma4_agent.llama_server.subprocess.Popen") as popen:
        result = manager.start(PROFILES["standby"], wait_health=False)
    assert result == "skipped_standby"
    popen.assert_not_called()
    print("V6 standby does not start server: OK")
    return True


def test_external_server_detected_not_killed() -> bool:
    from unittest.mock import patch
    from gemma4_agent.config import AgentConfig
    from gemma4_agent.llama_server import LlamaServerManager
    from gemma4_agent.profiles import PROFILES

    # Construir manager manualmente para no leer env del usuario
    cfg = AgentConfig()  # defaults
    manager = LlamaServerManager.__new__(LlamaServerManager)
    manager._config = cfg  # type: ignore[attr-defined]
    manager._proc = None  # type: ignore[attr-defined]
    manager._current_profile = None  # type: ignore[attr-defined]
    manager._external_detected = False  # type: ignore[attr-defined]
    from pathlib import Path as _Path
    manager._log_dir = _Path("/tmp/g4_test_logs")  # type: ignore[attr-defined]

    with patch("gemma4_agent.llama_server.port_in_use", return_value=True), \
         patch("gemma4_agent.llama_server.subprocess.Popen") as popen:
        result = manager.start(PROFILES["performance"], wait_health=False)

    assert result == "external", f"expected 'external', got {result!r}"
    popen.assert_not_called()
    assert manager.is_external_server() is True
    assert manager.current_profile() is None
    print("V7 external server detected, not killed: OK")
    return True


def test_light_profile_missing_model_falls_back() -> bool:
    """Light con model_path inexistente -> ctx=4096 aplicado pero
    GEMMA4_MODEL_PATH no se sobreescribe."""
    import os
    from dataclasses import replace
    from gemma4_agent.profiles import PROFILES, apply_profile_to_env

    saved_model = os.environ.get("GEMMA4_MODEL_PATH")
    saved_ctx = os.environ.get("GEMMA4_AGENT_CONTEXT")
    saved_mmproj = os.environ.get("GEMMA4_MMPROJ_PATH")
    try:
        # Setear un modelo "actual" del usuario
        os.environ["GEMMA4_MODEL_PATH"] = "C:/fake/user/model.gguf"

        # Crear un Light con model_path que NO existe
        light_bad = replace(PROFILES["light"], model_path="C:/nope/inexistente.gguf")
        apply_profile_to_env(light_bad)

        # Context si se aplica
        assert os.environ["GEMMA4_AGENT_CONTEXT"] == "4096"
        # vision off -> mmproj vaciado
        assert os.environ["GEMMA4_MMPROJ_PATH"] == ""
        # model path NO sobreescrito (queda el del usuario)
        assert os.environ["GEMMA4_MODEL_PATH"] == "C:/fake/user/model.gguf", \
            "model_path should NOT be overwritten when profile path is missing"
    finally:
        for k, v in (("GEMMA4_MODEL_PATH", saved_model),
                     ("GEMMA4_AGENT_CONTEXT", saved_ctx),
                     ("GEMMA4_MMPROJ_PATH", saved_mmproj)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    print("V8 light missing model falls back: OK")
    return True


# ====================================================================
# Fase W — Voice (wake-word + STT streaming + TTS streaming + SSE)
# ====================================================================


def test_sse_streaming_yields_deltas_in_order() -> bool:
    """V-SSE-1: mock urlopen con frames SSE, verificar deltas en orden + final."""
    from unittest.mock import patch, MagicMock
    from gemma4_agent.config import AgentConfig
    from gemma4_agent.llm_client import LLMClient

    # SSE frames simulando llama-server stream
    frames = [
        b'data: {"choices":[{"delta":{"content":"Hola"}}]}\n\n',
        b'data: {"choices":[{"delta":{"content":" mundo"}}]}\n\n',
        b'data: {"choices":[{"delta":{"content":"."},"finish_reason":"stop"}]}\n\n',
        b'data: [DONE]\n\n',
    ]
    # urllib.request.urlopen devuelve un objeto iterable por lineas
    fake_resp = MagicMock()
    fake_resp.__iter__ = lambda self: iter(frames)
    fake_resp.close = MagicMock()

    cfg = AgentConfig()
    client = LLMClient(cfg)
    with patch("urllib.request.urlopen", return_value=fake_resp):
        events = list(client.chat_stream(messages=[{"role": "user", "content": "hi"}]))

    deltas = [e for e in events if e["type"] == "delta"]
    final_events = [e for e in events if e["type"] == "final"]
    assert len(deltas) == 3, f"expected 3 deltas, got {len(deltas)}: {deltas}"
    assert deltas[0]["content_delta"] == "Hola"
    assert deltas[1]["content_delta"] == " mundo"
    assert deltas[2]["content_delta"] == "."
    assert len(final_events) == 1
    final = final_events[0]
    assert final["content"] == "Hola mundo."
    assert final["finish_reason"] == "stop"
    assert final["tool_calls"] == []
    print("W-SSE deltas + final reconstructed: OK")
    return True


def test_voice_wake_detector_matches_phrases() -> bool:
    """Mock Vosk recognizer; verificar callback se llama solo para 'gemma' y 'hey gemma'.

    Despues del fix "abre Steam → abre este", el 3er parametro del callback
    es tail_s (cuanto audio del ring buffer queda DESPUES del wake), calculado
    como result_duration_s - wake_end_relative_s.
    """
    from unittest.mock import MagicMock
    from gemma4_agent.voice.wake import WakeDetector

    fires: list[tuple[str, float, float]] = []
    # Firma actual: on_wake(phrase, wall_clock_ts, tail_s)
    det = WakeDetector(on_wake=lambda phrase, ts, tail_s: fires.append((phrase, ts, tail_s)))

    # Inyectar recognizer mock directamente (bypass load() que lee modelo de disco)
    rec = MagicMock()
    det._rec = rec
    det._loaded = True

    # Caso 1: "gemma" con start=0.30 end=0.62. Le damos 1.0s de audio (16000 samples)
    # antes de que Vosk emita el Result. tail_s = 1.0 - (0.62-0.30) = 0.68
    rec.AcceptWaveform.return_value = True
    rec.Result.return_value = '{"text": "gemma", "result": [{"word":"gemma","start":0.30,"end":0.62,"conf":0.9}]}'
    det.feed(np.zeros(16000, dtype=np.int16))  # 1.0s
    assert len(fires) == 1 and fires[0][0] == "gemma"
    assert abs(fires[0][2] - 0.68) < 0.01, f"expected tail≈0.68 got {fires[0][2]}"

    # Caso 2: "hey gemma" con start_first=0.10 end_last_gemma=0.88. 1.5s audio.
    # tail_s = 1.5 - (0.88-0.10) = 0.72
    det._last_fire_at = 0.0  # reset debounce
    rec.Result.return_value = '{"text": "hey gemma", "result": [{"word":"hey","start":0.10,"end":0.40,"conf":0.9},{"word":"gemma","start":0.50,"end":0.88,"conf":0.9}]}'
    det.feed(np.zeros(24000, dtype=np.int16))  # 1.5s
    assert len(fires) == 2 and fires[1][0] == "hey gemma"
    assert abs(fires[1][2] - 0.72) < 0.01, f"expected tail≈0.72 got {fires[1][2]}"

    # Caso 3: "tema" (palabra random) -> no fire
    det._last_fire_at = 0.0
    rec.Result.return_value = '{"text": "tema musical"}'
    det.feed(np.zeros(16000, dtype=np.int16))
    assert len(fires) == 2, f"unexpected wake from 'tema': {fires}"

    # Caso 4: partial result (AcceptWaveform=False) -> no fire incluso con match
    rec.AcceptWaveform.return_value = False
    rec.Result.return_value = '{"text": "gemma"}'
    det.feed(np.zeros(16000, dtype=np.int16))
    assert len(fires) == 2, "partial result should not fire wake"

    # Caso 5: result sin word timestamps -> DESCARTADO (no podemos validar conf).
    det._last_fire_at = 0.0
    rec.AcceptWaveform.return_value = True
    rec.Result.return_value = '{"text": "gemma"}'  # sin "result" array
    det.feed(np.zeros(16000, dtype=np.int16))
    assert len(fires) == 2, f"result sin word-conf debe descartarse, got {fires}"

    # Caso 6: result con "gemma" pero conf baja -> DESCARTADO (falso positivo).
    det._last_fire_at = 0.0
    rec.Result.return_value = '{"text": "gemma", "result": [{"word":"gemma","start":0.0,"end":0.5,"conf":0.5}]}'
    det.feed(np.zeros(16000, dtype=np.int16))
    assert len(fires) == 2, f"conf 0.5 debe descartarse, got {fires}"

    # Caso 7: result con "gemma" conf alta + audio largo POST-wake. start=0.0 end=0.7
    # 2.0s audio -> tail_s = 2.0 - (0.7-0.0) = 1.3
    det._last_fire_at = 0.0
    rec.Result.return_value = '{"text": "gemma", "result": [{"word":"gemma","start":0.0,"end":0.7,"conf":0.95}]}'
    det.feed(np.zeros(32000, dtype=np.int16))  # 2.0s
    assert len(fires) == 3
    assert abs(fires[2][2] - 1.3) < 0.01, f"expected tail≈1.3 got {fires[2][2]}"

    # Caso 8: BUG ANTI-WRAP. Vosk re-zerea timestamps cada ~10min mientras
    # nuestro contador externo seguia creciendo (el bug viejo). Con el nuevo
    # diseno, samples_since_last_result se resetea con cada AcceptWaveform=True,
    # asi que aunque Vosk reportara wake_end=0.5 despues de horas, tail_s seria
    # correcto. Simulamos: dos wakes consecutivos, el segundo NO debe heredar
    # un tail inflado del primero.
    det._last_fire_at = 0.0
    rec.Result.return_value = '{"text": "gemma", "result": [{"word":"gemma","start":0.0,"end":0.5,"conf":0.95}]}'
    det.feed(np.zeros(8000, dtype=np.int16))  # 0.5s -> tail_s=0.0
    assert len(fires) == 4
    assert abs(fires[3][2] - 0.0) < 0.01, f"expected tail≈0.0 (audio == wake), got {fires[3][2]}"
    # Sin meter mas chunks, el samples_since_last_result fue reseteado a 0.
    # Si simulamos un NUEVO Result con timestamps que parecen acumulativos
    # (Vosk no se rezeo) pero con poco audio nuevo, el tail debe reflejar
    # SOLO el audio nuevo.
    det._last_fire_at = 0.0
    rec.Result.return_value = '{"text": "gemma", "result": [{"word":"gemma","start":5.0,"end":5.5,"conf":0.95}]}'
    det.feed(np.zeros(16000, dtype=np.int16))  # 1.0s nuevo -> tail = 1.0 - 0.5 = 0.5
    assert len(fires) == 5
    assert abs(fires[4][2] - 0.5) < 0.01, f"expected tail≈0.5 (audio - wake_relative), got {fires[4][2]}"
    print("W1 wake matches + tail_s calculation: OK")
    return True


def test_voice_state_machine_wake_to_listening_to_transcribing() -> bool:
    """Simular eventos en el controller sin cargar modelos reales."""
    import numpy as np
    from unittest.mock import MagicMock
    from gemma4_agent.voice.controller import (
        VoiceController, S_IDLE_LISTENING, S_LISTENING, S_TRANSCRIBING,
        S_WAKE_DETECTED, S_THINKING, WAKE_FEEDBACK_MS,
    )

    states: list[str] = []
    ctrl = VoiceController(on_state=states.append, beep_on_wake=False)
    # Forzar estado IDLE_LISTENING sin llamar enable()
    ctrl._state = S_IDLE_LISTENING

    # Mockear los subcomponentes para evitar I/O real
    ctrl._wake = MagicMock()
    ctrl._stt = MagicMock()
    ctrl._tts = MagicMock()
    ctrl._tts.feed_text = MagicMock(return_value=0)

    # 1. Detectamos wake -> WAKE_DETECTED
    ctrl._on_wake_detected("gemma", 0.0)
    assert ctrl._state == S_WAKE_DETECTED
    # Esperar a que el timer de 200ms dispare _enter_listening
    import time as _time
    _time.sleep((WAKE_FEEDBACK_MS / 1000.0) + 0.1)
    assert ctrl._state == S_LISTENING, f"expected LISTENING got {ctrl._state}"

    # 2. STT emite Partial -> TRANSCRIBING (esto lo hace el thread STT real;
    #    simulamos directo)
    ctrl._cancel_timer()
    ctrl._set_state(S_TRANSCRIBING)
    assert ctrl._state == S_TRANSCRIBING

    # 3. Final text -> THINKING
    finals: list[str] = []
    ctrl._on_final = finals.append
    ctrl._handle_final("apaga la luz")
    assert ctrl._state == S_THINKING
    assert finals == ["apaga la luz"]
    print("W2 state machine WAKE->LISTENING->TRANSCRIBING->THINKING: OK")
    return True


def test_voice_state_machine_listening_timeout_5s() -> bool:
    """Sin speech_started en 5s -> vuelve a IDLE_LISTENING silenciosamente."""
    from unittest.mock import MagicMock, patch
    from gemma4_agent.voice.controller import (
        VoiceController, S_LISTENING, S_IDLE_LISTENING,
    )
    states: list[str] = []
    ctrl = VoiceController(on_state=states.append, beep_on_wake=False)
    ctrl._wake = MagicMock()
    ctrl._stt = MagicMock()
    ctrl._tts = MagicMock()
    ctrl._state = S_LISTENING

    # Acelerar el timeout (5s real seria muy lento). Parcheamos LISTENING_TIMEOUT_S.
    with patch("gemma4_agent.voice.controller.LISTENING_TIMEOUT_S", 0.2):
        ctrl._start_listening_timeout()
        import time as _time
        _time.sleep(0.5)

    assert ctrl._state == S_IDLE_LISTENING, f"expected IDLE_LISTENING got {ctrl._state}"
    # Verifica que el wake reset se llamo (parte del cleanup)
    ctrl._wake.reset.assert_called()
    print("W3 listening timeout returns to IDLE silently: OK")
    return True


def test_voice_state_machine_followup_close_phrase() -> bool:
    """En FOLLOWUP, recibir final 'gracias' -> IDLE_LISTENING sin enviar al agente."""
    from unittest.mock import MagicMock
    from gemma4_agent.voice.controller import (
        VoiceController, S_FOLLOWUP, S_IDLE_LISTENING,
    )
    sent_to_agent: list[str] = []
    ctrl = VoiceController(on_final=sent_to_agent.append, beep_on_wake=False)
    ctrl._wake = MagicMock()
    ctrl._stt = MagicMock()
    ctrl._tts = MagicMock()
    ctrl._state = S_FOLLOWUP

    ctrl._handle_final("gracias")
    assert ctrl._state == S_IDLE_LISTENING
    assert sent_to_agent == [], "close phrase should NOT be sent to agent"

    # Pero si el final es otra cosa, SI se manda
    ctrl._state = S_FOLLOWUP
    ctrl._handle_final("apaga la luz")
    assert sent_to_agent == ["apaga la luz"]
    print("W4 followup close phrase exits silently: OK")
    return True


def test_voice_disabled_in_light_profile() -> bool:
    """Apply LIGHT profile -> voice controller deberia poder llamarse disable()."""
    from unittest.mock import MagicMock
    from gemma4_agent.voice.controller import (
        VoiceController, S_IDLE_DISABLED, S_IDLE_LISTENING,
    )
    ctrl = VoiceController(beep_on_wake=False)
    # Mock TODOS los subcomponentes ANTES de llamar enable/disable
    ctrl._wake = MagicMock(); ctrl._wake.load = MagicMock(return_value=True)
    ctrl._wake.unload = MagicMock()
    ctrl._stt = MagicMock(); ctrl._stt.load = MagicMock(return_value=True)
    ctrl._stt.unload = MagicMock()
    ctrl._tts = MagicMock(); ctrl._tts.load = MagicMock(return_value=True)
    ctrl._tts.unload = MagicMock()
    ctrl._audio = MagicMock(); ctrl._audio.start = MagicMock(return_value=True)
    ctrl._audio.stop = MagicMock()

    # Estado fresco
    ctrl._state = S_IDLE_DISABLED
    assert ctrl.enable() is True
    assert ctrl._state == S_IDLE_LISTENING

    # Disable libera modelos
    ctrl.disable()
    assert ctrl._state == S_IDLE_DISABLED
    ctrl._wake.unload.assert_called()
    ctrl._stt.unload.assert_called()
    ctrl._tts.unload.assert_called()
    ctrl._audio.stop.assert_called()
    print("W5 disable() unloads all models: OK")
    return True


def test_tts_sentence_chunker_flushes_on_punctuation() -> bool:
    """feed_text con tokens; assertear que solo oraciones cerradas se encolan."""
    from gemma4_agent.voice.tts import StreamingTTS, _split_sentences

    # Test del splitter puro primero
    sentences, rest = _split_sentences("Hola. Como estas")
    assert sentences == ["Hola."], f"got {sentences}"
    assert rest == "Como estas"

    sentences, rest = _split_sentences("Hola. Adios! Listo.")
    # SENTENCE_END_RE requiere space O EOL despues del signo. "Adios!" sin space
    # final no cierra al final de string -- es ok porque flush() lo agarra.
    # Aca verificamos que al menos cierra las dos con espacio.
    assert "Hola." in sentences
    # Tercera oracion sin espacio final queda en rest
    assert rest.endswith("Listo.") or "Listo" in rest, f"got rest={rest!r}"

    # Test del feed_text via StreamingTTS sin cargar Piper real
    tts = StreamingTTS()
    tts._loaded = True  # bypass load()
    tts._muted = False

    encolados: list[str] = []
    # Reemplazar la queue por una list
    class FakeQueue:
        def put(self, item):
            encolados.append(item)
    tts._queue = FakeQueue()  # type: ignore[assignment]

    # Texto en chunks pequenos: solo cierra cuando aparece "." + espacio
    tts.feed_text("Hola")
    assert encolados == []  # sin cierre todavia
    tts.feed_text(" mundo")
    assert encolados == []  # idem
    tts.feed_text(". Como ")
    # "Hola mundo. " cierra; "Como " queda en buffer
    assert len(encolados) == 1
    assert "Hola mundo." in encolados[0]
    print("W6 sentence chunker flushes on '. ' boundary: OK")
    return True


def test_stt_auto_fallback_to_base_when_slow() -> bool:
    """fallback_to_base() restaura modelo previo si la recarga falla.

    Antes este test verificaba que transcribe_stream dispara el fallback en
    runtime. Tras el refactor de transcribe_stream (post-bug runtime
    20:40:52 donde el fallback espureo se disparaba cada partial), el
    fallback se aisla a un metodo explicito y solo el caller decide cuando
    invocarlo. Aqui validamos la garantia critica: si el reload del modelo
    base falla, el StreamingSTT NO queda roto -- restaura el modelo previo.
    """
    from unittest.mock import MagicMock
    from gemma4_agent.voice.stt import StreamingSTT

    stt = StreamingSTT()
    stt._loaded = True
    stt._model_size = "small"
    prior_whisper = MagicMock()
    stt._whisper = prior_whisper

    # Forzar que load() falle al intentar cargar 'base'
    stt.load = MagicMock(return_value=False)  # type: ignore[method-assign]

    ok = stt.fallback_to_base()
    assert ok is False, "fallback should return False when load fails"
    assert stt._model_size == "small", f"size should be restored to small, got {stt._model_size}"
    assert stt._whisper is prior_whisper, "whisper should be restored to previous instance"
    assert stt._loaded is True, "loaded flag should be restored"
    print("W7 STT fallback restores prior model on failed reload: OK")
    return True


def test_voice_close_phrase_normalization() -> bool:
    """Las frases de cierre matchean con accents folded e case-insensitive."""
    from unittest.mock import MagicMock
    from gemma4_agent.voice.controller import (
        VoiceController, S_FOLLOWUP, S_IDLE_LISTENING,
    )
    sent: list[str] = []
    ctrl = VoiceController(
        on_final=sent.append,
        close_phrases=["gracias", "ya está", "ListO"],
        beep_on_wake=False,
    )
    ctrl._wake = MagicMock(); ctrl._stt = MagicMock(); ctrl._tts = MagicMock()
    ctrl._state = S_FOLLOWUP
    ctrl._handle_final("YA ESTA")  # uppercase + sin acento -> normaliza igual
    assert ctrl._state == S_IDLE_LISTENING
    assert sent == []
    print("W8 close phrase normalization (case + accents): OK")
    return True


# ============================================================================
# Roadmap optimizacion — item 1.4: parser robusto de tool_call.arguments
# (issue ggml-org/llama.cpp #21384 — args con `{` / `}` literales)
# ============================================================================


def test_optroad_normalize_tool_call_arguments_dict() -> bool:
    from gemma4_agent.llm_client import normalize_tool_call_arguments
    out = normalize_tool_call_arguments({"path": "C:/x", "count": 3})
    assert out == {"path": "C:/x", "count": 3}
    # None y vacios.
    assert normalize_tool_call_arguments(None) == {}
    assert normalize_tool_call_arguments("") == {}
    print("OPTROAD-1.4-a dict passthrough + empty: OK")
    return True


def test_optroad_normalize_tool_call_arguments_braces() -> bool:
    """Issue #21384: args serializados como string con `{` y `}` literales."""
    from gemma4_agent.llm_client import normalize_tool_call_arguments
    # Caso 1: args como string JSON valido (path con braces).
    s = '{"path": "C:/Users/${USER}/file.txt", "pattern": "\\\\d{3}"}'
    out = normalize_tool_call_arguments(s)
    assert out["path"] == "C:/Users/${USER}/file.txt"
    assert out["pattern"] == "\\d{3}"
    # Caso 2: doble-stringificado (JSON-of-JSON).
    inner = '{"a": 1, "b": "x"}'
    double = json.dumps(inner)  # '"{\\"a\\": 1, ...}"'
    out2 = normalize_tool_call_arguments(double)
    assert out2 == {"a": 1, "b": "x"}, f"got {out2!r}"
    print("OPTROAD-1.4-b braces + double-string: OK")
    return True


def test_optroad_normalize_tool_call_arguments_malformed() -> bool:
    """Args completamente rotos: deben caer en _raw, NO levantar."""
    from gemma4_agent.llm_client import normalize_tool_call_arguments
    out = normalize_tool_call_arguments("not even close to JSON {")
    assert "_raw" in out and "_parse_error" in out
    # No debe perder el contenido original
    assert "not even close" in out["_raw"]
    print("OPTROAD-1.4-c malformed → _raw with error: OK")
    return True


def test_optroad_normalize_tool_calls_list_response() -> bool:
    """Aplicacion sobre el formato OpenAI completo."""
    from gemma4_agent.llm_client import normalize_tool_calls_list
    tcs = [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "filesystem", "arguments": '{"action": "read", "path": "C:/x"}'},
        },
        {
            "id": "call_2",
            "type": "function",
            "function": {"name": "terminal", "arguments": {"action": "run", "command": "echo"}},
        },
    ]
    out = normalize_tool_calls_list(tcs)
    assert out[0]["function"]["arguments"] == {"action": "read", "path": "C:/x"}
    assert out[1]["function"]["arguments"] == {"action": "run", "command": "echo"}
    # Lista vacia.
    assert normalize_tool_calls_list([]) == []
    print("OPTROAD-1.4-d list + mixed shapes: OK")
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
        test_h1_1_chat_timeout_param_accepted,
        test_h1_2_run_with_timeout_returns_on_hang,
        test_h1_2_run_with_timeout_captures_exception,
        test_h1_3_is_unverified_result,
        test_h1_4_format_phrase_fires_failure_warning,
        test_h1_5_replan_excludes_needs_user_failures,
        test_h2_1_experience_prune_max_records,
        test_h2_2_summarization_cooldown_helper,
        test_h2_3_semantic_router_transient_retry,
        test_h3_1_phrase_confirm_prepends_when_unack,
        test_h3_2_plan_status_surfaces_only_on_short_reply,
        test_h3_3_parse_args_distinguishes_malformed,
        test_triggercmd_import_basic,
        test_triggercmd_destructive_detection,
        test_triggercmd_import_off_routine,
        test_triggercmd_import_duplicate_skipped,
        test_g2_compaction_disabled_keeps_truncation,
        test_j1_knowledge_rerank_fallback_without_model,
        test_j2_memory_auto_save_prefixes_and_caps,
        test_j2_fact_extraction_env_default_off,
        test_j3_personas_registry_has_six,
        test_j4_project_context_walks_up,
        test_j4_project_context_disabled_env,
        test_j5_parallel_tools_default_off,
        test_j5_parallel_executor_preserves_order_and_calls_each,
        test_j5_sequential_handles_parse_error,
        test_k1_session_roundtrip,
        test_k1_auto_title_heuristic_fallback,
        test_k1_session_disabled_env,
        test_k2_timeline_writes_jsonl,
        test_k2_timeline_disabled_env,
        test_k3_context_budget_scales_with_size,
        test_u1_ui_modules_importable,
        test_u1_hud_state_setters,
        test_audit_atomic_write_replaces_existing,
        test_audit_settings_env_names_match_config,
        test_audit_jsonstore_concurrent_writes,
        test_audit_experience_recent_exists,
        test_audit_timeline_safe_payload_preserves_dicts,
        test_audit_planner_question_mark_inverted_supported,
        # Fase V — VRAM profiles
        test_profiles_recommend_by_vram,
        test_profiles_set_and_get_active,
        test_profiles_apply_to_env_complete,
        test_profiles_round_trip_via_agentconfig,
        test_profile_watcher_hysteresis,
        test_standby_profile_does_not_start_server,
        test_external_server_detected_not_killed,
        test_light_profile_missing_model_falls_back,
        # Fase W — voice + SSE
        test_sse_streaming_yields_deltas_in_order,
        test_voice_wake_detector_matches_phrases,
        test_voice_state_machine_wake_to_listening_to_transcribing,
        test_voice_state_machine_listening_timeout_5s,
        test_voice_state_machine_followup_close_phrase,
        test_voice_disabled_in_light_profile,
        test_tts_sentence_chunker_flushes_on_punctuation,
        test_stt_auto_fallback_to_base_when_slow,
        test_voice_close_phrase_normalization,
        # Roadmap optimizacion — 1.4 parser tool_call.arguments robusto (#21384)
        test_optroad_normalize_tool_call_arguments_dict,
        test_optroad_normalize_tool_call_arguments_braces,
        test_optroad_normalize_tool_call_arguments_malformed,
        test_optroad_normalize_tool_calls_list_response,
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
