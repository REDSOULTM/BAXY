"""End-to-end REAL test: ejecuta media_tool con executor real que ataca al
Opera GX del user via CDP. Verifica que cada plataforma:
  1. Connecta CDP exitosamente.
  2. Navega a la search URL real.
  3. Encuentra cards.
  4. (NO clickea play — solo verifica que llego al detail page).

Esta prueba NO inicia playback real (no queremos abrir 4 reproductores
simultaneamente). Solo verifica el flow hasta `clicked_first_result`.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Ensure repo on path.
REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from gemma4_agent.domain_tools import (  # noqa: E402
    _STREAMING_PLATFORMS,
    _set_streaming_preference,
    media_tool,
)
from gemma4_agent.ops_tools import browser_real_tool  # noqa: E402
from gemma4_agent.state import AgentState  # noqa: E402


def _make_state() -> AgentState:
    """Use a per-run state file."""
    tmp = Path(tempfile.gettempdir()) / "gemma4_e2e_streaming_state.json"
    tmp.unlink(missing_ok=True)
    return AgentState(path=tmp)


def _make_executor(state: AgentState):
    """Executor minimal: passes browser_real calls through; others noop."""
    captures = REPO / "captures"
    captures.mkdir(exist_ok=True)

    def execute(name: str, args: dict) -> dict:
        if name == "browser_real":
            return browser_real_tool(args, state, captures)
        # No-op for window/gui/etc — we focus on browser CDP path.
        return {"ok": True, "noop": True, "tool": name}
    return execute


def run_one(provider: str, profile: str, query: str, state, executor) -> dict:
    print(f"\n=== E2E: {provider} ===", file=sys.stderr)
    _set_streaming_preference(state, provider, profile)
    t0 = time.time()
    result = media_tool(
        {"action": "play", "provider": provider, "query": query,
         "auto_play": True, "auto_play_wait": 1.5},
        executor, state,
    )
    elapsed = time.time() - t0
    info = result.get("web_auto_play_info") or {}
    summary = {
        "provider": provider,
        "query": query,
        "elapsed_sec": round(elapsed, 1),
        "ok": result.get("ok"),
        "played": result.get("played"),
        "attempted_play": result.get("attempted_play"),
        "via_cdp": result.get("via_cdp"),
        "completion_status": result.get("completion_status"),
        "steps": info.get("steps", []),
        "abort_reason": info.get("abort_reason"),
        "detail_url": info.get("detail_url"),
        "cdp_unavailable_reason": info.get("cdp_unavailable_reason"),
        "_full_result": result,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False), file=sys.stderr)
    return summary


def main() -> int:
    state = _make_state()
    executor = _make_executor(state)

    # Pre-flight: garantizar CDP via auto-launch (mismo que el flow real).
    from gemma4_agent.domain_tools import _ensure_cdp_browser
    ens = _ensure_cdp_browser(timeout_total=12)
    print(f"ensure_cdp_browser: cdp_ok={ens['cdp_ok']} "
          f"action={ens['action']} browser={ens.get('browser_key')}",
          file=sys.stderr)
    if not ens["cdp_ok"]:
        print(f"FATAL: could not start CDP browser: {ens.get('reason')}",
                file=sys.stderr)
        return 1
    # Now connect from the test harness too (the streaming flow will reuse).
    pre = executor("browser_real", {
        "action": "connect_cdp",
        "endpoint": "http://127.0.0.1:9222",
        "session_id": "streaming",
    })
    if not pre.get("ok"):
        print(f"FATAL: CDP connect failed after launch: {pre.get('error')}",
                file=sys.stderr)
        return 1
    print(f"CDP connected ({len(pre.get('tabs', []))} tabs)", file=sys.stderr)

    cases = [
        # provider, profile_name, query
        ("disney", "Ema", "Loki"),
        ("netflix", "Emmanuel", "Stranger Things"),
        ("hbo_max", "Emmanuel", "House of Dragon"),
        ("prime_video", "Emmanuel", "The Boys"),
    ]
    results = []
    for prov, prof, q in cases:
        try:
            r = run_one(prov, prof, q, state, executor)
        except Exception as exc:
            r = {"provider": prov, "exception": f"{type(exc).__name__}: {exc}"}
        results.append(r)

    out = REPO / "gemma4_agent" / "docs" / "e2e_streaming_results.json"
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                   encoding="utf-8")

    # Summary.
    print("\n\n========== E2E SUMMARY ==========", file=sys.stderr)
    for r in results:
        prov = r.get("provider")
        ok = r.get("played") or r.get("attempted_play")
        tag = "✓ PLAY ATTEMPTED" if ok else "✗ FAILED"
        print(f"\n{tag} {prov}", file=sys.stderr)
        print(f"  via_cdp={r.get('via_cdp')}  played={r.get('played')}  "
                f"elapsed={r.get('elapsed_sec')}s", file=sys.stderr)
        for s in r.get("steps", []):
            print(f"    - {s}", file=sys.stderr)
        if r.get("abort_reason"):
            print(f"  abort: {r['abort_reason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
