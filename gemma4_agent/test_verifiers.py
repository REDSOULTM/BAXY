"""Tests para verify_core y verifiers concretos.

NO toca llama-server ni LLM. Usa mocks de result/args para exercer cada
verifier. Verificaciones que requieren estado real del SO (psutil, pycaw,
win32gui, filesystem write) se test con tmp paths o assertions sobre
confirmed=None cuando la dep no esta.

Run:
    python -m gemma4_agent.test_verifiers
    pytest gemma4_agent/test_verifiers.py -q
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Importar verifiers (registra todo via decorators)
from gemma4_agent import verifiers as _v  # noqa: F401
from gemma4_agent.verify_core import (
    VerifierOutcome,
    collect_evidence_keys,
    register_verifier,
    registered_tool_names,
    summarize_verifiers,
    verify,
)


# ============================================================================
# Core registry / decorator
# ============================================================================

def test_registered_tool_names_includes_hot_tools() -> None:
    names = set(registered_tool_names())
    expected = {"app", "steam", "window", "filesystem", "audio",
                "terminal", "gui", "clipboard", "web", "system",
                "memory", "verify"}
    missing = expected - names
    assert not missing, f"verifiers faltantes: {missing}"


def test_unknown_tool_returns_none() -> None:
    outcome = verify("nonexistent_tool_xyz", {}, {"ok": True})
    assert outcome.confirmed is None
    assert outcome.reason == "no_verifier_registered"


def test_verifier_crash_returns_failed() -> None:
    """Si un verifier crashea, el core devuelve confirmed=False con la excepcion."""
    @register_verifier("__crashy_test")
    def _crashy(args, result):
        raise RuntimeError("intentional crash")
    outcome = verify("__crashy_test", {}, {"ok": True})
    assert outcome.confirmed is False
    assert "verifier crashed" in outcome.reason
    assert "RuntimeError" in outcome.reason


def test_verifier_returning_non_outcome_handled() -> None:
    """Si un verifier devuelve algo raro, el core no crashea."""
    @register_verifier("__weird_return_test")
    def _weird(args, result):
        return {"ok": True}  # no es VerifierOutcome
    outcome = verify("__weird_return_test", {}, {"ok": True})
    assert outcome.confirmed is False
    assert "non-VerifierOutcome" in outcome.reason


def test_opt_out_via_env() -> None:
    os.environ["GEMMA4_VERIFIER_OFF"] = "1"
    try:
        outcome = verify("app", {"action": "open", "name": "X"},
                         {"ok": True, "verified": True})
        assert outcome.confirmed is None
        assert outcome.reason == "disabled_by_env"
    finally:
        os.environ.pop("GEMMA4_VERIFIER_OFF", None)


# ============================================================================
# summarize_verifiers
# ============================================================================

def test_summarize_empty_returns_empty_string() -> None:
    assert summarize_verifiers([]) == ""


def test_summarize_all_confirmed_returns_empty_string() -> None:
    """Si todo OK, no agrega footer (no inflar el reply)."""
    outcomes = [
        VerifierOutcome("app", True, "ok"),
        VerifierOutcome("audio", True, "ok"),
    ]
    assert summarize_verifiers(outcomes) == ""


def test_summarize_mixed_shows_counts() -> None:
    outcomes = [
        VerifierOutcome("app", True, "ok"),
        VerifierOutcome("audio", False, "fail"),
        VerifierOutcome("gui", None, "no_verifier"),
    ]
    footer = summarize_verifiers(outcomes)
    assert "1 verificada(s)" in footer
    assert "1 no confirmada(s)" in footer
    assert "1 no verificable(s)" in footer
    assert footer.startswith("\n\n[") and footer.endswith("]")


def test_collect_evidence_only_from_confirmed_true() -> None:
    outcomes = [
        VerifierOutcome("app", True, "ok", evidence_keys=["app:Steam"]),
        VerifierOutcome("audio", False, "fail", evidence_keys=["volume:50"]),  # should NOT be collected
        VerifierOutcome("gui", None, "n/a", evidence_keys=["screenshot:x"]),   # should NOT
    ]
    keys = collect_evidence_keys(outcomes)
    assert keys == ["app:Steam"], f"got {keys}"


# ============================================================================
# verify_app
# ============================================================================

def test_app_search_with_matches_confirmed() -> None:
    outcome = verify("app",
                     {"action": "search", "query": "code"},
                     {"ok": True, "matches": [{"name": "Code"}, {"name": "VSCode"}]})
    assert outcome.confirmed is True
    assert "2 matches" in outcome.reason


def test_app_open_with_tool_self_verify_confirmed() -> None:
    """Si la tool ya hizo auto-verify y dice True, el verifier confia."""
    outcome = verify("app",
                     {"action": "open", "name": "Notepad"},
                     {"ok": True, "verified": True})
    assert outcome.confirmed is True
    assert "app:Notepad" in outcome.evidence_keys


def test_app_open_failed_tool_returns_failed() -> None:
    outcome = verify("app",
                     {"action": "open", "name": "FakeApp"},
                     {"ok": False, "error": "app not found"})
    assert outcome.confirmed is False


def test_app_close_not_running_fast_path() -> None:
    outcome = verify("app",
                     {"action": "close", "name": "OperaThatNeverRan"},
                     {"ok": True, "not_running": True, "closed": False})
    assert outcome.confirmed is True
    assert "closed" in outcome.evidence_keys[0]


def test_app_uninstall_unverifiable() -> None:
    outcome = verify("app",
                     {"action": "uninstall", "name": "X"},
                     {"ok": True})
    assert outcome.confirmed is None
    assert "async" in outcome.reason


# ============================================================================
# verify_terminal
# ============================================================================

def test_terminal_exit_zero_confirmed() -> None:
    outcome = verify("terminal",
                     {"command": "echo hi"},
                     {"ok": True, "exit_code": 0, "stdout": "hi"})
    assert outcome.confirmed is True


def test_terminal_exit_nonzero_failed() -> None:
    outcome = verify("terminal",
                     {"command": "exit 1"},
                     {"ok": True, "exit_code": 1, "stderr": "boom"})
    assert outcome.confirmed is False
    assert "exit_code=1" in outcome.reason


def test_terminal_timeout_status_failed() -> None:
    outcome = verify("terminal",
                     {"command": "sleep 999"},
                     {"ok": False, "status": "timeout", "timeout_sec": 60})
    assert outcome.confirmed is False
    assert "timed out" in outcome.reason


# ============================================================================
# verify_filesystem
# ============================================================================

def test_filesystem_write_with_tool_self_verify() -> None:
    outcome = verify("filesystem",
                     {"action": "write", "path": "/tmp/x.txt", "content": "hi"},
                     {"ok": True, "verified": True, "bytes": 2, "path": "/tmp/x.txt"})
    assert outcome.confirmed is True
    assert "file:/tmp/x.txt" in outcome.evidence_keys


def test_filesystem_write_real_stat() -> None:
    """Sin tool_self_verify, el verifier hace stat real con tmpfile."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False) as f:
        f.write("hello world")
        path = f.name
    try:
        outcome = verify("filesystem",
                         {"action": "write", "path": path, "content": "hello world"},
                         {"ok": True, "path": path})  # NO verified flag
        assert outcome.confirmed is True
        assert path in outcome.detail["size"].__class__.__name__ or outcome.detail["size"] > 0
    finally:
        Path(path).unlink(missing_ok=True)


