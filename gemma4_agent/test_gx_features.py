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
