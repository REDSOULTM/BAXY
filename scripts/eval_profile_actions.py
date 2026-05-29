"""Deep action-reliability eval for a running llama-server (a profile's model).

Runs a battery of realistic voice commands through the FULL agent and measures
whether each one that SHOULD call a tool actually does, plus latency. Used to
stress-test the small profiles (vram3/vram4) and find failure clusters.

Assumes a llama-server is already healthy on :8080 with the profile's model.
Run:  python scripts/eval_profile_actions.py [--runs N] [--label NAME]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# (command, should_call_tool)  — expected behavior. True = a domain tool MUST
# be invoked; False = it's chat/knowledge, no tool needed.
BATTERY: list[tuple[str, bool]] = [
    # ---- ES single action ----
    ("abre steam", True),
    ("pon música en spotify", True),
    ("saca un screenshot", True),
    ("sube el volumen", True),
    ("mutea el sonido", True),
    ("cierra la ventana", True),
    ("minimiza todo", True),
    ("abre la calculadora", True),
    ("reproduce una canción", True),
    ("pausa la música", True),
    # ---- ES multi-step ----
    ("abre chrome y busca gatos", True),
    ("abre spotify y pon rock", True),
    # ---- EN single action ----
    ("open steam", True),
    ("take a screenshot", True),
    ("turn up the volume", True),
    ("close the window", True),
    ("play some music", True),
    # ---- other langs ----
    ("ouvre le navigateur", True),       # fr
    ("schließe das fenster", True),      # de
    ("apri spotify", True),              # it
    # ---- knowledge / chat (should NOT need a tool) ----
    ("hola", False),
    ("gracias", False),
    ("quién es batman", False),          # may pull web, but ok either way
    ("cómo estás", False),
]


def run_battery(runs: int, label: str) -> None:
    os.environ.setdefault("GEMMA4_AGENT_CONTEXT", "16384")
    from gemma4_agent.agent_core.agent import Gemma4Agent
    from gemma4_agent.infra.config import AgentConfig
    ag = Gemma4Agent(AgentConfig.from_env())

    results: dict[str, list[bool]] = defaultdict(list)
    latencies: dict[str, list[float]] = defaultdict(list)
    fails: list[tuple[str, str]] = []

    for cmd, should_call in BATTERY:
        for _ in range(runs):
            seen: list[str] = []

            def progress(*a, **k):
                if a and isinstance(a[0], str):
                    seen.append(a[0])

            t = time.time()
            try:
                r = ag.run_text(cmd, progress=progress)
            except TypeError:
                r = ag.run_text(cmd)
            dt = time.time() - t
            called = any("tool_start" in s or "tool_end" in s for s in seen)
            latencies[cmd].append(dt)
            # success = called when expected, OR (not called) when not expected
            ok = (called == should_call) if should_call else True
            results[cmd].append(ok)
            if should_call and not called:
                reply = (getattr(r, "content", None) or str(r))[:60]
                fails.append((cmd, reply))

    print(f"\n==== ACTION EVAL [{label}] runs={runs} ====")
    total_ok = total = 0
    for cmd, should_call in BATTERY:
        oks = results[cmd]
        rate = sum(oks) / max(1, len(oks))
        avg = sum(latencies[cmd]) / max(1, len(latencies[cmd]))
        total_ok += sum(oks); total += len(oks)
        flag = "" if rate == 1.0 else ("  <-- FAIL" if should_call else "  <-- over")
        kind = "ACT" if should_call else "chat"
        print(f"  [{kind}] {cmd[:34]:36s} {sum(oks)}/{len(oks)} avg {avg:4.1f}s{flag}")
    print(f"\n  OVERALL: {total_ok}/{total} = {total_ok/max(1,total):.3f}")
    if fails:
        print(f"\n  FAILURE SAMPLES ({len(fails)}):")
        seen_cmds = set()
        for cmd, reply in fails:
            if cmd in seen_cmds:
                continue
            seen_cmds.add(cmd)
            print(f"    {cmd!r}: {reply!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--label", default="profile")
    args = ap.parse_args()
    run_battery(args.runs, args.label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