def test_filesystem_write_missing_file_failed() -> None:
    outcome = verify("filesystem",
                     {"action": "write", "path": "/tmp/does_not_exist_xyz.txt"},
                     {"ok": True})
    assert outcome.confirmed is False
    assert "no existe" in outcome.reason


def test_filesystem_delete_absent_confirmed() -> None:
    nonexistent = "/tmp/this_should_not_exist_after_delete.txt"
    Path(nonexistent).unlink(missing_ok=True)
    outcome = verify("filesystem",
                     {"action": "delete", "path": nonexistent},
                     {"ok": True})
    assert outcome.confirmed is True


def test_filesystem_list_readonly_confirmed() -> None:
    outcome = verify("filesystem",
                     {"action": "list", "path": "/tmp"},
                     {"ok": True, "items": []})
    assert outcome.confirmed is True


# ============================================================================
# verify_window
# ============================================================================

def test_window_list_confirmed() -> None:
    outcome = verify("window", {"action": "list"},
                     {"ok": True, "windows": [{"title": "A"}, {"title": "B"}]})
    assert outcome.confirmed is True
    assert outcome.detail["count"] == 2


def test_window_active_with_title_confirmed() -> None:
    outcome = verify("window", {"action": "active"},
                     {"ok": True, "active": {"title": "Notepad - Untitled",
                                              "pid": 1234, "process": "notepad.exe"}})
    assert outcome.confirmed is True


def test_window_focus_when_inner_fails_failed() -> None:
    outcome = verify("window",
                     {"action": "focus", "title": "X"},
                     {"ok": True, "result": {"ok": False, "error": "window not found"}})
    assert outcome.confirmed is False


# ============================================================================
# verify_audio
# ============================================================================

def test_audio_set_volume_with_tool_verify() -> None:
    outcome = verify("audio",
                     {"action": "set_volume", "level": 50},
                     {"ok": True, "verified": True, "level": 50})
    assert outcome.confirmed is True
    assert "volume:50" in outcome.evidence_keys


def test_audio_mute_with_verified_flag() -> None:
    outcome = verify("audio",
                     {"action": "mute", "state": True},
                     {"ok": True, "verified": True, "muted": True})
    assert outcome.confirmed is True


def test_audio_get_volume_confirmed() -> None:
    outcome = verify("audio", {"action": "get_volume"},
                     {"ok": True, "level": 75, "muted": False})
    assert outcome.confirmed is True


# ============================================================================
# verify_steam
# ============================================================================

def test_steam_launch_game_unverifiable() -> None:
    """launch_game es async; el verifier reporta None honestamente."""
    outcome = verify("steam",
                     {"action": "launch_game", "query": "Doom"},
                     {"ok": True, "matched_game": {"name": "Doom Eternal"}})
    assert outcome.confirmed is None


def test_steam_list_games_confirmed() -> None:
    outcome = verify("steam", {"action": "list_games"},
                     {"ok": True, "count": 42})
    assert outcome.confirmed is True


# ============================================================================
# verify_gui
# ============================================================================

def test_gui_screenshot_with_real_file() -> None:
    """Crea un PNG fake con bytes suficientes para pasar la heuristica."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG\r\n" + b"\x00" * 2000)  # bytes para que pase size>1000
        path = f.name
    try:
        outcome = verify("gui",
                         {"action": "screenshot"},
                         {"ok": True, "image_path": path})
        assert outcome.confirmed is True
        assert "screenshot" in outcome.evidence_keys[0]
    finally:
        Path(path).unlink(missing_ok=True)


def test_gui_screenshot_missing_file_failed() -> None:
    outcome = verify("gui",
                     {"action": "screenshot"},
                     {"ok": True, "image_path": "/tmp/nonexistent_screenshot.png"})
    assert outcome.confirmed is False


def test_gui_click_unverifiable() -> None:
    """gui inputs son fire-and-forget; sin screenshot adicional no se mide."""
    outcome = verify("gui",
                     {"action": "click", "x": 100, "y": 200},
                     {"ok": True})
    assert outcome.confirmed is None


# ============================================================================
# verify_clipboard
# ============================================================================

def test_clipboard_read_with_content_confirmed() -> None:
    outcome = verify("clipboard", {"action": "read"},
                     {"ok": True, "content": "hello"})
    assert outcome.confirmed is True


def test_clipboard_write_unverifiable_for_privacy() -> None:
    outcome = verify("clipboard",
                     {"action": "write", "content": "x"},
                     {"ok": True, "wrote_chars": 1})
    assert outcome.confirmed is None
    assert "privacidad" in outcome.reason


# ============================================================================
# verify_web
# ============================================================================

def test_web_search_confirmed() -> None:
    outcome = verify("web",
                     {"action": "search", "query": "python"},
                     {"ok": True, "count": 5, "engine": "duckduckgo"})
    assert outcome.confirmed is True


def test_web_open_unverifiable() -> None:
    outcome = verify("web",
                     {"action": "open", "url": "https://example.com"},
                     {"ok": True})
    assert outcome.confirmed is None


def test_web_research_with_sources_confirmed() -> None:
    outcome = verify("web",
                     {"action": "research", "query": "x"},
                     {"ok": True, "source_count": 3})
    assert outcome.confirmed is True


def test_web_research_zero_sources_unverifiable() -> None:
    outcome = verify("web",
                     {"action": "research", "query": "x"},
                     {"ok": True, "source_count": 0})
    assert outcome.confirmed is None


# ============================================================================
# verify_system
# ============================================================================

def test_system_time_confirmed() -> None:
    outcome = verify("system", {"action": "time"},
                     {"ok": True, "iso": "2026-05-15T18:00:00", "human": "18:00"})
    assert outcome.confirmed is True


def test_system_processes_confirmed() -> None:
    outcome = verify("system", {"action": "processes"},
                     {"ok": True, "processes": [{"name": "x.exe"}]})
    assert outcome.confirmed is True


def test_system_shutdown_unverifiable() -> None:
    outcome = verify("system", {"action": "shutdown"},
                     {"ok": True})
    assert outcome.confirmed is None


# ============================================================================
# verify (meta) is self-skip
# ============================================================================

def test_verify_meta_self_skip() -> None:
    outcome = verify("verify",
                     {"action": "app_opened", "name": "X"},
                     {"ok": True, "found": True})
    assert outcome.confirmed is None
    assert "self-skip" in outcome.reason


# ============================================================================
# verify_memory
# ============================================================================

def test_memory_save_confirmed() -> None:
    outcome = verify("memory",
                     {"action": "save", "key": "user.name", "value": "Ana"},
                     {"ok": True, "key": "user.name"})
    assert outcome.confirmed is True
    assert "memory:user.name" in outcome.evidence_keys


def test_memory_recall_confirmed() -> None:
    outcome = verify("memory", {"action": "recall"},
                     {"ok": True, "items": {"a": 1, "b": 2}})
    assert outcome.confirmed is True


# ============================================================================
# Runner
# ============================================================================
TESTS = [
    # core
    test_registered_tool_names_includes_hot_tools,
    test_unknown_tool_returns_none,
    test_verifier_crash_returns_failed,
    test_verifier_returning_non_outcome_handled,
    test_opt_out_via_env,
    # summarize
    test_summarize_empty_returns_empty_string,
    test_summarize_all_confirmed_returns_empty_string,
    test_summarize_mixed_shows_counts,
    test_collect_evidence_only_from_confirmed_true,
    # app
    test_app_search_with_matches_confirmed,
    test_app_open_with_tool_self_verify_confirmed,
    test_app_open_failed_tool_returns_failed,
    test_app_close_not_running_fast_path,
    test_app_uninstall_unverifiable,
    # terminal
    test_terminal_exit_zero_confirmed,
    test_terminal_exit_nonzero_failed,
    test_terminal_timeout_status_failed,
    # filesystem
    test_filesystem_write_with_tool_self_verify,
    test_filesystem_write_real_stat,
    test_filesystem_write_missing_file_failed,
    test_filesystem_delete_absent_confirmed,
    test_filesystem_list_readonly_confirmed,
    # window
    test_window_list_confirmed,
    test_window_active_with_title_confirmed,
    test_window_focus_when_inner_fails_failed,
    # audio
    test_audio_set_volume_with_tool_verify,
    test_audio_mute_with_verified_flag,
    test_audio_get_volume_confirmed,
    # steam
    test_steam_launch_game_unverifiable,
    test_steam_list_games_confirmed,
    # gui
    test_gui_screenshot_with_real_file,
    test_gui_screenshot_missing_file_failed,
    test_gui_click_unverifiable,
    # clipboard
    test_clipboard_read_with_content_confirmed,
    test_clipboard_write_unverifiable_for_privacy,
    # web
    test_web_search_confirmed,
    test_web_open_unverifiable,
    test_web_research_with_sources_confirmed,
    test_web_research_zero_sources_unverifiable,
    # system
    test_system_time_confirmed,
    test_system_processes_confirmed,
    test_system_shutdown_unverifiable,
    # meta
    test_verify_meta_self_skip,
    # memory
    test_memory_save_confirmed,
    test_memory_recall_confirmed,
]


def main() -> int:
    failures = 0
    for t in TESTS:
        try:
            ok = t()
            if not ok:
                print(f"[FAIL] {t.__name__}: returned falsy")
                failures += 1
        except AssertionError as exc:
            print(f"[FAIL] {t.__name__}: {exc}")
            failures += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {t.__name__}: {type(exc).__name__}: {exc}")
            failures += 1
    total = len(TESTS)
    print(f"\n{total - failures}/{total} pass")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
